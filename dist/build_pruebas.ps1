Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $root 'dist'
$outDir = Join-Path $distDir 'TrueVoice_Pruebas'

$runtimeCandidates = @(
  (Join-Path $env:LOCALAPPDATA 'TrueVoice\runtime'),
  (Join-Path $env:APPDATA 'TrueVoice\runtime'),
  (Join-Path 'C:\Program Files\TrueVoice_Inst' 'runtime'),
  (Join-Path 'C:\Program Files\TrueVoice' 'runtime')
)

function Resolve-RuntimeSource {
  foreach ($candidate in $runtimeCandidates) {
    if (-not (Test-Path $candidate)) { continue }
    $ready    = Join-Path $candidate '.ready'
    $modelDir = Join-Path $candidate 'models\huggingface\models--microsoft--VibeVoice-1.5b'
    if ((Test-Path $ready) -and (Test-Path $modelDir)) {
      return $candidate
    }
  }
  throw 'No se encontro runtime listo con el modelo microsoft/VibeVoice-1.5b. Ejecuta una vez el bootstrap para descargarlo.'
}

# -----------------------------------------------------------------------
Write-Host '[1/7] Localizando runtime con modelo descargado...'
$runtimeSource = Resolve-RuntimeSource
Write-Host "    Runtime detectado: $runtimeSource"

# -----------------------------------------------------------------------
Write-Host '[2/7] Preparando carpeta de salida...'
if (Test-Path $outDir) {
  Write-Host "    Limpiando carpeta existente: $outDir"
  Remove-Item -Recurse -Force $outDir
}
New-Item -ItemType Directory -Path $outDir | Out-Null
Write-Host "    Carpeta creada: $outDir"

# -----------------------------------------------------------------------
Write-Host '[3/7] Exportando frontend web (Expo)...'
$webDistSrc  = Join-Path $root 'truevoice-web\dist'
$webDistDst  = Join-Path $root 'truevoice-go\internal\server\webdist'
$expoCliPath = Join-Path $root 'truevoice-web\node_modules\expo\bin\cli'

if (Test-Path $expoCliPath) {
  Push-Location (Join-Path $root 'truevoice-web')
  try {
    node .\node_modules\expo\bin\cli export --platform web
  } finally {
    Pop-Location
  }

  Write-Host '[4/7] Copiando webdist exportado al backend...'
  if (-not (Test-Path $webDistSrc)) { throw "No existe $webDistSrc tras el export" }
  if (Test-Path $webDistDst) { Remove-Item -Recurse -Force $webDistDst }
  New-Item -ItemType Directory -Path $webDistDst | Out-Null
  Copy-Item -Path (Join-Path $webDistSrc '*') -Destination $webDistDst -Recurse -Force
} else {
  Write-Host '    node_modules no encontrados; usando webdist ya compilado en truevoice-go...'
  if (-not (Test-Path (Join-Path $webDistDst 'index.html'))) {
    throw "No hay webdist en $webDistDst y tampoco hay node_modules para hacer export. Ejecuta 'npm install' en truevoice-web primero."
  }
  Write-Host '    OK - webdist existente sera embebido en el binario.'
  Write-Host '[4/7] (Paso omitido - webdist ya en su lugar)'
}

# -----------------------------------------------------------------------
Write-Host '[5/7] Compilando truevoice.exe...'
Push-Location (Join-Path $root 'truevoice-go')
try {
  go build -o (Join-Path $outDir 'truevoice.exe') .\cmd\truevoice
} finally {
  Pop-Location
}

# -----------------------------------------------------------------------
Write-Host '[6/7] Copiando archivos de la app...'

# Python sidecar y recursos
Copy-Item (Join-Path $root 'vibevoice_app.py')    $outDir -Force
Copy-Item (Join-Path $root 'inference_wrapper.py') $outDir -Force
Copy-Item (Join-Path $root 'patches.py')           $outDir -Force
Copy-Item (Join-Path $root 'frontend_config.json') $outDir -Force
Copy-Item (Join-Path $root 'requirements.txt')     $outDir -Force

# Paquete VibeVoice
if (Test-Path (Join-Path $root 'VibeVoice')) {
  Write-Host '    Copiando VibeVoice...'
  Copy-Item (Join-Path $root 'VibeVoice') (Join-Path $outDir 'VibeVoice') -Recurse -Force
}

# Runtime Python + modelo (la parte pesada)
Write-Host '    Copiando runtime Python + modelo (puede tardar unos minutos)...'
Copy-Item $runtimeSource (Join-Path $outDir 'runtime') -Recurse -Force

# Carpetas de datos vacías (se crean en el destino también)
foreach ($d in @('api_outputs', 'temp_outputs', 'voices', 'race_sessions', 'contexts')) {
  New-Item -ItemType Directory -Path (Join-Path $outDir $d) -Force | Out-Null
}

# -----------------------------------------------------------------------
Write-Host '[7/7] Generando scripts de arranque y parada...'

$startBat = @'
@echo off
setlocal
set "APP_ROOT=%~dp0"
set "TRUEVOICE_RUNTIME_DIR=%APP_ROOT%runtime"
set "HF_HOME=%TRUEVOICE_RUNTIME_DIR%\models\huggingface"
set "TRANSFORMERS_CACHE=%HF_HOME%\transformers"
set "MKL_NUM_THREADS=0"
set "OPENBLAS_NUM_THREADS=0"
set "NUMEXPR_NUM_THREADS=0"
set "TOKENIZERS_PARALLELISM=true"

start "TrueVoice" /D "%APP_ROOT%" "%APP_ROOT%truevoice.exe"
echo Esperando servidor en http://localhost:8000 ...
timeout /t 3 /nobreak >nul
start "" http://localhost:8000/app
endlocal
'@
Set-Content -Path (Join-Path $outDir 'start_app.bat') -Value $startBat -Encoding ASCII

$stopBat = @'
@echo off
setlocal
for /f "tokens=2 delims=," %%P in ('tasklist /FI "IMAGENAME eq truevoice.exe" /FO CSV /NH') do (
  taskkill /PID %%~P /F >nul 2>nul
)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root=[System.IO.Path]::GetFullPath('%~dp0'); ^
   Get-CimInstance Win32_Process | Where-Object { ^
     $_.Name -eq 'python.exe' -and $_.ExecutablePath -like ($root + 'runtime\python\*') ^
   } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo TrueVoice detenido.
endlocal
'@
Set-Content -Path (Join-Path $outDir 'stop_app.bat') -Value $stopBat -Encoding ASCII

# -----------------------------------------------------------------------
Write-Host ''
Write-Host '====================================================='
Write-Host "  Carpeta lista: $outDir"
$sizeBytes = (Get-ChildItem $outDir -Recurse -File | Measure-Object -Property Length -Sum).Sum
$sizeGb = [Math]::Round($sizeBytes / 1GB, 2)
Write-Host "  Tamanyo aproximado: $sizeGb GB"
Write-Host ''
Write-Host '  Para probar:  ejecuta start_app.bat'
Write-Host '  Para zipear:  Compress-Archive -Path dist\TrueVoice_Pruebas -DestinationPath dist\TrueVoice_Pruebas.zip'
Write-Host '====================================================='
