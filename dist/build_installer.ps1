Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$distDir = Join-Path $root 'dist'
$staging = Join-Path $distDir 'staging'
$tmp = Join-Path $distDir 'tmp'
$installerPath = Join-Path $distDir 'TrueVoiceInstaller.exe'
$vibeZip = Join-Path $staging 'VibeVoice.zip'

Write-Host '[1/8] Preparando carpetas temporales...'
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
if (Test-Path $installerPath) { Remove-Item -Force $installerPath }
New-Item -ItemType Directory -Path $staging | Out-Null
New-Item -ItemType Directory -Path $tmp | Out-Null

Write-Host '[2/8] Exportando frontend web...'
Push-Location (Join-Path $root 'truevoice-web')
try {
  node .\\node_modules\\expo\\bin\\cli export --platform web
} finally {
  Pop-Location
}

Write-Host '[3/8] Copiando webdist al backend...'
$webDistSrc = Join-Path $root 'truevoice-web\\dist'
$webDistDst = Join-Path $root 'truevoice-go\\internal\\server\\webdist'
if (-not (Test-Path $webDistSrc)) {
  throw "No existe $webDistSrc"
}
if (Test-Path $webDistDst) { Remove-Item -Recurse -Force $webDistDst }
New-Item -ItemType Directory -Path $webDistDst | Out-Null
Copy-Item -Path (Join-Path $webDistSrc '*') -Destination $webDistDst -Recurse -Force

Write-Host '[4/8] Compilando ejecutable de TrueVoice...'
Push-Location (Join-Path $root 'truevoice-go')
try {
  go build -o (Join-Path $staging 'truevoice.exe') .\\cmd\\truevoice
} finally {
  Pop-Location
}

Write-Host '[5/8] Empaquetando recursos Python...'
Copy-Item (Join-Path $root 'vibevoice_app.py') $staging -Force
Copy-Item (Join-Path $root 'inference_wrapper.py') $staging -Force
Copy-Item (Join-Path $root 'patches.py') $staging -Force
Copy-Item (Join-Path $root 'frontend_config.json') $staging -Force
Copy-Item (Join-Path $root 'requirements.txt') $staging -Force

Compress-Archive -Path (Join-Path $root 'VibeVoice\\*') -DestinationPath $vibeZip -Force

$installPs1 = @'
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-InstallLog {
  param([string]$Message)
  $line = "[$([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss'))] $Message"
  Write-Host $line
  if ($script:InstallLogPath) {
    Add-Content -Path $script:InstallLogPath -Value $line -Encoding ASCII
  }
}

function Select-InstallDirectory {
  if ($env:TRUEVOICE_INSTALL_DIR -and $env:TRUEVOICE_INSTALL_DIR.Trim()) {
    return $env:TRUEVOICE_INSTALL_DIR.Trim()
  }

  $defaultDir = Join-Path $env:LOCALAPPDATA "Programs\TrueVoice"
  try {
    Add-Type -AssemblyName System.Windows.Forms | Out-Null
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "Selecciona la carpeta donde instalar TrueVoice"
    $dialog.ShowNewFolderButton = $true
    if (Test-Path $defaultDir) {
      $dialog.SelectedPath = $defaultDir
    }

    $result = $dialog.ShowDialog()
    if ($result -eq [System.Windows.Forms.DialogResult]::OK -and $dialog.SelectedPath) {
      return $dialog.SelectedPath
    }

    throw "Instalacion cancelada por el usuario."
  } catch {
    Write-Host "No se pudo abrir selector grafico. Se usara consola."
    $typed = Read-Host "Carpeta de instalacion (Enter para '$defaultDir')"
    if (-not $typed) {
      return $defaultDir
    }
    return $typed
  }
}

$installDir = Select-InstallDirectory
if (-not (Test-Path $installDir)) {
  New-Item -ItemType Directory -Path $installDir -Force | Out-Null
}

$script:InstallLogPath = Join-Path $installDir "install.log"
Write-InstallLog "Instalando archivos en $installDir"

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

