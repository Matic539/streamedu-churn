"""Datos del laboratorio: generador de históricos, clientes activos y oráculo.

`generar_historicos()` reproduce exactamente los 1.000 clientes del script del
docente (misma semilla y mismo orden de sorteos), pero con un generador propio
en vez del estado global de numpy.
"""
from __future__ import annotations

import math

import numpy as np

from .config import CUOTA_MENSUAL_USD, FEATURES, SEMILLA

# Coeficientes de la "lógica oculta" con que el docente generó la etiqueta churn.
COEF_ORACULO = {
    "tickets_soporte": 0.25,
    "dias_sin_conectar": 0.08,
    "fallos_pago": 0.4,
    "horas_uso_semanal": -0.15,
}
SESGO_ORACULO = -1.2

# Los 5 clientes activos de la guía (mismos valores que el script del docente).
CLIENTES_ACTIVOS = [
    {"customer_id": "ACT-001", "nombre": "Ana Gomez", "meses_antiguedad": 14, "horas_uso_semanal": 1.2, "tickets_soporte": 5, "fallos_pago": 1, "dias_sin_conectar": 22, "cuota_mensual": 29.0},
    {"customer_id": "ACT-002", "nombre": "Carlos Ruiz", "meses_antiguedad": 2, "horas_uso_semanal": 1.5, "tickets_soporte": 4, "fallos_pago": 2, "dias_sin_conectar": 19, "cuota_mensual": 29.0},
    {"customer_id": "ACT-003", "nombre": "Lucia Fernandez", "meses_antiguedad": 20, "horas_uso_semanal": 18.5, "tickets_soporte": 0, "fallos_pago": 0, "dias_sin_conectar": 1, "cuota_mensual": 29.0},
    {"customer_id": "ACT-004", "nombre": "Pedro Soto", "meses_antiguedad": 8, "horas_uso_semanal": 6.0, "tickets_soporte": 2, "fallos_pago": 1, "dias_sin_conectar": 12, "cuota_mensual": 29.0},
    {"customer_id": "ACT-005", "nombre": "Elena Castro", "meses_antiguedad": 1, "horas_uso_semanal": 12.0, "tickets_soporte": 1, "fallos_pago": 0, "dias_sin_conectar": 3, "cuota_mensual": 29.0},
]

# Cliente ficticio para demostrar la regla SUPER VIP (pregunta 4): con los 5 de la
# guía nadie la cumple. 24 meses x 29 = LTV 696 y uso muy bajo (riesgo real ~95%).
CLIENTE_DEMO_SUPER_VIP = {
    "customer_id": "ACT-006", "nombre": "Martina Rojas", "meses_antiguedad": 24, "horas_uso_semanal": 1.0,
    "tickets_soporte": 6, "fallos_pago": 2, "dias_sin_conectar": 25, "cuota_mensual": 29.0,
}


def generar_historicos(n: int = 1000, semilla: int = SEMILLA) -> list[dict]:
    rng = np.random.RandomState(semilla)  # mismo flujo que np.random.seed(42)
    historicos = []
    for i in range(n):
        meses_antiguedad = int(rng.randint(1, 36))
        horas_uso_semanal = round(float(rng.uniform(0.5, 25.0)), 2)
        tickets_soporte = int(rng.randint(0, 8))
        fallos_pago = int(rng.randint(0, 4))
        dias_sin_conectar = int(rng.randint(0, 30))
        score = (
            tickets_soporte * 0.25
            + dias_sin_conectar * 0.08
            + fallos_pago * 0.4
            - horas_uso_semanal * 0.15
        )
        prob = 1 / (1 + np.exp(-(score - 1.2)))
        churn = 1 if rng.random_sample() < prob else 0
        historicos.append({
            "customer_id": f"HIST-{1000 + i}",
            "meses_antiguedad": meses_antiguedad,
            "horas_uso_semanal": horas_uso_semanal,
            "tickets_soporte": tickets_soporte,
            "fallos_pago": fallos_pago,
            "dias_sin_conectar": dias_sin_conectar,
            "cuota_mensual": CUOTA_MENSUAL_USD,
            "churn": churn,
        })
    return historicos


def probabilidad_real(cliente) -> float:
    """Probabilidad con que se generaron los datos (solo existe porque son sintéticos)."""
    z = SESGO_ORACULO + sum(coef * float(cliente[c]) for c, coef in COEF_ORACULO.items())
    return 1 / (1 + math.exp(-z))


def probabilidad_real_matriz(X) -> np.ndarray:
    """Igual que probabilidad_real, para una matriz con las columnas en el orden de FEATURES."""
    X = np.asarray(X, dtype=float)
    z = np.full(X.shape[0], SESGO_ORACULO)
    for c, coef in COEF_ORACULO.items():
        z += coef * X[:, FEATURES.index(c)]
    return 1 / (1 + np.exp(-z))
