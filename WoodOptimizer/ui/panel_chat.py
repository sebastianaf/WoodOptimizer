"""
Panel de chat con el asistente LLM.
Requiere PySide2 o PySide6 (disponible dentro de FreeCAD).
"""
from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt, Signal, QThread
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtCore import Qt, Signal, QThread


# ─── Worker de LLM en hilo separado ──────────────────────────────────────────

class _LLMWorker(QThread):
    """Ejecuta la llamada al LLM fuera del hilo principal para no bloquear la UI."""
    chunk_ready   = Signal(str)    # fragmento de texto
    tool_executed = Signal(str, str)  # (tool_name, result_summary)
    finished_ok   = Signal(str)    # texto final completo
    error         = Signal(str)

    def __init__(self, client, message: str, history: list[dict], parent=None):
        super().__init__(parent)
        self._client  = client
        self._message = message
        self._history = history

    def run(self):
        try:
            def on_tool(name, args, result_json):
                import json
                r = json.loads(result_json)
                summary = str(r)[:80]
                self.tool_executed.emit(name, summary)

            for fragment in self._client.stream_chat(
                self._message, self._history, on_tool_call=on_tool
            ):
                self.chunk_ready.emit(fragment)
        except Exception as e:
            self.error.emit(str(e))


# ─── Panel principal ──────────────────────────────────────────────────────────

