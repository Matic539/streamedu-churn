"""Script 3: pipeline de producción y lógica de negocio.

Carga el modelo entrenado, predice la probabilidad de abandono de cada cliente
activo, aplica las reglas de LTV (incluida SUPER VIP) y guarda los resultados en
MongoDB Atlas: active_customers, retention_actions y evaluaciones.

Uso:  python -B 3_business_pipeline.py
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from pymongo.errors import PyMongoError  # noqa: E402

from streamedu.config import configurar_consola, ConfigError, dir_modelos, enmascarar_uri, leer_config_mongo  # noqa: E402
from streamedu.db import ConexionError, conectar  # noqa: E402
from streamedu.modelo import IntegridadError, ModeloNoEntrenadoError, cargar_artefactos  # noqa: E402
from streamedu.negocio import aplicar_logica_negocio  # noqa: E402,F401  (misma función que pide la guía)
from streamedu.pipeline import ejecutar_pipeline, formatear_reporte  # noqa: E402


def main() -> int:
    configurar_consola()
    try:
        artefactos = cargar_artefactos(dir_modelos())
        uri, db_name = leer_config_mongo()
        cliente, db = conectar(uri, db_name)
    except (ModeloNoEntrenadoError, IntegridadError, ConfigError, ConexionError) as e:
        print(f"[ERROR] {e}")
        return 1
    print(f"[INFO] Conectado a {enmascarar_uri(uri)} | base {db_name} | modelo {artefactos.version}")
    try:
        resumen = ejecutar_pipeline(db, artefactos)
    except PyMongoError as e:
        print(f"[ERROR] MongoDB rechazó la operación ({type(e).__name__}).")
        return 1
    finally:
        cliente.close()
    if not resumen.filas and not resumen.omitidos:
        print("No hay clientes activos para evaluar: ejecuta primero 1_seed_mongodb.py")
        return 1
    print(formatear_reporte(resumen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
