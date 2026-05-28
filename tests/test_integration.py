"""
Tests de integración: pipeline completo desde piezas FreeCAD hasta export.
No requieren FreeCAD real — usan el mismo mock de los otros tests.
"""
import json
import sys
import types
import pytest

from WoodOptimizer.mcp import state as state_module


# ─── Mock FreeCAD ─────────────────────────────────────────────────────────────

def _make_freecad_mock():
    fc = types.ModuleType("FreeCAD")

    class Vector:
        def __init__(self, x=0, y=0, z=0):
            self.x, self.y, self.z = x, y, z

    class Placement:
        def __init__(self):
            self.Base = Vector()

    class BoundBox:
        def __init__(self, xl, yl, zl):
            self.XLength, self.YLength, self.ZLength = xl, yl, zl

    class Shape:
        def __init__(self, xl=0, yl=0, zl=0, null=False):
            self._null = null
            self.BoundBox = BoundBox(xl, yl, zl)
        def isNull(self): return self._null

    class FreeCADObject:
        def __init__(self, name, label, xl, yl, zl):
            self.Name, self.Label = name, label
            self.Shape = Shape(xl, yl, zl)
            self.Placement = Placement()
            self.Length, self.Width, self.Height = xl, yl, zl

    class Document:
        def __init__(self, objects=None):
            self.Objects = list(objects or [])
            self._map = {o.Name: o for o in self.Objects}
        def addObject(self, t, n):
            obj = FreeCADObject(n, n, 0, 0, 0)
            self.Objects.append(obj); self._map[n] = obj; return obj
        def getObject(self, n): return self._map.get(n)
        def removeObject(self, n):
            o = self._map.pop(n, None)
            if o and o in self.Objects: self.Objects.remove(o)
        def recompute(self): pass

    fc.Vector = Vector
    fc._Document = Document
    fc._Object = FreeCADObject
    fc.ActiveDocument = None
    return fc


def _closet_doc(fc):
    """Documento con un armario sencillo de 6 piezas de 18mm."""
    return fc._Document(objects=[
        fc._Object("lat_izq",  "Lateral izq",   400, 18, 2400),
        fc._Object("lat_der",  "Lateral der",   400, 18, 2400),
        fc._Object("techo",    "Techo",          564, 18,  400),
        fc._Object("base",     "Base",           564, 18,  400),
        fc._Object("fondo",    "Fondo",         2364, 18,  400),
        fc._Object("entrepano","Entrepaño",       564, 18,  400),
    ])


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    fc = _make_freecad_mock()
    monkeypatch.setitem(sys.modules, "FreeCAD", fc)
    for mod in ["WoodOptimizer.core.geometry", "WoodOptimizer.mcp.handlers"]:
        if mod in sys.modules:
            monkeypatch.delitem(sys.modules, mod)

    doc = _closet_doc(fc)
    monkeypatch.setattr(state_module, "_state",
                        state_module.WorkbenchState(doc=doc, remnants=[]))
    yield fc


# ─── Pipeline completo ────────────────────────────────────────────────────────

def test_full_pipeline_places_all_pieces():
    """Todas las piezas deben quedar colocadas en el plan."""
    from WoodOptimizer.mcp.handlers import handle_optimize_cuts
    result = handle_optimize_cuts()
    assert "error" not in result
    assert result["pieces_placed"] == 6
    assert result["unplaced"] == []


def test_full_pipeline_efficiency_reasonable():
    """La eficiencia de un armario estándar debe ser > 30%."""
    from WoodOptimizer.mcp.handlers import handle_optimize_cuts
    result = handle_optimize_cuts()
    assert result["efficiency"] > 30.0


def test_full_pipeline_cut_plan_structure():
    """El plan de corte debe tener estructura completa y coherente."""
    from WoodOptimizer.mcp.handlers import handle_optimize_cuts, handle_get_cut_plan
    handle_optimize_cuts()
    plan = handle_get_cut_plan()

    assert "sheets" in plan
    assert len(plan["sheets"]) >= 1
    for sheet in plan["sheets"]:
        assert "pieces" in sheet
        assert "efficiency" in sheet
        assert sheet["width"] > 0
        assert sheet["height"] > 0


def test_pipeline_with_remnant_reduces_sheets():
    """Un retal suficientemente grande debe usarse antes de abrir un tablero nuevo."""
    from WoodOptimizer.mcp.handlers import handle_optimize_cuts, handle_add_remnant

    # Sin retales
    r1 = handle_optimize_cuts()
    sheets_without = r1["sheets_used"]

    # Añadir un retal grande y re-optimizar
    handle_add_remnant(width=2400, height=1200, thickness=18, label="retal_grande")
    r2 = handle_optimize_cuts()
    # El retal debe haber sido aprovechado (no más tableros que sin él)
    assert r2["sheets_used"] <= sheets_without