class ChatPanel(QtWidgets.QWidget):
    """
    Panel de chat con el asistente de diseño.

    Mockup del AGENTS.md:
    ┌─ Asistente de diseño ──────────────────────┐
    │ Proveedor: [Ollama ▼]                       │
    │ URL:       [http://localhost:11434    ]      │
    │ Modelo:    [qwen2.5-coder:32b ▼]  [↻]       │
    ├─────────────────────────────────────────────┤
    │  (historial de chat)                        │
    ├─────────────────────────────────────────────┤
    │ [                         ] [Enviar]         │
    └─────────────────────────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[dict] = []
        self._worker: _LLMWorker | None = None
        self._client = None
        self._build_ui()
        self._load_config()

    # ── Construcción de la UI ─────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Config box ───────────────────────────────────────────────────────
        config_box = QtWidgets.QGroupBox("Configuración del proveedor")
        form = QtWidgets.QFormLayout(config_box)
        form.setLabelAlignment(Qt.AlignRight)

        self._cmb_provider = QtWidgets.QComboBox()
        self._cmb_provider.addItems(["ollama", "openai_compat"])
        self._cmb_provider.currentTextChanged.connect(self._on_provider_changed)
        form.addRow("Proveedor:", self._cmb_provider)

        self._txt_url = QtWidgets.QLineEdit("http://localhost:11434")
        self._txt_url.editingFinished.connect(self._save_config)
        form.addRow("URL:", self._txt_url)

        model_row = QtWidgets.QHBoxLayout()
        self._cmb_model = QtWidgets.QComboBox()
        self._cmb_model.setEditable(True)
        self._cmb_model.setMinimumWidth(200)
        model_row.addWidget(self._cmb_model)

        btn_refresh = QtWidgets.QPushButton("↻")
        btn_refresh.setFixedWidth(30)
        btn_refresh.setToolTip("Actualizar lista de modelos")
        btn_refresh.clicked.connect(self._refresh_models)
        model_row.addWidget(btn_refresh)

        form.addRow("Modelo:", model_row)
        root.addWidget(config_box)

        # ── Historial de chat ─────────────────────────────────────────────────
        self._chat_display = QtWidgets.QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setMinimumHeight(250)
        font = QtGui.QFont("Monospace", 10)
        font.setStyleHint(QtGui.QFont.TypeWriter)
        self._chat_display.setFont(font)
        root.addWidget(self._chat_display, stretch=1)

        # ── Input ─────────────────────────────────────────────────────────────
        input_row = QtWidgets.QHBoxLayout()
        self._txt_input = QtWidgets.QLineEdit()
        self._txt_input.setPlaceholderText(
            "Ej: diseñame un closet de 60×240 con 3 entrepaños y cajón inferior"
        )
        self._txt_input.returnPressed.connect(self._send)
        input_row.addWidget(self._txt_input, stretch=1)

        self._btn_send = QtWidgets.QPushButton("Enviar")
        self._btn_send.clicked.connect(self._send)
        input_row.addWidget(self._btn_send)

        root.addLayout(input_row)

        # ── Barra de estado ───────────────────────────────────────────────────
        self._status = QtWidgets.QLabel("Listo.")
        self._status.setStyleSheet("color: gray; font-size: 10px;")
        root.addWidget(self._status)

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        from ..llm.config import load_config
        cfg = load_config()
        idx = self._cmb_provider.findText(cfg.provider)
        if idx >= 0:
            self._cmb_provider.setCurrentIndex(idx)
        self._txt_url.setText(cfg.url)
        self._cmb_model.setCurrentText(cfg.model)
        self._rebuild_client()

    def _save_config(self):
        from ..llm.config import save_config, ProviderConfig
        save_config(ProviderConfig(
            provider=self._cmb_provider.currentText(),
            url=self._txt_url.text().strip(),
            model=self._cmb_model.currentText().strip(),
        ))
        self._rebuild_client()

    def _on_provider_changed(self, provider: str):
        default_url = "http://localhost:11434" if provider == "ollama" else "https://api.openai.com"
        self._txt_url.setText(default_url)
        self._save_config()

    def _rebuild_client(self):
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

    # ── Modelos ───────────────────────────────────────────────────────────────

    def _refresh_models(self):
        if self._client is None:
            return
        self._status.setText("Cargando modelos...")
        try:
            models = self._client.provider.list_models()
            self._cmb_model.clear()
            self._cmb_model.addItems(models)
            self._status.setText(f"{len(models)} modelos disponibles.")
        except Exception as e:
            self._status.setText(f"Error: {e}")

    # ── Chat ──────────────────────────────────────────────────────────────────

    def _send(self):
        text = self._txt_input.text().strip()
        if not text or self._worker is not None:
            return

        self._txt_input.clear()
        self._btn_send.setEnabled(False)
        self._status.setText("Procesando...")

        self._append_message("user", text)

        self._worker = _LLMWorker(self._client, text, self._history, parent=self)
        self._worker.chunk_ready.connect(self._on_chunk)
        self._worker.tool_executed.connect(self._on_tool)
        self._worker.error.connect(self._on_error)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

        # Preparar bloque vacío del asistente para ir llenando
        self._current_assistant_text = ""
        self._chat_display.append("\n<b>Asistente:</b> ")

    def _on_chunk(self, fragment: str):
        self._current_assistant_text += fragment
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertText(fragment)
        self._chat_display.setTextCursor(cursor)
        self._chat_display.ensureCursorVisible()

    def _on_tool(self, name: str, summary: str):
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.insertHtml(f'<br><span style="color:#888">  ⚙ {name}</span>')
        self._chat_display.setTextCursor(cursor)

    def _on_error(self, msg: str):
        self._append_message("error", msg)

    def _on_worker_done(self):
        self._history.append({"role": "user",
                               "content": self._txt_input.text() or ""})
        self._history.append({"role": "assistant",
                               "content": self._current_assistant_text})
        self._worker = None
        self._btn_send.setEnabled(True)
        self._status.setText("Listo.")

    def _append_message(self, role: str, text: str):
        colors = {"user": "#005f87", "error": "#c0392b"}
        labels = {"user": "Tú", "error": "Error"}
        color = colors.get(role, "#333")
        label = labels.get(role, role)
        self._chat_display.append(
            f'<br><b style="color:{color}">{label}:</b> {text}'
        )
        self._chat_display.ensureCursorVisible()
