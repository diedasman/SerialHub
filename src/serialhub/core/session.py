from __future__ import annotations

from dataclasses import dataclass, field

from serialhub.core.models import SerialConfig, SerialEvent
from serialhub.logging.session_logger import SessionLogger


@dataclass(slots=True)
class DeviceSession:
    device_id: str
    port: str
    config: SerialConfig
    raw_events: list[SerialEvent] = field(default_factory=list)
    parsed_lines: list[str] = field(default_factory=list)
    dlms_lines: list[str] = field(default_factory=list)
    logger: SessionLogger | None = None
    timestamps_enabled: bool = True

    def add_raw_event(self, event: SerialEvent, limit: int = 1000) -> None:
        self.raw_events.append(event)
        if len(self.raw_events) > limit:
            self.raw_events = self.raw_events[-limit:]

    def add_parsed_line(self, line: str, limit: int = 1000) -> None:
        self.parsed_lines.append(line)
        if len(self.parsed_lines) > limit:
            self.parsed_lines = self.parsed_lines[-limit:]

    def add_dlms_line(self, line: str, limit: int = 1000) -> None:
        self.dlms_lines.append(line)
        if len(self.dlms_lines) > limit:
            self.dlms_lines = self.dlms_lines[-limit:]
