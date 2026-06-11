# Todd Transcript

## Overview

Speak it. Transcribe it. Translate it.

Todd Transcript is a Windows desktop transcription and translation app for source-based developer use. It records microphone, system audio, or mixed audio, sends audio to a local pipeline backend, and keeps recent output in a searchable history. Optional realtime windows can use OpenAI Realtime or Gemini 3.5 Live Translate for transcription and text translation.

Useful for:
- Turning meetings, videos, or app audio into text.
- Translating spoken content into a target language.
- Saving realtime transcript or translation output as Markdown.

Todd Transcript is built with Python and pywebview. The desktop UI, global hotkeys, audio capture, local history, hotwords, and websocket pipeline client are included in this repository.

Local pipeline mode always uses Whisper Large v3 Turbo for normal transcription. For polishing and translation, choose either Qwen 3.5 4B or Gemini 3.1 Flash Lite.

----------

說出來，轉成文字，翻成需要的語言。

Todd Transcript 是一款以原始碼開發模式執行的 Windows 桌面轉錄與翻譯工具。它可以錄製麥克風、系統音訊或混合音訊，將音訊送到本機 pipeline 後端，並把近期輸出保存在可瀏覽的歷史紀錄中。即時語音辨識與即時文字翻譯皆可選擇 OpenAI Realtime 或 Gemini 3.5 Live Translate。

適合用來：
- 將會議、影片或應用程式音訊轉成文字。
- 將語音內容翻譯成指定目標語言。
- 將即時轉錄或翻譯結果儲存為 Markdown。

Todd Transcript 使用 Python 與 pywebview 建構。桌面 UI、全域快捷鍵、音訊擷取、本機歷史紀錄、hotwords，以及 websocket pipeline client 都包含在此 repository 中。

本機 pipeline 模式一律使用 Whisper Large v3 Turbo 執行一般轉錄；逐字稿整理與翻譯則可選擇 Qwen 3.5 4B 或 Gemini 3.1 Flash Lite。

## Usage

1. Start Todd Transcript.
2. Open Settings.
3. Confirm the pipeline URL, target language, recorder source, and hotkeys.
4. Press `Ctrl+\`` to start transcription, or click `Start` in the Transcribe card.
5. Press `Ctrl+B` to start translation, or click `Start` in the Translate card.
6. Use the History page to review or delete saved output.
7. Open Realtime ASR or Realtime Translate when you want live transcript windows.
8. Save realtime output to `realtime_exports/` when needed.

----------

1. 啟動 Todd Transcript。
2. 開啟 Settings。
3. 確認 pipeline URL、目標語言、錄音來源與快捷鍵。
4. 按 `Ctrl+\`` 開始轉錄，或在 Transcribe 區塊點選 `Start`。
5. 按 `Ctrl+B` 開始翻譯，或在 Translate 區塊點選 `Start`。
6. 使用 History 頁面查看或刪除已儲存輸出。
7. 需要即時顯示時，開啟 Realtime ASR 或 Realtime Translate 視窗。
8. 視需要將即時輸出儲存到 `realtime_exports/`。

## Features

- Desktop settings window with transcribe, translate, history, hotword, and settings pages.
- Configurable global hotkeys for transcription and translation.
- Microphone, system audio, and mixed audio capture support.
- Local websocket pipeline mode for transcription, translation, and post-processing.
- Normal transcription always uses local Whisper Large v3 Turbo.
- Selectable text engine for polishing and translation: Qwen 3.5 4B or Gemini 3.1 Flash Lite.
- Hotwords stored in `data/hotwords.txt` for local recognition hints.
- Local history stored in `data/history.json`.
- Realtime transcription and translation using OpenAI Realtime or Gemini 3.5 Live Translate.
- Gemini realtime mode displays text transcripts only; generated translated audio is discarded.
- Markdown export for realtime transcript and translation sessions.

----------

