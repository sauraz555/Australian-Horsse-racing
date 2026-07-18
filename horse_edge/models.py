"""Data models for HorseEdgeEngine.

Plain stdlib dataclasses (no pydantic) so the deterministic core has zero
third-party dependencies. Used mainly to build the ingest scaffold; the scoring
path operates on plain dicts loaded from JSON.
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

# The ten scoring factors, in report order. Sub-scores are 0-100 (agent-supplied).
FACTORS = ["SPD", "PACE", "SECT", "CLASS", "SUIT", "PREP", "DRAW", "JT", "GEAR", "BREED"]

RUNNING_STYLES = ["LEADER", "ON-PACE", "MIDFIELD", "BACKMARKER"]


@dataclass
class FormLine:
    """A single past-start line."""
    date: Optional[str] = None
    track: Optional[str] = None
    dist: Optional[str] = None
    going: Optional[str] = None
    barrier: Optional[str] = None
    weight: Optional[str] = None
    jockey: Optional[str] = None
    finish: Optional[str] = None
    margin: Optional[str] = None
    sp: Optional[str] = None
    race_class: Optional[str] = None
    last600: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class Runner:
    number: Optional[int] = None
    name: str = ""
    barrier: Optional[int] = None
    weight: Optional[float] = None
    jockey: Optional[str] = None
    trainer: Optional[str] = None
    sire: Optional[str] = None
    last5: Optional[str] = None
    dist_record: Optional[str] = None
    wet_form: Optional[str] = None
    odds: Optional[float] = None
    gear: Optional[str] = None
    notes: Optional[str] = None
    running_style: Optional[str] = None       # LEADER / ON-PACE / MIDFIELD / BACKMARKER
    last600: Optional[float] = None           # best/representative closing 600m (s)
    # Agent-supplied judgment (Step 3). Each 0-100; leave empty until Judge step.
    factor_scores: dict = field(default_factory=dict)
    form_lines: list = field(default_factory=list)
    flags: list = field(default_factory=list)
    # Computed by `score` (Step 4) — left null in the ingest scaffold.
    total_rating: Optional[float] = None
    tissue_prob: Optional[float] = None
    market_prob: Optional[float] = None
    devig_prob: Optional[float] = None
    edge: Optional[float] = None
    value_class: Optional[str] = None
    ev: Optional[float] = None
    kelly_fraction: Optional[float] = None
    kelly_stake: Optional[float] = None
    sectional: Optional[dict] = None


@dataclass
class RaceCard:
    track: Optional[str] = None
    date: Optional[str] = None
    race_no: Optional[int] = None
    distance: Optional[int] = None
    race_class: Optional[str] = None
    condition: Optional[str] = None
    rail: Optional[str] = None
    prize: Optional[str] = None
    field_size: Optional[int] = None
    weather: Optional[str] = None
    bias_notes: Optional[str] = None
    runners: list = field(default_factory=list)
    data_gaps: dict = field(default_factory=dict)
    raw_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def racecard_to_dict(rc: RaceCard) -> dict:
    return asdict(rc)


def _pick(cls, d: dict) -> dict:
    names = {f.name for f in dataclasses.fields(cls)}
    return {k: v for k, v in d.items() if k in names}


def runner_from_dict(d: dict) -> Runner:
    d = dict(d)
    lines = [FormLine(**_pick(FormLine, x)) for x in d.get("form_lines", []) if isinstance(x, dict)]
    r = Runner(**_pick(Runner, d))
    r.form_lines = lines
    return r


def racecard_from_dict(d: dict) -> RaceCard:
    rc = RaceCard(**_pick(RaceCard, d))
    rc.runners = [runner_from_dict(x) for x in d.get("runners", []) if isinstance(x, dict)]
    return rc


# ---------------------------------------------------------------------------
# Small parsing helpers (shared by ingest / cli)
# ---------------------------------------------------------------------------

def to_int(v) -> Optional[int]:
    if v is None:
        return None
    m = re.search(r"-?\d+", str(v))
    return int(m.group()) if m else None


def to_float(v) -> Optional[float]:
    if v is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", str(v))
    return float(m.group()) if m else None
