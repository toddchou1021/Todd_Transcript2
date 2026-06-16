from __future__ import annotations

import base64
import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import websocket

from .audio_recorder import AudioRecorder
from .paths import EXPORTS_DIR


GEMINI_TRANSLATE_SAMPLE_RATE = 16000
GEMINI_TRANSLATE_CHUNK_FRAMES = 1600
GEMINI_REALTIME_MODEL = "gemini-3.5-live-translate-preview"


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
            return {"ok": False, "error": self._missing_api_key_error()}
        with self._lock:
            if self.state.get("running"):
                return {"ok": True}
            self._stop_event.clear()
            self._prepare_text_for_start_locked()
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
        export_dir = EXPORTS_DIR
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / export_name
        path.write_text(text + "\n", encoding="utf-8")
        return {"ok": True, "path": str(path)}

    def _run(self, input_mode: str, target_language: str | None, api_key: str) -> None:
        chunks: queue.Queue[bytes] = queue.Queue()
        try:
            self._set_state(status="Connecting")
            self._ws = websocket.WebSocket()
            headers = self._connection_headers(api_key)
            connect_options: dict[str, Any] = {}
            if headers:
                connect_options["header"] = headers
            self._ws.connect(self._url(api_key), **connect_options)

            recv_thread = threading.Thread(target=self._receive_loop, daemon=True)
            recv_thread.start()
            self._send_session_update(target_language)
            self._wait_until_ready()
            if self._stop_event.is_set():
                return

            self._recorder = AudioRecorder(
                sample_rate=self._sample_rate(),
                channels=1,
                input_mode=input_mode,
                chunk_frames=self._chunk_frames(),
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
                    self._on_receive_error()
                return
            self._handle_event(event)

    def _api_key(self) -> str:
        configured = ((self.config.get("gemini") or {}).get("api_key") or "").strip()
        return configured or os.environ.get("GEMINI_API_KEY", "").strip()

    def _missing_api_key_error(self) -> str:
        return "Enter a Gemini API key in the main window first."

    def _connection_headers(self, api_key: str) -> list[str]:
        return []

    def _sample_rate(self) -> int:
        return GEMINI_TRANSLATE_SAMPLE_RATE

    def _chunk_frames(self) -> int:
        return GEMINI_TRANSLATE_CHUNK_FRAMES

    def _wait_until_ready(self) -> None:
        return

    def _on_receive_error(self) -> None:
        return

    def _set_state(self, **values: Any) -> None:
        with self._lock:
            self.state.update(values)

    def _clear_text_locked(self) -> None:
        self.state["text"] = ""

    def _prepare_text_for_start_locked(self) -> None:
        text = str(self.state.get("text") or "").rstrip()
        if text:
            self.state["text"] = text + "\n\n"

    def _send_json(self, payload: dict[str, Any]) -> None:
        if not self._ws:
            raise RuntimeError("Realtime socket is not connected")
        self._ws.send(json.dumps(payload))

    def _audio_b64(self, pcm: bytes) -> str:
        return base64.b64encode(pcm).decode("ascii")

    def _url(self, api_key: str) -> str:
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
    model = GEMINI_REALTIME_MODEL
    session_model = "live-translate"
    title = "Realtime ASR"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._gemini_ready = threading.Event()
        with self._lock:
            self.state["finals"] = []
            self.state["partial"] = ""
            self.state["session_model"] = self.session_model
            self.state["provider"] = "gemini"

    def start(self, input_mode: str, target_language: str | None = None) -> dict[str, Any]:
        with self._lock:
            if self.state.get("running"):
                return {"ok": True}
        self._gemini_ready.clear()
        with self._lock:
            self.state["provider"] = "gemini"
            self.state["model"] = self._selected_model()
            self.state["session_model"] = self.session_model
        return super().start(input_mode, target_language)

    def stop(self) -> dict[str, Any]:
        self._gemini_ready.set()
        return super().stop()

    def get_text(self) -> str:
        with self._lock:
            return self._join_finals(self.state.get("finals") or [])

    def _clear_text_locked(self) -> None:
        self.state["finals"] = []
        self.state["partial"] = ""
        self.state["text"] = ""

    def _prepare_text_for_start_locked(self) -> None:
        text = str(self.state.get("text") or "").rstrip()
        if not text:
            text = self._join_finals(self.state.get("finals") or []).rstrip()
        if text:
            text += "\n\n"
            self.state["finals"] = [text]
            self.state["text"] = text
        self.state["partial"] = ""

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            state = dict(self.state)
            state["audio_duration"] = round(self.duration(), 3)
            state["show_partial_words"] = self._show_partial_words()
            if not state["show_partial_words"]:
                state["partial"] = ""
            return state

    def _selected_model(self) -> str:
        return str(((self.config.get("realtime") or {}).get("gemini_translate_model")) or GEMINI_REALTIME_MODEL)

    def _url(self, api_key: str) -> str:
        encoded_key = quote(api_key, safe="")
        return (
            "wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
            f"?key={encoded_key}"
        )

    def _send_session_update(self, target_language: str | None) -> None:
        self._send_json(
            {
                "setup": {
                    "model": f"models/{self._selected_model()}",
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "translationConfig": {
                            "targetLanguageCode": "en",
                            "echoTargetLanguage": True,
                        },
                    },
                    "inputAudioTranscription": {},
                    "outputAudioTranscription": {},
                },
            }
        )

    def _send_audio(self, pcm: bytes) -> None:
        self._send_json(
            {
                "realtimeInput": {
                    "audio": {
                        "data": self._audio_b64(pcm),
                        "mimeType": f"audio/pcm;rate={GEMINI_TRANSLATE_SAMPLE_RATE}",
                    }
                }
            }
        )

    def _handle_event(self, event: dict[str, Any]) -> None:
        self._handle_gemini_event(event)

    def _wait_until_ready(self) -> None:
        if not self._gemini_ready.wait(timeout=15):
            raise RuntimeError("Gemini realtime transcription setup timed out.")
        error = str(self.get_status().get("error") or "")
        if error:
            raise RuntimeError(error)

    def _on_receive_error(self) -> None:
        self._gemini_ready.set()

    def _handle_gemini_event(self, event: dict[str, Any]) -> None:
        if "setupComplete" in event:
            self._gemini_ready.set()
            return
        if "error" in event:
            error = event.get("error") or {}
            self._set_state(error=str(error.get("message") or error or "Gemini Live error"), status="Error")
            self._gemini_ready.set()
            return

        content = event.get("serverContent") or {}
        input_transcription = content.get("inputTranscription") or {}
        transcript_delta = str(input_transcription.get("text") or "")
        if transcript_delta:
            with self._lock:
                transcript = str(self.state.get("text") or "") + transcript_delta
                self.state["text"] = transcript
                self.state["finals"] = [transcript]
                self.state["partial"] = ""
                self.state["status"] = "Transcribing"

    def _join_finals(self, finals: list[str]) -> str:
        result = ""
        for part in finals:
            value = str(part or "")
            if not value:
                continue
            result += value
        return result.strip(" ")

    def _show_partial_words(self) -> bool:
        return bool(((self.config.get("realtime") or {}).get("show_partial_words", False)))


