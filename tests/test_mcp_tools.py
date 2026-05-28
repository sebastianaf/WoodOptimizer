"""Tests de los handlers MCP (sin FreeCAD ni servidor HTTP)."""
import sys
import types
import pytest
from WoodOptimizer.core.models import Remnant, Sheet
from WoodOptimizer.mcp import state as state_module


# ─── Mock de FreeCAD ─────────────────────────────────────────────────────────

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
        def isNull(self):
            return self._null

    class FreeCADObject:
        def __init__(self, name, label, xl, yl, zl, material=None):
            self.Name = name
            self.Label = label
            self.Shape = Shape(xl, yl, zl)
            self.Placement = Placement()
            self.Length = xl
            self.Width = yl
            self.Height = zl
            if material:
                self.Material = material

    class Document:
        def __init__(self, objects=None):
            self.Objects = list(objects or [])
            self._map = {o.Name: o for o in self.Objects}

        def addObject(self, obj_type, name):
            obj = FreeCADObject(name, name, 0, 0, 0)
            self.Objects.append(obj)
            self._map[name] = obj
            return obj

        def getObject(self, name):
            return self._map.get(name)

        def removeObject(self, name):
            obj = self._map.pop(name, None)
            if obj and obj in self.Objects:
                self.Objects.remove(obj)

        def recompute(self):
            pass

    fc.Vector = Vector
    fc._Document = Document
    fc._Object = FreeCADObject
    fc.ActiveDocument = None
    return fc


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    """Reinicia el estado y el mock de FreeCAD antes de cada test."""
    mock_fc = _make_freecad_mock()
    monkeypatch.setitem(sys.modules, "FreeCAD", mock_fc)

    for mod in ["WoodOptimizer.core.geometry", "WoodOptimizer.mcp.handlers"]:
        if mod in sys.modules:
            monkeypatch.delitem(sys.modules, mod)

    # Documento con algunas piezas precargadas
    doc = mock_fc._Document(objects=[
        mock_fc._Object("lat_1", "Lateral",    400, 18, 2400),
        mock_fc._Object("lat_2", "Lateral",    400, 18, 2400),
        mock_fc._Object("tec",   "Techo",      564, 18,  400),
        mock_fc._Object("bas",   "Base",       564, 18,  400),
        mock_fc._Object("ent_1", "Entrepano",  564, 18,  400),
    ])

    # Resetear estado limpio
    monkeypatch.setattr(state_module, "_state",
                        state_module.WorkbenchState(doc=doc, remnants=[]))
    yield mock_fc


def _handlers():
    from WoodOptimizer.mcp import handlers
    return handlers


# ─── get_parts ───────────────────────────────────────────────────────────────

def test_get_parts_returns_all():
    h = _handlers()
    parts = h.handle_get_parts()
    assert len(parts) == 5


def test_get_parts_fields():
    h = _handlers()
    p = h.handle_get_parts()[0]
    assert {"id", "label", "length", "width", "thickness", "material"} <= set(p)


def test_get_parts_material_filter():
    h = _handlers()
    # Agregar una pieza con material distinto
    state_module.get_state().doc._map["lat_1"].Material = "pino"
    # Sin filtro: 5 piezas
    assert len(h.handle_get_parts()) == 5
    # Con filtro por material que no existe: 0 piezas
    assert len(h.handle_get_parts("madera_exotica")) == 0


# ─── create_part ─────────────────────────────────────────────────────────────

def test_create_part_adds_to_document():
    h = _handlers()
    result = h.handle_create_part("nuevo", 800, 400, 18)
    assert result["created"] == "nuevo"
    doc = state_module.get_state().doc
    assert doc.getObject("nuevo") is not None


def test_create_part_dimensions_stored():
    h = _handlers()
    h.handle_create_part("panel", 1000, 500, 15)
    obj = state_module.get_state().doc.getObject("panel")
    assert obj.Length == 1000
    assert obj.Width == 15    # espesor → Width en FreeCAD
    assert obj.Height == 500  # ancho → Height en FreeCAD


# ─── update_part ─────────────────────────────────────────────────────────────

def test_update_part_changes_length():
    h = _handlers()
    h.handle_update_part("lat_1", length=500)
    obj = state_module.get_state().doc.getObject("lat_1")
    assert obj.Length == 500


