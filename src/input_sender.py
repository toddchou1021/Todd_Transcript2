from __future__ import annotations

import time

import pyperclip


def copy_text(text: str) -> None:
    pyperclip.copy(text or "")


def paste_text(text: str) -> None:
    if not text:
        return
    import keyboard

    pyperclip.copy(text)
    time.sleep(0.05)
    keyboard.press_and_release("ctrl+v")
