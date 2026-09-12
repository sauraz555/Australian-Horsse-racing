"""Map-based speed profiling.

From each runner's running style, early-speed rating (1-10) and barrier, predict
the first-600m running order, the Pace Pressure Index, the overall tempo, barrier
outcomes (caught wide / forced back / boxed in) and the three tempo scenarios
with their beneficiaries and probabilities.
"""
from __future__ import annotations

from .models import norm_style, label
from .tracks import track_info


def _early_speed(r: dict) -> float:
    es = r.get("early_speed")
    if es is not None:
        return float(es)
    return {"LEADER": 8.5, "ON-PACE": 6.5, "MIDFIELD": 4.5, "BACKMARKER": 2.5}[norm_style(r.get("running_style"))]


def predicted_order(runners: list) -> list:
    """First-600m order: early speed desc, inside barrier breaks ties."""
    ranked = sorted(runners, key=lambda r: (-_early_speed(r), r.get("barrier") or 99))
    return [{"number": r.get("number"), "name": r.get("name"),
             "early_speed": _early_speed(r), "barrier": r.get("barrier"),
             "style": norm_style(r.get("running_style"))} for r in ranked]


def pace_pressure_index(runners: list) -> int:
    return sum(1 for r in runners
               if norm_style(r.get("running_style")) in ("LEADER", "ON-PACE")
               and isinstance(r.get("barrier"), int) and 1 <= r["barrier"] <= 6)


def tempo(runners: list) -> dict:
    fast = [r for r in runners if _early_speed(r) >= 7.0]
    n = len(fast)
    ppi = pace_pressure_index(runners)
    if n == 0:
        t, p = "SLOW", (0.65, 0.28, 0.07)
    elif n == 1:
        t, p = "BELOW AVERAGE", (0.55, 0.35, 0.10)
    elif n == 2:
        t, p = "AVERAGE", (0.30, 0.50, 0.20)
    elif n == 3:
        t, p = "ABOVE AVERAGE", (0.15, 0.50, 0.35)
    else:
        t, p = "FAST" if n == 4 else "VERY FAST", (0.08, 0.35, 0.57)
    if ppi >= 4 and n < 4:
        t = "ABOVE AVERAGE" if n <= 2 else "FAST"
        p = (max(0.05, p[0] - 0.1), p[1], min(0.6, p[2] + 0.1))
    return {"tempo": t, "n_fast": n, "ppi": ppi,
            "scenario_probs": {"A_slow": round(p[0], 2), "B_genuine": round(p[1], 2),
                               "C_collapse": round(p[2], 2)}}


def barrier_outcomes(runners: list) -> None:
    field = len(runners)
    for r in runners:
        b = r.get("barrier")
        es = _early_speed(r)
        out = "neutral"
        if isinstance(b, int):
            wide = b >= max(field - 2, 7)
            inside = b <= 3
            if wide and es >= 7:
                out = "forced forward / risk of being caught wide"
            elif wide and es <= 4:
                out = "forced back from wide gate — needs luck"
            elif wide:
                out = "must find cover — three-wide risk"
            elif inside and es <= 3:
                out = "inside but slow away — boxed-in risk"
            elif inside and es >= 7:
                out = "gets the rail / economical run"
            elif inside:
                out = "gets cover / economical"
        r["barrier_outcome"] = out


def race_shape(order: list) -> str:
    if not order:
        return "no runners"
    top = order[0]
    if len(order) > 1 and order[1]["early_speed"] >= top["early_speed"] - 0.5:
        contest = [o for o in order if o["early_speed"] >= top["early_speed"] - 0.5]
        names = ", ".join(f"{o['name']} (#{o['number']})" for o in contest[:3])
        return f"Contested lead — {names} likely to fight for the front; speed battle risk."
    if top["early_speed"] < 6:
        return "No genuine leader — tactical race; whoever takes it up may get a soft lead."
    return f"{top['name']} (#{top['number']}) should lead uncontested and control the tempo."


def scenarios(runners: list, tem: dict) -> dict:
    def by_sect(rs):
        return sorted(rs, key=lambda r: -float((r.get("scores") or {}).get("SECT") or 0))
    lead = [r for r in runners if norm_style(r.get("running_style")) == "LEADER"]
    onp = [r for r in runners if norm_style(r.get("running_style")) == "ON-PACE"]
    mid = [r for r in runners if norm_style(r.get("running_style")) == "MIDFIELD"]
    back = [r for r in runners if norm_style(r.get("running_style")) == "BACKMARKER"]
    return {
        "A_slow": {"prob": tem["scenario_probs"]["A_slow"],
                   "benefits": [label(r) for r in (lead + onp)[:4]],
                   "note": "Leaders and on-pace runners get a breather and kick; closers left flat-footed."},
        "B_genuine": {"prob": tem["scenario_probs"]["B_genuine"],
                      "benefits": [label(r) for r in by_sect(onp + mid)[:4]],
                      "note": "Even tempo — horses with cover in the first half and strong sectionals win."},
        "C_collapse": {"prob": tem["scenario_probs"]["C_collapse"],
                       "benefits": [label(r) for r in by_sect(mid + back)[:4]],
                       "note": "Speed battle collapses the leaders — best closing sectionals swoop late."},
    }


def build_speedmap(runners: list, track: str | None = None) -> dict:
    order = predicted_order(runners)
    tem = tempo(runners)
    barrier_outcomes(runners)
    groups = {"LEADER": [], "ON-PACE": [], "MIDFIELD": [], "BACKMARKER": []}
    for r in runners:
        groups[norm_style(r.get("running_style"))].append(label(r))
    likely = max(tem["scenario_probs"], key=tem["scenario_probs"].get)
    return {
        "groups": groups,
        "predicted_first_600m": order,
        "shape": race_shape(order),
        "tempo": tem["tempo"],
        "n_fast_beginners": tem["n_fast"],
        "ppi": tem["ppi"],
        "scenarios": scenarios(runners, tem),
        "most_likely_scenario": likely,
        "track": track_info(track),
    }
