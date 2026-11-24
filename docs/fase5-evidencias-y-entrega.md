# Fase 5: evidencias, Word y entrega

## Ejecución final en Atlas (24/11/2026, Windows, Python 3.13)

Sistema `Windows-11-10.0.26300-SP0`, Python 3.13.0, base `streamedu_db`. Ejecutado con `scripts/preparar_evidencias.py`.

| Colección | Documentos |
|---|---|
| `active_customers` | 6 |
| `evaluaciones` | 2 |
| `historical_customers` | 1000 |
| `metricas_modelo` | 2 |
| `retention_actions` | 3 |

## Modelo

Versión `4eefde7493e5`, semilla elegida 44 (menor pérdida de validación entre 42 y 46), 35 épocas, 241 parámetros. TensorFlow 2.21.0, Keras 3.15.1, scikit-learn 1.9.1. Prueba: 200 clientes no vistos, 42,5% con churn.

| Modelo | Accuracy | Precisión | Recall | AUC | Brier |
|---|---|---|---|---|---|
| Línea base (nadie se va) | 57,50% | | | | |
| Red neuronal (Keras) | 74,00% | 73,91% | 60,00% | 0,794 | 0,180 |
| Regresión logística | 77,00% | 77,46% | 64,71% | 0,812 | 0,175 |
| Oráculo (fórmula real) | 76,00% | 76,06% | 63,53% | 0,814 | 0,174 |

Matriz de confusión de la red (umbral 0,5): VN 97, FP 18, FN 34, VP 51.

## Pregunta 2

Promedio de 5 semillas (42 a 46), misma red y mismos datos.

| | Accuracy | AUC | Pérdida final |
|---|---|---|---|
| Con `StandardScaler` | 74,30% | 0,796 | 0,541 |
| Sin `StandardScaler` | 70,20% | 0,755 | 0,582 |

## Actividad 1 y SUPER VIP

| Cliente | Prob. predicha | Prob. real | Clasificación | Costo USD |
|---|---|---|---|---|
| ACT-001 Ana Gomez | 91,03% | 88,4% | CRÍTICO VIP | 26,10 |
| ACT-002 Carlos Ruiz | 91,50% | 86,9% | CRÍTICO ESTÁNDAR | 4,35 |
| ACT-003 Lucia Fernandez | 2,69% | 2,0% | BAJO (SEGURO) | 0,00 |
| ACT-004 Pedro Soto | 39,78% | 44,0% | BAJO (SEGURO) | 0,00 |
| ACT-005 Elena Castro | 3,24% | 7,5% | BAJO (SEGURO) | 0,00 |
| ACT-006 Martina Rojas | 91,45% | 95,0% | CRÍTICO SUPER VIP | 49,00 |

Presupuesto de los 5 clientes de la guía: USD 30,45. ACT-006 es un cliente ficticio que demuestra la regla SUPER VIP y no se cuenta en la Actividad 1.

## Evidencias

Carpeta `docs/evidencias/`:

| Archivo | Qué muestra |
|---|---|
| `evidencia-1-atlas-colecciones.png` | Atlas Data Explorer: Cluster0, base `streamedu_db` con sus 5 colecciones y `historical_customers` abierta (1000 documentos). La cantidad de las demás colecciones se ve en la captura 2 |
| `evidencia-2-consola.png` | Resumen de `preparar_evidencias.py` en PowerShell: conteos, red, métricas, pregunta 2 y tabla de los 6 clientes |
| `evidencia-3-atlas-super-vip.png` | `retention_actions` filtrada por `SUPER_VIP`: registro de ACT-006 |
| `resultados.json` | Todos los valores de esta página y del Word |

## Revisión de seguridad

- Pruebas: 50 OK (`python -B -m unittest`, sin Atlas).
- bandit: sin hallazgos.
- pip-audit: sin vulnerabilidades conocidas en `requirements.txt`.
- Búsqueda de secretos: sin resultados.
- `.gitignore` excluye `.env` y `modelos/`.
- Usuario de Atlas: `scripts/diagnostico.py` comprobó que puede leer, escribir y borrar en `streamedu_db` y que Atlas le deniega la lectura de una base distinta.

## Cambios durante la ejecución en Windows

| Paso | Archivo | Cambio |
|---|---|---|
| Fase 0, 0.10 | `scripts/diagnostico.py` | La prueba de permisos mínimos también reconoce el código 8000 de Atlas, solo si el texto del error dice "not allowed" |
| Fase 5, 5.8 | Generador del Word (fuera del repositorio) | Pregunta 1: "77% más caro" pasó a "las reglas ahorran un 77%" |

Fases 1 a 4: ninguno.
