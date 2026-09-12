# HorseEdgeEngine v2 — Scoring Skills (Australian)

How to turn your research into the 13 factor sub-scores (0–100) and the speed-map
inputs. **50 = an average runner in THIS field**; 80+ = clear edge; <40 = clear
negative. Spread the scores — the probability model is only as sharp as they are.
Score from the handicapping, **never from the price** (MARKET is the only factor
that may look at odds, and it is excluded from the win probability).

## The 13 factors

**FORM (15)** — the last 5–10 starts read *with the trip*, not the finishing
position. A 6th three-wide without cover in a genuine tempo can rate above a 2nd
that had the box seat behind a crawl. Weight recent, relevant (same going/trip)
runs highest. Forgive runs go up; flattered runs come down.

**CLASS (10)** — benchmark/grade today vs the horse's rating and its recent grades
(the model flags UP / DOWN / SAME from `last_start_class`). Form-line strength:
did the winner and placegetters from its last race go on with it? Low-grade
(maiden, BM58–64) is volatile and small edges mean little; high-grade (BM84+,
Listed, Group) is decided on genuine class.

**DIST (10)** — record at today's trip and ±200 m, sectional profile, pedigree.
Ideal 80+, suitable 60–75, slight concern 45–55, major concern <40.

**TRACK (10; auto-lifted to ~15 Soft / ~22 Heavy)** — course, course-and-distance
and, above all, **today's going**. On Soft 5+ a horse with no wet form is a clear
negative; on Heavy 8+ with no wet ability it is a critical negative regardless of
class. Use sire wet stats for small samples (`horse_edge/data/sire_wet.json`).

**BARRIER (7; up to 12 in sprints / tight tracks / big fields)** — the gate
*relative to style and early speed*. Inside + speed = rail run (85); inside + slow
= boxed-in risk (45); wide + speed = caught wide (45); wide + slow = forced back,
needs luck (35). The model also writes a `barrier_outcome` per runner.

**POSITION (10)** — how well the *expected settling position* suits the *expected
tempo*. In a slow/leaderless map on-pacers score 80+, backmarkers 45; in a
speed-battle map closers with the best sectionals score high. On tight tracks the
model adds +5 for LEADER/ON-PACE automatically.

**SECT (10)** — closing 600/400/200 m vs par (sprint 32.0–33.0 s, miler 33.0–34.0 s,
stayer 34.5–36.0 s on good ground, metro). Fastest-closer-that-didn't-win = up;
fast close off a crawl = discount. Enter a representative `last600` for the flag.

**JOCKEY (5)** — research the rider **for today**: current 30/90-day strike rate,
this track and distance, on this horse, hot or cold. Booking signals: top rider
on = +, stable's #1 rider elsewhere = −. **Apprentice claims**: enter the kg in
`apprentice_claim`; score the rider's ability separately (a good 3 kg claimer can
be a plus, a raw one on a hard ride a minus).

**TRAINER (5)** — strike rate, 14/30/90-day stable form, track/distance, and the
preparation pattern (first-up vs second-up vs third-up records). Hot/normal/cold —
not on one winner.

**FITNESS (5; higher for staying trips / maidens)** — run number this prep, days
since last run, records after similar breaks, trials/jump-outs (comfort under
minimal pressure, not the win). 2nd/3rd-up peak = 80+; deep into prep with a
quick backup and a rise in trip = bounce risk (45).

**WEIGHT (5)** — effective weight after claim vs rivals (`weight_vs_field`), up in
weight for winning, rivals meeting it better at the weights, rating vs benchmark.
Light and well-in = 80+; top weight up for a win against stronger opposition = 45.

**GEAR (3; 5 in maidens)** — *change* and *number of applications*: gelded since
last start (90), blinkers 3rd application (80), winkers first time (65), blinkers
first time (55 — high variance either way), tongue tie first time (40), blinkers
OFF after poor runs (40), no change (50). Verify how it went with the same gear.

**MARKET (5)** — the only price-aware factor: opening → current → best, BSP vs
bookmakers, and *why* it moved (scratching, liquidity, correction, public,
professional, stable). Late steam with a reason = 70+; big drift on no news = 35.
Not in the win probability.

## Speed-map inputs

- `running_style`: LEADER (settles 1st–2nd) · ON-PACE (3rd–5th) · MIDFIELD · BACKMARKER
- `early_speed` 1–10: gate speed and willingness to roll forward. 9–10 will lead
  regardless; 7–8 wants to be on speed; 4–6 takes a sit; 1–3 gets back.
- `earlier_races_today`: winner settled / barrier / lane for each race already run
  — this is the live track-pattern feed.

## Australian market notes

- **BSP** (Betfair Starting Price) is the sharpest single price; when it diverges
  ≥3 % from the bookmakers, trust the exchange.
- Bookmaker books run ~115–125 %; country meetings higher. Always de-vig.
- A move is only *significant* when implied probability shifts ≥5 %; late (last
  10–30 min) moves carry information, overnight moves rarely do.
- Best-odds-guaranteed / fixed early for expected steamers; BSP for expected drifters.

## Before you run `analyze`

- Every runner has all 13 `scores`, `running_style`, `early_speed`, odds (or a
  documented gap), and `data_*` lists.
- Scratched runners are marked `"scratched": true` (they're dropped, and the map
  is rebuilt without them).
- Your best horses are genuinely separated from the roughies.
- You have asked: *would I rate this horse here if I hadn't seen its price?*
