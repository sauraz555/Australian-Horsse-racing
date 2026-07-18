# HorseEdgeEngine — Design Spec

**Date:** 2026-07-18
**Status:** Approved for planning
**Author:** Claude (with Saurav)

## 1. Purpose

An **agent-native** Australian horse-racing analysis toolkit. It ingests a form guide
(pasted text, PDF, or Excel), lets any LLM agent research missing data and apply racing
judgment, does all the deterministic betting math in Python, and produces a structured
value-betting report in a fixed output format.

It is the horse-racing sibling of the existing `GreyhoundEdgeEngine`, but with two
deliberate differences:

1. **No hardcoded LLM SDK / no API key.** The agent running it (Claude Opus, Gemini 3 Pro,
   Cursor, etc.) is the brain. The program is a set of CLI tools + persona/skill files.
   This is what "runs with any agent" means.
2. **PDF and Excel input**, not just pasted text.

The source of truth for the analysis methodology and the required output format is the
user's system prompt, stored verbatim as `SYSTEM_PROMPT.md`.

## 2. Design principles

- **Python owns arithmetic; the LLM owns judgment.** Anything that is pure, reproducible
  math lives in Python so the agent never fumbles it. Anything requiring reading form,
  weighing class, or writing prose stays with the agent.
- **Deterministic core has zero third-party dependencies.** `weights`, `pace`, `sectional`,
  `scoring`, `market` import only the standard library, so the math is verifiable via
  `smoke_test.py` with no install and no key. Only the ingest adapters need `pdfplumber` /
  `openpyxl` / `pandas`.
- **Fail loud, never invent.** Ingest flags missing fields rather than guessing. Missing
  decision-critical data is surfaced as a gap for the agent to research, per system-prompt
  rule #6.
- **Model-agnostic.** Nothing in the code references a specific model or vendor.

## 3. Workflow (the agent contract)

Described in `AGENT.md`. Five steps:

1. **Ingest** — `python -m horse_edge.cli ingest <file> [-o race.json]`
   Parses text/PDF/Excel → normalized `race.json` scaffold (race meta + one entry per
   runner with raw form fields) **plus a `data_gaps` block** listing what's missing:
   - Race-level: track condition, rail, weather, field size, distance, class.
   - Runner-level: odds, wet form, last-5, distance record, gear, jockey/trainer,
     sectionals, settling positions.

2. **Research (LLM)** — For every decision-critical gap (odds, track condition,
   scratchings, gear changes, wet form, sectionals, late market moves), the agent uses its
   own web-search/browsing tools to fill the field, recording a short source note. Fields
   that cannot be found are left `null`; the agent notes reduced confidence and Python
   reweights around them.

3. **Judge (LLM)** — Using `skills.md`, the agent fills each runner's `factor_scores`
   (SPD, PACE, SECT, CLASS, SUIT, PREP, DRAW, JT, GEAR, BREED — each 0–100 representing that
   factor's merit for this runner), assigns a running style (LEADER / ON-PACE / MIDFIELD /
   BACKMARKER), and confirms race conditions. Includes the "forgive file" review.

4. **Score** — `python -m horse_edge.cli score race.json [-o scored.json] [--bankroll 100]`
   Python computes everything deterministic (see §5) and writes `scored.json`.

5. **Report (LLM)** — The agent writes the final markdown report in the **exact**
   `<output_format>` from `SYSTEM_PROMPT.md`, using the numbers in `scored.json`.

## 4. Module layout

```
HorseEdgeEngine/
  horse_edge/
    __init__.py
    models.py          # dataclasses: RaceCard, Runner, FormLine, FactorScores,
                       #   Weights, PaceMap, Prediction, ScoredRace, DataGaps
    ingest.py          # read_text / read_pdf / read_excel -> RaceCard scaffold + gaps
    weights.py         # BASE_WEIGHTS + adjust_weights(conditions) -> normalized weights
    pace.py            # running-style helpers, Pace Pressure Index, race shape,
                       #   track-bias lookup
    sectional.py       # benchmark tables + upgrade/downgrade flags
    scoring.py         # weights x sub-scores -> total ratings -> tissue probabilities
    market.py          # implied prob, overround, de-vig, value class, EV, Quarter-Kelly
    cli.py             # subcommands: ingest, template, score, demo
    data/
      track_bias.json          # from <track_bias_database>
      sire_wet.json            # from <breeding_reference>
      sectional_benchmarks.json# from <sectional_analysis>
  AGENT.md             # persona + 5-step workflow + CLI contract (primary agent entry)
  skills.md            # factor definitions & how to assign sub-scores, forgive file,
                       #   gear, breeding, prep patterns
  SYSTEM_PROMPT.md     # the user's original prompt, verbatim = output-format source of truth
  CLAUDE.md            # one-liner: "read AGENT.md"  (Claude Code discovery)
  GEMINI.md            # one-liner: "read AGENT.md"  (Gemini CLI discovery)
  README.md            # human setup + how an agent uses it
  requirements.txt     # pdfplumber, openpyxl, pandas, (pydantic optional)
  smoke_test.py        # runs the deterministic pipeline, no third-party deps, no key
  sample_race.txt      # realistic AUS race paste
  sample_race.json     # ingest output for the sample
  sample_scored.json   # score output for the sample (worked example for the agent)
```

