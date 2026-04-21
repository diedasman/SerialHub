$ErrorActionPreference = "Stop"

if (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
    $pythonArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
    $pythonArgs = @()
} else {
    throw "Python 3.12 or newer is required to install SerialHub."
}

& $python @pythonArgs -m pip install --user pipx
& $python @pythonArgs -m pipx ensurepath
& $python @pythonArgs -m pipx install --force .

Write-Host "SerialHub installed with pipx. Restart the terminal if needed, then run: serialhub"
