"""HorseEdgeEngine v2 CLI — the agent runs ONE command after its research.

  analyze  <race.json>   the whole numerical model -> analysis.json (+ summary)
  template [-o file]     the race.json schema with a worked example runner
  extract  <file>        PDF / Excel / CSV / text form guide -> plain text
  guide                  the one-shot agent workflow
  demo                   analyse the bundled sample
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .models import FACTORS
from .model import analyse, DEFAULT_SPREAD
from . import extract as extract_mod

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------

def cmd_analyze(args) -> None:
    with open(args.race, encoding="utf-8") as f:
        data = json.load(f)
    try:
        out = analyse(data, bankroll=args.bankroll, spread=args.spread)
    except ValueError as e:
        sys.exit(f"ERROR: {e}")
    dest = args.output or os.path.join(os.path.dirname(os.path.abspath(args.race)), "analysis.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print_summary(out)
    print(f"\nWrote {dest}")


def cmd_template(args) -> None:
    dest = args.output or "race.json"
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(TEMPLATE, f, indent=2, ensure_ascii=False)
    print(f"Template written -> {dest}")


def cmd_extract(args) -> None:
    text = extract_mod.extract_text(args.input)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Extracted {len(text)} chars -> {args.output}")
    else:
        print(text)


def cmd_guide(args) -> None:
    print(GUIDE)


def cmd_demo(args) -> None:
    sample = os.path.join(_ROOT, "sample_race.json")
    if not os.path.exists(sample):
        sys.exit(f"sample not found: {sample}")
    ns = argparse.Namespace(race=sample, bankroll=args.bankroll, spread=args.spread,
                            output=os.path.join(_ROOT, "sample_analysis.json"))
    cmd_analyze(ns)


# ---------------------------------------------------------------------------
# printing
# ---------------------------------------------------------------------------

def _pct(x, d=1):
    return "-" if x is None else f"{x*100:.{d}f}%"


def _num(x, fmt="{:.2f}"):
    return "-" if x is None else fmt.format(x)


def print_summary(out: dict) -> None:
    race, sm, pat = out["race"], out["speedmap"], out["track_pattern"]
    W = 100
    print("\n" + "=" * W)
    print(f"{race.get('track','?')}  R{race.get('race_no','?')}  {race.get('distance','?')}m  "
          f"{race.get('race_class','')}  [{race.get('condition','?')} | rail {race.get('rail','?')}]"
          f"  grade: {out['grade'].get('band','?').upper()}")
    print(f"Tempo: {sm['tempo']} (fast beginners {sm['n_fast_beginners']}, PPI {sm['ppi']}) — "
          f"{sm['shape']}")
    lead = ", ".join(f"{o['name']}(#{o['number']})" for o in sm["predicted_first_600m"][:4])
    print(f"First 600m: {lead}")
    print(f"Today's pattern: {pat['observed_bias']} [{pat['strength']}] | historical: {pat.get('historical_bias')}")
    mk = out["market"]
    if mk.get("overround_pct"):
        print(f"Market: {mk['overround_pct']}% book ({mk['n_priced']}/{mk['n_runners']} priced, "
              f"{mk['n_with_opening']} with opening, {mk['n_with_bsp']} with BSP)")
    print("-" * W)
    print(f"{'Rk':>2} {'#':>2} {'Horse':<18} {'Score':>5} {'Win%':>6} {'Fair':>6} {'Mkt$':>6} "
          f"{'Edge':>6} {'EV':>7} {'Move':>9} {'Val':>4}  Flags")
    for r in out["runners"]:
        mv = (r.get("movement") or {}).get("direction", "-")
        vr = (r.get("value_rating") or {}).get("score")
        flags = f"🚩{len(r.get('red_flags') or [])} ✅{len(r.get('positive_signals') or [])}"
        edge = "-" if r.get("edge") is None else f"{r['edge']*100:+.1f}"
        ev = "-" if r.get("ev") is None else f"{r['ev']*100:+.1f}%"
        print(f"{r['rank']:>2} {str(r.get('number','')):>2} {(r.get('name') or '')[:18]:<18} "
              f"{_num(r.get('score_total'), '{:.0f}'):>5} {_pct(r.get('win_prob')):>6} "
              f"{_num(r.get('fair_odds')):>6} {_num(r.get('bet_price')):>6} {edge:>6} {ev:>7} "
              f"{mv:>9} {('-' if vr is None else vr):>4}  {flags}")
    print("-" * W)
    sc = sm["scenarios"]
    print("Scenarios: " + " | ".join(f"{k} {v['prob']*100:.0f}%" for k, v in sc.items())
          + f"  → most likely {sm['most_likely_scenario']}")
    s = out["shortlist"]

    def nm(x):
        return "-" if not x else f"{x['name']} (#{x['number']})"

    print(f"Top: {nm(s['top'])} | 2nd: {nm(s['second'])} | 3rd: {nm(s['third'])}")
    print(f"Best value: {nm(s['best_value'])} | Rough: {nm(s['rough_chance'])} | "
          f"Vulnerable fav: {nm(s['vulnerable_favourite']) if s['vulnerable_favourite'] else s['vulnerable_note']} | "
          f"Avoid: {nm(s['avoid_at_price'])}")
    d, c = out["decision"], out["confidence"]
    print(f"CONFIDENCE {c['score']}/10 ({c['label']}): " + "; ".join(c["reasons"]))
    line = f"DECISION: {d['decision']}"
    if d.get("selection"):
        line += (f" — {d['selection']} @ ${d.get('price')} (fair ${d.get('fair_odds')}, "
                 f"min ${d.get('min_odds')}, EV {d['ev']*100:+.0f}%, stake ${d.get('stake')})")
    print(line + f"\n  reason: {d['reason']}")
    a = out["data_audit"]["counts"]
    print(f"Data audit: verified {a['verified']} | uncertain {a['uncertain']} | unavailable {a['unavailable']}")
    ex = out.get("exotics") or {}
    if ex.get("best2_for_top4"):
        b2 = ", ".join(f"{x['name']} {x['p_top4']*100:.0f}%" for x in ex["best2_for_top4"])
        print(f"Exotics: best-2-for-top-4 {b2}", end="")
        if ex.get("trifecta"):
            t = ex["trifecta"]
            print(f" | trifecta {t['banker']['name']} / " +
                  ", ".join(m["name"] for m in t["minors"]) + f" (hit {t['hit_prob']*100:.0f}%)", end="")
        print()
    if mk.get("n_priced") == 0:
        print("\n⚠ NO ODDS on any runner — ranking done, but value/EV/stakes need prices "
              "(open, current, best, bsp). Decision = WAIT FOR MARKET.")


# ---------------------------------------------------------------------------
# guide + template
# ---------------------------------------------------------------------------

GUIDE = """\
HorseEdgeEngine v2 — one-shot agent workflow (full contract in AGENTS.md)

