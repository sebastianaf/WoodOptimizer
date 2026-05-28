from __future__ import annotations
from dataclasses import dataclass
from .models import Sheet, Remnant, PlacedPart, SheetLayout, CutPlan

# ─── Constantes de estrategia (port de packing2d.rb) ───────────────────────

# Score: cómo elegir el espacio libre donde ubicar una pieza
SCORE_BESTAREA_FIT     = 0  # espacio libre más grande primero (como WORST-FIT clásico)
SCORE_BESTSHORTSIDE    = 1  # menor diferencia en el lado más corto
SCORE_BESTLONGSIDE     = 2  # menor diferencia en el lado más largo
SCORE_WORSTAREA_FIT    = 3  # espacio libre más ajustado (BEST-FIT clásico)

# Split: cómo partir el espacio restante tras ubicar la pieza (guillotina)
SPLIT_SHORTERLEFTOVER  = 0  # corte por el eje con menos sobrante → H-first si rw ≤ rh
SPLIT_LONGERLEFTOVER   = 1  # corte por el eje con más sobrante
SPLIT_MINIMIZE_AREA    = 2  # maximiza el producto length×width del sobrante menor
SPLIT_MAXIMIZE_AREA    = 3  # maximiza el sobrante más grande (= prefer_large_remnants)
SPLIT_SHORTER_AXIS     = 4  # H-first si pieza es más ancha que alta
SPLIT_LONGER_AXIS      = 5  # H-first si pieza es más alta que ancha

EPS = 0.001   # tolerancia numérica


# ─── Tipos internos ────────────────────────────────────────────────────────

@dataclass
class Rect:
    """Proyección 2D de una pieza para el algoritmo de empaque."""
    width: int
    height: int
    part_id: str
    rotatable: bool = True


@dataclass
class _FreeRect:
    x: int
    y: int
    width: int
    height: int

    @property
    def area(self) -> int:
        return self.width * self.height

    def fits(self, w: int, h: int) -> bool:
        return w <= self.width and h <= self.height


# ─── Split guillotina (port de leftover.rb) ───────────────────────────────

def _split_horizontal_first(
    fr: _FreeRect, pw: int, ph: int, kerf: int
) -> list[_FreeRect]:
    """
    Corte horizontal primero (como split_horizontal_first de OCL).
    Produce: franja inferior ancho-completo + franja derecha al alto de la pieza.
    """
    rw = fr.width - pw - kerf    # ancho restante
    rh = fr.height - ph - kerf   # alto restante

    result = []
    # Franja inferior: ancho completo del espacio libre, alto restante
    if rh > 0:
        result.append(_FreeRect(fr.x, fr.y + ph + kerf, fr.width, rh))
    # Franja derecha: ancho restante, al alto de la pieza
    if rw > 0:
        result.append(_FreeRect(fr.x + pw + kerf, fr.y, rw, ph))
    return result


def _split_vertical_first(
    fr: _FreeRect, pw: int, ph: int, kerf: int
) -> list[_FreeRect]:
    """
    Corte vertical primero (como split_vertical_first de OCL).
    Produce: franja derecha alto-completo + franja inferior al ancho de la pieza.
    """
    rw = fr.width - pw - kerf
    rh = fr.height - ph - kerf

    result = []
    # Franja derecha: ancho restante, alto completo del espacio libre
    if rw > 0:
        result.append(_FreeRect(fr.x + pw + kerf, fr.y, rw, fr.height))
    # Franja inferior: al ancho de la pieza, alto restante
    if rh > 0:
        result.append(_FreeRect(fr.x, fr.y + ph + kerf, pw, rh))
    return result


def _guillotine_split(
    fr: _FreeRect,
    pw: int,
    ph: int,
    kerf: int,
    split_strategy: int,
) -> list[_FreeRect]:
    """
    Decide H-first o V-first según la estrategia y delega.
    Port de leftover.rb#split_horizontally_first?
    """
    rw = fr.width - pw - kerf
    rh = fr.height - ph - kerf

    if split_strategy == SPLIT_SHORTERLEFTOVER:
        h_first = rw <= rh
    elif split_strategy == SPLIT_LONGERLEFTOVER:
        h_first = rw > rh
    elif split_strategy == SPLIT_MINIMIZE_AREA:
        # H-first cuando la franja inferior (fr.width × rh) ≤ franja derecha (fr.height × rw)
        h_first = fr.width * max(0, rh) <= fr.height * max(0, rw)
    elif split_strategy == SPLIT_MAXIMIZE_AREA:
        # Port exacto de OCL SPLIT_MAXIMIZE_AREA:
        # H-first cuando franja-inferior > franja-derecha en área
        h_first = fr.width * max(0, rh) > fr.height * max(0, rw)
    elif split_strategy == SPLIT_SHORTER_AXIS:
        h_first = pw < ph
    elif split_strategy == SPLIT_LONGER_AXIS:
        h_first = pw >= ph
    else:
        h_first = rw <= rh  # default: shorter leftover

    if h_first:
        return _split_horizontal_first(fr, pw, ph, kerf)
    return _split_vertical_first(fr, pw, ph, kerf)


# ─── Score (port de leftover.rb#heuristic_score) ─────────────────────────

def _score(fr: _FreeRect, pw: int, ph: int, score_strategy: int) -> float:
    """Puntaje para ubicar pieza (pw×ph) en espacio fr. Menor = mejor."""
    if score_strategy == SCORE_BESTAREA_FIT:
        # OCL: box_area - leftover_area → favorece espacios grandes (worst-fit clásico)
        return pw * ph - fr.area
    elif score_strategy == SCORE_WORSTAREA_FIT:
        # OCL: leftover_area - box_area → favorece ajuste más ceñido (best-fit clásico)
        return fr.area - pw * ph
    elif score_strategy == SCORE_BESTSHORTSIDE:
        return min(abs(pw - fr.width), abs(ph - fr.height))
    elif score_strategy == SCORE_BESTLONGSIDE:
        return max(abs(pw - fr.width), abs(ph - fr.height))
    return fr.area  # fallback


