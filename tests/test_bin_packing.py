"""Tests del algoritmo guillotina 2D bin packing (port de OpenCutList)."""
import pytest
from WoodOptimizer.core.models import Sheet, Remnant
from WoodOptimizer.core.bin_packing import Rect, optimize, SPLIT_MAXIMIZE_AREA, SPLIT_SHORTERLEFTOVER


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def std_sheet():
    return Sheet(width=2440, height=1220, thickness=18, kerf=3)


def _make_rects(*dims) -> list[Rect]:
    """Crea Rects desde tuplas (width, height, id)."""
    return [Rect(width=w, height=h, part_id=pid) for w, h, pid in dims]


# ─── Tests básicos ────────────────────────────────────────────────────────────

def test_empty_parts_returns_empty_plan(std_sheet):
    plan = optimize([], std_sheet)
    assert plan.layouts == []
    assert plan.remnants == []
    assert plan.efficiency == 0.0


def test_single_part_fits_in_one_sheet(std_sheet):
    parts = _make_rects((500, 400, "p1"))
    plan = optimize(parts, std_sheet)

    assert len(plan.layouts) == 1
    assert len(plan.layouts[0].placed) == 1
    assert plan.layouts[0].placed[0].part_id == "p1"
    assert plan.unplaced == []


def test_single_part_placed_at_origin(std_sheet):
    parts = _make_rects((500, 400, "p1"))
    plan = optimize(parts, std_sheet)

    p = plan.layouts[0].placed[0]
    assert p.x == 0
    assert p.y == 0


def test_efficiency_single_part(std_sheet):
    parts = _make_rects((2440, 1220, "p1"))  # ocupa tablero completo
    plan = optimize(parts, std_sheet)

    assert plan.efficiency == pytest.approx(1.0, abs=0.01)


def test_efficiency_partial(std_sheet):
    # pieza que ocupa exactamente la mitad del tablero
    parts = _make_rects((1220, 1220, "p1"))
    plan = optimize(parts, std_sheet)

    assert plan.efficiency == pytest.approx(0.5, abs=0.01)


# ─── BFD: piezas grandes primero ─────────────────────────────────────────────

def test_bfd_large_part_placed_first(std_sheet):
    """Las piezas más grandes deben ocupar la primera posición (BFD)."""
    parts = _make_rects(
        (300, 200, "small"),
        (1000, 800, "large"),
    )
    plan = optimize(parts, std_sheet)

    # Con BFD la pieza grande se ubica en (0,0)
    large_placed = next(p for p in plan.layouts[0].placed if p.part_id == "large")
    assert large_placed.x == 0
    assert large_placed.y == 0


# ─── Múltiples piezas y tableros ─────────────────────────────────────────────

def test_multiple_parts_same_sheet(std_sheet):
    parts = _make_rects(
        (600, 400, "p1"),
        (600, 400, "p2"),
    )
    plan = optimize(parts, std_sheet)

    assert len(plan.layouts) == 1
    assert len(plan.layouts[0].placed) == 2


def test_overflow_opens_second_sheet(std_sheet):
    """Piezas que no caben en un tablero deben abrirlo nuevo."""
    # Cada pieza ocupa casi el tablero completo
    parts = _make_rects(
        (2400, 1200, "p1"),
        (2400, 1200, "p2"),
    )
    plan = optimize(parts, std_sheet)

    assert len(plan.layouts) == 2
    assert all(len(l.placed) == 1 for l in plan.layouts)


def test_many_small_parts_packed_efficiently(std_sheet):
    """Muchas piezas pequeñas deben caber en un solo tablero."""
    parts = _make_rects(*[(300, 200, f"p{i}") for i in range(10)])
    plan = optimize(parts, std_sheet)

    assert len(plan.layouts) == 1
    assert len(plan.unplaced) == 0


# ─── Rotación ─────────────────────────────────────────────────────────────────

def test_rotation_used_when_needed(std_sheet):
    """Una pieza más ancha que alta debe rotarse si no cabe normal."""
    # Tablero apaisado: 1220×2440 (rotado respecto al estándar)
    narrow_sheet = Sheet(width=1220, height=2440, thickness=18, kerf=3)
    # Pieza que solo cabe rotada: 2000×300 no cabe en 1220 de ancho
    parts = _make_rects((2000, 300, "p1"))
    plan = optimize(parts, narrow_sheet)

    assert len(plan.layouts) == 1
    p = plan.layouts[0].placed[0]
    assert p.rotated is True
    # Tras rotación: width=300, height=2000 → cabe en 1220×2440
    assert p.width == 300
    assert p.height == 2000


def test_rotation_not_applied_when_not_needed(std_sheet):
    parts = [Rect(width=500, height=300, part_id="p1", rotatable=False)]
    plan = optimize(parts, std_sheet)

    assert plan.layouts[0].placed[0].rotated is False


def test_non_rotatable_placed_without_rotation(std_sheet):
    parts = [Rect(width=500, height=300, part_id="p1", rotatable=False)]
    plan = optimize(parts, std_sheet)
    assert not plan.unplaced


# ─── Retales disponibles ──────────────────────────────────────────────────────

def test_remnant_used_before_new_sheet(std_sheet):
    """Si hay un retal que contiene la pieza, debe usarse antes que un tablero nuevo."""
    remnants = [Remnant(width=600, height=500, thickness=18, label="retal_grande")]
    parts = _make_rects((500, 400, "p1"))

    plan = optimize(parts, std_sheet, available_remnants=remnants)

    assert len(plan.layouts) == 1
    assert plan.layouts[0].is_remnant is True


