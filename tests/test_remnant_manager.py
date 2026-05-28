"""Tests del RemnantManager."""
import json
import pytest

from WoodOptimizer.core.models import Remnant, CutPlan, SheetLayout, Sheet, PlacedPart
from WoodOptimizer.core.remnant_manager import RemnantManager, _MIN_DIM


@pytest.fixture
def mgr(tmp_path):
    return RemnantManager(path=tmp_path / "retales.json")


def _remnant(w=600, h=400, t=18, label="r1"):
    return Remnant(width=w, height=h, thickness=t, label=label)


def _plan_with_remnants(remnants: list[Remnant]) -> CutPlan:
    sheet = Sheet(width=2440, height=1220, thickness=18, kerf=3)
    layout = SheetLayout(sheet=sheet, placed=[], is_remnant=False)
    return CutPlan(layouts=[layout], remnants=remnants, efficiency=0.7, unplaced=[])


# ── add ────────────────────────────────────────────────────────────────────────

def test_add_valid_remnant(mgr):
    assert mgr.add(_remnant()) is True
    assert len(mgr.remnants) == 1


def test_add_too_small_width_rejected(mgr):
    assert mgr.add(Remnant(width=_MIN_DIM - 1, height=400, thickness=18)) is False
    assert len(mgr.remnants) == 0


def test_add_too_small_height_rejected(mgr):
    assert mgr.add(Remnant(width=600, height=_MIN_DIM - 1, thickness=18)) is False
    assert len(mgr.remnants) == 0


def test_add_exact_min_dim_accepted(mgr):
    assert mgr.add(Remnant(width=_MIN_DIM, height=_MIN_DIM, thickness=18)) is True


# ── remove ─────────────────────────────────────────────────────────────────────

def test_remove_by_index(mgr):
    mgr.add(_remnant(label="a"))
    mgr.add(_remnant(label="b"))
    removed = mgr.remove(0)
    assert removed is not None
    assert len(mgr.remnants) == 1


def test_remove_out_of_range_returns_none(mgr):
    assert mgr.remove(99) is None


def test_remove_by_label(mgr):
    mgr.add(_remnant(label="target"))
    mgr.add(_remnant(label="keep"))
    count = mgr.remove_by_label("target")
    assert count == 1
    assert all(r.label != "target" for r in mgr.remnants)


def test_clear(mgr):
    mgr.add(_remnant())
    mgr.add(_remnant(label="r2"))
    mgr.clear()
    assert len(mgr.remnants) == 0


# ── sorted_by_score ────────────────────────────────────────────────────────────

def test_sorted_by_score_largest_first(mgr):
    mgr.add(Remnant(width=300, height=300, thickness=18, label="small"))
    mgr.add(Remnant(width=1200, height=800, thickness=18, label="large"))
    mgr.add(Remnant(width=600, height=400, thickness=18, label="medium"))
    ranked = mgr.sorted_by_score()
    assert ranked[0].label == "large"
    assert ranked[-1].label == "small"


# ── import_from_plan ───────────────────────────────────────────────────────────

def test_import_from_plan_adds_remnants(mgr):
    plan = _plan_with_remnants([
        _remnant(600, 400, label="p1"),
        _remnant(800, 500, label="p2"),
    ])
    added = mgr.import_from_plan(plan)
    assert added == 2
    assert len(mgr.remnants) == 2


def test_import_from_plan_skips_small(mgr):
    plan = _plan_with_remnants([
        _remnant(600, 400, label="ok"),
        Remnant(width=50, height=50, thickness=18, label="tiny"),
    ])
    added = mgr.import_from_plan(plan)
    assert added == 1


def test_import_from_plan_respects_min_area(mgr):
    plan = _plan_with_remnants([
        _remnant(600, 400, label="medium"),   # 240 000 mm²
        _remnant(1200, 800, label="large"),   # 960 000 mm²
    ])
    added = mgr.import_from_plan(plan, min_area=500_000)
    assert added == 1
    assert mgr.remnants[0].label == "large"


# ── save / load ────────────────────────────────────────────────────────────────

def test_save_and_load_round_trip(mgr):
    mgr.add(_remnant(600, 400, label="guardado"))
    path = mgr.save()
    data = json.loads(path.read_text())
    assert len(data) == 1
    assert data[0]["label"] == "guardado"

    mgr2 = RemnantManager(path=path)
    loaded = mgr2.load()
    assert loaded == 1
    assert mgr2.remnants[0].width == 600


def test_load_nonexistent_file_returns_zero(tmp_path):
    mgr = RemnantManager(path=tmp_path / "no_existe.json")
    assert mgr.load() == 0
    assert len(mgr.remnants) == 0


def test_load_malformed_json_returns_zero(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json }")
    mgr = RemnantManager(path=bad)
    assert mgr.load() == 0


def test_load_skips_small_from_file(tmp_path):
    path = tmp_path / "small.json"
    path.write_text(json.dumps([
        {"width": 50, "height": 50, "thickness": 18, "label": "tiny"},
        {"width": 600, "height": 400, "thickness": 18, "label": "ok"},
    ]))
    mgr = RemnantManager(path=path)
    mgr.load()
    assert len(mgr.remnants) == 1
    assert mgr.remnants[0].label == "ok"


# ── stats ──────────────────────────────────────────────────────────────────────

def test_stats_empty(mgr):
    s = mgr.stats()
    assert s["count"] == 0
    assert s["total_area_m2"] == 0.0
    assert s["best"] is None


def test_stats_with_remnants(mgr):
    mgr.add(Remnant(width=1000, height=1000, thickness=18, label="cuadrado"))
    mgr.add(Remnant(width=500, height=300, thickness=18, label="chico"))
    s = mgr.stats()
    assert s["count"] == 2
    assert abs(s["total_area_m2"] - 1.15) < 0.01
    assert s["best"]["label"] == "cuadrado"
