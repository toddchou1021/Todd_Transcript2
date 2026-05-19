from __future__ import annotations

from pathlib import Path


class HotwordsManager:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def get_all(self) -> list[str]:
        seen: set[str] = set()
        words: list[str] = []
        for line in self.path.read_text(encoding="utf-8", errors="ignore").splitlines():
            word = line.strip()
            if not word or word.startswith("#") or word in seen:
                continue
            seen.add(word)
            words.append(word)
        return words

    def add(self, word: str) -> list[str]:
        word = word.strip()
        if not word:
            return self.get_all()
        words = self.get_all()
        if word not in words:
            words.append(word)
            self.path.write_text("\n".join(words) + "\n", encoding="utf-8")
        return words

    def remove(self, word: str) -> list[str]:
        words = [w for w in self.get_all() if w != word]
        self.path.write_text("\n".join(words) + ("\n" if words else ""), encoding="utf-8")
        return words
