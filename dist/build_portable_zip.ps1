Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $root 'dist'
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$stagingName = 'portable_staging_' + $stamp
$staging = Join-Path $distDir $stagingName
$zipPath = Join-Path $distDir 'TrueVoicePortable.zip'

$runtimeCandidates = @(
  (Join-Path $env:LOCALAPPDATA 'TrueVoice\runtime'),
  (Join-Path $env:APPDATA 'TrueVoice\runtime'),
  (Join-Path 'C:\Program Files\TrueVoice_Inst' 'runtime'),
  (Join-Path 'C:\Program Files\TrueVoice' 'runtime')
)

function Resolve-RuntimeSource {
  foreach ($candidate in $runtimeCandidates) {
    if (-not (Test-Path $candidate)) {
      continue
    }

    $ready = Join-Path $candidate '.ready'
    $modelDir = Join-Path $candidate 'models\huggingface\transformers\models--microsoft--VibeVoice-1.5b'
    if ((Test-Path $ready) -and (Test-Path $modelDir)) {
      return $candidate
    }
  }

  throw 'No se encontro runtime listo con el modelo microsoft/VibeVoice-1.5b. Ejecuta una vez el bootstrap para descargarlo.'
}

Write-Host '[1/8] Localizando runtime con modelo descargado...'
$runtimeSource = Resolve-RuntimeSource
Write-Host "Runtime detectado: $runtimeSource"

Write-Host '[2/8] Preparando carpetas temporales...'
if (Test-Path $zipPath) {
  try {
    Remove-Item -Force $zipPath -ErrorAction Stop
  } catch {
    $zipPath = Join-Path $distDir ("TrueVoicePortable_" + $stamp + ".zip")
    Write-Host "Aviso: TrueVoicePortable.zip esta bloqueado; se usara: $zipPath"
  }
}
New-Item -ItemType Directory -Path $staging | Out-Null

# Cleanup best-effort of old staging folders from previous runs.
$oldStagingDirs = Get-ChildItem -Path $distDir -Directory -Filter 'portable_staging_*' -ErrorAction SilentlyContinue
foreach ($old in $oldStagingDirs) {
  if ($null -eq $old -or -not ($old.PSObject.Properties.Name -contains 'FullName')) {
    continue
  }
  if ($old.FullName -eq $staging) {
    continue
  }

  try {
    Remove-Item -Recurse -Force $old.FullName -ErrorAction Stop
  } catch {
    Write-Host "Aviso: no se pudo eliminar staging previo: $($old.FullName)"
  }
}

Write-Host '[3/8] Exportando frontend web...'
Push-Location (Join-Path $root 'truevoice-web')
try {
  node .\node_modules\expo\bin\cli export --platform web
} finally {
  Pop-Location
}

Write-Host '[4/8] Copiando webdist al backend...'
$webDistSrc = Join-Path $root 'truevoice-web\dist'
$webDistDst = Join-Path $root 'truevoice-go\internal\server\webdist'
if (-not (Test-Path $webDistSrc)) {
  throw "No existe $webDistSrc"
}
if (Test-Path $webDistDst) { Remove-Item -Recurse -Force $webDistDst }
New-Item -ItemType Directory -Path $webDistDst | Out-Null
Copy-Item -Path (Join-Path $webDistSrc '*') -Destination $webDistDst -Recurse -Force

Write-Host '[5/8] Compilando truevoice.exe...'
Push-Location (Join-Path $root 'truevoice-go')
try {
  go build -o (Join-Path $staging 'truevoice.exe') .\cmd\truevoice
} finally {
  Pop-Location
}

Write-Host '[6/8] Copiando app, runtime y modelo...'
Copy-Item (Join-Path $root 'vibevoice_app.py') $staging -Force
Copy-Item (Join-Path $root 'inference_wrapper.py') $staging -Force
Copy-Item (Join-Path $root 'patches.py') $staging -Force
Copy-Item (Join-Path $root 'frontend_config.json') $staging -Force
Copy-Item (Join-Path $root 'requirements.txt') $staging -Force

if (Test-Path (Join-Path $root 'VibeVoice')) {
  Copy-Item (Join-Path $root 'VibeVoice') (Join-Path $staging 'VibeVoice') -Recurse -Force
}

Copy-Item $runtimeSource (Join-Path $staging 'runtime') -Recurse -Force

foreach ($d in @('api_outputs', 'temp_outputs', 'voices', 'race_sessions', 'contexts')) {
  New-Item -ItemType Directory -Path (Join-Path $staging $d) -Force | Out-Null
}

$startBat = @'
@echo off
setlocal
set "APP_ROOT=%~dp0"
set "TRUEVOICE_RUNTIME_DIR=%APP_ROOT%runtime"
set "HF_HOME=%TRUEVOICE_RUNTIME_DIR%\models\huggingface"
set "TRANSFORMERS_CACHE=%HF_HOME%\transformers"

start "TrueVoice" /D "%APP_ROOT%" "%APP_ROOT%truevoice.exe"
echo Esperando servidor en http://localhost:8000 ...
timeout /t 3 /nobreak >nul
start "" http://localhost:8000/app
endlocal
'@
Set-Content -Path (Join-Path $staging 'start_app.bat') -Value $startBat -Encoding ASCII

$stopBat = @'
@echo off
setlocal
for /f "tokens=2 delims=," %%P in ('tasklist /FI "IMAGENAME eq truevoice.exe" /FO CSV /NH') do (
  taskkill /PID %%~P /F >nul 2>nul
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$root=[System.IO.Path]::GetFullPath('%~dp0'); Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'python.exe' -and $_.ExecutablePath -like ($root + 'runtime\\python\\*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo TrueVoice detenido.
endlocal
'@
Set-Content -Path (Join-Path $staging 'stop_app.bat') -Value $stopBat -Encoding ASCII

Write-Host '[7/8] Creando ZIP portable...'
Push-Location $staging
try {
  tar -a -c -f $zipPath *
} finally {
  Pop-Location
}

Write-Host '[8/8] Verificando artefacto...'
$zipInfo = Get-Item -LiteralPath $zipPath
$sizeGb = [Math]::Round($zipInfo.Length / 1GB, 2)
Write-Host "ZIP generado: $zipPath ($sizeGb GB)"
