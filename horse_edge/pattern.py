"""Track-pattern detection from earlier races on today's card.

Historical bias (from data/track_bias.json) and TODAY's observed bias are kept
separate, as the master prompt requires. Each earlier race the agent records:
  {"race_no": 1, "distance": 1200, "winner_settled": "led|on-pace|midfield|back",
   "winner_barrier": 3, "winner_ran": "rail|midtrack|wide", "margin": 1.5,
   "placegetters_settled": ["on-pace", "midfield"], "notes": "..."}
"""
from __future__ import annotations

from .tracks import track_info

_SETTLE = {"led": "LEADER", "lead": "LEADER", "leader": "LEADER", "on-pace": "ON-PACE",
           "on pace": "ON-PACE", "onpace": "ON-PACE", "handy": "ON-PACE",
           "midfield": "MIDFIELD", "mid": "MIDFIELD", "back": "BACKMARKER",
           "backmarker": "BACKMARKER", "rear": "BACKMARKER", "last": "BACKMARKER"}


def detect_pattern(earlier: list, track: str | None, field_size: int | None = None) -> dict:
    hist = track_info(track)
    if not earlier:
        return {"races_observed": 0, "observed_bias": "NO LIVE EVIDENCE",
                "strength": "none", "historical_bias": (hist or {}).get("bias"),
                "historical_note": (hist or {}).get("rail_note"),
                "note": "No earlier races recorded — rely on historical bias only, and re-check "
                        "after early races have been run."}

    settle = {"LEADER": 0, "ON-PACE": 0, "MIDFIELD": 0, "BACKMARKER": 0}
    lane = {"rail": 0, "midtrack": 0, "wide": 0}
    inside = mid = wide_b = 0
    n = 0
    for e in earlier:
        n += 1
        s = _SETTLE.get(str(e.get("winner_settled") or "").lower().strip())
        if s:
            settle[s] += 1
        ln = str(e.get("winner_ran") or "").lower()
        if "rail" in ln or "fence" in ln or "inside" in ln:
            lane["rail"] += 1
        elif "wide" in ln or "out" in ln:
            lane["wide"] += 1
        elif ln:
            lane["midtrack"] += 1
        b = e.get("winner_barrier")
        if isinstance(b, int):
            fs = e.get("field_size") or field_size or 12
            if b <= 4:
                inside += 1
            elif b >= max(fs - 3, 8):
                wide_b += 1
            else:
                mid += 1

    front = settle["LEADER"] + settle["ON-PACE"]
    backs = settle["BACKMARKER"] + settle["MIDFIELD"]
    parts = []
    strength = "weak"
    if n >= 2 and front / n >= 0.75:
        parts.append("LEADER / ON-PACE bias observed")
        strength = "strong" if n >= 3 else "moderate"
    elif n >= 2 and settle["BACKMARKER"] / n >= 0.5:
        parts.append("BACKMARKER / run-on pattern observed")
        strength = "strong" if n >= 3 else "moderate"
    elif n >= 2 and backs / n >= 0.75:
        parts.append("closers getting home — no front-running edge")
        strength = "moderate"
    if n >= 2 and lane["rail"] / n >= 0.75:
        parts.append("winners hugging the rail (inside lane live)")
    elif n >= 2 and lane["wide"] / n >= 0.5:
        parts.append("winners coming wide — rail may be off")
    if n >= 2 and inside / n >= 0.75:
        parts.append("inside barriers dominating")
    elif n >= 2 and wide_b / n >= 0.5:
        parts.append("wide barriers winning — draw not a negative today")
    if not parts:
        parts.append("no clear pattern yet")
        strength = "none" if n < 2 else "weak"

    hb = (hist or {}).get("bias")
    agree = None
    if hb and n >= 2:
        if ("LEADER" in parts[0] or "ON-PACE" in parts[0]) and hb in ("leader", "on-pace"):
            agree = "today's pattern CONFIRMS the historical bias"
        elif "BACKMARKER" in parts[0] and hb in ("leader", "on-pace"):
            agree = "today's pattern CONTRADICTS the historical bias — trust today"
        elif "no clear" in parts[0]:
            agree = "no live confirmation of the historical bias yet"
    return {
        "races_observed": n,
        "winner_settling": settle,
        "winner_lane": lane,
        "winner_barriers": {"inside": inside, "mid": mid, "wide": wide_b},
        "observed_bias": "; ".join(parts),
        "strength": strength,
        "historical_bias": hb,
        "historical_note": (hist or {}).get("rail_note"),
        "agreement": agree,
    }
