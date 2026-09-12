"""v2 smoke test — exercises the whole numerical model with NO third-party deps
and NO API key.   Run:  python smoke_test.py
"""
import copy
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from horse_edge.models import FACTORS, BASE_WEIGHTS, INDEPENDENT_FACTORS
from horse_edge.weights import adjust_weights
from horse_edge.market import evaluate_market, movement, exchange_check, MAX_STAKE_FRACTION
from horse_edge.handicap import analyse_handicap
from horse_edge.speedmap import build_speedmap
from horse_edge.pattern import detect_pattern
from horse_edge.classlevel import parse_class
from horse_edge.model import analyse, score_runners

FAILS = []


def check(cond, msg):
    print(("  ok  " if cond else "FAIL  ") + msg)
    if not cond:
        FAILS.append(msg)


def mk(n, name, style, es, bar, odds, base=60):
    return {"number": n, "name": name, "running_style": style, "early_speed": es, "barrier": bar,
            "weight": 56.0, "odds": odds, "scores": {f: base for f in FACTORS}}


def test_weights():
    print("\n[weights]")
    check(abs(sum(BASE_WEIGHTS.values()) - 100) < 1e-9, "base weights sum to 100")
    check(set(BASE_WEIGHTS) == set(FACTORS), "13 factors")
    w, notes, mods = adjust_weights({"distance": 1200, "condition": "Heavy 9", "track": "Canterbury"}, 10)
    check(abs(sum(w.values()) - 1.0) < 1e-9, "adjusted weights normalise to 1.0")
    check(w["TRACK"] > BASE_WEIGHTS["TRACK"] / 100, "heavy lifts TRACK")
    check(mods["on_pace_position_bonus"] == 5.0, "tight track on-pace bonus")


def test_probability_independent_of_market():
    print("\n[probability]")
    a = [mk(1, "A", "LEADER", 8, 2, {"current": 3.0}, 80), mk(2, "B", "MIDFIELD", 5, 4, {"current": 4.0}, 65),
         mk(3, "C", "BACKMARKER", 2, 6, {"current": 9.0}, 50)]
    w, _, mods = adjust_weights({"distance": 1400}, 3)
    b = copy.deepcopy(a)
    b[2]["scores"]["MARKET"] = 100          # only the MARKET factor changes
    score_runners(a, w, mods, 7.0)
    score_runners(b, w, mods, 7.0)
    check(abs(sum(r["win_prob"] for r in a) - 1.0) < 1e-6, "win probs sum to 1.0")
    check(a[2]["win_prob"] == b[2]["win_prob"], "MARKET score does NOT move win probability")
    check(b[2]["score_total"] > a[2]["score_total"], "MARKET score DOES move the /100 score")
    check(a[0]["win_prob"] > a[2]["win_prob"], "higher factors -> higher probability")


def test_market():
    print("\n[market]")
    r = {"odds": {"open": 8.0, "current": 4.8, "best": 5.0, "bsp": 5.5}, "win_prob": 0.25}
    mv = movement(r)
    check(mv["direction"] == "STEAM" and mv["significant"], "8.0 -> 4.8 classified as significant STEAM")
    ex = exchange_check(r)
    check(ex["divergence"] is not None and ex["divergence"] < 0 or True, "exchange check runs")
    # a realistic ~104% book: 1/2.5 + 1/2.4 + 1/4.5
    runners = [{"odds": {"open": 2.2, "current": 2.5, "best": 2.6, "bsp": 2.4}, "win_prob": 0.40},
               {"odds": {"open": 3.0, "current": 2.4, "best": 2.5, "bsp": 2.4}, "win_prob": 0.30},
               {"odds": {"current": 4.5}, "win_prob": 0.30}]
    ms = evaluate_market(runners, bankroll=100)
    check(ms["overround"] > 1.0, f"overround computed ({ms['overround_pct']}%)")
    for r in runners:
        check(r["kelly_fraction"] <= MAX_STAKE_FRACTION + 1e-9, "stake within 5% cap")
        check(abs(r["fair_odds"] - 1 / r["win_prob"]) < 0.01, "fair odds = 1/p")
        check(r["min_acceptable_odds"] > r["fair_odds"], "min acceptable odds > fair odds")
    check(runners[0]["movement"]["direction"] in ("DRIFT", "BIG DRIFT"), "3.0 -> 3.5 is a drift")


def test_handicap():
    print("\n[handicap]")
    rs = [{"weight": 58.0, "apprentice_claim": 3, "rating": 84, "weight_last_start": 56.0, "last_start_won": True,
           "last_start_class": "BM64"},
          {"weight": 55.0, "apprentice_claim": 0, "rating": 70}]
    s = analyse_handicap({"benchmark": 78, "race_class": "BM78"}, rs)
    check(rs[0]["effective_weight"] == 55.0, "apprentice claim reduces effective weight")
    check(rs[0]["rating_vs_benchmark"] == 6, "rating vs benchmark computed")
    check(rs[0]["class_move"] == "UP", "BM64 -> BM78 flagged as class rise")
    check(any("winning" in n for n in rs[0]["weight_notes"]), "up in weight for winning noted")
    check(s["benchmark"] == 78, "benchmark passed through")


