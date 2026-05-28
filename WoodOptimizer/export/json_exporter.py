from __future__ import annotations
import json
import os
from ..core.models import CutPlan


def export(plan: CutPlan, path: str | None = None) -> str:
    """Exporta la lista de corte como JSON. Retorna la ruta del archivo."""
    if path is None:
        path = os.path.join(os.path.expanduser("~"), "cutlist.json")

    data = {
        "efficiency": round(plan.efficiency * 100, 1),
        "sheets": [
            {
                "index": i + 1,
                "width": l.sheet.width,
                "height": l.sheet.height,
                "thickness": l.sheet.thickness,
                "is_remnant": l.is_remnant,
                "efficiency": round(l.efficiency * 100, 1),
                "pieces": [
                    {
                        "part_id": p.part_id, "x": p.x, "y": p.y,
                        "width": p.width, "height": p.height, "rotated": p.rotated,
                    }
                    for p in l.placed
                ],
            }
            for i, l in enumerate(plan.layouts)
        ],
        "remnants": [
            {"width": r.width, "height": r.height, "thickness": r.thickness, "label": r.label}
            for r in plan.remnants
        ],
        "unplaced": plan.unplaced,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return path
