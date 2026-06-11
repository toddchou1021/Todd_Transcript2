from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import socket
import runpy
import shutil
import ssl
import subprocess
import sys
import tkinter
from pathlib import Path


APP_NAME = "Todd Transcript"
APP_VERSION = "1.0.4"


def _log(message: str) -> None:
    try:
        log_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_NAME
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "launcher.log").open("a", encoding="utf-8") as fh:
            fh.write(message.rstrip() + "\n")
    except Exception:
        pass


def _message(title: str, body: str) -> None:
    _log(f"{title}: {body}")
    try:
        ctypes.windll.user32.MessageBoxW(None, body, title, 0x40)
    except Exception:
        pass


def _launcher_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)).resolve()


def _install_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _run_checked(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _venv_is_valid(venv: Path) -> bool:
    return (
        (venv / "pyvenv.cfg").exists()
        and (venv / "Scripts" / "python.exe").exists()
        and (venv / "Scripts" / "pythonw.exe").exists()
    )


def _ensure_venv(app_dir: Path) -> Path:
    venv = app_dir / ".venv"
    python = venv / "Scripts" / "python.exe"
    marker = venv / f".todd-deps-{APP_VERSION}"
    if marker.exists() and _venv_is_valid(venv):
        return python

    if venv.exists() and not _venv_is_valid(venv):
        shutil.rmtree(venv, ignore_errors=True)

    _message(
        APP_NAME,
        "Todd Transcript will set up its local backend environment now. This can take several minutes on first launch.",
    )

    if not _venv_is_valid(venv):
        try:
            _run_checked(["py", "-3.12", "-m", "venv", str(venv)], app_dir)
        except Exception:
            _run_checked(["python", "-m", "venv", str(venv)], app_dir)

    _run_checked([str(python), "-m", "pip", "install", "--upgrade", "pip"], app_dir)
    _run_checked(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "torch",
            "torchvision",
            "torchaudio",
            "--index-url",
            "https://download.pytorch.org/whl/cu128",
        ],
        app_dir,
    )
    _run_checked([str(python), "-m", "pip", "install", "-r", str(app_dir / "requirements.txt")], app_dir)
    marker.write_text("ok\n", encoding="utf-8")
    return python


def _windowed_python(python: Path) -> Path:
    pythonw = python.with_name("pythonw.exe")
    return pythonw if pythonw.exists() else python


def _add_runtime_paths(app_dir: Path, python: Path) -> None:
    venv = python.parents[1]
    site_packages = venv / "Lib" / "site-packages"
    scripts = venv / "Scripts"
    runtime_paths = [app_dir, site_packages]
    sys.path = [str(path) for path in runtime_paths if path.exists()] + [
        path for path in sys.path if path not in {str(app_dir), str(site_packages)}
    ]
    _log("Runtime paths: " + "; ".join(str(path) for path in runtime_paths if path.exists()))
    if hasattr(os, "add_dll_directory"):
        for path in [scripts, site_packages]:
            if path.exists():
                try:
                    os.add_dll_directory(str(path))
                except OSError:
                    pass
    os.environ["PATH"] = str(scripts) + os.pathsep + os.environ.get("PATH", "")


def _run_app_in_process(app_dir: Path, python: Path) -> None:
    env_python = str(python)
    os.environ["TODD_INSTALLED_SOURCE"] = "1"
    os.environ["TODD_APP_SOURCE_DIR"] = str(app_dir)
    os.environ["TODD_VENV_PYTHON"] = env_python
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    _add_runtime_paths(app_dir, python)
    sys.argv = [str(app_dir / "launcher.py")]
    runpy.run_path(str(app_dir / "launcher.py"), run_name="__main__")


def main() -> None:
    root = _install_root()
    app_dir = root / "app"
    launcher = app_dir / "launcher.py"
    if not launcher.exists():
        _message(APP_NAME, f"App files are missing: {launcher}")
        return

    try:
        python = _ensure_venv(app_dir)
    except Exception as exc:
        _message(APP_NAME, f"Backend setup failed:\n\n{exc}")
        return

    try:
        os.chdir(app_dir)
        _run_app_in_process(app_dir, python)
    except Exception as exc:
        import traceback

        _log(traceback.format_exc())
        _message(APP_NAME, f"Unable to launch Todd Transcript:\n\n{exc}")


if __name__ == "__main__":
    main()
