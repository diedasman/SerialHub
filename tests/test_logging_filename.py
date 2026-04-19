from datetime import datetime
from pathlib import Path

import pytest

from serialhub.defaults import sanitize_log_filename
from serialhub.logging.paths import build_log_filename, resolve_log_destination


def test_sanitize_log_filename() -> None:
    assert sanitize_log_filename("session") == "session.txt"
    assert sanitize_log_filename("session.txt") == "session.txt"
    assert sanitize_log_filename('bad<>:"/\\|?*name') == "bad_name.txt"
    assert sanitize_log_filename("   .  ") == "serialhub-log.txt"


def test_build_log_filename_uses_device_id_and_timestamp() -> None:
    stamp = datetime(2026, 4, 18, 12, 34, 56)
    assert build_log_filename("192.168.0.10:4059", timestamp=stamp) == "192.168.0.10_4059-20260418-123456.txt"


def test_resolve_log_destination_uses_existing_directory(tmp_path: Path) -> None:
    target_dir = tmp_path / "serial-logs"
    target_dir.mkdir()

    resolved = resolve_log_destination(
        str(target_dir),
        device_id="COM7",
        fallback_dir=tmp_path / "fallback",
        timestamp=datetime(2026, 4, 18, 8, 0, 0),
    )

    assert resolved == target_dir / "COM7-20260418-080000.txt"


def test_resolve_log_destination_preserves_explicit_txt_path(tmp_path: Path) -> None:
    target_path = tmp_path / "manual" / "capture.txt"

    resolved = resolve_log_destination(
        str(target_path),
        device_id="COM7",
        fallback_dir=tmp_path / "fallback",
    )

    assert resolved == target_path


def test_resolve_log_destination_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        resolve_log_destination(
            str(tmp_path / "missing-dir"),
            device_id="COM7",
            fallback_dir=tmp_path / "fallback",
        )
