from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Part:
    """Pieza de madera con sus tres dimensiones reales."""
    id: str
    label: str
    length: int    # mm — eje X
    width: int     # mm — eje Y
    thickness: int  # mm — eje Z
    material: str = "melamina_blanco"


@dataclass
class Sheet:
    """Tablero completo disponible para cortar."""
    width: int = 2440   # mm
    height: int = 1220  # mm
    thickness: int = 18
    kerf: int = 3       # ancho de sierra mm


@dataclass
class Remnant:
    """Retal de tablero disponible para reusar."""
    width: int
    height: int
    thickness: int
    label: str = ""

    @property
    def area(self) -> int:
        return self.width * self.height


@dataclass
class PlacedPart:
    """Pieza ubicada en un tablero con su posición y orientación."""
    part_id: str
    x: int
    y: int
    width: int
    height: int
    rotated: bool = False


@dataclass
class SheetLayout:
    """Un tablero con todas sus piezas ubicadas."""
    sheet: Sheet
    placed: list[PlacedPart] = field(default_factory=list)
    is_remnant: bool = False

    @property
    def used_area(self) -> int:
        return sum(p.width * p.height for p in self.placed)

    @property
    def total_area(self) -> int:
        return self.sheet.width * self.sheet.height

    @property
    def efficiency(self) -> float:
        return self.used_area / self.total_area if self.total_area else 0.0


@dataclass
class CutPlan:
    """Resultado completo de la optimización de corte."""
    layouts: list[SheetLayout]
    remnants: list[Remnant]   # ordenados por área desc
    efficiency: float
    unplaced: list[str] = field(default_factory=list)  # part_ids que no caben