$idx = 0
foreach ($f in $filesToCopy) {
  $idx++
  $pct = [Math]::Floor((($idx / $filesToCopy.Count) * 25))
  Write-Progress -Id 1 -Activity "Instalando TrueVoice" -Status "Copiando archivos ($idx/$($filesToCopy.Count))..." -PercentComplete $pct
  Copy-Item -Path (Join-Path $PSScriptRoot $f) -Destination (Join-Path $installDir $f) -Force
}

$vibeZip = Join-Path $PSScriptRoot "VibeVoice.zip"
$vibeDst = Join-Path $installDir "VibeVoice"
if (Test-Path $vibeDst) {
  Remove-Item -Recurse -Force $vibeDst
}
Write-Progress -Id 1 -Activity "Instalando TrueVoice" -Status "Extrayendo VibeVoice..." -PercentComplete 30
Expand-Archive -Path $vibeZip -DestinationPath $vibeDst -Force

foreach ($d in @("api_outputs", "temp_outputs", "voices", "race_sessions", "contexts")) {
  New-Item -ItemType Directory -Path (Join-Path $installDir $d) -Force | Out-Null
}
Write-InstallLog "Archivos base instalados"

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "TrueVoice.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $installDir "debug_launcher.cmd"
$shortcut.WorkingDirectory = $installDir
$shortcut.IconLocation = Join-Path $installDir "truevoice.exe"
$shortcut.Save()
Write-InstallLog "Acceso directo creado en escritorio"

Write-InstallLog "Inicializando runtime (descarga VibeVoice y modelo 1.5B). Puede tardar varios minutos"
function Get-StageProgress {
  param([string]$Stage)

  switch ($Stage) {
    "idle" { return @{ Percent = 5; Status = "Preparando instalador..." } }
    "checking" { return @{ Percent = 12; Status = "Comprobando runtime Python..." } }
    "downloading_python" { return @{ Percent = 25; Status = "Descargando runtime Python embebido..." } }
    "installing_dependencies" { return @{ Percent = 55; Status = "Descargando e instalando VibeVoice y dependencias..." } }
    "downloading_model" { return @{ Percent = 75; Status = "Descargando modelo de generacion de voz VibeVoice 1.5B..." } }
    "ready" { return @{ Percent = 95; Status = "Finalizando instalacion..." } }
    "failed" { return @{ Percent = 100; Status = "Error durante la instalacion" } }
    default { return @{ Percent = 18; Status = "Instalando..." } }
  }
}

$proc = Start-Process -FilePath (Join-Path $installDir "truevoice.exe") -WorkingDirectory $installDir -PassThru
$bootstrapStarted = $false
$ready = $false
Write-InstallLog "Servidor de bootstrap iniciado (PID=$($proc.Id))"

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
    Write-InstallLog "Bootstrap stage=$stage ready=$($statusObj.ready)"

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
  Write-InstallLog "ERROR: Timeout esperando bootstrap del runtime/modelo"
  throw "Timeout esperando bootstrap del runtime/modelo."
}

try { Stop-Process -Id $proc.Id -Force } catch {}
Write-Progress -Id 1 -Activity "Instalando TrueVoice" -Status "Instalacion completada" -PercentComplete 100
Write-InstallLog "Instalacion completada correctamente"
Write-Host "Instalacion completada correctamente."
'@
Set-Content -Path (Join-Path $staging 'install.ps1') -Value $installPs1 -Encoding ASCII

$launcherPs1 = @'
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$appRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ((Split-Path -Leaf $appRoot) -eq "dist") {
  $appRoot = Split-Path -Parent $appRoot
}

$goExe = Join-Path $appRoot "truevoice-go\\cmd\\truevoice"
$installedExe = Join-Path $appRoot "truevoice.exe"

if (Test-Path $installedExe) {
  Write-Host "Lanzando instalacion de TrueVoice..."
  & $installedExe
  exit $LASTEXITCODE
}

