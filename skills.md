# HorseEdgeEngine — Skills & Heuristics

How to assign the **0–100 factor sub-scores** and running styles in Step 3
(Judge). Python turns these into ratings, probabilities and stakes; the quality of
your sub-scores is the quality of the tissue. Score each factor as "this runner's
merit on this dimension, for THIS race" — 50 = average runner in the field, 80+ =
clear edge, <40 = clear negative. Spread your scores; don't bunch everything at
60–70 or the tissue goes flat.

**Technique-first, not odds-first.** The rating must be built from the handicapping
— speed/sectionals, pace fit, class/grade, jockey form on the day, gear and
blinkers history, preparation, track/condition suitability, breeding. Do NOT let
the market price influence a sub-score; odds only enter later, at the value
comparison. If your tissue just mirrors the odds, you have no edge.

## The 10 factors

**SPD — Weight-Adjusted Speed Rating.** Best recent times adjusted for weight
carried and the class of the race. Reward horses whose figures top the field off
today's weight. On Heavy 8+, dry-track figures are unreliable — score
conservatively (Python already cuts the SPD weight).

**PACE — Pace/Speed-Map fit.** Does the likely tempo suit this runner's style?
Cross-reference the Pace Pressure Index: in a hot tempo (PPI 4+) upgrade genuine
closers and downgrade leaders who'll be pressured; in a slow tempo upgrade
leaders/on-pace. On tight tracks Python adds +5 to LEADER/ON-PACE PACE at scoring
time — you still score the base merit.

**SECT — Sectional Time.** Reward the fastest last-600m runners, especially those
who closed hard without winning (blackbook). Use the benchmark: sprint 32.0–33.0s,
miler 33.0–34.0s, stayer 34.5–36.0s (good ground, metro). A fast close in a
slow-run race is worth less than the same close in a genuine tempo.

**CLASS — Class Assessment.** First read the **grade band** `score` reports:
- **Low-grade** (maiden, BM58–64, Class 1–3): form is volatile and class gaps are
  small. Improvement, breeding and gear/first-up angles pay; don't over-trust a
  narrow ratings edge. Well-bred or lightly-raced improvers are live.
- **Mid-grade** (BM70–78, Class 4–6): proven grade record matters — favour horses
  that have handled this level over unexposed types stepping up.
- **High-grade** (BM84+, Listed, Group): class is paramount. Only genuine class
  contenders win; mark down horses raising sharply in grade, reward proven
  class-droppers.
Then, per runner: has it competed at or above today's grade, and is it going up or
down in class today? Reward proven droppers; penalise sharp risers. In small
fields (≤8) class matters more (Python lifts the weight).

**SUIT — Track/Distance/Condition Suitability.** Course-and-distance record, and
crucially wet-track form when the going is Soft/Heavy. Rule #7 is binary: a horse
that has NEVER shown ability on Heavy, facing Heavy 9, gets a very low SUIT score
regardless of other merits. Consult `horse_edge/data/sire_wet.json` for first-time
wet runners.

**PREP — Preparation & Fitness.** Where is the horse in its campaign?
- 1st-up: lean on trainer first-up strike rate + trial quality; most horses race
  shorter fresh. Unproven-fresh runners can be value — the market overrates proven
  first-uppers.
- 2nd/3rd-up: the classic Australian "on the rise" angle — most trainers point for
  the 2nd or 3rd run. Upgrade a horse whose first-up run was a fitness builder.
- 4th+ up with no break, stepping up in trip/class: bounce risk — downgrade.

**DRAW — Barrier + Rail.** Inside barriers (1–6) are generally best; wide draws
hurt most in sprints, big fields and on tight tracks, and matter least over ≥2000m
and on heavy ground. Fold the rail position in: True = inside shortest path;
+5m or more = developing leader bias. (Python re-weights DRAW by conditions; you
score how well THIS barrier suits THIS horse's style.)

**JT — Jockey/Trainer.** Research the jockey **for today**, not from memory: their
current form and strike rate, ideally at this track and distance, and whether
they're running hot or cold right now. Booking signals matter — a top rider taking
the mount, or a stable's #1 jockey choosing a different runner, moves the score.
Fold in the trainer's strike rate and first-up/second-up pattern. A strong
in-form jockey/trainer combination is a genuine positive; a struggling apprentice
on a hard-to-win chance is a negative.

**GEAR — Gear Changes.** Number of applications matters more than on/off:
- Gelding since last start → strongest single improver → high score.
- Blinkers 1st time → high variance (can worsen). Blinkers **3rd** application →
  historically the strongest win rate → flag and reward.
- Winkers 1st time → moderate positive. Cross-over noseband → moderate.
- Tongue tie 1st time → low win rate; 2nd–10th → fine. Tongue tie is on 72% of
  runners — its mere presence is not significant, only a CHANGE is.
- Blinkers coming OFF after poor runs → often declining form → lower score.

Research the **full campaign gear history**, not just today's line: how many starts
the horse has had in blinkers, whether previous gear applications coincided with
improved or worse runs, and any recent clear-out or first-time change. The *number*
of applications and the *change* are what predict — a stable pattern is neutral.

**BREED — Breeding/Pedigree.** Weight this heavily (via a high sub-score) only for
first-starters, first-time-at-distance, or first-time-wet with no relevant form;
near-zero for horses with 10+ starts of established form. Use sire wet stats and
dam-sire average winning distance. Default: if nothing says a horse can't handle
the ground, assume it can.

## Running-style classification
From the last 3–5 settling positions, barrier and jockey style:
- **LEADER** — settles 1st–2nd.
- **ON-PACE** — settles 3rd–5th, the box-seat.
- **MIDFIELD** — middle third.
- **BACKMARKER** — rear third.
Set `running_style` on every runner — it drives the Pace Pressure Index and the
tight-track on-pace bonus.

## Forgive File (David Gately method)
Before finalising, review any horse with a poor last-start result: was it
explained by a wide barrier, unsuitable pace, track bias, interference or surface?
If yes, do **not** penalise it — fold the excuse into higher sub-scores and treat
it as a likely market overlay. Use the trip-adjustment lengths in
`<visual_assessment_cues>` when you have stewards' or in-running notes.

## Sanity checks before you score
- Did you set `factor_scores` (all 10) and `running_style` for every runner?
- Are your best horses genuinely separated from the roughies (spread the scores)?
- Did you research the decision-critical `data_gaps`, or explicitly note what
  stays unknown and why (rule #6)?
