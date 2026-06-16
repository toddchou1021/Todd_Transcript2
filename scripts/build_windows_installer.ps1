$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Version = "1.0.6"
$AppName = "Todd Transcript"
$SetupName = "ToddTranscriptSetup-$Version"
$AppExe = Join-Path $Root "dist\$AppName.exe"
$HelperExe = Join-Path $Root "dist\ToddAudioHelper.exe"
$SetupExe = Join-Path $Root "dist\$SetupName.exe"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

& $Python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency install failed." }
& $Python -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller install failed." }

Get-Process | Where-Object { $_.ProcessName -in @("Todd Transcript", "ToddTranscriptSetup-1.0.1", "ToddTranscriptSetup-1.0.2", "ToddTranscriptSetup-1.0.3", "ToddTranscriptSetup-1.0.4", "ToddTranscriptSetup-1.0.5", "ToddTranscriptSetup-1.0.6") } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500
Remove-Item -Force $AppExe, $HelperExe, $SetupExe -ErrorAction SilentlyContinue

& $Python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --console `
  --name "ToddAudioHelper" `
  --hidden-import "pyaudiowpatch" `
  audio_capture_helper.py
if ($LASTEXITCODE -ne 0) { throw "Audio helper PyInstaller build failed." }

if (-not (Test-Path $HelperExe)) {
  throw "Audio helper executable was not created: $HelperExe"
}

& $Python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $AppName `
  --icon "assets\app.ico" `
  --version-file "scripts\app_version_info.txt" `
  --add-data "assets;assets" `
  --add-binary "$HelperExe;." `
  --hidden-import "websockets.asyncio.server" `
  --hidden-import "pyaudiowpatch" `
  launcher.py
if ($LASTEXITCODE -ne 0) { throw "Application PyInstaller build failed." }

if (-not (Test-Path $AppExe)) {
  throw "Application executable was not created: $AppExe"
}

& $Python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $SetupName `
  --icon "assets\app.ico" `
  --add-binary "$AppExe;." `
  --version-file "scripts\installer_version_info.txt" `
  "scripts\installer_bootstrap.py"
if ($LASTEXITCODE -ne 0) { throw "Installer PyInstaller build failed." }

if (-not (Test-Path $SetupExe)) {
  throw "Installer executable was not created: $SetupExe"
}

Write-Host "Installer created: $SetupExe"
