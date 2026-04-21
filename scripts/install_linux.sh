#!/usr/bin/env bash
set -euo pipefail

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python 3.12 or newer is required to install SerialHub." >&2
  exit 1
fi

"$PYTHON_BIN" -m pip install --user pipx
"$PYTHON_BIN" -m pipx ensurepath
"$PYTHON_BIN" -m pipx install --force .

echo "SerialHub installed with pipx. Restart the terminal if needed, then run: serialhub"
