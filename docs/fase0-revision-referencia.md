# Fase 0: revisión del código base del docente y entorno

INACAP · TI2082 · Aplicaciones de Inteligencia Artificial · Tarea 3 (laboratorio Deep Learning + MongoDB)
Fecha: 21/11/2026

Este documento resume la revisión del material y del código base (`streamedu-churn-dl/`) antes de construir esta versión. Los scripts usados para verificar cada hallazgo están en `../revision-referencia/` (corren el código del docente sin modificarlo, con una base simulada).

## 1. Verificación del material

- `tarea 3.zip` y las carpetas son idénticos (MD5 de los 10 archivos). La guía en `Tarea-3/` y la copia en `streamedu-churn-dl/` son el mismo archivo.
- El código pegado en el Word coincide línea a línea con los 4 `.py`.
- **El material no trae `.pkl`, `.keras` ni modelos**: no había nada que cargar. El `scaler.pkl` lo crea el script 2 al entrenar.
- `.env.example` solo tiene marcadores (`usuario`, `tu-cluster`).
- `bash.txt` es idéntico al de la Tarea 2 (enlaces opcionales, no se usan).
- **Notebook de AI Horde:** generación de imágenes; no se relaciona con la guía. La única clave es la anónima pública de AI Horde (diez ceros, documentada por el servicio, no es un secreto). El adaptador se llama `openrouter` pero llama a AI Horde e ignora el modelo pedido; las celdas img2img y ControlNet lanzan `NotImplementedError`; las imágenes guardadas vienen de una ejecución anterior con un servicio de pago (hay comentarios de costo en USD). No se usa.
- **PDF de la clase:** 167 diapositivas "Actualidad de IA 2024, bloque 2" (Alejandro Cuevas Rivero) con marca "Confidencial". Aplican "Predicción de Churn" (clasificación, período de observación y desbalanceo de clases) y "Métodos supervisados" (redes neuronales: tratar el desbalanceo). Por la marca, no se incluye en ninguna entrega.
- **Material-estudio:** el AI Canvas (monetización, costo de inferencia) y el taller ayudan a argumentar la pregunta 1. Nada más aplica.

## 2. Ejecución de la referencia

Entorno aislado: Python 3.13, TensorFlow 2.21.0, Keras 3.15.1, scikit-learn 1.9.1, pymongo 4.20.1, FastAPI 0.165.0, con `mongomock` en lugar de Atlas. Los scripts del docente corrieron sin cambios. Scripts de la revisión en `Unidad-3/Tarea-3/revision-referencia/`.

**Datos:** 1.000 históricos con 42,5% de churn; el conjunto de prueba (200) tiene 42,0%. La semilla de numpy hace que los datos sean siempre los mismos.

**Modelo, sobre el mismo conjunto de prueba:**

| Modelo | Accuracy | AUC | Brier |
|---|---|---|---|
| Línea base: "nadie se va" | 58,0% | | |
| Red del docente (5 corridas) | 77,0% a 78,0% | 0,837 a 0,847 | 0,157 a 0,163 |
| Regresión logística | 80,5% | 0,849 | 0,155 |
| Oráculo: la fórmula oculta con que se generaron las etiquetas | 81,0% | 0,854 | 0,151 |

**Clientes activos (6 corridas de la red sin semilla):**

| Cliente | Prob. real (oráculo) | Red del docente | Nivel según la corrida |
|---|---|---|---|
| ACT-001 Ana | 88,4% | 80,8% a 86,5% | CRÍTICO |
| ACT-002 Carlos | 86,9% | 80,2% a 85,3% | CRÍTICO |
| ACT-003 Lucía | 2,0% | 1,8% a 4,0% | BAJO |
| ACT-004 Pedro | 44,0% | **36,8% a 53,8%** | **BAJO o MODERADO** |
| ACT-005 Elena | 7,5% | 3,2% a 6,8% | BAJO |

## 3. Hallazgos de la revisión

### 3.1 Modelo y medición

