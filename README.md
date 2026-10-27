<div align="center">

```
██╗      ██████╗  ██████╗ █████╗ ██╗      ██████╗ ███████╗███████╗██╗  ██╗     █████╗ ██╗
██║     ██╔═══██╗██╔════╝██╔══██╗██║      ██╔══██╗██╔════╝██╔════╝██║ ██╔╝    ██╔══██╗██║
██║     ██║   ██║██║     ███████║██║      ██║  ██║█████╗  ███████╗█████╔╝     ███████║██║
██║     ██║   ██║██║     ██╔══██║██║      ██║  ██║██╔══╝  ╚════██║██╔═██╗     ██╔══██║██║
███████╗╚██████╔╝╚██████╗██║  ██║███████╗ ██████╔╝███████╗███████║██║  ██╗    ██║  ██║██║
╚══════╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝    ╚═╝  ╚═╝╚═╝
```

**Your private, local-first AI desktop assistant — powered by LM Studio**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-6.8%2B-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![LM Studio](https://img.shields.io/badge/LM%20Studio-Compatible-6C63FF?style=for-the-badge)](https://lmstudio.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Windows](https://img.shields.io/badge/Windows-10%2B-0078D4?style=for-the-badge&logo=windows&logoColor=white)](https://microsoft.com/windows)

</div>

---

## ✨ What is LocalDesk AI?

**LocalDesk AI** is a sleek, dark-themed desktop chat assistant that connects to any locally-running LLM via [LM Studio](https://lmstudio.ai). Every single token is processed **on your own machine** — no cloud, no subscriptions, no data leaving your PC.

> Built for the privacy-conscious power user who wants GPT-level intelligence without the surveillance.

---

## 🖥️ Features

| Feature | Description |
|---|---|
| 🤖 **Streaming Responses** | Tokens appear in real-time as the model generates — no waiting |
| 📷 **Screen Capture** | Capture your full desktop and preview it before attaching |
| 🎙️ **Voice Input** | 8-second local speech recognition via Whisper (runs 100% offline) |
| 📎 **Image Attach** | Attach any PNG/JPG/WEBP to your message for vision models |
| 🛡️ **Hide from Screen Share** | One checkbox makes the window **completely invisible** to OBS, Teams, Zoom & all capture tools |
| 🔁 **Auto-connect** | Automatically detects and loads models from LM Studio on startup |
| 💬 **Chat History** | Full multi-turn conversation memory per session |
| 🖼️ **Screenshot Preview** | Review & approve captured screenshots before they get sent |
| 📌 **Always on Top** | Pin the window above all other apps |
| 🗑️ **Clear Chat** | Wipe conversation history with one click |

---

## 🚀 Quick Start

### Prerequisites

- **[LM Studio](https://lmstudio.ai)** — download, load a model, start the local server
- **Python 3.10+**

### 1. Clone the repo

```bash
git clone https://github.com/sankhadeep-coder/COURSERA-HACKER.git
cd COURSERA-HACKER
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Install dependencies

```bash
.venv\Scripts\pip install -r requirements.txt
```

### 4. Run

```bash
# Option A — double-click
run.bat

# Option B — terminal
.venv\Scripts\python.exe app.py
```

---

## 🎙️ Voice Input (Optional)

Voice input uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and runs fully offline:

```bash
.venv\Scripts\pip install sounddevice numpy faster-whisper
```

The first time you click **Voice Input**, Whisper's `base` model (~150 MB) will be downloaded automatically.

---

## 🛡️ Hide from Screen Share

Check **"Hide from screen share"** in the sidebar.

This calls the Windows `SetWindowDisplayAffinity` API (`WDA_EXCLUDEFROMCAPTURE`) — the window vanishes from **every** capture tool instantly:

- ✅ OBS Studio
- ✅ Microsoft Teams
- ✅ Zoom
- ✅ Discord
- ✅ Windows Snipping Tool / Win+Shift+S
- ✅ Any DirectX/DXGI screen recorder

> You still see the window on your physical monitor. Requires **Windows 10 v2004 (Build 19041)** or later.

---

## 🏗️ Architecture

```
LocalDesk AI
├── app.py                  # Main application (single file, ~1100 lines)
│   ├── StreamWorker        # QThread — streams tokens from LM Studio API
│   ├── ModelsWorker        # QThread — fetches available models
│   ├── VoiceWorker         # QThread — records mic & runs Whisper locally
│   ├── ScreenshotPreviewDialog  # Modal preview before attaching screenshots
│   ├── ChatBubble          # Individual message widget (user / AI)
│   ├── TypingIndicator     # Animated 3-dot loader
│   ├── StatusPill          # Live connection status indicator
│   └── MainWindow          # Main UI — sidebar + chat area
├── requirements.txt        # Core dependencies
├── run.bat                 # Windows one-click launcher
└── .gitignore
```

---

## 🔌 LM Studio Setup

1. Download [LM Studio](https://lmstudio.ai) and install a model (e.g. `google/gemma-4-12b-qat`)
2. Go to **Developer** tab → toggle **Status: Running**
3. The server runs at `http://127.0.0.1:1234` by default
4. Launch LocalDesk AI → models auto-detect ✅

Any **OpenAI-compatible** local server works — LM Studio, Ollama (with `--host`), LlamaFile, Jan, etc.

---

## ⚙️ Requirements

```
PySide6>=6.8
requests>=2.32

# Optional — voice input:
sounddevice>=0.5
numpy>=2.0
faster-whisper>=1.1
```

---

## 🤝 Contributing

Pull requests are welcome! For major changes, open an issue first.

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/amazing-thing`
3. Commit: `git commit -m "Add amazing thing"`
4. Push: `git push origin feature/amazing-thing`
5. Open a Pull Request

---

## 📄 License

[MIT](LICENSE) © 2026 Sankhadeep Mukherjee

---

<div align="center">

**Built with ❤️ for privacy — zero telemetry, zero cloud, zero compromise.**

*If this helped you, give it a ⭐ on GitHub!*

</div>
