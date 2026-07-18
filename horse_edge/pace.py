"""Pace map construction: running-style grouping, Pace Pressure Index (PPI),
race shape, and track-bias lookup.
"""
from __future__ import annotations

import functools
import json
import os
from typing import Optional

_DATA = os.path.join(os.path.dirname(__file__), "data")

_ON_PACE = {"ON-PACE", "ON PACE", "ONPACE"}


@functools.lru_cache(maxsize=1)
def load_track_bias() -> dict:
    with open(os.path.join(_DATA, "track_bias.json"), encoding="utf-8") as f:
        return json.load(f)


def _norm_style(style: Optional[str]) -> str:
    s = (style or "MIDFIELD").upper().strip()
    if s in _ON_PACE:
        return "ON-PACE"
    if s in ("LEADER", "MIDFIELD", "BACKMARKER"):
        return s
    return "MIDFIELD"


def track_bias(track: Optional[str]) -> Optional[dict]:
    if not track:
        return None
    tb = load_track_bias()
    key = track.strip().lower()
    for k, v in tb.items():
        if k.lower() == key:
            return {"track": k, **v}
    for k, v in tb.items():          # partial match ("Royal Randwick" -> "Randwick")
        if k.lower() in key:
            return {"track": k, **v}
    return None


def is_tight(track: Optional[str]) -> bool:
    b = track_bias(track)
    return bool(b and b.get("tight"))


def pace_pressure_index(runners: list) -> dict:
    """Count LEADER/ON-PACE runners drawn inside (barriers 1-6)."""
    count = 0
    n_leaders = 0
    n_onpace = 0
    for r in runners:
        style = _norm_style(r.get("running_style"))
        bar = r.get("barrier")
        if style == "LEADER":
            n_leaders += 1
        elif style == "ON-PACE":
            n_onpace += 1
        if style in ("LEADER", "ON-PACE") and isinstance(bar, int) and 1 <= bar <= 6:
            count += 1
    if count <= 1:
        tempo, favours = "SLOW", "LEADERS and ON-PACE runners"
    elif count <= 3:
        tempo, favours = "MODERATE", "reasonably predictable — balanced"
    else:
        tempo, favours = "GENUINE/HOT", "MIDFIELD and BACKMARKERS"
    return {
        "ppi": count,
        "tempo": tempo,
        "favours": favours,
        "n_leaders": n_leaders,
        "n_onpace": n_onpace,
    }


def race_shape(runners: list) -> str:
    leaders = [r for r in runners if _norm_style(r.get("running_style")) == "LEADER"]
    n = len(leaders)
    if n == 0:
        return "No genuine leader — tactical race; box-seat horse advantaged."
    if n == 1:
        nm = leaders[0].get("name") or f"#{leaders[0].get('number')}"
        return f"Single leader ({nm}) controls tempo — likely on-pace result."
    inside = [r for r in leaders if isinstance(r.get("barrier"), int) and r["barrier"] <= 6]
    if len(inside) >= 2:
        return "Multiple leaders drawn inside — fast early tempo, likely run-on race."
    return "Multiple leaders — contested lead, moderate-to-genuine tempo."


def build_pace_map(runners: list, track: Optional[str] = None) -> dict:
    groups = {"LEADER": [], "ON-PACE": [], "MIDFIELD": [], "BACKMARKER": []}
    for r in runners:
        label = r.get("name") or f"#{r.get('number')}"
        groups[_norm_style(r.get("running_style"))].append(label)
    return {
        "groups": groups,
        "ppi": pace_pressure_index(runners),
        "shape": race_shape(runners),
        "track_bias": track_bias(track),
    }
