"""Script 4 (bonus de la guía): microservicio FastAPI.

Uso:  python -B 4_api_fastapi.py      y abrir http://127.0.0.1:8000/docs
(Equivale a: uvicorn 4_api_fastapi:app --host 127.0.0.1 --port 8000, sin --reload.)
"""
from __future__ import annotations

import os

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from streamedu.api import app, ejecutar  # noqa: E402,F401

if __name__ == "__main__":
    ejecutar()
