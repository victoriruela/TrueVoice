Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$installDir = Join-Path $env:ProgramFiles "TrueVoice"
if (-not (Test-Path $installDir)) {
  New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

Write-Host "Instalando archivos en $installDir ..."
$filesToCopy = @(
  "truevoice.exe",
  "vibevoice_app.py",
  "inference_wrapper.py",
  "patches.py",
  "frontend_config.json",
  "requirements.txt",
  "debug_launcher.cmd",
  "debug_launcher.ps1"
)

foreach ($f in $filesToCopy) {
  Copy-Item -Path (Join-Path $PSScriptRoot $f) -Destination (Join-Path $installDir $f) -Force
}

$vibeZip = Join-Path $PSScriptRoot "VibeVoice.zip"
$vibeDst = Join-Path $installDir "VibeVoice"
if (Test-Path $vibeDst) {
  Remove-Item -Recurse -Force $vibeDst
}
Expand-Archive -Path $vibeZip -DestinationPath $vibeDst -Force

foreach ($d in @("api_outputs", "temp_outputs", "voices", "race_sessions", "contexts")) {
  New-Item -ItemType Directory -Path (Join-Path $installDir $d) -Force | Out-Null
}

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "TrueVoice.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $installDir "debug_launcher.cmd"
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = Join-Path $installDir "truevoice.exe"
$shortcut.Save()

Write-Host "Inicializando runtime (descarga VibeVoice y modelo 1.5B). Puede tardar varios minutos..."
function Get-StageProgress {
  param([string]$Stage)

  switch ($Stage) {
    "idle" { return @{ Percent = 5; Status = "Preparando instalador..." } }
    "checking" { return @{ Percent = 12; Status = "Comprobando runtime Python..." } }
    "downloading_python" { return @{ Percent = 25; Status = "Descargando runtime Python embebido..." } }
    "installing_dependencies" { return @{ Percent = 45; Status = "Descargando e instalando VibeVoice y dependencias..." } }
    "downloading_model" { return @{ Percent = 75; Status = "Descargando modelo de generacion de voz VibeVoice 1.5B..." } }
    "ready" { return @{ Percent = 100; Status = "Instalacion completada" } }
    "failed" { return @{ Percent = 100; Status = "Error durante la instalacion" } }
    default { return @{ Percent = 18; Status = "Instalando..." } }
  }
}

$proc = Start-Process -FilePath (Join-Path $installDir "truevoice.exe") -WorkingDirectory $installDir -PassThru
$bootstrapStarted = $false
$ready = $false

for ($i = 0; $i -lt 720; $i++) {
  Start-Sleep -Seconds 5
  if ($proc.HasExited) {
    throw "truevoice.exe termino antes de completar bootstrap."
  }

  try {
    if (-not $bootstrapStarted) {
      Invoke-WebRequest -Uri "http://localhost:8000/setup/bootstrap" -Method POST -UseBasicParsing -TimeoutSec 10 | Out-Null
      $bootstrapStarted = $true
    }

    $statusResp = Invoke-WebRequest -Uri "http://localhost:8000/setup/status" -UseBasicParsing -TimeoutSec 10
    $statusObj = $statusResp.Content | ConvertFrom-Json
    $stage = [string]$statusObj.stage
    $progress = Get-StageProgress -Stage $stage

    $statusText = [string]$progress.Status
    if ($statusObj.error) {
      $statusText = "Error: $($statusObj.error)"
    }

    Write-Progress -Id 1 -Activity "Instalando TrueVoice" -Status $statusText -PercentComplete $progress.Percent

    if ($statusObj.ready -eq $true -and $stage -eq "ready") {
      $ready = $true
      break
    }

    if ($stage -eq "failed") {
      throw "Bootstrap fallo: $($statusObj.error)"
    }
  } catch {
    # El servidor puede no estar listo aun; se sigue intentando hasta timeout.
    Write-Progress -Id 1 -Activity "Instalando TrueVoice" -Status "Iniciando servicio de instalacion..." -PercentComplete 8
  }
}

Write-Progress -Id 1 -Activity "Instalando TrueVoice" -Completed

if (-not $ready) {
  try { Stop-Process -Id $proc.Id -Force } catch {}
  throw "Timeout esperando bootstrap del runtime/modelo."
}

try { Stop-Process -Id $proc.Id -Force } catch {}
Write-Host "Instalacion completada correctamente."
