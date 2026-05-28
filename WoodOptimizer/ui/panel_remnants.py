"""
Panel de gestión de retales.
Tabla Qt con: etiqueta, ancho, alto, espesor, área.
Botones: Añadir, Eliminar, Importar desde plan, Guardar, Cargar.
"""
from __future__ import annotations

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    from PySide6.QtCore import Qt
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtCore import Qt

from ..core.models import Remnant


_HEADERS = ["Etiqueta", "Ancho (mm)", "Alto (mm)", "Espesor", "Área (m²)"]
_COL_LABEL, _COL_W, _COL_H, _COL_T, _COL_AREA = range(5)


class RemnantsPanel(QtWidgets.QWidget):
    """Panel de administración de retales del taller."""

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

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Barra de herramientas
        toolbar = QtWidgets.QHBoxLayout()

        self._btn_add = QtWidgets.QPushButton("+ Añadir")
        self._btn_add.clicked.connect(self._add_remnant)
        toolbar.addWidget(self._btn_add)

        self._btn_del = QtWidgets.QPushButton("− Eliminar")
        self._btn_del.clicked.connect(self._delete_selected)
        toolbar.addWidget(self._btn_del)

        self._btn_import = QtWidgets.QPushButton("↓ Importar plan")
        self._btn_import.setToolTip("Importar retales del último plan de corte")
        self._btn_import.clicked.connect(self._import_from_plan)
        toolbar.addWidget(self._btn_import)

        toolbar.addStretch()

        self._btn_save = QtWidgets.QPushButton("💾 Guardar")
        self._btn_save.clicked.connect(self._save)
        toolbar.addWidget(self._btn_save)

        root.addLayout(toolbar)

        # Tabla
        self._table = QtWidgets.QTableWidget(0, len(_HEADERS))
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        root.addWidget(self._table, stretch=1)

        # Barra de estado
        self._status = QtWidgets.QLabel("0 retales.")
        self._status.setStyleSheet("color: gray; font-size: 10px;")
        root.addWidget(self._status)

    # ── Tabla ─────────────────────────────────────────────────────────────────

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
            area_str = f"{r.area / 1_000_000:.3f}"
            self._table.setItem(row, _COL_AREA,  QtWidgets.QTableWidgetItem(area_str))

        stats = self._manager.stats()
        total = stats["total_area_m2"]
        self._status.setText(
            f"{stats['count']} retales  |  área total: {total:.3f} m²"
        )

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _add_remnant(self):
        dlg = _AddRemnantDialog(self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            r = dlg.remnant()
            if not self._manager.add(r):
                QtWidgets.QMessageBox.warning(
                    self, "Retal demasiado pequeño",
                    "El retal debe tener al menos 100mm en cada dimensión."
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
            label = rems[row].label
            self._manager.remove_by_label(label)
        self._refresh_table()

    def _import_from_plan(self):
        from ..mcp.state import get_state
        state = get_state()
        if state.last_cut_plan is None:
            QtWidgets.QMessageBox.information(
                self, "Sin plan",
                "Ejecuta optimize_cuts primero para generar un plan."
            )
            return
        added = self._manager.import_from_plan(state.last_cut_plan)
        self._refresh_table()
        QtWidgets.QMessageBox.information(
            self, "Importado",
            f"Se importaron {added} retales del plan de corte."
        )

    def _save(self):
        try:
            path = self._manager.save()
            self._status.setText(f"Guardado en {path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error al guardar", str(e))


class _AddRemnantDialog(QtWidgets.QDialog):
    """Diálogo para añadir un retal manualmente."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Añadir retal")
        self.setModal(True)

        form = QtWidgets.QFormLayout(self)

        self._label = QtWidgets.QLineEdit()
        self._label.setPlaceholderText("ej: retal_lateral_izq")
        form.addRow("Etiqueta:", self._label)

        self._width = QtWidgets.QSpinBox()
        self._width.setRange(100, 9999)
        self._width.setValue(600)
        self._width.setSuffix(" mm")
        form.addRow("Ancho:", self._width)

        self._height = QtWidgets.QSpinBox()
        self._height.setRange(100, 9999)
        self._height.setValue(400)
        self._height.setSuffix(" mm")
        form.addRow("Alto:", self._height)

        self._thickness = QtWidgets.QSpinBox()
        self._thickness.setRange(3, 100)
        self._thickness.setValue(18)
        self._thickness.setSuffix(" mm")
        form.addRow("Espesor:", self._thickness)

        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def remnant(self) -> Remnant:
        label = self._label.text().strip() or f"retal_{self._width.value()}x{self._height.value()}"
        return Remnant(
            width=self._width.value(),
            height=self._height.value(),
            thickness=self._thickness.value(),
            label=label,
        )
