@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

echo ============================================================
echo       TrueVoice - Exportar imagenes Docker a .tar
echo ============================================================
echo.
echo Este script exporta las imagenes Docker a archivos .tar
echo para poder desplegar la aplicacion en otro PC sin internet.
echo.

REM Verificar Docker
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker no esta disponible o no esta iniciado.
    pause
    exit /b 1
)

REM Posicionarse en el directorio del script
cd /d "%~dp0"

REM Verificar que las imagenes existen
docker image inspect truevoice-api:latest >nul 2>&1
if errorlevel 1 (
    echo [ERROR] La imagen truevoice-api:latest no existe.
    echo Ejecuta deploy.bat primero para construirla.
    pause
    exit /b 1
)
docker image inspect truevoice-frontend:latest >nul 2>&1
if errorlevel 1 (
    echo [ERROR] La imagen truevoice-frontend:latest no existe.
    echo Ejecuta deploy.bat primero para construirla.
    pause
    exit /b 1
)

echo Exportando truevoice-api:latest ...
echo ^(Este archivo puede pesar varios GB, ten paciencia^)
docker save truevoice-api:latest -o truevoice-api.tar
if errorlevel 1 ( echo [ERROR] Fallo al exportar truevoice-api & pause & exit /b 1 )
echo [OK] truevoice-api.tar creado

echo.
echo Exportando truevoice-frontend:latest ...
docker save truevoice-frontend:latest -o truevoice-frontend.tar
if errorlevel 1 ( echo [ERROR] Fallo al exportar truevoice-frontend & pause & exit /b 1 )
echo [OK] truevoice-frontend.tar creado

echo.
echo ============================================================
echo [OK] Exportacion completada!
echo.
echo Copia la carpeta docker_app\ completa (incluyendo los .tar)
echo al otro PC y ejecuta deploy.bat desde alli.
echo ============================================================
echo.
pause
