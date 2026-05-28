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
    # Auto-sync: if doc is None, try to grab whatever FreeCAD has active now.
    # This handles the case where the workbench was activated before any
    # document was open, or a new document was created after activation.
    if _state.doc is None:
        try:
            import FreeCAD
            if FreeCAD.ActiveDocument is not None:
                _state.doc = FreeCAD.ActiveDocument
        except Exception:
            pass
    return _state


def set_document(doc: object) -> None:
    _state.doc = doc
