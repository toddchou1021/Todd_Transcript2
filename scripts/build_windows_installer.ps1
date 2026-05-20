$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Version = "1.0.1"
$AppName = "Todd Transcript"
$SetupName = "ToddTranscriptSetup-$Version"
$AppExe = Join-Path $Root "dist\$AppName.exe"
$HelperExe = Join-Path $Root "dist\ToddAudioHelper.exe"
$SetupExe = Join-Path $Root "dist\$SetupName.exe"

python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency install failed." }
python -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller install failed." }

Get-Process | Where-Object { $_.ProcessName -in @("Todd Transcript", "ToddTranscriptSetup-1.0.1") } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Remove-Item -Force $AppExe, $HelperExe, $SetupExe -ErrorAction SilentlyContinue

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --console `
  --name "ToddAudioHelper" `
  audio_capture_helper.py
if ($LASTEXITCODE -ne 0) { throw "Audio helper PyInstaller build failed." }

if (-not (Test-Path $HelperExe)) {
  throw "Audio helper executable was not created: $HelperExe"
}

python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $AppName `
  --icon "assets\app.ico" `
  --add-data "assets;assets" `
  --add-binary "$HelperExe;." `
  --hidden-import "websockets.asyncio.server" `
  --collect-all "transformers" `
  --collect-all "torch" `
  --collect-all "tokenizers" `
  --collect-all "safetensors" `
  launcher.py
if ($LASTEXITCODE -ne 0) { throw "Application PyInstaller build failed." }

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
if ($LASTEXITCODE -ne 0) { throw "Installer PyInstaller build failed." }

if (-not (Test-Path $SetupExe)) {
  throw "Installer executable was not created: $SetupExe"
}

Write-Host "Installer created: $SetupExe"
