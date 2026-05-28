"""Remnants management panel — label, width, height, thickness, area table."""
from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtCore import Qt

from ..core.models import Remnant


_HEADERS = ["Label", "Width (mm)", "Height (mm)", "Thickness", "Area (m²)"]
_COL_LABEL, _COL_W, _COL_H, _COL_T, _COL_AREA = range(5)


class RemnantsPanel(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = None
        self._build_ui()
        self._load_manager()

    def _load_manager(self):
        from ..core.remnant_manager import RemnantManager
        self._manager = RemnantManager()
        self._manager.load()
        self._refresh_table()

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        toolbar = QtWidgets.QHBoxLayout()

        self._btn_add = QtWidgets.QPushButton("+ Add")
        self._btn_add.clicked.connect(self._add_remnant)
        toolbar.addWidget(self._btn_add)

        self._btn_del = QtWidgets.QPushButton("− Remove")
        self._btn_del.clicked.connect(self._delete_selected)
        toolbar.addWidget(self._btn_del)

        self._btn_import = QtWidgets.QPushButton("↓ Import from plan")
        self._btn_import.setToolTip("Import offcuts from the last cut plan")
        self._btn_import.clicked.connect(self._import_from_plan)
        toolbar.addWidget(self._btn_import)

        toolbar.addStretch()

        self._btn_save = QtWidgets.QPushButton("Save")
        self._btn_save.clicked.connect(self._save)
        toolbar.addWidget(self._btn_save)

        root.addLayout(toolbar)

        self._table = QtWidgets.QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        root.addWidget(self._table, stretch=1)

        self._status = QtWidgets.QLabel("0 offcuts.")
        self._status.setStyleSheet("color: gray; font-size: 10px;")
        root.addWidget(self._status)

    def _refresh_table(self):
        if self._manager is None:
            return
        rems = self._manager.sorted_by_score()
        self._table.setRowCount(len(rems))
        for row, r in enumerate(rems):
            self._table.setItem(row, _COL_LABEL, QtWidgets.QTableWidgetItem(r.label))
            self._table.setItem(row, _COL_W,     QtWidgets.QTableWidgetItem(str(r.width)))
            self._table.setItem(row, _COL_H,     QtWidgets.QTableWidgetItem(str(r.height)))
            self._table.setItem(row, _COL_T,     QtWidgets.QTableWidgetItem(str(r.thickness)))
            self._table.setItem(row, _COL_AREA,  QtWidgets.QTableWidgetItem(
                f"{r.area / 1_000_000:.3f}"
            ))

        stats = self._manager.stats()
        self._status.setText(
            f"{stats['count']} offcuts  |  total area: {stats['total_area_m2']:.3f} m²"
        )

    def _add_remnant(self):
        dlg = _AddRemnantDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            r = dlg.remnant()
            if not self._manager.add(r):
                QtWidgets.QMessageBox.warning(
                    self, "Offcut too small",
                    "Each dimension must be at least 100 mm."
                )
                return
            self._refresh_table()

    def _delete_selected(self):
        rows = sorted(
            {i.row() for i in self._table.selectedItems()},
            reverse=True,
        )
        if not rows:
            return
        rems = self._manager.sorted_by_score()
        for row in rows:
            self._manager.remove_by_label(rems[row].label)
        self._refresh_table()

    def _import_from_plan(self):
        from ..mcp.state import get_state
        state = get_state()
        if state.last_cut_plan is None:
            QtWidgets.QMessageBox.information(
                self, "No plan",
                "Run optimize_cuts first to generate a cut plan."
            )
            return
        added = self._manager.import_from_plan(state.last_cut_plan)
        self._refresh_table()
        QtWidgets.QMessageBox.information(
            self, "Imported",
            f"{added} offcut(s) imported from the cut plan."
        )

    def _save(self):
        try:
            path = self._manager.save()
            self._status.setText(f"Saved to {path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save error", str(e))


class _AddRemnantDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add offcut")
        self.setModal(True)

        form = QtWidgets.QFormLayout(self)

        self._label = QtWidgets.QLineEdit()
        self._label.setPlaceholderText("e.g.: left_side_offcut")
        form.addRow("Label:", self._label)

        self._width = QtWidgets.QSpinBox()
        self._width.setRange(100, 9999)
        self._width.setValue(600)
        self._width.setSuffix(" mm")
        form.addRow("Width:", self._width)

        self._height = QtWidgets.QSpinBox()
        self._height.setRange(100, 9999)
        self._height.setValue(400)
        self._height.setSuffix(" mm")
        form.addRow("Height:", self._height)

        self._thickness = QtWidgets.QSpinBox()
        self._thickness.setRange(3, 100)
        self._thickness.setValue(18)
        self._thickness.setSuffix(" mm")
        form.addRow("Thickness:", self._thickness)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def remnant(self) -> Remnant:
        label = self._label.text().strip() or f"offcut_{self._width.value()}x{self._height.value()}"
        return Remnant(
            width=self._width.value(),
            height=self._height.value(),
            thickness=self._thickness.value(),
            label=label,
        )