def test_update_part_unknown_raises():
    h = _handlers()
    with pytest.raises(ValueError, match="no encontrado"):
        h.handle_update_part("inexistente", length=100)


# ─── delete_part ─────────────────────────────────────────────────────────────

def test_delete_part_removes_from_document():
    h = _handlers()
    h.handle_delete_part("lat_1")
    doc = state_module.get_state().doc
    assert doc.getObject("lat_1") is None


def test_delete_part_unknown_raises():
    h = _handlers()
    with pytest.raises(ValueError, match="no encontrado"):
        h.handle_delete_part("fantasma")


# ─── optimize_cuts ───────────────────────────────────────────────────────────

def test_optimize_cuts_returns_summary():
    h = _handlers()
    result = h.handle_optimize_cuts()
    assert "sheets_used" in result
    assert "efficiency" in result
    assert "pieces_placed" in result


def test_optimize_cuts_places_all_pieces():
    h = _handlers()
    result = h.handle_optimize_cuts(thickness=18)
    assert result["pieces_placed"] == 5
    assert result["unplaced"] == []


def test_optimize_cuts_stores_plan():
    h = _handlers()
    h.handle_optimize_cuts()
    assert state_module.get_state().last_cut_plan is not None


def test_optimize_cuts_no_pieces_of_thickness():
    h = _handlers()
    result = h.handle_optimize_cuts(thickness=30)
    assert "error" in result


# ─── get_cut_plan ─────────────────────────────────────────────────────────────

def test_get_cut_plan_without_optimize_returns_error():
    h = _handlers()
    result = h.handle_get_cut_plan()
    assert "error" in result


def test_get_cut_plan_after_optimize():
    h = _handlers()
    h.handle_optimize_cuts()
    plan = h.handle_get_cut_plan()
    assert "sheets" in plan
    assert "efficiency" in plan
    assert isinstance(plan["sheets"], list)


def test_get_cut_plan_structure():
    h = _handlers()
    h.handle_optimize_cuts()
    plan = h.handle_get_cut_plan()
    sheet = plan["sheets"][0]
    assert {"sheet", "width", "height", "is_remnant", "efficiency", "pieces"} <= set(sheet)


# ─── get_remnants / add_remnant ───────────────────────────────────────────────

def test_get_remnants_empty_initially():
    h = _handlers()
    assert h.handle_get_remnants() == []


def test_add_remnant_stores_it():
    h = _handlers()
    h.handle_add_remnant(700, 500, 18, "retal_taller")
    remnants = h.handle_get_remnants()
    assert len(remnants) == 1
    assert remnants[0]["label"] == "retal_taller"


def test_add_remnant_autolabel():
    h = _handlers()
    h.handle_add_remnant(700, 500, 18)
    rem = h.handle_get_remnants()[0]
    assert rem["label"].startswith("retal_")


def test_remnant_used_in_optimization():
    h = _handlers()
    h.handle_add_remnant(700, 600, 18, "retal_grande")
    result = h.handle_optimize_cuts()
    # El retal debe ser considerado (aunque las piezas pueden no caber)
    assert "sheets_used" in result


# ─── export_cutlist ───────────────────────────────────────────────────────────

def test_export_without_plan_returns_error():
    h = _handlers()
    result = h.handle_export_cutlist("csv")
    assert "error" in result


def test_export_csv(tmp_path):
    h = _handlers()
    h.handle_optimize_cuts()
    out = tmp_path / "test.csv"
    result = h.handle_export_cutlist("csv", str(out))
    assert result["exported"] == "csv"
    assert out.exists()
    assert out.stat().st_size > 0


def test_export_json(tmp_path):
    h = _handlers()
    h.handle_optimize_cuts()
    out = tmp_path / "test.json"
    result = h.handle_export_cutlist("json", str(out))
    assert result["exported"] == "json"
    import json
    data = json.loads(out.read_text())
    assert "sheets" in data
    assert "efficiency" in data


def test_export_unknown_format():
    h = _handlers()
    h.handle_optimize_cuts()
    result = h.handle_export_cutlist("xlsx")
    assert "error" in result


def test_export_csv_content(tmp_path):
    h = _handlers()
    h.handle_optimize_cuts()
    out = tmp_path / "cutlist.csv"
    h.handle_export_cutlist("csv", str(out))
    lines = out.read_text().splitlines()
    # Cabecera + al menos una fila por pieza
    assert len(lines) >= 2
    assert "part_id" in lines[0]
