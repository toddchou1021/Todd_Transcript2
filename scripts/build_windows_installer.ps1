$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Version = "1.0.1"
$AppName = "Todd Transcript"
$SetupName = "ToddTranscriptSetup-$Version"
$AppExe = Join-Path $Root "dist\$AppName.exe"
$SetupExe = Join-Path $Root "dist\$SetupName.exe"

python -m pip install -r requirements.txt
python -m pip install pyinstaller

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $AppName `
  --icon "assets\app.ico" `
  --add-data "assets;assets" `
  --add-data "audio_capture_helper.py;." `
  --hidden-import "websockets.asyncio.server" `
  --collect-all "faster_whisper" `
  --collect-all "ctranslate2" `
  launcher.py

if (-not (Test-Path $AppExe)) {
  throw "Application executable was not created: $AppExe"
}

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $SetupName `
  --icon "assets\app.ico" `
  --add-binary "$AppExe;." `
  "scripts\installer_bootstrap.py"

if (-not (Test-Path $SetupExe)) {
  throw "Installer executable was not created: $SetupExe"
}

Write-Host "Installer created: $SetupExe"
