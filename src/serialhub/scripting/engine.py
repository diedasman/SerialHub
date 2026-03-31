from __future__ import annotations

import builtins
import queue
import re
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass

ScriptLogCallback = Callable[[str], None]
ScriptSendCallback = Callable[[bytes], None]
MessageHandler = Callable[[str, bytes], None]
PatternHandler = Callable[[re.Match[str], str, bytes], None]
PatternDecorator = Callable[[PatternHandler], PatternHandler]


@dataclass(slots=True)
class RxMessage:
    raw: bytes
    text: str


class ScriptRunner:
    def __init__(
        self,
        device_id: str,
        script_source: str,
        sender: ScriptSendCallback,
        logger: ScriptLogCallback,
    ) -> None:
        self.device_id = device_id
        self.script_source = script_source
        self._sender = sender
        self._logger = logger

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._rx_queue: queue.Queue[RxMessage] = queue.Queue()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"script:{self.device_id}")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def publish_rx(self, payload: bytes) -> None:
        text = payload.decode("latin-1", errors="ignore")
        self._rx_queue.put(RxMessage(raw=payload, text=text))

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def _run(self) -> None:
        on_message_handlers: list[MessageHandler] = []
        on_pattern_handlers: list[tuple[re.Pattern[str], PatternHandler]] = []

        def log(message: object) -> None:
            self._logger(str(message))

        def stop_requested() -> bool:
            return self._stop_event.is_set()

        def sleep(seconds: float) -> None:
            time.sleep(seconds)

        def send(data: str | bytes, *, hex_mode: bool = False, append_crlf: bool = False) -> None:
            payload = data
            if isinstance(payload, str):
                payload = payload.strip() if hex_mode else payload
                if hex_mode:
                    payload_bytes = bytes.fromhex(payload)
                else:
                    payload_bytes = payload.encode("utf-8")
            else:
                payload_bytes = payload

            if append_crlf:
                payload_bytes += b"\r\n"
            self._sender(payload_bytes)

        def on_message(func: MessageHandler) -> MessageHandler:
            on_message_handlers.append(func)
            return func

        def on_pattern(pattern: str) -> PatternDecorator:
            compiled = re.compile(pattern)

            def decorator(func: PatternHandler) -> PatternHandler:
                on_pattern_handlers.append((compiled, func))
                return func

            return decorator

        def wait_for(pattern: str, timeout: float = 5.0) -> str | None:
            compiled = re.compile(pattern)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and not self._stop_event.is_set():
                remaining = max(0.01, deadline - time.monotonic())
                try:
                    msg = self._rx_queue.get(timeout=min(0.2, remaining))
                except queue.Empty:
                    continue
                if compiled.search(msg.text):
                    return msg.text
            return None

        safe_builtins = {
            key: getattr(builtins, key)
            for key in (
                "abs",
                "all",
                "any",
                "bool",
                "bytes",
                "dict",
                "enumerate",
                "float",
                "int",
                "len",
                "list",
                "max",
                "min",
                "print",
                "range",
                "reversed",
                "set",
                "sorted",
                "str",
                "sum",
                "tuple",
                "zip",
            )
        }

        globals_scope = {
            "__builtins__": safe_builtins,
            "log": log,
            "send": send,
            "sleep": sleep,
            "wait_for": wait_for,
            "stop_requested": stop_requested,
            "on_message": on_message,
            "on_pattern": on_pattern,
        }

        locals_scope: dict[str, object] = {}

        try:
            exec(self.script_source, globals_scope, locals_scope)
            candidate = locals_scope.get("main") or globals_scope.get("main")
            if callable(candidate):
                candidate()

            while not self._stop_event.is_set():
                try:
                    message = self._rx_queue.get(timeout=0.2)
                except queue.Empty:
                    continue

                for handler in on_message_handlers:
                    try:
                        handler(message.text, message.raw)
                    except Exception as exc:  # pragma: no cover - defensive
                        self._logger(f"on_message handler error: {exc}")

                for pattern, handler in on_pattern_handlers:
                    match = pattern.search(message.text)
                    if not match:
                        continue
                    try:
                        handler(match, message.text, message.raw)
                    except Exception as exc:  # pragma: no cover - defensive
                        self._logger(f"on_pattern handler error: {exc}")
        except Exception as exc:
            self._logger(f"Script crashed: {exc}")
            self._logger(traceback.format_exc())


class ScriptEngine:
    def __init__(self) -> None:
        self._runners: dict[str, ScriptRunner] = {}

    def start(
        self,
        device_id: str,
        script_source: str,
        sender: ScriptSendCallback,
        logger: ScriptLogCallback,
    ) -> None:
        self.stop(device_id)
        runner = ScriptRunner(device_id=device_id, script_source=script_source, sender=sender, logger=logger)
        self._runners[device_id] = runner
        runner.start()

    def stop(self, device_id: str) -> None:
        runner = self._runners.get(device_id)
        if not runner:
            return
        runner.stop()
        self._runners.pop(device_id, None)

    def stop_all(self) -> None:
        for device_id in list(self._runners.keys()):
            self.stop(device_id)

    def publish_rx(self, device_id: str, payload: bytes) -> None:
        runner = self._runners.get(device_id)
        if runner:
            runner.publish_rx(payload)

    def is_running(self, device_id: str) -> bool:
        runner = self._runners.get(device_id)
        return runner.is_running() if runner else False
