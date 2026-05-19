from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


APP_NAME = "Todd Transcript"
APP_EXE = f"{APP_NAME}.exe"


def _payload_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def _install_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / APP_NAME


def _create_shortcut(path: Path, target: Path) -> None:
    try:
        command = (
            "$ws=New-Object -ComObject WScript.Shell; "
            f"$s=$ws.CreateShortcut('{str(path)}'); "
            f"$s.TargetPath='{str(target)}'; "
            f"$s.WorkingDirectory='{str(target.parent)}'; "
            f"$s.IconLocation='{str(target)}'; "
            "$s.Save()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass


def main() -> None:
    source = _payload_dir() / APP_EXE
    if not source.exists():
        raise FileNotFoundError(f"Installer payload is missing: {source}")

    target_dir = _install_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / APP_EXE
    shutil.copy2(source, target)

    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop" / f"{APP_NAME}.lnk"
    start_menu = Path(os.environ.get("APPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / f"{APP_NAME}.lnk"
    start_menu.parent.mkdir(parents=True, exist_ok=True)
    _create_shortcut(desktop, target)
    _create_shortcut(start_menu, target)

    subprocess.Popen([str(target)], cwd=str(target.parent))


if __name__ == "__main__":
    main()
