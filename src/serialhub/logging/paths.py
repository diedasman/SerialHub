from __future__ import annotations

from datetime import datetime
from pathlib import Path

from serialhub.defaults import sanitize_log_filename


def build_log_filename(device_id: str, timestamp: datetime | None = None) -> str:
    stamp = (timestamp or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return sanitize_log_filename(f"{device_id}-{stamp}")


def resolve_log_destination(
    configured_path: str,
    *,
    device_id: str,
    fallback_dir: Path,
    timestamp: datetime | None = None,
) -> Path:
    raw_value = configured_path.strip()
    if raw_value:
        target = Path(raw_value).expanduser()
        if target.suffix.lower() == ".txt":
            return target
        if not target.exists():
            raise ValueError("The selected log folder does not exist.")
        if not target.is_dir():
            raise ValueError("Log destination must be a folder or a .txt file path.")
        return target / build_log_filename(device_id, timestamp=timestamp)

    fallback_dir.mkdir(parents=True, exist_ok=True)
    return fallback_dir / build_log_filename(device_id, timestamp=timestamp)
