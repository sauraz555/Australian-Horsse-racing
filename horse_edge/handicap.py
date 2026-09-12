"""Weights, apprentice claims and benchmark ratings.

Australian apprentice claims reduce the carried weight (typically 4kg, 3kg, 2kg or
1.5kg). Effective weight = declared weight − claim. Benchmark (BM) races handicap
off a rating: a runner rated above the race benchmark is "well in".
"""
from __future__ import annotations

from typing import Optional

from .classlevel import parse_class


def effective_weight(r: dict) -> Optional[float]:
    w = r.get("weight")
    if w is None:
        return None
    return round(float(w) - float(r.get("apprentice_claim") or 0), 1)


def analyse_handicap(race: dict, runners: list) -> dict:
    """Populate per-runner weight fields in place; return a race-level summary."""
    eff = []
    for r in runners:
        r["effective_weight"] = effective_weight(r)
        if r["effective_weight"] is not None:
            eff.append(r["effective_weight"])
    mean_w = round(sum(eff) / len(eff), 2) if eff else None
    top_w = max(eff) if eff else None

    bench = race.get("benchmark")
    for r in runners:
        notes = []
        ew = r.get("effective_weight")
        claim = float(r.get("apprentice_claim") or 0)
        if claim:
            notes.append(f"apprentice claim −{claim:g}kg → carries {ew}kg")
        if ew is not None and mean_w is not None:
            r["weight_vs_field"] = round(ew - mean_w, 2)      # + = carries more than average
            r["weight_vs_topweight"] = round(ew - top_w, 2) if top_w is not None else None
        last_w = r.get("weight_last_start")
        if last_w is not None and r.get("weight") is not None:
            delta = round(float(r["weight"]) - float(last_w), 1)
            r["weight_change"] = delta
            if delta > 0 and r.get("last_start_won"):
                notes.append(f"up {delta:g}kg for winning last start")
            elif delta < 0:
                notes.append(f"drops {abs(delta):g}kg from last start")
        if bench is not None and r.get("rating") is not None:
            diff = int(r["rating"]) - int(bench)
            r["rating_vs_benchmark"] = diff
            if diff >= 4:
                notes.append(f"rated {diff} above BM{bench} — well above the benchmark")
            elif diff <= -4:
                notes.append(f"rated {abs(diff)} below BM{bench} — near the minimum")
        lsc = r.get("last_start_class")
        if lsc and race.get("race_class"):
            a = parse_class(lsc)["rank"]
            b = parse_class(race["race_class"])["rank"]
            if a is not None and b is not None:
                if b > a + 5:
                    r["class_move"] = "UP"
                    notes.append(f"rises in class ({lsc} → {race['race_class']})")
                elif b < a - 5:
                    r["class_move"] = "DOWN"
                    notes.append(f"drops in class ({lsc} → {race['race_class']})")
                else:
                    r["class_move"] = "SAME"
        r["weight_notes"] = notes
    return {"mean_effective_weight": mean_w, "top_weight": top_w, "benchmark": bench}
