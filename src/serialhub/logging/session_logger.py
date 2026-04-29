from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from serialhub.core.models import SerialEvent, can_coalesce_serial_payload


class SessionLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self._file = None
        self._lock = threading.Lock()
        self._pending_event: SerialEvent | None = None

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
            self._flush_pending_locked()
            self._file.write(f"# Logging stopped at {datetime.now().isoformat(timespec='seconds')}\n")
            self._file.close()
            self._file = None
            self._pending_event = None

    def write(self, line: str) -> None:
        with self._lock:
            if not self._file:
                return
            self._write_locked(line)

    def log_event(self, event: SerialEvent) -> None:
        with self._lock:
            if not self._file:
                return

            if self._pending_event and can_coalesce_serial_payload(self._pending_event, event):
                self._pending_event.payload += event.payload
                if self._pending_event.payload.endswith((b"\n", b"\r")):
                    self._flush_pending_locked()
                return

            self._flush_pending_locked()

            if event.direction in {"RX", "TX"} and event.payload is not None:
                if event.payload.endswith((b"\n", b"\r")):
                    self._write_locked(self._format_event_line(event))
                    return
                self._pending_event = self._copy_event(event)
                return

            self._write_locked(self._format_event_line(event))

    def _write_locked(self, line: str) -> None:
        if not self._file:
            return
        self._file.write(line + "\n")
        self._file.flush()

    def _flush_pending_locked(self) -> None:
        if self._pending_event is None:
            return
        self._write_locked(self._format_event_line(self._pending_event))
        self._pending_event = None

    def _format_event_line(self, event: SerialEvent) -> str:
        if event.direction in {"RX", "TX"}:
            payload_text = (event.payload or b"").decode("utf-8", errors="replace").rstrip("\r\n")
            return (
                f"{event.timestamp.isoformat(timespec='milliseconds')}"
                f" {payload_text}"
                # f" | {event.device_id} | {event.direction} | HEX={payload_hex} | ASCII={payload_ascii}"
            )
        return (
            f"{event.timestamp.isoformat(timespec='milliseconds')}"
            # f" | {event.device_id} | {event.direction} | {event.text or ''}"
        )

    def _copy_event(self, event: SerialEvent) -> SerialEvent:
        return SerialEvent(
            device_id=event.device_id,
            port=event.port,
            direction=event.direction,
            payload=bytes(event.payload or b""),
            text=event.text,
            timestamp=event.timestamp,
        )
