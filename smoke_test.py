"""Deterministic smoke test — runs the math core with NO third-party deps and NO
API key. Verifies weight normalization, tissue probabilities, de-vig, EV and the
Quarter-Kelly 5% cap. Also scores the bundled sample if present.

Run:  python smoke_test.py
"""
import json
import os
import sys

try:  # keep emoji value-flags from crashing cp1252 (Windows) consoles
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from horse_edge.models import FACTORS
from horse_edge.weights import BASE_WEIGHTS, adjust_weights, RANGES
from horse_edge.scoring import score_runners
from horse_edge.market import evaluate_market, MAX_STAKE_FRACTION

FAILS = []


def check(cond, msg):
    if cond:
        print(f"  ok  {msg}")
    else:
        print(f"FAIL  {msg}")
        FAILS.append(msg)


def test_base_weights():
    print("\n[base weights]")
    check(abs(sum(BASE_WEIGHTS.values()) - 100) < 1e-9, "base weights sum to 100")
    check(set(BASE_WEIGHTS) == set(FACTORS), "base weights cover all 10 factors")
    for f, (lo, hi) in RANGES.items():
        check(lo <= BASE_WEIGHTS[f] <= hi, f"{f} base within range [{lo},{hi}]")


def test_adjust_normalizes():
    print("\n[weight adjustment]")
    w, notes, mods = adjust_weights({"condition": "Heavy 9", "distance": 1200,
                                     "field_size": 14, "track": "Randwick"})
    check(abs(sum(w.values()) - 1.0) < 1e-9, "adjusted weights normalize to 1.0")
    check(w["SUIT"] > BASE_WEIGHTS["SUIT"] / 100, "heavy track lifts SUIT weight")
    check(w["SPD"] < BASE_WEIGHTS["SPD"] / 100, "heavy track cuts SPD weight")

    wt, _n, modt = adjust_weights({"condition": "Good 4", "distance": 1100,
                                   "field_size": 8, "track": "Canterbury", "tight": True})
    check(modt["on_pace_pace_bonus"] == 5.0, "tight track gives on-pace PACE bonus")


def test_scoring_and_market():
    print("\n[scoring + market]")
    runners = [
        {"name": "A", "barrier": 2, "running_style": "LEADER", "odds": 3.0,
         "factor_scores": {f: 75 for f in FACTORS}},
        {"name": "B", "barrier": 4, "running_style": "ON-PACE", "odds": 4.5,
         "factor_scores": {f: 65 for f in FACTORS}},
        {"name": "C", "barrier": 7, "running_style": "BACKMARKER", "odds": 9.0,
         "factor_scores": {f: 55 for f in FACTORS}},
    ]
    weights, _n, mods = adjust_weights({"condition": "Good 4", "distance": 1400,
                                        "field_size": 3, "track": "Randwick"})
    score_runners(runners, weights, mods["on_pace_pace_bonus"])
    total = sum(r["tissue_prob"] for r in runners)
    check(abs(total - 1.0) < 1e-6, "tissue probabilities sum to 1.0")
    check(runners[0]["tissue_prob"] > runners[2]["tissue_prob"], "higher sub-scores -> higher tissue")

    evaluate_market(runners, bankroll=100.0)
    for r in runners:
        check(r["kelly_fraction"] <= MAX_STAKE_FRACTION + 1e-9,
              f"{r['name']} stake within 5% cap")
        # EV consistency: EV = p*odds - 1 (stored values are rounded to 4dp)
        check(abs(r["ev"] - (r["tissue_prob"] * r["odds"] - 1)) < 1e-3,
              f"{r['name']} EV matches p*odds-1")


def test_spread():
    print("\n[tissue spread]")
    import copy
    base = [
        {"name": "Fav", "odds": 2.0, "factor_scores": {f: 80 for f in FACTORS}},
        {"name": "Mid", "odds": 5.0, "factor_scores": {f: 65 for f in FACTORS}},
        {"name": "Out", "odds": 15.0, "factor_scores": {f: 55 for f in FACTORS}},
    ]
    weights, _n, _m = adjust_weights({"distance": 1400, "field_size": 3})
    linear = copy.deepcopy(base)
    score_runners(linear, weights, spread=1.0)
    sharp = copy.deepcopy(base)
    score_runners(sharp, weights, spread=7.0)
    check(abs(sum(r["tissue_prob"] for r in sharp) - 1.0) < 1e-6, "spread tissue sums to 1.0")
    check(sharp[0]["tissue_prob"] > linear[0]["tissue_prob"], "spread>1 lifts favourite share")
    check(sharp[2]["tissue_prob"] < linear[2]["tissue_prob"], "spread>1 shortens outsider share")
    print(f"  linear fav {linear[0]['tissue_prob']*100:.1f}% -> "
          f"spread fav {sharp[0]['tissue_prob']*100:.1f}%")


