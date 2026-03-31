from serialhub.app import SerialHubApp
from serialhub.core.models import SerialEvent


def test_on_serial_event_ignored_when_shutting_down() -> None:
    app = SerialHubApp()
    app._shutting_down = True
    app._on_serial_event(SerialEvent(device_id='COM4', port='COM4', direction='INFO', text='closing'))
