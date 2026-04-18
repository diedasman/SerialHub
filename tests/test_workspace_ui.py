import asyncio
from types import SimpleNamespace

from textual.widgets import Button

from serialhub.app import ScriptEditorScreen, SerialHubApp
from serialhub.core.models import DeviceInfo, SerialEvent


class FakeDeviceManager:
    def __init__(self) -> None:
        self.connected: set[str] = set()
        self.devices = [DeviceInfo(port="COM1", description="Demo Device", hwid="HWID-1")]

    def scan_devices(self) -> list[DeviceInfo]:
        return self.devices

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


class MultiDeviceManager(FakeDeviceManager):
    def __init__(self) -> None:
        super().__init__()
        self.devices = [
            DeviceInfo(port="COM1", description="Demo Device 1", hwid="HWID-1"),
            DeviceInfo(port="COM2", description="Demo Device 2", hwid="HWID-2"),
        ]


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
            assert app.query_one("#close-active-workspace", Button).disabled is False

            app._close_workspace_for_device("COM1")
            await pilot.pause()

            assert "COM1" not in app.sessions
            assert app.active_device_id is None
            assert app.query_one("#workspace-selection").renderable == "No device workspaces open."
            assert app.query_one("#close-active-workspace", Button).disabled is True

    asyncio.run(scenario())


def test_toolbar_close_button_closes_active_workspace() -> None:
    async def scenario() -> None:
        app = SerialHubApp()
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            app._connect_selected_device()
            await pilot.pause()

            await pilot.click("#close-active-workspace")
            await pilot.pause()

            assert "COM1" not in app.sessions
            assert app.active_device_id is None

    asyncio.run(scenario())


def test_workspace_log_scroll_does_not_jump_when_user_is_reading_history() -> None:
    async def scenario() -> None:
        app = SerialHubApp()
        app.device_manager = FakeDeviceManager()

        async with app.run_test() as pilot:
            app._connect_selected_device()

            for index in range(80):
                app._handle_serial_event_ui(
                    SerialEvent(
                        device_id="COM1",
                        port="COM1",
                        direction="RX",
                        payload=f"line-{index}".encode(),
                    )
                )
            await pilot.pause()

            raw_log = app._workspace_logs["COM1"]
            raw_log.scroll_to(y=0, animate=False, immediate=True)
            await pilot.pause()
            assert raw_log.scroll_y == 0

            app._handle_serial_event_ui(
                SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"latest-line")
            )
            await pilot.pause()

            assert raw_log.scroll_y == 0
            assert raw_log.max_scroll_y > 0

    asyncio.run(scenario())


def test_second_connected_device_keeps_workspace_log_visible() -> None:
    async def scenario() -> None:
        app = SerialHubApp()
        app.device_manager = MultiDeviceManager()

        async with app.run_test() as pilot:
            app.selected_port = "COM1"
            app._connect_selected_device()
            await pilot.pause()

            app.selected_port = "COM2"
            app._connect_selected_device()
            await pilot.pause()
            await pilot.pause()

            raw_log = app._workspace_logs["COM2"]
            assert app.active_device_id == "COM2"
            assert raw_log.region.height > 0
            assert raw_log.size.height > 0

    asyncio.run(scenario())