def test_negative_kelly_no_bet():
    print("\n[no-value guard]")
    runners = [
        {"name": "Fav", "odds": 1.5, "factor_scores": {f: 50 for f in FACTORS}},
        {"name": "Dog", "odds": 3.0, "factor_scores": {f: 50 for f in FACTORS}},
    ]
    weights, _n, _m = adjust_weights({"distance": 1200, "field_size": 2})
    score_runners(runners, weights)
    evaluate_market(runners, bankroll=100.0)
    # equal ratings -> each ~50% model; the 1.5 shot (implied ~67%) must be no-bet
    fav = runners[0]
    check(fav["ev"] < 0.05, "overbet favourite fails EV threshold")
    check(fav["bet"] == "NO BET", "overbet favourite flagged NO BET")


def test_exotics():
    print("\n[exotics]")
    from horse_edge.exotics import build_exotics
    probs = [0.30, 0.22, 0.15, 0.12, 0.08, 0.06, 0.04, 0.03]
    runners = [{"name": f"R{i}", "number": i, "tissue_prob": p}
               for i, p in enumerate(probs, start=1)]
    ex = build_exotics(runners, bankroll=100.0, n=5000, seed=1)
    check(abs(sum(r["p_win"] for r in runners) - 1.0) < 0.02, "p_win sums ~1.0")
    check(abs(sum(r["p_top4"] for r in runners) - 4.0) < 0.05, "p_top4 sums ~4.0")
    check(len(ex["best2_for_top4"]) == 2, "best 2 for top 4 returned")
    check(ex["trifecta"]["combos"] == 6, "trifecta banker = 3P2 = 6 combos")
    check(ex["first_four"]["combos"] == 24, "first four banker = 4P3 = 24 combos")
    check(runners[0]["p_top4"] > runners[-1]["p_top4"], "stronger runner higher top-4 prob")


def test_grade():
    print("\n[grade]")
    from horse_edge.classlevel import parse_class
    check(parse_class("BM88")["band"] == "high", "BM88 -> high grade")
    check(parse_class("Class 3 Maiden")["band"] == "low", "maiden -> low grade")
    check(parse_class("Group 2")["matched"] == "Group 2", "Group 2 recognised")
    check(parse_class("BM64")["band"] == "low", "BM64 -> low grade")
    check(parse_class("Listed")["band"] == "high", "Listed -> high grade")


def test_sample():
    print("\n[bundled sample]")
    path = os.path.join(os.path.dirname(__file__), "sample_race.json")
    if not os.path.exists(path):
        print("  (sample_race.json not found — skipped)")
        return
    with open(path, encoding="utf-8") as f:
        rc = json.load(f)
    runners = rc["runners"]
    weights, _n, mods = adjust_weights({
        "condition": rc["condition"], "distance": rc["distance"],
        "field_size": rc["field_size"], "track": rc["track"],
    })
    score_runners(runners, weights, mods["on_pace_pace_bonus"])
    evaluate_market(runners, bankroll=100.0)
    check(abs(sum(r["tissue_prob"] for r in runners) - 1.0) < 1e-6,
          "sample tissue probabilities sum to 1.0")
    top = max(runners, key=lambda r: r["tissue_prob"])
    print(f"  model favourite: {top['name']} "
          f"({top['tissue_prob']*100:.1f}%, ${top['odds']}, {top['value_class']})")


def main():
    test_base_weights()
    test_adjust_normalizes()
    test_scoring_and_market()
    test_spread()
    test_negative_kelly_no_bet()
    test_exotics()
    test_grade()
    test_sample()
    print("\n" + ("=" * 40))
    if FAILS:
        print(f"{len(FAILS)} CHECK(S) FAILED")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
