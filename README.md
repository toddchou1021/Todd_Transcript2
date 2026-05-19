# Todd Transcript Next

Source-based developer rewrite of the installed desktop app.

## Developer Mode

```powershell
python -m pip install -r requirements.txt
python main.py
```

The rewrite intentionally omits screenshot capture, foreground-window context capture,
context popups, and screenshot analysis. Pipeline sessions send only audio, hotwords,
language, and processing configuration.
