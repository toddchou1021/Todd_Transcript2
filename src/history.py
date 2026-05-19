from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class HistoryManager:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._save([])

    def _load(self) -> list[dict[str, Any]]:
        raw = self.path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            records: list[dict[str, Any]] = []
            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if isinstance(item, dict):
                    records.append(item)
            return records

    def _save(self, records: list[dict[str, Any]]) -> None:
        self.path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(
        self,
        *,
        mode: str,
        audio_duration: float,
        asr_text: str,
        final_text: str,
        elapsed: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "audio_duration": round(audio_duration, 3),
            "elapsed": elapsed or {},
            "asr": {"concatenated_text": asr_text or ""},
            "gpt": {"text": final_text or "", "raw_response": None},
            "gpt_prompt": "(pipeline mode)",
        }
        records = self._load()
        records.append(record)
        self._save(records[-500:])
        return record

    def all(self) -> list[dict[str, Any]]:
        return list(reversed(self._load()))

    def page(self, page: int, page_size: int = 20) -> dict[str, Any]:
        records = self.all()
        start = max(0, page) * page_size
        chunk = records[start : start + page_size]
        return {"records": [self._flatten(r) for r in chunk], "has_more": start + page_size < len(records)}

    def clear(self) -> None:
        self._save([])

    def delete_by_ts(self, timestamp: str) -> None:
        self._save([r for r in self._load() if r.get("timestamp") != timestamp])

    def stats(self) -> dict[str, int]:
        today = datetime.now().strftime("%Y-%m-%d")
        total_words = today_words = total_count = today_count = 0
        for record in self._load():
            text = self._flatten(record)["final_text"]
            count = len(text.split()) if text and text.isascii() else len(text.replace(" ", ""))
            total_words += count
            total_count += 1
            if str(record.get("timestamp", "")).startswith(today):
                today_words += count
                today_count += 1
        return {
            "today_words": today_words,
            "today_count": today_count,
            "total_words": total_words,
            "total_count": total_count,
        }

    @staticmethod
    def _flatten(record: dict[str, Any]) -> dict[str, Any]:
        asr = record.get("asr") or {}
        gpt = record.get("gpt") or {}
        asr_text = asr.get("concatenated_text") or ""
        gpt_text = gpt.get("text") or ""
        return {
            "timestamp": record.get("timestamp", ""),
            "mode": record.get("mode", ""),
            "audio_duration": record.get("audio_duration", 0),
            "asr_text": asr_text,
            "gpt_text": gpt_text,
            "final_text": gpt_text or asr_text,
        }
