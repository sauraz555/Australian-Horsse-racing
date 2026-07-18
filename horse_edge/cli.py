"""HorseEdgeEngine command-line interface.

Subcommands:
  ingest   <file>        text/pdf/excel/csv -> race.json scaffold + data_gaps
  template [-o file]     blank race.json scaffold to fill by hand
  score    <race.json>   deterministic math -> scored.json (+ printed table)
  demo                   run the bundled sample end-to-end (no deps, no key)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

from . import ingest as ingest_mod
from .models import FACTORS, Runner, RaceCard, racecard_to_dict, to_int
from .weights import adjust_weights
from .pace import build_pace_map, is_tight
from .sectional import assess_last600
from .scoring import score_runners, DEFAULT_SPREAD
from .market import evaluate_market
from .exotics import build_exotics
from .classlevel import parse_class

_ROOT = os.path.dirname(os.path.dirname(__file__))


# ---------------------------------------------------------------------------
# Condition inference (feeds the weight engine)
# ---------------------------------------------------------------------------

def _text_has(*values) -> bool:
    return any(v for v in values)


def _detect_first_up(runners: list) -> bool:
    """Race-level: majority of the field resuming (nudges PREP weight)."""
    if not runners:
        return False
    hits = 0
    for r in runners:
        blob = " ".join(str(r.get(k) or "") for k in ("notes", "last5")).lower()
        if any(t in blob for t in ("1st up", "first up", "1st-up", "resuming", "resume", "fresh", "spell")):
            hits += 1
    return hits >= max(2, len(runners) / 2)


def _detect_gear_change(runners: list) -> bool:
    for r in runners:
        gear = str(r.get("gear") or "").upper()
        notes = str(r.get("notes") or "").lower()
        if re.search(r"\bB1\b|\bW1\b|\bTT1\b|1ST TIME|FIRST TIME", gear):
            return True
        if "gelded" in notes or "first time" in notes or "1st time" in notes:
            return True
    return False


def _conditions_from_race(rc: dict) -> dict:
    runners = rc.get("runners") or []
    track = rc.get("track")
    return {
        "track": track,
        "condition": rc.get("condition"),
        "distance": to_int(rc.get("distance")),
        "field_size": to_int(rc.get("field_size")) or len(runners),
        "race_class": rc.get("race_class"),
        "tight": is_tight(track),
        "first_starters": "maiden" in str(rc.get("race_class") or "").lower(),
        "first_up": _detect_first_up(runners),
        "gear_change": _detect_gear_change(runners),
    }


def _runner_flags(r: dict) -> list:
    flags = list(r.get("flags") or [])
    blob = " ".join(str(r.get(k) or "") for k in ("notes", "last5")).lower()
    if any(t in blob for t in ("1st up", "first up", "resuming", "fresh")):
        flags.append("FIRST-UP")
    gear = str(r.get("gear") or "").upper()
    if re.search(r"\bB1\b|1ST TIME|FIRST TIME", gear):
        flags.append("GEAR: blinkers first time")
    if "gelded" in blob:
        flags.append("GEAR: recently gelded")
    # de-dup, keep order
    seen = set()
    out = []
    for f in flags:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_ingest(args) -> None:
    rc = ingest_mod.read_any(args.input)
    d = racecard_to_dict(rc)
    dest = args.output or _default_out(args.input, "_race.json")
    _write_json(dest, d)
    print(f"Ingested {args.input} -> {dest}")
    print(f"Runners detected: {len(d.get('runners') or [])}")
    gaps = d.get("data_gaps", {})
    if gaps.get("race"):
        print("Race-level gaps:", ", ".join(gaps["race"]))
    rg = gaps.get("runners") or {}
    if rg:
        print("Runner-level gaps (research/fill before scoring):")
        for name, miss in rg.items():
            print(f"  {name}: {', '.join(miss)}")
    if gaps.get("hint"):
        print("Hint:", gaps["hint"])
    print("\nNext: research the gaps, fill factor_scores (0-100) + running_style, "
          "then `score`.")


def cmd_template(args) -> None:
    example = Runner(
        number=1, name="EXAMPLE HORSE", barrier=4, weight=58.0,
        jockey="J Smith", trainer="C Waller", sire="Snitzel",
        last5="21x34", dist_record="3:1-1-0", wet_form="2:0-1-0",
        odds=4.50, gear="B3, TT", notes="2nd up; class drop",
        running_style="ON-PACE", last600=33.4,
        factor_scores={f: None for f in FACTORS},
    )
    rc = RaceCard(
        track="Randwick", date="2026-07-18", race_no=1, distance=1400,
        race_class="BM78", condition="Good 4", rail="True", prize="$150,000",
        field_size=1, weather="Fine", bias_notes="", runners=[example],
    )
    d = racecard_to_dict(rc)
    d["_help"] = {
        "factor_scores": "Each factor 0-100 = that runner's merit. Keys: " + ", ".join(FACTORS),
        "running_style": "One of LEADER / ON-PACE / MIDFIELD / BACKMARKER",
        "workflow": "Fill one entry per runner, then: score this file.",
    }
    dest = args.output or "race_template.json"
    _write_json(dest, d)
    print(f"Template written -> {dest}")


def cmd_score(args) -> None:
    with open(args.race, encoding="utf-8") as f:
        rc = json.load(f)
    runners = rc.get("runners") or []
    if not runners:
        sys.exit("ERROR: no runners in the file. Ingest/fill runners first.")

    missing = [r.get("name") or f"#{r.get('number')}" for r in runners if not r.get("factor_scores")]
    if missing:
        sys.exit("ERROR: these runners have no factor_scores (do Step 3 'Judge' first): "
                 + ", ".join(missing))

    conditions = _conditions_from_race(rc)
    weights, notes, modifiers = adjust_weights(conditions)

    for r in runners:
        r["flags"] = _runner_flags(r)
        if r.get("last600") is not None:
            r["sectional"] = assess_last600(float(r["last600"]), conditions["distance"])

    pace_map = build_pace_map(runners, conditions["track"])
    score_runners(runners, weights, modifiers.get("on_pace_pace_bonus", 0.0),
                  spread=args.spread)
    summ = evaluate_market(runners, bankroll=args.bankroll)
    grade = parse_class(rc.get("race_class"))
    exotics = build_exotics(runners, bankroll=args.bankroll)  # also attaches p_top4 etc.

    runners.sort(key=lambda r: (r.get("tissue_prob") or 0), reverse=True)
    out = {
        "race": {k: v for k, v in rc.items() if k not in ("runners", "raw_text", "data_gaps")},
        "conditions": conditions,
        "race_grade": grade,
        "adjusted_weights_pct": {k: round(v * 100, 1) for k, v in weights.items()},
        "weight_notes": notes,
        "pace_map": pace_map,
        "market_summary": summ,
        "bankroll": args.bankroll,
        "spread": args.spread,
        "exotics": exotics,
        "runners": runners,
    }
    dest = args.output or _default_out(args.race, "_scored.json", strip="_race")
    _write_json(dest, out)
    _print_summary(out)
    print(f"\nWrote {dest}")


def cmd_demo(args) -> None:
    sample = os.path.join(_ROOT, "sample_race.json")
    if not os.path.exists(sample):
        sys.exit(f"Sample not found: {sample}")
    ns = argparse.Namespace(
        race=sample,
        bankroll=args.bankroll,
        spread=args.spread,
        output=os.path.join(_ROOT, "sample_scored.json"),
    )
    cmd_score(ns)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _sel(sel: dict) -> str:
    return f"{sel.get('name') or ''} (#{sel.get('number')})"


def _print_summary(out: dict) -> None:
    race = out["race"]
    grade = out.get("race_grade") or {}
    print("\n" + "=" * 76)
    print(f"{race.get('track','?')}  R{race.get('race_no','?')}  "
          f"{race.get('distance','?')}m  {race.get('race_class','')}  "
          f"[{race.get('condition','?')} | rail {race.get('rail','?')}]")
    if grade.get("band") and grade["band"] != "unknown":
        print(f"Grade: {grade.get('matched')} ({grade['band'].upper()}-grade)")
    pm = out["pace_map"]
    print(f"Pace: PPI {pm['ppi']['ppi']} ({pm['ppi']['tempo']}) — favours {pm['ppi']['favours']}")
    print(f"Shape: {pm['shape']}")
    mkt = out["market_summary"]
    if mkt.get("overround_pct"):
        print(f"Market overround: {mkt['overround_pct']}%  ({mkt['n_priced']}/{mkt['n_runners']} priced)")
    print("-" * 76)
    print(f"{'#':>2} {'Runner':<18} {'Tissue':>7} {'Top4':>6} {'Mkt':>6} {'Edge':>6} "
          f"{'EV':>7} {'Stake':>7}  Value")
    for r in out["runners"]:
        tissue = f"{r['tissue_prob']*100:.1f}%" if r.get("tissue_prob") is not None else "  -"
        top4 = f"{r['p_top4']*100:.0f}%" if r.get("p_top4") is not None else "  -"
        mktp = f"{r['devig_prob']*100:.1f}%" if r.get("devig_prob") is not None else "  -"
        edge = f"{r['edge']*100:+.1f}" if r.get("edge") is not None else "  -"
        ev = f"{r['ev']*100:+.1f}%" if r.get("ev") is not None else "   -"
        stake = f"${r['kelly_stake']:.2f}" if r.get("kelly_stake") else "   -"
        vc = r.get("value_class", "")
        print(f"{str(r.get('number','')):>2} {(r.get('name') or '')[:18]:<18} "
              f"{tissue:>7} {top4:>6} {mktp:>6} {edge:>6} {ev:>7} {stake:>7}  {vc}")
    _print_exotics(out.get("exotics") or {})


def _print_exotics(ex: dict) -> None:
    if not ex or ex.get("best2_for_top4") is None:
        return
    print("-" * 76)
    print(f"EXOTICS (model, {ex.get('sims','?')} sims — from ratings, not odds)")
    b2 = ex.get("best2_for_top4") or []
    if b2:
        print("  Best 2 for Top 4: " +
              ", ".join(f"{_sel(s)} {s['p_top4']*100:.0f}%" for s in b2))
    q = ex.get("quinella")
    if q:
        print(f"  Quinella: {' / '.join(_sel(s) for s in q['selections'])} "
              f"— hit {q['hit_prob']*100:.0f}%")
    tri = ex.get("trifecta")
    if tri:
        print(f"  Trifecta [{tri['confidence']}]: {_sel(tri['banker'])} / "
              f"{', '.join(_sel(s) for s in tri['minors'])}  "
              f"({tri['combos']} combos, hit {tri['hit_prob']*100:.0f}%, "
              f"flexi ${tri['suggested_flexi_outlay']:.2f})")
    ff = ex.get("first_four")
    if ff:
        print(f"  First Four [{ff['confidence']}]: {_sel(ff['banker'])} / "
              f"{', '.join(_sel(s) for s in ff['minors'])}  "
              f"({ff['combos']} combos, hit {ff['hit_prob']*100:.0f}%, "
              f"flexi ${ff['suggested_flexi_outlay']:.2f})")


def _write_json(dest: str, data: dict) -> None:
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _default_out(inp: str, suffix: str, strip: str = "") -> str:
    base, _ext = os.path.splitext(inp)
    if strip and base.endswith(strip):
        base = base[: -len(strip)]
    return base + suffix


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="horse_edge", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    pi = sub.add_parser("ingest", help="parse text/pdf/excel/csv -> race.json scaffold")
    pi.add_argument("input")
    pi.add_argument("-o", "--output")
    pi.set_defaults(func=cmd_ingest)

    pt = sub.add_parser("template", help="write a blank race.json scaffold")
    pt.add_argument("-o", "--output")
    pt.set_defaults(func=cmd_template)

    ps = sub.add_parser("score", help="deterministic math -> scored.json")
    ps.add_argument("race")
    ps.add_argument("-o", "--output")
    ps.add_argument("--bankroll", type=float, default=100.0)
    ps.add_argument("--spread", type=float, default=DEFAULT_SPREAD,
                    help="rating->probability sharpness (1.0 = linear spec; "
                         f"default {DEFAULT_SPREAD})")
    ps.set_defaults(func=cmd_score)

    pd = sub.add_parser("demo", help="run the bundled sample end-to-end")
    pd.add_argument("--bankroll", type=float, default=100.0)
    pd.add_argument("--spread", type=float, default=DEFAULT_SPREAD)
    pd.set_defaults(func=cmd_demo)
    return p


def main(argv=None) -> None:
    try:  # keep emoji value-flags from crashing cp1252 (Windows) consoles
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
