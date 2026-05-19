from __future__ import annotations

import json
import threading
import time
from typing import Callable, Any

import websocket


class PipelineClient:
    def __init__(self, url: str, timeout: int = 300):
        self.url = url
        self.timeout = timeout
        self.ws: websocket.WebSocket | None = None
        self.connected = False
        self.done = threading.Event()
        self.error = ""
        self.asr_text = ""
        self.gpt_text = ""
        self.asr_elapsed = 0.0
        self.gpt_elapsed = 0.0
        self.total_elapsed = 0.0
        self.on_asr_delta: Callable[[str], None] | None = None
        self.on_asr_done: Callable[[str], None] | None = None
        self.on_gpt_delta: Callable[[str], None] | None = None
        self.on_gpt_done: Callable[[str], None] | None = None
        self.on_error: Callable[[str], None] | None = None
        self.on_done: Callable[[], None] | None = None
        self._recv_thread: threading.Thread | None = None
        self._running = False
        self._stop_sent_at = 0.0

    def connect(self, client_version: str, device_id: str = "dev") -> None:
        self.ws = websocket.WebSocket()
        self.ws.settimeout(self.timeout)
        self.ws.connect(self.url)
        self.connected = True
        self.ws.send(json.dumps({"type": "hello", "client_version": client_version, "device_id": device_id}))

    def start_session(self, config: dict[str, Any]) -> None:
        if not self.ws or not self.connected:
            raise RuntimeError("Pipeline is not connected")
        self.done.clear()
        self.error = ""
        self.asr_text = ""
        self.gpt_text = ""
        self.ws.send(json.dumps({"type": "start", "config": config}))
        self._running = True
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()

    def send_audio_chunk(self, pcm_data: bytes) -> None:
        if self.ws and self.connected:
            try:
                self.ws.send_binary(pcm_data)
            except Exception:
                self.connected = False

    def stop_session(self, wait_timeout: int | float = 300) -> bool:
        if not self.ws or not self.connected:
            self.error = "Pipeline disconnected before stop"
            return False
        try:
            self._stop_sent_at = time.time()
            self.ws.send(json.dumps({"type": "stop", "client_stop_sent": round(self._stop_sent_at, 3)}))
        except Exception as exc:
            self.error = f"Pipeline stop failed: {exc}"
            self.connected = False
            return False
        if not self.done.wait(timeout=wait_timeout):
            self.error = "Pipeline timed out"
            return False
        return not self.error

    def close(self) -> None:
        self._running = False
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self.connected = False

    def _recv_loop(self) -> None:
        while self._running and self.ws and self.connected:
            try:
                self.ws.settimeout(30.0)
                raw = self.ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception as exc:
                self._fail(f"Pipeline WebSocket error: {exc}")
                return
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            self._handle_message(msg)

    def _handle_message(self, msg: dict[str, Any]) -> None:
        kind = msg.get("type", "")
        if kind == "asr_delta":
            if self.on_asr_delta:
                self.on_asr_delta(msg.get("text", ""))
        elif kind == "asr_done":
            self.asr_text = msg.get("text", "")
            self.asr_elapsed = float(msg.get("elapsed", 0.0) or 0.0)
            if self.on_asr_done:
                self.on_asr_done(self.asr_text)
        elif kind == "gpt_delta":
            if self.on_gpt_delta:
                self.on_gpt_delta(msg.get("text", ""))
        elif kind == "gpt_done":
            self.gpt_text = msg.get("text", "")
            self.gpt_elapsed = float(msg.get("elapsed", 0.0) or 0.0)
            if self.on_gpt_done:
                self.on_gpt_done(self.gpt_text)
        elif kind == "error":
            self._fail(msg.get("message", "Unknown pipeline error"))
        elif kind == "version_rejected":
            self._fail("The backend rejected this client version.")
        elif kind == "done":
            self.total_elapsed = float(msg.get("total_elapsed", 0.0) or 0.0)
            if self.on_done:
                self.on_done()
            self.done.set()

    def _fail(self, message: str) -> None:
        self.error = message
        if self.on_error:
            self.on_error(message)
        self.done.set()
