from __future__ import annotations

import os
import sys
from pathlib import Path


def _source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _app_root() -> Path:
    if getattr(sys, "frozen", False):
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "Todd Transcript"
    return _source_root()


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return _source_root()


ROOT_DIR = _app_root()
RESOURCE_DIR = _resource_root()
ASSETS_DIR = RESOURCE_DIR / "assets"
DATA_DIR = ROOT_DIR / "data"
EXPORTS_DIR = ROOT_DIR / "realtime_exports"
CONFIG_PATH = ROOT_DIR / "config.yaml"
ICON_PATH = ASSETS_DIR / "app.ico"
LOGO_PATH = ASSETS_DIR / "app-logo.png"
HELPER_PATH = RESOURCE_DIR / ("ToddAudioHelper.exe" if getattr(sys, "frozen", False) else "audio_capture_helper.py")
