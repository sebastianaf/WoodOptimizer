from __future__ import annotations
from .models import Part

try:
    import FreeCAD as _FC
    HAS_FREECAD = True
except ImportError:
    HAS_FREECAD = False


def extract_parts(doc=None) -> list[Part]:
    """
    Lee todos los objetos con Shape del documento FreeCAD activo.
    Convención de ejes igual a Woodworking workbench:
      X = largo (length), Y = espesor (thickness), Z = ancho (width)
    """
    if not HAS_FREECAD:
        raise RuntimeError("FreeCAD no está disponible en este entorno")

    if doc is None:
        doc = _FC.ActiveDocument
    if doc is None:
        raise RuntimeError("No hay ningún documento FreeCAD activo")

    parts = []
    for obj in doc.Objects:
        if not hasattr(obj, "Shape") or obj.Shape.isNull():
            continue
        bb = obj.Shape.BoundBox
        material = getattr(obj, "Material", None)
        if hasattr(material, "Name"):
            material = material.Name
        parts.append(Part(
            id=obj.Name,
            label=obj.Label,
            length=round(bb.XLength),
            width=round(bb.ZLength),
            thickness=round(bb.YLength),
            material=material or "melamina_blanco",
        ))
    return parts


def create_part(
    doc,
    name: str,
    length: float,
    width: float,
    thickness: float,
    x: float = 0,
    y: float = 0,
    z: float = 0,
) -> object:
    """
    Crea un Part::Box en el documento FreeCAD.
    Ejes: X = largo, Y = espesor, Z = ancho (igual a Woodworking WB).
    Llamado por el handler MCP de create_part.
    """
    if not HAS_FREECAD:
        raise RuntimeError("FreeCAD no está disponible en este entorno")

    box = doc.addObject("Part::Box", name)
    box.Label = name
    box.Length = length
    box.Width = thickness    # Y = espesor
    box.Height = width       # Z = ancho
    box.Placement = _FC.Placement(_FC.Vector(x, y, z), _FC.Rotation())
    doc.recompute()
    return box


def update_part(
    doc,
    name: str,
    length: float | None = None,
    width: float | None = None,
    thickness: float | None = None,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
) -> object:
    """Modifica dimensiones o posición de una pieza existente en FreeCAD."""
    if not HAS_FREECAD:
        raise RuntimeError("FreeCAD no está disponible en este entorno")

    obj = doc.getObject(name)
    if obj is None:
        raise ValueError(f"Objeto '{name}' no encontrado en el documento")

    if length is not None:
        obj.Length = length
    if thickness is not None:
        obj.Width = thickness
    if width is not None:
        obj.Height = width
    if x is not None or y is not None or z is not None:
        base = obj.Placement.Base
        obj.Placement = _FC.Placement(
            _FC.Vector(
                x if x is not None else base.x,
                y if y is not None else base.y,
                z if z is not None else base.z,
            ),
            obj.Placement.Rotation,
        )

    doc.recompute()
    return obj


def delete_part(doc, name: str) -> None:
    """Elimina un objeto por nombre del documento FreeCAD."""
    if not HAS_FREECAD:
        raise RuntimeError("FreeCAD no está disponible en este entorno")

    obj = doc.getObject(name)
    if obj is None:
        raise ValueError(f"Objeto '{name}' no encontrado en el documento")
    doc.removeObject(name)
    doc.recompute()
