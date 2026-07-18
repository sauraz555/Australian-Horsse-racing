# HorseEdgeEngine

Agent-native toolkit for value-betting analysis of Australian horse races. Paste a
form guide (text, PDF, or Excel); an LLM agent researches gaps and applies racing
judgment while deterministic Python does all the betting math and produces a
structured, value-based report.

Sibling of the Greyhound Edge Engine, but **model-agnostic**: no API key, no
hardcoded LLM SDK. Whatever agent runs it (Claude Opus, Gemini Pro, Cursor, …) is
the brain; the CLI is the calculator.

## Setup

The math core needs **nothing** beyond Python 3.9+. Install extras only for the
input formats you'll use:

```bash
pip install -r requirements.txt      # pdfplumber (PDF) + openpyxl (Excel)
# text/CSV pastes use the standard library only.
```

## Quick check (no key, no extras)

```bash
python smoke_test.py                  # verifies the deterministic math
python -m horse_edge.cli demo         # scores the bundled sample end-to-end
```

## How an agent uses it (5 steps)

1. **Ingest** — `python -m horse_edge.cli ingest <file> -o race.json`
   Parses text/PDF/Excel/CSV → `race.json` scaffold + a `data_gaps` report.
2. **Research** — the agent fills decision-critical gaps (odds, condition,
   scratchings, gear, wet form, sectionals) with its own web tools.
3. **Judge** — the agent sets each runner's `factor_scores` (0–100) and
   `running_style`.
4. **Score** — `python -m horse_edge.cli score race.json -o scored.json`
   Deterministic weights, pace map, sectionals, tissue, de-vig, EV, Quarter-Kelly.
5. **Report** — the agent writes the final markdown in the required output format.

Full contract: **[AGENTS.md](AGENTS.md)**. Heuristics: **[skills.md](skills.md)**.
Methodology + output format (verbatim): **[SYSTEM_PROMPT.md](SYSTEM_PROMPT.md)**.

**Works with any agent CLI.** `AGENTS.md` is the cross-tool standard (Google
Antigravity, Cursor, Windsurf, Codex, …); `GEMINI.md` covers Gemini CLI and
Antigravity; `CLAUDE.md` covers Claude Code. All three point at `AGENTS.md`, so
opening your agent inside this folder is enough — it auto-loads the contract. Any
agent can also just run `python -m horse_edge.cli guide`.

## CLI

```
python -m horse_edge.cli ingest <file> [-o race.json]
python -m horse_edge.cli template [-o race.json]
python -m horse_edge.cli score  <race.json> [-o scored.json] [--bankroll 100] [--spread 7.0]
python -m horse_edge.cli demo
```

`--spread` sets tissue sharpness: `1.0` reproduces the literal `rating ÷ Σrating`
spec (compresses fields, avoid); default `7.0` gives realistic favourite
probabilities and stays independent of the market.

## Layout

```
horse_edge/
  models.py      ingest.py     weights.py    pace.py
  sectional.py   scoring.py    market.py     cli.py
  data/          track_bias.json  sire_wet.json  sectional_benchmarks.json
AGENTS.md  skills.md  SYSTEM_PROMPT.md  CLAUDE.md  GEMINI.md
sample_race.txt  sample_race.json  sample_scored.json  smoke_test.py
```

## Guardrails (never overridden)

- No negative-EV bets. No overlay → skip the race.
- Quarter-Kelly, 5% single-bet cap.
- Tissue is built independently of the market, then compared.
- Missing data is surfaced and reweighted, never invented.

Analysis is informational, for a legal-age audience, and not financial advice.
