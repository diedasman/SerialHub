import asyncio
from types import SimpleNamespace

from serialhub.app import ScriptEditorScreen, SerialHubApp
from serialhub.core.models import DeviceInfo, SerialEvent


class FakeDeviceManager:
    def __init__(self) -> None:
        self.connected: set[str] = set()

    def scan_devices(self) -> list[DeviceInfo]:
        return [DeviceInfo(port="COM1", description="Demo Device", hwid="HWID-1")]

    def connect(self, port: str, config, event_callback):
        self.connected.add(port)
        return SimpleNamespace(is_open=True)

    def disconnect(self, device_id: str) -> None:
        self.connected.discard(device_id)

    def disconnect_all(self) -> None:
        self.connected.clear()

    def get_connection(self, device_id: str):
        return SimpleNamespace(is_open=device_id in self.connected, send=lambda payload: len(payload))

    def connected_ports(self) -> list[str]:
        return sorted(self.connected)


def test_script_editor_shortcut_opens_and_closes_screen() -> None:
    async def scenario() -> None:
        app = SerialHubApp()
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            app.action_toggle_script_editor()
            await pilot.pause()
            assert isinstance(app.screen, ScriptEditorScreen)

            await pilot.press("ctrl+e")
            await pilot.pause()
            assert not isinstance(app.screen, ScriptEditorScreen)

    asyncio.run(scenario())


def test_disconnect_preserves_workspace_until_close() -> None:
    async def scenario() -> None:
        app = SerialHubApp()
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            app._connect_selected_device()
            await pilot.pause()

            app._handle_serial_event_ui(
                SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"hello")
            )
            await pilot.pause()

            app._disconnect_device("COM1")
            await pilot.pause()

            assert "COM1" in app.sessions
            assert app.active_device_id == "COM1"
            assert app.query_one("#workspace-selection").renderable == "Active workspace: COM1 (saved)"

            app._close_workspace_for_device("COM1")
            await pilot.pause()

            assert "COM1" not in app.sessions
            assert app.active_device_id is None
            assert app.query_one("#workspace-selection").renderable == "No device workspaces open."

    asyncio.run(scenario())
