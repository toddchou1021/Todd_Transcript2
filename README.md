# Todd Transcript

## Overview

Speak it. Transcribe it. Translate it.

Todd Transcript is a Windows desktop app for transcription and translation. It records microphone, system audio, or mixed audio, runs normal transcription through Gemini, and keeps recent output in a searchable local history. Realtime transcription and translation use Gemini Live.

Useful for:
- Turning meetings, videos, or app audio into text.
- Translating spoken content into a target language.
- Saving realtime transcript or translation output as Markdown.

Todd Transcript is built with Python and pywebview. The desktop UI, global hotkeys, audio capture, local history, hotwords, bundled backend, and websocket pipeline client are included in this repository.

For normal use, download the latest `ToddTranscriptSetup-*-Thin.exe` installer from [GitHub Releases](https://github.com/toddchou1021/Todd_Transcript2/releases), run it, then open Todd Transcript and save your Gemini API key in Settings.

Normal recording transcription, text polishing, and normal translation use Gemini 3.1 Flash Lite. Realtime ASR and realtime translation use Gemini Live.

----------

說出來，轉成文字，翻成需要的語言。

Todd Transcript 是一款 Windows 桌面轉錄與翻譯工具。它可以錄製麥克風、系統音訊或混合音訊，使用 Gemini 進行一般轉錄，並把近期輸出保存在可瀏覽的本機歷史紀錄中。即時語音辨識與即時翻譯使用 Gemini Live。

適合用來：
- 將會議、影片或應用程式音訊轉成文字。
- 將語音內容翻譯成指定目標語言。
- 將即時轉錄或翻譯結果儲存為 Markdown。

Todd Transcript 使用 Python 與 pywebview 建構。桌面 UI、全域快捷鍵、音訊擷取、本機歷史紀錄、hotwords、內建後端，以及 websocket pipeline client 都包含在此 repository 中。

一般使用者可從 [GitHub Releases](https://github.com/toddchou1021/Todd_Transcript2/releases) 下載最新的 `ToddTranscriptSetup-*-Thin.exe` installer，執行安裝後開啟 Todd Transcript，並在 Settings 儲存 Gemini API key。

一般錄音轉錄、文字整理與一般翻譯使用 Gemini 3.1 Flash Lite。即時語音辨識與即時翻譯使用 Gemini Live。

## Usage

1. Start Todd Transcript.
2. Open Settings.
3. Confirm the UI language, target language, recorder source, and hotkeys.
4. Open Realtime ASR, Realtime Translate, or ASR + Translate when you want live windows.
5. Press `Ctrl+Alt+F` to start normal recording transcription, or click `Start` in the Transcribe row.
6. Press `Ctrl+Alt+D` to start normal recording translation, or click `Start` in the Translate row.
7. Use the History page to review, copy, or delete saved output.
8. Save realtime output to `realtime_exports/` when needed.

----------

1. 啟動 Todd Transcript。
2. 開啟 Settings。
3. 確認介面語言、目標語言、錄音來源與快捷鍵。
4. 需要即時視窗時，開啟 Realtime ASR、Realtime Translate 或 ASR + Translate。
5. 按 `Ctrl+Alt+F` 開始一般錄音轉錄，或在 Transcribe 列點選 `Start`。
6. 按 `Ctrl+Alt+D` 開始一般錄音翻譯，或在 Translate 列點選 `Start`。
7. 使用 History 頁面查看、複製或刪除已儲存輸出。
8. 視需要將即時輸出儲存到 `realtime_exports/`。

## Features

- Desktop app with speech control, history, hotwords, and runtime settings.
- Realtime ASR, realtime translation, and combined realtime windows.
- Configurable global hotkeys for normal recording transcription and translation.
- Microphone, system audio, and mixed audio capture support.
- English and Traditional Chinese UI display language.
- Gemini 3.1 Flash Lite for normal recording transcription, text polishing, and normal translation.
- Gemini Live realtime transcription and translation.
- Hotwords stored in `data/hotwords.txt` for local recognition hints.
- Local history stored in `data/history.json`.
- Markdown export for realtime transcript and translation sessions.

----------

- 桌面 app 包含語音控制、歷史紀錄、hotwords 與執行設定。
- 支援即時語音辨識、即時翻譯，以及合併即時視窗。
- 可自訂一般錄音轉錄與翻譯的全域快捷鍵。
- 支援麥克風、系統音訊與混合音訊擷取。
- 介面顯示語言可選英文或繁體中文。
- Gemini 3.1 Flash Lite 用於一般錄音轉錄、文字整理與一般翻譯。
- 即時轉錄與即時翻譯使用 Gemini Live。
- Hotwords 會儲存在 `data/hotwords.txt`，作為本機辨識提示。
- 歷史紀錄會儲存在 `data/history.json`。
- 可將即時轉錄與翻譯工作階段匯出為 Markdown。

## Models and Services

### Cloud API Services

- Normal recording transcription: Gemini 3.1 Flash Lite, `gemini-3.1-flash-lite`.
- Text polishing and normal translation: Gemini 3.1 Flash Lite.
- Realtime ASR and realtime translation: Gemini Live, `gemini-3.5-live-translate-preview`.
- These Gemini features require a Gemini API key saved in the app.

Normal recording audio is sent to Gemini 3.1 Flash Lite for transcription. If text polishing or translation is used, the transcript text is also sent to Gemini. Realtime modes send realtime audio to Gemini Live.

### Model Use In Todd Transcript

| App function | Model or service |
| --- | --- |
| Normal recording transcription | Gemini 3.1 Flash Lite, `gemini-3.1-flash-lite` |
| Normal transcript polishing | Gemini 3.1 Flash Lite, `gemini-3.1-flash-lite` |
| Normal recording translation | Gemini 3.1 Flash Lite transcription, then Gemini 3.1 Flash Lite translation |
| Realtime ASR window | Gemini Live, `gemini-3.5-live-translate-preview` input transcription |
| Realtime Translate window | Gemini Live, `gemini-3.5-live-translate-preview` output transcription |
| Realtime ASR + Translate window | Gemini Live for both realtime transcript and translation text |

### Gemini API Key

1. Open [Google AI Studio API keys](https://aistudio.google.com/app/apikey).
2. Sign in with your Google account.
3. Create an API key. If AI Studio asks for a project, create or select one.
4. Copy the key.
5. In Todd Transcript, open Settings and save it in the Gemini API Key field.

For better security, restrict the key to the Gemini API in Google AI Studio after creating it. Do not commit `config.yaml`; it stores your local key.

### Current Gemini Limits

Google says Gemini API limits can vary by project, account tier, and time, and active limits should be checked in Google AI Studio. As of this README update, the current expected limits for this app are:

- Gemini 3.1 Flash Lite: 500 requests per day.
- Gemini Live `gemini-3.5-live-translate-preview`: unlimited daily requests.

----------

### 雲端 API 服務

- 一般錄音轉錄：Gemini 3.1 Flash Lite，`gemini-3.1-flash-lite`。
- 文字整理與一般翻譯：Gemini 3.1 Flash Lite。
- 即時語音辨識與即時翻譯：Gemini Live，`gemini-3.5-live-translate-preview`。
- 這些 Gemini 功能需要在 app 中儲存 Gemini API key。

一般錄音音訊會送到 Gemini 3.1 Flash Lite 進行轉錄；使用文字整理或翻譯時，逐字稿文字也會送到 Gemini。即時模式會將即時音訊送到 Gemini Live。

### Todd Transcript 使用的模型

| App 功能 | 模型或服務 |
| --- | --- |
| 一般錄音轉錄 | Gemini 3.1 Flash Lite，`gemini-3.1-flash-lite` |
| 一般逐字稿整理 | Gemini 3.1 Flash Lite，`gemini-3.1-flash-lite` |
| 一般錄音翻譯 | Gemini 3.1 Flash Lite 轉錄，然後使用 Gemini 3.1 Flash Lite 翻譯 |
| Realtime ASR 視窗 | Gemini Live，`gemini-3.5-live-translate-preview` 輸入逐字稿 |
| Realtime Translate 視窗 | Gemini Live，`gemini-3.5-live-translate-preview` 輸出逐字稿 |
| Realtime ASR + Translate 視窗 | Gemini Live 同時提供即時逐字稿與翻譯文字 |

### Gemini API Key

1. 開啟 [Google AI Studio API keys](https://aistudio.google.com/app/apikey)。
2. 使用 Google 帳號登入。
3. 建立 API key；如果 AI Studio 要求選擇 project，請建立或選擇一個 project。
4. 複製 API key。
5. 在 Todd Transcript 中開啟 Settings，並將 key 儲存在 Gemini API Key 欄位。

為了提高安全性，建立 key 後可在 Google AI Studio 將它限制為只能使用 Gemini API。請勿 commit `config.yaml`；它會儲存你的本機 API key。

### 目前 Gemini 使用限制

Google 表示 Gemini API 限制可能因 project、帳戶層級與時間而不同，實際可用限制應以 Google AI Studio 顯示為準。截至本 README 更新時，此 app 目前預期限制如下：

- Gemini 3.1 Flash Lite：每天 500 次 requests。
- Gemini Live `gemini-3.5-live-translate-preview`：每天 requests 無上限。

## Requirements

- Windows
- Python 3.11 or newer recommended for source mode and local builds
- A Gemini API key for transcription, polishing, translation, and realtime features

The thin installer can prepare the local Python environment on first launch. Source mode requires installing dependencies from `requirements.txt`.

----------

- Windows
- 從原始碼執行或本機建置時，建議使用 Python 3.11 或更新版本
- 使用轉錄、文字整理、翻譯與即時功能時需要 Gemini API key

Thin installer 可在首次啟動時準備本機 Python 環境。從原始碼執行時，需要先安裝 `requirements.txt` 中的相依套件。

## Installation

### Run From Source

```powershell
python -m pip install -r requirements.txt
python launcher.py
```

You can also use:

```powershell
.\Start Todd Transcript Dev.ps1
```

Create or edit local settings from the example file when needed:

```powershell
Copy-Item config.example.yaml config.yaml
```

### Build The Windows Installer

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_thin_windows_installer.ps1
```

The installer output is written to `dist/ToddTranscriptSetup-1.0.6-Thin.exe`. It installs a launcher that starts both the desktop app and the bundled local backend. On first launch, the thin installer prepares the local Python environment and dependencies. This can take several minutes.

----------

### 從原始碼執行

```powershell
python -m pip install -r requirements.txt
python launcher.py
```

也可以使用：

```powershell
.\Start Todd Transcript Dev.ps1
```

需要時可從範例檔建立或編輯本機設定：

```powershell
Copy-Item config.example.yaml config.yaml
```

### 建置 Windows Installer

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_thin_windows_installer.ps1
```

Installer 會輸出到 `dist/ToddTranscriptSetup-1.0.6-Thin.exe`。它會安裝一個 launcher，同時啟動桌面 app 與內建本機後端。Thin installer 會在首次啟動時準備本機 Python 環境與相依套件，可能需要數分鐘。

## Configuration

The main local settings live in `config.yaml`. The safe template is `config.example.yaml`.

- `ui_language` controls the app display language: `en` or `zh`.
- `target_language` controls translation output language.
- `recorder.input_mode` controls the default audio source: `microphone`, `system_audio`, or `both`.
- `hotkey.transcribe` controls the normal transcription hotkey.
- `hotkey.translate` controls the normal translation hotkey.
- `pipeline_api.url` controls the local backend websocket endpoint.
- `gemini.api_key` stores the Gemini API key locally.

----------

主要本機設定位於 `config.yaml`，安全範本則是 `config.example.yaml`。

- `ui_language` 控制 app 顯示語言：`en` 或 `zh`。
- `target_language` 控制翻譯輸出的目標語言。
- `recorder.input_mode` 控制預設音訊來源：`microphone`、`system_audio` 或 `both`。
- `hotkey.transcribe` 控制一般轉錄快捷鍵。
- `hotkey.translate` 控制一般翻譯快捷鍵。
- `pipeline_api.url` 控制本機後端 websocket 端點。
- `gemini.api_key` 會在本機儲存 Gemini API key。

## Privacy

Configuration, API keys, hotwords, history, realtime exports, and cache files are stored locally. Normal recording transcription, polishing, translation, and realtime features send transcript text or audio to Gemini APIs.

----------

設定、API key、hotwords、歷史紀錄、即時匯出檔與快取檔均保留在本機。一般錄音轉錄、文字整理、翻譯與即時功能會將逐字稿文字或音訊送到 Gemini API。

## License

MIT License. See `LICENSE`.
