from datetime import datetime

from serialhub.app import SerialHubApp
from serialhub.core.models import SerialConfig, SerialEvent
from serialhub.core.session import DeviceSession
from serialhub.logging.session_logger import SessionLogger


def test_raw_workspace_output_omits_rx_tx_tags() -> None:
    app = SerialHubApp(require_login=False)
    session = DeviceSession(
        device_id="COM1",
        port="COM1",
        transport="serial",
        config=SerialConfig(),
        timestamps_enabled=False,
    )
    event = SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"hello\r\n")

    assert app._render_raw_event_lines(session, event) == ["hello"]


def test_session_logger_strips_line_terminators_without_periods(tmp_path) -> None:
    log_path = tmp_path / "session.txt"
    logger = SessionLogger(log_path)
    timestamp = datetime(2026, 4, 19, 10, 30, 15, 123000)
    event = SerialEvent(
        device_id="COM1",
        port="COM1",
        direction="RX",
        payload=b"meter-ready\r\n",
        timestamp=timestamp,
    )

    logger.start()
    logger.log_event(event)
    logger.stop()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines[1] == "2026-04-19T10:30:15.123 meter-ready"


def test_session_logger_coalesces_split_serial_fragments(tmp_path) -> None:
    log_path = tmp_path / "session.txt"
    logger = SessionLogger(log_path)
    timestamp = datetime(2026, 4, 29, 10, 30, 15, 123000)

    logger.start()
    logger.log_event(
        SerialEvent(
            device_id="COM1",
            port="COM1",
            direction="RX",
            payload=b"METER|mode=BASIC|ms=199",
            timestamp=timestamp,
        )
    )
    logger.log_event(
        SerialEvent(
            device_id="COM1",
            port="COM1",
            direction="RX",
            payload=b"973\n",
            timestamp=timestamp,
        )
    )
    logger.stop()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines[1] == "2026-04-29T10:30:15.123 METER|mode=BASIC|ms=199973"


def test_session_logger_flushes_unterminated_fragment_on_stop(tmp_path) -> None:
    log_path = tmp_path / "session.txt"
    logger = SessionLogger(log_path)
    timestamp = datetime(2026, 4, 29, 10, 30, 15, 123000)

    logger.start()
    logger.log_event(
        SerialEvent(
            device_id="COM1",
            port="COM1",
            direction="RX",
            payload=b"partial-frame",
            timestamp=timestamp,
        )
    )
    logger.stop()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert lines[1] == "2026-04-29T10:30:15.123 partial-frame"


def test_active_workspace_text_coalesces_split_serial_line() -> None:
    app = SerialHubApp(require_login=False)
    session = DeviceSession(
        device_id="COM1",
        port="COM1",
        transport="serial",
        config=SerialConfig(),
        timestamps_enabled=False,
    )

    assert (
        session.add_raw_event(SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"METER|ms=199"))
        is False
    )
    assert (
        session.add_raw_event(SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"973\nNEXT"))
        is True
    )
    assert (
        session.add_raw_event(SerialEvent(device_id="COM1", port="COM1", direction="RX", payload=b"-LINE\n"))
        is True
    )

    assert len(session.raw_events) == 1
    assert app._active_workspace_text(session) == "METER|ms=199973\nNEXT-LINE"
