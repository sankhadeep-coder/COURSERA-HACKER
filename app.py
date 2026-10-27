import sys
import base64
import os
import json
import ctypes
import ctypes.wintypes
from datetime import datetime

import requests
from PySide6.QtCore import (
    Qt, QThread, Signal, QBuffer, QByteArray, QIODevice,
    QTimer, QSize, QEvent
)
from PySide6.QtGui import (
    QGuiApplication, QPixmap, QImage, QCursor, QPainter
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QComboBox, QMessageBox,
    QFileDialog, QCheckBox, QFrame, QScrollArea, QDialog, QSizePolicy
)

DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Colour Palette
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class C:
    BG_DEEP       = "#0a0a0f"
    BG_PRIMARY    = "#0f1117"
    BG_SECONDARY  = "#161822"
    BG_CARD       = "#1a1d2e"
    BG_INPUT      = "#1e2235"
    BG_HOVER      = "#252940"

    ACCENT        = "#6c63ff"
    ACCENT_LIGHT  = "#8b83ff"
    ACCENT_DARK   = "#4f46e5"

    GREEN         = "#10b981"
    GREEN_DARK    = "#059669"
    RED           = "#ef4444"
    AMBER         = "#f59e0b"
    CYAN          = "#06b6d4"

    TEXT_PRIMARY   = "#e8eaed"
    TEXT_SECONDARY = "#9aa0b8"
    TEXT_MUTED     = "#5c6382"

    BORDER        = "#2a2e45"
    BORDER_LIGHT  = "#363b58"

    USER_BUBBLE   = "#6c63ff"
    AI_BUBBLE     = "#1e2235"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API Workers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class StreamWorker(QThread):
    """Streams tokens from the LM Studio /chat/completions endpoint."""
    token_received = Signal(str)
    finished_text = Signal(str)
    failed = Signal(str)

    def __init__(self, base_url, model, messages, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.messages = messages

    def run(self):
        full_text = ""
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": self.messages,
                    "temperature": 0.6,
                    "stream": True,
                },
                timeout=300,
                stream=True,
            )
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content", "")
                    if token:
                        full_text += token
                        self.token_received.emit(token)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

            self.finished_text.emit(full_text.strip())

        except requests.exceptions.ConnectionError:
            self.failed.emit(
                "Could not connect to LM Studio.\n\n"
                "Open LM Studio → Developer → start the local server.\n"
                "Default address: http://127.0.0.1:1234"
            )
        except Exception as exc:
            self.failed.emit(f"Request failed: {exc}")


class ModelsWorker(QThread):
    models_ready = Signal(list)
    failed = Signal(str)

    def __init__(self, base_url, parent=None):
        super().__init__(parent)
        self.base_url = base_url.rstrip("/")

    def run(self):
        try:
            r = requests.get(f"{self.base_url}/models", timeout=10)
            r.raise_for_status()
            items = r.json().get("data", [])
            self.models_ready.emit([m.get("id", "") for m in items if m.get("id")])
        except Exception as exc:
            self.failed.emit(str(exc))


