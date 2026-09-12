"""The numerical model: 13-factor score → independent win probability → fair odds,
plus the Confidence (1-10) and Value (1-10) ratings, the BET / SMALL BET / WAIT /
PASS decision, the final shortlist, automatic trap/flag detection and the
mandatory data-quality audit. `analyse()` orchestrates everything.
"""
from __future__ import annotations

import re
from typing import Optional

from .models import FACTORS, INDEPENDENT_FACTORS, norm_style, label
from .weights import adjust_weights
from .classlevel import parse_class
from .handicap import analyse_handicap
from .speedmap import build_speedmap
from .pattern import detect_pattern
from .sectional import assess_last600
from .market import evaluate_market, MIN_EV
from .exotics import build_exotics
from .tracks import condition_band

DEFAULT_SPREAD = 7.0   # rating -> probability sharpness; 1.0 = linear
NEUTRAL = 50.0         # a missing factor score counts as "average" and is flagged

RACE_KEYS = ["track", "date", "race_no", "distance", "race_class", "condition",
             "rail", "field_size", "weather", "prize"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse_record(s) -> Optional[tuple]:
    """'3:1-1-0' -> (starts, wins, seconds, thirds)."""
    if not s:
        return None
    m = re.match(r"\s*(\d+)\s*:\s*(\d+)\s*-\s*(\d+)\s*-\s*(\d+)", str(s))
    return tuple(int(x) for x in m.groups()) if m else None


def _wet_proven(r: dict) -> bool:
    rec = r.get("record") or {}
    for k in ("soft", "heavy"):
        p = _parse_record(rec.get(k))
        if p and (p[1] > 0 or p[2] > 0):
            return True
    return False


def _dedupe(xs):
    seen, out = set(), []
    for x in xs:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ---------------------------------------------------------------------------
# scoring & probability
# ---------------------------------------------------------------------------

def score_runners(runners: list, weights: dict, mods: dict, spread: float) -> None:
    ind_total = sum(weights[f] for f in INDEPENDENT_FACTORS)
    ratings = []
    for r in runners:
        sc = dict(r.get("scores") or {})
        bonus = mods.get("on_pace_position_bonus", 0.0)
        if bonus and norm_style(r.get("running_style")) in ("LEADER", "ON-PACE"):
            sc["POSITION"] = min(100.0, float(sc.get("POSITION") or NEUTRAL) + bonus)
        missing = [f for f in FACTORS if sc.get(f) is None]
        total = sum(weights[f] * float(NEUTRAL if sc.get(f) is None else sc[f]) for f in FACTORS)
        rating = sum((weights[f] / ind_total) * float(NEUTRAL if sc.get(f) is None else sc[f])
                     for f in INDEPENDENT_FACTORS)
        r["score_total"] = round(total, 1)
        r["model_rating"] = round(rating, 2)
        r["scores_missing"] = missing
        ratings.append(rating)
    powered = [x ** spread if x > 0 else 0.0 for x in ratings]
    s = sum(powered)
    for r, p in zip(runners, powered):
        r["win_prob"] = round(p / s, 4) if s > 0 else None


# ---------------------------------------------------------------------------
# ratings: confidence 1-10, value 1-10
# ---------------------------------------------------------------------------

def confidence(race: dict, runners: list, speedmap: dict, ms: dict, audit: dict) -> dict:
    c, why = 5.0, []
    n = len(runners)
    if n <= 8:
        c += 1; why.append("small field (+1)")
    elif n >= 14:
        c -= 1; why.append("big field (−1)")
    probs = sorted([r.get("win_prob") or 0 for r in runners], reverse=True)
    gap = (probs[0] - probs[1]) if len(probs) > 1 else probs[0]
    if gap >= 0.08:
        c += 2; why.append(f"clear top pick (+2, {gap*100:.0f}% gap)")
    elif gap >= 0.04:
        c += 1; why.append(f"modest separation (+1, {gap*100:.0f}% gap)")
    else:
        why.append(f"top runners bunched ({gap*100:.0f}% gap, 0)")
    if speedmap["shape"].startswith("Contested") or speedmap["n_fast_beginners"] >= 3:
        c -= 1; why.append("pace uncertainty (−1)")
    light = sum(1 for r in runners if ((r.get("career") or {}).get("starts") or 99) < 5)
    if n and light >= max(2, 0.3 * n):
        c -= 1; why.append("lightly raced field (−1)")
    ur = audit.get("unavailable_ratio", 0)
    if ur > 0.30:
        c -= 2; why.append("major data gaps (−2)")
    elif ur > 0.15:
        c -= 1; why.append("some data gaps (−1)")
    if n and ms.get("n_priced") == n:
        c += 1; why.append("full market verified (+1)")
    elif ms.get("n_priced") == 0:
        c -= 1; why.append("no odds (−1)")
    band, _ = condition_band(race.get("condition"))
    if band in ("soft", "heavy") and n:
        if sum(1 for r in runners if _wet_proven(r)) < 0.3 * n:
            c -= 1; why.append("wet track, few proven (−1)")
    if "maiden" in str(race.get("race_class") or "").lower():
        c -= 1; why.append("maiden (−1)")
    c = int(max(1, min(10, round(c))))
    lab = ("VERY LOW" if c <= 2 else "LOW" if c <= 4 else "MEDIUM" if c <= 6
           else "HIGH" if c <= 8 else "VERY HIGH")
    return {"score": c, "label": lab, "reasons": why}


def value_rating(r: dict) -> dict:
    edge, ev = r.get("edge"), r.get("ev")
    if edge is None or ev is None:
        return {"score": None, "label": "NO ODDS"}
    if edge >= 0.10 and ev >= 0.20:
        v = 9
    elif edge >= 0.08 and ev >= 0.12:
        v = 8
    elif edge >= 0.06 and ev >= 0.08:
        v = 7
    elif edge >= 0.03 and ev >= MIN_EV:
        v = 6
    elif edge >= 0.0 and ev >= 0:
        v = 4
    elif edge > -0.03:
        v = 3
    else:
        v = 1
    div = (r.get("exchange") or {}).get("divergence")
    if div is not None:
        if div <= -0.03:
            v = min(10, v + 1)          # Betfair shorter -> exchange support
        elif div >= 0.03:
            v = max(1, v - 1)           # bookies shorter than exchange -> over-bet
    if (r.get("movement") or {}).get("direction") == "STEAM":
        v = min(10, v + 1)
    lab = ("STRONG VALUE" if v >= 8 else "VALUE" if v >= 6 else "MARGINAL" if v >= 4
           else "NO VALUE")
    return {"score": v, "label": lab}


# ---------------------------------------------------------------------------
# flags, audit, shortlist, decision
# ---------------------------------------------------------------------------

def auto_flags(runners: list) -> None:
    for r in runners:
        traps = list(r.get("traps") or [])
        red = list(r.get("red_flags") or [])
        pos = list(r.get("positive_signals") or [])
        mp, edge, ev = r.get("market_prob"), r.get("edge"), r.get("ev")
        if edge is not None and mp and mp >= 0.30 and edge <= -0.03:
            traps.append("short-price trap — likely winner but poor value")
        bo = r.get("barrier_outcome") or ""
        if "forced back" in bo or "boxed" in bo or "caught wide" in bo:
            red.append(f"barrier: {bo}")
        if (r.get("weight_change") or 0) > 0 and r.get("last_start_won"):
            traps.append("last-start winner going up in weight")
        if r.get("class_move") == "UP":
            red.append("rises in class")
        elif r.get("class_move") == "DOWN":
            pos.append("class drop")
        mv = (r.get("movement") or {}).get("direction")
        if mv == "BIG DRIFT":
            red.append("significant market drift")
        elif mv == "STEAM":
            pos.append("late market support (steam)")
        if edge is not None and edge >= 0.03 and (ev or 0) >= MIN_EV:
            pos.append("price above fair odds")
        if (r.get("sectional") or {}).get("flag") == "ELITE":
            pos.append("elite closing sectional")
        if r.get("scores_missing"):
            red.append(f"unscored factors: {', '.join(r['scores_missing'])}")
        r["traps"], r["red_flags"], r["positive_signals"] = _dedupe(traps), _dedupe(red), _dedupe(pos)


def data_audit(race: dict, runners: list) -> dict:
    verified, uncertain, unavailable = [], [], []
    for k in RACE_KEYS:
        (unavailable if race.get(k) in (None, "") else verified).append(f"race.{k}")
    for r in runners:
        nm = r.get("name") or f"#{r.get('number')}"
        verified += [f"{nm}: {x}" for x in (r.get("data_verified") or [])]
        uncertain += [f"{nm}: {x}" for x in (r.get("data_uncertain") or [])]
        unavailable += [f"{nm}: {x}" for x in (r.get("data_unavailable") or [])]
        od = r.get("odds")
        if not od or (isinstance(od, dict) and not any(od.values())):
            unavailable.append(f"{nm}: odds")
        for f in r.get("scores_missing") or []:
            unavailable.append(f"{nm}: score {f}")
    tot = len(verified) + len(uncertain) + len(unavailable)
    return {"verified": verified, "uncertain": uncertain, "unavailable": unavailable,
            "counts": {"verified": len(verified), "uncertain": len(uncertain),
                       "unavailable": len(unavailable)},
            "unavailable_ratio": round(len(unavailable) / tot, 3) if tot else 0.0}


def shortlist(runners: list) -> dict:
    by_p = sorted(runners, key=lambda r: -(r.get("win_prob") or 0))
    valued = [r for r in runners if r.get("edge") is not None]

    def pick(r):
        return None if r is None else {"number": r.get("number"), "name": r.get("name"),
                                       "win_prob": r.get("win_prob"), "fair_odds": r.get("fair_odds"),
                                       "bet_price": r.get("bet_price"), "edge": r.get("edge"),
                                       "ev": r.get("ev")}

    best_value = None
    if valued:
        bv = max(valued, key=lambda r: r["edge"])
        if bv["edge"] >= 0.03 and (bv.get("ev") or 0) >= MIN_EV:
            best_value = bv
    rough_c = [r for r in valued if (r.get("win_prob") or 0) < 0.10 and (r.get("ev") or -1) > 0]
    rough = max(rough_c, key=lambda r: r["edge"]) if rough_c else None
    mkt_fav = max([r for r in runners if r.get("market_prob")],
                  key=lambda r: r["market_prob"], default=None)
    vulnerable = (mkt_fav if mkt_fav and mkt_fav.get("edge") is not None
                  and mkt_fav["edge"] <= -0.03 else None)
    avoid = None
    if valued:
        av = min(valued, key=lambda r: r["edge"])
        if av["edge"] <= -0.05:
            avoid = av
    return {
        "top": pick(by_p[0]) if by_p else None,
        "second": pick(by_p[1]) if len(by_p) > 1 else None,
        "third": pick(by_p[2]) if len(by_p) > 2 else None,
        "best_value": pick(best_value),
        "rough_chance": pick(rough),
        "market_favourite": pick(mkt_fav),
        "vulnerable_favourite": pick(vulnerable),
        "vulnerable_note": None if vulnerable else "no genuinely vulnerable favourite",
        "avoid_at_price": pick(avoid),
    }


def decision(runners: list, conf: dict, ms: dict) -> dict:
    if ms.get("n_priced") == 0:
        return {"decision": "WAIT FOR MARKET", "selection": None,
                "reason": "no verified odds — value cannot be assessed yet"}
    cands = [r for r in runners if r.get("value_ok")]
    if not cands:
        return {"decision": "PASS / NO BET", "selection": None,
                "reason": f"no runner clears +{int(MIN_EV*100)}% EV at or above its minimum acceptable odds"}
    best = max(cands, key=lambda r: r["ev"])
    c = conf["score"]
    base = {"selection": label(best), "price": best.get("bet_price"), "win_prob": best.get("win_prob"),
            "fair_odds": best.get("fair_odds"), "min_odds": best.get("min_acceptable_odds"),
            "edge": best.get("edge"), "ev": best.get("ev")}
    if c <= 3:
        return {"decision": "WAIT FOR MARKET", **base, "stake": 0.0,
                "reason": f"value exists but confidence is {c}/10 — wait for scratchings/market to settle"}
    if c >= 6:
        return {"decision": "BET", **base, "stake": best.get("kelly_stake"),
                "reason": f"+{best['ev']*100:.0f}% EV at ${best['bet_price']} vs fair ${best['fair_odds']}, confidence {c}/10"}
    return {"decision": "SMALL BET", **base, "stake": round((best.get("kelly_stake") or 0) / 2, 2),
            "reason": f"value (+{best['ev']*100:.0f}% EV) but only medium confidence {c}/10 — half stake"}


# ---------------------------------------------------------------------------
# orchestrator
# ---------------------------------------------------------------------------

def analyse(data: dict, bankroll: float = 100.0, spread: float = DEFAULT_SPREAD) -> dict:
    race = data.get("race") or {}
    runners = [r for r in (data.get("runners") or []) if not r.get("scratched")]
    if not runners:
        raise ValueError("no (unscratched) runners in race.json")
    race.setdefault("field_size", len(runners))

    weights, wnotes, mods = adjust_weights(race, len(runners))
    grade = parse_class(race.get("race_class"))
    hcap = analyse_handicap(race, runners)
    sm = build_speedmap(runners, race.get("track"))
    pat = detect_pattern(data.get("earlier_races_today") or [], race.get("track"), race.get("field_size"))
    for r in runners:
        if r.get("last600") is not None:
            r["sectional"] = assess_last600(float(r["last600"]), race.get("distance"))

    score_runners(runners, weights, mods, spread)
    ms = evaluate_market(runners, bankroll)
    auto_flags(runners)
    for r in runners:
        r["value_rating"] = value_rating(r)
    audit = data_audit(race, runners)
    conf = confidence(race, runners, sm, ms, audit)

    runners.sort(key=lambda r: -(r.get("win_prob") or 0))
    for i, r in enumerate(runners, 1):
        r["rank"] = i
    ex = build_exotics(runners, bankroll=bankroll)

    return {
        "race": race,
        "grade": grade,
        "weights_pct": {f: round(w * 100, 1) for f, w in weights.items()},
        "weight_notes": wnotes,
        "handicap": hcap,
        "speedmap": sm,
        "track_pattern": pat,
        "market": ms,
        "confidence": conf,
        "decision": decision(runners, conf, ms),
        "shortlist": shortlist(runners),
        "data_audit": audit,
        "exotics": ex,
        "bankroll": bankroll,
        "spread": spread,
        "runners": runners,
    }
