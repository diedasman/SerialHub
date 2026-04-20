import asyncio
import socketserver
import threading
import time
from types import SimpleNamespace

from serialhub.core.models import TcpConfig
from serialhub.core.tcp_connection import TcpConnection


class EchoHandler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        while True:
            data = self.request.recv(4096)
            if not data:
                return
            self.request.sendall(data.upper())


def test_tcp_connection_sends_and_receives_payload() -> None:
    events = []

    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), EchoHandler) as server:
        server.daemon_threads = True
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        host, port = server.server_address
        config = TcpConfig(host=host, port=port, timeout=2.0)
        conn = TcpConnection(device_id=config.device_id, config=config, event_callback=events.append)

        try:
            conn.open()
            assert conn.is_open is True

            written = conn.send(b"ping")
            assert written == 4

            deadline = time.time() + 2.0
            while time.time() < deadline:
                if any(event.direction == "RX" and event.payload == b"PING" for event in events):
                    break
                time.sleep(0.01)

            assert any(event.direction == "INFO" and event.text == "Connection opened" for event in events)
            assert any(event.direction == "TX" and event.payload == b"ping" for event in events)
            assert any(event.direction == "RX" and event.payload == b"PING" for event in events)
        finally:
            conn.close()
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2.0)

    assert conn.is_open is False
    assert any(event.direction == "INFO" and event.text == "Connection closed" for event in events)


class SlowClosingWriter:
    def __init__(self) -> None:
        self.closed = False
        self.aborted = False
        self.transport = SimpleNamespace(abort=self._abort)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        await asyncio.sleep(1.0)

    def _abort(self) -> None:
        self.aborted = True


def test_tcp_connection_aborts_slow_writer_shutdown() -> None:
    config = TcpConfig(host="127.0.0.1", port=4059, timeout=5.0)
    conn = TcpConnection(device_id=config.device_id, config=config, event_callback=lambda event: None)
    writer = SlowClosingWriter()

    started = time.perf_counter()
    asyncio.run(conn._close_writer_async(writer))
    elapsed = time.perf_counter() - started

    assert writer.closed is True
    assert writer.aborted is True
    assert elapsed < 0.75
