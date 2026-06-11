from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import tempfile
import threading
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests
import websockets

HOST = os.environ.get("TODD_PIPELINE_HOST", "127.0.0.1")
PORT = int(os.environ.get("TODD_PIPELINE_PORT", "8765"))
WHISPER_MODEL = os.environ.get("TODD_WHISPER_MODEL", "openai/whisper-large-v3-turbo")
QWEN_MODEL = os.environ.get("TODD_QWEN_MODEL", "qwen3.5:4b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
GEMINI_MODEL = os.environ.get("TODD_GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_API_URL = os.environ.get("TODD_GEMINI_API_URL", "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent")


@dataclass
class SessionState:
    config: dict[str, Any] = field(default_factory=dict)
    chunks: list[bytes] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    @property
    def sample_rate(self) -> int:
        try:
            return int(self.config.get("sample_rate", 16000) or 16000)
        except (TypeError, ValueError):
            return 16000

    @property
    def channels(self) -> int:
        try:
            return max(1, int(self.config.get("channels", 1) or 1))
        except (TypeError, ValueError):
            return 1


class WhisperTranscriber:
    def __init__(self, model_id: str, device: str, dtype: str) -> None:
        self.model_id = model_id
        self.device_name = device
        self.dtype_name = dtype
        self._pipe: Any = None
        self._load_lock = threading.Lock()

    def _resolve_device(self) -> str:
        import torch

        if self.device_name == "auto":
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        return self.device_name

    def _resolve_dtype(self, device: str) -> Any:
        import torch

        if self.dtype_name == "auto":
            return torch.float16 if device.startswith("cuda") else torch.float32
        return {
            "float16": torch.float16,
            "float32": torch.float32,
            "bfloat16": torch.bfloat16,
        }[self.dtype_name]

    def load(self) -> None:
        if self._pipe is not None:
            return
        with self._load_lock:
            if self._pipe is not None:
                return

            try:
                from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
            except Exception as exc:
                raise RuntimeError(
                    "Local backend needs transformers, torch, and accelerate installed to use openai/whisper-large-v3-turbo."
                ) from exc

            device = self._resolve_device()
            torch_dtype = self._resolve_dtype(device)
            logging.info("Loading %s on %s with %s", self.model_id, device, torch_dtype)

            model_kwargs = {
                "torch_dtype": torch_dtype,
                "low_cpu_mem_usage": True,
                "use_safetensors": True,
                "attn_implementation": "sdpa",
            }
            try:
                model = AutoModelForSpeechSeq2Seq.from_pretrained(
                    self.model_id,
                    local_files_only=True,
                    **model_kwargs,
                )
                processor = AutoProcessor.from_pretrained(self.model_id, local_files_only=True)
            except Exception:
                model = AutoModelForSpeechSeq2Seq.from_pretrained(self.model_id, **model_kwargs)
                processor = AutoProcessor.from_pretrained(self.model_id)

            model.to(device)
            self._pipe = pipeline(
                "automatic-speech-recognition",
                model=model,
                tokenizer=processor.tokenizer,
                feature_extractor=processor.feature_extractor,
                torch_dtype=torch_dtype,
                device=device,
                chunk_length_s=25,
                batch_size=4,
                ignore_warning=True,
            )
            logging.info("Model loaded")

    def transcribe(self, wav_path: Path, language: str | None = None) -> str:
        self.load()
        assert self._pipe is not None

        generate_kwargs: dict[str, Any] = {"task": "transcribe"}
        if language:
            generate_kwargs["language"] = language

        result = self._pipe(str(wav_path), generate_kwargs=generate_kwargs)
        if isinstance(result, dict):
            return str(result.get("text", "")).strip()
        return str(result).strip()


class OllamaPostprocessor:
    def __init__(self, model: str, url: str, timeout: float, enabled: bool) -> None:
        self.model = model
        self.url = normalize_ollama_chat_url(url)
        self.timeout = timeout
        self.enabled = enabled

    def generate(self, system: str, user: str) -> str:
        if not self.enabled:
            return ""
        payload = {
            "model": self.model,
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 20,
                "min_p": 0.0,
                "presence_penalty": 1.5,
                "repeat_penalty": 1.0,
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        response = requests.post(self.url, json=payload, timeout=self.timeout)
        if response.status_code == 404:
            raise RuntimeError(f"Ollama model '{self.model}' was not found. Pull it with: ollama pull {self.model}")
        response.raise_for_status()
        data = response.json()
        message = data.get("message") or {}
        return strip_thinking(str(message.get("content") or "")).strip()

    def process(self, transcript: str, config: dict[str, Any]) -> tuple[str, float, str]:
        if not self.enabled or not transcript.strip():
            return transcript, 0.0, "disabled"

        started = time.time()
        try:
            if is_translate_session(config):
                target = str(config.get("target_language") or "en")
                target_instruction = target
                if target.lower() in {"zh", "zh-tw", "traditional chinese", "chinese"}:
                    target_instruction = "Traditional Chinese (Taiwan). Use Traditional Chinese characters only, not Simplified Chinese."
                system = (
                    "You are a transcript translation engine. Return only the translated text. "
                    "Do not answer the transcript, do not explain, do not add labels, and do not include thinking."
                )
                user = (
                    f"Translate this transcript to {target_instruction}. Keep names, product names, "
                    f"and technical terms accurate.\n\n<transcript>\n{transcript}\n</transcript>"
                )
                result = self.generate(system, user)
                mode = "translate"
            elif should_skip_gpt(config):
                return transcript, 0.0, "skipped"
            else:
                system = (
                    "You are a transcript cleanup engine for direct text insertion. "
                    "Fix obvious ASR mistakes, punctuation, casing, and spacing. Preserve the user's language. "
                    "If the transcript is Chinese, return Traditional Chinese characters for Taiwan only; do not use Simplified Chinese. "
                    "Do not answer the transcript. Do not summarize. Do not add new information. "
                    "Do not add labels. Return only the cleaned transcript text."
                )
                hotwords = str(config.get("hotwords") or "").strip()
                user = (
                    f"<transcript>\n{transcript}\n</transcript>\n\n"
                    f"<hotwords>\n{hotwords}\n</hotwords>\n\n"
                    "Return only the final cleaned text."
                )
                result = self.generate(system, user)
                mode = "polish"

            if not result:
                return transcript, round(time.time() - started, 3), f"{mode}:empty"
            return result, round(time.time() - started, 3), mode
        except Exception as exc:
            logging.exception("Ollama postprocess failed")
            return transcript, round(time.time() - started, 3), f"error:{exc}"


class GeminiTextPostprocessor:
    def __init__(self, model: str, api_url_template: str, timeout: float) -> None:
        self.model = model
        self.api_url_template = api_url_template
        self.timeout = timeout

    def generate(self, prompt: str, config: dict[str, Any]) -> str:
        api_key = gemini_api_key(config)
        if not api_key:
            raise RuntimeError("Enter a Gemini API key in Settings before using Gemini mode.")

        model = gemini_model(config) or self.model
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        }
        url = self.api_url_template.format(model=model)
        response = requests.post(
            url,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return gemini_response_text(response.json()).strip()

    def process(self, transcript: str, config: dict[str, Any]) -> tuple[str, float, str]:
        if not transcript.strip():
            return transcript, 0.0, "gemini:empty"
        if should_skip_gpt(config):
            return transcript, 0.0, "skipped"

        started = time.time()
        try:
            if is_translate_session(config):
                target = str(config.get("target_language") or "en")
                target_instruction = target
                if target.lower() in {"zh", "zh-tw", "traditional chinese", "chinese"}:
                    target_instruction = "Traditional Chinese (Taiwan). Use Traditional Chinese characters only, not Simplified Chinese."
                prompt = (
                    "You are a transcript translation engine. Return only the translated text. "
                    "Do not answer the transcript, do not explain, do not add labels, and do not include thinking.\n\n"
                    f"Translate this transcript to {target_instruction}. Keep names, product names, and technical terms accurate.\n\n"
                    f"<transcript>\n{transcript}\n</transcript>"
                )
                mode = "gemini_translate"
            else:
                hotwords = str(config.get("hotwords") or "").strip()
                prompt = (
                    "You are a transcript cleanup engine for direct text insertion. "
                    "Fix obvious ASR mistakes, punctuation, casing, and spacing. Preserve the user's language. "
                    "If the transcript is Chinese, return Traditional Chinese characters for Taiwan only; do not use Simplified Chinese. "
                    "Do not answer the transcript. Do not summarize. Do not add new information. "
                    "Do not add labels. Return only the cleaned transcript text.\n\n"
                    f"<transcript>\n{transcript}\n</transcript>\n\n"
                    f"<hotwords>\n{hotwords}\n</hotwords>\n\n"
                    "Return only the final cleaned text."
                )
                mode = "gemini_polish"

            result = self.generate(prompt, config)
            if not result:
                return transcript, round(time.time() - started, 3), f"{mode}:empty"
            return result, round(time.time() - started, 3), mode
        except Exception as exc:
            logging.exception("Gemini postprocess failed")
            return transcript, round(time.time() - started, 3), f"error:{exc}"


def strip_thinking(text: str) -> str:
    marker = "</think>"
    if marker in text:
        text = text.split(marker, 1)[1]
    return text.strip()


def gemini_api_key(config: dict[str, Any]) -> str:
    gemini = config.get("gemini")
    if isinstance(gemini, dict):
        key = str(gemini.get("api_key") or "").strip()
        if key:
            return key
    return os.environ.get("GEMINI_API_KEY", "").strip()


def gemini_model(config: dict[str, Any]) -> str:
    gemini = config.get("gemini")
    if isinstance(gemini, dict):
        model = str(gemini.get("model") or "").strip()
        if model:
            return model
    return GEMINI_MODEL


def gemini_response_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")
    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    text = "".join(str(part.get("text") or "") for part in parts)
    if not text.strip():
        raise RuntimeError("Gemini returned an empty response.")
    return text


def normalize_ollama_chat_url(url: str) -> str:
    value = (url or "http://127.0.0.1:11434").rstrip("/")
    if value.endswith("/api/chat"):
        return value
    if value.endswith("/api/generate"):
        return value.rsplit("/", 1)[0] + "/chat"
    return value + "/api/chat"


def should_skip_gpt(config: dict[str, Any]) -> bool:
    return bool(config.get("skip_gpt"))


def is_translate_session(config: dict[str, Any]) -> bool:
    if bool(config.get("translate")):
        return True
    target = config.get("target_language")
    return isinstance(target, str) and bool(target.strip())


def ai_provider(config: dict[str, Any]) -> str:
    provider = str(config.get("ai_provider") or "qwen").strip().lower()
    return "gemini" if provider == "gemini" else "qwen"


def sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    clean = dict(config)
    for key in ("gemini", "openai"):
        value = clean.get(key)
        if isinstance(value, dict):
            clean[key] = dict(value)
            if clean[key].get("api_key"):
                clean[key]["api_key"] = "***"
    return clean


def language_from_config(config: dict[str, Any]) -> str | None:
    language = config.get("language") or config.get("source_language")
    if isinstance(language, str) and language.strip():
        return language.strip()
    return None


def write_pcm_wav(path: Path, pcm: bytes, sample_rate: int, channels: int) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)


async def send_json(ws: websockets.ServerConnection, payload: dict[str, Any]) -> None:
    await ws.send(json.dumps(payload, ensure_ascii=False))


async def handle_client(
    ws: websockets.ServerConnection,
    transcriber: WhisperTranscriber,
    postprocessor: OllamaPostprocessor,
    gemini_processor: GeminiTextPostprocessor,
) -> None:
    session = SessionState()
    peer = getattr(ws, "remote_address", None)
    logging.info("Client connected: %s", peer)

    try:
        async for message in ws:
            if isinstance(message, bytes):
                session.chunks.append(message)
                continue

            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                await send_json(ws, {"type": "error", "message": "Invalid JSON message"})
                continue

            msg_type = payload.get("type")
            if msg_type == "hello":
                logging.info("Client hello: %s", payload)
                await send_json(ws, {"type": "hello_ok", "backend_version": "1.0.4"})
                continue

            if msg_type == "start":
                session = SessionState(config=dict(payload.get("config") or {}))
                logging.info("Session started: %s", sanitize_config(session.config))
                continue

            if msg_type == "warmup":
                await process_warmup(ws, transcriber)
                continue

            if msg_type == "stop":
                await process_stop(ws, transcriber, postprocessor, gemini_processor, session)
                session = SessionState()
                continue

            logging.debug("Ignoring message type: %s", msg_type)
    except websockets.ConnectionClosed:
        logging.info("Client disconnected: %s", peer)
    except Exception as exc:
        logging.exception("Client handler failed")
        try:
            await send_json(ws, {"type": "error", "message": str(exc)})
        except Exception:
            pass


async def process_stop(
    ws: websockets.ServerConnection,
    transcriber: WhisperTranscriber,
    postprocessor: OllamaPostprocessor,
    gemini_processor: GeminiTextPostprocessor,
    session: SessionState,
) -> None:
    started = time.time()
    pcm = b"".join(session.chunks)
    if not pcm:
        await send_json(ws, {"type": "error", "message": "No audio was received by the local backend."})
        await send_json(ws, {"type": "done", "total_elapsed": 0.0, "timing": {}})
        return

    with tempfile.NamedTemporaryFile(prefix="todd-transcript-", suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)

    try:
        write_pcm_wav(wav_path, pcm, session.sample_rate, session.channels)
        language = language_from_config(session.config)
        text = await asyncio.to_thread(transcriber.transcribe, wav_path, language)
        asr_elapsed = round(time.time() - started, 3)

        if ai_provider(session.config) == "gemini":
            final_text, gpt_elapsed, gpt_mode = await asyncio.to_thread(gemini_processor.process, text, session.config)
        else:
            final_text, gpt_elapsed, gpt_mode = await asyncio.to_thread(postprocessor.process, text, session.config)

        await send_json(ws, {"type": "asr_delta", "text": text})
        await send_json(
            ws,
            {
                "type": "asr_done",
                "text": text,
                "elapsed": asr_elapsed,
                "raw_json": {"model": transcriber.model_id},
            },
        )

        total_elapsed = round(time.time() - started, 3)

        await send_json(ws, {"type": "gpt_delta", "text": final_text})
        await send_json(ws, {"type": "gpt_done", "text": final_text, "elapsed": gpt_elapsed})
        await send_json(
            ws,
            {
                "type": "done",
                "total_elapsed": total_elapsed,
                "timing": {
                    "asr_elapsed": asr_elapsed,
                    "gpt_elapsed": gpt_elapsed,
                    "local_backend": True,
                    "gpt_mode": gpt_mode,
                },
            },
        )
        logging.info(
            "Processed %.2fs audio in %.2fs (asr=%.2fs, gpt=%.2fs, mode=%s)",
            len(pcm) / max(1, session.sample_rate * session.channels * 2),
            total_elapsed,
            asr_elapsed,
            gpt_elapsed,
            gpt_mode,
        )
    except Exception as exc:
        logging.exception("Transcription failed")
        await send_json(ws, {"type": "error", "message": f"Transcription failed: {exc}"})
        await send_json(
            ws,
            {
                "type": "done",
                "total_elapsed": round(time.time() - started, 3),
                "timing": {"local_backend": True},
            },
        )
    finally:
        try:
            wav_path.unlink(missing_ok=True)
        except Exception:
            pass


async def process_warmup(ws: websockets.ServerConnection, transcriber: WhisperTranscriber) -> None:
    started = time.time()
    try:
        await send_json(ws, {"type": "warmup_started"})
        await asyncio.to_thread(transcriber.load)
        await send_json(
            ws,
            {
                "type": "warmup_done",
                "elapsed": round(time.time() - started, 3),
                "model": transcriber.model_id,
            },
        )
    except Exception as exc:
        logging.exception("Warmup failed")
        await send_json(ws, {"type": "warmup_error", "message": str(exc)})


async def main_async(args: argparse.Namespace) -> None:
    transcriber = WhisperTranscriber(args.model, args.device, args.dtype)
    postprocessor = OllamaPostprocessor(
        args.ollama_model,
        args.ollama_url,
        args.ollama_timeout,
        not args.no_ollama,
    )
    gemini_processor = GeminiTextPostprocessor(args.gemini_model, args.gemini_api_url, args.gemini_timeout)

    async def handler(ws: websockets.ServerConnection) -> None:
        await handle_client(ws, transcriber, postprocessor, gemini_processor)

    async with websockets.serve(
        handler,
        args.host,
        args.port,
        max_size=None,
        ping_interval=20,
        ping_timeout=20,
    ):
        logging.info("Todd Transcript local backend listening on ws://%s:%s/ws/pipeline", args.host, args.port)
        await asyncio.Future()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local Whisper backend for Todd Transcript")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--model", default=WHISPER_MODEL)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda:0"], default=os.environ.get("TODD_WHISPER_DEVICE", "auto"))
    parser.add_argument("--dtype", choices=["auto", "float16", "float32", "bfloat16"], default=os.environ.get("TODD_WHISPER_DTYPE", "auto"))
    parser.add_argument("--ollama-model", default=QWEN_MODEL)
    parser.add_argument("--ollama-url", default=OLLAMA_URL)
    parser.add_argument("--ollama-timeout", type=float, default=float(os.environ.get("TODD_OLLAMA_TIMEOUT", "60")))
    parser.add_argument("--gemini-model", default=GEMINI_MODEL)
    parser.add_argument("--gemini-api-url", default=GEMINI_API_URL)
    parser.add_argument("--gemini-timeout", type=float, default=float(os.environ.get("TODD_GEMINI_TIMEOUT", "120")))
    parser.add_argument("--no-ollama", action="store_true")
    parser.add_argument("--log-level", default=os.environ.get("TODD_BACKEND_LOG_LEVEL", "INFO"))
    args, _unknown = parser.parse_known_args()
    return args


def main() -> None:
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
