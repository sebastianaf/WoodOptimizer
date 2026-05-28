"""
WoodOptimizer Workbench — punto de entrada para FreeCAD.
Este archivo es cargado automáticamente por FreeCAD al iniciar el addon.
"""
import os
import sys

# Asegurar que el workbench esté en el path de Python
try:
    _wb_path = os.path.dirname(os.path.abspath(__file__))
except NameError:
    import FreeCAD as _fc
    _wb_path = os.path.join(_fc.getUserAppDataDir(), "Mod", "WoodOptimizer")
if _wb_path not in sys.path:
    sys.path.insert(0, _wb_path)

import FreeCAD
import FreeCADGui as Gui

_icon_path = os.path.join(_wb_path, "WoodOptimizer", "icons")
_MCP_PORT  = 7891


class WoodOptimizerWorkbench(Gui.Workbench):
    """Workbench principal de WoodOptimizer."""

    MenuText = "WoodOptimizer"
    ToolTip  = "Optimizador de corte de madera con asistente IA"
    Icon     = ""

    def Initialize(self):
        """Llamado una sola vez al registrar el workbench."""
        from WoodOptimizer.commands import cmd_open_panel, cmd_optimize, cmd_export

        self.appendToolbar("WoodOptimizer", [
            "WO_OpenPanel",
            "WO_Optimize",
            "WO_Export",
        ])
        self.appendMenu("WoodOptimizer", [
            "WO_OpenPanel",
            "WO_Optimize",
            "WO_Export",
        ])

        FreeCAD.Console.PrintMessage("[WoodOptimizer] Workbench cargado.\n")

    def Activated(self):
        """Llamado cuando el usuario cambia a este workbench."""
        self._sync_document()
        self._start_mcp()
        FreeCAD.Console.PrintMessage(
            f"[WoodOptimizer] Servidor MCP activo en puerto {_MCP_PORT}.\n"
        )

    def Deactivated(self):
        pass

    def ContextMenu(self, recipient):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"

    # ── helpers ──────────────────────────────────────────────────────────────

    def _sync_document(self):
        from WoodOptimizer.mcp.state import set_document
        try:
            set_document(FreeCAD.ActiveDocument)
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"[WoodOptimizer] No se pudo sincronizar documento: {e}\n")

    def _start_mcp(self):
        try:
            from WoodOptimizer.mcp.server import start_mcp_server
            start_mcp_server(port=_MCP_PORT)
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"[WoodOptimizer] Error al arrancar MCP: {e}\n")


_icon_file = os.path.join(_wb_path, "WoodOptimizer", "icons", "workbench.svg")
if os.path.exists(_icon_file):
    WoodOptimizerWorkbench.Icon = _icon_file

Gui.addWorkbench(WoodOptimizerWorkbench())
