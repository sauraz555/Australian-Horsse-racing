"""Market analysis: implied probability, overround, de-vig, value classification,
Expected Value and Quarter-Kelly staking.
"""
from __future__ import annotations

from typing import Optional, Tuple

KELLY_FRACTION = 0.25          # Quarter-Kelly
MAX_STAKE_FRACTION = 0.05      # hard cap: 5% of bankroll on a single bet
MIN_EV = 0.05                  # +5% EV threshold to recommend a bet


def implied_prob(odds: Optional[float]) -> Optional[float]:
    return 1.0 / odds if odds and odds > 0 else None


def market_summary(runners: list) -> dict:
    imp = [implied_prob(r.get("odds")) for r in runners]
    priced = [p for p in imp if p is not None]
    overround = sum(priced) if priced else None
    return {
        "overround": round(overround, 4) if overround is not None else None,
        "overround_pct": round(overround * 100, 1) if overround is not None else None,
        "n_priced": len(priced),
        "n_runners": len(runners),
    }


def classify_value(edge: float) -> str:
    if edge >= 0.08:
        return "STRONG OVERLAY ✅✅"
    if edge >= 0.03:
        return "OVERLAY ✅"
    if edge > -0.03:
        return "FAIR ⚖️"
    return "UNDERLAY ❌"


def expected_value(model_p: float, odds: float) -> float:
    return model_p * odds - 1.0


def quarter_kelly(model_p: Optional[float], odds: Optional[float], bankroll: float,
                  cap: float = MAX_STAKE_FRACTION,
                  fraction: float = KELLY_FRACTION) -> Tuple[float, float]:
    """Return (stake_fraction, stake_amount). Negative Kelly -> no bet (0, 0)."""
    if not odds or odds <= 1 or model_p is None:
        return 0.0, 0.0
    b = odds - 1.0
    q = 1.0 - model_p
    f_star = (b * model_p - q) / b
    if f_star <= 0:
        return 0.0, 0.0
    frac = min(cap, f_star * fraction)
    return frac, round(frac * bankroll, 2)


def evaluate_market(runners: list, bankroll: float = 100.0, min_ev: float = MIN_EV) -> dict:
    """Populate market fields on each runner dict in place; return the summary."""
    summ = market_summary(runners)
    orr = summ["overround"]
    for r in runners:
        odds = r.get("odds")
        model_p = r.get("tissue_prob")
        imp = implied_prob(odds)
        r["market_prob"] = round(imp, 5) if imp is not None else None
        r["devig_prob"] = round(imp / orr, 5) if (imp is not None and orr) else None

        if model_p is not None and r["devig_prob"] is not None:
            edge = model_p - r["devig_prob"]
            r["edge"] = round(edge, 4)
            r["value_class"] = classify_value(edge)
        else:
            r["edge"] = None
            r["value_class"] = "NO ODDS — cannot price value"

        if model_p is not None and odds:
            ev = expected_value(model_p, odds)
            frac, stake = quarter_kelly(model_p, odds, bankroll)
            r["ev"] = round(ev, 4)
            r["kelly_fraction"] = round(frac, 4)
            r["kelly_stake"] = stake
            r["bet"] = "BET" if (ev >= min_ev and frac > 0) else "NO BET"
        else:
            r["ev"] = None
            r["kelly_fraction"] = 0.0
            r["kelly_stake"] = 0.0
            r["bet"] = "NO ODDS"
    return summ
