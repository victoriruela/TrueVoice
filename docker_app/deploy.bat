@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

echo ============================================================
echo          TrueVoice - Despliegue automatico en Docker
echo ============================================================
echo.

REM ── 1. Verificar Docker ─────────────────────────────────────
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker no esta disponible o no esta iniciado.
    echo Por favor, inicia Docker Desktop e intentalo de nuevo.
    pause
    exit /b 1
)
echo [OK] Docker disponible
echo.

REM ── 2. Posicionarse en el directorio de este .bat ────────────
cd /d "%~dp0"

REM ── 3. Cargar imagenes desde .tar si existen ─────────────────
set BUILT=0
if exist "truevoice-api.tar" (
    if exist "truevoice-frontend.tar" (
        echo Cargando imagenes desde archivos .tar ...
        docker load -i truevoice-api.tar
        if errorlevel 1 ( echo [ERROR] Fallo al cargar truevoice-api.tar & pause & exit /b 1 )
        docker load -i truevoice-frontend.tar
        if errorlevel 1 ( echo [ERROR] Fallo al cargar truevoice-frontend.tar & pause & exit /b 1 )
        set BUILT=1
        echo [OK] Imagenes cargadas correctamente
        echo.
    )
)

REM ── 4. Si no hay .tar, construir desde codigo fuente ─────────
if !BUILT!==0 (
    echo No se encontraron archivos .tar.
    echo Construyendo imagenes desde codigo fuente...
    echo ^(La primera vez puede tardar 10-20 minutos^)
    echo.
    docker compose build
    if errorlevel 1 (
        echo [ERROR] Fallo al construir las imagenes.
        pause
        exit /b 1
    )
    echo [OK] Imagenes construidas correctamente
    echo.
)

REM ── 5. Advertencia sobre acceso al disco C: y RAM ───────────
echo IMPORTANTE: Requisitos previos antes de continuar:
echo.
echo  1. Docker Desktop ^> Settings ^> Resources ^> File Sharing
echo     Habilita el acceso a la unidad C:
echo.
echo  2. RAM para WSL2 (necesario para el modelo de IA ~6 GB):
echo     Crea o edita el archivo C:\Users\%USERNAME%\.wslconfig
echo     con el siguiente contenido:
echo       [wsl2]
echo       memory=14GB
echo     Luego ejecuta: wsl --shutdown  y reinicia Docker Desktop
echo.
echo  Si ya lo tienes configurado, ignora este mensaje.
echo.

REM ── 6. Detectar discos y generar override ────────────────────
echo Detectando discos del sistema...
powershell -ExecutionPolicy Bypass -File "%~dp0generate_drives.ps1"
if errorlevel 1 (
    echo [WARN] No se pudo generar el override de discos. Continuando con C: por defecto.
)
echo.

REM ── 7. Iniciar contenedores ──────────────────────────────────
echo Iniciando contenedores...
docker compose up -d
if errorlevel 1 (
    echo [ERROR] Fallo al iniciar los contenedores.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo [OK] TrueVoice iniciado correctamente!
echo.
echo  Accede a la aplicacion en: http://localhost:8501
echo.
echo  Las carpetas de voces y salida se eligen directamente
echo  desde el panel lateral de la aplicacion. Navega por
echo  los discos detectados en este PC y pulsa "Seleccionar".
echo ============================================================
echo.

REM Abrir el navegador automaticamente
timeout /t 3 /nobreak >nul
start http://localhost:8501

pause
