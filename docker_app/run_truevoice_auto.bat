@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

echo ============================================================
echo     TrueVoice - Iniciar Docker y ejecutar contenedores
echo ============================================================
echo.

REM 1) Ir a la carpeta del script
cd /d "%~dp0"

REM 2) Iniciar Ollama antes de Docker
where ollama >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro el comando ollama en PATH.
    echo Instala Ollama y vuelve a intentarlo.
    pause
    exit /b 1
)

ollama list >nul 2>&1
if errorlevel 1 (
    echo Ollama no esta activo. Intentando iniciarlo...
    start /min "Ollama" ollama serve

    echo Esperando a que Ollama quede operativo...
    set /a OLLAMA_MAX_ATTEMPTS=24
    set /a OLLAMA_ATTEMPT=0

    :wait_ollama
    set /a OLLAMA_ATTEMPT+=1
    ollama list >nul 2>&1
    if not errorlevel 1 goto ollama_ready

    if !OLLAMA_ATTEMPT! GEQ !OLLAMA_MAX_ATTEMPTS! (
        echo [ERROR] Ollama no estuvo listo a tiempo.
        echo Inicia Ollama manualmente y reintenta.
        pause
        exit /b 1
    )

    timeout /t 5 /nobreak >nul
    goto wait_ollama
)

:ollama_ready
echo [OK] Ollama disponible
echo.

REM 3) Verificar que Docker CLI exista
where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro el comando docker en PATH.
    echo Instala Docker Desktop y vuelve a intentarlo.
    pause
    exit /b 1
)

REM 4) Si Docker ya esta listo, no abrir Docker Desktop
docker info >nul 2>&1
if errorlevel 1 (
    echo Docker no esta listo. Intentando abrir Docker Desktop...

    set "DOCKER_DESKTOP="
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" set "DOCKER_DESKTOP=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    if not defined DOCKER_DESKTOP if exist "%LocalAppData%\Docker\Docker Desktop.exe" set "DOCKER_DESKTOP=%LocalAppData%\Docker\Docker Desktop.exe"

    if not defined DOCKER_DESKTOP (
        echo [ERROR] No se encontro Docker Desktop.exe.
        echo Ruta esperada: %ProgramFiles%\Docker\Docker\Docker Desktop.exe
        pause
        exit /b 1
    )

    start /min "Docker Desktop" "!DOCKER_DESKTOP!"

    echo Esperando a que Docker quede operativo...
    set /a MAX_ATTEMPTS=48
    set /a ATTEMPT=0

    :wait_docker
    set /a ATTEMPT+=1
    docker info >nul 2>&1
    if not errorlevel 1 goto docker_ready

    if !ATTEMPT! GEQ !MAX_ATTEMPTS! (
        echo [ERROR] Docker no estuvo listo a tiempo.
        echo Abre Docker Desktop manualmente y reintenta.
        pause
        exit /b 1
    )

    timeout /t 5 /nobreak >nul
    goto wait_docker
)

:docker_ready
echo [OK] Docker disponible
echo.

REM 5) Verificar que las imagenes existan antes de ejecutar
docker image inspect truevoice-api:latest >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Falta la imagen truevoice-api:latest.
    echo Ejecuta deploy.bat para construirla o cargarla desde .tar.
    pause
    exit /b 1
)

docker image inspect truevoice-frontend:latest >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Falta la imagen truevoice-frontend:latest.
    echo Ejecuta deploy.bat para construirla o cargarla desde .tar.
    pause
    exit /b 1
)

REM 6) Levantar contenedores sin reconstruir imagenes
echo Iniciando contenedores TrueVoice...
docker compose up -d --no-build
if errorlevel 1 (
    echo [ERROR] Fallo al iniciar los contenedores.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo [OK] TrueVoice iniciado correctamente
echo  Frontend: http://localhost:8501
echo  API:      http://localhost:8000
echo ============================================================
echo.

start http://localhost:8501
