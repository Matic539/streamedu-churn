"""Script 1: genera y carga los datos de StreamEdu en MongoDB Atlas.

Crea "historical_customers" (1.000 clientes pasados, los mismos del docente) y
"active_customers" (los 5 clientes de la guía). Es idempotente: volver a
ejecutarlo deja los mismos datos sin duplicar.

Uso:
  python -B 1_seed_mongodb.py                    carga o actualiza los datos
  python -B 1_seed_mongodb.py --demo-super-vip   además agrega ACT-006 (reto SUPER VIP)
  python -B 1_seed_mongodb.py --reiniciar        borra las colecciones del laboratorio y carga de cero
  python -B 1_seed_mongodb.py --solo-verificar   solo muestra lo que hay en Atlas
"""
from __future__ import annotations

import argparse
import sys

from pymongo import ReplaceOne
from pymongo.errors import BulkWriteError, PyMongoError

from streamedu.config import configurar_consola, ConfigError, enmascarar_uri, leer_config_mongo
from streamedu.datos import CLIENTE_DEMO_SUPER_VIP, CLIENTES_ACTIVOS, generar_historicos
from streamedu.db import (
    COL_ACCIONES,
    COL_ACTIVOS,
    COL_HISTORICOS,
    ConexionError,
    borrar_colecciones_lab,
    conectar,
    preparar_colecciones,
)


def cargar(db, reiniciar: bool = False, demo_super_vip: bool = False) -> dict:
    if reiniciar:
        borrar_colecciones_lab(db)
    avisos = preparar_colecciones(db)
    historicos = generar_historicos()
    db[COL_HISTORICOS].bulk_write(
        [ReplaceOne({"customer_id": d["customer_id"]}, d, upsert=True) for d in historicos], ordered=False
    )
    activos = [dict(c) for c in CLIENTES_ACTIVOS] + ([dict(CLIENTE_DEMO_SUPER_VIP)] if demo_super_vip else [])
    db[COL_ACTIVOS].bulk_write(
        [ReplaceOne({"customer_id": c["customer_id"]}, c, upsert=True) for c in activos], ordered=False
    )
    return {"avisos": avisos, **resumen(db)}


def resumen(db) -> dict:
    hist = db[COL_HISTORICOS]
    return {
        "historicos": hist.count_documents({}),
        "historicos_churn": hist.count_documents({"churn": 1}),
        "activos": db[COL_ACTIVOS].count_documents({}),
        "ids_activos": [d["customer_id"] for d in db[COL_ACTIVOS].find({}, {"customer_id": 1}).sort("customer_id", 1)],
        "acciones": db[COL_ACCIONES].count_documents({}),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reiniciar", action="store_true", help="borra las colecciones del laboratorio antes de cargar")
    p.add_argument("--demo-super-vip", action="store_true", help="agrega el cliente ficticio ACT-006")
    p.add_argument("--solo-verificar", action="store_true", help="no escribe nada")
    args = p.parse_args(argv)
    configurar_consola()
    try:
        uri, db_name = leer_config_mongo()
        cliente, db = conectar(uri, db_name)
    except (ConfigError, ConexionError) as e:
        print(f"[ERROR] {e}")
        return 1
    print(f"[INFO] Conectado a {enmascarar_uri(uri)} | base {db_name}")
    try:
        r = resumen(db) if args.solo_verificar else cargar(db, args.reiniciar, args.demo_super_vip)
    except (BulkWriteError, PyMongoError) as e:
        print(f"[ERROR] MongoDB rechazó la operación ({type(e).__name__}).")
        return 1
    finally:
        cliente.close()
    for aviso in r.get("avisos", []):
        print(f"[AVISO] {aviso}")
    tasa = r["historicos_churn"] / r["historicos"] * 100 if r["historicos"] else 0
    print(f"[OK] {COL_HISTORICOS}: {r['historicos']} documentos ({r['historicos_churn']} con churn = 1, {tasa:.1f}%)")
    print(f"[OK] {COL_ACTIVOS}: {r['activos']} documentos ({', '.join(r['ids_activos'])})")
    print(f"[OK] {COL_ACCIONES}: {r['acciones']} documentos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
