"""Combine adjusted weights with agent-supplied factor sub-scores into total
ratings and tissue (model) probabilities.
"""
from __future__ import annotations

from typing import Optional

from .models import FACTORS

_ON_PACE_STYLES = {"LEADER", "ON-PACE", "ON PACE", "ONPACE"}


def total_rating(factor_scores: Optional[dict], weights: dict,
                 pace_bonus: float = 0.0, running_style: Optional[str] = None) -> float:
    """weighted sum of 0-100 sub-scores; weights are normalized (sum ~1.0)."""
    scores = dict(factor_scores or {})
    if pace_bonus and (running_style or "").upper().strip() in _ON_PACE_STYLES:
        scores["PACE"] = min(100.0, float(scores.get("PACE", 0) or 0) + pace_bonus)
    total = 0.0
    for f in FACTORS:
        total += weights.get(f, 0.0) * float(scores.get(f, 0) or 0)
    return total


DEFAULT_SPREAD = 7.0  # calibrated; turns a compressed rating field into realistic tissues


def score_runners(runners: list, weights: dict, pace_bonus: float = 0.0,
                  spread: float = DEFAULT_SPREAD) -> list:
    """Populate total_rating and tissue_prob on each runner dict in place.

    tissue_prob = rating**spread / Σ rating**spread.
      spread = 1.0 -> the spec's literal linear formula (rating / Σ rating).
      spread > 1.0 -> sharpens the field so genuine favourites get realistic
                      probabilities instead of the ~1/N compression linear gives.
    Scale-invariant: only the ratios between ratings matter, so tissue stays
    independent of the market.
    """
    totals = []
    for r in runners:
        t = total_rating(r.get("factor_scores"), weights, pace_bonus, r.get("running_style"))
        r["total_rating"] = round(t, 3)
        totals.append(t)
    powered = [t ** spread if t > 0 else 0.0 for t in totals]
    s = sum(powered)
    for r, p in zip(runners, powered):
        r["tissue_prob"] = round(p / s, 5) if s > 0 else None
    return runners
