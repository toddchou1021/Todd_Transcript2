from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def _is_backend_running(host: str = "127.0.0.1", port: int = 8765) -> bool:
    try:
        import websocket

        ws = websocket.WebSocket()
        ws.settimeout(2)
        ws.connect(f"ws://{host}:{port}/ws/pipeline")
        ws.send(json.dumps({"type": "hello", "client_version": "launcher", "device_id": "launcher"}))
        raw = ws.recv()
        ws.close()
        return json.loads(raw).get("type") == "hello_ok"
    except Exception:
        return False


def _backend_python() -> str:
    installed_python = os.environ.get("TODD_VENV_PYTHON")
    if installed_python and Path(installed_python).exists():
        return installed_python
    local_python = Path(__file__).resolve().parent / ".venv" / "Scripts" / "python.exe"
    if local_python.exists() and not getattr(sys, "frozen", False):
        return str(local_python)
    return sys.executable


def _start_backend() -> subprocess.Popen | None:
    if _is_backend_running():
        return None
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if os.environ.get("TODD_INSTALLED_SOURCE"):
        cmd = [_backend_python(), str(Path(__file__).resolve()), "--backend"]
    else:
        cmd = [sys.executable, "--backend"] if getattr(sys, "frozen", False) else [_backend_python(), str(Path(__file__).resolve()), "--backend"]
    proc = subprocess.Popen(cmd, creationflags=creationflags)
    for _ in range(240):
        if _is_backend_running():
            return proc
        if proc.poll() is not None:
            return proc
        time.sleep(0.25)
    return proc


def _run_app() -> None:
    backend = _start_backend()
    if backend:
        atexit.register(lambda: backend.poll() is None and backend.terminate())
    from main import main

    main()


def main() -> None:
    if "--backend" in sys.argv:
        from backend.local_pipeline import main as backend_main

        backend_main()
        return
    if "--audio-helper" in sys.argv:
        from audio_capture_helper import main as helper_main

        helper_main()
        return
    _run_app()


if __name__ == "__main__":
    main()
