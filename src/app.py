from __future__ import annotations

import os
import threading
import time
import traceback
import ctypes
from datetime import datetime
from typing import Any

import keyboard
import webview

from . import APP_NAME, APP_VERSION
from .audio_recorder import AudioRecorder
from .config import ConfigStore
from .history import HistoryManager
from .hotwords import HotwordsManager
from .input_sender import copy_text, paste_text
from .pipeline import PipelineClient
from .realtime import RealtimeASRController, RealtimeTranslateController
from .tray import TrayController
from .ui.realtime_windows import REALTIME_ASR_HTML, REALTIME_COMBINED_HTML, REALTIME_TRANSLATE_HTML
from .ui.settings import SettingsWindow
from .ui.status_overlay import RecordingOverlay
from .paths import ICON_PATH


class ToddTranscriptApp:
    def __init__(self):
        self.config = ConfigStore()
        self.history = HistoryManager(self.config.resolve(self.config.get("history_file")))
        self.hotwords = HotwordsManager(self.config.resolve(self.config.get("hotwords_file")))
        self.status = "Idle"
        self.error = ""
        self._lock = threading.RLock()
        self._recording = False
        self._recording_mode = ""
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._recorder: AudioRecorder | None = None
        self._pipeline: PipelineClient | None = None
        self._warmup_pipeline: PipelineClient | None = None
        self._warmup_thread: threading.Thread | None = None
        self._hotkey_handles: list[int] = []
        self.overlay = RecordingOverlay()
        self.realtime_asr = RealtimeASRController(self.config.data)
        self.realtime_translate = RealtimeTranslateController(self.config.data)
        self._realtime_asr_window = None
        self._realtime_translate_window = None
        self._realtime_combined_window = None
        self._settings_window: SettingsWindow | None = None
        self._tray = TrayController(ICON_PATH, self.show_main_window, self.exit_app)
        self._exiting = False
        self._warming_up = False

    def run(self) -> None:
        self._set_windows_app_id()
        self._register_hotkeys()
        self.overlay.start()
        self._tray.start()
        self.start_backend_warmup()
        try:
            self._settings_window = SettingsWindow(AppAPI(self), on_closing=self._on_main_window_closing)
            self._settings_window.start()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self._tray.stop()
        self._warming_up = False
        if self._warmup_pipeline:
            self._warmup_pipeline.close()
        self.stop_recording()
        self.realtime_asr.stop()
        self.realtime_translate.stop()
        self.overlay.destroy()
        for handle in self._hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._hotkey_handles.clear()

    def _set_windows_app_id(self) -> None:
        if os.name != "nt":
            return
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ToddTranscript.App")
        except Exception:
            pass

    def show_main_window(self) -> None:
        window = self._settings_window.window if self._settings_window else None
        if not window:
            return
        try:
            window.show()
            window.restore()
        except Exception:
            pass

    def exit_app(self) -> None:
        self._exiting = True
        try:
            self._tray.stop()
        except Exception:
            pass
        for window in (self._realtime_asr_window, self._realtime_translate_window, self._realtime_combined_window):
            if window:
                try:
                    window.destroy()
                except Exception:
                    pass
        window = self._settings_window.window if self._settings_window else None
        if window:
            try:
                window.destroy()
            except Exception:
                pass

    def _on_main_window_closing(self):
        if self._exiting:
            return True
        window = self._settings_window.window if self._settings_window else None
        if window:
            try:
                window.hide()
            except Exception:
                pass
        return False

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "recording": self._recording,
                "mode": self._recording_mode,
                "status": self.status,
                "error": self.error,
            }

    def start_backend_warmup(self) -> None:
        if self._warmup_thread and self._warmup_thread.is_alive():
            return
        self._warmup_thread = threading.Thread(target=self._warmup_worker, daemon=True)
        self._warmup_thread.start()

    def _warmup_worker(self) -> None:
        with self._lock:
            if self._recording or self._exiting:
                return
            self._warming_up = True
            self.error = ""
            self.status = "App Warming Up"
        try:
            cfg = self.config.data
            client = PipelineClient(
                str(cfg.get("pipeline_api", {}).get("url", "ws://127.0.0.1:8765/ws/pipeline")),
                int(cfg.get("pipeline_api", {}).get("timeout", 300)),
            )
            self._warmup_pipeline = client
            client.connect(APP_VERSION, "warmup")
            client.warmup(wait_timeout=int(cfg.get("pipeline_api", {}).get("timeout", 300)))
            if client.error:
                self._set_error(client.error)
        except Exception as exc:
            self._set_error(f"Warmup failed: {exc}")
        finally:
            if self._warmup_pipeline:
                self._warmup_pipeline.close()
            self._warmup_pipeline = None
            with self._lock:
                self._warming_up = False
                if not self._recording and not self.error:
                    self.status = "Idle"

    def reload_managers(self) -> None:
        self.history = HistoryManager(self.config.resolve(self.config.get("history_file")))
        self.hotwords = HotwordsManager(self.config.resolve(self.config.get("hotwords_file")))

    def save_hotkey(self, mode: str, combo: str) -> dict[str, Any]:
        key = "transcribe" if mode in {"hold", "transcribe"} else "translate"
        self.config.set(f"hotkey.{key}", combo)
        self._register_hotkeys()
        return self.config.public_config()

    def start_recording(self, mode: str) -> dict[str, Any]:
        mode = "translate" if mode == "translate" else "transcribe"
        with self._lock:
            if self._recording:
                return {"ok": False, "error": "Recording is already running."}
            self._warming_up = False
            self._recording = True
            self._recording_mode = mode
            self._stop_event.clear()
            self.error = ""
            self.status = f"Recording {mode}"
        self._worker = threading.Thread(target=self._record_worker, args=(mode,), daemon=True)
        self._worker.start()
        return {"ok": True}

    def stop_recording(self) -> dict[str, Any]:
        with self._lock:
            if not self._recording:
                return {"ok": True}
            self.status = "Stopping"
            self._stop_event.set()
        return {"ok": True}

    def _record_worker(self, mode: str) -> None:
        audio_duration = 0.0
        try:
            cfg = self.config.data
            recorder_cfg = cfg.get("recorder", {})
            sample_rate = int(recorder_cfg.get("sample_rate", 16000))
            channels = int(recorder_cfg.get("channels", 1))
            input_mode = str(recorder_cfg.get("input_mode", "microphone"))

            client = PipelineClient(
                str(cfg.get("pipeline_api", {}).get("url", "ws://127.0.0.1:8765/ws/pipeline")),
                int(cfg.get("pipeline_api", {}).get("timeout", 300)),
            )
            self._pipeline = client
            client.on_error = self._set_error
            client.on_asr_delta = lambda text: self._set_status("Receiving transcript")
            client.on_asr_done = lambda text: self._set_status("Processing")
            client.on_gpt_delta = lambda text: self._set_status("Receiving final text")
            client.on_gpt_done = lambda text: self._set_status("Finalizing")
            client.on_done = lambda: self._set_status("Done")

            self._set_status("Connecting backend")
            client.connect(APP_VERSION, "developer")
            client.start_session(self._pipeline_config(mode, sample_rate, channels, input_mode))

            self._recorder = AudioRecorder(sample_rate=sample_rate, channels=channels, input_mode=input_mode)
            self._recorder.set_chunk_callback(client.send_audio_chunk)
            self._recorder.set_level_callback(self.overlay.update_level)
            self._set_status(f"Recording {mode}")
            self.overlay.show(mode)
            self._recorder.start()

            while not self._stop_event.wait(0.05):
                pass

            self._set_status("Stopping audio")
            self._recorder.stop()
            audio_duration = self._recorder.duration()

            self._set_status("Waiting for backend")
            client.stop_session(wait_timeout=int(cfg.get("pipeline_api", {}).get("timeout", 300)))
            final_text = client.gpt_text or client.asr_text
            if final_text:
                paste_text(final_text)
                self.history.add(
                    mode=mode,
                    audio_duration=audio_duration,
                    asr_text=client.asr_text,
                    final_text=final_text,
                    elapsed={
                        "asr": client.asr_elapsed,
                        "gpt": client.gpt_elapsed,
                        "total": client.total_elapsed,
                    },
                )
                self._set_status("Inserted text")
            elif client.error:
                self._set_error(client.error)
            else:
                self._set_status("No text returned")
        except Exception as exc:
            self._set_error(f"{exc}")
            traceback.print_exc()
        finally:
            self.overlay.hide()
            if self._pipeline:
                self._pipeline.close()
            with self._lock:
                self._recording = False
                self._recording_mode = ""
                if not self.error:
                    self.status = "Idle"
            self._recorder = None
            self._pipeline = None

    def _pipeline_config(self, mode: str, sample_rate: int, channels: int, input_mode: str) -> dict[str, Any]:
        config = {
            "mode": mode,
            "translate": mode == "translate",
            "postprocess": self.config.get("postprocess", True),
            "skip_gpt": bool(mode != "translate" and self.config.get("postprocess", True) is False),
            "ai_provider": self.config.get("ai_provider", "qwen"),
            "gemini": {
                "api_key": self.config.get("gemini.api_key", ""),
                "model": self.config.get("gemini.model", "gemini-3.1-flash-lite"),
            },
            "hotwords": "\n".join(self.hotwords.get_all()),
            "sample_rate": sample_rate,
            "channels": channels,
            "input_mode": input_mode,
            "qwen_thinking": False,
            "think": False,
        }
        if mode == "translate":
            config["target_language"] = self.config.get("target_language", "zh")
        return config

    def _set_status(self, message: str) -> None:
        with self._lock:
            if self._warming_up and not self._recording and message != "App Warming Up":
                return
            self.status = message
        self.overlay.set_status(message)

    def _set_error(self, message: str) -> None:
        with self._lock:
            self.error = message
            self.status = "Error"

    def _register_hotkeys(self) -> None:
        for handle in self._hotkey_handles:
            try:
                keyboard.remove_hotkey(handle)
            except Exception:
                pass
        self._hotkey_handles.clear()
        hotkeys = self.config.get("hotkey", {})
        bindings = {
            hotkeys.get("transcribe"): lambda: self.start_recording("transcribe"),
            hotkeys.get("translate"): lambda: self.start_recording("translate"),
            "esc": self.stop_recording,
        }
        for combo, callback in bindings.items():
            if not combo:
                continue
            try:
                self._hotkey_handles.append(keyboard.add_hotkey(combo, callback, suppress=False))
            except Exception as exc:
                self._set_error(f"Could not register hotkey {combo}: {exc}")


