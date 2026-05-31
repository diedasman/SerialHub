# Contributing to SerialHub

Thanks for contributing.

## Development Setup

1. Create and activate a virtual environment.
2. Install in editable mode with dev dependencies:

```bash
python -m pip install -e .[dev]
```

3. Run checks before opening a PR:

```bash
ruff check src tests
python -m compileall src tests
python -m pytest
```

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
