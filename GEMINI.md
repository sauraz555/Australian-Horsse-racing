# HorseEdgeEngine — Gemini CLI / Antigravity

Read **[AGENTS.md](AGENTS.md)** first and follow it exactly. It is the full
contract; `SYSTEM_PROMPT.md` is the analysis method and output format;
`skills.md` explains how to score the 13 factors.

**The user's only action is pasting a form guide. You do everything else.**

Gemini-specific notes:
- Use your **Google Search grounding / web fetch** tools for every research step —
  stewards' reports, Racing.com fields and gear, track & rail, BoM weather,
  Betfair BSP, TAB/Sportsbet prices, sectionals. Never ask the user for them.
- Use `run_shell_command` with **absolute paths** for the toolkit:
  `python "C:\...\HorseEdgeEngine\hre.py" analyze "C:\...\HorseEdgeEngine\race.json"`
  (`hre.py` self-locates the package, so the working directory doesn't matter).
- Write `race.json` with your file-write tool (schema: `python hre.py template`),
  then run `analyze`, then write the report from `analysis.json`.
- If a form guide is a PDF/Excel: `python hre.py extract <file>` first.
- Never invent odds, sectionals or gear. Mark gaps `Data unavailable / not verified`.
