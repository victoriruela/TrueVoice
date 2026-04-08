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
