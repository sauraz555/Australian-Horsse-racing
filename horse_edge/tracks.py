"""Australian track reference: layout, straight length, historical bias."""
from __future__ import annotations

import functools
import json
import os
import re
from typing import Optional, Tuple

_DATA = os.path.join(os.path.dirname(__file__), "data")


@functools.lru_cache(maxsize=1)
def load_tracks() -> dict:
    with open(os.path.join(_DATA, "track_bias.json"), encoding="utf-8") as f:
        return json.load(f)


def track_info(track: Optional[str]) -> Optional[dict]:
    if not track:
        return None
    key = track.strip().lower()
    tb = load_tracks()
    for k, v in tb.items():
        if k.lower() == key:
            return {"track": k, **v}
    for k, v in tb.items():            # "Royal Randwick" -> "Randwick"
        if k.lower() in key:
            return {"track": k, **v}
    return None


def is_tight(track: Optional[str]) -> bool:
    info = track_info(track)
    return bool(info and info.get("tight"))


def condition_band(condition) -> Tuple[str, Optional[int]]:
    """('firm'|'good'|'soft'|'heavy'|'synthetic', number)."""
    if not condition:
        return ("good", None)
    s = str(condition).lower()
    m = re.search(r"\d+", s)
    num = int(m.group()) if m else None
    if "synth" in s or "poly" in s:
        return ("synthetic", num)
    if "heavy" in s or (num is not None and num >= 8):
        return ("heavy", num)
    if "soft" in s or (num is not None and 5 <= num <= 7):
        return ("soft", num)
    if "firm" in s or (num is not None and num <= 2):
        return ("firm", num)
    return ("good", num)
