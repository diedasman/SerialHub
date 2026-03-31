from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "SerialHub"
ENV_DATA_DIR = "SERIALHUB_DATA_DIR"


def get_data_dir() -> Path:
    custom = os.environ.get(ENV_DATA_DIR)
    if custom:
        path = Path(custom).expanduser().resolve()
    else:
        path = Path(user_data_dir(appname=APP_NAME, appauthor=False)).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_dir() -> Path:
    path = get_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_macros_path() -> Path:
    return get_data_dir() / "macros.json"
