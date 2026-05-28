"""
Panel principal del workbench con pestañas:
  1. Chat — asistente de diseño
  2. Plan de corte — diagrama visual
  3. Retales — gestión
"""
from __future__ import annotations

try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets

from .panel_chat import ChatPanel
from .panel_cutplan import CutPlanPanel
from .panel_remnants import RemnantsPanel


class MainPanel(QtWidgets.QDockWidget):
    """Panel dockeable que contiene todas las pestañas del workbench."""

    def __init__(self, parent=None):
        super().__init__("WoodOptimizer", parent)
        self.setObjectName("WoodOptimizerPanel")
        self.setMinimumWidth(420)

        self._tab_cutplan = CutPlanPanel()
        self._tab_remnants = RemnantsPanel()

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(ChatPanel(), "Asistente")
        tabs.addTab(self._tab_cutplan, "Plan de corte")
        tabs.addTab(self._tab_remnants, "Retales")

        # Actualizar diagrama al cambiar a esa pestaña
        tabs.currentChanged.connect(self._on_tab_changed)

        self.setWidget(tabs)
        self._tabs = tabs

    def _on_tab_changed(self, index: int):
        if self._tabs.widget(index) is self._tab_cutplan:
            self._tab_cutplan.refresh()


def show_panel():
    """Abre el panel principal anclado en FreeCAD."""
    try:
        import FreeCADGui
        mw = FreeCADGui.getMainWindow()
        panel = MainPanel(mw)
        mw.addDockWidget(
            __import__("PySide2.QtCore", fromlist=["Qt"]).Qt.RightDockWidgetArea
            if not _has_pyside6() else
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.RightDockWidgetArea,
            panel,
        )
        panel.show()
    except Exception as e:
        print(f"[WoodOptimizer] Error al abrir panel: {e}")


def _has_pyside6() -> bool:
    try:
        import PySide6  # noqa: F401
        return True
    except ImportError:
        return False
