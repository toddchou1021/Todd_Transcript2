from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import requests
from websockets.asyncio.server import serve

HOST = os.environ.get("TODD_PIPELINE_HOST", "127.0.0.1")
PORT = int(os.environ.get("TODD_PIPELINE_PORT", "8765"))
WHISPER_MODEL = os.environ.get("TODD_WHISPER_MODEL", "openai/whisper-large-v3-turbo")
QWEN_MODEL = os.environ.get("TODD_QWEN_MODEL", "qwen3.5:4b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
_ASR_MODEL: Any = None
_ASR_PROCESSOR: Any = None
_ASR_DEVICE: str | None = None
_ASR_DTYPE: Any = None


async def _send(ws, payload: dict[str, Any]) -> None:
    await ws.send(json.dumps(payload, ensure_ascii=False))


async def handle_pipeline(ws) -> None:
    session: dict[str, Any] = {}
    chunks: list[bytes] = []
    started_at = time.time()

    async for raw in ws:
        if isinstance(raw, bytes):
            chunks.append(raw)
            continue

        try:
            msg = json.loads(raw)
        except Exception:
            continue

        kind = msg.get("type")
        if kind == "hello":
            await _send(ws, {"type": "hello_ok", "backend_version": "1.0.1"})
        elif kind == "start":
            session = msg.get("config") or {}
            chunks.clear()
            started_at = time.time()
        elif kind == "stop":
            await process_session(ws, session, chunks, started_at)
            chunks.clear()


async def process_session(ws, config: dict[str, Any], chunks: list[bytes], started_at: float) -> None:
    sample_rate = int(config.get("sample_rate", 16000) or 16000)
    channels = int(config.get("channels", 1) or 1)
    pcm = b"".join(chunks)

    if not pcm:
        await _send(ws, {"type": "error", "message": "No audio was received by the local backend."})
        await _send(ws, {"type": "done", "total_elapsed": round(time.time() - started_at, 3)})
        return

    wav_path = _write_wav(pcm, sample_rate, channels)
    try:
        asr_started = time.time()
        transcript = await asyncio.to_thread(_transcribe, wav_path, config)
        asr_elapsed = time.time() - asr_started
        await _send(ws, {"type": "asr_done", "text": transcript, "elapsed": round(asr_elapsed, 3)})

        final_text = transcript
        gpt_elapsed = 0.0
        if transcript and not config.get("skip_gpt"):
            gpt_started = time.time()
            final_text = await asyncio.to_thread(_postprocess, transcript, config)
            gpt_elapsed = time.time() - gpt_started
            await _send(ws, {"type": "gpt_done", "text": final_text, "elapsed": round(gpt_elapsed, 3)})

        await _send(
            ws,
            {
                "type": "done",
                "total_elapsed": round(time.time() - started_at, 3),
                "asr_elapsed": round(asr_elapsed, 3),
                "gpt_elapsed": round(gpt_elapsed, 3),
            },
        )
    except Exception as exc:
        await _send(ws, {"type": "error", "message": str(exc)})
        await _send(ws, {"type": "done", "total_elapsed": round(time.time() - started_at, 3)})
    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass


def _write_wav(pcm: bytes, sample_rate: int, channels: int) -> Path:
    handle = tempfile.NamedTemporaryFile(prefix="todd-transcript-", suffix=".wav", delete=False)
    path = Path(handle.name)
    handle.close()
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm)
    return path


def _transcribe(path: Path, config: dict[str, Any]) -> str:
    try:
        import numpy as np
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    except Exception as exc:
        raise RuntimeError(
            "Local backend needs torch and transformers installed to use openai/whisper-large-v3-turbo."
        ) from exc

    global _ASR_MODEL, _ASR_PROCESSOR, _ASR_DEVICE, _ASR_DTYPE
    if _ASR_MODEL is None or _ASR_PROCESSOR is None:
        device_setting = os.environ.get("TODD_WHISPER_DEVICE", "auto").lower()
        if device_setting == "auto":
            _ASR_DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            _ASR_DEVICE = device_setting
        _ASR_DTYPE = torch.float16 if str(_ASR_DEVICE).startswith("cuda") else torch.float32
        try:
            _ASR_PROCESSOR = AutoProcessor.from_pretrained(WHISPER_MODEL, local_files_only=True)
            _ASR_MODEL = AutoModelForSpeechSeq2Seq.from_pretrained(
                WHISPER_MODEL,
                torch_dtype=_ASR_DTYPE,
                low_cpu_mem_usage=True,
                use_safetensors=True,
                local_files_only=True,
            ).to(_ASR_DEVICE)
        except Exception:
            _ASR_PROCESSOR = AutoProcessor.from_pretrained(WHISPER_MODEL)
            _ASR_MODEL = AutoModelForSpeechSeq2Seq.from_pretrained(
                WHISPER_MODEL,
                torch_dtype=_ASR_DTYPE,
                low_cpu_mem_usage=True,
                use_safetensors=True,
            ).to(_ASR_DEVICE)
        _ASR_MODEL.eval()

    language = (config.get("source_language") or "").strip() or None
    audio, sample_rate = _read_wav_float32(path, np)
    inputs = _ASR_PROCESSOR(audio, sampling_rate=sample_rate, return_tensors="pt")
    input_features = inputs.input_features.to(_ASR_DEVICE, dtype=_ASR_DTYPE)
    generate_kwargs: dict[str, Any] = {"max_new_tokens": 256}
    if language:
        generate_kwargs["language"] = language
    with torch.inference_mode():
        predicted_ids = _ASR_MODEL.generate(input_features, **generate_kwargs)
    return _ASR_PROCESSOR.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()


def _read_wav_float32(path: Path, np) -> tuple[Any, int]:
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if sample_width != 2:
        raise RuntimeError(f"Unsupported WAV sample width: {sample_width}")
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio, sample_rate


def _postprocess(transcript: str, config: dict[str, Any]) -> str:
    translate = bool(config.get("translate"))
    target_language = str(config.get("target_language") or "zh")
    if translate:
        prompt = (
            f"Translate the transcript into {target_language}. Preserve names and technical terms. "
            f"Return only the translation.\n\nTranscript:\n{transcript}"
        )
    else:
        prompt = (
            "Clean up punctuation and obvious speech-recognition errors in this transcript. "
            "Do not summarize. Return only the corrected transcript.\n\n"
            f"Transcript:\n{transcript}"
        )

    response = requests.post(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        json={"model": QWEN_MODEL, "prompt": prompt, "stream": False, "think": False},
        timeout=300,
    )
    if response.status_code == 404:
        raise RuntimeError(f"Ollama model '{QWEN_MODEL}' was not found. Pull it with: ollama pull {QWEN_MODEL}")
    response.raise_for_status()
    data = response.json()
    return str(data.get("response") or "").strip() or transcript


async def _main() -> None:
    async with serve(handle_pipeline, HOST, PORT, max_size=None):
        await asyncio.Future()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
