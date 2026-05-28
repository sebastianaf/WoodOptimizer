"""Tests de geometry.py con FreeCAD mockeado (sin FreeCAD instalado)."""
import sys
import types
import pytest


# ─── Mock de FreeCAD antes de importar geometry ──────────────────────────────

def _make_freecad_mock():
    """Crea un módulo FreeCAD mínimo que satisface las importaciones."""
    fc = types.ModuleType("FreeCAD")

    class Vector:
        def __init__(self, x=0, y=0, z=0):
            self.x, self.y, self.z = x, y, z

    class Placement:
        def __init__(self):
            self.Base = Vector()

    class BoundBox:
        def __init__(self, xl, yl, zl):
            self.XLength = xl
            self.YLength = yl
            self.ZLength = zl

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
            if material:
                self.Material = material

    class Document:
        def __init__(self, objects=None):
            self.Objects = objects or []
            self._objects = {o.Name: o for o in self.Objects}

        def addObject(self, obj_type, name):
            obj = FreeCADObject(name, name, 0, 0, 0)
            obj.Placement = Placement()
            obj.Length = 0
            obj.Width = 0
            obj.Height = 0
            self.Objects.append(obj)
            self._objects[name] = obj
            return obj

        def getObject(self, name):
            return self._objects.get(name)

        def removeObject(self, name):
            obj = self._objects.pop(name, None)
            if obj and obj in self.Objects:
                self.Objects.remove(obj)

        def recompute(self):
            pass

    fc.Vector = Vector
    fc.ActiveDocument = None
    fc._Document = Document
    fc._FreeCADObject = FreeCADObject
    fc._Shape = Shape
    return fc


@pytest.fixture(autouse=True)
def patch_freecad(monkeypatch):
    """Inyecta el mock de FreeCAD en sys.modules antes de cada test."""
    mock_fc = _make_freecad_mock()
    monkeypatch.setitem(sys.modules, "FreeCAD", mock_fc)
    # Forzar re-importación de geometry con el mock
    if "WoodOptimizer.core.geometry" in sys.modules:
        monkeypatch.delitem(sys.modules, "WoodOptimizer.core.geometry")
    yield mock_fc


def _import_geometry():
    from WoodOptimizer.core import geometry
    return geometry


# ─── Tests extract_parts ─────────────────────────────────────────────────────

def test_extract_parts_empty_document(patch_freecad):
    geo = _import_geometry()
    doc = patch_freecad._Document(objects=[])
    parts = geo.extract_parts(doc)
    assert parts == []


def test_extract_parts_single_object(patch_freecad):
    geo = _import_geometry()
    obj = patch_freecad._FreeCADObject("Box", "Lateral", 600.0, 18.0, 2400.0)
    doc = patch_freecad._Document(objects=[obj])

    parts = geo.extract_parts(doc)

    assert len(parts) == 1
    p = parts[0]
    assert p.id == "Box"
    assert p.label == "Lateral"
    assert p.length == 600    # XLength
    assert p.thickness == 18  # YLength
    assert p.width == 2400    # ZLength


def test_extract_parts_skips_null_shapes(patch_freecad):
    geo = _import_geometry()

    class NullShapeObj:
        Name = "Null"
        Label = "Null"
        Shape = patch_freecad._Shape(null=True)

    doc = patch_freecad._Document(objects=[NullShapeObj()])
    parts = geo.extract_parts(doc)
    assert parts == []


def test_extract_parts_skips_objects_without_shape(patch_freecad):
    geo = _import_geometry()

    class NoShape:
        Name = "Sketch"
        Label = "Sketch"

    doc = patch_freecad._Document(objects=[NoShape()])
    parts = geo.extract_parts(doc)
    assert parts == []


def test_extract_parts_multiple_objects(patch_freecad):
    geo = _import_geometry()
    objs = [
        patch_freecad._FreeCADObject(f"Box{i}", f"Pieza{i}", 600.0, 18.0, float(400 + i * 100))
        for i in range(3)
    ]
    doc = patch_freecad._Document(objects=objs)
    parts = geo.extract_parts(doc)
    assert len(parts) == 3


def test_extract_parts_default_material(patch_freecad):
    geo = _import_geometry()
    obj = patch_freecad._FreeCADObject("Box", "Panel", 600.0, 18.0, 400.0)
    doc = patch_freecad._Document(objects=[obj])

    parts = geo.extract_parts(doc)
    assert parts[0].material == "melamina_blanco"


def test_extract_parts_no_active_document_raises(patch_freecad):
    geo = _import_geometry()
    patch_freecad.ActiveDocument = None

    with pytest.raises(RuntimeError, match="No hay ningún documento"):
        geo.extract_parts()


# ─── Tests create_part ────────────────────────────────────────────────────────

def test_create_part_adds_object(patch_freecad):
    geo = _import_geometry()
    doc = patch_freecad._Document()
    obj = geo.create_part(doc, "Lateral", length=600, width=2400, thickness=18)
    assert obj is not None
    assert obj.Name == "Lateral"


def test_create_part_sets_dimensions(patch_freecad):
    geo = _import_geometry()
    doc = patch_freecad._Document()
    obj = geo.create_part(doc, "Panel", length=800, width=400, thickness=15)

    # Según convención: Length=largo, Width=espesor, Height=ancho
    assert obj.Length == 800
    assert obj.Width == 15
    assert obj.Height == 400


def test_create_part_sets_position(patch_freecad):
    geo = _import_geometry()
    doc = patch_freecad._Document()
    obj = geo.create_part(doc, "Panel", length=600, width=400, thickness=18, x=100, y=50, z=200)

    assert obj.Placement.Base.x == 100
    assert obj.Placement.Base.y == 50
    assert obj.Placement.Base.z == 200


# ─── Tests delete_part ────────────────────────────────────────────────────────

def test_delete_part_removes_object(patch_freecad):
    geo = _import_geometry()
    obj = patch_freecad._FreeCADObject("Box", "Panel", 600.0, 18.0, 400.0)
    doc = patch_freecad._Document(objects=[obj])

    geo.delete_part(doc, "Box")
    assert doc.getObject("Box") is None


def test_delete_part_raises_if_not_found(patch_freecad):
    geo = _import_geometry()
    doc = patch_freecad._Document()

    with pytest.raises(ValueError, match="no encontrado"):
        geo.delete_part(doc, "Inexistente")


# ─── Test sin FreeCAD ─────────────────────────────────────────────────────────

def test_raises_without_freecad(monkeypatch):
    """Sin FreeCAD instalado, las funciones deben lanzar RuntimeError."""
    monkeypatch.delitem(sys.modules, "FreeCAD", raising=False)
    if "WoodOptimizer.core.geometry" in sys.modules:
        monkeypatch.delitem(sys.modules, "WoodOptimizer.core.geometry")

    from WoodOptimizer.core import geometry
    # Simular que HAS_FREECAD es False
    monkeypatch.setattr(geometry, "HAS_FREECAD", False)

    with pytest.raises(RuntimeError, match="FreeCAD no está disponible"):
        geometry.extract_parts()
