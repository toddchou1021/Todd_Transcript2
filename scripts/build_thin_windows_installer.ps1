$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Version = "1.0.4"
$AppName = "Todd Transcript"
$SetupName = "ToddTranscriptSetup-$Version-Thin"
$ThinRoot = Join-Path $Root "build\thin-installer"
$PayloadRoot = Join-Path $ThinRoot "payload"
$AppPayload = Join-Path $ThinRoot "app_payload.zip"
$LauncherExe = Join-Path $Root "dist\$AppName.exe"
$SetupExe = Join-Path $Root "dist\$SetupName.exe"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
  $Python = "python"
}

& $Python -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "PyInstaller install failed." }

Remove-Item -Recurse -Force $ThinRoot -ErrorAction SilentlyContinue
Remove-Item -Force $LauncherExe, $SetupExe -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $PayloadRoot -Force | Out-Null

$Items = @(
  "assets",
  "backend",
  "src",
  "audio_capture_helper.py",
  "config.example.yaml",
  "launcher.py",
  "main.py",
  "requirements.txt"
)

foreach ($Item in $Items) {
  $Source = Join-Path $Root $Item
  $Destination = Join-Path $PayloadRoot $Item
  if (Test-Path $Source -PathType Container) {
    Copy-Item -Path $Source -Destination $Destination -Recurse -Force
  } else {
    Copy-Item -Path $Source -Destination $Destination -Force
  }
}

Get-ChildItem -Path $PayloadRoot -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Get-ChildItem -Path $PayloadRoot -Recurse -File -Include "*.pyc", "*.pyo" | Remove-Item -Force

Compress-Archive -Path (Join-Path $PayloadRoot "*") -DestinationPath $AppPayload -Force

& $Python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $AppName `
  --icon "assets\app.ico" `
  --version-file "scripts\app_version_info.txt" `
  --hidden-import "src.app" `
  --hidden-import "ctypes.wintypes" `
  --hidden-import "_socket" `
  --hidden-import "_ssl" `
  --hidden-import "unicodedata" `
  "scripts\thin_launcher.py"
if ($LASTEXITCODE -ne 0) { throw "Thin launcher build failed." }

if (-not (Test-Path $LauncherExe)) {
  throw "Thin launcher executable was not created: $LauncherExe"
}

& $Python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $SetupName `
  --icon "assets\app.ico" `
  --add-binary "$LauncherExe;." `
  --add-data "$AppPayload;." `
  --version-file "scripts\installer_version_info.txt" `
  "scripts\thin_installer_bootstrap.py"
if ($LASTEXITCODE -ne 0) { throw "Thin installer build failed." }

if (-not (Test-Path $SetupExe)) {
  throw "Thin installer executable was not created: $SetupExe"
}

Write-Host "Thin installer created: $SetupExe"