class VoiceWorker(QThread):
    transcript_ready = Signal(str)
    failed = Signal(str)
    status = Signal(str)

    def run(self):
        try:
            import sounddevice as sd
            import numpy as np
            from faster_whisper import WhisperModel

            seconds = 8
            sample_rate = 16000
            self.status.emit("Recording for 8s… speak now")
            recording = sd.rec(
                int(seconds * sample_rate),
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
            )
            sd.wait()
            self.status.emit("Transcribing locally…")
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(recording.flatten(), language=None)
            text = " ".join(seg.text.strip() for seg in segments).strip()
            if not text:
                self.failed.emit("No speech detected. Try again closer to your mic.")
            else:
                self.transcript_ready.emit(text)
        except ImportError:
            self.failed.emit(
                "Voice dependencies not installed.\n\n"
                "Run: pip install sounddevice numpy faster-whisper"
            )
        except Exception as exc:
            self.failed.emit(f"Voice input failed: {exc}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Screenshot Preview Dialog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ScreenshotPreviewDialog(QDialog):
    """Shows a captured screenshot and lets the user accept or discard it."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Screenshot Preview")
        self.setMinimumSize(700, 500)
        self.resize(900, 620)
        self.setModal(True)
        self.result_data_url = None
        self._pixmap = pixmap

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ──
        header = QFrame()
        header.setFixedHeight(52)
        header.setStyleSheet(f"background: {C.BG_PRIMARY}; border-bottom: 1px solid {C.BORDER};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(20, 0, 20, 0)

        title = QLabel("Screenshot Preview")
        title.setStyleSheet(f"color: {C.TEXT_PRIMARY}; font-size: 15px; font-weight: 700;")
        h_layout.addWidget(title)
        h_layout.addStretch()

        size_label = QLabel(f"{pixmap.width()} × {pixmap.height()} px")
        size_label.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 12px;")
        h_layout.addWidget(size_label)

        layout.addWidget(header)

        # ── Image preview area ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {C.BG_DEEP};
                border: none;
            }}
            QScrollBar:vertical, QScrollBar:horizontal {{
                background: transparent; width: 8px; height: 8px;
            }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: {C.BORDER}; border-radius: 4px; min-height: 30px; min-width: 30px;
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
        """)

        preview_container = QWidget()
        preview_container.setStyleSheet(f"background: {C.BG_DEEP};")
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.setContentsMargins(20, 20, 20, 20)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Scale to fit nicely
        scaled = pixmap.scaled(
            QSize(840, 520),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setStyleSheet(f"""
            border: 2px solid {C.BORDER};
            border-radius: 8px;
            padding: 4px;
            background: {C.BG_CARD};
        """)
        preview_layout.addWidget(self.image_label)

        scroll.setWidget(preview_container)
        layout.addWidget(scroll, 1)

        # ── Footer with buttons ──
        footer = QFrame()
        footer.setFixedHeight(64)
        footer.setStyleSheet(f"background: {C.BG_PRIMARY}; border-top: 1px solid {C.BORDER};")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(20, 0, 20, 0)
        f_layout.setSpacing(12)

        hint = QLabel("Review the screenshot before attaching it to your message.")
        hint.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 12px;")
        f_layout.addWidget(hint)
        f_layout.addStretch()

        discard_btn = QPushButton("  Discard")
        discard_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        discard_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.BG_CARD}; color: {C.TEXT_SECONDARY};
                border: 1px solid {C.BORDER}; border-radius: 10px;
                padding: 10px 24px; font-weight: 600; font-size: 13px;
            }}
            QPushButton:hover {{ background: {C.BG_HOVER}; color: {C.RED}; }}
        """)
        discard_btn.clicked.connect(self.reject)
        f_layout.addWidget(discard_btn)

        attach_btn = QPushButton("  Attach Screenshot")
        attach_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        attach_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.ACCENT}; color: white;
                border: none; border-radius: 10px;
                padding: 10px 24px; font-weight: 600; font-size: 13px;
            }}
            QPushButton:hover {{ background: {C.ACCENT_DARK}; }}
        """)
        attach_btn.clicked.connect(self._accept_screenshot)
        f_layout.addWidget(attach_btn)

        layout.addWidget(footer)

        # Dialog styling
        self.setStyleSheet(f"""
            QDialog {{
                background: {C.BG_DEEP};
                color: {C.TEXT_PRIMARY};
                font-family: 'Segoe UI', 'SF Pro Display', system-ui, sans-serif;
            }}
        """)

    def _accept_screenshot(self):
        byte_array = QByteArray()
        qbuffer = QBuffer(byte_array)
        qbuffer.open(QIODevice.OpenModeFlag.WriteOnly)
        self._pixmap.save(qbuffer, "PNG")
        qbuffer.close()
        encoded = base64.b64encode(byte_array.data()).decode("ascii")
        self.result_data_url = "data:image/png;base64," + encoded
        self.accept()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Chat Bubble Widget
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class ChatBubble(QFrame):
    def __init__(self, sender: str, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self.full_text = text
        self._sender = sender

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # Header row: avatar + name + time
        header = QHBoxLayout()
        header.setSpacing(8)

        avatar = QLabel("Y" if is_user else "AI")
        avatar.setFixedSize(26, 26)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_bg = C.USER_BUBBLE if is_user else C.GREEN
        avatar.setStyleSheet(
            f"background: {avatar_bg}; color: white; border-radius: 13px;"
            f" font-size: 10px; font-weight: 700; border: none;"
        )

        name = QLabel(sender)
        name.setStyleSheet(
            f"color: {C.TEXT_PRIMARY}; font-weight: 600; font-size: 13px; border: none; background: transparent;"
        )

        ts = QLabel(datetime.now().strftime("%H:%M"))
        ts.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: 11px; border: none; background: transparent;"
        )

        header.addWidget(avatar)
        header.addWidget(name)
        header.addStretch()
        header.addWidget(ts)
        layout.addLayout(header)

        # Body
        self.body = QLabel(text)
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.setStyleSheet(
            f"color: {C.TEXT_PRIMARY}; font-size: 13px; padding: 2px 0;"
            f" border: none; background: transparent;"
        )
        self.body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.body)

        # Bubble frame styling
        if is_user:
            bg = "#1a1545"
            border_col = C.ACCENT + "40"
            margin = "2px 40px 2px 8px"
        else:
            bg = C.BG_CARD
            border_col = C.BORDER
            margin = "2px 8px 2px 40px"

        self.setStyleSheet(
            f"ChatBubble {{ background: {bg}; border: 1px solid {border_col};"
            f" border-radius: 12px; margin: {margin}; }}"
        )

    def update_text(self, text):
        self.full_text = text
        self.body.setText(text)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Typing Indicator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class TypingIndicator(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(60, 8, 20, 8)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._dots = []
        for _ in range(3):
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 14px; background: transparent; border: none;")
            dot.setFixedWidth(16)
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(dot)
            self._dots.append(dot)
        layout.addStretch()

        self._phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)

    def start_animation(self):
        self.show()
        self._timer.start(300)

    def stop_animation(self):
        self._timer.stop()
        self.hide()

    def _animate(self):
        for i, dot in enumerate(self._dots):
            if i == (self._phase % 3):
                dot.setStyleSheet(f"color: {C.ACCENT}; font-size: 16px; background: transparent; border: none;")
            else:
                dot.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 14px; background: transparent; border: none;")
        self._phase += 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Themed Button
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _make_btn(text, accent=False):
    btn = QPushButton(text)
    if accent:
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.ACCENT}; color: white;
                border: none; border-radius: 10px;
                padding: 10px 18px; font-weight: 600; font-size: 13px;
            }}
            QPushButton:hover {{ background: {C.ACCENT_DARK}; }}
            QPushButton:disabled {{ background: {C.BG_SECONDARY}; color: {C.TEXT_MUTED}; }}
        """)
    else:
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.BG_CARD}; color: {C.TEXT_PRIMARY};
                border: 1px solid {C.BORDER}; border-radius: 10px;
                padding: 10px 18px; font-weight: 600; font-size: 13px;
            }}
            QPushButton:hover {{ background: {C.BG_HOVER}; }}
            QPushButton:disabled {{ background: {C.BG_SECONDARY}; color: {C.TEXT_MUTED}; }}
        """)
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    return btn


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Status Pill
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class StatusPill(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(32)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(14)
        self._label = QLabel("Disconnected")
        self._label.setStyleSheet(f"color: {C.TEXT_SECONDARY}; font-size: 12px; border: none; background: transparent;")

        layout.addWidget(self._dot)
        layout.addWidget(self._label)
        layout.addStretch()

        self.set_status("disconnected")

    def set_status(self, status, text=None):
        color_map = {
            "connected": C.GREEN,
            "disconnected": C.RED,
            "loading": C.AMBER,
            "generating": C.CYAN,
        }
        color = color_map.get(status, C.TEXT_MUTED)
        self._dot.setStyleSheet(f"color: {color}; font-size: 12px; border: none; background: transparent;")
        self._label.setText(text if text else status.capitalize())
        self.setStyleSheet(
            f"StatusPill {{ background: {C.BG_CARD}; border: 1px solid {C.BORDER}; border-radius: 16px; }}"
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main Window
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LocalDesk AI")
        self.resize(1060, 760)
        self.setMinimumSize(780, 580)
        self.base_url = DEFAULT_BASE_URL
        self.history: list[dict] = []
        self.pending_image: str | None = None
        self.busy = False
        self.worker = None
        self._ai_bubble: ChatBubble | None = None
        self._bubbles: list[ChatBubble] = []
        self._hidden_from_capture = False

        self._build_ui()
        self._apply_global_style()

        # Auto-connect on launch
        QTimer.singleShot(600, self.refresh_models)

    # hide from screen share as soon as the native HWND exists
    def showEvent(self, event):
        super().showEvent(event)
        if self._hidden_from_capture:
            self._set_capture_exclusion(True)

    def _set_capture_exclusion(self, hide: bool):
        """Hide/show this window from ALL screen capture tools AND the taskbar."""
        try:
            hwnd = int(self.winId())

            # ── 1. Hide from screen-capture (SetWindowDisplayAffinity) ──
            # WDA_EXCLUDEFROMCAPTURE = 0x11 (Windows 10 v2004+)
            affinity = 0x00000011 if hide else 0x00000000
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, affinity)

            # ── 2. Hide from taskbar (extended window style trick) ──
            GWL_EXSTYLE    = -20
            WS_EX_TOOLWINDOW = 0x00000080   # hides from taskbar
            WS_EX_APPWINDOW  = 0x00040000   # forces onto taskbar
            SWP_NOMOVE     = 0x0002
            SWP_NOSIZE     = 0x0001
            SWP_NOZORDER   = 0x0004
            SWP_FRAMECHANGED = 0x0020

            GetWindowLongPtr = ctypes.windll.user32.GetWindowLongPtrW
            SetWindowLongPtr = ctypes.windll.user32.SetWindowLongPtrW
            SetWindowPos     = ctypes.windll.user32.SetWindowPos

            ex_style = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
            if hide:
                ex_style = (ex_style | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
            else:
                ex_style = (ex_style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            SetWindowLongPtr(hwnd, GWL_EXSTYLE, ex_style)
            # Flush the style change so taskbar updates immediately
            SetWindowPos(hwnd, None, 0, 0, 0, 0,
                         SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)

        except Exception as exc:
            self.status_pill.set_status("disconnected", f"Capture-hide error: {exc}")

    @staticmethod
    def _apply_affinity_to_hwnd(hwnd: int, hide: bool):
        """Apply SetWindowDisplayAffinity to any arbitrary HWND."""
        affinity = 0x00000011 if hide else 0x00000000
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, affinity)

    def _toggle_capture_hide(self, state):
        self._hidden_from_capture = bool(state)
        self._set_capture_exclusion(self._hidden_from_capture)
        if self._hidden_from_capture:
            self.status_pill.set_status("connected", "Hidden from screen share")
        else:
            self.status_pill.set_status("connected", "Visible to screen share")

    # ──────────────────────────────────────────────────────────────
    #  Build UI
    # ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── LEFT SIDEBAR ─────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(260)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(16, 20, 16, 16)
        sb.setSpacing(10)

        # Logo
        logo_row = QHBoxLayout()
        logo_icon = QLabel("◆")
        logo_icon.setStyleSheet(f"color: {C.ACCENT}; font-size: 22px; background: transparent;")
        logo_text = QLabel("LocalDesk AI")
        logo_text.setStyleSheet(f"color: {C.TEXT_PRIMARY}; font-size: 18px; font-weight: 700; background: transparent;")
        logo_row.addWidget(logo_icon)
        logo_row.addWidget(logo_text)
        logo_row.addStretch()
        sb.addLayout(logo_row)

        tagline = QLabel("Your private local assistant")
        tagline.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 11px; background: transparent;")
        sb.addWidget(tagline)

        sb.addWidget(self._divider())

        # Connection
        sb.addWidget(self._section_title("CONNECTION"))
        self.status_pill = StatusPill()
        sb.addWidget(self.status_pill)

        sb.addWidget(self._field_label("Server URL"))
        self.server_input = QLineEdit(DEFAULT_BASE_URL)
        self.server_input.setObjectName("fieldInput")
        sb.addWidget(self.server_input)

        sb.addWidget(self._field_label("Active Model"))
        self.model_combo = QComboBox()
        self.model_combo.setObjectName("fieldCombo")
        sb.addWidget(self.model_combo)

        self.refresh_btn = _make_btn("⟳  Refresh Models")
        self.refresh_btn.clicked.connect(self.refresh_models)
        sb.addWidget(self.refresh_btn)

        sb.addWidget(self._divider())

        # Tools
        sb.addWidget(self._section_title("TOOLS"))

        self.screenshot_btn = _make_btn("📷  Capture Screen")
        self.screenshot_btn.clicked.connect(self.capture_screen)
        sb.addWidget(self.screenshot_btn)

        self.attach_btn = _make_btn("📎  Attach Image")
        self.attach_btn.clicked.connect(self.attach_image)
        sb.addWidget(self.attach_btn)

        self.voice_btn = _make_btn("🎙  Voice Input (8s)")
        self.voice_btn.clicked.connect(self.record_voice)
        sb.addWidget(self.voice_btn)

        sb.addStretch()

        # ── Hide from screen share ──
        self.capture_hide_cb = QCheckBox("  Hide from screen share")
        self.capture_hide_cb.setStyleSheet(
            f"color: {C.ACCENT_LIGHT}; font-size: 12px; font-weight: 600;"
        )
        self.capture_hide_cb.setToolTip(
            "When checked, this window will be invisible\n"
            "to all screen-capture and recording tools.\n"
            "Requires Windows 10 v2004 or later."
        )
        self.capture_hide_cb.stateChanged.connect(self._toggle_capture_hide)
        sb.addWidget(self.capture_hide_cb)

        self.topmost_cb = QCheckBox("  Always on top")
        self.topmost_cb.setStyleSheet(f"color: {C.TEXT_SECONDARY}; font-size: 12px;")
        self.topmost_cb.stateChanged.connect(self._toggle_topmost)
        sb.addWidget(self.topmost_cb)

        self.clear_btn = _make_btn("🗑  Clear Chat")
        self.clear_btn.clicked.connect(self.clear_chat)
        sb.addWidget(self.clear_btn)

        root.addWidget(sidebar)

        # ── MAIN CHAT AREA ───────────────────────────────────────
        chat_panel = QWidget()
        chat_panel.setObjectName("chatPanel")
        cp = QVBoxLayout(chat_panel)
        cp.setContentsMargins(0, 0, 0, 0)
        cp.setSpacing(0)

        # Header bar
        chat_header = QWidget()
        chat_header.setObjectName("chatHeader")
        chat_header.setFixedHeight(52)
        ch = QHBoxLayout(chat_header)
        ch.setContentsMargins(24, 0, 24, 0)

        self.model_display = QLabel("No model loaded")
        self.model_display.setStyleSheet(f"color: {C.TEXT_PRIMARY}; font-size: 14px; font-weight: 600; background: transparent;")
        ch.addWidget(self.model_display)
        ch.addStretch()

        self.header_status = QLabel("")
        self.header_status.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 12px; background: transparent;")
        ch.addWidget(self.header_status)

        cp.addWidget(chat_header)

        # Scrollable chat
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("chatScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._chat_widget = QWidget()
        self._chat_widget.setObjectName("chatWidget")
        self._chat_vbox = QVBoxLayout(self._chat_widget)
        self._chat_vbox.setContentsMargins(16, 16, 16, 16)
        self._chat_vbox.setSpacing(8)

        # Welcome card
        self._welcome = self._build_welcome()
        self._chat_vbox.addWidget(self._welcome)
        self._chat_vbox.addStretch()

        self.scroll_area.setWidget(self._chat_widget)
        cp.addWidget(self.scroll_area, 1)

        # Image attachment banner
        self._img_banner = QWidget()
        self._img_banner.setObjectName("imgBanner")
        self._img_banner.setFixedHeight(38)
        self._img_banner.hide()
        ib = QHBoxLayout(self._img_banner)
        ib.setContentsMargins(24, 0, 24, 0)

        self._img_label = QLabel("")
        self._img_label.setStyleSheet(f"color: {C.GREEN}; font-size: 12px; background: transparent;")
        ib.addWidget(self._img_label)
        ib.addStretch()

        remove_btn = QPushButton("✕ Remove")
        remove_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        remove_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {C.RED}; border: none;"
            f" font-size: 12px; font-weight: 600; }}"
            f" QPushButton:hover {{ color: #ff6b6b; }}"
        )
        remove_btn.clicked.connect(self._remove_image)
        ib.addWidget(remove_btn)
        cp.addWidget(self._img_banner)

        # Typing indicator
        self.typing_indicator = TypingIndicator()
        self.typing_indicator.hide()
        cp.addWidget(self.typing_indicator)

        # Input bar
        input_bar = QWidget()
        input_bar.setObjectName("inputBar")
        inp = QHBoxLayout(input_bar)
        inp.setContentsMargins(20, 12, 20, 14)
        inp.setSpacing(12)

        self.prompt = QTextEdit()
        self.prompt.setObjectName("prompt")
        self.prompt.setPlaceholderText("Message LocalDesk AI…   (Ctrl+Enter to send)")
        self.prompt.setFixedHeight(52)
        self.prompt.installEventFilter(self)
        inp.addWidget(self.prompt, 1)

        self.send_btn = _make_btn("Send  ➤", accent=True)
        self.send_btn.setFixedSize(100, 52)
        self.send_btn.clicked.connect(self.send_message)
        inp.addWidget(self.send_btn)

        cp.addWidget(input_bar)

        # Footer
        footer = QLabel(
            "🔒  All requests stay on your machine  ·  Screenshots capture the full desktop"
        )
        footer.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 10px; padding: 2px 24px 8px 24px; background: transparent;")
        footer.setWordWrap(True)
        cp.addWidget(footer)

        root.addWidget(chat_panel, 1)

    # ── small UI helpers ──────────────────────────────────────────
    @staticmethod
    def _divider():
        d = QFrame()
        d.setFixedHeight(1)
        d.setStyleSheet(f"background: {C.BORDER};")
        return d

    @staticmethod
    def _section_title(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {C.TEXT_MUTED}; font-size: 10px; font-weight: 700;"
            f" letter-spacing: 1px; background: transparent;"
        )
        return lbl

    @staticmethod
    def _field_label(text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {C.TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        return lbl

    def _build_welcome(self):
        w = QWidget()
        w.setObjectName("welcome")
        wl = QVBoxLayout(w)
        wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wl.setSpacing(12)
        wl.setContentsMargins(40, 60, 40, 60)

        icon = QLabel("◆")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"color: {C.ACCENT}; font-size: 48px; background: transparent;")
        wl.addWidget(icon)

        title = QLabel("Welcome to LocalDesk AI")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {C.TEXT_PRIMARY}; font-size: 22px; font-weight: 700; background: transparent;")
        wl.addWidget(title)

        sub = QLabel(
            "Ask anything — everything runs locally on your machine.\n"
            "Capture your screen, attach images, or use voice input."
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {C.TEXT_MUTED}; font-size: 13px; background: transparent;")
        wl.addWidget(sub)

        return w

    # ── global stylesheet ─────────────────────────────────────────
    def _apply_global_style(self):
        self.setStyleSheet(f"""
            * {{
                font-family: 'Segoe UI', 'SF Pro Display', system-ui, sans-serif;
                font-size: 13px;
            }}
            QMainWindow, QWidget#sidebar, QWidget#chatPanel,
            QWidget#chatHeader, QWidget#inputBar, QWidget#imgBanner,
            QWidget#chatWidget, QWidget#welcome {{
                border: none;
            }}
            QMainWindow {{ background: {C.BG_DEEP}; }}

            QWidget#sidebar {{
                background: {C.BG_PRIMARY};
                border-right: 1px solid {C.BORDER};
            }}
            QWidget#chatPanel {{ background: {C.BG_DEEP}; }}
            QWidget#chatHeader {{
                background: {C.BG_PRIMARY};
                border-bottom: 1px solid {C.BORDER};
            }}
            QWidget#chatWidget {{ background: {C.BG_DEEP}; }}
            QWidget#inputBar {{
                background: {C.BG_PRIMARY};
                border-top: 1px solid {C.BORDER};
            }}
            QWidget#imgBanner {{
                background: {C.BG_CARD};
                border-top: 1px solid {C.BORDER};
            }}

            QScrollArea#chatScroll {{
                background: {C.BG_DEEP};
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 8px;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER}; min-height: 40px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {C.BORDER_LIGHT}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

            QLineEdit#fieldInput, QComboBox#fieldCombo {{
                background: {C.BG_INPUT}; border: 1px solid {C.BORDER};
                border-radius: 8px; padding: 8px 12px;
                color: {C.TEXT_PRIMARY}; font-size: 12px;
            }}
            QLineEdit#fieldInput:focus {{ border-color: {C.ACCENT}; }}
            QComboBox#fieldCombo::drop-down {{ border: none; width: 20px; }}
            QComboBox#fieldCombo QAbstractItemView {{
                background: {C.BG_CARD}; border: 1px solid {C.BORDER};
                color: {C.TEXT_PRIMARY}; selection-background-color: {C.ACCENT};
            }}

            QTextEdit#prompt {{
                background: {C.BG_INPUT}; border: 1px solid {C.BORDER};
                border-radius: 12px; padding: 14px 16px;
                color: {C.TEXT_PRIMARY}; font-size: 14px;
                selection-background-color: {C.ACCENT};
            }}
            QTextEdit#prompt:focus {{ border-color: {C.ACCENT}; }}
        """)

    # ──────────────────────────────────────────────────────────────
    #  Events
    # ──────────────────────────────────────────────────────────────
    def eventFilter(self, obj, event):
        if obj is self.prompt and event.type() == QEvent.Type.KeyPress:
            if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                    and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self.send_message()
                return True
        return super().eventFilter(obj, event)

    def _toggle_topmost(self, state):
        visible = self.isVisible()
        flags = self.windowFlags()
        if state:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if visible:
            self.show()

    def _scroll_bottom(self):
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))

    # ──────────────────────────────────────────────────────────────
    #  Model management
    # ──────────────────────────────────────────────────────────────
    def current_server(self):
        return self.server_input.text().strip().rstrip("/")

    def refresh_models(self):
        self.base_url = self.current_server()
        if not self.base_url:
            self.status_pill.set_status("disconnected", "No server URL")
            return
        self.status_pill.set_status("loading", "Connecting…")
        self.refresh_btn.setEnabled(False)
        self._mw = ModelsWorker(self.base_url)
        self._mw.models_ready.connect(self._on_models)
        self._mw.failed.connect(self._on_models_fail)
        self._mw.finished.connect(lambda: self.refresh_btn.setEnabled(True))
        self._mw.start()

    def _on_models(self, models):
        self.model_combo.clear()
        self.model_combo.addItems(models)
        if models:
            self.status_pill.set_status("connected", f"{len(models)} model(s) ready")
            pretty = models[0].split("/")[-1] if "/" in models[0] else models[0]
            self.model_display.setText(f"●  {pretty}")
        else:
            self.status_pill.set_status("disconnected", "No models loaded")
            self.model_display.setText("No model loaded")

    def _on_models_fail(self, err):
        self.status_pill.set_status("disconnected", "Connection failed")
        QMessageBox.warning(self, "LM Studio Connection", err)

    # ──────────────────────────────────────────────────────────────
    #  Chat
    # ──────────────────────────────────────────────────────────────
    def _add_bubble(self, sender, text, is_user) -> ChatBubble:
        if self._welcome.isVisible():
            self._welcome.hide()

        bubble = ChatBubble(sender, text, is_user)
        # Insert before the trailing stretch
        idx = self._chat_vbox.count() - 1
        self._chat_vbox.insertWidget(idx, bubble)
        self._bubbles.append(bubble)
        self._scroll_bottom()
        return bubble

    def send_message(self):
        if self.busy:
            return
        text = self.prompt.toPlainText().strip()
        if not text and not self.pending_image:
            return
        if self.model_combo.count() == 0:
            QMessageBox.information(self, "No Model", "Start LM Studio and click Refresh Models first.")
            return

        # Build API content
        parts = []
        if text:
            parts.append({"type": "text", "text": text})
        if self.pending_image:
            parts.append({"type": "image_url", "image_url": {"url": self.pending_image}})

        content = parts[0]["text"] if len(parts) == 1 and parts[0]["type"] == "text" else parts

        # User bubble
        display = text if text else "[Image attached]"
        if self.pending_image:
            display += "\n📎 Image attached"
        self._add_bubble("You", display, is_user=True)

        self.history.append({"role": "user", "content": content})
        self.prompt.clear()
        self.pending_image = None
        self._img_banner.hide()

        # Go busy
        self.busy = True
        self.send_btn.setEnabled(False)
        self.status_pill.set_status("generating", "Generating…")
        self.header_status.setText("Generating response…")
        self.typing_indicator.start_animation()

        # AI bubble (streaming)
        self._ai_bubble = self._add_bubble("LocalDesk AI", "", is_user=False)

        self.worker = StreamWorker(
            self.current_server(),
            self.model_combo.currentText(),
            self.history.copy(),
        )
        self.worker.token_received.connect(self._on_token)
        self.worker.finished_text.connect(self._on_answer)
        self.worker.failed.connect(self._on_fail)
        self.worker.finished.connect(self._on_done)
        self.worker.start()

    def _on_token(self, token):
        if self._ai_bubble:
            self._ai_bubble.full_text += token
            self._ai_bubble.update_text(self._ai_bubble.full_text)
            self._scroll_bottom()

    def _on_answer(self, answer):
        self.history.append({"role": "assistant", "content": answer})
        if self._ai_bubble:
            self._ai_bubble.update_text(answer)
        self.typing_indicator.stop_animation()
        self.status_pill.set_status("connected", "Ready")
        self.header_status.setText("")
        self._ai_bubble = None

    def _on_fail(self, err):
        self.typing_indicator.stop_animation()
        self.status_pill.set_status("disconnected", "Request failed")
        self.header_status.setText("")
        QMessageBox.warning(self, "Local AI Request", err)
        if self.history and self.history[-1].get("role") == "user":
            self.history.pop()
        if self._ai_bubble:
            self._ai_bubble.setParent(None)
            self._ai_bubble.deleteLater()
            if self._ai_bubble in self._bubbles:
                self._bubbles.remove(self._ai_bubble)
            self._ai_bubble = None

    def _on_done(self):
        self.busy = False
        self.send_btn.setEnabled(True)

    # ──────────────────────────────────────────────────────────────
    #  Screenshot (with preview)
    # ──────────────────────────────────────────────────────────────
    def capture_screen(self):
        # Minimise so we don't capture ourselves
        self.showMinimized()
        QTimer.singleShot(400, self._do_capture)

    def _do_capture(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.showNormal()
            QMessageBox.warning(self, "Screenshot", "No display screen detected.")
            return
        pixmap = screen.grabWindow(0)
        self.showNormal()
        self.activateWindow()

        if pixmap.isNull():
            QMessageBox.warning(self, "Screenshot", "Could not capture the screen.")
            return

        dlg = ScreenshotPreviewDialog(pixmap, parent=self)

        # If capture-hide is active, apply it to the preview dialog HWND too,
        # so the preview window is never visible to screen-recording tools.
        if self._hidden_from_capture:
            # We need the native HWND — it's created when the dialog is shown,
            # so call winId() after exec() starts via a singleShot.
            def _hide_dlg():
                try:
                    self._apply_affinity_to_hwnd(int(dlg.winId()), True)
                except Exception:
                    pass
            QTimer.singleShot(0, _hide_dlg)

        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_data_url:
            self.pending_image = dlg.result_data_url
            self._img_label.setText("📷  Full-screen screenshot attached")
            self._img_banner.show()
            self.status_pill.set_status("connected", "Screenshot attached")
        else:
            self.status_pill.set_status("connected", "Screenshot discarded")

    # ──────────────────────────────────────────────────────────────
    #  Attach image / voice
    # ──────────────────────────────────────────────────────────────
    def attach_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                raw = f.read()
            ext = path.lower().rsplit(".", 1)[-1]
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            self.pending_image = f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")
            self._img_label.setText(f"📎  {os.path.basename(path)}")
            self._img_banner.show()
        except Exception as exc:
            QMessageBox.warning(self, "Image Attachment", str(exc))

    def _remove_image(self):
        self.pending_image = None
        self._img_banner.hide()

    def record_voice(self):
        if not self.voice_btn.isEnabled():
            return
        self.voice_btn.setEnabled(False)
        self.status_pill.set_status("loading", "Listening…")
        self._vw = VoiceWorker()
        self._vw.status.connect(lambda s: self.status_pill.set_status("loading", s))
        self._vw.transcript_ready.connect(self._on_voice)
        self._vw.failed.connect(lambda e: QMessageBox.warning(self, "Voice Input", e))
        self._vw.finished.connect(lambda: self.voice_btn.setEnabled(True))
        self._vw.finished.connect(lambda: self.status_pill.set_status("connected", "Ready"))
        self._vw.start()

    def _on_voice(self, text):
        existing = self.prompt.toPlainText().strip()
        self.prompt.setPlainText((existing + "\n" if existing else "") + text)
        self.status_pill.set_status("connected", "Transcription added")

    # ──────────────────────────────────────────────────────────────
    #  Clear chat
    # ──────────────────────────────────────────────────────────────
    def clear_chat(self):
        self.history.clear()
        self.pending_image = None
        self._img_banner.hide()

        # Remove every bubble
        for bubble in self._bubbles:
            bubble.setParent(None)
            bubble.deleteLater()
        self._bubbles.clear()
        self._ai_bubble = None

        self._welcome.show()
        self.status_pill.set_status("connected", "Chat cleared")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Entry Point
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LocalDesk AI")
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