- 桌面設定視窗包含轉錄、翻譯、歷史紀錄、hotword 與設定頁面。
- 可自訂轉錄與翻譯的全域快捷鍵。
- 支援麥克風、系統音訊與混合音訊擷取。
- 透過本機 websocket pipeline 執行轉錄、翻譯與後處理。
- 一般轉錄一律使用本機 Whisper Large v3 Turbo。
- 整理與翻譯可選擇文字引擎：Qwen 3.5 4B 或 Gemini 3.1 Flash Lite。
- Hotwords 會儲存在 `data/hotwords.txt`，作為本機辨識提示。
- 歷史紀錄會儲存在 `data/history.json`。
- 即時轉錄與翻譯可選用 OpenAI Realtime 或 Gemini 3.5 Live Translate。
- Gemini 即時模式只顯示文字；app 不播放或儲存產生的翻譯音訊。
- 可將即時轉錄與翻譯工作階段匯出為 Markdown。

## Requirements

- Windows
- Python 3.11 or newer recommended
- A local pipeline websocket service at `ws://127.0.0.1:8765/ws/pipeline`
- Local Whisper model weights, typically `openai/whisper-large-v3-turbo`, available to the pipeline backend
- Qwen 3.5 4B available to the pipeline backend through Ollama when using Qwen text processing
- A Gemini API key when using Gemini for polishing, normal translation, realtime ASR, or realtime translation
- An OpenAI API key when using OpenAI realtime ASR or translation

----------

- Windows
- 建議使用 Python 3.11 或更新版本
- 本機 pipeline websocket 服務：`ws://127.0.0.1:8765/ws/pipeline`
- Pipeline 後端可使用的本機 Whisper 模型權重，通常是 `openai/whisper-large-v3-turbo`
- 使用 Qwen 文字處理時，Pipeline 後端需要可透過 Ollama 執行的 Qwen 3.5 4B
- 使用 Gemini 整理、一般翻譯、即時 ASR 或即時翻譯時需要 Gemini API key
- 使用 OpenAI 即時 ASR 或即時翻譯時需要 OpenAI API key

## Installation

This repository is currently source-first. Create your local config from the example file:

```powershell
Copy-Item config.example.yaml config.yaml
```

API keys and runtime files stay local in `config.yaml`, `data/`, and `realtime_exports/`.

The local pipeline backend is separate from this desktop client. Download or prepare the Whisper and Qwen models in that backend environment, then keep `pipeline_api.url` pointed at the running websocket service.

For Windows end users, build or use the installer:

```powershell
.\scripts\build_thin_windows_installer.ps1
```

The installer output is written to `dist/ToddTranscriptSetup-1.0.4-Thin.exe`. It installs a one-click launcher that starts both the desktop app and the bundled local backend. On first launch, the thin installer prepares the local Python environment and dependencies. The backend uses `openai/whisper-large-v3-turbo` through Transformers and reuses the normal Hugging Face cache when available. Qwen text processing still requires Ollama with the configured model available locally. Gemini features require a Gemini API key saved in the app.

----------

此 repository 目前以原始碼執行為主。請先從範例檔建立本機設定：

```powershell
Copy-Item config.example.yaml config.yaml
```

API key 與執行時產生的檔案會保留在本機的 `config.yaml`、`data/` 與 `realtime_exports/`。

本機 pipeline 後端與此桌面 client 分開執行。請在後端環境下載或準備 Whisper 與 Qwen 模型，然後讓 `pipeline_api.url` 指向正在執行的 websocket 服務。

Windows 一般使用者可以建置或使用 installer：

```powershell
.\scripts\build_thin_windows_installer.ps1
```

Installer 會輸出到 `dist/ToddTranscriptSetup-1.0.4-Thin.exe`。安裝後會提供一鍵啟動器，同時啟動桌面 app 與內建本機 backend。Thin installer 會在首次啟動時準備本機 Python 環境與相依套件。Backend 會透過 Transformers 使用 `openai/whisper-large-v3-turbo`，並在可用時重用一般 Hugging Face cache。Qwen 文字處理仍需要本機 Ollama 已具備設定的模型。Gemini 功能需要在 app 中儲存 Gemini API key。

