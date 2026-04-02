# generate_drives.ps1
# Detecta los discos disponibles en este PC y genera docker-compose.override.yml
# con los volumenes necesarios para que el explorador de carpetas funcione en Docker.
# Docker Compose carga este archivo automaticamente junto con docker-compose.yml.

$drives = Get-PSDrive -PSProvider FileSystem |
    Where-Object { $_.Root -match '^[A-Z]:\\$' -and (Test-Path $_.Root) } |
    Sort-Object Root

if (-not $drives) {
    Write-Host "[WARN] No se detectaron discos. Usando C: por defecto."
    $drives = @([PSCustomObject]@{ Root = 'C:\' })
}

$volumeLines = @()
foreach ($drive in $drives) {
    $letter = $drive.Root[0].ToString().ToLower()
    $volumeLines += "      - ${letter}:/:/mnt/${letter}"
}
$volumesBlock = $volumeLines -join "`n"

$yaml = @"
# AUTO-GENERADO por generate_drives.ps1 — NO editar manualmente.
# Se regenera automaticamente al ejecutar deploy.bat o generate_drives.ps1.
services:
  api:
    volumes:
$volumesBlock
  frontend:
    volumes:
$volumesBlock
"@

$outFile = Join-Path $PSScriptRoot "docker-compose.override.yml"
$yaml | Set-Content -Path $outFile -Encoding UTF8

$driveList = ($drives | ForEach-Object { $_.Root.TrimEnd('\') }) -join ", "
Write-Host "[OK] Discos detectados: $driveList"
Write-Host "[OK] Generado: $outFile"
