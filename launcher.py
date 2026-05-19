from __future__ import annotations

import atexit
from pathlib import Path
import socket
import subprocess
import sys
import time


def _is_backend_running(host: str = "127.0.0.1", port: int = 8765) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) == 0


def _start_backend() -> subprocess.Popen | None:
    if _is_backend_running():
        return None
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    cmd = [sys.executable, "--backend"] if getattr(sys, "frozen", False) else [sys.executable, str(Path(__file__).resolve()), "--backend"]
    proc = subprocess.Popen(cmd, creationflags=creationflags)
    for _ in range(60):
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