# ─── Función principal ─────────────────────────────────────────────────────

def optimize(
    parts: list[Rect],
    sheet: Sheet,
    available_remnants: list[Remnant] | None = None,
    prefer_large_remnants: bool = True,
) -> CutPlan:
    """
    Guillotine 2D bin packing con Best Fit Decreasing.

    Algoritmo portado de OpenCutList (lairdubois-opencutlist-sketchup-extension),
    específicamente de lib/bin_packing_2d/leftover.rb y packer.rb.

    Parámetros:
      parts               : piezas a empacar (proyección 2D)
      sheet               : tablero estándar (se abre uno nuevo cuando es necesario)
      available_remnants  : retales disponibles (se usan antes de abrir tableros nuevos)
      prefer_large_remnants: True → SPLIT_MAXIMIZE_AREA (OCL), favorece retales grandes
                             False → SPLIT_SHORTERLEFTOVER (OCL), heurística corta
    """
    if not parts:
        return CutPlan(layouts=[], remnants=[], efficiency=0.0)

    split_strategy = SPLIT_MAXIMIZE_AREA if prefer_large_remnants else SPLIT_SHORTERLEFTOVER
    score_strategy = SCORE_WORSTAREA_FIT   # ajuste más ceñido por defecto

    # BFD: piezas más grandes primero (OCL PRESORT_AREA_DECR)
    sorted_parts = sorted(parts, key=lambda r: r.width * r.height, reverse=True)

    layouts: list[SheetLayout] = []
    free_rects: list[list[_FreeRect]] = []

    def _add_sheet(s: Sheet, is_remnant: bool = False) -> int:
        idx = len(layouts)
        layouts.append(SheetLayout(sheet=s, is_remnant=is_remnant))
        free_rects.append([_FreeRect(0, 0, s.width, s.height)])
        return idx

    # Retales disponibles primero, ordenados de mayor a menor área (mismo espesor)
    if available_remnants:
        for rem in sorted(available_remnants, key=lambda r: r.area, reverse=True):
            if rem.thickness == sheet.thickness:
                _add_sheet(Sheet(
                    width=rem.width,
                    height=rem.height,
                    thickness=rem.thickness,
                    kerf=sheet.kerf,
                ), is_remnant=True)

    unplaced: list[str] = []

    for rect in sorted_parts:
        best_sheet_idx = -1
        best_fi = -1
        best_score = float("inf")
        best_pw = rect.width
        best_ph = rect.height

        for sheet_idx in range(len(layouts)):
            for fi, fr in enumerate(free_rects[sheet_idx]):
                # Orientación normal
                if fr.fits(rect.width, rect.height):
                    s = _score(fr, rect.width, rect.height, score_strategy)
                    if s < best_score:
                        best_score = s
                        best_sheet_idx = sheet_idx
                        best_fi = fi
                        best_pw, best_ph = rect.width, rect.height
                # Orientación rotada
                if rect.rotatable and fr.fits(rect.height, rect.width):
                    s = _score(fr, rect.height, rect.width, score_strategy)
                    if s < best_score:
                        best_score = s
                        best_sheet_idx = sheet_idx
                        best_fi = fi
                        best_pw, best_ph = rect.height, rect.width

        if best_fi >= 0:
            fr = free_rects[best_sheet_idx].pop(best_fi)
            free_rects[best_sheet_idx].extend(
                _guillotine_split(fr, best_pw, best_ph, sheet.kerf, split_strategy)
            )
            layouts[best_sheet_idx].placed.append(PlacedPart(
                part_id=rect.part_id,
                x=fr.x, y=fr.y,
                width=best_pw, height=best_ph,
                rotated=(best_pw != rect.width),
            ))
        else:
            # Abrir tablero nuevo
            new_idx = _add_sheet(sheet, is_remnant=False)
            fr = free_rects[new_idx][0]

            pw, ph = rect.width, rect.height
            if not fr.fits(pw, ph):
                if rect.rotatable and fr.fits(rect.height, rect.width):
                    pw, ph = rect.height, rect.width
                else:
                    # Pieza más grande que el tablero estándar
                    layouts.pop()
                    free_rects.pop()
                    unplaced.append(rect.part_id)
                    continue

            free_rects[new_idx].pop(0)
            free_rects[new_idx].extend(
                _guillotine_split(fr, pw, ph, sheet.kerf, split_strategy)
            )
            layouts[new_idx].placed.append(PlacedPart(
                part_id=rect.part_id,
                x=fr.x, y=fr.y,
                width=pw, height=ph,
                rotated=(pw != rect.width),
            ))

    # Retales generados: espacios libres ≥ 100×100 mm
    MIN_DIM = 100
    remnants: list[Remnant] = []
    for i, layout in enumerate(layouts):
        for fr in free_rects[i]:
            if fr.width >= MIN_DIM and fr.height >= MIN_DIM:
                remnants.append(Remnant(
                    width=fr.width,
                    height=fr.height,
                    thickness=layout.sheet.thickness,
                    label=f"retal_{len(remnants) + 1}",
                ))
    remnants.sort(key=lambda r: r.area, reverse=True)

    total_used = sum(l.used_area for l in layouts)
    total_area = sum(l.total_area for l in layouts)
    efficiency = total_used / total_area if total_area else 0.0

    return CutPlan(
        layouts=layouts,
        remnants=remnants,
        efficiency=efficiency,
        unplaced=unplaced,
    )
