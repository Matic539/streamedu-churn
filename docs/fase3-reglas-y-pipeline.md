# Fase 3: reglas de negocio, pipeline y reto SUPER VIP (script 3)

## Regla de negocio (`streamedu/negocio.py`)

| P(churn) | LTV | Clasificación | Acción | Costo USD |
|---|---|---|---|---|
| ≥ 0,70 | ≥ 500 | CRÍTICO SUPER VIP | 1 Mes Gratis + Mentoría 1 a 1 | 49,00 |
| ≥ 0,70 | 180 a 499 | CRÍTICO VIP | Llamada de ejecutivo + 30% por 3 meses | 26,10 |
| ≥ 0,70 | < 180 | CRÍTICO ESTÁNDAR | Email con cupón 15% el próximo mes | 4,35 |
| 0,40 a 0,6999 | cualquiera | RIESGO MODERADO | Notificación in-app + encuesta | 0,50 |
| < 0,40 | cualquiera | BAJO (SEGURO) | Ninguna | 0,00 |

- **SUPER VIP se evalúa antes que VIP**, porque todo cliente con LTV ≥ 500 también tiene LTV ≥ 180.
- Condición `LTV >= 500`, como en el código de la guía (el texto dice "más de $500"; con cuota 29 no cambia nada, porque 500 no es múltiplo de 29).
- **Costo SUPER VIP (supuesto declarado):** 1 mes gratis = 29,00 + mentoría valorizada en 20,00 = 49,00. Está en `COSTO_MENTORIA_USD`.
- La probabilidad se redondea a 4 decimales **antes** de clasificar: lo que se guarda en Atlas y lo que decide es el mismo número (en el docente, 69,96% se mostraba como "70.0%" pero quedaba MODERADO).
- Misma firma y mismas claves que la función de la guía, más `segmento`, `clasificacion`, `es_super_vip` y `probabilidad_usada`.

## Por qué hace falta ACT-006

Con los 5 clientes de la guía nadie puede ser SUPER VIP: Lucía tiene LTV 580 pero riesgo bajo, y Ana es crítica pero tiene LTV 406 (para llegar a 500 se necesitan 18 meses). Para demostrar la regla se agrega un cliente ficticio con `1_seed_mongodb.py --demo-super-vip`: **ACT-006 Martina Rojas**, 24 meses (LTV 696), 1 hora de uso semanal, 6 tickets, 2 fallos de pago y 25 días sin conectar (probabilidad real 95%).

## Pipeline (`streamedu/pipeline.py`)

1. Lee los clientes activos y **valida** cada documento (campos, tipos y rangos). Un documento malo se informa y se omite sin detener a los demás.
2. Predice en bloque y aplica la regla.
3. Actualiza `active_customers` (probabilidad, riesgo, clasificación, versión del modelo, corrida) con `bulk_write`.
4. En `retention_actions` deja **una sola acción pendiente por cliente**: si ya existe, la actualiza; si el riesgo bajó a BAJO, la marca `DESCARTADA_RIESGO_BAJO`. El docente insertaba otra copia en cada ejecución (3 → 6).
5. Registra la corrida en `evaluaciones` (conteo por clasificación y presupuesto total).

## Pruebas (`tests/test_negocio.py`, `tests/test_mongo.py`)

- Los 4 niveles de la guía, SUPER VIP, prioridad sobre VIP (LTV 493 y 500), Lucía con LTV 580 y riesgo bajo, VIP desde el mes 7, bordes 0,3999 / 0,40 / 0,6999 / 0,70, redondeo, entradas inválidas.
- **Comparación con el docente** en 123.000 combinaciones (probabilidad de 0 a 1 cada 0,001, 0 a 40 meses, 3 cuotas): fuera de la zona SUPER VIP decide exactamente igual.
- Pipeline: clasificaciones, acciones, costo total, sin duplicados al repetir, acción descartada o actualizada cuando cambia el riesgo, documento inválido omitido y formato del reporte.
