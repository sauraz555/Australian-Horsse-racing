# HorseEdgeEngine v2

Agent-native research & value model for Australian horse racing (Racing.com /
TAB / Sportsbet / Betfair). **You paste a form guide; the agent does the rest** —
researches every runner with its own web tools, fills one `race.json`, runs one
command for the numerical model, and writes the full report.

No API key. No hardcoded LLM. Works under **Gemini CLI**, **Google Antigravity**,
**Claude Code**, Cursor, or any agent that can run a shell command.

## Use it

Open your agent inside this folder (it auto-loads `AGENTS.md` / `GEMINI.md` /
`CLAUDE.md`) and paste a form guide. That's it.

```
python hre.py guide      # the agent workflow
python hre.py demo       # analyse the bundled sample, no deps
python smoke_test.py     # verify the numerical model
```

## What the model computes (`python hre.py analyze race.json`)

- **13-factor score /100** with race-type re-weighting (sprint / staying / wet /
  tight track / field size / maiden)
- **Independent win probability** (market factor excluded) → **fair odds** →
  **minimum acceptable odds**
- **Market layer:** opening → current → best fixed → **BSP**; overround & de-vig;
  **SP movement** (steam / support / drift) by implied-probability shift; Betfair
  divergence; edge; EV; Quarter-Kelly stake (5 % cap)
- **Apprentice claims & benchmark ratings:** effective weight, weight swings,
  rating vs benchmark, class moves
- **Map-based speed profiling:** early-speed rating → predicted first-600 m order,
  Pace Pressure Index, tempo, barrier outcomes, 3 scenarios with probabilities
- **Track-pattern detection** from earlier races on today's card, kept separate
  from historical bias
- **Confidence 1–10** and **Value 1–10**, **BET / SMALL BET / WAIT / PASS**
- Shortlist (top, value, rough, vulnerable favourite, avoid), automatic trap and
  flag detection, exotics (Plackett-Luce), mandatory data-quality audit

## Files

```
hre.py                 single entry point (absolute-path safe for agent sandboxes)
horse_edge/
  model.py             13-factor model, probability, confidence, value, decision
  market.py            implied/overround/de-vig, SP moves, BSP, EV, Kelly
  speedmap.py          early speed → running order, tempo, scenarios
  pattern.py           today's track pattern from earlier races
  handicap.py          apprentice claims, weight swings, benchmark
  weights.py  classlevel.py  sectional.py  exotics.py  tracks.py  extract.py  cli.py
  data/                track_bias.json  sire_wet.json  sectional_benchmarks.json
AGENTS.md              the agent contract (Antigravity, Cursor, Codex …)
GEMINI.md  CLAUDE.md   tool-specific pointers (Gemini CLI / Claude Code)
SYSTEM_PROMPT.md       the master Australian research prompt + output format
skills.md              how to score the 13 factors
sample_race.json       worked example  ·  smoke_test.py
```

Optional: `pip install pdfplumber openpyxl` to `extract` PDF / Excel form guides.

Informational only; not financial advice; 18+.
