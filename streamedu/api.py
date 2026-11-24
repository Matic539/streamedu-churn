"""Microservicio FastAPI (Script 4, bonus de la guía), corregido.

- Carga el modelo UNA vez al iniciar (el docente lo cargaba en cada petición).
- Valida rangos y rechaza campos extra (422); avisa si un valor está fuera del rango de entrenamiento.
- Si no hay modelo responde 503; si Atlas no responde, igual entrega la predicción con
  `sincronizado_mongodb_cloud: false` (el docente respondía 500 y se perdía el resultado).
- El registro en Atlas guarda el id del cliente, no su nombre (minimización de datos).
- Se ejecuta solo en 127.0.0.1 y sin --reload.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .config import CUOTA_MENSUAL_USD, FEATURES, ConfigError, dir_modelos, leer_config_mongo
from .db import COL_API_LOG, ConexionError, conectar
from .modelo import IntegridadError, ModeloNoEntrenadoError, cargar_artefactos
from .negocio import aplicar_logica_negocio

log = logging.getLogger("streamedu.api")


class ClienteInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={"examples": [{
            "customer_id": "ACT-999", "nombre": "Sofia Vargas", "meses_antiguedad": 10,
            "horas_uso_semanal": 1.5, "tickets_soporte": 4, "fallos_pago": 1,
            "dias_sin_conectar": 18, "cuota_mensual": 29.0,
        }]},
    )

    customer_id: str = Field(..., pattern=r"^ACT-[0-9]{3,6}$", max_length=10)
    nombre: str = Field(..., min_length=1, max_length=80)
    meses_antiguedad: int = Field(..., ge=1, le=120)
    horas_uso_semanal: float = Field(..., ge=0.0, le=168.0, allow_inf_nan=False)
    tickets_soporte: int = Field(..., ge=0, le=50)
    fallos_pago: int = Field(..., ge=0, le=12)
    dias_sin_conectar: int = Field(..., ge=0, le=365)
    cuota_mensual: float = Field(default=CUOTA_MENSUAL_USD, gt=0, le=1000, allow_inf_nan=False)


class _Estado:
    artefactos = None
    error_modelo: str | None = None
    db = None
    cliente_mongo = None


estado = _Estado()


def _cargar_modelo() -> None:
    try:
        estado.artefactos = cargar_artefactos(dir_modelos())
        estado.error_modelo = None
    except (ModeloNoEntrenadoError, IntegridadError) as e:
        estado.artefactos, estado.error_modelo = None, str(e)


def _base_auditoria():
    """Conexión perezosa con timeout corto. Si falla, la API sigue respondiendo."""
    if estado.db is not None:
        return estado.db
    try:
        uri, db_name = leer_config_mongo()
        estado.cliente_mongo, estado.db = conectar(uri, db_name, timeout_ms=3000)
    except (ConfigError, ConexionError) as e:
        log.warning("Auditoría en Atlas no disponible: %s", e)
        return None
    return estado.db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _cargar_modelo()
    yield
    if estado.cliente_mongo is not None:
        estado.cliente_mongo.close()


app = FastAPI(
    title="StreamEdu: API de predicción de churn con Deep Learning",
    description="Evalúa el riesgo de fuga de un estudiante y registra la decisión en MongoDB Atlas.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/salud")
def salud():
    return {
        "modelo_cargado": estado.artefactos is not None,
        "modelo_version": estado.artefactos.version if estado.artefactos else None,
        "detalle": estado.error_modelo,
    }


@app.post("/evaluar-cliente")
def evaluar_cliente_endpoint(datos: ClienteInput):
    if estado.artefactos is None:
        raise HTTPException(status_code=503, detail="Modelo no disponible: ejecuta primero 2_train_model.py")
    cliente = datos.model_dump()
    prob = float(estado.artefactos.predecir([cliente])[0])
    decision = aplicar_logica_negocio(cliente, prob)

    rangos = estado.artefactos.metadata.get("rangos_entrenamiento", {})
    fuera = [f for f in FEATURES if f in rangos and not rangos[f][0] <= cliente[f] <= rangos[f][1]]

    sincronizado = False
    db = _base_auditoria()
    if db is not None:
        try:
            db[COL_API_LOG].insert_one({
                "customer_id": datos.customer_id,
                "variables": {f: cliente[f] for f in (*FEATURES, "cuota_mensual")},
                "probabilidad_churn": decision["probabilidad_usada"],
                "decision_negocio": decision,
                "modelo_version": estado.artefactos.version,
                "fecha": datetime.now(timezone.utc),
            })
            sincronizado = True
        except Exception as e:  # noqa: BLE001 (la auditoría nunca debe botar la respuesta)
            log.warning("No se pudo registrar en Atlas: %s", type(e).__name__)

    return {
        "customer_id": datos.customer_id,
        "nombre": datos.nombre,
        "probabilidad_abandono_porcentaje": round(decision["probabilidad_usada"] * 100, 2),
        "analisis_negocio": decision,
        "fuera_de_rango_entrenamiento": fuera,
        "modelo_version": estado.artefactos.version,
        "sincronizado_mongodb_cloud": sincronizado,
    }


def ejecutar(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=int(os.getenv("STREAMEDU_PUERTO", port)), reload=False)