The user pastes a form guide. That is their ONLY action. You do everything else:

 1. READ the form guide (if it's a file: python hre.py extract <file>).
 2. RESEARCH every section of SYSTEM_PROMPT.md with your own web tools —
    Racing.com fields/stewards, TAB, Sportsbet, Betfair (BSP), Punters, official
    track & weather. Never invent; mark "Data unavailable / not verified".
 3. WRITE race.json (schema: python hre.py template) — race, earlier races today,
    every runner's profile, odds {open,current,best,bsp}, running_style,
    early_speed 1-10, 13 factor scores 0-100, flags, verified/unavailable lists.
 4. RUN:  python "<repo>/hre.py" analyze "<repo>/race.json"      (absolute paths)
    -> analysis.json: win %, fair odds, min odds, edge, EV, stakes, speed map,
       today's track pattern, confidence 1-10, value 1-10, BET/PASS decision,
       shortlist, exotics, data audit.
 5. REPORT in the FINAL OUTPUT FORMAT of SYSTEM_PROMPT.md using those numbers.

Do NOT ask the user for odds, scratchings or anything else — go and find them.
"""

TEMPLATE = {
    "_help": {
        "factors": "scores: each of " + ", ".join(FACTORS) + " is 0-100 (50 = average for this field)",
        "running_style": "LEADER | ON-PACE | MIDFIELD | BACKMARKER",
        "early_speed": "1 (very slow away) .. 10 (blistering gate speed)",
        "odds": "decimal prices: open (first price), current, best (best fixed), bsp (Betfair)",
        "records": "'starts:wins-seconds-thirds', e.g. '3:1-1-0'",
        "earlier_races_today": "results already run on this card, for live track-pattern detection",
        "data_lists": "data_verified / data_uncertain / data_unavailable feed the mandatory audit",
    },
    "race": {
        "track": "Flemington", "date": "2026-09-12", "race_no": 3, "race_name": "RMBL Rising Stars",
        "time": "13:30", "distance": 1600, "surface": "Turf", "race_class": "BM78",
        "conditions_type": "Handicap", "benchmark": 78, "prize": 80000,
        "age_restriction": None, "sex_restriction": None, "field_size": 11,
        "condition": "Soft 6", "condition_prev_day": "Good 4", "penetrometer": None,
        "rain_24h_mm": 4.0, "rain_7d_mm": 22.0, "rain_expected": False,
        "temp_c": 14, "wind_kmh": 20, "wind_dir": "NW", "weather": "Overcast",
        "rail": "Out 3m entire circuit", "rail_prev_meeting": "True",
        "scratchings": [], "late_rider_changes": [], "late_gear_changes": [],
        "notes": "",
    },
    "earlier_races_today": [
        {"race_no": 1, "distance": 1200, "winner_settled": "led", "winner_barrier": 3,
         "winner_ran": "rail", "margin": 1.2, "placegetters_settled": ["on-pace", "midfield"],
         "notes": "leaders held on"}
    ],
    "runners": [
        {
            "number": 5, "name": "EXAMPLE HORSE", "age": 4, "sex": "G", "barrier": 6,
            "weight": 58.0, "apprentice_claim": 0, "weight_last_start": 57.0,
            "rating": 80, "last_start_class": "BM70", "last_start_won": True,
            "career": {"starts": 12, "wins": 3, "places": 4, "prize": 150000},
            "jockey": "J Smith", "jockey_claim": None, "trainer": "C Waller",
            "sire": "Snitzel", "dam_sire": "Zabeel",
            "gear": "Blinkers first time", "gear_history": "raced without blinkers last 6",
            "prep": {"run_no": 2, "days_since_last": 14, "first_up": "3:1-0-1",
                     "second_up": "3:1-1-0", "trials": "won 900m trial 2/9 easily"},
            "running_style": "ON-PACE", "early_speed": 7, "last600": 34.1,
            "odds": {"open": 6.0, "current": 4.8, "best": 5.0, "bsp": 5.2, "place": 1.9},
            "record": {"distance": "3:1-0-1", "track": "2:0-1-0", "track_distance": "1:0-0-0",
                       "firm": "0:0-0-0", "good": "8:2-3-0", "soft": "3:1-1-0",
                       "heavy": "1:0-0-0", "synthetic": "0:0-0-0"},
            "form_lines": [
                {"date": "2026-08-29", "track": "Caulfield", "dist": 1400, "going": "Good 4",
                 "class": "BM70", "finish": 1, "field": 12, "margin": 0.5, "barrier": 4,
                 "weight": 57.0, "jockey": "J Smith", "sp": 7.0, "settled": "on-pace",
                 "last600": 34.0, "tempo": "genuine", "notes": "clear run, won well"}
            ],
            "stewards": "no report", "vet": "nil",
            "scores": {f: 60 for f in FACTORS},
            "hidden_positives": [], "hidden_negatives": [], "red_flags": [],
            "positive_signals": [], "traps": [],
            "data_verified": ["form", "odds", "gear"], "data_uncertain": ["sectionals"],
            "data_unavailable": ["trial sectionals"],
            "notes": "",
        }
    ],
}


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="horse_edge", description=__doc__,
                                epilog="First time? python hre.py guide",
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", aliases=["analyse", "score"], help="run the numerical model")
    a.add_argument("race")
    a.add_argument("-o", "--output")
    a.add_argument("--bankroll", type=float, default=100.0)
    a.add_argument("--spread", type=float, default=DEFAULT_SPREAD,
                   help=f"rating->probability sharpness (1.0 = linear; default {DEFAULT_SPREAD})")
    a.set_defaults(func=cmd_analyze)

    t = sub.add_parser("template", help="write the race.json schema")
    t.add_argument("-o", "--output")
    t.set_defaults(func=cmd_template)

    e = sub.add_parser("extract", help="form guide file -> plain text")
    e.add_argument("input")
    e.add_argument("-o", "--output")
    e.set_defaults(func=cmd_extract)

    g = sub.add_parser("guide", help="print the agent workflow")
    g.set_defaults(func=cmd_guide)

    d = sub.add_parser("demo", help="analyse the bundled sample")
    d.add_argument("--bankroll", type=float, default=100.0)
    d.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    d.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
