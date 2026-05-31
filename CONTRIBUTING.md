# Contributing to SerialHub

Thanks for contributing.

## Development Setup

Use a local virtual environment for development and testing.

Windows PowerShell shortcut from the project root:

```powershell
. .\scripts\dev_setup.ps1
```

Manual setup:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

Linux manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

If you use VS Code, point it at the virtual-environment interpreter so imports resolve correctly.

## Running From Source

Terminal mode:

```powershell
python -m serialhub
```

Browser mode:

```powershell
python -m serialhub --web
```

To bind a different browser host or port:

```powershell
python -m serialhub --web --host 0.0.0.0 --port 8000
```

By default SerialHub stores local app data in a per-user application-data folder:

- Windows: `%LOCALAPPDATA%\SerialHub`
- Linux: `$XDG_DATA_HOME/SerialHub` or `~/.local/share/SerialHub`

Override the storage location with `SERIALHUB_DATA_DIR` if needed.
## Pull Request Guidelines

- Keep changes focused and small when possible.
- Add or update tests for behavior changes.
- Update `README.md` when UX or setup changes.
- Keep cross-platform support (Windows + Linux) in mind.

## Hardware Testing

If your change affects serial I/O behavior, include a short manual test note with:

- device used (for example `ESP32 CH340`)
- port and baud used
- commands sent
- expected vs observed output