def test_pipeline_export_csv(tmp_path):
    """Exportar a CSV debe crear un archivo con cabecera y datos."""
    from WoodOptimizer.mcp.handlers import handle_optimize_cuts, handle_export_cutlist
    handle_optimize_cuts()
    result = handle_export_cutlist("csv", str(tmp_path / "corte.csv"))
    assert "error" not in result
    content = (tmp_path / "corte.csv").read_text()
    assert "part_id" in content or "label" in content or len(content) > 10


def test_pipeline_export_json(tmp_path):
    """Exportar a JSON debe producir un objeto parseable con los tableros."""
    from WoodOptimizer.mcp.handlers import handle_optimize_cuts, handle_export_cutlist
    handle_optimize_cuts()
    result = handle_export_cutlist("json", str(tmp_path / "corte.json"))
    assert "error" not in result
    data = json.loads((tmp_path / "corte.json").read_text())
    assert isinstance(data, (dict, list))


def test_pipeline_export_pdf(tmp_path):
    """El PDF debe generarse sin errores y tener tamaño > 0."""
    from WoodOptimizer.mcp.handlers import handle_optimize_cuts, handle_export_cutlist
    handle_optimize_cuts()
    result = handle_export_cutlist("pdf", str(tmp_path / "corte.pdf"))
    assert "error" not in result
    assert (tmp_path / "corte.pdf").stat().st_size > 1000


def test_pipeline_export_unknown_format_returns_error():
    from WoodOptimizer.mcp.handlers import handle_optimize_cuts, handle_export_cutlist
    handle_optimize_cuts()
    result = handle_export_cutlist("xlsx")
    assert "error" in result


# ─── Ciclo retales: optimize → importar → re-optimize ─────────────────────────

def test_remnant_lifecycle(tmp_path):
    """
    Flujo completo:
    1. Optimizar → obtener retales generados
    2. Importar retales al RemnantManager
    3. Persistir a disco
    4. Cargar desde disco en manager nuevo
    5. Los retales cargados deben estar disponibles
    """
    from WoodOptimizer.mcp.handlers import handle_optimize_cuts
    from WoodOptimizer.core.remnant_manager import RemnantManager
    from WoodOptimizer.mcp.state import get_state

    handle_optimize_cuts()
    plan = get_state().last_cut_plan
    assert plan is not None

    mgr = RemnantManager(path=tmp_path / "retales.json")
    imported = mgr.import_from_plan(plan)
    mgr.save()

    mgr2 = RemnantManager(path=tmp_path / "retales.json")
    loaded = mgr2.load()
    assert loaded == imported


# ─── LLM client + execute_tool sin proveedor real ────────────────────────────

def test_execute_tool_get_parts_returns_6_pieces():
    from WoodOptimizer.llm.client import execute_tool
    result = json.loads(execute_tool("get_parts", {}))
    assert isinstance(result, list)
    assert len(result) == 6


def test_execute_tool_optimize_then_export(tmp_path):
    from WoodOptimizer.llm.client import execute_tool
    opt = json.loads(execute_tool("optimize_cuts", {}))
    assert "error" not in opt
    exp = json.loads(execute_tool("export_cutlist", {
        "format": "json", "path": str(tmp_path / "out.json")
    }))
    assert "error" not in exp


def test_llm_chat_tool_loop(tmp_path):
    """
    Simula el flujo LLM completo: el modelo llama a get_parts, luego
    devuelve texto. Verifica que el historial queda correcto.
    """
    from WoodOptimizer.llm.providers.base import LLMResponse, ToolCall
    from WoodOptimizer.llm.client import LLMClient

    class _MockProvider:
        calls = []
        _responses = [
            LLMResponse(tool_calls=[ToolCall(id="1", name="get_parts", arguments={})]),
            LLMResponse(tool_calls=[ToolCall(id="2", name="optimize_cuts", arguments={})]),
            LLMResponse(text="He creado el plan. Hay 6 piezas en 1 tablero."),
        ]
        def complete(self, model, messages, tools=None, system=None):
            self.calls.append(messages)
            return self._responses.pop(0) if self._responses else LLMResponse(text="fin")
        def list_models(self): return []

    provider = _MockProvider()
    client = LLMClient(provider=provider, model="test")
    text, history = client.chat("Diseña un armario", [])

    assert "6" in text or "plan" in text.lower()
    # 3 rondas LLM: get_parts → optimize_cuts → respuesta final
    assert len(provider.calls) == 3
    tool_msgs = [m for m in history if m.get("role") == "tool"]
    assert len(tool_msgs) == 2
