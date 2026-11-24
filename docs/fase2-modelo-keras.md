# Fase 2: red neuronal con Keras (script 2)

## Arquitectura (la de la guía, sin cambios)

| Capa | Neuronas | Activación | Parámetros | Para qué |
|---|---|---|---|---|
| Entrada | 5 | | | meses, horas de uso, tickets, fallos de pago, días sin conectar (escaladas) |
| Dense `oculta_1` | 16 | ReLU | 5 × 16 + 16 = 96 | combina las variables en "conceptos" (por ejemplo, desconexión con fallos de pago) |
| Dropout | | 20% | 0 | apaga neuronas al azar al entrenar para no memorizar (sobreajuste) |
| Dense `oculta_2` | 8 | ReLU | 16 × 8 + 8 = 136 | resume los conceptos |
| Dense `salida` | 1 | Sigmoid | 8 + 1 = 9 | probabilidad de abandono entre 0 y 1 |
| **Total** | | | **241** | (Keras muestra además 484 valores internos del optimizador Adam) |

Compilación: Adam, entropía cruzada binaria, 35 épocas, lote 16, 10% del entrenamiento como validación.

## Cambios respecto del docente

1. **Reproducible:** `keras.utils.set_random_seed` y operaciones deterministas. Dos ejecuciones con la misma semilla dan exactamente lo mismo (prueba automática). En el código del docente Pedro (ACT-004) daba entre 36,8% y 53,8% según la corrida.
2. **5 reinicios, elegidos por validación.** Con la semilla 42 la red quedó con neuronas ReLU inactivas para los clientes de bajo riesgo y entregaba 30,2% tanto a Lucía como a Elena (su probabilidad real es 2,0% y 7,5%). En vez de elegir la semilla a mano, se entrenan las semillas 42 a 46 y se queda la de menor pérdida de **validación**; el conjunto de prueba no participa en la elección.
3. **División estratificada:** 80/20 con la misma proporción de churn en ambos lados (42,5%).
4. **Medición completa** sobre los 200 clientes de prueba: línea base ("nadie se va"), accuracy, precisión, recall, F1, AUC, Brier y matriz de confusión, comparadas con una regresión logística y con el **oráculo** (la fórmula con que se generaron las etiquetas, que existe porque los datos son sintéticos).
5. **Sin pickle:** el escalador se guarda como JSON (media y desviación), y `metadata.json` guarda la huella SHA-256 del modelo y del escalador. El pipeline y la API se niegan a cargar archivos alterados. El `.keras` se carga con `safe_mode=True`.
6. **Métricas en Atlas:** cada entrenamiento queda en `metricas_modelo` con la pérdida por época.

## Resultados de referencia (base simulada en Linux; los del Word salen de la ejecución en Windows)

| Modelo | Accuracy | AUC | Brier |
|---|---|---|---|
| Línea base | 57,5% | | |
| Red neuronal (semilla 44) | 74,0% | 0,794 | 0,180 |
| Regresión logística | 77,0% | 0,812 | 0,175 |
| Oráculo | 76,0% | 0,814 | 0,174 |

La red queda cerca del techo (el oráculo) y no supera a la regresión logística: los datos se generaron con una fórmula logística, así que un modelo lineal ya es el modelo correcto. Una red densa rinde más cuando las relaciones no son lineales o hay muchas variables.

## Pregunta 2: sin StandardScaler

`& $py -B 2_train_model.py --sin-escalador` entrena la misma red con y sin escalador para las semillas 42 a 46 (no reemplaza el modelo guardado):

| | Con escalador | Sin escalador |
|---|---|---|
| Test Accuracy media | 74,3% | 70,2% |
| AUC media | 0,796 | 0,755 |
| Pérdida final media | 0,541 | 0,582 |

Sin escalar, las variables con números grandes (meses hasta 35, días hasta 29) dominan los gradientes frente a las chicas (fallos de pago de 0 a 3), y en 35 épocas la red aprende peor. En el código del docente, comentar la línea del escalador rompe el script (`X_train_scaled` deja de existir) y además el pipeline seguiría escalando: por eso se hizo como opción aparte.

## Pruebas (`tests/test_modelo.py`)

Arquitectura y 241 parámetros; división 800/200 estratificada; métricas presentes; misma semilla, mismas predicciones; artefactos sin `.pkl` y carga idéntica; detecta escalador alterado o faltante; experimento sin escalador.
