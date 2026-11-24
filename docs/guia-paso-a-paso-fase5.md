# Guía paso a paso, Fase 5: evidencias y repositorio

Requisito: la Fase 0 terminada (diagnóstico OK). Tiempo estimado: 20 minutos.
En cada PowerShell nuevo, primero:

```powershell
cd "$env:USERPROFILE\OneDrive\Escritorio\Estudio\Semestre10\Aplicaciones de Inteligencia Artificial\Unidad-3\Tarea-3\streamedu-churn"
$py = "$env:USERPROFILE\.virtualenvs\streamedu-churn\Scripts\python.exe"
```

## 1. Pruebas automáticas

```powershell
& $py -B -m unittest
```

Esperado: `Ran 50 tests in ...` y `OK` (tarda cerca de 1 minuto). No usan Atlas.

## 2. Ejecutar el flujo completo en Atlas

```powershell
& $py -B scripts\preparar_evidencias.py
```

Tarda de 2 a 4 minutos. Hace, en orden: script 1 con `--reiniciar`, script 2 (5 reinicios), experimento sin escalador (pregunta 2), script 3 con los 5 clientes (Actividad 1), agrega ACT-006 y vuelve a ejecutar el script 3 (pregunta 4). Termina con un resumen como este (tus números pueden variar levemente):

```
======================================================================================
STREAMEDU | Deep Learning + MongoDB Atlas | base streamedu_db | modelo 89aa3b66d701
======================================================================================
Atlas: active_customers 6 | evaluaciones 2 | historical_customers 1000 | metricas_modelo 2 | retention_actions 3
Red: Entrada(5) > Dense 16 ReLU > Dropout 0,2 > Dense 8 ReLU > Dense 1 Sigmoid | 241 parámetros | ...
Prueba (200 clientes no vistos): Test Accuracy 74.00% | AUC 0.794 | ...
Pregunta 2 (5 semillas): con escalador 74.30% | sin escalador 70.20%
--------------------------------------------------------------------------------------
ID       Nombre             Prob.  Clasificación        Costo  Acción
ACT-001  Ana Gomez         91.03%  CRÍTICO VIP          26.10  Llamada urgente de Ejecutivo ...
...
ACT-006  Martina Rojas     91.45%  CRÍTICO SUPER VIP    49.00  1 Mes Gratis + Mentoría 1 a 1
--------------------------------------------------------------------------------------
[OK] Resultados en docs\evidencias\resultados.json | 120 s
```

Si aparece `[AVISO] No se pudo crear el validador`, avísame (el usuario no pudo crear la colección con validación; los datos igual quedan cargados).

## 3. Las 3 capturas

Usa **Win + Shift + S** (recorte de pantalla) y pégalas en el chat. Yo las guardo en `docs\evidencias\` con su nombre.

| # | Nombre | Qué mostrar | Criterio de la pauta |
|---|---|---|---|
| 1 | `evidencia-1-atlas-colecciones` | Atlas → tu clúster → **Browse Collections** (Data Explorer) → clic en la base `streamedu_db`: la lista de colecciones con su cantidad de documentos (1000, 6, 3...) y el nombre del clúster arriba | 1: conexión y carga en la nube |
| 2 | `evidencia-2-consola` | La ventana de PowerShell con el resumen final del paso 2 (desde la línea `====` hasta `[OK] Resultados`) | 2 y 3: entrenamiento y Actividad 1 |
| 3 | `evidencia-3-atlas-super-vip` | Data Explorer → `streamedu_db` → `retention_actions`. En **Filter** escribe `{ "decision_negocio.segmento": "SUPER_VIP" }` y **Apply**. Expande `decision_negocio` para que se vean `customer_id: "ACT-006"`, la clasificación, la acción y el costo | 4: reto SUPER VIP (la guía pide esta captura) |

Revisa que en ninguna captura aparezca la URI, la contraseña ni la pestaña Database Access.

## 4. Repositorio en GitHub

**4.1 Crear el repositorio vacío.** En github.com (cuenta `Matic539`): **New repository** → nombre `streamedu-churn` → **Public** → sin README, sin .gitignore y sin licencia → **Create repository**.

**4.2 Subir el proyecto** (yo te aviso cuando el código y las capturas estén listos):

```powershell
git --version
git init -b main
git add .
git status --short
```

Revisa la lista de `git status --short`: **no** debe aparecer `.env` ni la carpeta `modelos`. Si aparecen, detente y avísame. Luego:

```powershell
git commit -m "StreamEdu: churn con Deep Learning, reglas de negocio y MongoDB Atlas (Tarea 3)"
git remote add origin https://github.com/Matic539/streamedu-churn.git
git push -u origin main
```

Si `git commit` pide tu nombre y correo: `git config --global user.name "Matias Lopez"` y `git config --global user.email "<tu correo de GitHub>"`, y repite el commit. El `push` abre una ventana para iniciar sesión en GitHub la primera vez.

## 5. Entregar

En `Tarea-3\entrega\` queda el Word completado. Ábrelo, revisa la portada y súbelo a la plataforma del ramo. El enlace del repositorio ya va en la portada.

## Solución de problemas

| Síntoma | Solución |
|---|---|
| `No hay modelo entrenado` en el script 3 | Ejecuta el script 2 (o `preparar_evidencias.py`, que lo hace todo) |
| `No se pudo llegar a Atlas a tiempo` | Tu IP cambió: Network Access → Add Current IP Address |
| `MongoDB rechazó la operación (BulkWriteError)` | Algún documento no cumple el validador. Repite con `& $py -B 1_seed_mongodb.py --reiniciar` y avísame |
| La captura 3 no muestra documentos | Revisa que el filtro tenga comillas rectas y que hayas aplicado el paso 2 completo |
| `git` no se reconoce | Instala Git para Windows (git-scm.com) con las opciones por defecto y abre otra terminal |
| `git push` rechazado | El repositorio no estaba vacío: bórralo y créalo de nuevo sin README |