Write-Host "Exportando frontend para pruebas..."
Push-Location (Join-Path $appRoot "truevoice-web")
try {
  node .\\node_modules\\expo\\bin\\cli export --platform web
} finally {
  Pop-Location
}

$webDistSrc = Join-Path $appRoot "truevoice-web\\dist"
$webDistDst = Join-Path $appRoot "truevoice-go\\internal\\server\\webdist"
if (Test-Path $webDistDst) { Remove-Item -Recurse -Force $webDistDst }
New-Item -ItemType Directory -Path $webDistDst | Out-Null
Copy-Item -Path (Join-Path $webDistSrc '*') -Destination $webDistDst -Recurse -Force

Write-Host "Iniciando backend Go en modo debug..."
Push-Location (Join-Path $appRoot "truevoice-go")
try {
  go run .\\cmd\\truevoice
} finally {
  Pop-Location
}
'@
Set-Content -Path (Join-Path $staging 'debug_launcher.ps1') -Value $launcherPs1 -Encoding ASCII

$launcherCmd = @'
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0debug_launcher.ps1"
endlocal
'@
Set-Content -Path (Join-Path $staging 'debug_launcher.cmd') -Value $launcherCmd -Encoding ASCII

$installCmd = @'
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Sta -File "%~dp0install.ps1"
endlocal
'@
Set-Content -Path (Join-Path $staging 'install.cmd') -Value $installCmd -Encoding ASCII

Write-Host '[6/8] Generando definicion SED para IExpress...'
$sedPath = Join-Path $tmp 'truevoice_installer.sed'
$targetPath = $installerPath
$srcPath = $staging

$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3

[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
HideExtractAnimation=0
UseLongFileName=1
InsideCompressed=1
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=Instalacion finalizada.
TargetName=$targetPath
FriendlyName=TrueVoice Installer
AppLaunched=cmd /c install.cmd
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles

[Strings]
FILE0=truevoice.exe
FILE1=vibevoice_app.py
FILE2=inference_wrapper.py
FILE3=patches.py
FILE4=frontend_config.json
FILE5=requirements.txt
FILE6=VibeVoice.zip
FILE7=install.ps1
FILE8=install.cmd
FILE9=debug_launcher.cmd
FILE10=debug_launcher.ps1

[SourceFiles]
SourceFiles0=$srcPath

[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
%FILE3%=
%FILE4%=
%FILE5%=
%FILE6%=
%FILE7%=
%FILE8%=
%FILE9%=
%FILE10%=
"@
Set-Content -Path $sedPath -Value $sed -Encoding ASCII

Write-Host '[7/8] Compilando instalador con IExpress...'
$iexpress = Join-Path $env:WINDIR 'System32\\iexpress.exe'
if (-not (Test-Path $iexpress)) {
  throw 'No se encontro iexpress.exe en el sistema.'
}
& $iexpress /N /Q $sedPath
$iexpressExit = $LASTEXITCODE

for ($i = 0; $i -lt 60 -and -not (Test-Path $installerPath); $i++) {
  Start-Sleep -Seconds 1
}

$installerInfo = Get-Item -LiteralPath $installerPath -ErrorAction SilentlyContinue
$rcxTmp = Get-ChildItem -Path $distDir -Filter 'RCX*.tmp' -File -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if ($rcxTmp -and ((-not $installerInfo) -or $installerInfo.Length -lt 1000000)) {
  if (Test-Path $installerPath) {
    Remove-Item -Force $installerPath
  }
  Move-Item -LiteralPath $rcxTmp.FullName -Destination $installerPath -Force
}

if (-not (Test-Path $installerPath)) {
  throw "No se genero $installerPath (ExitCode IExpress=$iexpressExit)"
}

Write-Host '[8/8] Copiando debug_launcher al directorio dist...'
Copy-Item (Join-Path $staging 'debug_launcher.ps1') (Join-Path $distDir 'debug_launcher.ps1') -Force
Copy-Item (Join-Path $staging 'debug_launcher.cmd') (Join-Path $distDir 'debug_launcher.cmd') -Force

Write-Host "Instalador generado: $installerPath"
