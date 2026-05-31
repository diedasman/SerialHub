from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

import serial

Direction = Literal["RX", "TX", "INFO", "ERROR"]
DeviceTransport = Literal["serial", "tcp"]

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


def normalize_tcp_host(host: str) -> str:
    value = host.strip()
    if not value:
        raise ValueError("IP address is required.")
    try:
        return str(ipaddress.ip_address(value))
    except ValueError as exc:
        raise ValueError(f"Invalid IP address '{host}'.") from exc


def build_tcp_device_id(host: str, port: int) -> str:
    normalized_host = normalize_tcp_host(host)
    if ":" in normalized_host:
        return f"[{normalized_host}]:{port}"
    return f"{normalized_host}:{port}"


class DeviceConnection(Protocol):
    @property
    def is_open(self) -> bool: ...

    def open(self) -> None: ...

    def close(self) -> None: ...

    def send(self, data: bytes) -> int: ...


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
class TcpConfig:
    host: str
    port: int
    timeout: float = 10.0
    read_size: int = 4096

    @property
    def device_id(self) -> str:
        return build_tcp_device_id(self.host, self.port)

    def validate(self) -> None:
        self.host = normalize_tcp_host(self.host)
        if self.port <= 0 or self.port > 65535:
            raise ValueError("TCP port must be between 1 and 65535.")
        if self.timeout <= 0:
            raise ValueError("TCP timeout must be > 0.")
        if self.read_size <= 0:
            raise ValueError("TCP read size must be > 0.")


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


def can_coalesce_serial_payload(previous: SerialEvent, current: SerialEvent) -> bool:
    return (
        previous.direction in {"RX", "TX"}
        and current.direction == previous.direction
        and previous.payload is not None
        and current.payload is not None
        and not previous.payload.endswith((b"\n", b"\r"))
    )


@dataclass(slots=True)
class MacroCommandDefinition:
    label: str
    command: str
    delay_ms: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "command": self.command,
            "delay_ms": self.delay_ms,
        }

    @classmethod
    def from_value(
        cls,
        value: object,
        *,
        index: int,
        default_delay_ms: int = 0,
    ) -> MacroCommandDefinition | None:
        if isinstance(value, dict):
            command = str(value.get("command", value.get("value", value.get("payload", ""))))
            if not command:
                return None
            label = str(value.get("label", f"Command {index}")).strip() or f"Command {index}"
            raw_delay = value.get("delay_ms", value.get("delay", default_delay_ms))
            try:
                delay_ms = int(float(raw_delay or 0))
            except (TypeError, ValueError):
                delay_ms = default_delay_ms
            return cls(label=label, command=command, delay_ms=max(0, delay_ms))

        command = str(value)
        if not command:
            return None
        return cls(label=f"Command {index}", command=command, delay_ms=max(0, default_delay_ms))


@dataclass(slots=True, init=False)
class MacroDefinition:
    name: str
    commands: list[MacroCommandDefinition]
    label: str = ""
    cmd_delay: float = 0.0
    path: Path | None = None
    _hex_mode: bool = False

    def __init__(
        self,
        name: str,
        commands: list[str | dict[str, object] | MacroCommandDefinition] | None = None,
        label: str = "",
        cmd_delay: float = 0.0,
        path: Path | None = None,
        *,
        payload: str | None = None,
        hex_mode: bool = False,
        delay_ms: int | None = None,
    ) -> None:
        self.name = name
        default_delay_ms = int(delay_ms) if delay_ms is not None else int(float(cmd_delay or 0) * 1000)
        raw_commands: list[object] = list(commands or ([payload] if payload else []))
        self.commands = []
        for index, command in enumerate(raw_commands, start=1):
            if isinstance(command, MacroCommandDefinition):
                self.commands.append(command)
                continue
            parsed_command = MacroCommandDefinition.from_value(
                command,
                index=index,
                default_delay_ms=default_delay_ms,
            )
            if parsed_command is not None:
                self.commands.append(parsed_command)
        self.label = label
        self.cmd_delay = float(delay_ms) / 1000 if delay_ms is not None else float(cmd_delay)
        self.path = path
        self._hex_mode = bool(hex_mode)
        if not self.label:
            self.label = self.name

    @property
    def payload(self) -> str:
        return self.commands[0].command if self.commands else ""

    @property
    def hex_mode(self) -> bool:
        return self._hex_mode

    @property
    def delay_ms(self) -> int:
        return int(self.cmd_delay * 1000)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "label": self.label,
            "commands": [command.to_dict() for command in self.commands],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> MacroDefinition:
        name = str(data.get("name", "")).strip()
        label = str(data.get("label", name)).strip() or name
        raw_commands = data.get("commands")
        commands: list[MacroCommandDefinition] = []
        raw_delay = data.get("cmd_delay", data.get("delay_ms", 0))
        try:
            cmd_delay = float(raw_delay or 0)
        except (TypeError, ValueError):
            cmd_delay = 0.0
        if "delay_ms" in data and "cmd_delay" not in data:
            cmd_delay = cmd_delay / 1000
        default_delay_ms = int(cmd_delay * 1000)
        if isinstance(raw_commands, list):
            for index, item in enumerate(raw_commands, start=1):
                command = MacroCommandDefinition.from_value(
                    item,
                    index=index,
                    default_delay_ms=default_delay_ms,
                )
                if command is not None:
                    commands.append(command)
        elif data.get("payload") is not None:
            # Backwards compatibility for the previous single-command macro format.
            payload = str(data.get("payload", ""))
            if payload:
                commands = [
                    MacroCommandDefinition(
                        label=label or name,
                        command=payload,
                        delay_ms=default_delay_ms,
                    )
                ]

        return cls(
            name=name,
            label=label,
            commands=commands,
            cmd_delay=max(0.0, cmd_delay),
            hex_mode=bool(data.get("hex_mode", False)),
        )


ConnectionConfig = SerialConfig | TcpConfig
