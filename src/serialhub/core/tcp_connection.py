from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import Callable

from serialhub.core.models import SerialEvent, TcpConfig

_CLOSE_WAIT_TIMEOUT_SECONDS = 0.25
_THREAD_JOIN_TIMEOUT_SECONDS = 0.5


class TcpConnection:
    def __init__(
        self,
        device_id: str,
        config: TcpConfig,
        event_callback: Callable[[SerialEvent], None],
    ) -> None:
        self.device_id = device_id
        self.port = device_id
        self.config = config
        self._event_callback = event_callback

        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._main_task: asyncio.Task[None] | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._stop_event = threading.Event()
        self._opened_event = threading.Event()
        self._open_error: Exception | None = None
        self._is_open = False
        self._close_reported = False

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._is_open

    def open(self) -> None:
        self.config.validate()
        with self._lock:
            if self._is_open:
                return
            self._stop_event.clear()
            self._opened_event.clear()
            self._open_error = None
            self._close_reported = False
            self._thread = threading.Thread(
                target=self._run_event_loop,
                daemon=True,
                name=f"tcp:{self.device_id}",
            )
            self._thread.start()

        if not self._opened_event.wait(self.config.timeout + 1.0):
            self.close()
            raise TimeoutError(f"Timed out connecting to {self.device_id}.")

        if self._open_error is not None:
            error = self._open_error
            self.close()
            raise error

    def close(self) -> None:
        with self._lock:
            loop = self._loop
            main_task = self._main_task
            thread = self._thread
            self._is_open = False

        self._stop_event.set()
        self._opened_event.set()

        if loop and loop.is_running():
            if main_task:
                loop.call_soon_threadsafe(main_task.cancel)
            with contextlib.suppress(Exception):
                future = asyncio.run_coroutine_threadsafe(self._close_stream_async(), loop)
                future.result(timeout=_CLOSE_WAIT_TIMEOUT_SECONDS + 0.1)
            with contextlib.suppress(Exception):
                loop.call_soon_threadsafe(self._abort_writer)

        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=_THREAD_JOIN_TIMEOUT_SECONDS)

    def send(self, data: bytes) -> int:
        if not data:
            return 0

        with self._lock:
            loop = self._loop

        if not self.is_open or loop is None:
            raise RuntimeError(f"TCP socket {self.device_id} is not open.")

        future = asyncio.run_coroutine_threadsafe(self._send_async(data), loop)
        written = future.result(timeout=self.config.timeout + 1.0)
        self._event_callback(
            SerialEvent(device_id=self.device_id, port=self.port, direction="TX", payload=data)
        )
        return written

    def _run_event_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
            self._main_task = loop.create_task(self._connection_main())

        try:
            loop.run_until_complete(self._main_task)
        except asyncio.CancelledError:
            pass
        finally:
            pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                with contextlib.suppress(Exception):
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            with self._lock:
                self._main_task = None
                self._loop = None
                self._thread = None
            loop.close()

    async def _connection_main(self) -> None:
        opened = False
        try:
            connect_task = asyncio.open_connection(self.config.host, self.config.port)
            reader, writer = await asyncio.wait_for(connect_task, timeout=self.config.timeout)
            with self._lock:
                self._reader = reader
                self._writer = writer
                self._is_open = True
            opened = True
            self._opened_event.set()
            self._event_callback(
                SerialEvent(
                    device_id=self.device_id,
                    port=self.port,
                    direction="INFO",
                    text="Connection opened",
                )
            )
            await self._reader_loop(reader)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not opened:
                self._open_error = exc
                self._opened_event.set()
                return
            if not self._stop_event.is_set():
                self._event_callback(
                    SerialEvent(device_id=self.device_id, port=self.port, direction="ERROR", text=str(exc))
                )
        finally:
            await self._cleanup_async(opened=opened)

    async def _reader_loop(self, reader: asyncio.StreamReader) -> None:
        while not self._stop_event.is_set():
            chunk = await reader.read(self.config.read_size)
            if chunk:
                self._event_callback(
                    SerialEvent(device_id=self.device_id, port=self.port, direction="RX", payload=chunk)
                )
                continue

            if not self._stop_event.is_set():
                self._event_callback(
                    SerialEvent(
                        device_id=self.device_id,
                        port=self.port,
                        direction="INFO",
                        text="Connection closed by remote host",
                    )
                )
            return

    async def _send_async(self, data: bytes) -> int:
        with self._lock:
            writer = self._writer
        if writer is None or writer.is_closing():
            raise RuntimeError(f"TCP socket {self.device_id} is not open.")

        writer.write(data)
        await writer.drain()
        return len(data)

    async def _close_stream_async(self) -> None:
        with self._lock:
            writer = self._writer
        await self._close_writer_async(writer)

    def _abort_writer(self, writer: asyncio.StreamWriter | None = None) -> None:
        target = writer
        if target is None:
            with self._lock:
                target = self._writer
        if target is None:
            return
        transport = getattr(target, "transport", None)
        if transport is None:
            return
        with contextlib.suppress(Exception):
            transport.abort()

    async def _close_writer_async(self, writer: asyncio.StreamWriter | None) -> None:
        if writer is None:
            return
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), timeout=_CLOSE_WAIT_TIMEOUT_SECONDS)
        except TimeoutError:
            self._abort_writer(writer)
        except Exception:
            self._abort_writer(writer)

    async def _cleanup_async(self, *, opened: bool) -> None:
        with self._lock:
            writer = self._writer
            self._reader = None
            self._writer = None
            self._is_open = False

        await self._close_writer_async(writer)

        if opened and not self._close_reported:
            self._close_reported = True
            self._event_callback(
                SerialEvent(
                    device_id=self.device_id,
                    port=self.port,
                    direction="INFO",
                    text="Connection closed",
                )
            )
