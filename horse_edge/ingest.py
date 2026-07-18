"""Input adapters: turn a pasted text / PDF / Excel / CSV form guide into a
`RaceCard` scaffold plus a `data_gaps` report for the agent to research and fill.

Structured inputs (CSV/Excel) are parsed reliably by header. Free-text pastes get
labeled-field extraction plus a best-effort runner-line pass; the full source is
always kept in `raw_text` so the agent can recover any detail deterministic
parsing misses.
"""
from __future__ import annotations

import csv
import os
import re

from .models import RaceCard, Runner, racecard_to_dict, to_int, to_float

# Fields the agent should research if missing before scoring.
CRITICAL_RACE = ["condition", "rail", "field_size", "distance", "race_class"]
CRITICAL_RUNNER = ["odds", "wet_form", "last5", "gear", "jockey", "trainer", "dist_record"]

_HEADER_MAP = {
    "number": ["number", "no", "no.", "#", "tab", "runner no", "runner"],
    "name": ["name", "horse", "horse name"],
    "barrier": ["barrier", "gate", "draw", "bar"],
    "weight": ["weight", "wt", "wgt", "kg"],
    "jockey": ["jockey", "rider"],
    "trainer": ["trainer"],
    "last5": ["last5", "last 5", "form", "recent form"],
    "dist_record": ["dist record", "distance record", "dist rec"],
    "wet_form": ["wet form", "wet", "wet record"],
    "odds": ["odds", "price", "sp"],
    "gear": ["gear", "equipment"],
    "notes": ["notes", "comment", "comments"],
    "running_style": ["style", "run style", "running style", "map"],
    "sire": ["sire"],
}


# ---------------------------------------------------------------------------
# Format dispatch
# ---------------------------------------------------------------------------

def read_any(path: str) -> RaceCard:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _from_text(_read_pdf(path))
    if ext == ".csv":
        return _from_rows(_read_csv(path))
    if ext in (".xlsx", ".xlsm", ".xls"):
        return _from_rows(_read_xlsx(path))
    # .txt, .md, or anything else -> treat as text
    return _from_text(_read_text_file(path))


def _read_text_file(path: str) -> str:
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _read_pdf(path: str) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise SystemExit("PDF ingest needs pdfplumber. Run: pip install pdfplumber")
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _read_csv(path: str) -> list:
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return [row for row in csv.reader(f)]


def _read_xlsx(path: str) -> list:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("Excel ingest needs openpyxl. Run: pip install openpyxl")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        rows.append(["" if c is None else str(c) for c in row])
    return rows


# ---------------------------------------------------------------------------
# Free-text parsing
# ---------------------------------------------------------------------------

def _grab(pattern: str, text: str):
    m = re.search(rf"(?:{pattern})\s*[:\-]\s*([^\n|]+)", text, re.I)
    return m.group(1).strip() if m else None


def _from_text(text: str) -> RaceCard:
    rc = RaceCard(raw_text=text)
    rc.track = _grab(r"track", text)
    rc.date = _grab(r"date", text)
    rc.race_no = to_int(_grab(r"race\s*(?:no|number|#)?", text))
    rc.distance = to_int(_grab(r"distance", text))
    rc.race_class = _grab(r"class", text)
    rc.condition = _grab(r"condition|going", text)
    rc.rail = _grab(r"rail", text)
    rc.prize = _grab(r"prize", text)
    rc.field_size = to_int(_grab(r"field\s*size", text))
    rc.weather = _grab(r"weather", text)
    rc.bias_notes = _grab(r"bias", text)
    rc.runners = _parse_runner_lines(text)
    if rc.field_size is None and rc.runners:
        rc.field_size = len(rc.runners)
    _attach_gaps(rc)
    return rc


_META_PREFIXES = ("details", "runners", "additional", "pace", "race", "track",
                  "class", "distance", "condition", "rail", "prize", "weather",
                  "field", "bias", "scratch")


def _parse_runner_lines(text: str) -> list:
    """Best-effort: a runner line starts with a small number then a capitalised name."""
    runners = []
    seen = set()
    for line in text.splitlines():
        m = re.match(r"^\s*(\d{1,2})[\.\)]?\s+([A-Z][A-Za-z0-9 '’\-\.]{2,30})", line)
        if not m:
            continue
        num = int(m.group(1))
        name = m.group(2).strip()
        if name.lower().startswith(_META_PREFIXES):
            continue
        if num in seen:
            continue
        seen.add(num)
        odds = None
        mo = re.search(r"\$\s?(\d+(?:\.\d+)?)", line)
        if mo:
            odds = float(mo.group(1))
        runners.append(Runner(number=num, name=name, odds=odds))
    return runners


# ---------------------------------------------------------------------------
# Structured (CSV / Excel) parsing
# ---------------------------------------------------------------------------

def _norm(h: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", str(h).strip().lower())


def _from_rows(rows: list) -> RaceCard:
    rc = RaceCard()
    rows = [r for r in rows if any(str(c).strip() for c in r)]
    if not rows:
        _attach_gaps(rc)
        return rc

    header = [_norm(c) for c in rows[0]]
    col = {}
    for field, alts in _HEADER_MAP.items():
        wanted = {_norm(a) for a in alts}
        for i, h in enumerate(header):
            if h in wanted:
                col[field] = i
                break

    runners = []
    for row in rows[1:]:
        def get(f):
            i = col.get(f)
            if i is None or i >= len(row):
                return None
            v = str(row[i]).strip()
            return v or None

        r = Runner(
            number=to_int(get("number")),
            name=get("name") or "",
            barrier=to_int(get("barrier")),
            weight=to_float(get("weight")),
            jockey=get("jockey"),
            trainer=get("trainer"),
            sire=get("sire"),
            last5=get("last5"),
            dist_record=get("dist_record"),
            wet_form=get("wet_form"),
            odds=to_float(get("odds")),
            gear=get("gear"),
            notes=get("notes"),
            running_style=get("running_style"),
        )
        if r.name or r.number is not None:
            runners.append(r)

    rc.runners = runners
    rc.field_size = len(runners) or None
    rc.raw_text = "\n".join(", ".join(str(c) for c in row) for row in rows)
    _attach_gaps(rc)
    return rc


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------

def _attach_gaps(rc: RaceCard) -> None:
    race_gaps = [f for f in CRITICAL_RACE if not getattr(rc, f, None)]
    runner_gaps = {}
    for r in rc.runners:
        missing = [f for f in CRITICAL_RUNNER if not getattr(r, f, None)]
        if not r.factor_scores:
            missing.append("factor_scores")
        if not r.running_style:
            missing.append("running_style")
        if missing:
            runner_gaps[r.name or f"#{r.number}"] = missing

    rc.data_gaps = {
        "race": race_gaps,
        "runners": runner_gaps,
        "note": ("Step 2 (Research): fill decision-critical gaps — odds, track "
                 "condition, scratchings, gear changes, wet form, sectionals, late "
                 "market moves — using your own web tools before scoring. Step 3 "
                 "(Judge): set factor_scores (0-100) and running_style for each "
                 "runner. Leave genuinely-unfindable fields null (rule #6)."),
    }
    if not rc.runners:
        rc.data_gaps["runners_detected"] = 0
        rc.data_gaps["hint"] = "No runners auto-detected — populate 'runners' from raw_text."


def ingest_to_dict(path: str) -> dict:
    return racecard_to_dict(read_any(path))
