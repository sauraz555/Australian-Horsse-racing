"""Conditional weight adjustment engine.

Implements the base factor weights and every `IF ...` conditional rule from the
system prompt's <analysis_framework>. Produces one race-level weight vector,
normalized to sum to 1.0 (only relative weight matters once ratings become
probabilities).

Precedence note: weight adjustments are RACE-level. Track condition is the most
fundamental modifier, so the condition band (heavy/soft) is applied LAST and wins
for the factors it touches (SPD/SUIT/DRAW/BREED) — e.g. on a heavy day a wide
draw genuinely matters less, regardless of trip or field size. Per-horse factors
(first-up, individual gear changes) are better expressed in that runner's PREP /
GEAR sub-scores than in the shared weight vector; see skills.md.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Base weights (sum = 100) from <analysis_framework>.
BASE_WEIGHTS: Dict[str, float] = {
    "SPD": 22, "PACE": 17, "SECT": 15, "CLASS": 10, "SUIT": 10,
    "PREP": 8, "DRAW": 7, "JT": 5, "GEAR": 3, "BREED": 3,
}

# Documented allowable range per factor; adjustments clamp to these.
RANGES: Dict[str, Tuple[float, float]] = {
    "SPD": (18, 28), "PACE": (12, 22), "SECT": (10, 20), "CLASS": (8, 15),
    "SUIT": (5, 25), "PREP": (5, 15), "DRAW": (3, 20), "JT": (3, 10),
    "GEAR": (1, 8), "BREED": (0, 12),
}


def condition_band(condition) -> Tuple[str, int | None]:
    """Return (band, number) where band is firm/good/soft/heavy."""
    if not condition:
        return ("good", None)
    s = str(condition).lower()
    m = re.search(r"\d+", s)
    num = int(m.group()) if m else None
    if "heavy" in s or (num is not None and num >= 8):
        return ("heavy", num)
    if "soft" in s or (num is not None and 5 <= num <= 7):
        return ("soft", num)
    if "firm" in s or (num is not None and num <= 2):
        return ("firm", num)
    return ("good", num)


def adjust_weights(conditions: dict) -> Tuple[Dict[str, float], List[str], dict]:
    """Apply conditional rules to the base weights.

    conditions keys (all optional): condition, distance, field_size, track,
    tight (bool), race_class, first_starters (bool), first_up (bool),
    gear_change (bool).

    Returns (normalized_weights, notes, modifiers).
    modifiers["on_pace_pace_bonus"] is a flat additive applied to LEADER/ON-PACE
    PACE sub-scores at scoring time on tight tracks.
    """
    w = dict(BASE_WEIGHTS)
    notes: List[str] = []
    modifiers = {"on_pace_pace_bonus": 0.0}

    def setw(factor: str, value: float, why: str) -> None:
        lo, hi = RANGES[factor]
        w[factor] = max(lo, min(hi, value))
        notes.append(f"{factor} → {w[factor]:.0f} ({why})")

    band, _num = condition_band(conditions.get("condition"))
    dist = conditions.get("distance") or 0
    field_size = conditions.get("field_size") or 0
    tight = bool(conditions.get("tight"))
    race_class = (conditions.get("race_class") or "").lower()
    first_starters = bool(conditions.get("first_starters"))
    first_up = bool(conditions.get("first_up"))
    gear_change = bool(conditions.get("gear_change"))

    # 1) Tight / turning track
    if tight:
        setw("DRAW", 17, "tight/turning track")
        setw("PACE", 20, "tight track — pace decisive")
        modifiers["on_pace_pace_bonus"] = 5.0
        notes.append("On-pace/leader runners +5 PACE sub-score bonus (tight track)")

    # 2) Distance
    if dist >= 2000:
        setw("PREP", 13, "staying trip — fitness key")
        setw("SECT", 19, "staying trip — closing speed key")
        if not tight:
            setw("DRAW", 4, "staying trip — barrier matters less")
    elif dist and dist <= 1200:
        setw("PACE", 20, "sprint — pace pressure decisive")
        if not tight:
            setw("DRAW", 12, "sprint — gate speed critical")

    # 3) Field size
    if field_size and field_size <= 8:
        setw("DRAW", 3, "small field")
        setw("CLASS", 15, "small field — quality matters more")
    elif field_size and field_size >= 14:
        setw("DRAW", 14, "big field — wide draws penalized")

    # 4) Maiden / first-starters
    if "maiden" in race_class or first_starters:
        setw("BREED", 10, "maiden/first-starters — pedigree predictive")
        setw("SPD", 15, "limited speed data")

    # 5) Race-level first-up (only when the field broadly resumes, e.g. 2yo maiden)
    if first_up:
        setw("PREP", 13, "first-up field — fitness/trials key")

    # 6) Race-level significant gear-change context
    if gear_change:
        setw("GEAR", 6, "significant gear change context")

    # 7) Condition band LAST so heavy/soft override draw-related factors.
    if band == "heavy":
        setw("SUIT", 22, "heavy track — wet form paramount")
        setw("SPD", 15, "heavy — dry speed figures unreliable")
        setw("DRAW", 4, "heavy — barrier matters less")
        setw("BREED", 6, "heavy — sire wet stats predictive")
    elif band == "soft":
        setw("SUIT", 16, "soft track — check soft-ground form")

    total = sum(w.values())
    normalized = {k: v / total for k, v in w.items()}
    return normalized, notes, modifiers
