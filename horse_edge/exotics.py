"""Exotic bet construction from the MODEL ratings (not the market).

Runs a Plackett-Luce / Harville Monte-Carlo over each runner's tissue strength to
estimate top-2/3/4 finishing probabilities, then builds:
  - Best 2 for Top 4 (place / exotic anchors)
  - Quinella (top-2 pair)
  - Trifecta (banker structure)
  - First Four (banker structure)
plus the single most-likely trifecta and first-four orderings for reference.

Because the strengths come from the factor sub-scores (jockey, class, gear, pace,
sectionals, …) rather than the odds, these structures reflect the handicapping,
not the market.
"""
from __future__ import annotations

import random
from collections import Counter
from itertools import permutations

DEFAULT_SIMS = 20000
DEFAULT_SEED = 42


def _sample_top_k(strengths, k, rng):
    """One Plackett-Luce draw of the first k finishers (weighted, no replacement)."""
    pool = [(i, w) for i, w in strengths if w > 0]
    order = []
    for _ in range(min(k, len(pool))):
        total = sum(w for _, w in pool)
        r = rng.random() * total
        acc = 0.0
        pick = len(pool) - 1
        for j, (_idx, w) in enumerate(pool):
            acc += w
            if r <= acc:
                pick = j
                break
        order.append(pool[pick][0])
        pool.pop(pick)
    return order


def simulate_places(runners, n=DEFAULT_SIMS, seed=DEFAULT_SEED, k=4):
    rng = random.Random(seed)
    m = len(runners)
    strengths = [(i, max(float(r.get("tissue_prob") or 0.0), 0.0)) for i, r in enumerate(runners)]
    win = [0] * m
    top2 = [0] * m
    top3 = [0] * m
    top4 = [0] * m
    tri = Counter()
    ff = Counter()
    pair = Counter()
    kk = min(k, m)
    for _ in range(n):
        order = _sample_top_k(strengths, kk, rng)
        if order:
            win[order[0]] += 1
        for idx in order[:2]:
            top2[idx] += 1
        for idx in order[:3]:
            top3[idx] += 1
        for idx in order[:4]:
            top4[idx] += 1
        if len(order) >= 2:
            pair[frozenset(order[:2])] += 1
        if len(order) >= 3:
            tri[tuple(order[:3])] += 1
        if len(order) >= 4:
            ff[tuple(order[:4])] += 1
    return {"n": n, "win": win, "top2": top2, "top3": top3, "top4": top4,
            "tri": tri, "ff": ff, "pair": pair}


def _banker_hit(counter, banker, minors, n):
    """Fraction of sims where `banker` won and the remaining places ⊆ `minors`."""
    hit = 0
    for order, cnt in counter.items():
        if order[0] == banker and all(x in minors for x in order[1:]):
            hit += cnt
    return hit / n if n else 0.0


def build_exotics(runners, bankroll=100.0, n=DEFAULT_SIMS, seed=DEFAULT_SEED):
    m = len(runners)
    if m < 3:
        return {"note": "field too small for exotics (need >= 3 runners)"}

    sim = simulate_places(runners, n=n, seed=seed)
    N = sim["n"]

    def label(i):
        return {"number": runners[i].get("number"), "name": runners[i].get("name")}

    # attach place probabilities onto each runner (model-based)
    for i, r in enumerate(runners):
        r["p_win"] = round(sim["win"][i] / N, 4)
        r["p_top2"] = round(sim["top2"][i] / N, 4)
        r["p_top3"] = round(sim["top3"][i] / N, 4)
        r["p_top4"] = round(sim["top4"][i] / N, 4)

    order_win = sorted(range(m), key=lambda i: sim["win"][i], reverse=True)
    order_t4 = sorted(range(m), key=lambda i: sim["top4"][i], reverse=True)
    banker = order_win[0]

    best2 = [{**label(i), "p_top4": round(sim["top4"][i] / N, 4)} for i in order_t4[:2]]

    # Quinella: the top-2 by win probability
    q = order_win[:2]
    quinella = {
        "selections": [label(i) for i in q],
        "hit_prob": round(sim["pair"].get(frozenset(q), 0) / N, 4),
    }

    # Trifecta banker: win pick over the next 3 (by top-4 prob) for 2nd/3rd
    minors3 = [i for i in order_t4 if i != banker][:3]
    tri = None
    if len(minors3) == 3:
        combos = len(list(permutations(minors3, 2)))  # 3P2 = 6
        outlay = round(0.010 * bankroll, 2)
        tri = {
            "structure": "banker to win, over 3 for 2nd/3rd",
            "banker": label(banker),
            "minors": [label(i) for i in minors3],
            "combos": combos,
            "hit_prob": round(_banker_hit(sim["tri"], banker, set(minors3), N), 4),
            "suggested_flexi_outlay": outlay,
            "per_combo": round(outlay / combos, 2) if combos else 0.0,
            "confidence": "Med",
        }
    tri_modal = None
    if sim["tri"]:
        (a, b, c), cnt = sim["tri"].most_common(1)[0]
        tri_modal = {"selections": [label(a), label(b), label(c)], "prob": round(cnt / N, 4)}

    # First Four banker: win pick over the next 4 for 2nd/3rd/4th
    minors4 = [i for i in order_t4 if i != banker][:4]
    ff = None
    if m >= 4 and len(minors4) == 4:
        combos = len(list(permutations(minors4, 3)))  # 4P3 = 24
        outlay = round(0.005 * bankroll, 2)
        ff = {
            "structure": "banker to win, over 4 for 2nd/3rd/4th",
            "banker": label(banker),
            "minors": [label(i) for i in minors4],
            "combos": combos,
            "hit_prob": round(_banker_hit(sim["ff"], banker, set(minors4), N), 4),
            "suggested_flexi_outlay": outlay,
            "per_combo": round(outlay / combos, 2) if combos else 0.0,
            "confidence": "Low",
        }
    ff_modal = None
    if sim["ff"]:
        (a, b, c, d), cnt = sim["ff"].most_common(1)[0]
        ff_modal = {"selections": [label(a), label(b), label(c), label(d)], "prob": round(cnt / N, 4)}

    return {
        "sims": N,
        "note": "Model-based (Plackett-Luce over ratings). Exotic EV needs live pool "
                "dividends — size these small; treat as structured plays, not EV-verified.",
        "best2_for_top4": best2,
        "quinella": quinella,
        "trifecta": tri,
        "trifecta_most_likely": tri_modal,
        "first_four": ff,
        "first_four_most_likely": ff_modal,
    }
