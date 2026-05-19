from __future__ import annotations

import base64
import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any

import websocket

from .audio_recorder import AudioRecorder
from .paths import ROOT_DIR


REALTIME_SAMPLE_RATE = 24000
ASR_COMMIT_SECONDS = 2.0


class RealtimeBaseController:
    model = ""
    title = ""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._ws: websocket.WebSocket | None = None
        self._recorder: AudioRecorder | None = None
        self._started_at = 0.0
        self._last_audio_duration = 0.0
        self.state: dict[str, Any] = {
            "running": False,
            "status": "Idle",
            "model": self.model,
            "input_mode": "",
            "error": "",
            "audio_duration": 0.0,
        }

    def update_config(self, config: dict[str, Any]) -> None:
        self.config = config

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            state = dict(self.state)
            state["audio_duration"] = round(self.duration(), 3)
            return state

    def clear_text(self) -> None:
        with self._lock:
            self._clear_text_locked()

    def get_text(self) -> str:
        with self._lock:
            return str(self.state.get("text") or "")

    def duration(self) -> float:
        if self.state.get("running") and self._started_at:
            return max(0.0, time.monotonic() - self._started_at)
        return max(0.0, self._last_audio_duration)

    def start(self, input_mode: str, target_language: str | None = None) -> dict[str, Any]:
        api_key = self._api_key()
        if not api_key:
            return {"ok": False, "error": "Enter an OpenAI API key in Settings first."}
        with self._lock:
            if self.state.get("running"):
                return {"ok": True}
            self._stop_event.clear()
            self._clear_text_locked()
            self._started_at = time.monotonic()
            self._last_audio_duration = 0.0
            self.state.update(
                {
                    "running": True,
                    "status": "Connecting",
                    "input_mode": input_mode,
                    "target_language": target_language or "",
                    "error": "",
                    "audio_duration": 0.0,
                }
            )
        self._thread = threading.Thread(target=self._run, args=(input_mode, target_language, api_key), daemon=True)
        self._thread.start()
        return {"ok": True}

    def stop(self) -> dict[str, Any]:
        self._stop_event.set()
        if self._recorder:
            self._recorder.stop()
        if self._ws:
            try:
                self._commit_or_close()
            except Exception:
                pass
            try:
                self._ws.close()
            except Exception:
                pass
        with self._lock:
            self.state["running"] = False
            if not self.state.get("error"):
                self.state["status"] = "Idle"
        return {"ok": True}

    def save_markdown(self, export_name: str) -> dict[str, Any]:
        text = self.get_text().strip()
        if not text:
            return {"ok": False, "error": "Nothing to save."}
        export_dir = ROOT_DIR / "realtime_exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / export_name
        path.write_text(text + "\n", encoding="utf-8")
        return {"ok": True, "path": str(path)}

    def _run(self, input_mode: str, target_language: str | None, api_key: str) -> None:
        chunks: queue.Queue[bytes] = queue.Queue()
        try:
            self._set_state(status="Connecting")
            self._ws = websocket.WebSocket()
            self._ws.connect(
                self._url(),
                header=[
                    f"Authorization: Bearer {api_key}",
                    "OpenAI-Safety-Identifier: todd-transcript-dev-user",
                ],
            )
            self._send_session_update(target_language)

            recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
            recv_thread.start()

            self._recorder = AudioRecorder(
                sample_rate=REALTIME_SAMPLE_RATE,
                channels=1,
                input_mode=input_mode,
            )
            self._recorder.set_chunk_callback(chunks.put)
            self._set_state(status="Listening")
            self._recorder.start()

            while not self._stop_event.is_set():
                try:
                    pcm = chunks.get(timeout=0.1)
                except queue.Empty:
                    continue
                self._send_audio(pcm)
        except Exception as exc:
            self._set_state(error=str(exc), status="Error")
        finally:
            if self._recorder:
                try:
                    self._last_audio_duration = self._recorder.duration()
                    self._recorder.stop()
                except Exception:
                    pass
            elif self._started_at:
                self._last_audio_duration = max(0.0, time.monotonic() - self._started_at)
            if self._ws:
                try:
                    self._ws.close()
                except Exception:
                    pass
            with self._lock:
                self.state["running"] = False
                self.state["audio_duration"] = round(self._last_audio_duration, 3)
                if not self.state.get("error"):
                    self.state["status"] = "Idle"
            self._recorder = None
            self._ws = None

    def _receive_loop(self) -> None:
        while not self._stop_event.is_set() and self._ws:
            try:
                raw = self._ws.recv()
                if not raw:
                    continue
                event = json.loads(raw)
            except Exception as exc:
                if not self._stop_event.is_set():
                    self._set_state(error=str(exc), status="Error")
                return
            self._handle_event(event)

    def _api_key(self) -> str:
        configured = ((self.config.get("openai") or {}).get("api_key") or "").strip()
        return configured or os.environ.get("OPENAI_API_KEY", "").strip()

    def _set_state(self, **values: Any) -> None:
        with self._lock:
            self.state.update(values)

    def _clear_text_locked(self) -> None:
        self.state["text"] = ""

    def _send_json(self, payload: dict[str, Any]) -> None:
        if not self._ws:
            raise RuntimeError("Realtime socket is not connected")
        self._ws.send(json.dumps(payload))

    def _audio_b64(self, pcm: bytes) -> str:
        return base64.b64encode(pcm).decode("ascii")

    def _url(self) -> str:
        raise NotImplementedError

    def _send_session_update(self, target_language: str | None) -> None:
        raise NotImplementedError

    def _send_audio(self, pcm: bytes) -> None:
        raise NotImplementedError

    def _handle_event(self, event: dict[str, Any]) -> None:
        raise NotImplementedError

    def _commit_or_close(self) -> None:
        pass


