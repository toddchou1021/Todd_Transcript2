from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT_DIR / "assets"
DATA_DIR = ROOT_DIR / "data"
CONFIG_PATH = ROOT_DIR / "config.yaml"
ICON_PATH = ASSETS_DIR / "app.ico"
LOGO_PATH = ASSETS_DIR / "app-logo.png"
HELPER_PATH = ROOT_DIR / "audio_capture_helper.py"
