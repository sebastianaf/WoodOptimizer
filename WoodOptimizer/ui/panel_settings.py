"""
Panel de configuración del proveedor LLM.
"""
from __future__ import annotations

try:
    from PySide6 import QtWidgets
    from PySide6.QtCore import Qt
except ImportError:
    from PySide2 import QtWidgets
    from PySide2.QtCore import Qt

_DEEPSEEK_URL  = "https://api.deepseek.com/v1"
_OPENAI_URL    = "https://api.openai.com/v1"
_OLLAMA_URL    = "http://localhost:11434"

_PRESETS = {
    "ollama":        (_OLLAMA_URL,   "",            "qwen2.5-coder:32b"),
    "deepseek":      (_DEEPSEEK_URL, "",            "deepseek-chat"),
    "openai":        (_OPENAI_URL,   "",            "gpt-4o-mini"),
    "openai_compat": ("",            "",            ""),
}


class SettingsPanel(QtWidgets.QWidget):
    """Pestaña de configuración del proveedor LLM."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # ── Grupo: Proveedor ─────────────────────────────────────────────────
        grp = QtWidgets.QGroupBox("Proveedor LLM")
        form = QtWidgets.QFormLayout(grp)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)

        self._cmb_preset = QtWidgets.QComboBox()
        self._cmb_preset.addItems(["ollama", "deepseek", "openai", "openai_compat"])
        self._cmb_preset.currentTextChanged.connect(self._on_preset_changed)
        form.addRow("Proveedor:", self._cmb_preset)

        self._txt_url = QtWidgets.QLineEdit()
        self._txt_url.setPlaceholderText("URL base de la API")
        form.addRow("URL:", self._txt_url)

        self._txt_model = QtWidgets.QLineEdit()
        self._txt_model.setPlaceholderText("nombre del modelo")
        form.addRow("Modelo:", self._txt_model)

        self._txt_key = QtWidgets.QLineEdit()
        self._txt_key.setPlaceholderText("sk-… (vacío para Ollama)")
        self._txt_key.setEchoMode(QtWidgets.QLineEdit.Password)
        form.addRow("API Key:", self._txt_key)

        self._chk_show = QtWidgets.QCheckBox("Mostrar API Key")
        self._chk_show.toggled.connect(self._toggle_key_visibility)
        form.addRow("", self._chk_show)

        root.addWidget(grp)

        # ── Botones ──────────────────────────────────────────────────────────
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()

        self._btn_test = QtWidgets.QPushButton("Probar conexión")
        self._btn_test.clicked.connect(self._test_connection)
        btn_row.addWidget(self._btn_test)

        self._btn_save = QtWidgets.QPushButton("Guardar")
        self._btn_save.setDefault(True)
        self._btn_save.clicked.connect(self._save)
        btn_row.addWidget(self._btn_save)

        root.addLayout(btn_row)

        # ── Estado ───────────────────────────────────────────────────────────
        self._lbl_status = QtWidgets.QLabel("")
        self._lbl_status.setWordWrap(True)
        self._lbl_status.setAlignment(Qt.AlignLeft)
        root.addWidget(self._lbl_status)

        root.addStretch()

        # ── Nota ─────────────────────────────────────────────────────────────
        note = QtWidgets.QLabel(
            "<small>La configuración se guarda en las preferencias de FreeCAD "
            "y en <code>~/.woodoptimizer_config.json</code> como respaldo.</small>"
        )
        note.setWordWrap(True)
        note.setTextFormat(Qt.RichText)
        root.addWidget(note)

    # ── Lógica ───────────────────────────────────────────────────────────────

    def _on_preset_changed(self, preset: str):
        url, _, model = _PRESETS.get(preset, ("", "", ""))
        if url:
            self._txt_url.setText(url)
        if model:
            self._txt_model.setText(model)
        api_key_enabled = preset != "ollama"
        self._txt_key.setEnabled(api_key_enabled)
        self._chk_show.setEnabled(api_key_enabled)

    def _toggle_key_visibility(self, visible: bool):
        mode = QtWidgets.QLineEdit.Normal if visible else QtWidgets.QLineEdit.Password
        self._txt_key.setEchoMode(mode)

    def _load(self):
        from ..llm.config import load_config
        cfg = load_config()

        preset = cfg.provider
        if preset not in [self._cmb_preset.itemText(i)
                          for i in range(self._cmb_preset.count())]:
            preset = "openai_compat"

        self._cmb_preset.blockSignals(True)
        idx = self._cmb_preset.findText(preset)
        self._cmb_preset.setCurrentIndex(idx if idx >= 0 else 0)
        self._cmb_preset.blockSignals(False)

        self._txt_url.setText(cfg.url)
        self._txt_model.setText(cfg.model)
        self._txt_key.setText(cfg.api_key)

        api_key_enabled = cfg.provider != "ollama"
        self._txt_key.setEnabled(api_key_enabled)
        self._chk_show.setEnabled(api_key_enabled)

    def _save(self):
        from ..llm.config import save_config, ProviderConfig

        preset = self._cmb_preset.currentText()
        provider = "ollama" if preset == "ollama" else "openai_compat"

        cfg = ProviderConfig(
            provider=provider,
            url=self._txt_url.text().strip(),
            model=self._txt_model.text().strip(),
            api_key=self._txt_key.text().strip(),
        )
        try:
            save_config(cfg)
            self._set_status("Configuración guardada correctamente.", ok=True)
        except Exception as e:
            self._set_status(f"Error al guardar: {e}", ok=False)

    def _test_connection(self):
        from ..llm.config import ProviderConfig
        from ..llm.providers.ollama import OllamaProvider
        from ..llm.providers.openai_compat import OpenAICompatProvider

        preset = self._cmb_preset.currentText()
        provider = "ollama" if preset == "ollama" else "openai_compat"
        url     = self._txt_url.text().strip()
        api_key = self._txt_key.text().strip()
        model   = self._txt_model.text().strip()

        self._set_status("Probando conexión…", ok=None)
        QtWidgets.QApplication.processEvents()

        try:
            if provider == "ollama":
                p = OllamaProvider(url=url)
            else:
                p = OpenAICompatProvider(url=url, api_key=api_key)

            models = p.list_models()
            if models:
                self._set_status(
                    f"Conexión OK. Modelos disponibles: {', '.join(models[:5])}"
                    + (" …" if len(models) > 5 else ""),
                    ok=True,
                )
            else:
                self._set_status("Conexión OK (sin modelos listados).", ok=True)
        except Exception as e:
            self._set_status(f"Error de conexión: {e}", ok=False)

    def _set_status(self, msg: str, ok):
        if ok is True:
            color = "green"
        elif ok is False:
            color = "red"
        else:
            color = "gray"
        self._lbl_status.setText(f'<span style="color:{color}">{msg}</span>')
