"""Comando FreeCAD: abrir el panel principal de WoodOptimizer."""
from __future__ import annotations


class WO_OpenPanel:
    """Abre el panel dockeable de WoodOptimizer."""

    def GetResources(self):
        import os
        icon = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "icons", "workbench.svg",
        )
        return {
            "Pixmap":  icon,
            "MenuText": "Abrir panel",
            "ToolTip":  "Abre el asistente de diseño y plan de corte",
        }

    def Activated(self):
        from ..ui.panel_main import show_panel
        show_panel()

    def IsActive(self):
        return True


def register():
    import FreeCADGui as Gui
    Gui.addCommand("WO_OpenPanel", WO_OpenPanel())
