"""Utilidades compartidas por las pruebas (sin Atlas: base simulada con mongomock)."""
from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
# Código del docente, si está junto al proyecto (no va en el repositorio).
REFERENCIA = Path(os.getenv("STREAMEDU_REFERENCIA", RAIZ.parent / "streamedu-churn-dl"))

import mongomock  # noqa: E402
import numpy as np  # noqa: E402
from mongomock import collection as _mm_col  # noqa: E402


def _aceptar_sort(metodo):
    """pymongo 4.20 envía `sort` en ReplaceOne/UpdateOne dentro de bulk_write y mongomock 4.3 no lo acepta.
    Solo afecta a la base simulada de las pruebas; el proyecto no usa `sort` en esas operaciones."""
    def envoltura(self, *args, sort=None, **kwargs):
        return metodo(self, *args, **kwargs)
    return envoltura


if not getattr(_mm_col.BulkOperationBuilder, "_parche_sort", False):
    _mm_col.BulkOperationBuilder.add_update = _aceptar_sort(_mm_col.BulkOperationBuilder.add_update)
    _mm_col.BulkOperationBuilder.add_replace = _aceptar_sort(_mm_col.BulkOperationBuilder.add_replace)
    _mm_col.BulkOperationBuilder._parche_sort = True


def base_simulada(nombre: str = "streamedu_test"):
    return mongomock.MongoClient()[nombre]


def cargar_script(nombre_archivo: str, alias: str, carpeta: Path = RAIZ):
    """Importa un script cuyo nombre empieza con número (p. ej. 1_seed_mongodb.py)."""
    ruta = carpeta / nombre_archivo
    spec = importlib.util.spec_from_file_location(alias, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class ArtefactosFalsos:
    """Sustituye al modelo: devuelve probabilidades fijas por cliente."""

    def __init__(self, probabilidades: dict, version: str = "falso000001"):
        self.probabilidades = dict(probabilidades)
        self.version = version
        self.metadata = {"version_modelo": version, "rangos_entrenamiento": {}}

    def predecir(self, clientes):
        return np.array([self.probabilidades[c["customer_id"]] for c in clientes], dtype=float)


def _bson_tipo(valor) -> str:
    if isinstance(valor, bool):
        return "bool"
    if isinstance(valor, int):
        return "int" if -(2**31) <= valor < 2**31 else "long"
    if isinstance(valor, float):
        return "double"
    if isinstance(valor, str):
        return "string"
    return type(valor).__name__


def errores_esquema(doc: dict, esquema: dict) -> list[str]:
    """Validador mínimo del subconjunto de $jsonSchema que usa el proyecto (mongomock no valida)."""
    errores = [f"falta {c}" for c in esquema.get("required", []) if c not in doc]
    for campo, regla in esquema.get("properties", {}).items():
        if campo not in doc:
            continue
        v = doc[campo]
        tipos = regla.get("bsonType")
        tipos = [tipos] if isinstance(tipos, str) else tipos
        if tipos and _bson_tipo(v) not in tipos:
            errores.append(f"{campo}: tipo {_bson_tipo(v)} no permitido")
            continue
        if "minimum" in regla and v < regla["minimum"]:
            errores.append(f"{campo}: menor que el mínimo")
        if "maximum" in regla and v > regla["maximum"]:
            errores.append(f"{campo}: mayor que el máximo")
        if "enum" in regla and v not in regla["enum"]:
            errores.append(f"{campo}: fuera de enum")
        if "pattern" in regla and not re.search(regla["pattern"], v):
            errores.append(f"{campo}: no calza con el patrón")
        if "minLength" in regla and len(v) < regla["minLength"]:
            errores.append(f"{campo}: muy corto")
        if "maxLength" in regla and len(v) > regla["maxLength"]:
            errores.append(f"{campo}: muy largo")
    return errores
