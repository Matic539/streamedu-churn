"""Verificación del estado de MongoDB Atlas (solo lectura, salvo --probar-validador).

Nunca imprime la URI ni credenciales. Pensado para el agente y para Matías.

Uso:
  python -B scripts/verificar_atlas.py                     colecciones, conteos, validadores e índices
  python -B scripts/verificar_atlas.py --super-vip         además muestra la acción SUPER VIP de ACT-006
  python -B scripts/verificar_atlas.py --probar-validador  intenta insertar un cliente inválido: Atlas debe rechazarlo
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from pymongo.errors import PyMongoError, WriteError  # noqa: E402

from streamedu.config import ConfigError, configurar_consola, enmascarar_uri, leer_config_mongo  # noqa: E402
from streamedu.db import (  # noqa: E402
    COL_ACCIONES,
    COL_ACTIVOS,
    COL_API_LOG,
    COL_EVALUACIONES,
    COL_METRICAS,
    COLECCIONES_LAB,
    ConexionError,
    ESTADO_PENDIENTE,
    conectar,
)


def tiene_validador(db, nombre: str) -> str:
    try:
        for info in db.list_collections(filter={"name": nombre}):
            return "sí" if info.get("options", {}).get("validator") else "no"
    except (PyMongoError, NotImplementedError, TypeError):
        return "desconocido"
    return "no existe"


def resumen(db) -> None:
    existentes = set(db.list_collection_names())
    print(f"{'Colección':22} {'Docs':>6}  {'Validador':10} Índices")
    for nombre in COLECCIONES_LAB:
        if nombre not in existentes:
            print(f"{nombre:22} {'-':>6}  {'-':10} (no existe)")
            continue
        indices = ", ".join(sorted(db[nombre].index_information()))
        print(f"{nombre:22} {db[nombre].count_documents({}):>6}  {tiene_validador(db, nombre):10} {indices}")
    ids = [d["customer_id"] for d in db[COL_ACTIVOS].find({}, {"customer_id": 1}).sort("customer_id", 1)]
    print(f"\nClientes activos: {', '.join(ids) if ids else '(ninguno)'}")
    por_estado = {}
    for d in db[COL_ACCIONES].find({}, {"estado_campana": 1}):
        por_estado[d.get("estado_campana")] = por_estado.get(d.get("estado_campana"), 0) + 1
    print(f"Acciones por estado: {por_estado if por_estado else '(ninguna)'}")
    pendientes = sorted(d["customer_id"] for d in db[COL_ACCIONES].find({"estado_campana": ESTADO_PENDIENTE}, {"customer_id": 1}))
    print(f"Acciones pendientes por cliente: {', '.join(pendientes) if pendientes else '(ninguna)'}")
    duplicadas = len(pendientes) - len(set(pendientes))
    print(f"Acciones pendientes duplicadas: {duplicadas}")
    ultima = db[COL_EVALUACIONES].find_one({}, sort=[("fecha", -1)])
    if ultima:
        print(f"Última corrida: {ultima['corrida_id']} | modelo {ultima['modelo_version']} | "
              f"{ultima['clientes_evaluados']} clientes | presupuesto USD {ultima['presupuesto_total_usd']:.2f} | {ultima['conteo_por_clasificacion']}")
    tipos = {}
    for d in db[COL_METRICAS].find({}, {"tipo": 1}):
        tipos[d.get("tipo")] = tipos.get(d.get("tipo"), 0) + 1
    print(f"Métricas registradas por tipo: {tipos if tipos else '(ninguna)'}")
    if COL_API_LOG in existentes:
        con_nombre = db[COL_API_LOG].count_documents({"$or": [{"nombre": {"$exists": True}}, {"cliente.nombre": {"$exists": True}}]})
        print(f"Registros de la API: {db[COL_API_LOG].count_documents({})} (con nombre de cliente: {con_nombre})")


def mostrar_super_vip(db) -> int:
    doc = db[COL_ACCIONES].find_one({"customer_id": "ACT-006", "estado_campana": ESTADO_PENDIENTE}, {"_id": 0})
    if not doc:
        print("\n[FALTA] No hay acción pendiente para ACT-006 (ejecuta 1_seed_mongodb.py --demo-super-vip y luego 3_business_pipeline.py).")
        return 1
    d = doc["decision_negocio"]
    print(f"\nAcción pendiente de ACT-006: {doc['customer_id']} {doc.get('nombre')} | P(churn) {doc['probabilidad_churn']:.4f} | "
          f"{d['clasificacion']} | {d['accion_comercial']} | USD {d['presupuesto_asignado_usd']:.2f} | LTV USD {d['ltv_acumulado_usd']:.2f} | modelo {doc['modelo_version']}")
    return 0 if d.get("segmento") == "SUPER_VIP" else 1


def probar_validador(db) -> int:
    malo = {"customer_id": "ACT-999", "nombre": "Prueba Validador", "meses_antiguedad": 5, "horas_uso_semanal": 500.0,
            "tickets_soporte": 1, "fallos_pago": 0, "dias_sin_conectar": 3, "cuota_mensual": 29.0}
    try:
        db[COL_ACTIVOS].insert_one(malo)
    except WriteError as e:
        if e.code == 121:
            print("\n[OK] Atlas rechazó el documento inválido (500 horas por semana): el validador $jsonSchema está activo.")
            return 0
        print(f"\n[ERROR] Atlas rechazó el documento por otro motivo (código {e.code}).")
        return 1
    db[COL_ACTIVOS].delete_one({"customer_id": "ACT-999", "nombre": "Prueba Validador"})
    print("\n[FALLA] Atlas aceptó el documento inválido: el validador NO está activo (el documento de prueba ya se borró).")
    return 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--super-vip", action="store_true")
    p.add_argument("--probar-validador", action="store_true")
    args = p.parse_args(argv)
    configurar_consola()
    try:
        uri, db_name = leer_config_mongo()
        cliente, db = conectar(uri, db_name)
    except (ConfigError, ConexionError) as e:
        print(f"[ERROR] {e}")
        return 1
    codigo = 0
    try:
        print(f"Atlas: {enmascarar_uri(uri)} | base {db_name}\n")
        resumen(db)
        if args.super_vip:
            codigo |= mostrar_super_vip(db)
        if args.probar_validador:
            codigo |= probar_validador(db)
    except PyMongoError as e:
        print(f"[ERROR] MongoDB ({type(e).__name__}).")
        codigo = 1
    finally:
        cliente.close()
    return codigo


if __name__ == "__main__":
    sys.exit(main())