| # | Sev. | Hallazgo | Evidencia |
|---|---|---|---|
| M1 | Alta | Sin semilla de TensorFlow, cada corrida da otros números, y Pedro cruza el umbral de 40%: según la corrida queda BAJO (sin acción) o MODERADO. La tabla de la Actividad 1 no es reproducible. Con `keras.utils.set_random_seed(42)` dos corridas dan exactamente lo mismo (36,297%), aunque con esa semilla Pedro queda BAJO y su probabilidad real es 44,0%. | Tabla de la sección 3 |
| M2 | Media | Solo mide accuracy, y la imprime como "Precision". Con 42% de churn, decir "nadie se va" ya da 58%. Como las decisiones usan umbrales de probabilidad (0,40 y 0,70), importan también AUC, recall, matriz de confusión y calibración (Brier). | Sección 3 |
| M3 | Info | Los datos son sintéticos y la etiqueta sale de una fórmula logística: el techo es 81,0%. Una regresión logística llega a 80,5%; la red, a 77 a 78%. Aquí la red no supera a un modelo lineal, y es esperable. Conviene decirlo en el Word: muestra comprensión, no debilidad. | Sección 3 |
| M4 | Baja | `meses_antiguedad` no participa en la fórmula de abandono, así que la red debe aprender a ignorarla. El LTV, que depende solo de esa variable, es independiente del riesgo. | Lectura de `1_seed_mongodb.py` |
| M5 | Baja | `train_test_split` sin `stratify`. `input_shape` en `Dense` está obsoleto en Keras 3 y da un aviso en cada entrenamiento. | Ejecución |
| M6 | Media | Pregunta 2: comentar la línea del escalador rompe el script (`X_train_scaled` deja de existir), y el pipeline y la API siguen aplicando `scaler.pkl`. Medido bien (5 corridas cada uno): sin escalador 75,0% a 78,5% (media 76,3%) contra 77,0% a 78,0% (media 77,5%). La caída es chica y la variación crece, pero las **decisiones cambian**: Ana bajó a MODERADO en 2 de 5 corridas y Carlos en 1. | Ejecución |

### 3.2 Reglas de negocio y pipeline

| # | Sev. | Hallazgo | Evidencia |
|---|---|---|---|
| N1 | Alta | **Con los 5 clientes activos nadie llega a SUPER VIP.** LTV ≥ 500 exige 18 meses a USD 29: Lucía tiene LTV 580 pero riesgo 2%, y Ana es crítica pero tiene LTV 406. La captura de la pregunta 4 no se puede obtener sin agregar un cliente. Además, la guía dice "más de $500" y también "LTV >= 500", y no da el costo de "1 Mes Gratis + Mentoría 1 a 1". La regla debe evaluarse antes que la de VIP, que también se cumple. | Cálculo |
| N2 | Media | El pipeline no es idempotente: cada ejecución vuelve a insertar las acciones (3 → 6 tras dos corridas), sin identificador de corrida ni versión del modelo. No se sabe cuál acción está vigente. | Ejecución |
| N3 | Baja | La tabla de la guía distingue CRÍTICO VIP y CRÍTICO ESTÁNDAR; el código guarda "CRITICO" para ambos y el segmento queda solo en `es_cliente_vip`. | Lectura |
| N4 | Baja | Clasifica con la probabilidad sin redondear y la muestra con 1 decimal: 69,96% se ve como "70.0%" pero queda MODERADO. Montos como "$26.1" y "$0.0"; "1 meses". | Ejecución |
| N5 | Baja | No valida los documentos: un cliente activo sin `nombre` o sin una variable detiene el pipeline a mitad (KeyError), con parte de los clientes ya actualizados. Actualiza uno por uno en vez de en bloque. | Lectura |
| N6 | Negocio | El costo de la acción no se compara con lo que se arriesga perder. VIP empieza en el mes 7 (6 × 29 = 174 < 180). El LTV supone que todos los meses se pagaron a la cuota actual e ignora los fallos de pago. Sirve para la pregunta 1. | Cálculo |

### 3.3 Seguridad