class RealtimeTranslateController(RealtimeBaseController):
    model = GEMINI_REALTIME_MODEL
    title = "Realtime Translate"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._gemini_ready = threading.Event()
        with self._lock:
            self.state["translation_text"] = ""
            self.state["source_text"] = ""
            self.state["provider"] = "gemini"

    def start(self, input_mode: str, target_language: str | None = None) -> dict[str, Any]:
        with self._lock:
            if self.state.get("running"):
                return {"ok": True}
        self._gemini_ready.clear()
        with self._lock:
            self.state["provider"] = "gemini"
            self.state["model"] = self._selected_model()
        return super().start(input_mode, target_language)

    def stop(self) -> dict[str, Any]:
        self._gemini_ready.set()
        return super().stop()

    def get_text(self) -> str:
        with self._lock:
            return str(self.state.get("translation_text") or "").strip()

    def _clear_text_locked(self) -> None:
        self.state["translation_text"] = ""
        self.state["source_text"] = ""
        self.state["text"] = ""

    def _prepare_text_for_start_locked(self) -> None:
        translation = str(self.state.get("translation_text") or "").rstrip()
        source = str(self.state.get("source_text") or "").rstrip()
        if translation:
            translation += "\n\n"
        if source:
            source += "\n\n"
        self.state["translation_text"] = translation
        self.state["source_text"] = source
        self.state["text"] = translation

    def _selected_model(self) -> str:
        return str(((self.config.get("realtime") or {}).get("gemini_translate_model")) or GEMINI_REALTIME_MODEL)

    def _url(self, api_key: str) -> str:
        encoded_key = quote(api_key, safe="")
        return (
            "wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"
            f"?key={encoded_key}"
        )

    def _send_session_update(self, target_language: str | None) -> None:
        self._send_json(
            {
                "setup": {
                    "model": f"models/{self._selected_model()}",
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "translationConfig": {
                            "targetLanguageCode": self._gemini_language_code(target_language),
                            "echoTargetLanguage": True,
                        },
                    },
                    "inputAudioTranscription": {},
                    "outputAudioTranscription": {},
                },
            }
        )

    def _send_audio(self, pcm: bytes) -> None:
        self._send_json(
            {
                "realtimeInput": {
                    "audio": {
                        "data": self._audio_b64(pcm),
                        "mimeType": f"audio/pcm;rate={GEMINI_TRANSLATE_SAMPLE_RATE}",
                    }
                }
            }
        )

    def _handle_event(self, event: dict[str, Any]) -> None:
        self._handle_gemini_event(event)

    def _wait_until_ready(self) -> None:
        if not self._gemini_ready.wait(timeout=15):
            raise RuntimeError("Gemini Live Translate setup timed out.")
        error = str(self.get_status().get("error") or "")
        if error:
            raise RuntimeError(error)

    def _on_receive_error(self) -> None:
        self._gemini_ready.set()

    def _handle_gemini_event(self, event: dict[str, Any]) -> None:
        if "setupComplete" in event:
            self._gemini_ready.set()
            return
        if "error" in event:
            error = event.get("error") or {}
            self._set_state(error=str(error.get("message") or error or "Gemini Live error"), status="Error")
            self._gemini_ready.set()
            return

        content = event.get("serverContent") or {}
        input_transcription = content.get("inputTranscription") or {}
        output_transcription = content.get("outputTranscription") or {}
        source_delta = str(input_transcription.get("text") or "")
        translation_delta = str(output_transcription.get("text") or "")
        if source_delta or translation_delta:
            with self._lock:
                if source_delta:
                    self.state["source_text"] = str(self.state.get("source_text") or "") + source_delta
                if translation_delta:
                    self.state["translation_text"] = str(self.state.get("translation_text") or "") + translation_delta
                    self.state["text"] = self.state["translation_text"]
                    self.state["status"] = "Translating"

    def _gemini_language_code(self, target_language: str | None) -> str:
        language = str(target_language or self.config.get("target_language") or "en").strip()
        if language.lower() in {"zh", "zh-tw", "chinese", "traditional chinese"}:
            return "zh-TW"
        return language
