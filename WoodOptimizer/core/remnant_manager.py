"""
Gestión de retales: persistencia en JSON, puntuación por tamaño,
importación desde un plan de corte.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from .models import Remnant, CutPlan

_DEFAULT_PATH = Path.home() / ".woodoptimizer_remnants.json"
_MIN_DIM = 100  # mm — retales menores se descartan


def _score(r: Remnant) -> int:
    """Mayor área → mayor puntuación (para ordenar mejores primero)."""
    return r.width * r.height


class RemnantManager:
    """
    Centraliza el ciclo de vida de los retales.

    - Puntúa por área (los más grandes primero).
    - Descarta retales menores a _MIN_DIM en cualquier dimensión.
    - Persiste en JSON para sobrevivir entre sesiones de FreeCAD.
    """

    def __init__(self, path: str | Path | None = None):
        self._path = Path(path) if path else _DEFAULT_PATH
        self._remnants: list[Remnant] = []

    # ── Acceso ────────────────────────────────────────────────────────────────

    @property
    def remnants(self) -> list[Remnant]:
        return list(self._remnants)

    def sorted_by_score(self) -> list[Remnant]:
        return sorted(self._remnants, key=_score, reverse=True)

    # ── Mutación ──────────────────────────────────────────────────────────────

    def add(self, remnant: Remnant) -> bool:
        """Añade un retal si supera la dimensión mínima. Retorna True si fue añadido."""
        if remnant.width < _MIN_DIM or remnant.height < _MIN_DIM:
            return False
        self._remnants.append(remnant)
        return True

    def remove(self, index: int) -> Remnant | None:
        if 0 <= index < len(self._remnants):
            return self._remnants.pop(index)
        return None

    def remove_by_label(self, label: str) -> int:
        before = len(self._remnants)
        self._remnants = [r for r in self._remnants if r.label != label]
        return before - len(self._remnants)

    def clear(self):
        self._remnants.clear()

    # ── Importar desde plan ───────────────────────────────────────────────────

    def import_from_plan(self, plan: CutPlan, min_area: int = 0) -> int:
        """
        Importa los retales generados por un plan de corte.
        Filtra por área mínima y dimensión mínima.
        Retorna cantidad de retales importados.
        """
        added = 0
        for r in plan.remnants:
            if r.area >= min_area and r.width >= _MIN_DIM and r.height >= _MIN_DIM:
                self._remnants.append(r)
                added += 1
        return added

    # ── Persistencia ─────────────────────────────────────────────────────────

    def save(self, path: str | Path | None = None) -> Path:
        target = Path(path) if path else self._path
        data = [
            {"width": r.width, "height": r.height,
             "thickness": r.thickness, "label": r.label}
            for r in self._remnants
        ]
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return target

    def load(self, path: str | Path | None = None) -> int:
        """Carga retales desde JSON. Retorna cantidad cargada."""
        target = Path(path) if path else self._path
        if not target.exists():
            return 0
        try:
            data = json.loads(target.read_text())
            self._remnants = [
                Remnant(
                    width=int(item["width"]),
                    height=int(item["height"]),
                    thickness=int(item["thickness"]),
                    label=item.get("label", ""),
                )
                for item in data
                if int(item.get("width", 0)) >= _MIN_DIM
                and int(item.get("height", 0)) >= _MIN_DIM
            ]
            return len(self._remnants)
        except (json.JSONDecodeError, KeyError, ValueError):
            return 0

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> dict:
        if not self._remnants:
            return {"count": 0, "total_area_m2": 0.0, "best": None}
        best = max(self._remnants, key=_score)
        total_mm2 = sum(r.area for r in self._remnants)
        return {
            "count": len(self._remnants),
            "total_area_m2": round(total_mm2 / 1_000_000, 3),
            "best": {"width": best.width, "height": best.height,
                     "label": best.label},
        }
