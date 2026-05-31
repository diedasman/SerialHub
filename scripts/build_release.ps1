param(
    [string]$Version = "",
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $python = $venvPython
    $pythonArgs = @()
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $python = "py"
    $pythonArgs = @("-3.12")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = "python"
    $pythonArgs = @()
} else {
    throw "Python 3.12 or newer is required to build SerialHub."
}

Push-Location $projectRoot
try {
    if ($InstallDependencies) {
        & $python @pythonArgs -m pip install --upgrade pip
        & $python @pythonArgs -m pip install -e . pyinstaller
    }

    if (!$Version) {
        $env:PYTHONPATH = (Join-Path $projectRoot "src")
        $Version = (& $python @pythonArgs -c "from serialhub import __version__; print(__version__.split('+', 1)[0])").Trim()
    }

    $cleanVersion = $Version.Trim()
    if ($cleanVersion.StartsWith("v")) {
        $cleanVersion = $cleanVersion.Substring(1)
    }
    if (!$cleanVersion) {
        throw "A release version is required."
    }

    $exeBaseName = "SerialHub-v$cleanVersion"
    $cssPath = Join-Path $projectRoot "src\serialhub\serialhub.tcss"
    $assetsPath = Join-Path $projectRoot "src\serialhub\assets"
    $iconPath = Join-Path $assetsPath "app.ico"
    $pyInstallerArgs = @(
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name", $exeBaseName,
        "--specpath", "build\pyinstaller",
        "--workpath", "build\pyinstaller",
        "--distpath", "dist",
        "--add-data", "${cssPath};serialhub",
        "--add-data", "${assetsPath};serialhub\assets",
        "--collect-submodules", "textual.widgets",
        "--hidden-import", "textual_serve.server",
        "--collect-submodules", "serial"
    )
    if (Test-Path $iconPath) {
        $pyInstallerArgs += @("--icon", $iconPath)
    }
    $pyInstallerArgs += "src\serialhub\__main__.py"

    & $python @pythonArgs -m PyInstaller @pyInstallerArgs
    Write-Host "Built dist\$exeBaseName.exe"
} finally {
    Pop-Location
}
