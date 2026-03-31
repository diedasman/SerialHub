from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from serialhub.core.models import SerialEvent


class SessionLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self._file = None
        self._lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        return self._file is not None

    def start(self) -> None:
        with self._lock:
            if self._file:
                return
            self._file = self.log_path.open("a", encoding="utf-8")
            self._file.write(f"# Logging started at {datetime.now().isoformat(timespec='seconds')}\n")
            self._file.flush()

    def stop(self) -> None:
        with self._lock:
            if not self._file:
                return
            self._file.write(f"# Logging stopped at {datetime.now().isoformat(timespec='seconds')}\n")
            self._file.close()
            self._file = None

    def write(self, line: str) -> None:
        with self._lock:
            if not self._file:
                return
            self._file.write(line + "\n")
            self._file.flush()

    def log_event(self, event: SerialEvent) -> None:
        if event.direction in {"RX", "TX"}:
            payload_hex = event.payload_hex()
            payload_ascii = event.payload_ascii()
            line = (
                f"{event.timestamp.isoformat(timespec='milliseconds')}"
                f" | {event.device_id} | {event.direction} | HEX={payload_hex} | ASCII={payload_ascii}"
            )
        else:
            line = (
                f"{event.timestamp.isoformat(timespec='milliseconds')}"
                f" | {event.device_id} | {event.direction} | {event.text or ''}"
            )
        self.write(line)
