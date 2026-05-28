"""Comando FreeCAD: ejecutar optimización de corte desde la barra de herramientas."""
from __future__ import annotations


class WO_Optimize:
    """Ejecuta optimize_cuts sobre el documento activo y muestra el resultado."""

    def GetResources(self):
        return {
            "MenuText": "Optimizar corte",
            "ToolTip":  "Calcula el plan de corte óptimo para las piezas del documento",
        }

    def Activated(self):
        import FreeCAD
        from ..mcp.handlers import handle_optimize_cuts

        try:
            result = handle_optimize_cuts()
            if "error" in result:
                FreeCAD.Console.PrintError(f"[WoodOptimizer] {result['error']}\n")
            else:
                FreeCAD.Console.PrintMessage(
                    f"[WoodOptimizer] Plan calculado: "
                    f"{result['sheets_used']} tableros, "
                    f"{result['efficiency']}% eficiencia.\n"
                )
        except Exception as e:
            FreeCAD.Console.PrintError(f"[WoodOptimizer] Error: {e}\n")

    def IsActive(self):
        try:
            import FreeCAD
            return FreeCAD.ActiveDocument is not None
        except Exception:
            return False


def register():
    import FreeCADGui as Gui
    Gui.addCommand("WO_Optimize", WO_Optimize())
