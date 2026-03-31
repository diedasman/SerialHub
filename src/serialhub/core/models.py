from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

import serial

Direction = Literal["RX", "TX", "INFO", "ERROR", "SCRIPT"]

PARITY_MAP = {
    "N": serial.PARITY_NONE,
    "E": serial.PARITY_EVEN,
    "O": serial.PARITY_ODD,
    "M": serial.PARITY_MARK,
    "S": serial.PARITY_SPACE,
}

STOP_BITS_MAP = {
    "1": serial.STOPBITS_ONE,
    "1.5": serial.STOPBITS_ONE_POINT_FIVE,
    "2": serial.STOPBITS_TWO,
}


@dataclass(slots=True)
class SerialConfig:
    baudrate: int = 9600
    parity: str = "N"
    stopbits: str = "1"
    databits: int = 8
    timeout: float = 0.2

    def validate(self) -> None:
        if self.parity not in PARITY_MAP:
            raise ValueError(f"Unsupported parity '{self.parity}'.")
        if self.stopbits not in STOP_BITS_MAP:
            raise ValueError(f"Unsupported stop bits '{self.stopbits}'.")
        if self.databits not in (5, 6, 7, 8):
            raise ValueError("Databits must be one of 5, 6, 7, 8.")
        if self.baudrate <= 0:
            raise ValueError("Baudrate must be > 0.")


@dataclass(slots=True)
class DeviceInfo:
    port: str
    description: str
    hwid: str = ""

    @property
    def label(self) -> str:
        if self.description and self.description != "n/a":
            return f"{self.port} - {self.description}"
        return self.port


@dataclass(slots=True)
class SerialEvent:
    device_id: str
    port: str
    direction: Direction
    payload: bytes | None = None
    text: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def payload_hex(self) -> str:
        if not self.payload:
            return ""
        return self.payload.hex(" ").upper()

    def payload_ascii(self) -> str:
        if not self.payload:
            return ""
        return "".join(chr(b) if 32 <= b < 127 else "." for b in self.payload)


@dataclass(slots=True)
class MacroDefinition:
    name: str
    payload: str
    hex_mode: bool = False
    delay_ms: int = 0

    def to_dict(self) -> dict[str, str | bool | int]:
        return {
            "name": self.name,
            "payload": self.payload,
            "hex_mode": self.hex_mode,
            "delay_ms": self.delay_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> MacroDefinition:
        name = str(data.get("name", "")).strip()
        payload = str(data.get("payload", ""))
        hex_mode = bool(data.get("hex_mode", False))
        delay_ms = int(data.get("delay_ms", 0) or 0)
        return cls(name=name, payload=payload, hex_mode=hex_mode, delay_ms=delay_ms)