| # | Sev. | Hallazgo |
|---|---|---|
| S1 | Alta | La guía indica Network Access `0.0.0.0/0` y no dice qué rol darle al usuario; el predeterminado de Atlas lee y escribe en cualquier base. Con la URI filtrada, cualquiera tendría acceso a todo el clúster, incluida la base de la Tarea 1. Corresponde: solo la IP propia y `readWrite` solo en `streamedu_db`. |
| S2 | Media | Si falta `MONGO_URI`, `MongoClient(None)` se conecta a `localhost:27017` sin avisar (verificado): se podría "cargar" en una base local creyendo que es Atlas. Sin `serverSelectionTimeoutMS` ni `ping`, una IP no autorizada deja el script colgado 30 s con un error poco claro. El script 1 borra las colecciones (`delete_many({})`) sin confirmación. |
| S3 | Media | `scaler.pkl` usa pickle: si alguien reemplaza el archivo en la carpeta, el pipeline y la API ejecutarían su código al cargarlo. Se evita guardando media y desviación en JSON, o con una capa `Normalization` dentro del `.keras`, que se carga con `safe_mode`. |
| S4 | Media | La API no valida rangos: cuota −1000 da LTV −10.000; acepta 500 horas por semana (una semana tiene 168) y 100.000 días sin conectar (sale CRÍTICO por extrapolación); un nombre de 100.000 caracteres; `customer_id` vacío; campos extra. Todo responde 200 y se guarda en Atlas. |
| S5 | Media | La API carga el modelo y el escalador en cada petición (150 a 330 ms y avisos de retracing de TensorFlow) y crea un `MongoClient` por petición. Si Atlas falla, responde 500 y se pierde la predicción. Con la URI de ejemplo de la propia guía (`cluster0.xxxx`) responde 500, porque el filtro solo reconoce "tu-cluster". Sin modelo responde 500 (corresponde 503). |
| S6 | Baja | La API guarda el documento completo del cliente, con nombre, en `api_predictions_log`: más datos personales de los necesarios. Sin autenticación (aceptable solo en `127.0.0.1`). Se ejecuta con `--reload`, que es modo desarrollo. |
| S7 | Baja | Sin `requirements.txt` ni versiones fijas; Pydantic avisa que `example=` en `Field` está obsoleto; sin `.gitignore`, así que el `.env` podría terminar en una entrega. |

**Lo que está bien:** la regla de negocio es una función pura y separada; el escalador se ajusta solo con los datos de entrenamiento (sin fuga); el modelo usa el formato nativo `.keras`; los costos coinciden con la tabla (30% × 29 × 3 = 26,10; 15% × 29 = 4,35); los datos son reproducibles; `.env.example` no trae credenciales.

## 4. Decisiones de esta versión

| Tema | Decisión | Motivo |
|---|---|---|
| Estructura | Se mantienen los 4 scripts con sus nombres y orden; la lógica va en el paquete `streamedu/` | La Actividad 1 y las preguntas 2 y 4 se refieren a esos scripts |
| Base de datos | MongoDB Atlas (clúster M0 existente), base `streamedu_db`, usuario `streamedu_app` con `readWrite` solo en esa base y acceso solo desde la IP propia | Criterio 1 de la pauta; corrige S1 |
| Configuración | `MONGO_URI` obligatoria y con formato de Atlas; error claro si falta; la URI nunca se imprime completa | Corrige S2 |
| Arquitectura | La de la guía sin cambios (241 parámetros) | La pauta evalúa "el modelo Keras de la guía" |
| Reproducibilidad | Semillas fijas, operaciones deterministas y 5 reinicios elegidos por pérdida de validación | Corrige M1 |
| Medición | Línea base, precisión, recall, F1, AUC, Brier y matriz de confusión, contra regresión logística y oráculo | Corrige M2 y M3 |
| Artefactos | `churn_model.keras` + `escalador.json` + `metadata.json` con SHA-256; sin pickle | Corrige S3 |
| Reglas | Función con la misma firma y claves; SUPER VIP antes que VIP; probabilidad redondeada antes de clasificar | Pregunta 4; N3 y N4 |
| Pipeline | Una acción pendiente por cliente, corrida registrada, validación de documentos, escritura en bloque | Corrige N2 y N5 |
| API | Modelo cargado una vez, rangos validados, 503 sin modelo, Atlas con timeout, log sin nombre, solo 127.0.0.1 | Corrige S4, S5 y S6 |
| Dependencias | `requirements.txt` con versiones fijas y hashes, resuelto para Windows y Python 3.13 | Corrige S7 |
| Entorno | Entorno virtual en `%USERPROFILE%\.virtualenvs\streamedu-churn` (fuera de OneDrive) | Rutas largas de TensorFlow y sincronización de OneDrive |

Guía de instalación: `guia-paso-a-paso-fase0.md`.

## Cambios durante la ejecución en Windows

| Fecha | Archivo | Qué falló | Qué se cambió y por qué |
|---|---|---|---|
| 24/11/2026 | `scripts/diagnostico.py` | La prueba de permisos mínimos mostraba `[AVISO] respuesta inesperada al probar permisos (8000)` | El clúster Atlas devolvió el código 8000 al denegar la lectura de otra base, y el script solo reconocía el 13. Ahora acepta también el 8000, solo si el texto del error dice "not allowed". Cualquier otro caso mantiene el aviso. Pruebas: 50 OK |
