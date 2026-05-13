from __future__ import annotations

from types import SimpleNamespace

from serialhub.core import device_manager
from serialhub.core.device_manager import DeviceManager, is_supported_serial_port


def test_linux_scan_devices_only_lists_supported_physical_serial_ports(monkeypatch) -> None:
    ports = [
        SimpleNamespace(device="/dev/ttyUSB0", description="USB serial", hwid="USB-0"),
        SimpleNamespace(device="/dev/ttyACM1", description="ACM serial", hwid="ACM-1"),
        SimpleNamespace(device="/dev/ttyAMA2", description="AMA serial", hwid="AMA-2"),
        SimpleNamespace(device="/dev/ttyS0", description="Built-in UART", hwid="S-0"),
        SimpleNamespace(device="/dev/input/mouse0", description="Mouse", hwid="MOUSE-0"),
        SimpleNamespace(device="/dev/null", description="Null", hwid="NULL"),
    ]
    monkeypatch.setattr(device_manager.sys, "platform", "linux")
    monkeypatch.setattr(device_manager.list_ports, "comports", lambda: ports)

    devices = DeviceManager().scan_devices()

    assert [device.port for device in devices] == ["/dev/ttyACM1", "/dev/ttyAMA2", "/dev/ttyUSB0"]


def test_non_linux_scan_devices_keeps_pyserial_results(monkeypatch) -> None:
    ports = [
        SimpleNamespace(device="COM4", description="USB serial", hwid="USB-4"),
        SimpleNamespace(device="/dev/ttyS0", description="Serial", hwid="S-0"),
    ]
    monkeypatch.setattr(device_manager.sys, "platform", "win32")
    monkeypatch.setattr(device_manager.list_ports, "comports", lambda: ports)

    devices = DeviceManager().scan_devices()

    assert [device.port for device in devices] == ["/dev/ttyS0", "COM4"]


def test_linux_supported_serial_port_matches_usb_acm_and_ama(monkeypatch) -> None:
    monkeypatch.setattr(device_manager.sys, "platform", "linux")

    assert is_supported_serial_port("/dev/ttyUSB0")
    assert is_supported_serial_port("/dev/ttyACM0")
    assert is_supported_serial_port("/dev/ttyAMA0")
    assert not is_supported_serial_port("/dev/ttyS0")
    assert not is_supported_serial_port("/dev/null")
