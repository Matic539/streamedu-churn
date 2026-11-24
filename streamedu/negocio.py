"""Reglas de negocio: traduce P(churn) y el LTV en una acción comercial rentable.

Tabla de la guía más el reto SUPER VIP (pregunta 4):

| P(churn)  | LTV        | Clasificación      | Acción                                        | Costo |
|-----------|------------|--------------------|-----------------------------------------------|-------|
| >= 0,70   | >= 500     | CRÍTICO SUPER VIP  | 1 Mes Gratis + Mentoría 1 a 1                 | 49,00 |
| >= 0,70   | 180 a 499  | CRÍTICO VIP        | Llamada de ejecutivo + 30% por 3 meses        | 26,10 |
| >= 0,70   | < 180      | CRÍTICO ESTÁNDAR   | Email con cupón 15% el próximo mes            |  4,35 |
| 0,40-0,69 | cualquiera | RIESGO MODERADO    | Notificación in-app + encuesta                |  0,50 |
| < 0,40    | cualquiera | BAJO (SEGURO)      | Ninguna                                       |  0,00 |

La regla SUPER VIP se evalúa antes que la VIP, porque todo SUPER VIP también es VIP.
"""
from __future__ import annotations

import math

from .config import CUOTA_MENSUAL_USD

UMBRAL_CRITICO = 0.70
UMBRAL_MODERADO = 0.40
LTV_VIP = 180.0
LTV_SUPER_VIP = 500.0  # la guía: "LTV >= 500"

# Costo SUPER VIP: supuesto declarado (la guía no lo da): 1 mes gratis (29,00) + mentoría valorizada en 20,00.
COSTO_MENTORIA_USD = 20.00
COSTO_SUPER_VIP = round(CUOTA_MENSUAL_USD + COSTO_MENTORIA_USD, 2)
COSTO_VIP = round(0.30 * CUOTA_MENSUAL_USD * 3, 2)        # 26,10
COSTO_ESTANDAR = round(0.15 * CUOTA_MENSUAL_USD * 1, 2)   # 4,35
COSTO_MODERADO = 0.50

NIVEL_CRITICO = "CRITICO"
NIVEL_MODERADO = "MODERADO"
NIVEL_BAJO = "BAJO (SEGURO)"

# Textos de acción iguales a los del docente (para compararlos en las pruebas).
ACCION_SUPER_VIP = "1 Mes Gratis + Mentoría 1 a 1"
ACCION_VIP = "Llamada urgente de Ejecutivo Cuenta + 30% Descuento por 3 meses"
ACCION_ESTANDAR = "Email automatizado con Cupon 15% Descuento el proximo mes"
ACCION_MODERADO = "Notificacion In-App recomendando nuevos cursos + Encuesta rapida"
ACCION_NINGUNA = "Ninguna accion (No interrumpir ni regalar margen)"


def redondear_probabilidad(prob: float) -> float:
    """La probabilidad se redondea a 4 decimales ANTES de clasificar: lo que se guarda y lo que decide es lo mismo."""
    return round(float(prob), 4)


def aplicar_logica_negocio(cliente: dict, prob_churn: float) -> dict:
    """Misma firma y mismas claves que la función de la guía, más segmento y clasificación."""
    prob = float(prob_churn)
    if not math.isfinite(prob) or not 0.0 <= prob <= 1.0:
        raise ValueError("prob_churn debe estar entre 0 y 1")
    meses = cliente["meses_antiguedad"]
    cuota = float(cliente.get("cuota_mensual", CUOTA_MENSUAL_USD))
    if isinstance(meses, bool) or not isinstance(meses, int) or meses < 0:
        raise ValueError("meses_antiguedad debe ser un entero mayor o igual a 0")
    if not math.isfinite(cuota) or cuota <= 0:
        raise ValueError("cuota_mensual debe ser mayor que 0")

    p = redondear_probabilidad(prob)
    ltv = round(meses * cuota, 2)
    es_vip = ltv >= LTV_VIP
    es_super_vip = ltv >= LTV_SUPER_VIP          # NUEVO (reto SUPER VIP)

    # >>> SUPER VIP
    if p >= UMBRAL_CRITICO:                      # P(churn) >= 0,70
        nivel = NIVEL_CRITICO
        if es_super_vip:                         # NUEVO: LTV >= 500, se evalúa ANTES que VIP
            segmento = "SUPER_VIP"
            clasificacion = "CRÍTICO SUPER VIP"
            accion = ACCION_SUPER_VIP            # "1 Mes Gratis + Mentoría 1 a 1"
            costo = COSTO_SUPER_VIP              # 29,00 (mes gratis) + 20,00 (mentoría) = 49,00
        elif es_vip:                             # LTV >= 180
            segmento = "VIP"
            clasificacion = "CRÍTICO VIP"
            accion = ACCION_VIP
            costo = COSTO_VIP                    # 26,10
        else:
            segmento = "ESTANDAR"
            clasificacion = "CRÍTICO ESTÁNDAR"
            accion = ACCION_ESTANDAR
            costo = COSTO_ESTANDAR               # 4,35
    # <<< SUPER VIP
    elif p >= UMBRAL_MODERADO:
        nivel, segmento, clasificacion, accion, costo = NIVEL_MODERADO, None, "RIESGO MODERADO", ACCION_MODERADO, COSTO_MODERADO
    else:
        nivel, segmento, clasificacion, accion, costo = NIVEL_BAJO, None, "BAJO (SEGURO)", ACCION_NINGUNA, 0.0

    return {
        "nivel_riesgo": nivel,
        "es_cliente_vip": es_vip,
        "ltv_acumulado_usd": ltv,
        "accion_comercial": accion,
        "presupuesto_asignado_usd": costo,
        # Campos agregados en la versión propia
        "es_super_vip": es_super_vip,
        "segmento": segmento,
        "clasificacion": clasificacion,
        "probabilidad_usada": p,
    }


def formato_usd(valor: float) -> str:
    return f"${valor:,.2f}"
