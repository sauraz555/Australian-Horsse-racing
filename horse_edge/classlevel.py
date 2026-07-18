"""Australian race-class / grade recognition.

Turns a free-text class string ("BM88", "Group 2", "Class 3 Maiden", "Listed")
into a rank and a low / mid / high grade band, so the analysis weights class
appropriately and the report frames the race correctly. Grade is a first-class
consideration, not an afterthought — a low-grade maiden is far more volatile than
a Group race and rewards improvement/breeding angles, while high-grade races are
won on genuine class.
"""
from __future__ import annotations

import re

# (regex, rank, canonical). Higher rank = higher class. Highest-ranked match wins.
_LEVELS = [
    (r"group\s*1|\bg\.?1\b|grade\s*1",              95, "Group 1"),
    (r"group\s*2|\bg\.?2\b|grade\s*2",              88, "Group 2"),
    (r"group\s*3|\bg\.?3\b|grade\s*3",              80, "Group 3"),
    (r"listed|\blr\b",                              72, "Listed"),
    (r"\bwfa\b|weight[- ]for[- ]age",               68, "WFA"),
    (r"\bopen\b",                                   66, "Open"),
    (r"bm\s*9\d|benchmark\s*9\d",                   65, "BM90+"),
    (r"bm\s*8[4-9]|benchmark\s*8[4-9]",             58, "BM84-89"),
    (r"class\s*6|\bcl\s*6\b",                       50, "Class 6"),
    (r"bm\s*7[8-9]|benchmark\s*7[8-9]",             50, "BM78-79"),
    (r"bm\s*7[0-7]|benchmark\s*7[0-7]",             40, "BM70-77"),
    (r"class\s*5|\bcl\s*5\b",                       42, "Class 5"),
    (r"class\s*4|\bcl\s*4\b",                       36, "Class 4"),
    (r"bm\s*6\d|benchmark\s*6\d",                   30, "BM60-69"),
    (r"class\s*3|\bcl\s*3\b",                       26, "Class 3"),
    (r"bm\s*5\d|benchmark\s*5\d",                   24, "BM50-59"),
    (r"class\s*2|\bcl\s*2\b",                       22, "Class 2"),
    (r"class\s*1|\bcl\s*1\b",                       18, "Class 1"),
    (r"maiden|\bmdn\b|\bmsw\b|\bmdn-sw\b",          10, "Maiden"),
]

_BAND_NOTES = {
    "low": ("Low-grade race — form is more volatile and class edges are small. "
            "Improvement, breeding and gear/first-up angles carry more weight; "
            "place/exotic value can hide here."),
    "mid": ("Mid-grade race — proven class record matters. Favour horses that have "
            "already handled this grade over unexposed types stepping up."),
    "high": ("High-grade race — class is paramount. Only genuine class contenders "
             "win; discount horses raising sharply in grade."),
    "unknown": ("Grade not identified — assess class from each runner's form and "
                "the prize money, and state the uncertainty."),
}


def _band(rank: int) -> str:
    if rank is None:
        return "unknown"
    if rank < 35:      # maiden, Class 1-3, BM50-69
        return "low"
    if rank < 55:      # Class 4-6, BM70-79
        return "mid"
    return "high"      # BM84+, Open/WFA, Listed, Group


def parse_class(text) -> dict:
    if not text:
        return {"matched": None, "rank": None, "band": "unknown", "note": _BAND_NOTES["unknown"]}
    s = str(text).lower()
    best = None
    for pat, rank, canon in _LEVELS:
        if re.search(pat, s) and (best is None or rank > best[1]):
            best = (canon, rank)
    if best is None:
        return {"matched": None, "rank": None, "band": "unknown", "note": _BAND_NOTES["unknown"]}
    canon, rank = best
    band = _band(rank)
    return {"matched": canon, "rank": rank, "band": band, "note": _BAND_NOTES[band]}
