# Guía paso a paso, Fase 0: entorno y MongoDB Atlas

Tiempo estimado: 20 a 30 minutos (la instalación de TensorFlow es lo más lento).
Todo se ejecuta en **PowerShell** (Windows Terminal). Copia los comandos tal cual.

Al terminar tendrás: un entorno virtual con las dependencias exactas, una base `streamedu_db` en tu clúster de Atlas con un usuario de permisos mínimos y el diagnóstico en verde.

---

## 1. Ir a la carpeta del proyecto

```powershell
cd "$env:USERPROFILE\OneDrive\Escritorio\Estudio\Semestre10\Aplicaciones de Inteligencia Artificial\Unidad-3\Tarea-3\streamedu-churn"
Get-ChildItem -Name
```

Salida esperada (entre otros): `requirements.txt`, `.env.example`, `streamedu`, `scripts`, `docs`.

## 2. Crear el entorno virtual (fuera de OneDrive)

```powershell
py -3.13 --version
py -3.13 -m venv "$env:USERPROFILE\.virtualenvs\streamedu-churn"
$py = "$env:USERPROFILE\.virtualenvs\streamedu-churn\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install --require-hashes -r requirements.txt
```

- La primera línea debe mostrar `Python 3.13.x`.
- La última descarga unos 600 MB (TensorFlow) y tarda de 5 a 10 minutos. Termina con `Successfully installed ...` y sin líneas `ERROR`.
- `--require-hashes` verifica que cada paquete sea exactamente el que se probó.

> En cada PowerShell nuevo vuelve a definir `$py` (línea 3) antes de los demás comandos.

## 3. Preparar MongoDB Atlas (en el navegador)

Usa tu clúster M0 actual (proyecto "IA"). No se crea otro clúster.

**3.1 Usuario de base de datos con permisos mínimos**

1. Menú izquierdo: **Database Access** → **+ Add New Database User**.
2. Authentication Method: **Password**. Username: `streamedu_app`.
3. Clic en **Autogenerate Secure Password** y guárdala en tu gestor de contraseñas. No la pegues en el chat.
4. En **Database User Privileges**, en vez de un rol general, elige **Specific Privileges** → **Add Specific Privilege**: rol `readWrite`, base `streamedu_db`, colección en blanco.
5. Opcional: **Restrict Access to Specific Clusters** y marca solo tu clúster.
6. **Add User**.

**3.2 Acceso de red**

1. Menú izquierdo: **Network Access**.
2. Si tu IP actual no aparece, **Add IP Address** → **Add Current IP Address** → **Confirm**.
3. **No** agregues `0.0.0.0/0` (la guía lo sugiere, pero abre el clúster a todo internet).

**3.3 Copiar la cadena de conexión**

**Database** (o **Clusters**) → **Connect** en tu clúster → **Drivers** → Python. Copia la cadena `mongodb+srv://...`.

## 4. Crear el archivo .env

```powershell
Copy-Item .env.example .env
notepad .env
```

En el Bloc de notas, en la línea `MONGO_URI`, pega la cadena de Atlas entre comillas y reemplaza:
- el usuario por `streamedu_app`,
- `<db_password>` por la contraseña generada (sin los signos `<` `>`).

Deja `DB_NAME="streamedu_db"`. Guarda y cierra.

Comprueba que no quedaron marcadores (debe mostrar `0`), sin imprimir la cadena:

```powershell
(Select-String -Path .env -Pattern '<db_password>|<cluster>|tu_password').Count
```

## 5. Ejecutar el diagnóstico

```powershell
& $py -B scripts\diagnostico.py
```

Salida esperada (los tiempos cambian):

```
1. Python
  [OK]    Python 3.13.x
  [OK]    Entorno virtual fuera de OneDrive
2. Dependencias (versiones fijas de requirements.in)
  [OK]    tensorflow 2.21.0 (esperado 2.21.0)
  ... (10 líneas [OK])
3. TensorFlow
  [OK]    importa en 8.4 s; dispositivos: CPU
4. Archivo .env
  [OK]    .env existe
  [OK]    .env está en .gitignore
  [OK]    MONGO_URI con formato de Atlas: mongodb+srv://***@cluster0.ab***.mongodb.net  | DB_NAME = streamedu_db
5. MongoDB Atlas
  [OK]    ping respondió en 180 ms
  [OK]    el usuario puede escribir, leer y borrar en streamedu_db
  [OK]    permisos mínimos: el usuario no puede leer otras bases

Diagnóstico OK
```

La URI sale enmascarada, así que puedes pegarme la salida completa en el chat.

## 6. Pruebas automáticas

```powershell
& $py -B -m unittest
```

No usan Atlas (trabajan con una base simulada). Deben terminar en `OK`.

---

## Solución de problemas

| Síntoma | Causa y solución |
|---|---|
| `py` no reconoce `-3.13` | Python 3.13 no está instalado o no está en el lanzador. Revisa con `py -0`. |
| `pip` falla con `No such file or directory` o rutas largas | Windows limita las rutas a 260 caracteres. PowerShell **como administrador**: `New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force`, cierra la terminal y repite el paso 2. |
| `THESE PACKAGES DO NOT MATCH THE HASHES` | Descarga corrupta en la caché. Repite con `& $py -m pip install --no-cache-dir --require-hashes -r requirements.txt`. |
| `ImportError: DLL load failed` al importar TensorFlow | Falta el Visual C++ Redistributable de Microsoft (x64). Instálalo desde el sitio de Microsoft y reinicia la terminal. |
| `No se pudo llegar a Atlas a tiempo` | Tu IP cambió o no está en Network Access (paso 3.2). |
| `Atlas rechazó el usuario o la contraseña` | Revisa usuario y contraseña en `.env`. Si la contraseña tiene `@`, `:` o `/`, genera otra autogenerada (solo letras y números). |
| `No se pudo resolver el clúster` | El nombre del clúster en la URI está mal copiado. |
| `el usuario puede leer otras bases` | El usuario quedó con un rol general. En Database Access → Edit, deja solo `readWrite` en `streamedu_db`. |
| `MONGO_URI todavía tiene texto de ejemplo` | Quedó `<db_password>` o `<cluster>` en `.env`. |
