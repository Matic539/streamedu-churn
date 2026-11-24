# Fase 4: API FastAPI (script 4, bonus de la guía)

`& $py -B 4_api_fastapi.py` levanta la API en `http://127.0.0.1:8000` (documentación interactiva en `/docs`).

| Ruta | Qué hace |
|---|---|
| `POST /evaluar-cliente` | Predice, aplica la regla y registra la consulta en `api_predictions_log` |
| `GET /salud` | Indica si el modelo está cargado y su versión |

## Cambios respecto del docente

| Problema del docente | Corrección |
|---|---|
| Cargaba el modelo y el pickle en **cada** petición (150 a 330 ms) | Se carga una vez al iniciar; la inferencia toma ~2,5 ms |
| Aceptaba cuota −1000 (LTV −10.000), 500 horas por semana, 100.000 días, nombre de 100.000 caracteres, id vacío y campos extra | Rangos de `RANGOS`, formato `ACT-###`, largo máximo y `extra="forbid"`: responde 422 |
| Valores fuera de lo que vio el modelo se trataban igual | Responde `fuera_de_rango_entrenamiento` con las variables afectadas |
| Sin modelo respondía 500 | Responde 503 con un mensaje claro |
| Si Atlas fallaba respondía 500 y se perdía la predicción (con la URI de ejemplo de la guía siempre fallaba) | Timeout de 3 s; responde 200 con `sincronizado_mongodb_cloud: false` |
| Guardaba el nombre del cliente en el registro | Guarda el `customer_id` y las variables, no el nombre |
| Se ejecutaba con `--reload` | Solo `127.0.0.1` y sin recarga automática |

## Pruebas (`tests/test_api.py`)

Respuesta normal y registro sin nombre; el modelo se carga una sola vez; 10 entradas inválidas con 422; aviso fuera de rango; 503 sin modelo; respuesta sin Atlas; `/salud`.
