from __future__ import annotations

import io
import math
import subprocess
import sys
import threading
import time
import wave
from array import array
from pathlib import Path
from typing import Callable

import pyaudio

from .paths import HELPER_PATH


class AudioRecorder:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, input_mode: str = "microphone"):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)
        self.input_mode = input_mode
        self.chunk_frames = 1024
        self._running = False
        self._thread: threading.Thread | None = None
        self._frames: list[bytes] = []
        self._chunk_callback: Callable[[bytes], None] | None = None
        self._level_callback: Callable[[float], None] | None = None
        self._started_at = 0.0
        self._helper: subprocess.Popen | None = None

    def set_chunk_callback(self, callback: Callable[[bytes], None] | None) -> None:
        self._chunk_callback = callback

    def set_level_callback(self, callback: Callable[[float], None] | None) -> None:
        self._level_callback = callback

    def start(self) -> None:
        if self._running:
            return
        self._frames = []
        self._running = True
        self._started_at = time.time()
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()

    def stop(self) -> bytes:
        if not self._running:
            return self.to_wav()
        self._running = False
        if self._helper:
            self._helper.terminate()
        if self._thread:
            self._thread.join(timeout=3)
        return self.to_wav()

    def duration(self) -> float:
        if self._started_at <= 0:
            return 0.0
        if self._running:
            return time.time() - self._started_at
        total_frames = sum(len(frame) for frame in self._frames) / 2 / max(1, self.channels)
        return total_frames / float(self.sample_rate)

    def is_recording(self) -> bool:
        return self._running

    def to_wav(self) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(self.channels)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(b"".join(self._frames))
        return buf.getvalue()

    def _emit(self, chunk: bytes) -> None:
        if not chunk:
            return
        self._frames.append(chunk)
        if self._level_callback:
            self._level_callback(_pcm_level(chunk))
        if self._chunk_callback:
            self._chunk_callback(chunk)

    def _record_loop(self) -> None:
        if self.input_mode in {"system_audio", "both"}:
            self._record_from_helper()
        else:
            self._record_microphone()

    def _record_microphone(self) -> None:
        audio = pyaudio.PyAudio()
        stream = None
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_frames,
            )
            while self._running:
                self._emit(stream.read(self.chunk_frames, exception_on_overflow=False))
        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            audio.terminate()

    def _record_from_helper(self) -> None:
        helper_cmd = [str(HELPER_PATH)] if getattr(sys, "frozen", False) else [sys.executable, str(HELPER_PATH)]
        if not Path(HELPER_PATH).exists():
            raise FileNotFoundError(f"Audio helper not found: {HELPER_PATH}")
        mode = "both" if self.input_mode == "both" else "system"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._helper = subprocess.Popen(
            helper_cmd
            + [
                "--mode",
                mode,
                "--sample-rate",
                str(self.sample_rate),
                "--chunk",
                str(self.chunk_frames),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        try:
            assert self._helper.stdout is not None
            bytes_per_chunk = self.chunk_frames * 2
            while self._running:
                chunk = self._helper.stdout.read(bytes_per_chunk)
                if not chunk:
                    break
                self._emit(chunk)
        finally:
            if self._helper and self._helper.poll() is None:
                self._helper.terminate()
            self._helper = None


def _pcm_level(chunk: bytes) -> float:
    if len(chunk) < 2:
        return 0.0
    samples = array("h")
    samples.frombytes(chunk[: len(chunk) - (len(chunk) % 2)])
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return 0.0
    step = max(1, len(samples) // 512)
    selected = samples[::step]
    mean_square = sum(float(s) * float(s) for s in selected) / len(selected)
    rms = math.sqrt(mean_square)
    return min(1.0, rms / 12000.0)
