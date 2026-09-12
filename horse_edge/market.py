"""Market layer: implied probabilities, overround, de-vig, SP movement
(opening → current → best), Betfair BSP divergence, value edge, EV, fair odds,
minimum acceptable odds and Quarter-Kelly staking.

Runner odds are a dict: {"open": 6.0, "current": 4.8, "best": 5.0, "bsp": 5.2}.
Any key may be null. `best` (best available fixed price) is the betting price;
`current` sets the overround; `bsp` is the exchange cross-check.
"""
from __future__ import annotations

from typing import Optional

KELLY_FRACTION = 0.25
MAX_STAKE_FRACTION = 0.05
MIN_EV = 0.05
SIGNIFICANT_MOVE = 0.05        # implied-probability shift that counts as a real move
EXCHANGE_DIVERGENCE = 0.03


def implied(odds: Optional[float]) -> Optional[float]:
    try:
        o = float(odds)
    except (TypeError, ValueError):
        return None
    return 1.0 / o if o > 1.0 else None


def _price(r: dict, key: str) -> Optional[float]:
    od = r.get("odds")
    if isinstance(od, dict):
        return od.get(key)
    if key in ("current", "best") and od not in (None, ""):   # bare number
        return od
    return None


def bet_price(r: dict) -> Optional[float]:
    return _price(r, "best") or _price(r, "current") or _price(r, "bsp")


def classify_value(edge: float) -> str:
    if edge >= 0.08:
        return "STRONG OVERLAY"
    if edge >= 0.03:
        return "OVERLAY"
    if edge > -0.03:
        return "FAIR"
    return "UNDERLAY"


def movement(r: dict) -> dict:
    o, c = _price(r, "open"), _price(r, "current")
    io, ic = implied(o), implied(c)
    if io is None or ic is None:
        return {"direction": "unknown", "shift": None, "significant": False,
                "note": "opening/current price not verified"}
    shift = ic - io                           # + = shortened (support)
    if abs(shift) < 0.01:
        d = "STEADY"
    elif shift > 0:
        d = "STEAM" if shift >= SIGNIFICANT_MOVE else "SUPPORT"
    else:
        d = "BIG DRIFT" if -shift >= SIGNIFICANT_MOVE else "DRIFT"
    return {"direction": d, "open": o, "current": c, "shift": round(shift, 4),
            "significant": abs(shift) >= SIGNIFICANT_MOVE,
            "note": f"${o} → ${c} ({shift*100:+.1f}% implied)"}


def exchange_check(r: dict) -> dict:
    c, b = _price(r, "current"), _price(r, "bsp")
    ic, ib = implied(c), implied(b)
    if ic is None or ib is None:
        return {"divergence": None, "note": "BSP not verified"}
    div = ic - ib                             # + = bookies shorter than exchange
    if div >= EXCHANGE_DIVERGENCE:
        note = "bookmakers shorter than Betfair — exchange says it's over-bet"
    elif -div >= EXCHANGE_DIVERGENCE:
        note = "Betfair shorter than bookmakers — exchange support; trust the exchange"
    else:
        note = "exchange agrees with bookmakers"
    return {"current": c, "bsp": b, "divergence": round(div, 4), "note": note}


def quarter_kelly(p: Optional[float], odds: Optional[float], bankroll: float):
    if p is None or not odds or odds <= 1:
        return 0.0, 0.0
    b = odds - 1.0
    f = (b * p - (1 - p)) / b
    if f <= 0:
        return 0.0, 0.0
    frac = min(MAX_STAKE_FRACTION, f * KELLY_FRACTION)
    return round(frac, 4), round(frac * bankroll, 2)


def evaluate_market(runners: list, bankroll: float = 100.0, min_ev: float = MIN_EV) -> dict:
    cur = [implied(_price(r, "current")) for r in runners]
    priced = [p for p in cur if p is not None]
    overround = sum(priced) if priced else None
    n_open = sum(1 for r in runners if _price(r, "open"))
    n_bsp = sum(1 for r in runners if _price(r, "bsp"))

    for r in runners:
        p = r.get("win_prob")
        price = bet_price(r)
        ic = implied(_price(r, "current"))
        r["market_prob"] = round(ic, 4) if ic is not None else None
        r["devig_prob"] = round(ic / overround, 4) if (ic is not None and overround) else None
        r["bet_price"] = price
        r["movement"] = movement(r)
        r["exchange"] = exchange_check(r)
        r["fair_odds"] = round(1.0 / p, 2) if p else None
        r["min_acceptable_odds"] = round((1.0 + min_ev) / p, 2) if p else None

        if p is not None and r["devig_prob"] is not None:
            edge = p - r["devig_prob"]
            r["edge"] = round(edge, 4)
            r["value_class"] = classify_value(edge)
        else:
            r["edge"] = None
            r["value_class"] = "NO ODDS"
        if p is not None and price:
            ev = p * price - 1.0
            frac, stake = quarter_kelly(p, price, bankroll)
            r["ev"] = round(ev, 4)
            r["kelly_fraction"] = frac
            r["kelly_stake"] = stake
            r["value_ok"] = bool(ev >= min_ev and frac > 0 and price >= (r["min_acceptable_odds"] or 0))
        else:
            r["ev"] = None
            r["kelly_fraction"] = 0.0
            r["kelly_stake"] = 0.0
            r["value_ok"] = False

    return {"overround": round(overround, 4) if overround else None,
            "overround_pct": round(overround * 100, 1) if overround else None,
            "n_priced": len(priced), "n_runners": len(runners),
            "n_with_opening": n_open, "n_with_bsp": n_bsp}
