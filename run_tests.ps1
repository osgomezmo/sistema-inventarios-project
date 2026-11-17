# Ejecutor de pruebas unitarias para todos los microservicios desde la carpeta raiz (PowerShell)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python test_microservicios.py @args
exit $LASTEXITCODE
