from __future__ import annotations

from dataclasses import dataclass, field

from serialhub.core.models import ConnectionConfig, DeviceTransport, SerialEvent, can_coalesce_serial_payload
from serialhub.logging.session_logger import SessionLogger

WORKSPACE_DATASTREAM_WINDOW = 32
WORKSPACE_DATASTREAM_DECAY = 0.55
WORKSPACE_DATASTREAM_IDLE_FLOOR = 0.15


@dataclass(slots=True)
class WorkspaceDatastream:
    window_size: int = WORKSPACE_DATASTREAM_WINDOW
    rx_samples: list[float] = field(default_factory=list)
    tx_samples: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.rx_samples:
            self.rx_samples = [0.0] * self.window_size
        else:
            self.rx_samples = self.rx_samples[-self.window_size :]
        if not self.tx_samples:
            self.tx_samples = [0.0] * self.window_size
        else:
            self.tx_samples = self.tx_samples[-self.window_size :]

    def record_event(self, event: SerialEvent) -> bool:
        payload_size = float(len(event.payload or b""))
        if payload_size <= 0:
            return False

        if event.direction == "RX":
            self._append(self.rx_samples, payload_size)
            self._append(self.tx_samples, 0.0)
            return True

        if event.direction == "TX":
            self._append(self.rx_samples, 0.0)
            self._append(self.tx_samples, payload_size)
            return True

        return False

    def tick(self) -> None:
        self._append(self.rx_samples, self._decayed_tail(self.rx_samples))
        self._append(self.tx_samples, self._decayed_tail(self.tx_samples))

    def _append(self, samples: list[float], value: float) -> None:
        samples.append(value)
        overflow = len(samples) - self.window_size
        if overflow > 0:
            del samples[:overflow]

    def _decayed_tail(self, samples: list[float]) -> float:
        value = samples[-1] * WORKSPACE_DATASTREAM_DECAY if samples else 0.0
        return value if value >= WORKSPACE_DATASTREAM_IDLE_FLOOR else 0.0


@dataclass(slots=True)
class DeviceSession:
    device_id: str
    port: str
    transport: DeviceTransport
    config: ConnectionConfig
    raw_events: list[SerialEvent] = field(default_factory=list)
    parsed_lines: list[str] = field(default_factory=list)
    logger: SessionLogger | None = None
    timestamps_enabled: bool = True
    chevrons_enabled: bool = True
    label: str = ""
    workspace_datastream: WorkspaceDatastream = field(default_factory=WorkspaceDatastream)

    def add_raw_event(self, event: SerialEvent, limit: int = 1000) -> bool:
        if self._coalesce_raw_event(event):
            return True
        self.raw_events.append(event)
        if len(self.raw_events) > limit:
            self.raw_events = self.raw_events[-limit:]
        return False

    def add_parsed_line(self, line: str, limit: int = 1000) -> None:
        self.parsed_lines.append(line)
        if len(self.parsed_lines) > limit:
            self.parsed_lines = self.parsed_lines[-limit:]

    def _coalesce_raw_event(self, event: SerialEvent) -> bool:
        if not self.raw_events:
            return False

        previous = self.raw_events[-1]
        if not can_coalesce_serial_payload(previous, event):
            return False

        previous.payload += event.payload
        return True
