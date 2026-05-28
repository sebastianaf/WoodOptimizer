"""
Panel visual del plan de corte.
Muestra cada tablero con las piezas coloreadas usando QPainter.
"""
from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtCore import Qt

from ..core.models import SheetLayout

# Paleta de colores para las piezas
_COLORS = [
    QtGui.QColor(135, 206, 250),  # azul claro
    QtGui.QColor(144, 238, 144),  # verde claro
    QtGui.QColor(255, 215, 130),  # naranja claro
    QtGui.QColor(216, 160, 216),  # lila claro
    QtGui.QColor(255, 182, 193),  # rosa claro
    QtGui.QColor(175, 225, 225),  # cian claro
    QtGui.QColor(240, 240, 140),  # amarillo claro
    QtGui.QColor(195, 195, 195),  # gris claro
]


class _SheetWidget(QtWidgets.QWidget):
    """Dibuja un único tablero con QPainter."""

    def __init__(self, layout: SheetLayout, color_map: dict[str, QtGui.QColor],
                 parent=None):
        super().__init__(parent)
        self._layout = layout
        self._color_map = color_map
        self.setMinimumSize(300, 160)

    def sizeHint(self):
        return QtCore.QSize(560, 300)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self._draw(painter)
        painter.end()

    def _draw(self, p: QtGui.QPainter):
        margin = 20
        sheet = self._layout.sheet

        available_w = self.width() - 2 * margin
        available_h = self.height() - 2 * margin
        scale = min(available_w / sheet.width, available_h / sheet.height)

        ox = margin
        oy = margin
        sw = int(sheet.width * scale)
        sh = int(sheet.height * scale)

        # Fondo del tablero
        p.setBrush(QtGui.QBrush(QtGui.QColor(248, 245, 220)))
        p.setPen(QtGui.QPen(QtGui.QColor(80, 80, 80), 1.5))
        p.drawRect(ox, oy, sw, sh)

        # Piezas
        font = p.font()
        font.setPointSize(7)
        p.setFont(font)

        for placed in self._layout.placed:
            color = self._color_map.get(placed.part_id, _COLORS[0])
            px = ox + int(placed.x * scale)
            py = oy + int(placed.y * scale)
            pw = max(1, int(placed.width * scale))
            ph = max(1, int(placed.height * scale))

            p.setBrush(QtGui.QBrush(color))
            p.setPen(QtGui.QPen(QtGui.QColor(50, 50, 50), 0.8))
            p.drawRect(px, py, pw, ph)

            if pw > 25 and ph > 12:
                p.setPen(Qt.black)
                label = placed.part_id
                if placed.rotated:
                    label += " R"
                p.drawText(
                    QtCore.QRect(px + 2, py + 2, pw - 4, ph - 4),
                    Qt.AlignCenter | Qt.TextWordWrap,
                    label,
                )


class CutPlanPanel(QtWidgets.QWidget):
    """
    Panel con scroll que muestra todos los tableros del plan de corte.

    Contiene:
    - Resumen de eficiencia global en la cabecera
    - Un SheetWidget por tablero
    - Botón de exportar PDF
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color_map: dict[str, QtGui.QColor] = {}
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        # Cabecera
        hdr = QtWidgets.QHBoxLayout()
        self._lbl_summary = QtWidgets.QLabel("Sin plan calculado.")
        self._lbl_summary.setStyleSheet("font-weight: bold;")
        hdr.addWidget(self._lbl_summary, stretch=1)

        self._btn_refresh = QtWidgets.QPushButton("↻ Actualizar")
        self._btn_refresh.clicked.connect(self.refresh)
        hdr.addWidget(self._btn_refresh)

        self._btn_pdf = QtWidgets.QPushButton("Exportar PDF")
        self._btn_pdf.clicked.connect(self._export_pdf)
        hdr.addWidget(self._btn_pdf)

        root.addLayout(hdr)

        # Área con scroll para los tableros
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QtWidgets.QWidget()
        self._vbox = QtWidgets.QVBoxLayout(self._container)
        self._vbox.setSpacing(10)
        self._vbox.addStretch()
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, stretch=1)

    def refresh(self):
        """Lee el plan actual del estado global y re-dibuja."""
        from ..mcp.state import get_state
        state = get_state()

        # Limpiar tableros anteriores
        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if state.last_cut_plan is None:
            self._lbl_summary.setText("Sin plan calculado. Ejecuta optimize_cuts.")
            return

        plan = state.last_cut_plan
        self._lbl_summary.setText(
            f"Tableros: {len(plan.layouts)}  |  "
            f"Eficiencia: {plan.efficiency * 100:.1f}%  |  "
            f"Sin ubicar: {len(plan.unplaced)}"
        )

        self._color_map.clear()
        color_idx = 0

        for i, layout in enumerate(plan.layouts):
            # Asignar colores únicos por pieza
            for placed in layout.placed:
                if placed.part_id not in self._color_map:
                    self._color_map[placed.part_id] = _COLORS[color_idx % len(_COLORS)]
                    color_idx += 1

            # Título del tablero
            lbl_type = "retal" if layout.is_remnant else "tablero nuevo"
            title = (f"Tablero {i+1} ({lbl_type})  —  "
                     f"{layout.sheet.width}×{layout.sheet.height} mm  "
                     f"eficiencia {layout.efficiency * 100:.1f}%")
            lbl = QtWidgets.QLabel(title)
            lbl.setStyleSheet("font-weight: bold; padding-top: 6px;")
            self._vbox.insertWidget(self._vbox.count() - 1, lbl)

            widget = _SheetWidget(layout, self._color_map)
            self._vbox.insertWidget(self._vbox.count() - 1, widget)

    def _export_pdf(self):
        from ..mcp.state import get_state
        state = get_state()
        if state.last_cut_plan is None:
            QtWidgets.QMessageBox.warning(
                self, "Sin plan",
                "Primero ejecuta optimize_cuts desde el chat."
            )
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Guardar PDF", "plan_de_corte.pdf",
            "PDF (*.pdf)"
        )
        if not path:
            return

        try:
            from ..export.pdf_exporter import export
            out = export(state.last_cut_plan, path)
            QtWidgets.QMessageBox.information(
                self, "PDF exportado", f"Guardado en:\n{out}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))
