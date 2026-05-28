"""
WoodOptimizer Workbench — FreeCAD entry point.
Loaded automatically by FreeCAD on startup.
"""
import os
import sys

try:
    _wb_path = os.path.dirname(os.path.abspath(__file__))
except NameError:
    import FreeCAD as _fc
    _wb_path = os.path.join(_fc.getUserAppDataDir(), "Mod", "WoodOptimizer")

if _wb_path not in sys.path:
    sys.path.insert(0, _wb_path)

import FreeCAD
import FreeCADGui as Gui


def _on_document_opened(doc):
    """Re-sync state whenever FreeCAD opens or switches to a document."""
    try:
        from WoodOptimizer.mcp.state import set_document
        set_document(doc)
    except Exception:
        pass


# Hook into FreeCAD's document signals so state.doc is always up to date
# regardless of when the user creates/opens a document relative to activation.
try:
    Gui.getMainWindow()  # only available in GUI mode
    FreeCAD.connect("documentOpened(QObject*)", _on_document_opened)
except Exception:
    pass  # headless mode — no signal to connect


class WoodOptimizerWorkbench(Gui.Workbench):

    MenuText  = "WoodOptimizer"
    ToolTip   = "Wood cutting optimizer with AI assistant"
    Icon      = ""
    _MCP_PORT = 7891

    def Initialize(self):
        from WoodOptimizer.commands import cmd_open_panel, cmd_optimize, cmd_export
        cmd_open_panel()
        cmd_optimize()
        cmd_export()

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

        FreeCAD.Console.PrintMessage("[WoodOptimizer] Workbench loaded.\n")

    def Activated(self):
        self._sync_document()
        self._start_mcp()
        FreeCAD.Console.PrintMessage(
            f"[WoodOptimizer] MCP server active on port {self._MCP_PORT}.\n"
        )

    def Deactivated(self):
        pass

    def ContextMenu(self, recipient):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"

    def _sync_document(self):
        from WoodOptimizer.mcp.state import set_document
        try:
            set_document(FreeCAD.ActiveDocument)
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"[WoodOptimizer] Could not sync document: {e}\n")

    def _start_mcp(self):
        try:
            from WoodOptimizer.mcp.server import start_mcp_server
            start_mcp_server(port=self._MCP_PORT)
        except Exception as e:
            FreeCAD.Console.PrintWarning(f"[WoodOptimizer] MCP server error: {e}\n")


_icon_file = os.path.join(_wb_path, "WoodOptimizer", "icons", "workbench.svg")
if os.path.exists(_icon_file):
    WoodOptimizerWorkbench.Icon = _icon_file

Gui.addWorkbench(WoodOptimizerWorkbench())
