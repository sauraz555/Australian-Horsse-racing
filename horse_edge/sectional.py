"""Sectional benchmark comparison for last-600m closing times."""
from __future__ import annotations

import functools
import json
import os
from typing import Optional

_DATA = os.path.join(os.path.dirname(__file__), "data")


@functools.lru_cache(maxsize=1)
def load_benchmarks() -> dict:
    with open(os.path.join(_DATA, "sectional_benchmarks.json"), encoding="utf-8") as f:
        return json.load(f)


def band_for_distance(distance: Optional[int]) -> Optional[str]:
    if not distance:
        return None
    if distance <= 1200:
        return "sprint"
    if distance <= 1600:
        return "miler"
    return "stayer"


def assess_last600(last600: Optional[float], distance: Optional[int]) -> dict:
    """Compare a runner's closing 600m to par for the class/distance band."""
    band = band_for_distance(distance)
    if band is None or last600 is None:
        return {"band": band, "flag": None, "note": "insufficient sectional data"}
    ref = load_benchmarks()[band]
    fast, slow = ref["last600_fast"], ref["last600_slow"]
    if last600 <= fast:
        flag = "ELITE"
        note = f"last 600m {last600:.1f}s ≤ elite par {fast:.1f}s — upgrade / blackbook"
    elif last600 <= slow:
        flag = "PAR"
        note = f"last 600m {last600:.1f}s within par {fast:.1f}-{slow:.1f}s"
    else:
        flag = "BELOW"
        note = f"last 600m {last600:.1f}s slower than par {slow:.1f}s"
    return {"band": band, "label": ref.get("label"), "flag": flag, "note": note}
