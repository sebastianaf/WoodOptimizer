from __future__ import annotations
from dataclasses import dataclass, field
from ..core.models import CutPlan, Remnant


@dataclass
class WorkbenchState:
    """Estado mutable compartido entre el servidor MCP y FreeCAD."""
    doc: object = None                         # FreeCAD.Document activo (o None)
    last_cut_plan: CutPlan | None = None       # último plan calculado
    remnants: list[Remnant] = field(default_factory=list)  # retales registrados


_state = WorkbenchState()


def get_state() -> WorkbenchState:
    return _state


def set_document(doc: object) -> None:
    """Llamado desde InitGui cuando el usuario abre/cambia documento."""
    _state.doc = doc
