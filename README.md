# Todd Transcript

## Overview

Speak it. Transcribe it. Translate it.

Todd Transcript is a Windows desktop transcription and translation app for source-based developer use. It records microphone, system audio, or mixed audio, sends audio to a local pipeline backend, and keeps recent output in a searchable history. Optional realtime windows can use OpenAI Realtime transcription and translation when an API key is configured locally.

Useful for:
- Turning meetings, videos, or app audio into text.
- Translating spoken content into a target language.
- Saving realtime transcript or translation output as Markdown.

Todd Transcript is built with Python and pywebview. The desktop UI, global hotkeys, audio capture, local history, hotwords, and websocket pipeline client are included in this repository.

----------

說出來，轉成文字，翻成需要的語言。

Todd Transcript 是一款以原始碼開發模式執行的 Windows 桌面轉錄與翻譯工具。它可以錄製麥克風、系統音訊或混合音訊，將音訊送到本機 pipeline 後端，並把近期輸出保存在可瀏覽的歷史紀錄中。若在本機設定 OpenAI API key，也可以使用 OpenAI Realtime 轉錄與翻譯視窗。

適合用來：
- 將會議、影片或應用程式音訊轉成文字。
- 將語音內容翻譯成指定目標語言。
- 將即時轉錄或翻譯結果儲存為 Markdown。

Todd Transcript 使用 Python 與 pywebview 建構。桌面 UI、全域快捷鍵、音訊擷取、本機歷史紀錄、hotwords，以及 websocket pipeline client 都包含在此 repository 中。

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
- Hotwords stored in `data/hotwords.txt` for local recognition hints.
- Local history stored in `data/history.json`.
- Optional OpenAI Realtime transcription and translation windows.
- Markdown export for realtime transcript and translation sessions.

----------

- 桌面設定視窗包含轉錄、翻譯、歷史紀錄、hotword 與設定頁面。
- 可自訂轉錄與翻譯的全域快捷鍵。
- 支援麥克風、系統音訊與混合音訊擷取。
- 透過本機 websocket pipeline 執行轉錄、翻譯與後處理。
- Hotwords 會儲存在 `data/hotwords.txt`，作為本機辨識提示。
- 歷史紀錄會儲存在 `data/history.json`。
- 可選用 OpenAI Realtime 轉錄與翻譯視窗。
- 可將即時轉錄與翻譯工作階段匯出為 Markdown。

## Requirements

- Windows
- Python 3.11 or newer recommended
- A local pipeline websocket service at `ws://127.0.0.1:8765/ws/pipeline`
- An OpenAI API key only if using the optional realtime windows

## Installation

This repository is currently source-first. Create your local config from the example file:

```powershell
Copy-Item config.example.yaml config.yaml
```

API keys and runtime files stay local in `config.yaml`, `data/`, and `realtime_exports/`.

----------

此 repository 目前以原始碼執行為主。請先從範例檔建立本機設定：

```powershell
Copy-Item config.example.yaml config.yaml
```

API key 與執行時產生的檔案會保留在本機的 `config.yaml`、`data/` 與 `realtime_exports/`。

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
- `openai.api_key` is only needed for realtime windows.

----------

主要本機設定位於 `config.yaml`，安全範本則是 `config.example.yaml`。

- `pipeline_api.url` 控制本機 websocket 後端。
- `target_language` 控制翻譯輸出的目標語言。
- `recorder.input_mode` 控制預設音訊來源。
- `openai.api_key` 只在使用 realtime 視窗時需要。

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