def test_remnant_wrong_thickness_ignored(std_sheet):
    """Retales con diferente espesor no deben usarse."""
    remnants = [Remnant(width=600, height=500, thickness=15, label="retal_15mm")]
    parts = _make_rects((500, 400, "p1"))

    plan = optimize(parts, std_sheet, available_remnants=remnants)

    # El retal de 15mm no sirve para tablero de 18mm → debe abrir tablero nuevo
    assert len(plan.layouts) == 1
    assert plan.layouts[0].is_remnant is False


def test_remnant_too_small_falls_back_to_sheet(std_sheet):
    """Si el retal es demasiado pequeño, debe abrirse un tablero nuevo."""
    remnants = [Remnant(width=200, height=100, thickness=18, label="retal_chico")]
    parts = _make_rects((500, 400, "p1"))

    plan = optimize(parts, std_sheet, available_remnants=remnants)

    # La pieza no cabe en el retal → debe ir a tablero nuevo
    assert any(not l.is_remnant for l in plan.layouts)
    assert plan.unplaced == []


def test_remnant_larger_used_first(std_sheet):
    """De varios retales disponibles, el más grande debe intentarse primero."""
    remnants = [
        Remnant(width=400, height=300, thickness=18, label="chico"),
        Remnant(width=1000, height=800, thickness=18, label="grande"),
    ]
    parts = _make_rects((900, 700, "p1"))
    plan = optimize(parts, std_sheet, available_remnants=remnants)

    # La pieza solo cabe en el retal grande
    used_layout = plan.layouts[0]
    assert used_layout.sheet.width == 1000
    assert used_layout.sheet.height == 800


# ─── Retales generados ────────────────────────────────────────────────────────

def test_remnants_generated_after_packing(std_sheet):
    """Debe haber retales útiles tras ubicar una pieza pequeña en un tablero grande."""
    parts = _make_rects((300, 200, "p1"))
    plan = optimize(parts, std_sheet)

    assert len(plan.remnants) > 0
    # Los retales deben estar ordenados por área desc
    areas = [r.area for r in plan.remnants]
    assert areas == sorted(areas, reverse=True)


def test_remnants_minimum_size(std_sheet):
    """Retales menores a 100×100mm no deben registrarse."""
    # Pieza que llena casi todo excepto una franja estrecha
    parts = _make_rects((2390, 1180, "p1"))
    plan = optimize(parts, std_sheet)

    for r in plan.remnants:
        assert r.width >= 100
        assert r.height >= 100


# ─── Piezas que no caben ──────────────────────────────────────────────────────

def test_part_larger_than_sheet_goes_unplaced(std_sheet):
    """Una pieza más grande que el tablero debe quedar en unplaced."""
    parts = _make_rects((3000, 1500, "gigante"))
    plan = optimize(parts, std_sheet)

    assert "gigante" in plan.unplaced


def test_valid_and_invalid_parts_mixed(std_sheet):
    """Piezas válidas deben colocarse aunque haya una inválida."""
    parts = _make_rects(
        (3000, 1500, "gigante"),
        (500, 400, "normal"),
    )
    plan = optimize(parts, std_sheet)

    assert "gigante" in plan.unplaced
    placed_ids = [p.part_id for l in plan.layouts for p in l.placed]
    assert "normal" in placed_ids


# ─── Estrategias de split ─────────────────────────────────────────────────────

def test_prefer_large_remnants_true_produces_larger_remnant(std_sheet):
    """prefer_large_remnants=True debe producir al menos un retal mayor."""
    parts = _make_rects((800, 600, "p1"))

    plan_large = optimize(parts, std_sheet, prefer_large_remnants=True)
    plan_short = optimize(parts, std_sheet, prefer_large_remnants=False)

    max_large = max((r.area for r in plan_large.remnants), default=0)
    max_short = max((r.area for r in plan_short.remnants), default=0)

    assert max_large >= max_short


def test_positions_non_overlapping(std_sheet):
    """Las piezas colocadas no deben solaparse entre sí."""
    parts = _make_rects(*[(400, 300, f"p{i}") for i in range(5)])
    plan = optimize(parts, std_sheet)

    for layout in plan.layouts:
        placed = layout.placed
        for i, a in enumerate(placed):
            for b in placed[i + 1:]:
                # Sin solapamiento si algún eje no se cruza
                no_overlap = (
                    a.x + a.width <= b.x or
                    b.x + b.width <= a.x or
                    a.y + a.height <= b.y or
                    b.y + b.height <= a.y
                )
                assert no_overlap, f"Solapamiento entre {a.part_id} y {b.part_id}"


def test_positions_within_sheet_bounds(std_sheet):
    """Ninguna pieza debe salirse de los límites del tablero."""
    parts = _make_rects(*[(600, 400, f"p{i}") for i in range(6)])
    plan = optimize(parts, std_sheet)

    for layout in plan.layouts:
        sw, sh = layout.sheet.width, layout.sheet.height
        for p in layout.placed:
            assert p.x >= 0
            assert p.y >= 0
            assert p.x + p.width <= sw + 1   # +1 por tolerancia kerf
            assert p.y + p.height <= sh + 1