## Local Models

Local transcribe and translate mode uses the bundled backend at `pipeline_api.url`.

- Normal ASR: `openai/whisper-large-v3-turbo`
- Text engine option: Qwen 3.5 4B through Ollama
- Text engine option: Gemini 3.1 Flash Lite for polishing and translation
- Realtime ASR: OpenAI `gpt-realtime-whisper` or Gemini `gemini-3.5-live-translate-preview` input transcription
- Realtime translation: OpenAI `gpt-realtime-translate` or Gemini `gemini-3.5-live-translate-preview`

The desktop app does not run model inference directly. The bundled backend runs Whisper through Transformers, then sends the transcript to either Ollama/Qwen or Gemini for polishing and translation.

----------

本機轉錄與翻譯模式會使用 `pipeline_api.url` 指向的內建 backend。

- 一般語音辨識：`openai/whisper-large-v3-turbo`
- 文字引擎選項：透過 Ollama 執行 Qwen 3.5 4B
- 文字引擎選項：Gemini 3.1 Flash Lite 用於整理與翻譯
- 即時 ASR：OpenAI `gpt-realtime-whisper` 或 Gemini `gemini-3.5-live-translate-preview` 輸入逐字稿
- 即時翻譯：OpenAI `gpt-realtime-translate` 或 Gemini `gemini-3.5-live-translate-preview`

桌面 app 本身不直接執行模型推論。內建 backend 會透過 Transformers 執行 Whisper，然後依設定將逐字稿送到 Ollama/Qwen 或 Gemini 進行整理與翻譯。

## Developer Mode

To run the project from source:

```powershell
python -m pip install -r requirements.txt
python main.py
```

You can also use:

```powershell
.\Start Todd Transcript Dev.ps1
```

----------

若要從原始碼執行專案：

```powershell
python -m pip install -r requirements.txt
python main.py
```

也可以使用：

```powershell
.\Start Todd Transcript Dev.ps1
```

## Configuration

The main local settings live in `config.yaml`. The safe template is `config.example.yaml`.

- `pipeline_api.url` controls the local websocket backend.
- `target_language` controls translation output language.
- `recorder.input_mode` controls the default audio source.
- `ai_provider` selects `qwen` or `gemini` for post-Whisper text processing.
- `gemini.api_key` is only needed when Gemini is selected for polishing or translation.
- `realtime.asr_provider` selects `openai` or `gemini` for realtime transcription.
- `realtime.translation_provider` selects `openai` or `gemini` for realtime translation.
- `openai.api_key` is needed when an OpenAI realtime provider is selected.

----------

主要本機設定位於 `config.yaml`，安全範本則是 `config.example.yaml`。

- `pipeline_api.url` 控制本機 websocket 後端。
- `target_language` 控制翻譯輸出的目標語言。
- `recorder.input_mode` 控制預設音訊來源。
- `ai_provider` 可選擇 Whisper 之後的文字處理使用 `qwen` 或 `gemini`。
- `gemini.api_key` 只在選用 Gemini 整理或翻譯時需要。
- `realtime.asr_provider` 可選擇即時轉錄使用 `openai` 或 `gemini`。
- `realtime.translation_provider` 可選擇即時翻譯使用 `openai` 或 `gemini`。
- `openai.api_key` 只在選用 OpenAI realtime provider 時需要。

## Notes

- This rewrite intentionally omits screenshot capture, foreground-window context capture, context popups, and screenshot analysis.
- Pipeline sessions send only audio, hotwords, language, and processing configuration.
- `config.yaml`, history, hotwords, realtime exports, and cache files are ignored by Git.

----------

- 此重寫版本刻意不包含截圖擷取、前景視窗內容擷取、context popup 與截圖分析。
- Pipeline 工作階段只會送出音訊、hotwords、語言與處理設定。
- `config.yaml`、歷史紀錄、hotwords、realtime 匯出檔與快取檔都會被 Git 忽略。

## License

No license file is currently included.
