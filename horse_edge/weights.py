"""Race-type re-weighting of the 13 factors ("adjust weighting when the race type
logically requires it"). Returns normalized weights (sum 1.0) plus notes.

Precedence: tight track and distance/field rules first; the going band is applied
LAST so a wet track has the final say on TRACK / BARRIER / SECT.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .models import BASE_WEIGHTS, FACTORS
from .tracks import condition_band, is_tight

RANGES = {
    "FORM": (10, 20), "CLASS": (6, 16), "DIST": (6, 14), "TRACK": (6, 25),
    "BARRIER": (3, 15), "POSITION": (6, 16), "SECT": (5, 16), "JOCKEY": (3, 8),
    "TRAINER": (3, 8), "FITNESS": (3, 12), "WEIGHT": (3, 9), "GEAR": (1, 7),
    "MARKET": (0, 8),
}


def adjust_weights(race: dict, n_runners: int) -> Tuple[Dict[str, float], List[str], dict]:
    w = dict(BASE_WEIGHTS)
    notes: List[str] = []
    mods = {"on_pace_position_bonus": 0.0}

    def setw(f: str, v: float, why: str) -> None:
        lo, hi = RANGES[f]
        w[f] = max(lo, min(hi, v))
        notes.append(f"{f} → {w[f]:.0f} ({why})")

    dist = race.get("distance") or 0
    field = race.get("field_size") or n_runners
    tight = is_tight(race.get("track"))
    cls = str(race.get("race_class") or "").lower()
    band, _ = condition_band(race.get("condition"))

    if tight:
        setw("BARRIER", 12, "tight/turning track")
        setw("POSITION", 14, "tight track — position decisive")
        mods["on_pace_position_bonus"] = 5.0
        notes.append("LEADER/ON-PACE +5 POSITION sub-score (tight track)")

    if dist and dist <= 1200:
        setw("BARRIER", 11 if not tight else w["BARRIER"], "sprint — gate speed critical")
        setw("POSITION", 13, "sprint — pace pressure decisive")
    elif dist >= 2000:
        setw("FITNESS", 9, "staying trip — fitness key")
        setw("SECT", 13, "staying trip — closing speed key")
        if not tight:
            setw("BARRIER", 4, "staying trip — barrier matters less")

    if field and field <= 8:
        setw("BARRIER", 3, "small field")
        setw("CLASS", 14, "small field — quality matters more")
    elif field and field >= 14:
        setw("BARRIER", 12 if not tight else w["BARRIER"], "big field — wide draws penalised")

    if "maiden" in cls or "mdn" in cls:
        setw("FORM", 11, "maiden — limited exposed form")
        setw("FITNESS", 8, "maiden — trials/fitness matter")
        setw("GEAR", 5, "maiden — gear changes more decisive")

    if band == "heavy":
        setw("TRACK", 22, "heavy track — wet form paramount")
        setw("SECT", 6, "heavy — dry sectionals unreliable")
        setw("BARRIER", 4, "heavy — barrier matters less")
    elif band == "soft":
        setw("TRACK", 15, "soft track — check wet form")
    elif band == "synthetic":
        setw("BARRIER", 4, "synthetic — minimal draw bias")
        setw("TRACK", 13, "synthetic — surface form matters")

    total = sum(w.values())
    return {f: w[f] / total for f in FACTORS}, notes, mods
