"""Comando FreeCAD: exportar plan de corte (CSV / JSON / PDF)."""
from __future__ import annotations


class WO_Export:
    """Exporta el último plan de corte al formato elegido por el usuario."""

    def GetResources(self):
        return {
            "MenuText": "Exportar plan",
            "ToolTip":  "Exporta el plan de corte a CSV, JSON o PDF",
        }

    def Activated(self):
        try:
            import FreeCADGui
            from PySide2 import QtWidgets
        except ImportError:
            try:
                from PySide6 import QtWidgets
            except ImportError:
                return

        from ..mcp.state import get_state
        from ..mcp.handlers import handle_export_cutlist

        state = get_state()
        if state.last_cut_plan is None:
            QtWidgets.QMessageBox.warning(
                None, "Sin plan",
                "Ejecuta primero una optimización (WO_Optimize o desde el chat)."
            )
            return

        fmt, ok = QtWidgets.QInputDialog.getItem(
            None,
            "Exportar plan de corte",
            "Formato:",
            ["pdf", "csv", "json"],
            0,
            False,
        )
        if not ok:
            return

        ext_map = {"pdf": "PDF (*.pdf)", "csv": "CSV (*.csv)", "json": "JSON (*.json)"}
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            None, "Guardar como", f"plan_de_corte.{fmt}", ext_map[fmt]
        )
        if not path:
            return

        result = handle_export_cutlist(fmt, path)
        if "error" in result:
            QtWidgets.QMessageBox.critical(None, "Error al exportar", result["error"])
        else:
            QtWidgets.QMessageBox.information(
                None, "Exportado", f"Plan guardado en:\n{result['path']}"
            )

    def IsActive(self):
        from ..mcp.state import get_state
        try:
            return get_state().last_cut_plan is not None
        except Exception:
            return False


def register():
    import FreeCADGui as Gui
    Gui.addCommand("WO_Export", WO_Export())
