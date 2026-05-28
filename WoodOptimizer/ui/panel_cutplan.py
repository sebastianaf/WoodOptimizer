"""Cut plan visual panel — QPainter sheet diagram with colored pieces."""
from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtCore import Qt

from ..core.models import SheetLayout

_COLORS = [
    QtGui.QColor(135, 206, 250),
    QtGui.QColor(144, 238, 144),
    QtGui.QColor(255, 215, 130),
    QtGui.QColor(216, 160, 216),
    QtGui.QColor(255, 182, 193),
    QtGui.QColor(175, 225, 225),
    QtGui.QColor(240, 240, 140),
    QtGui.QColor(195, 195, 195),
]


class _SheetWidget(QtWidgets.QWidget):

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
        scale = min(
            (self.width() - 2 * margin) / sheet.width,
            (self.height() - 2 * margin) / sheet.height,
        )
        ox, oy = margin, margin

        p.setBrush(QtGui.QBrush(QtGui.QColor(248, 245, 220)))
        p.setPen(QtGui.QPen(QtGui.QColor(80, 80, 80), 1.5))
        p.drawRect(ox, oy, int(sheet.width * scale), int(sheet.height * scale))

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
                label = placed.part_id + (" R" if placed.rotated else "")
                p.drawText(
                    QtCore.QRect(px + 2, py + 2, pw - 4, ph - 4),
                    Qt.AlignCenter | Qt.TextWordWrap,
                    label,
                )


class CutPlanPanel(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color_map: dict[str, QtGui.QColor] = {}
        self._build_ui()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        hdr = QtWidgets.QHBoxLayout()
        self._lbl_summary = QtWidgets.QLabel("No plan calculated.")
        self._lbl_summary.setStyleSheet("font-weight: bold;")
        hdr.addWidget(self._lbl_summary, stretch=1)

        btn_refresh = QtWidgets.QPushButton("↻ Refresh")
        btn_refresh.clicked.connect(self.refresh)
        hdr.addWidget(btn_refresh)

        self._btn_pdf = QtWidgets.QPushButton("Export PDF")
        self._btn_pdf.clicked.connect(self._export_pdf)
        hdr.addWidget(self._btn_pdf)

        root.addLayout(hdr)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._container = QtWidgets.QWidget()
        self._vbox = QtWidgets.QVBoxLayout(self._container)
        self._vbox.setSpacing(10)
        self._vbox.addStretch()
        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, stretch=1)

    def refresh(self):
        from ..mcp.state import get_state
        state = get_state()

        while self._vbox.count() > 1:
            item = self._vbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if state.last_cut_plan is None:
            self._lbl_summary.setText("No plan calculated. Run optimize_cuts.")
            return

        plan = state.last_cut_plan
        self._lbl_summary.setText(
            f"Sheets: {len(plan.layouts)}  |  "
            f"Efficiency: {plan.efficiency * 100:.1f}%  |  "
            f"Unplaced: {len(plan.unplaced)}"
        )

        self._color_map.clear()
        color_idx = 0

        for i, layout in enumerate(plan.layouts):
            for placed in layout.placed:
                if placed.part_id not in self._color_map:
                    self._color_map[placed.part_id] = _COLORS[color_idx % len(_COLORS)]
                    color_idx += 1

            sheet_type = "offcut" if layout.is_remnant else "new sheet"
            title = (f"Sheet {i+1} ({sheet_type})  —  "
                     f"{layout.sheet.width}×{layout.sheet.height} mm  "
                     f"efficiency {layout.efficiency * 100:.1f}%")
            lbl = QtWidgets.QLabel(title)
            lbl.setStyleSheet("font-weight: bold; padding-top: 6px;")
            self._vbox.insertWidget(self._vbox.count() - 1, lbl)
            self._vbox.insertWidget(self._vbox.count() - 1, _SheetWidget(layout, self._color_map))

    def _export_pdf(self):
        from ..mcp.state import get_state
        state = get_state()
        if state.last_cut_plan is None:
            QtWidgets.QMessageBox.warning(
                self, "No plan",
                "Run optimize_cuts from the chat first."
            )
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save PDF", "cut_plan.pdf", "PDF (*.pdf)"
        )
        if not path:
            return

        try:
            from ..export.pdf_exporter import export
            out = export(state.last_cut_plan, path)
            QtWidgets.QMessageBox.information(self, "PDF exported", f"Saved to:\n{out}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export error", str(e))
