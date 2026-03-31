from __future__ import annotations

import threading
import time
from collections.abc import Callable

import serial

from serialhub.core.models import PARITY_MAP, STOP_BITS_MAP, SerialConfig, SerialEvent

_BYTESIZE_MAP = {
    5: serial.FIVEBITS,
    6: serial.SIXBITS,
    7: serial.SEVENBITS,
    8: serial.EIGHTBITS,
}


class SerialConnection:
    def __init__(
        self,
        device_id: str,
        port: str,
        config: SerialConfig,
        event_callback: Callable[[SerialEvent], None],
    ) -> None:
        self.device_id = device_id
        self.port = port
        self.config = config
        self._event_callback = event_callback

        self._serial: serial.Serial | None = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def open(self) -> None:
        self.config.validate()
        with self._lock:
            if self.is_open:
                return
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.config.baudrate,
                parity=PARITY_MAP[self.config.parity],
                stopbits=STOP_BITS_MAP[self.config.stopbits],
                bytesize=_BYTESIZE_MAP[self.config.databits],
                timeout=self.config.timeout,
            )
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._reader_loop, daemon=True, name=f"serial:{self.port}")
            self._thread.start()

        self._event_callback(
            SerialEvent(device_id=self.device_id, port=self.port, direction="INFO", text="Connection opened")
        )

    def close(self) -> None:
        with self._lock:
            self._stop_event.set()
            serial_obj = self._serial

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        with self._lock:
            if serial_obj and serial_obj.is_open:
                serial_obj.close()
            self._serial = None

        self._event_callback(
            SerialEvent(device_id=self.device_id, port=self.port, direction="INFO", text="Connection closed")
        )

    def send(self, data: bytes) -> int:
        if not data:
            return 0
        with self._lock:
            if not self._serial or not self._serial.is_open:
                raise RuntimeError(f"Port {self.port} is not open.")
            written = self._serial.write(data)
            self._serial.flush()

        self._event_callback(
            SerialEvent(device_id=self.device_id, port=self.port, direction="TX", payload=data)
        )
        return written

    def _reader_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    serial_obj = self._serial
                if not serial_obj or not serial_obj.is_open:
                    return

                pending = serial_obj.in_waiting
                chunk = serial_obj.read(pending or 1)
                if chunk:
                    self._event_callback(
                        SerialEvent(device_id=self.device_id, port=self.port, direction="RX", payload=chunk)
                    )
                else:
                    time.sleep(0.02)
            except serial.SerialException as exc:
                self._event_callback(
                    SerialEvent(device_id=self.device_id, port=self.port, direction="ERROR", text=str(exc))
                )
                self._stop_event.set()
            except OSError as exc:
                self._event_callback(
                    SerialEvent(device_id=self.device_id, port=self.port, direction="ERROR", text=str(exc))
                )
                self._stop_event.set()
