# StreamEdu: predicción de abandono con Deep Learning y MongoDB Atlas

Laboratorio de la Tarea 3, Unidad 3 · Aplicaciones de Inteligencia Artificial (TI2082) · INACAP
Estudiante: Matías López García · Docente: Ademar Araya Fuentes · Noviembre de 2026

StreamEdu es una plataforma de cursos por suscripción (USD 29 al mes). Este proyecto une tres partes:

1. **MongoDB Atlas:** historial de 1.000 clientes, clientes activos, acciones de retención, corridas y métricas.
2. **Red neuronal (TensorFlow/Keras):** estima la probabilidad de abandono, P(churn), de cada cliente activo.
3. **Reglas de negocio:** cruzan P(churn) con el LTV (meses pagados × 29) para decidir una acción rentable, incluido el nivel **SUPER VIP** (reto de la pregunta 4).

Es una versión propia del código base del docente (`streamedu-churn-dl`): mantiene los 4 scripts, sus nombres y la arquitectura de la red, y corrige los problemas encontrados en la revisión (`docs/fase0-revision-referencia.md`).

## Estructura

```
1_seed_mongodb.py        Script 1: carga los datos en Atlas (idempotente; --demo-super-vip, --reiniciar)
2_train_model.py         Script 2: entrena la red y mide (--sin-escalador: pregunta 2)
3_business_pipeline.py   Script 3: predice, aplica las reglas y guarda las acciones en Atlas
4_api_fastapi.py         Script 4 (bonus): API REST en 127.0.0.1:8000
streamedu/               Paquete: config, db, datos, modelo, negocio, pipeline y api
scripts/                 diagnostico.py, verificar_atlas.py, preparar_evidencias.py y revisar_resultados.py
tests/                   Pruebas automáticas (unittest + mongomock; no usan Atlas)
docs/                    Documento por fase, guías paso a paso y evidencias
```

## Instalación (Windows, PowerShell)

```powershell
py -3.13 -m venv "$env:USERPROFILE\.virtualenvs\streamedu-churn"
$py = "$env:USERPROFILE\.virtualenvs\streamedu-churn\Scripts\python.exe"
& $py -m pip install --require-hashes -r requirements.txt
Copy-Item .env.example .env      # pegar la URI de Atlas (usuario con readWrite solo en streamedu_db)
& $py -B scripts\diagnostico.py
& $py -B -m unittest
```

Detalle, Atlas y solución de problemas: `docs/guia-paso-a-paso-fase0.md`.

## Uso (orden de la guía)

```powershell
& $py -B 1_seed_mongodb.py
& $py -B 2_train_model.py
& $py -B 3_business_pipeline.py
& $py -B 2_train_model.py --sin-escalador      # pregunta 2
& $py -B 1_seed_mongodb.py --demo-super-vip    # pregunta 4: agrega ACT-006
& $py -B 3_business_pipeline.py
& $py -B 4_api_fastapi.py                      # opcional: http://127.0.0.1:8000/docs
```

O todo junto, dejando los resultados en `docs/evidencias/resultados.json`: `& $py -B scripts\preparar_evidencias.py`.

## Red neuronal

Entrada (5) → Dense 16 ReLU → Dropout 0,2 → Dense 8 ReLU → Dense 1 Sigmoid: **241 parámetros**, Adam, entropía cruzada binaria, 35 épocas, lote 16. Se entrenan 5 reinicios (semillas 42 a 46) y se elige el de menor pérdida de validación. Las métricas se comparan con la línea base, una regresión logística y el oráculo (la fórmula que generó los datos). Detalle: `docs/fase2-modelo-keras.md`.

## Reglas de negocio

| P(churn) | LTV | Clasificación | Acción | Costo USD |
|---|---|---|---|---|
| ≥ 0,70 | ≥ 500 | CRÍTICO SUPER VIP | 1 mes gratis + mentoría 1 a 1 | 49,00 (supuesto: 29 + 20) |
| ≥ 0,70 | 180 a 499 | CRÍTICO VIP | Llamada de ejecutivo + 30% por 3 meses | 26,10 |
| ≥ 0,70 | < 180 | CRÍTICO ESTÁNDAR | Email con cupón 15% por 1 mes | 4,35 |
| 0,40 a 0,69 | cualquiera | RIESGO MODERADO | Notificación in-app + encuesta | 0,50 |
| < 0,40 | cualquiera | BAJO (SEGURO) | Ninguna | 0,00 |

## Principales correcciones al código base

| Problema en el código base | Corrección |
|---|---|
| Sin semilla de TensorFlow: la tabla de la Actividad 1 cambia en cada corrida (Pedro pasa de BAJO a MODERADO) | Semillas, operaciones deterministas y reinicios elegidos por validación |
| Solo accuracy (impresa como "Precision") | Línea base, precisión, recall, F1, AUC, Brier, matriz de confusión, regresión logística y oráculo |
| Con los 5 clientes de la guía nadie puede ser SUPER VIP | Cliente ficticio ACT-006 con `--demo-super-vip` |
| El pipeline duplica las acciones en cada ejecución | Una acción pendiente por cliente, corridas registradas |
| Sin `MONGO_URI` se conecta a localhost sin avisar; la guía abre Atlas a `0.0.0.0/0` | URI de Atlas obligatoria; usuario con permisos mínimos y solo la IP propia |
| Escalador guardado con pickle | JSON con huella SHA-256 verificada; `.keras` con `safe_mode` |
| La API carga el modelo en cada petición, no valida rangos y responde 500 si Atlas falla | Carga única, validación (422), 503 sin modelo, Atlas con timeout, registro sin nombres |

## Seguridad

- El `.env` no se versiona (`.gitignore`); la URI nunca se imprime completa.
- Usuario de Atlas `streamedu_app` con `readWrite` solo en `streamedu_db`; acceso solo desde la IP propia.
- Sin pickle; los artefactos del modelo (`modelos/`) no se suben al repositorio y se regeneran con el script 2.
- Dependencias con versión fija y hash (`requirements.txt`).
- Datos 100% ficticios.
