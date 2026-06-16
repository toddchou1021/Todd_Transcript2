from __future__ import annotations

import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path


APP_NAME = "Todd Transcript"
APP_EXE = f"{APP_NAME}.exe"
APP_VERSION = "1.0.6"
PUBLISHER = "Todd Chou"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"


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


def _write_uninstaller(target_dir: Path) -> Path:
    script = target_dir / "uninstall.ps1"
    target_dir.mkdir(parents=True, exist_ok=True)
    script.write_text(
        rf"""
$ErrorActionPreference = "Continue"
$AppName = "{APP_NAME}"
$InstallDir = "{target_dir}"
$DesktopShortcut = Join-Path $env:USERPROFILE "Desktop\$AppName.lnk"
$StartShortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$AppName.lnk"
$SelfPid = $PID
Get-CimInstance Win32_Process | Where-Object {{ $_.ProcessId -ne $SelfPid -and $_.CommandLine -like "*$InstallDir*" }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}
Remove-Item -LiteralPath $DesktopShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $StartShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "HKCU:\{UNINSTALL_KEY}" -Recurse -Force -ErrorAction SilentlyContinue
$Cleanup = Join-Path $env:TEMP "ToddTranscriptCleanup-$([guid]::NewGuid().ToString()).ps1"
@"
`$ErrorActionPreference = "SilentlyContinue"
Start-Sleep -Seconds 2
if (-not (Test-Path -LiteralPath "HKCU:\{UNINSTALL_KEY}")) {{
    Remove-Item -LiteralPath "$InstallDir" -Recurse -Force
}}
"@ | Set-Content -LiteralPath $Cleanup -Encoding UTF8
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Cleanup) -WindowStyle Hidden
""".strip()
        + "\n",
        encoding="utf-8",
    )
    if not script.exists():
        raise RuntimeError(f"Failed to create uninstaller: {script}")
    return script


def _register_uninstall(target_dir: Path, target: Path, uninstall_script: Path) -> None:
    uninstall_cmd = (
        f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{uninstall_script}"'
    )
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(target_dir))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(target))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, uninstall_cmd)
        winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, uninstall_cmd)
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


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
    uninstall_script = _write_uninstaller(target_dir)
    _register_uninstall(target_dir, target, uninstall_script)

    subprocess.Popen([str(target)], cwd=str(target.parent))


if __name__ == "__main__":
    main()