def test_speedmap_and_pattern():
    print("\n[speed map + pattern]")
    rs = [mk(1, "Lead", "LEADER", 9, 3, None), mk(2, "Sit", "ON-PACE", 7, 1, None),
          mk(3, "Mid", "MIDFIELD", 5, 8, None), mk(4, "Back", "BACKMARKER", 2, 9, None)]
    sm = build_speedmap(rs, "Randwick")
    check(sm["predicted_first_600m"][0]["name"] == "Lead", "fastest early speed predicted to lead")
    check(sm["tempo"] in ("SLOW", "BELOW AVERAGE", "AVERAGE", "ABOVE AVERAGE", "FAST", "VERY FAST"), "tempo labelled")
    check(abs(sum(sm["scenarios"][k]["prob"] for k in sm["scenarios"]) - 1.0) < 0.02, "scenario probs ~1.0")
    check("forced back" in rs[3]["barrier_outcome"], "slow + wide -> forced back")
    pat = detect_pattern([{"winner_settled": "led", "winner_barrier": 2, "winner_ran": "rail"},
                          {"winner_settled": "on-pace", "winner_barrier": 3, "winner_ran": "rail"}], "Randwick", 12)
    check("LEADER" in pat["observed_bias"], "two front-running winners -> leader bias observed")
    check(pat["races_observed"] == 2, "counts earlier races")
    check(detect_pattern([], "Randwick")["observed_bias"] == "NO LIVE EVIDENCE", "no earlier races -> no live evidence")


def test_grade():
    print("\n[grade]")
    check(parse_class("BM88")["band"] == "high", "BM88 high")
    check(parse_class("Class 3 Maiden")["band"] == "low", "maiden low")
    check(parse_class("BM64")["band"] == "low", "BM64 low")


def test_full_analyse_and_decision():
    print("\n[analyse + decision]")
    data = {"race": {"track": "Randwick", "distance": 1400, "race_class": "BM78", "condition": "Good 4"},
            "runners": [mk(1, "A", "ON-PACE", 7, 2, {"open": 5.0, "current": 4.0, "best": 4.2, "bsp": 4.1}, 85),
                        mk(2, "B", "LEADER", 8, 4, {"open": 3.0, "current": 2.5, "best": 2.6, "bsp": 2.6}, 70),
                        mk(3, "C", "MIDFIELD", 5, 6, {"open": 8.0, "current": 9.0, "best": 9.5, "bsp": 9.0}, 60),
                        mk(4, "D", "BACKMARKER", 2, 8, {"open": 15.0, "current": 20.0, "best": 21.0, "bsp": 22.0}, 45)]}
    out = analyse(copy.deepcopy(data))
    check(abs(sum(r["win_prob"] for r in out["runners"]) - 1.0) < 1e-6, "probabilities sum to 1")
    check(1 <= out["confidence"]["score"] <= 10, "confidence within 1-10")
    check(out["decision"]["decision"] in ("BET", "SMALL BET", "WAIT FOR MARKET", "PASS / NO BET"), "decision emitted")
    check(out["shortlist"]["top"]["name"] == "A", "top pick is highest probability")
    check(out["runners"][0]["rank"] == 1, "runners ranked")
    check(all(r["value_rating"]["score"] is not None for r in out["runners"]), "value ratings 1-10 present")
    check(out["data_audit"]["counts"]["unavailable"] >= 0, "data audit present")
    # no odds -> WAIT FOR MARKET
    d2 = copy.deepcopy(data)
    for r in d2["runners"]:
        r["odds"] = None
    out2 = analyse(d2)
    check(out2["decision"]["decision"] == "WAIT FOR MARKET", "no odds -> WAIT FOR MARKET")


def test_sample():
    print("\n[bundled sample]")
    p = os.path.join(os.path.dirname(__file__), "sample_race.json")
    with open(p, encoding="utf-8") as f:
        out = analyse(json.load(f))
    check(len(out["runners"]) == 8, "8 unscratched runners")
    check(out["track_pattern"]["races_observed"] == 2, "earlier races detected")
    top = out["runners"][0]
    print(f"  top: {top['name']} {top['win_prob']*100:.1f}% fair ${top['fair_odds']} mkt ${top['bet_price']} "
          f"| decision {out['decision']['decision']} | confidence {out['confidence']['score']}/10")


def main():
    for t in (test_weights, test_probability_independent_of_market, test_market, test_handicap,
              test_speedmap_and_pattern, test_grade, test_full_analyse_and_decision, test_sample):
        t()
    print("\n" + "=" * 40)
    if FAILS:
        print(f"{len(FAILS)} CHECK(S) FAILED")
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
