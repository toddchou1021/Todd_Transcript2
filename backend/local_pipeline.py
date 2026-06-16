from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import logging
import os
import time
import wave
from dataclasses import dataclass, field
from typing import Any

import requests
import websockets

HOST = os.environ.get("TODD_PIPELINE_HOST", "127.0.0.1")
PORT = int(os.environ.get("TODD_PIPELINE_PORT", "8765"))
GEMINI_MODEL = os.environ.get("TODD_GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_API_URL = os.environ.get(
    "TODD_GEMINI_API_URL",
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
)
GEMINI_UPLOAD_URL = os.environ.get("TODD_GEMINI_UPLOAD_URL", "https://generativelanguage.googleapis.com/upload/v1beta/files")
GEMINI_FILE_URL = os.environ.get("TODD_GEMINI_FILE_URL", "https://generativelanguage.googleapis.com/v1beta/{name}")
INLINE_AUDIO_LIMIT_BYTES = 14 * 1024 * 1024
WAV_MIME_TYPE = "audio/wav"


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


class GeminiClient:
    def __init__(
        self,
        model: str,
        api_url_template: str,
        upload_url: str,
        file_url_template: str,
        timeout: float,
    ) -> None:
        self.model = model
        self.api_url_template = api_url_template
        self.upload_url = upload_url
        self.file_url_template = file_url_template
        self.timeout = timeout

    def generate_text(self, prompt: str, config: dict[str, Any]) -> str:
        return self._generate([{"text": prompt}], config)

    def generate_from_audio(self, wav_bytes: bytes, prompt: str, config: dict[str, Any]) -> str:
        if len(wav_bytes) <= INLINE_AUDIO_LIMIT_BYTES:
            parts = [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": WAV_MIME_TYPE,
                        "data": base64.b64encode(wav_bytes).decode("ascii"),
                    }
                },
            ]
            return self._generate(parts, config)

        file_info = self._upload_file(wav_bytes, config)
        try:
            parts = [
                {"text": prompt},
                {
                    "file_data": {
                        "mime_type": file_info.get("mimeType") or file_info.get("mime_type") or WAV_MIME_TYPE,
                        "file_uri": file_info["uri"],
                    }
                },
            ]
            return self._generate(parts, config)
        finally:
            self._delete_file(file_info, config)

    def _generate(self, parts: list[dict[str, Any]], config: dict[str, Any]) -> str:
        api_key = gemini_api_key(config)
        if not api_key:
            raise RuntimeError("Enter a Gemini API key in Settings before using Gemini mode.")

        model = gemini_model(config) or self.model
        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0.1,
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        }
        response = requests.post(
            self.api_url_template.format(model=model),
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return gemini_response_text(response.json()).strip()

    def _upload_file(self, wav_bytes: bytes, config: dict[str, Any]) -> dict[str, Any]:
        api_key = gemini_api_key(config)
        if not api_key:
            raise RuntimeError("Enter a Gemini API key in Settings before using Gemini mode.")
        metadata_response = requests.post(
            self.upload_url,
            headers={
                "x-goog-api-key": api_key,
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(len(wav_bytes)),
                "X-Goog-Upload-Header-Content-Type": WAV_MIME_TYPE,
                "Content-Type": "application/json",
            },
            json={"file": {"display_name": "Todd Transcript recording"}},
            timeout=self.timeout,
        )
        metadata_response.raise_for_status()
        upload_url = metadata_response.headers.get("x-goog-upload-url")
        if not upload_url:
            raise RuntimeError("Gemini Files API did not return an upload URL.")

        upload_response = requests.post(
            upload_url,
            headers={
                "Content-Length": str(len(wav_bytes)),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
            },
            data=wav_bytes,
            timeout=self.timeout,
        )
        upload_response.raise_for_status()
        file_info = (upload_response.json() or {}).get("file") or {}
        if not file_info.get("uri"):
            raise RuntimeError("Gemini Files API upload did not return a file URI.")
        return file_info

    def _delete_file(self, file_info: dict[str, Any], config: dict[str, Any]) -> None:
        name = str(file_info.get("name") or "").strip()
        if not name:
            return
        try:
            requests.delete(
                self.file_url_template.format(name=name),
                headers={"x-goog-api-key": gemini_api_key(config)},
                timeout=min(self.timeout, 30),
            )
        except Exception:
            logging.debug("Best-effort Gemini file cleanup failed", exc_info=True)


class GeminiAudioTranscriber:
    def __init__(self, client: GeminiClient) -> None:
        self.client = client
        self.model_id = client.model

    def transcribe(self, wav_bytes: bytes, config: dict[str, Any]) -> str:
        hotwords = str(config.get("hotwords") or "").strip()
        prompt = (
            "Generate a verbatim transcript of the speech in this audio. "
            "Return only the transcript text. Do not summarize, explain, label speakers, or translate. "
            "Preserve the spoken language. If the speech is Chinese, use Traditional Chinese characters for Taiwan only. "
            "Use the hotwords only as spelling hints for names, products, and technical terms.\n\n"
            f"<hotwords>\n{hotwords}\n</hotwords>"
        )
        return self.client.generate_from_audio(wav_bytes, prompt, config)


class GeminiTextPostprocessor:
    def __init__(self, client: GeminiClient) -> None:
        self.client = client

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

            result = self.client.generate_text(prompt, config)
            if not result:
                return transcript, round(time.time() - started, 3), f"{mode}:empty"
            return result, round(time.time() - started, 3), mode
        except Exception as exc:
            logging.exception("Gemini postprocess failed")
            return transcript, round(time.time() - started, 3), f"error:{exc}"


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


def should_skip_gpt(config: dict[str, Any]) -> bool:
    return bool(config.get("skip_gpt"))


def is_translate_session(config: dict[str, Any]) -> bool:
    if bool(config.get("translate")):
        return True
    target = config.get("target_language")
    return isinstance(target, str) and bool(target.strip())


def sanitize_config(config: dict[str, Any]) -> dict[str, Any]:
    clean = dict(config)
    value = clean.get("gemini")
    if isinstance(value, dict):
        clean["gemini"] = dict(value)
        if clean["gemini"].get("api_key"):
            clean["gemini"]["api_key"] = "***"
    return clean


def write_pcm_wav_bytes(pcm: bytes, sample_rate: int, channels: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


async def send_json(ws: websockets.ServerConnection, payload: dict[str, Any]) -> None:
    await ws.send(json.dumps(payload, ensure_ascii=False))


async def handle_client(
    ws: websockets.ServerConnection,
    transcriber: GeminiAudioTranscriber,
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
                await send_json(ws, {"type": "hello_ok", "backend_version": "1.0.6"})
                continue

            if msg_type == "start":
                session = SessionState(config=dict(payload.get("config") or {}))
                logging.info("Session started: %s", sanitize_config(session.config))
                continue

            if msg_type == "warmup":
                await process_warmup(ws, transcriber)
                continue

            if msg_type == "stop":
                await process_stop(ws, transcriber, gemini_processor, session)
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
    transcriber: GeminiAudioTranscriber,
    gemini_processor: GeminiTextPostprocessor,
    session: SessionState,
) -> None:
    started = time.time()
    pcm = b"".join(session.chunks)
    if not pcm:
        await send_json(ws, {"type": "error", "message": "No audio was received by the local backend."})
        await send_json(ws, {"type": "done", "total_elapsed": 0.0, "timing": {}})
        return

    try:
        wav_bytes = write_pcm_wav_bytes(pcm, session.sample_rate, session.channels)
        text = await asyncio.to_thread(transcriber.transcribe, wav_bytes, session.config)
        asr_elapsed = round(time.time() - started, 3)

        final_text, gpt_elapsed, gpt_mode = await asyncio.to_thread(gemini_processor.process, text, session.config)

        await send_json(ws, {"type": "asr_delta", "text": text})
        await send_json(
            ws,
            {
                "type": "asr_done",
                "text": text,
                "elapsed": asr_elapsed,
                "raw_json": {"model": transcriber.model_id, "provider": "gemini"},
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
                    "asr_mode": "gemini_audio",
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


async def process_warmup(ws: websockets.ServerConnection, transcriber: GeminiAudioTranscriber) -> None:
    started = time.time()
    await send_json(ws, {"type": "warmup_started"})
    await send_json(
        ws,
        {
            "type": "warmup_done",
            "elapsed": round(time.time() - started, 3),
            "model": transcriber.model_id,
            "provider": "gemini",
        },
    )


async def main_async(args: argparse.Namespace) -> None:
    gemini_client = GeminiClient(
        args.gemini_model,
        args.gemini_api_url,
        args.gemini_upload_url,
        args.gemini_file_url,
        args.gemini_timeout,
    )
    transcriber = GeminiAudioTranscriber(gemini_client)
    gemini_processor = GeminiTextPostprocessor(gemini_client)

    async def handler(ws: websockets.ServerConnection) -> None:
        await handle_client(ws, transcriber, gemini_processor)

    async with websockets.serve(
        handler,
        args.host,
        args.port,
        max_size=None,
        ping_interval=20,
        ping_timeout=20,
    ):
        logging.info("Todd Transcript Gemini backend listening on ws://%s:%s/ws/pipeline", args.host, args.port)
        await asyncio.Future()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Gemini backend for Todd Transcript")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--gemini-model", default=GEMINI_MODEL)
    parser.add_argument("--gemini-api-url", default=GEMINI_API_URL)
    parser.add_argument("--gemini-upload-url", default=GEMINI_UPLOAD_URL)
    parser.add_argument("--gemini-file-url", default=GEMINI_FILE_URL)
    parser.add_argument("--gemini-timeout", type=float, default=float(os.environ.get("TODD_GEMINI_TIMEOUT", "120")))
    parser.add_argument("--log-level", default=os.environ.get("TODD_BACKEND_LOG_LEVEL", "INFO"))
    args, _unknown = parser.parse_known_args()
    return args


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