class RealtimeASRController(RealtimeBaseController):
    model = "gpt-realtime-whisper"
    session_model = "transcription"
    title = "Realtime ASR"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._pending_audio_bytes = 0
        self._last_commit_at = 0.0
        with self._lock:
            self.state["finals"] = []
            self.state["partial"] = ""
            self.state["session_model"] = self.session_model

    def get_text(self) -> str:
        with self._lock:
            return self._join_finals(self.state.get("finals") or [])

    def _clear_text_locked(self) -> None:
        self.state["finals"] = []
        self.state["partial"] = ""
        self.state["text"] = ""

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            state = dict(self.state)
            state["audio_duration"] = round(self.duration(), 3)
            state["show_partial_words"] = self._show_partial_words()
            if not state["show_partial_words"]:
                state["partial"] = ""
            return state

    def _url(self) -> str:
        return "wss://api.openai.com/v1/realtime?intent=transcription"

    def _send_session_update(self, target_language: str | None) -> None:
        self._pending_audio_bytes = 0
        self._last_commit_at = time.monotonic()
        language = ((self.config.get("realtime") or {}).get("source_language") or "").strip()
        transcription: dict[str, Any] = {"model": self.model}
        if language:
            transcription["language"] = language
        self._send_json(
            {
                "type": "session.update",
                "session": {
                    "type": "transcription",
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": REALTIME_SAMPLE_RATE},
                            "transcription": transcription,
                        }
                    },
                },
            }
        )

    def _send_audio(self, pcm: bytes) -> None:
        self._send_json({"type": "input_audio_buffer.append", "audio": self._audio_b64(pcm)})
        self._pending_audio_bytes += len(pcm)
        now = time.monotonic()
        min_bytes = int(REALTIME_SAMPLE_RATE * 2 * ASR_COMMIT_SECONDS)
        if self._pending_audio_bytes >= min_bytes and now - self._last_commit_at >= ASR_COMMIT_SECONDS:
            self._send_json({"type": "input_audio_buffer.commit"})
            self._pending_audio_bytes = 0
            self._last_commit_at = now

    def _commit_or_close(self) -> None:
        if self._pending_audio_bytes:
            self._send_json({"type": "input_audio_buffer.commit"})
            self._pending_audio_bytes = 0

    def _handle_event(self, event: dict[str, Any]) -> None:
        kind = event.get("type", "")
        if kind == "conversation.item.input_audio_transcription.delta":
            with self._lock:
                self.state["partial"] = str(event.get("delta") or "") if self._show_partial_words() else ""
        elif kind == "conversation.item.input_audio_transcription.completed":
            transcript = str(event.get("transcript") or "").strip()
            if transcript:
                with self._lock:
                    self.state.setdefault("finals", []).append(transcript)
                    self.state["partial"] = ""
                    self.state["text"] = self._join_finals(self.state.get("finals") or [])
        elif kind == "error":
            error = event.get("error") or {}
            self._set_state(error=str(error.get("message") or error or "Realtime error"), status="Error")

    def _join_finals(self, finals: list[str]) -> str:
        return " ".join(" ".join(part.split()) for part in finals if part).strip()

    def _show_partial_words(self) -> bool:
        return bool(((self.config.get("realtime") or {}).get("show_partial_words", False)))


class RealtimeTranslateController(RealtimeBaseController):
    model = "gpt-realtime-translate"
    title = "Realtime Translate"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        with self._lock:
            self.state["translation_text"] = ""
            self.state["source_text"] = ""

    def get_text(self) -> str:
        with self._lock:
            return str(self.state.get("translation_text") or "").strip()

    def _clear_text_locked(self) -> None:
        self.state["translation_text"] = ""
        self.state["source_text"] = ""
        self.state["text"] = ""

    def _url(self) -> str:
        return "wss://api.openai.com/v1/realtime/translations?model=gpt-realtime-translate"

    def _send_session_update(self, target_language: str | None) -> None:
        self._send_json(
            {
                "type": "session.update",
                "session": {
                    "audio": {
                        "output": {"language": target_language or self.config.get("target_language") or "zh"},
                    }
                },
            }
        )

    def _send_audio(self, pcm: bytes) -> None:
        self._send_json({"type": "session.input_audio_buffer.append", "audio": self._audio_b64(pcm)})

    def _handle_event(self, event: dict[str, Any]) -> None:
        kind = event.get("type", "")
        if kind == "session.output_transcript.delta":
            delta = str(event.get("delta") or "")
            with self._lock:
                self.state["translation_text"] = str(self.state.get("translation_text") or "") + delta
                self.state["text"] = self.state["translation_text"]
                self.state["status"] = "Translating"
        elif kind == "session.input_transcript.delta":
            delta = str(event.get("delta") or "")
            with self._lock:
                self.state["source_text"] = str(self.state.get("source_text") or "") + delta
        elif kind == "error":
            error = event.get("error") or {}
            self._set_state(error=str(error.get("message") or error or "Realtime error"), status="Error")
