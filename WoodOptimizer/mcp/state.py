from __future__ import annotations
from dataclasses import dataclass, field
from ..core.models import CutPlan, Remnant


@dataclass
class WorkbenchState:
    doc: object = None
    last_cut_plan: CutPlan | None = None
    remnants: list[Remnant] = field(default_factory=list)


_state = WorkbenchState()


def get_state() -> WorkbenchState:
    # Always sync with whatever document FreeCAD has active right now.
    # This covers: workbench activated before any doc was open, user opened
    # a new doc after activation, or user switched between documents.
    try:
        import FreeCAD
        if FreeCAD.ActiveDocument is not None:
            _state.doc = FreeCAD.ActiveDocument
    except Exception:
        pass
    return _state


def set_document(doc: object) -> None:
    _state.doc = doc
