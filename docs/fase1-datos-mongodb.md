# Fase 1: datos en MongoDB Atlas (script 1)

## Qué hace

`1_seed_mongodb.py` genera los 1.000 clientes históricos y carga los 5 clientes activos de la guía en la base `streamedu_db` de Atlas.

| Colección | Contenido | Índices y validación |
|---|---|---|
| `historical_customers` | 1.000 clientes pasados con la etiqueta `churn` (425 con churn = 1, 42,5%) | `customer_id` único; validador `$jsonSchema` (tipos y rangos) |
| `active_customers` | Los 5 clientes de la guía (ACT-001 a ACT-005) y, con `--demo-super-vip`, ACT-006 | `customer_id` único; validador `$jsonSchema` |
| `retention_actions` | Acciones de retención (las crea el script 3) | Índice parcial único: a lo más una acción `PENDIENTE_EJECUCION` por cliente |
| `evaluaciones` | Una fila por ejecución del script 3 | `corrida_id` único |
| `metricas_modelo` | Métricas de cada entrenamiento y del experimento de la pregunta 2 | índice por fecha |
| `api_predictions_log` | Consultas a la API (script 4) | |

## Cambios respecto del docente

1. **Mismos datos:** el generador usa la misma semilla (42) y el mismo orden de sorteos, pero con un generador propio (`RandomState`) en vez del estado global de numpy. Una prueba compara documento por documento contra el script del docente.
2. **Falla si falta la URI** (el docente caía en `localhost:27017` sin avisar) y exige una cadena de Atlas. La conexión usa timeout de 8 s y `ping`, con mensajes que orientan (IP no autorizada, usuario o contraseña, clúster mal escrito).
3. **Idempotente:** los documentos se cargan con `ReplaceOne(..., upsert=True)` por `customer_id`. Ejecutarlo dos veces deja los mismos 1.000 + 5 documentos. El borrado solo ocurre con `--reiniciar` y solo en las colecciones del laboratorio.
4. **Validación en la base:** rangos únicos en `streamedu/config.py` (`RANGOS`) que usan el validador de MongoDB, el pipeline y la API (por ejemplo, 0 a 168 horas por semana).

## Uso

```powershell
& $py -B 1_seed_mongodb.py                    # carga o actualiza
& $py -B 1_seed_mongodb.py --demo-super-vip   # agrega ACT-006 para el reto SUPER VIP
& $py -B 1_seed_mongodb.py --reiniciar        # borra las colecciones del laboratorio y carga de cero
& $py -B 1_seed_mongodb.py --solo-verificar   # solo muestra conteos
```

## Pruebas (`tests/test_datos.py`, `tests/test_mongo.py`)

- 1.000 históricos, 425 con churn, identificadores únicos y reproducibles.
- Idénticos al script del docente (si `../streamedu-churn-dl` está al lado; si no, la prueba se omite).
- Todos los documentos cumplen el `$jsonSchema` (validador mínimo en las pruebas, porque la base simulada no valida) y los documentos malos se rechazan.
- Carga idempotente, `--demo-super-vip`, `--reiniciar` e índices.
- Configuración: sin URI, con texto de ejemplo, sin Atlas o sin credenciales falla; la contraseña nunca aparece en los mensajes.
