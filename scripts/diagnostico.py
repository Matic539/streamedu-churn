"""Diagnóstico del entorno (Fase 0): Python, dependencias, TensorFlow, .env y Atlas.

Nunca imprime la URI ni la contraseña: solo el host recortado.
Uso:  python -B scripts/diagnostico.py
"""
from __future__ import annotations

import importlib
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

errores = 0


def ok(msg):
    print(f"  [OK]    {msg}")


def aviso(msg):
    print(f"  [AVISO] {msg}")


def falla(msg):
    global errores
    errores += 1
    print(f"  [ERROR] {msg}")


def leer_pines():
    pines = {}
    for linea in (RAIZ / "requirements.in").read_text(encoding="utf-8").splitlines():
        linea = linea.split("#")[0].strip()
        if "==" in linea:
            nombre, version = linea.split("==")
            pines[nombre.strip()] = version.strip()
    return pines


def main() -> int:
    from streamedu.config import configurar_consola

    configurar_consola()
    print("1. Python")
    v = sys.version_info
    (ok if (v.major, v.minor) == (3, 13) else falla)(f"Python {v.major}.{v.minor}.{v.micro}")
    if "onedrive" in sys.prefix.lower():
        aviso("El entorno virtual está dentro de OneDrive: muévelo a %USERPROFILE%\\.virtualenvs")
    elif sys.prefix == sys.base_prefix:
        aviso("No estás usando un entorno virtual.")
    else:
        ok("Entorno virtual fuera de OneDrive")

    print("2. Dependencias (versiones fijas de requirements.in)")
    from importlib.metadata import PackageNotFoundError, version

    for nombre, esperado in leer_pines().items():
        try:
            instalado = version(nombre)
        except PackageNotFoundError:
            falla(f"{nombre} no está instalado")
            continue
        (ok if instalado == esperado else falla)(f"{nombre} {instalado} (esperado {esperado})")

    print("3. TensorFlow")
    t0 = time.perf_counter()
    try:
        tf = importlib.import_module("tensorflow")
        dispositivos = [d.device_type for d in tf.config.list_physical_devices()]
        ok(f"importa en {time.perf_counter() - t0:.1f} s; dispositivos: {', '.join(dispositivos)}")
    except Exception as e:  # noqa: BLE001 (diagnóstico: mostrar cualquier falla)
        falla(f"no se pudo importar ({type(e).__name__}: {e})")

    print("4. Archivo .env")
    from streamedu.config import ConfigError, enmascarar_uri, leer_config_mongo

    env = RAIZ / ".env"
    if not env.exists():
        falla("No existe .env en la raíz del proyecto (cópialo desde .env.example).")
        return resumen()
    ok(".env existe")
    gitignore = RAIZ / ".gitignore"
    if gitignore.exists() and ".env" in gitignore.read_text(encoding="utf-8").split():
        ok(".env está en .gitignore")
    else:
        falla(".env no está en .gitignore")
    try:
        uri, db_name = leer_config_mongo()
        ok(f"MONGO_URI con formato de Atlas: {enmascarar_uri(uri)}  | DB_NAME = {db_name}")
    except ConfigError as e:
        falla(str(e))
        return resumen()

    print("5. MongoDB Atlas")
    from pymongo.errors import OperationFailure, PyMongoError

    from streamedu.db import COLECCIONES_LAB, ConexionError, conectar

    try:
        t0 = time.perf_counter()
        cliente, db = conectar(uri, db_name)
        ok(f"ping respondió en {(time.perf_counter() - t0) * 1000:.0f} ms")
    except ConexionError as e:
        falla(str(e))
        return resumen()
    try:
        col = db["_diagnostico"]
        res = col.insert_one({"prueba": True})
        if col.find_one({"_id": res.inserted_id}) is None:
            raise RuntimeError("no se pudo leer el documento de prueba")
        col.delete_one({"_id": res.inserted_id})
        db.drop_collection("_diagnostico")
        ok(f"el usuario puede escribir, leer y borrar en {db_name}")
    except (PyMongoError, RuntimeError) as e:
        falla(f"no se pudo escribir en {db_name} ({type(e).__name__}); revisa el rol readWrite")
    try:
        cliente["streamedu_prueba_permisos"]["x"].find_one({})
        aviso("el usuario puede leer otras bases: dale readWrite solo sobre " + db_name)
    except OperationFailure as e:
        if e.code == 13 or (e.code == 8000 and "not allowed" in str(e).lower()):
            ok("permisos mínimos: el usuario no puede leer otras bases")
        else:
            aviso(f"respuesta inesperada al probar permisos ({e.code})")
    existentes = set(db.list_collection_names())
    for nombre in COLECCIONES_LAB:
        if nombre in existentes:
            print(f"          {nombre}: {db[nombre].count_documents({})} documentos")
    cliente.close()
    return resumen()


def resumen() -> int:
    print()
    print("Diagnóstico OK" if errores == 0 else f"Diagnóstico con {errores} error(es)")
    return 0 if errores == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
