$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPath = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
$wasDotSourced = $MyInvocation.InvocationName -eq "."

if (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
    $pythonArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
    $pythonArgs = @()
} else {
    throw "Python 3.12 or newer is required to set up the SerialHub development environment."
}

if (!(Test-Path $venvPython)) {
    & $python @pythonArgs -m venv $venvPath
}

Push-Location $projectRoot
try {
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -e ".[dev]"
} finally {
    Pop-Location
}

if ($wasDotSourced) {
    . $activateScript
    Write-Host "SerialHub dev environment is active in this shell."
    Write-Host "Python: $((Get-Command python).Source)"
    Write-Host "Run with: serialhub"
} else {
    Write-Host "SerialHub dev environment is ready."
    Write-Host "Activate it with: .\.venv\Scripts\Activate.ps1"
    Write-Host "Or dot-source this script next time with: . .\scripts\dev_setup.ps1"
}
