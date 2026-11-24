"""Pipeline de producción: predice el abandono de los clientes activos y deja las acciones en MongoDB.

Diferencias con el script del docente:
- Idempotente: cada cliente tiene a lo más UNA acción pendiente. Volver a ejecutar actualiza esa
  acción en vez de duplicarla; si el riesgo baja a BAJO, la acción pendiente se marca descartada.
- Cada ejecución queda registrada en `evaluaciones` con su id de corrida y la versión del modelo.
- Valida cada documento antes de predecir: un cliente mal cargado se informa y se omite,
  sin detener a los demás.
- Escribe en bloque (bulk_write) en vez de un update por cliente.
"""
from __future__ import annotations

import math
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pymongo import UpdateMany, UpdateOne

from .config import FEATURES, RANGOS
from .db import COL_ACCIONES, COL_ACTIVOS, COL_EVALUACIONES, ESTADO_DESCARTADA, ESTADO_PENDIENTE
from .negocio import NIVEL_BAJO, aplicar_logica_negocio, formato_usd


def validar_cliente(doc: dict) -> list[str]:
    errores = []
    if not isinstance(doc.get("customer_id"), str) or not doc["customer_id"].strip():
        errores.append("customer_id vacío")
    if not isinstance(doc.get("nombre"), str) or not doc["nombre"].strip():
        errores.append("nombre vacío")
    for campo, (minimo, maximo, tipo) in RANGOS.items():
        valor = doc.get(campo)
        if campo == "cuota_mensual" and valor is None:
            continue  # la regla usa 29 por defecto, igual que la guía
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            errores.append(f"{campo} no es numérico")
        elif tipo is int and not float(valor).is_integer():
            errores.append(f"{campo} debe ser entero")
        elif not math.isfinite(float(valor)) or not minimo <= valor <= maximo:
            errores.append(f"{campo} fuera de rango [{minimo}, {maximo}]")
    return errores


@dataclass
class ResumenCorrida:
    corrida_id: str
    fecha: datetime
    modelo_version: str
    filas: list[dict] = field(default_factory=list)
    omitidos: list[dict] = field(default_factory=list)

    @property
    def costo_total(self) -> float:
        return round(sum(f["decision"]["presupuesto_asignado_usd"] for f in self.filas), 2)

    def conteo_niveles(self) -> dict:
        return dict(Counter(f["decision"]["clasificacion"] for f in self.filas))


def ejecutar_pipeline(db, artefactos, ahora: datetime | None = None) -> ResumenCorrida:
    ahora = ahora or datetime.now(timezone.utc)
    corrida_id = f"{ahora:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    resumen = ResumenCorrida(corrida_id, ahora, artefactos.version)

    clientes = list(db[COL_ACTIVOS].find({}).sort("customer_id", 1))
    validos = []
    for c in clientes:
        errores = validar_cliente(c)
        if errores:
            resumen.omitidos.append({"customer_id": c.get("customer_id"), "errores": errores})
        else:
            validos.append(c)

    probabilidades = artefactos.predecir(validos) if validos else []
    ops_activos, ops_acciones = [], []
    for cliente, prob in zip(validos, probabilidades):
        decision = aplicar_logica_negocio(
            {"meses_antiguedad": int(cliente["meses_antiguedad"]), "cuota_mensual": cliente.get("cuota_mensual", 29.0)},
            float(prob),
        )
        p = decision["probabilidad_usada"]
        resumen.filas.append({"cliente": cliente, "probabilidad": p, "decision": decision})
        ops_activos.append(UpdateOne({"_id": cliente["_id"]}, {"$set": {
            "probabilidad_churn": p,
            "riesgo": decision["nivel_riesgo"],
            "clasificacion": decision["clasificacion"],
            "segmento": decision["segmento"],
            "ultima_evaluacion": ahora,
            "corrida_id": corrida_id,
            "modelo_version": artefactos.version,
        }}))
        filtro = {"customer_id": cliente["customer_id"], "estado_campana": ESTADO_PENDIENTE}
        if decision["nivel_riesgo"] == NIVEL_BAJO:
            ops_acciones.append(UpdateMany(filtro, {"$set": {
                "estado_campana": ESTADO_DESCARTADA, "fecha_actualizacion": ahora, "corrida_id": corrida_id,
            }}))
        else:
            ops_acciones.append(UpdateOne(filtro, {
                "$set": {
                    "nombre": cliente["nombre"],
                    "probabilidad_churn": p,
                    "decision_negocio": decision,
                    "corrida_id": corrida_id,
                    "modelo_version": artefactos.version,
                    "fecha_actualizacion": ahora,
                },
                "$setOnInsert": {"fecha_creacion": ahora},
            }, upsert=True))

    if ops_activos:
        db[COL_ACTIVOS].bulk_write(ops_activos, ordered=False)
    if ops_acciones:
        db[COL_ACCIONES].bulk_write(ops_acciones, ordered=True)
    db[COL_EVALUACIONES].insert_one({
        "corrida_id": corrida_id,
        "fecha": ahora,
        "modelo_version": artefactos.version,
        "clientes_evaluados": len(resumen.filas),
        "clientes_omitidos": resumen.omitidos,
        "conteo_por_clasificacion": resumen.conteo_niveles(),
        "presupuesto_total_usd": resumen.costo_total,
    })
    return resumen


def formatear_reporte(resumen: ResumenCorrida) -> str:
    lineas = [
        "=" * 80,
        "REPORTE DE PREDICCION DEEP LEARNING + LOGICA DE NEGOCIO (MONGODB ATLAS)",
        f"Corrida {resumen.corrida_id} | modelo {resumen.modelo_version}",
        "=" * 80,
    ]
    for f in resumen.filas:
        c, d = f["cliente"], f["decision"]
        meses = c["meses_antiguedad"]
        lineas += [
            "",
            f"Cliente: {c['nombre']} ({c['customer_id']}) | Antiguedad: {meses} {'mes' if meses == 1 else 'meses'} (LTV: {formato_usd(d['ltv_acumulado_usd'])})",
            f"   Prediccion Red Neuronal: {f['probabilidad'] * 100:.2f}% probabilidad de abandono",
            f"   Nivel de Riesgo: {d['nivel_riesgo']} | Clasificacion: {d['clasificacion']} | VIP?: {'Si' if d['es_cliente_vip'] else 'No'}",
            f"   Accion de Negocio: {d['accion_comercial']} (Costo: {formato_usd(d['presupuesto_asignado_usd'])})",
        ]
    for o in resumen.omitidos:
        lineas.append(f"\n[AVISO] Cliente {o['customer_id']} omitido: {', '.join(o['errores'])}")
    lineas += [
        "",
        "-" * 80,
        "Resumen para la Actividad 1",
        f"{'ID':8} {'Nombre':16} {'Prob.':>8}  {'Nivel':14} {'Clasificacion':18} Costo",
    ]
    for f in resumen.filas:
        c, d = f["cliente"], f["decision"]
        lineas.append(f"{c['customer_id']:8} {c['nombre'][:16]:16} {f['probabilidad'] * 100:7.2f}%  {d['nivel_riesgo']:14} {d['clasificacion']:18} {formato_usd(d['presupuesto_asignado_usd'])}")
    lineas += [
        f"Presupuesto total de retencion: {formato_usd(resumen.costo_total)}",
        "",
        "[OK] Resultados sincronizados en MongoDB Atlas (active_customers, retention_actions, evaluaciones).",
    ]
    return "\n".join(lineas)
