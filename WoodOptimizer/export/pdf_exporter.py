"""
Exportación del plan de corte a PDF con diagramas visuales.
Requiere reportlab (incluido en FreeCAD AppImage y la mayoría de distros).
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.models import CutPlan

# Paleta de colores para las piezas (R, G, B en 0-1)
_COLORS = [
    (0.53, 0.81, 0.98),  # azul claro
    (0.67, 0.94, 0.67),  # verde claro
    (1.00, 0.85, 0.56),  # naranja claro
    (0.90, 0.70, 0.90),  # lila claro
    (1.00, 0.75, 0.75),  # rosa claro
    (0.75, 0.90, 0.90),  # cian claro
    (0.95, 0.95, 0.60),  # amarillo claro
    (0.80, 0.80, 0.80),  # gris claro
]

_PAGE_MARGIN = 40  # pt
_SHEET_HEADER = 14  # pt
_SHEET_GAP = 20    # pt


def export(plan: "CutPlan", path: str | None = None) -> str:
    """
    Genera un PDF con una página por tablero, cada pieza en color.

    Args:
        plan: Plan de corte calculado.
        path: Ruta de salida. Si es None usa ~/woodoptimizer_cutplan.pdf.

    Returns:
        Ruta absoluta del archivo generado.
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl_colors

    if path is None:
        path = str(Path.home() / "woodoptimizer_cutplan.pdf")

    page_w, page_h = A4  # 595 x 842 pt
    c = canvas.Canvas(path, pagesize=A4)
    c.setTitle("Plan de Corte — WoodOptimizer")

    # ── Portada / resumen ─────────────────────────────────────────────────────
    _draw_summary_page(c, plan, page_w, page_h)
    c.showPage()

    # ── Una página por tablero ────────────────────────────────────────────────
    color_map: dict[str, tuple[float, float, float]] = {}

    for idx, layout in enumerate(plan.layouts):
        _draw_sheet_page(c, layout, idx + 1, len(plan.layouts),
                         page_w, page_h, color_map)
        c.showPage()

    c.save()
    return os.path.abspath(path)


def _draw_summary_page(c, plan, pw, ph):
    from reportlab.lib.units import mm

    c.setFont("Helvetica-Bold", 18)
    c.drawString(_PAGE_MARGIN, ph - _PAGE_MARGIN - 18, "WoodOptimizer — Plan de Corte")

    c.setFont("Helvetica", 11)
    y = ph - _PAGE_MARGIN - 50
    lines = [
        f"Tableros usados:  {len(plan.layouts)}",
        f"Eficiencia global: {plan.efficiency * 100:.1f}%",
        f"Piezas colocadas: "
        f"{sum(len(l.placed) for l in plan.layouts)}",
        f"Piezas no ubicadas: {len(plan.unplaced)}",
        f"Retales generados: {len(plan.remnants)}",
    ]
    for line in lines:
        c.drawString(_PAGE_MARGIN, y, line)
        y -= 16

    if plan.unplaced:
        y -= 8
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0.8, 0, 0)
        c.drawString(_PAGE_MARGIN, y, "Piezas NO ubicadas:")
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", 10)
        y -= 14
        for pid in plan.unplaced:
            c.drawString(_PAGE_MARGIN + 10, y, f"• {pid}")
            y -= 13

    if plan.remnants:
        y -= 8
        c.setFont("Helvetica-Bold", 11)
        c.drawString(_PAGE_MARGIN, y, "Retales aprovechables:")
        c.setFont("Helvetica", 10)
        y -= 14
        for r in plan.remnants:
            label = r.label or "retal"
            c.drawString(_PAGE_MARGIN + 10, y,
                         f"• {label}: {r.width}×{r.height} mm  "
                         f"({r.area / 1_000_000:.3f} m²)")
            y -= 13
            if y < _PAGE_MARGIN + 30:
                break


def _draw_sheet_page(c, layout, sheet_num, total, pw, ph, color_map):
    # ── Título ────────────────────────────────────────────────────────────────
    title = (f"Tablero {sheet_num}/{total}"
             f"  {'(retal)' if layout.is_remnant else ''}"
             f"  {layout.sheet.width}×{layout.sheet.height} mm"
             f"  —  eficiencia {layout.efficiency * 100:.1f}%")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(_PAGE_MARGIN, ph - _PAGE_MARGIN - 11, title)

    # ── Calcular escala para que el tablero quepa en la página ────────────────
    available_w = pw - 2 * _PAGE_MARGIN
    available_h = ph - 2 * _PAGE_MARGIN - _SHEET_HEADER - _SHEET_GAP

    scale = min(
        available_w / layout.sheet.width,
        available_h / layout.sheet.height,
    )

    origin_x = _PAGE_MARGIN
    origin_y = ph - _PAGE_MARGIN - _SHEET_HEADER - _SHEET_GAP - layout.sheet.height * scale

    # ── Fondo del tablero ─────────────────────────────────────────────────────
    c.setFillColorRGB(0.97, 0.97, 0.92)
    c.setStrokeColorRGB(0.3, 0.3, 0.3)
    c.rect(origin_x, origin_y,
           layout.sheet.width * scale, layout.sheet.height * scale,
           fill=1, stroke=1)

    # ── Piezas ────────────────────────────────────────────────────────────────
    c.setFont("Helvetica", 7)
    for i, placed in enumerate(layout.placed):
        if placed.part_id not in color_map:
            color_map[placed.part_id] = _COLORS[len(color_map) % len(_COLORS)]
        r, g, b = color_map[placed.part_id]

        x = origin_x + placed.x * scale
        y = origin_y + placed.y * scale
        w = placed.width * scale
        h = placed.height * scale

        c.setFillColorRGB(r, g, b)
        c.setStrokeColorRGB(0.2, 0.2, 0.2)
        c.rect(x, y, w, h, fill=1, stroke=1)

        # Etiqueta centrada si hay espacio
        label = placed.part_id
        if w > 20 and h > 10:
            c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(x + w / 2, y + h / 2 - 3, label[:16])
            if placed.rotated:
                c.drawCentredString(x + w / 2, y + h / 2 - 10, "(R)")

    # ── Dimensiones tablero ───────────────────────────────────────────────────
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(
        origin_x + layout.sheet.width * scale / 2,
        origin_y - 10,
        f"{layout.sheet.width} mm",
    )
    c.drawString(
        origin_x + layout.sheet.width * scale + 4,
        origin_y + layout.sheet.height * scale / 2 - 4,
        f"{layout.sheet.height} mm",
    )
