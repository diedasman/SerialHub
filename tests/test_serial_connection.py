from serialhub.core.models import SerialConfig
from serialhub.core.serial_connection import SerialConnection


class BurstSerial:
    def __init__(self, first_byte: bytes, remainder: bytes) -> None:
        self.is_open = True
        self._first_byte = first_byte
        self._remainder = remainder
        self._first_read_done = False

    @property
    def in_waiting(self) -> int:
        if not self._first_read_done:
            return 0
        return len(self._remainder)

    def read(self, size: int) -> bytes:
        if not self._first_read_done:
            self._first_read_done = True
            return self._first_byte[:size]
        data = self._remainder[:size]
        self._remainder = self._remainder[size:]
        return data


def test_read_chunk_coalesces_leading_byte_with_same_burst(monkeypatch) -> None:
    monkeypatch.setattr("serialhub.core.serial_connection.time.sleep", lambda _: None)

    conn = SerialConnection(
        device_id="COM5",
        port="COM5",
        config=SerialConfig(baudrate=115200, timeout=0.2),
        event_callback=lambda event: None,
    )
    serial_obj = BurstSerial(b"M", b"ETER|mode=BASIC|ms=199973\n")

    chunk = conn._read_chunk(serial_obj)

    assert chunk == b"METER|mode=BASIC|ms=199973\n"