## 5. What Python computes (deterministic core)

**`weights.py`**
- `BASE_WEIGHTS`: the 10 factors and base weights from `<analysis_framework>`.
- `adjust_weights(conditions) -> dict`: applies every `IF` rule (track condition bands,
  tight/turning tracks, distance ≥2000m and ≤1200m, small/large fields, maiden/first-
  starters, first-up, gear changes). Adjustments clamp to each factor's documented range,
  then weights are **re-normalized to sum to 1.0** (only relative weight matters once
  ratings become probabilities).

**`pace.py`**
- Pace Pressure Index: count LEADER/ON-PACE runners in barriers 1–6 → SLOW (0–1) /
  MODERATE (2–3) / GENUINE (4+), with the running-style advantage it implies.
- Race-shape classifier (multiple leaders / single leader / no genuine leader).
- Track-bias lookup from `data/track_bias.json` (leader/on-pace/fair/run-on + rail impact).

**`sectional.py`**
- Compares a runner's last-600m to class/distance benchmarks; emits
  upgrade/downgrade/blackbook flags per the sectional rules.

**`scoring.py`**
- `total_rating(runner) = Σ (weight_f × subscore_f)` over the adjusted, normalized weights.
- `tissue_prob = total_rating**spread / Σ total_rating**spread`. **Tunable spread**
  (decided during build): `spread=1.0` reproduces the spec's literal linear
  `rating ÷ Σrating`, but that compresses fields toward 1/N and manufactures false
  longshot overlays, so the default is `spread=7.0` — scale-invariant, so tissue
  stays independent of the market (rule #8). Exposed as `--spread`. Probs sum to ~1.0.

**`market.py`**
- Implied prob `1/odds`, overround `Σ implied`, de-vigged market prob.
- Value class: STRONG OVERLAY (≥8% edge) / OVERLAY (3–8%) / FAIR (±3%) / UNDERLAY.
- `EV = model_prob × odds − 1`; recommend only if `EV ≥ +0.05`.
- Quarter-Kelly: `f* = (b·p − q)/b`, stake `= f*·0.25·bankroll`, hard-capped at 5% of
  bankroll; negative Kelly → NO BET.

## 6. What the LLM owns (judgment)

Reading the form guide; researching missing fields; assigning the 0–100 factor sub-scores;
classifying running styles; the "forgive file" assessment; gear-change and breeding reads;
and writing the final narrative report in the required output format.

## 7. Data models (shape)

- `FormLine`: date, track, dist, going, barrier, weight, jockey, finish, margin, sp,
  class, last600, notes.
- `Runner`: number, name, barrier, weight, jockey, trainer, last5, dist_record, wet_form,
  odds, gear, notes, running_style, form_lines[], `factor_scores` (10 factors),
  plus computed: total_rating, tissue_prob, ev, value_class, kelly_stake.
- `RaceCard`: track, date, race_no, distance, class, condition, rail, prize, field_size,
  weather, bias_notes, runners[], `data_gaps`.
- `ScoredRace`: RaceCard + adjusted weights used + pace map + market summary
  (overround) + per-runner predictions.

## 8. CLI

```
python -m horse_edge.cli ingest <file> [-o race.json]   # text/pdf/excel -> scaffold + gaps
python -m horse_edge.cli template [-o race.json]        # blank scaffold to fill by hand
python -m horse_edge.cli score  <race.json> [-o scored.json] [--bankroll 100]
python -m horse_edge.cli demo                            # runs bundled sample end-to-end
```

Ingest auto-detects format by extension (`.txt`/`.md` → text, `.pdf` → pdfplumber,
`.xlsx`/`.xls` → openpyxl, `.csv` → stdlib `csv`). Missing optional deps produce a
clear "pip install …" message rather than a stack trace.

**Text-ingest boundary (decided during build):** structured CSV/Excel is parsed by
header into every column; free-text pastes reliably yield only race meta +
runner number/name/odds, and always retain the full source in `raw_text` for the
agent to complete. Perfect parsing of arbitrary pipe/space form-guide tables is a
non-goal — that judgment is the agent's job (Step 2/3). `pandas` was dropped (CSV
uses the stdlib), so only `pdfplumber` and `openpyxl` are third-party.

## 9. Testing & verification

- `smoke_test.py`: loads `sample_scored`-style input through `weights → scoring → market`
  and asserts tissue probs sum to ~1.0, EV/Kelly are internally consistent, and the 5% cap
  holds. Runs with stdlib only.
- Manual: `python -m horse_edge.cli demo` produces `sample_scored.json`, hand-checked
  against the worked example.
- Ingest adapters tested against `sample_race.txt` and a small sample PDF/xlsx.

## 10. Out of scope (YAGNI)

- No live odds feeds or scraping in Python (the agent researches).
- No persistent database / performance-log storage engine — the `<iterative_learning>`
  log stays a markdown convention the agent maintains, not a Python subsystem.
- No GUI. CLI + agent only.
- No bundled LLM runner (agent-native by decision; a pluggable runner can be added later
  without touching the core).

## 11. Open questions

None blocking. Bankroll default $100 (overridable). Package name `horse_edge`, project
folder `HorseEdgeEngine` (renameable).
