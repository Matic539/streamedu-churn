"""Configuración del laboratorio StreamEdu.

Lee el archivo .env de la raíz del proyecto y valida la cadena de conexión a
MongoDB Atlas sin mostrarla nunca completa. Aquí también viven las constantes
que comparten los 4 scripts (variables del modelo, rangos válidos y semilla).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
# No sobrescribe variables que ya existan en el entorno.
load_dotenv(RAIZ / ".env")

DB_NAME_DEFECTO = "streamedu_db"
CUOTA_MENSUAL_USD = 29.0
SEMILLA = 42

# Variables predictoras, en el mismo orden que la guía.
FEATURES = (
    "meses_antiguedad",
    "horas_uso_semanal",
    "tickets_soporte",
    "fallos_pago",
    "dias_sin_conectar",
)

# Rangos válidos (mínimo, máximo, tipo). Se usan en el validador de MongoDB,
# en el pipeline y en la API. Una semana tiene 168 horas.
RANGOS = {
    "meses_antiguedad": (1, 120, int),
    "horas_uso_semanal": (0.0, 168.0, float),
    "tickets_soporte": (0, 50, int),
    "fallos_pago": (0, 12, int),
    "dias_sin_conectar": (0, 365, int),
    "cuota_mensual": (0.01, 1000.0, float),
}

MARCADORES_EJEMPLO = ("<", ">", "tu_password", "tu-cluster", "xxxx", "usuario:password")


class ConfigError(RuntimeError):
    """La configuración no permite continuar. El mensaje nunca incluye la URI."""


def configurar_consola() -> None:
    """Salida en UTF-8 aunque se redirija a un archivo en Windows (evita UnicodeEncodeError con tildes y tablas)."""
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def dir_modelos() -> Path:
    return Path(os.getenv("STREAMEDU_DIR_MODELOS", RAIZ / "modelos"))


def enmascarar_uri(uri: str) -> str:
    """Devuelve una versión segura para mostrar: sin usuario, sin contraseña y con el host recortado."""
    try:
        partes = urlsplit(uri)
        host = partes.hostname or "?"
    except ValueError:
        return "(URI con formato inválido)"
    trozos = host.split(".")
    if len(trozos) >= 2 and len(trozos[1]) > 2:
        trozos[1] = trozos[1][:2] + "***"
    return f"{partes.scheme}://***@{'.'.join(trozos)}"


def leer_config_mongo(exigir_atlas: bool = True) -> tuple[str, str]:
    """Valida MONGO_URI y DB_NAME. Falla con un mensaje claro en vez de usar localhost."""
    uri = os.getenv("MONGO_URI", "").strip().strip('"').strip("'")
    if not uri:
        raise ConfigError(
            "Falta MONGO_URI. Crea el archivo .env en la raíz del proyecto a partir de "
            ".env.example. (Sin esta variable pymongo se conectaría a localhost sin avisar.)"
        )
    if any(m in uri for m in MARCADORES_EJEMPLO):
        raise ConfigError(
            "MONGO_URI todavía tiene texto de ejemplo (<db_password>, tu_password, xxxx...). "
            "Pega la cadena de Atlas y reemplaza la contraseña."
        )
    try:
        partes = urlsplit(uri)
        usuario, clave, host = partes.username, partes.password, partes.hostname or ""
    except ValueError:
        raise ConfigError("MONGO_URI no tiene un formato válido.") from None
    if partes.scheme not in ("mongodb+srv", "mongodb"):
        raise ConfigError("MONGO_URI debe empezar con mongodb+srv:// (cadena de Atlas).")
    if exigir_atlas and not (partes.scheme == "mongodb+srv" and host.endswith(".mongodb.net")):
        raise ConfigError(
            "La pauta evalúa la conexión a MongoDB Atlas: la URI debe ser "
            "mongodb+srv://<usuario>:<clave>@<cluster>.mongodb.net/..."
        )
    if not usuario or not clave:
        raise ConfigError("MONGO_URI no trae usuario y contraseña.")
    db_name = os.getenv("DB_NAME", DB_NAME_DEFECTO).strip().strip('"').strip("'")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,38}", db_name):
        raise ConfigError("DB_NAME solo admite letras, números, guion y guion bajo (máximo 38).")
    return uri, db_name
