# LocalDesk AI

A free, local-first Windows desktop assistant built with Python, PySide6, and LM Studio's OpenAI-compatible local API.

## Features
- Chat with a model served by LM Studio.
- Refresh the model list from the local server.
- Optional always-on-top window.
- Attach an image or capture the full screen for a vision-capable local model.
- Optional 8-second microphone recording and local transcription using faster-whisper.
- No cloud inference API is configured.

## Requirements
- Windows 10/11
- Python 3.11 or 3.12 recommended for broad package compatibility.
- LM Studio with a model already downloaded.
- For image understanding, load a vision-capable model that supports image input.
- For voice transcription, install the optional dependencies below.

## Setup (beginner-friendly)

1. Extract the ZIP to a folder such as `C:\AI\LocalDeskAI`.
2. Install Python from https://www.python.org/downloads/windows/ if needed. During setup, enable **Add Python to PATH**.
3. Open the extracted folder in File Explorer.
4. Click the address bar, type `cmd`, and press Enter.
5. Run:

   ```bat
   py -3.12 -m venv .venv
   .venv\Scripts\python.exe -m pip install --upgrade pip
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   If `py -3.12` is unavailable, use `python -m venv .venv` instead.

6. Open LM Studio. Load a model.
7. Open the Developer tab and start the local server. The default OpenAI-compatible server address is usually `http://127.0.0.1:1234/v1`.
8. Run the app from the same Command Prompt:

   ```bat
   .venv\Scripts\python.exe app.py
   ```

9. In LocalDesk AI, click **Refresh models**, then choose a model.

## Voice input
The first voice transcription may download the `base` Whisper model, so internet is needed once unless its model files are already cached. After that, transcription can run locally. The current implementation records an 8-second clip and transcribes on CPU to keep setup simple.

If microphone support fails:
- Check Windows Settings → Privacy & security → Microphone.
- Confirm the microphone works in Windows Sound settings.
- If optional dependencies were skipped, run:

  ```bat
  .venv\Scripts\python.exe -m pip install sounddevice numpy faster-whisper
  ```

## Screenshot/image support
- **Capture screen** captures the full primary display, not a cropped selection. Check the contents before sending.
- **Attach image** lets you choose an image file.
- Image understanding requires a vision-capable model and compatible LM Studio server/model configuration. Text-only models cannot interpret images.
- The screenshot is sent to the configured local server as part of the request. Keep the server bound to localhost for local-only use.

## Privacy and capture behavior
This app does **not** implement stealth or screen-capture exclusion. The always-on-top setting only changes window stacking. Screen-capture exclusion APIs are not universal privacy guarantees; behavior varies by capture method and application. Do not rely on them to bypass interview rules, proctoring, recording, or monitoring.

## Troubleshooting
- **Could not connect:** Start LM Studio's local server and verify the server URL.
- **No models found:** Load a model in LM Studio, then refresh.
- **Image is not understood:** Select a vision-capable model.
- **Slow answers:** Try a smaller quantized model or reduce its context length in LM Studio.
- **Port differs:** Change the Server field to your actual local server URL.

## License
This project source is provided under the MIT License. Review the separate licenses of Python packages, Qt/PySide6, LM Studio, and any model weights you download.
