from __future__ import annotations

import threading
from collections.abc import Callable

from serial.tools import list_ports

from serialhub.core.models import DeviceInfo, SerialConfig, SerialEvent
from serialhub.core.serial_connection import SerialConnection


class DeviceManager:
    def __init__(self) -> None:
        self._connections: dict[str, SerialConnection] = {}
        self._lock = threading.Lock()

    def scan_devices(self) -> list[DeviceInfo]:
        devices = [
            DeviceInfo(port=port.device, description=port.description or "", hwid=port.hwid or "")
            for port in list_ports.comports()
        ]
        devices.sort(key=lambda d: d.port)
        return devices

    def connect(
        self,
        port: str,
        config: SerialConfig,
        event_callback: Callable[[SerialEvent], None],
    ) -> SerialConnection:
        with self._lock:
            if port in self._connections and self._connections[port].is_open:
                return self._connections[port]
            conn = SerialConnection(device_id=port, port=port, config=config, event_callback=event_callback)
            self._connections[port] = conn

        conn.open()
        return conn

    def disconnect(self, device_id: str) -> None:
        with self._lock:
            conn = self._connections.get(device_id)
        if not conn:
            return
        conn.close()
        with self._lock:
            self._connections.pop(device_id, None)

    def disconnect_all(self) -> None:
        with self._lock:
            ids = list(self._connections.keys())
        for device_id in ids:
            self.disconnect(device_id)

    def get_connection(self, device_id: str) -> SerialConnection | None:
        with self._lock:
            return self._connections.get(device_id)

    def connected_ports(self) -> list[str]:
        with self._lock:
            return sorted(device_id for device_id, conn in self._connections.items() if conn.is_open)
