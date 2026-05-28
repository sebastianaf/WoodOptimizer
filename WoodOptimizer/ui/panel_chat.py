"""
Chat panel — AI design assistant.
Controls: Send, Stop, Clear, multiline input.
Config lives in the Settings tab; this panel just reads it on every tab switch.
"""
from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, Signal, QThread
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtCore import Qt, Signal, QThread


# ─── Worker ───────────────────────────────────────────────────────────────────

class _LLMWorker(QThread):
    chunk_ready   = Signal(str)
    tool_executed = Signal(str)
    error         = Signal(str)

    def __init__(self, client, message: str, history: list[dict], parent=None):
        super().__init__(parent)
        self._client  = client
        self._message = message
        self._history = history
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            def on_tool(name, args, result_json):
                self.tool_executed.emit(name)

            for fragment in self._client.stream_chat(
                self._message, self._history, on_tool_call=on_tool
            ):
                if self._cancelled:
                    break
                self.chunk_ready.emit(fragment)
        except Exception as e:
            self.error.emit(str(e))


# ─── Chat panel ───────────────────────────────────────────────────────────────

class ChatPanel(QtWidgets.QWidget):
    """
    Assistant chat panel.

    Layout:
    ┌─ model indicator ──────────────────── [Clear] ┐
    ├───────────────────────────────────────────────┤
    │  chat history (read-only)                     │
    ├───────────────────────────────────────────────┤
    │  [multiline input]              [Stop] [Send] │
    │  status bar                                   │
    └───────────────────────────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[dict] = []
        self._worker: _LLMWorker | None = None
        self._client = None
        self._pending_user_msg = ""
        self._current_assistant_text = ""
        self._build_ui()
        self.reload_client()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        # ── Chat display ──────────────────────────────────────────────────────
        self._chat_display = QtWidgets.QTextEdit()
        self._chat_display.setReadOnly(True)
        font = QtGui.QFont("Monospace", 10)
        font.setStyleHint(QtGui.QFont.TypeWriter)
        self._chat_display.setFont(font)
        root.addWidget(self._chat_display, stretch=1)

        # ── Input area ────────────────────────────────────────────────────────
        self._txt_input = QtWidgets.QTextEdit()
        self._txt_input.setPlaceholderText(
            "e.g.: design a 60×240 closet with 3 shelves and bottom drawer"
        )
        self._txt_input.setMaximumHeight(80)
        self._txt_input.setAcceptRichText(False)
        # Ctrl+Enter or Shift+Enter → newline; Enter alone → send
        self._txt_input.installEventFilter(self)
        root.addWidget(self._txt_input)

        # ── Button row ────────────────────────────────────────────────────────
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()

        btn_clear = QtWidgets.QPushButton("Clear")
        btn_clear.setFixedWidth(54)
        btn_clear.setToolTip("Clear conversation history")
        btn_clear.clicked.connect(self._clear)
        btn_row.addWidget(btn_clear)

        self._btn_stop = QtWidgets.QPushButton("Stop")
        self._btn_stop.setFixedWidth(54)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._stop)
        btn_row.addWidget(self._btn_stop)

        self._btn_send = QtWidgets.QPushButton("Send")
        self._btn_send.setFixedWidth(64)
        self._btn_send.setDefault(True)
        self._btn_send.clicked.connect(self._send)
        btn_row.addWidget(self._btn_send)

        root.addLayout(btn_row)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = QtWidgets.QLabel("Ready.")
        self._status.setStyleSheet("color: gray; font-size: 10px;")
        root.addWidget(self._status)

    # ── Enter key filter ──────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._txt_input and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                mods = event.modifiers()
                if mods & (Qt.ShiftModifier | Qt.ControlModifier):
                    return False  # let QTextEdit insert newline
                self._send()
                return True
        return super().eventFilter(obj, event)

    # ── Client ────────────────────────────────────────────────────────────────

    def reload_client(self):
        """Rebuild the LLM client from saved config. Called by MainPanel on tab switch."""
        from ..llm.config import load_config
        from ..llm.client import LLMClient
        from ..llm.providers.ollama import OllamaProvider
        from ..llm.providers.openai_compat import OpenAICompatProvider

        cfg = load_config()
        if cfg.provider == "ollama":
            provider = OllamaProvider(url=cfg.url)
        else:
            provider = OpenAICompatProvider(url=cfg.url, api_key=cfg.api_key)
        self._client = LLMClient(provider=provider, model=cfg.model)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _send(self):
        text = self._txt_input.toPlainText().strip()
        if not text or self._worker is not None:
            return

        if self._client is None:
            self.reload_client()

        self._pending_user_msg = text
        self._txt_input.clear()
        self._btn_send.setEnabled(False)
        self._btn_stop.setEnabled(True)
        self._status.setText("Processing…")
        self._append_message("user", text)

        self._current_assistant_text = ""
        self._chat_display.append("\n<b>Assistant:</b> ")

        self._worker = _LLMWorker(self._client, text, self._history, parent=self)
        self._worker.chunk_ready.connect(self._on_chunk)
        self._worker.tool_executed.connect(self._on_tool)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

    def _stop(self):
        if self._worker is not None:
            self._worker.cancel()
            self._status.setText("Stopped.")

    def _clear(self):
        self._history.clear()
        self._chat_display.clear()
        self._status.setText("Conversation cleared.")

    # ── Worker callbacks ──────────────────────────────────────────────────────

    def _on_chunk(self, fragment: str):
        self._current_assistant_text += fragment
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(fragment)
        self._chat_display.setTextCursor(cursor)
        self._chat_display.ensureCursorVisible()

    def _on_tool(self, name: str):
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(f'<br><span style="color:#888">&nbsp;&nbsp;⚙ {name}…</span>')
        self._chat_display.setTextCursor(cursor)

    def _on_error(self, msg: str):
        self._chat_display.append(
            f'<br><span style="color:#c0392b"><b>Error:</b> {msg}</span>'
        )
        self._chat_display.ensureCursorVisible()

    def _on_worker_done(self):
        # Save user message captured at send time (input was already cleared)
        self._history.append({"role": "user", "content": self._pending_user_msg})
        self._history.append({"role": "assistant", "content": self._current_assistant_text})
        self._worker = None
        self._btn_send.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._status.setText("Ready.")

    # ── Display helpers ───────────────────────────────────────────────────────

    def _append_message(self, role: str, text: str):
        colors = {"user": "#005f87"}
        labels = {"user": "You"}
        color = colors.get(role, "#333")
        label = labels.get(role, role)
        self._chat_display.append(
            f'<br><b style="color:{color}">{label}:</b> {text}'
        )
        self._chat_display.ensureCursorVisible()
