from __future__ import annotations
import json
from ..core.models import Sheet, Remnant
from ..core.bin_packing import Rect, optimize
from ..core import geometry
from .state import get_state


# ─── Piezas ───────────────────────────────────────────────────────────────────

def handle_get_parts(material_filter: str | None = None) -> list[dict]:
    state = get_state()
    parts = geometry.extract_parts(state.doc)
    if material_filter:
        parts = [p for p in parts if p.material == material_filter]
    return [
        {
            "id": p.id, "label": p.label,
            "length": p.length, "width": p.width, "thickness": p.thickness,
            "material": p.material,
        }
        for p in parts
    ]


def handle_create_part(
    name: str,
    length: float,
    width: float,
    thickness: float,
    x: float = 0,
    y: float = 0,
    z: float = 0,
    material: str = "melamina_blanco",
) -> dict:
    state = get_state()
    obj = geometry.create_part(state.doc, name, length, width, thickness, x, y, z)
    return {"created": name, "length": length, "width": width, "thickness": thickness}


def handle_update_part(
    name: str,
    length: float | None = None,
    width: float | None = None,
    thickness: float | None = None,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
) -> dict:
    state = get_state()
    geometry.update_part(state.doc, name, length=length, width=width,
                         thickness=thickness, x=x, y=y, z=z)
    return {"updated": name}


def handle_delete_part(name: str) -> dict:
    state = get_state()
    geometry.delete_part(state.doc, name)
    return {"deleted": name}


# ─── Optimización ─────────────────────────────────────────────────────────────

def handle_optimize_cuts(
    sheet_width: int = 2440,
    sheet_height: int = 1220,
    thickness: int = 18,
    kerf: int = 3,
    prefer_large_remnants: bool = True,
) -> dict:
    state = get_state()
    raw_parts = geometry.extract_parts(state.doc)

    # Filtrar por espesor y convertir a Rect 2D
    rects = [
        Rect(width=p.length, height=p.width, part_id=p.id)
        for p in raw_parts
        if p.thickness == thickness
    ]

    if not rects:
        return {"error": f"No hay piezas con espesor {thickness}mm en el documento"}

    sheet = Sheet(width=sheet_width, height=sheet_height, thickness=thickness, kerf=kerf)
    plan = optimize(rects, sheet, available_remnants=state.remnants,
                    prefer_large_remnants=prefer_large_remnants)
    state.last_cut_plan = plan

    return {
        "sheets_used": len(plan.layouts),
        "efficiency": round(plan.efficiency * 100, 1),
        "pieces_placed": sum(len(l.placed) for l in plan.layouts),
        "unplaced": plan.unplaced,
        "remnants_generated": len(plan.remnants),
    }


def handle_get_cut_plan() -> dict:
    state = get_state()
    if state.last_cut_plan is None:
        return {"error": "No hay ningún plan calculado. Ejecuta optimize_cuts primero."}

    plan = state.last_cut_plan
    sheets = []
    for i, layout in enumerate(plan.layouts):
        sheets.append({
            "sheet": i + 1,
            "width": layout.sheet.width,
            "height": layout.sheet.height,
            "is_remnant": layout.is_remnant,
            "efficiency": round(layout.efficiency * 100, 1),
            "pieces": [
                {
                    "part_id": p.part_id, "x": p.x, "y": p.y,
                    "width": p.width, "height": p.height, "rotated": p.rotated,
                }
                for p in layout.placed
            ],
        })

    return {
        "efficiency": round(plan.efficiency * 100, 1),
        "sheets": sheets,
        "remnants": [
            {"width": r.width, "height": r.height, "thickness": r.thickness, "label": r.label}
            for r in plan.remnants
        ],
        "unplaced": plan.unplaced,
    }


# ─── Retales ──────────────────────────────────────────────────────────────────

def handle_get_remnants() -> list[dict]:
    state = get_state()
    return [
        {"width": r.width, "height": r.height, "thickness": r.thickness, "label": r.label}
        for r in state.remnants
    ]


def handle_add_remnant(
    width: int,
    height: int,
    thickness: int,
    label: str = "",
) -> dict:
    state = get_state()
    rem = Remnant(width=width, height=height, thickness=thickness,
                  label=label or f"retal_{len(state.remnants)+1}")
    state.remnants.append(rem)
    return {"added": rem.label, "width": width, "height": height, "thickness": thickness}


# ─── Exportación ──────────────────────────────────────────────────────────────

def handle_export_cutlist(format: str, path: str | None = None) -> dict:
    state = get_state()
    if state.last_cut_plan is None:
        return {"error": "No hay plan calculado. Ejecuta optimize_cuts primero."}

    from ..export import csv_exporter, json_exporter, pdf_exporter
    exporters = {
        "csv":  csv_exporter.export,
        "json": json_exporter.export,
        "pdf":  pdf_exporter.export,
    }

    if format not in exporters:
        return {"error": f"Formato '{format}' no soportado. Usa: csv, json, pdf"}

    out_path = exporters[format](state.last_cut_plan, path)
    return {"exported": format, "path": out_path}
