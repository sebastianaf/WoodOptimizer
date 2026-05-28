from __future__ import annotations
import csv
import os
from ..core.models import CutPlan


def export(plan: CutPlan, path: str | None = None) -> str:
    """Exporta la lista de corte como CSV. Retorna la ruta del archivo."""
    if path is None:
        path = os.path.join(os.path.expanduser("~"), "cutlist.csv")

    rows = []
    for i, layout in enumerate(plan.layouts, 1):
        for p in layout.placed:
            rows.append({
                "sheet": i,
                "sheet_width": layout.sheet.width,
                "sheet_height": layout.sheet.height,
                "is_remnant": layout.is_remnant,
                "part_id": p.part_id,
                "x": p.x,
                "y": p.y,
                "width": p.width,
                "height": p.height,
                "rotated": p.rotated,
            })

    with open(path, "w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    return path
