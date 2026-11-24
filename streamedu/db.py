"""Conexión a MongoDB Atlas, colecciones, índices y validadores."""
from __future__ import annotations

from pymongo import ASCENDING, MongoClient
from pymongo.errors import (
    CollectionInvalid,
    ConfigurationError,
    OperationFailure,
    PyMongoError,
    ServerSelectionTimeoutError,
)

from .config import FEATURES, RANGOS, leer_config_mongo

COL_HISTORICOS = "historical_customers"
COL_ACTIVOS = "active_customers"
COL_ACCIONES = "retention_actions"
COL_EVALUACIONES = "evaluaciones"
COL_METRICAS = "metricas_modelo"
COL_API_LOG = "api_predictions_log"
COLECCIONES_LAB = (
    COL_HISTORICOS,
    COL_ACTIVOS,
    COL_ACCIONES,
    COL_EVALUACIONES,
    COL_METRICAS,
    COL_API_LOG,
)

ESTADO_PENDIENTE = "PENDIENTE_EJECUCION"
ESTADO_DESCARTADA = "DESCARTADA_RIESGO_BAJO"


class ConexionError(RuntimeError):
    """No se pudo usar MongoDB. El mensaje orienta sin mostrar la URI."""


def mensaje_amigable(error: Exception) -> str:
    if isinstance(error, ServerSelectionTimeoutError):
        return (
            "No se pudo llegar a Atlas a tiempo. Revisa que tu IP actual esté en "
            "Network Access del proyecto y que tengas internet."
        )
    if isinstance(error, OperationFailure) and error.code == 18:
        return "Atlas rechazó el usuario o la contraseña de MONGO_URI (error de autenticación)."
    if isinstance(error, OperationFailure) and error.code == 13:
        return "El usuario no tiene permiso para esta operación (revisa el rol readWrite sobre la base)."
    if isinstance(error, ConfigurationError):
        return "No se pudo resolver el clúster de la URI (revisa el nombre del clúster en MONGO_URI)."
    return f"Error de MongoDB ({type(error).__name__})."


def conectar(uri: str | None = None, db_name: str | None = None, timeout_ms: int = 8000):
    """Devuelve (cliente, base). Verifica la conexión con ping y falla rápido."""
    if uri is None:
        uri, db_name = leer_config_mongo()
    try:
        cliente = MongoClient(
            uri,
            serverSelectionTimeoutMS=timeout_ms,
            connectTimeoutMS=timeout_ms,
            appname="streamedu-churn",
            tz_aware=True,
        )
        cliente.admin.command("ping")
    except PyMongoError as e:
        raise ConexionError(mensaje_amigable(e)) from None
    return cliente, cliente[db_name]


def _tipo_bson(tipo) -> list[str]:
    return ["int", "long"] if tipo is int else ["double", "int", "long"]


def _propiedades_numericas(campos) -> dict:
    props = {}
    for campo in campos:
        minimo, maximo, tipo = RANGOS[campo]
        props[campo] = {"bsonType": _tipo_bson(tipo), "minimum": minimo, "maximum": maximo}
    return props


def esquema_historicos() -> dict:
    props = _propiedades_numericas((*FEATURES, "cuota_mensual"))
    props["customer_id"] = {"bsonType": "string", "pattern": "^HIST-[0-9]{4,6}$"}
    props["churn"] = {"bsonType": ["int", "long"], "enum": [0, 1]}
    return {
        "bsonType": "object",
        "required": ["customer_id", *FEATURES, "cuota_mensual", "churn"],
        "properties": props,
    }


def esquema_activos() -> dict:
    props = _propiedades_numericas((*FEATURES, "cuota_mensual"))
    props["customer_id"] = {"bsonType": "string", "pattern": "^ACT-[0-9]{3,6}$"}
    props["nombre"] = {"bsonType": "string", "minLength": 1, "maxLength": 80}
    return {
        "bsonType": "object",
        "required": ["customer_id", "nombre", *FEATURES, "cuota_mensual"],
        "properties": props,
    }


def preparar_colecciones(db) -> list[str]:
    """Crea las colecciones con validador (si no existen) y los índices. Devuelve avisos."""
    avisos = []
    existentes = set(db.list_collection_names())
    for nombre, esquema in ((COL_HISTORICOS, esquema_historicos()), (COL_ACTIVOS, esquema_activos())):
        if nombre in existentes:
            continue
        try:
            db.create_collection(
                nombre,
                validator={"$jsonSchema": esquema},
                validationLevel="strict",
                validationAction="error",
            )
        except CollectionInvalid:
            pass
        except (OperationFailure, NotImplementedError) as e:
            avisos.append(f"No se pudo crear el validador de {nombre} ({type(e).__name__}).")
    db[COL_HISTORICOS].create_index([("customer_id", ASCENDING)], unique=True, name="uq_customer_id")
    db[COL_ACTIVOS].create_index([("customer_id", ASCENDING)], unique=True, name="uq_customer_id")
    db[COL_ACCIONES].create_index(
        [("customer_id", ASCENDING), ("estado_campana", ASCENDING)], name="ix_cliente_estado"
    )
    db[COL_ACCIONES].create_index(
        [("customer_id", ASCENDING)],
        unique=True,
        partialFilterExpression={"estado_campana": ESTADO_PENDIENTE},
        name="uq_una_accion_pendiente",
    )
    db[COL_EVALUACIONES].create_index([("corrida_id", ASCENDING)], unique=True, name="uq_corrida")
    db[COL_METRICAS].create_index([("fecha", ASCENDING)], name="ix_fecha")
    return avisos


def borrar_colecciones_lab(db) -> None:
    """Solo las colecciones de este laboratorio y solo en la base configurada."""
    for nombre in COLECCIONES_LAB:
        db.drop_collection(nombre)
