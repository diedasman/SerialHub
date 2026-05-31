#!/usr/bin/env bash
set -euo pipefail

APP_NAME="SerialHub"
PACKAGE_NAME="serialhub"
REPO_URL="https://github.com/diedasman/SerialHub"
REF="${SERIALHUB_REF:-main}"
INSTALL_DIR="${SERIALHUB_INSTALL_DIR:-${HOME}/.local/share/serialhub}"
BIN_DIR="${SERIALHUB_BIN_DIR:-${HOME}/.local/bin}"
VENV_DIR="${INSTALL_DIR}/venv"
LAUNCHER="${BIN_DIR}/serialhub"

info() {
  printf '%s\n' "$*"
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

find_python() {
  if command -v python3.12 >/dev/null 2>&1; then
    command -v python3.12
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi

  fail "Python 3.12 or newer is required, but no python3 command was found."
}

PYTHON_BIN="$(find_python)"

"${PYTHON_BIN}" - <<'PY' || fail "Python 3.12 or newer is required."
import sys

raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY

info "Installing ${APP_NAME} with ${PYTHON_BIN}..."
mkdir -p "${INSTALL_DIR}" "${BIN_DIR}"

"${PYTHON_BIN}" -m venv "${VENV_DIR}" || fail "Could not create a virtual environment. On Debian or Ubuntu, install python3.12-venv and try again."
"${VENV_DIR}/bin/python" -m pip install --upgrade pip

if [ -f "pyproject.toml" ] && [ -d "src/serialhub" ]; then
  info "Installing from local checkout: $(pwd)"
  "${VENV_DIR}/bin/python" -m pip install --upgrade .
else
  SOURCE_URL="${REPO_URL}/archive/refs/heads/${REF}.tar.gz"
  if [[ "${REF}" == v* ]]; then
    SOURCE_URL="${REPO_URL}/archive/refs/tags/${REF}.tar.gz"
  fi

  info "Installing from ${SOURCE_URL}"
  "${VENV_DIR}/bin/python" -m pip install --upgrade "${SOURCE_URL}"
fi

cat >"${LAUNCHER}" <<EOF
#!/usr/bin/env sh
exec "${VENV_DIR}/bin/${PACKAGE_NAME}" "\$@"
EOF
chmod 755 "${LAUNCHER}"

info ""
info "${APP_NAME} installed successfully."
info "Run it with: serialhub"

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *)
    info ""
    info "Add ${BIN_DIR} to your PATH if your shell cannot find serialhub:"
    info "  export PATH=\"${BIN_DIR}:\$PATH\""
    ;;
esac
