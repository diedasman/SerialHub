#!/usr/bin/env bash
set -euo pipefail

version="${1:-}"
if [[ -z "$version" ]]; then
    version="$(PYTHONPATH=src python -c 'from serialhub import __version__; print(__version__.split("+", 1)[0])')"
fi
version="${version#v}"
if [[ -z "$version" ]]; then
    echo "A release version is required." >&2
    exit 1
fi

python_version="${SERIALHUB_WINDOWS_PYTHON_VERSION:-3.12.10}"
py_root="build/winpy/python312"
site_packages="$py_root/Lib/site-packages"
exe_name="SerialHub-v${version}"
icon_args=()
if [[ -f "src/serialhub/assets/app.ico" ]]; then
    icon_args=(--icon 'Z:\src\src\serialhub\assets\app.ico')
fi

rm -rf "$py_root"
mkdir -p "$site_packages"

python - "$python_version" "$py_root" <<'PY'
from pathlib import Path
from sys import argv
from urllib.request import urlretrieve
from zipfile import ZipFile

python_version, root_arg = argv[1], argv[2]
root = Path(root_arg)
zip_path = root.parent / f"python-{python_version}-embed-amd64.zip"
url = f"https://www.python.org/ftp/python/{python_version}/python-{python_version}-embed-amd64.zip"
if not zip_path.exists():
    urlretrieve(url, zip_path)
with ZipFile(zip_path) as zf:
    zf.extractall(root)
pth = root / "python312._pth"
text = pth.read_text()
text = text.replace("#import site", "import site")
for line in ("Lib/site-packages", "../../../src"):
    if line not in text.splitlines():
        text = text.replace("import site", f"{line}\nimport site")
pth.write_text(text)
(root / "Lib" / "site-packages").mkdir(parents=True, exist_ok=True)
(root / "_wmi.pyd").unlink(missing_ok=True)
PY

python -m pip install --upgrade \
    --target "$site_packages" \
    --platform win_amd64 \
    --python-version 3.12 \
    --implementation cp \
    --abi cp312 \
    --only-binary=:all: \
    pyinstaller \
    pywin32-ctypes \
    pefile \
    textual \
    textual-serve \
    pyserial \
    platformdirs

docker run --rm \
    -v "$PWD:/src" \
    -w /src \
    debian:bookworm-slim \
    bash -lc "set -e; \
      apt-get update >/dev/null; \
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends wine >/dev/null; \
      WINEDEBUG=-all wine $py_root/python.exe -m PyInstaller \
        --noconfirm \
        --clean \
        --onefile \
        --console \
        --name '$exe_name' \
        --specpath build/pyinstaller \
        --workpath build/pyinstaller \
        --distpath dist \
        ${icon_args[*]} \
        --add-data 'Z:\src\src\serialhub\serialhub.tcss;serialhub' \
        --add-data 'Z:\src\src\serialhub\assets;serialhub/assets' \
        --collect-submodules textual.widgets \
        --hidden-import textual_serve.server \
        --collect-submodules serial \
        'Z:\src\src\serialhub\__main__.py'"

echo "Built dist/${exe_name}.exe"
