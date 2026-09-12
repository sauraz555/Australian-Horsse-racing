"""Shared constants and small helpers for HorseEdgeEngine v2.

The agent writes `race.json` (see AGENTS.md for the schema); every module here
works on plain dicts loaded from that file, so the numerical core has zero
third-party dependencies.
"""
from __future__ import annotations

import re
from typing import Optional

# The 13 scoring factors from the master prompt, in report order.
FACTORS = ["FORM", "CLASS", "DIST", "TRACK", "BARRIER", "POSITION", "SECT",
           "JOCKEY", "TRAINER", "FITNESS", "WEIGHT", "GEAR", "MARKET"]

# Base weights (sum = 100).
BASE_WEIGHTS = {
    "FORM": 15, "CLASS": 10, "DIST": 10, "TRACK": 10, "BARRIER": 7,
    "POSITION": 10, "SECT": 10, "JOCKEY": 5, "TRAINER": 5, "FITNESS": 5,
    "WEIGHT": 5, "GEAR": 3, "MARKET": 5,
}

FACTOR_LABELS = {
    "FORM": "Recent form", "CLASS": "Class", "DIST": "Distance",
    "TRACK": "Track / going", "BARRIER": "Barrier", "POSITION": "Expected race position",
    "SECT": "Sectionals / speed", "JOCKEY": "Jockey", "TRAINER": "Trainer",
    "FITNESS": "Fitness / preparation", "WEIGHT": "Weight / handicap",
    "GEAR": "Gear / setup", "MARKET": "Market / value",
}

# Win probability is built from the INDEPENDENT factors only (rule: probabilities
# must not be anchored on bookmaker prices). MARKET still counts in the /100 score.
INDEPENDENT_FACTORS = [f for f in FACTORS if f != "MARKET"]

STYLES = ["LEADER", "ON-PACE", "MIDFIELD", "BACKMARKER"]
_ON_PACE = {"ON-PACE", "ON PACE", "ONPACE", "HANDY"}


def norm_style(style: Optional[str]) -> str:
    s = (style or "MIDFIELD").upper().strip()
    if s in _ON_PACE:
        return "ON-PACE"
    if s in ("LEADER", "LEAD", "FRONT"):
        return "LEADER"
    if s in ("BACKMARKER", "BACK", "REAR", "CLOSER"):
        return "BACKMARKER"
    return "MIDFIELD"


def to_int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"-?\d+", str(v))
    return int(m.group()) if m else None


def to_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v))
    return float(m.group()) if m else None


def label(r: dict) -> str:
    return f"{r.get('name') or ''} (#{r.get('number')})"