class AppAPI:
    def __init__(self, app: ToddTranscriptApp):
        self.app = app

    def get_config(self) -> dict[str, Any]:
        return self.app.config.public_config()

    def set_config(self, key: str, value: Any) -> dict[str, Any]:
        cfg = self.app.config.set(key, value)
        self.app.realtime_asr.update_config(self.app.config.data)
        self.app.realtime_translate.update_config(self.app.config.data)
        if key in {"history_file", "hotwords_file"}:
            self.app.reload_managers()
        if key.startswith("hotkey."):
            self.app._register_hotkeys()
        if key == "openai.api_key" and value:
            os.environ["OPENAI_API_KEY"] = str(value)
        if key == "gemini.api_key" and value:
            os.environ["GEMINI_API_KEY"] = str(value)
        return cfg

    def save_hotkey(self, mode: str, combo: str) -> dict[str, Any]:
        return self.app.save_hotkey(mode, combo)

    def start_recording(self, mode: str) -> dict[str, Any]:
        return self.app.start_recording(mode)

    def stop_recording(self) -> dict[str, Any]:
        return self.app.stop_recording()

    def get_status(self) -> dict[str, Any]:
        return self.app.get_status()

    def get_stats(self) -> dict[str, int]:
        return self.app.history.stats()

    def get_history_page(self, page: int = 0) -> dict[str, Any]:
        return self.app.history.page(int(page))

    def delete_history_by_ts(self, timestamp: str) -> dict[str, Any]:
        self.app.history.delete_by_ts(timestamp)
        return {"ok": True}

    def clear_history(self) -> dict[str, Any]:
        self.app.history.clear()
        return {"ok": True}

    def get_hotwords(self) -> list[str]:
        return self.app.hotwords.get_all()

    def add_hotword(self, word: str) -> list[str]:
        return self.app.hotwords.add(word)

    def remove_hotword(self, word: str) -> list[str]:
        return self.app.hotwords.remove(word)

    def copy_text(self, text: str) -> dict[str, Any]:
        copy_text(text)
        return {"ok": True}

    def open_realtime_asr(self) -> dict[str, Any]:
        try:
            if self.app._realtime_asr_window:
                self.app._realtime_asr_window.show()
                return {"ok": True}
            self.app._realtime_asr_window = webview.create_window(
                "Realtime ASR",
                html=REALTIME_ASR_HTML,
                js_api=self,
                width=900,
                height=640,
                min_size=(720, 520),
                background_color="#121314",
                text_select=True,
            )
            self.app._realtime_asr_window.events.closing += self._on_realtime_asr_closing
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def open_realtime_translate(self) -> dict[str, Any]:
        try:
            if self.app._realtime_translate_window:
                self.app._realtime_translate_window.show()
                return {"ok": True}
            self.app._realtime_translate_window = webview.create_window(
                "Realtime Translate",
                html=REALTIME_TRANSLATE_HTML,
                js_api=self,
                width=960,
                height=640,
                min_size=(780, 520),
                background_color="#121314",
                text_select=True,
            )
            self.app._realtime_translate_window.events.closing += self._on_realtime_translate_closing
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def open_realtime_combined(self) -> dict[str, Any]:
        try:
            if self.app._realtime_combined_window:
                self.app._realtime_combined_window.show()
                return {"ok": True}
            self.app._realtime_combined_window = webview.create_window(
                "Realtime ASR + Translate",
                html=REALTIME_COMBINED_HTML,
                js_api=self,
                width=980,
                height=760,
                min_size=(820, 640),
                background_color="#121314",
                text_select=True,
            )
            self.app._realtime_combined_window.events.closing += self._on_realtime_combined_closing
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _on_realtime_asr_closing(self):
        self.app.realtime_asr.stop()
        self.app._realtime_asr_window = None

    def _on_realtime_translate_closing(self):
        self.app.realtime_translate.stop()
        self.app._realtime_translate_window = None

    def _on_realtime_combined_closing(self):
        self.app.realtime_asr.stop()
        self.app.realtime_translate.stop()
        self.app._realtime_combined_window = None

    def start_realtime_asr(self, input_mode: str) -> dict[str, Any]:
        return self.app.realtime_asr.start(input_mode)

    def stop_realtime_asr(self) -> dict[str, Any]:
        return self.app.realtime_asr.stop()

    def get_realtime_asr_status(self) -> dict[str, Any]:
        return self.app.realtime_asr.get_status()

    def clear_realtime_asr(self) -> dict[str, Any]:
        self.app.realtime_asr.clear_text()
        return {"ok": True}

    def save_realtime_asr(self) -> dict[str, Any]:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        result = self.app.realtime_asr.save_markdown(f"{stamp}_asr.md")
        if result.get("ok"):
            text = self.app.realtime_asr.get_text().strip()
            status = self.app.realtime_asr.get_status()
            record = self.app.history.add(
                mode="realtime_asr",
                audio_duration=float(status.get("audio_duration") or 0),
                asr_text=text,
                final_text=text,
                elapsed={"total": float(status.get("audio_duration") or 0)},
            )
            result["history_timestamp"] = record.get("timestamp", "")
        return result

    def start_realtime_translate(self, input_mode: str, target_language: str) -> dict[str, Any]:
        self.app.config.set("target_language", target_language)
        self.app.realtime_translate.update_config(self.app.config.data)
        return self.app.realtime_translate.start(input_mode, target_language)

    def stop_realtime_translate(self) -> dict[str, Any]:
        return self.app.realtime_translate.stop()

    def get_realtime_translate_status(self) -> dict[str, Any]:
        return self.app.realtime_translate.get_status()

    def clear_realtime_translate(self) -> dict[str, Any]:
        self.app.realtime_translate.clear_text()
        return {"ok": True}

    def save_realtime_translate(self) -> dict[str, Any]:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        result = self.app.realtime_translate.save_markdown(f"{stamp}_translation.md")
        if result.get("ok"):
            status = self.app.realtime_translate.get_status()
            text = self.app.realtime_translate.get_text().strip()
            source_text = str(status.get("source_text") or "").strip()
            record = self.app.history.add(
                mode="realtime_translate",
                audio_duration=float(status.get("audio_duration") or 0),
                asr_text=source_text,
                final_text=text,
                elapsed={"total": float(status.get("audio_duration") or 0)},
            )
            result["history_timestamp"] = record.get("timestamp", "")
        return result

    def start_realtime_combined(self, input_mode: str, target_language: str) -> dict[str, Any]:
        asr_result = self.start_realtime_asr(input_mode)
        if not asr_result.get("ok"):
            return asr_result
        translate_result = self.start_realtime_translate(input_mode, target_language)
        if not translate_result.get("ok"):
            self.stop_realtime_asr()
            return translate_result
        return {"ok": True}

    def stop_realtime_combined(self) -> dict[str, Any]:
        self.stop_realtime_asr()
        self.stop_realtime_translate()
        return {"ok": True}

    def get_realtime_combined_status(self) -> dict[str, Any]:
        asr = self.get_realtime_asr_status()
        translate = self.get_realtime_translate_status()
        errors = [str(value) for value in (asr.get("error"), translate.get("error")) if value]
        return {"asr": asr, "translate": translate, "error": " | ".join(errors)}

    def clear_realtime_combined(self) -> dict[str, Any]:
        self.clear_realtime_asr()
        self.clear_realtime_translate()
        return {"ok": True}

    def save_realtime_combined(self) -> dict[str, Any]:
        paths: list[str] = []
        errors: list[str] = []
        asr_result = self.save_realtime_asr()
        if asr_result.get("ok") and asr_result.get("path"):
            paths.append(str(asr_result["path"]))
        elif asr_result.get("error"):
            errors.append(str(asr_result["error"]))
        translate_result = self.save_realtime_translate()
        if translate_result.get("ok") and translate_result.get("path"):
            paths.append(str(translate_result["path"]))
        elif translate_result.get("error"):
            errors.append(str(translate_result["error"]))
        if not paths:
            return {"ok": False, "error": " | ".join(errors) or "Nothing to save."}
        return {"ok": True, "paths": paths}
