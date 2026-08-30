# Does letting an ending see its own beginning change the book?

*30 August 2026. Same plan, same models, same settings; the ledger slice is the only variable.*

## The change

`Ledger.about` sorted facts most-recent-first and truncated at 40. On a 71-scene novel that
meant: **at scene 71, 888 facts matched the scene's subjects, 40 survived, and the oldest was
from scene 68.** The final scene of the book could see scenes 68, 69 and 70 and nothing else.

The slice is now stratified — 65% recent, the rest spread evenly across everything older — which
takes scene 71 from spanning 3 scenes to spanning 15, oldest from scene 6, at the same 40 facts
and the same brief size.

## The result

Both books completed: 71 of 71 scenes, all four threads terminal, no halt and no intervention.

| | recency-capped | stratified |
|---|---:|---:|
| duplication, per scene | .001 | **.003** |
| duplication, manuscript-wide | .055 | **.065** |
| recap grammar | .042 | .041 |
| dialogue share | .223 | .211 |
| scenes peopled but silent | 0 | 1 |
| worst phrase, in scenes of 71 | 15 | **10** |
| worst gesture, in scenes of 71 | 7 | 7 |
| gesture rate | 2.1 | **1.9** |

**A wash.** One clear gain — the worst single refrain falls from 15 scenes to 10, which is the
measure the whole refrain-feedback effort targets. Two small regressions in duplication. Dialogue
and recap unchanged within noise.

## What could not be measured

The change exists so that the ending can draw on the middle and the beginning. Nothing here
measures that, and the attempt to build something that does failed twice:

- **Share of the last third's vocabulary first seen in the first third**: 84.0% capped against
  84.6% stratified. Both high, both identical, because cast and setting vocabulary recurs no
  matter what the ledger does.
- The two earlier attempts — fact reuse and retrieval distance — are recorded in
  `docs/MEASUREMENTS.md` as having measured the cap itself rather than the book.

So the change is justified by **argument, not by outcome**: a novel whose last scene can see three
scenes of its own history is wrong in a way that does not need a metric. It is kept on that basis,
with the measured effect honestly recorded as neutral.

## One confound worth naming

`current_only` — which retires a placement a later placement replaced — landed *after* this run
started. So the stratified book was built with the wider slice **and** with superseded placements
that the wider slice deliberately reaches back for: at scene 71 of the earlier book, 12 of the 18
states in the slice were stale. That is a plausible mechanism for the small duplication increase,
since a brief carrying old locations invites prose that re-describes them.

Re-running with both changes together is the obvious next test and has not been done.

---

# Third run: both changes, and the extraction range

*Same plan again. 71 of 71 scenes, 59,140 words, all threads terminal, no halt — the fourth
consecutive full-length book to run untouched.*

| | 1. capped | 2. stratified | 3. + supersede, range |
|---|---:|---:|---:|
| duplication, per scene | .001 | .003 | **.001** |
| duplication, manuscript-wide | .055 | .065 | .066 |
| recap grammar | .042 | .041 | .044 |
| dialogue share | .223 | .211 | .211 |
| scenes peopled but silent | 0 | 1 | **0** |
| worst phrase, in scenes of 71 | 15 | 10 | **7** |
| worst gesture, in scenes of 71 | 7 | 7 | **6** |
| gesture rate | 2.1 | 1.9 | **1.7** |
| facts per scene, minimum | 5 | 5 | **8** |

Retiring superseded placements undid run 2's per-scene duplication regression exactly — .003 back
to .001 — which is the mechanism that writeup predicted: a brief carrying old locations invites
prose that re-describes them.

## The result worth having — retracted

**A replicate run has since measured the noise floor, and this section does not survive it.** Two
runs of one plan with identical code give a worst refrain of 7 and 11, and gesture rates of 1.73
and 2.36. The claimed effects below are the same size as the variation between runs that differ in
nothing at all. See [replicate-noise-floor.md](replicate-noise-floor.md).

The paragraph is kept as written, because the reasoning was sound and only the evidence was
missing, and because a retracted claim is more useful visible than deleted.

~~The worst single refrain more than halved across the three runs, 15 scenes → 10 → 7, and the
gesture rate fell every time.~~ Manuscript-wide duplication nevertheless rose, .055 → .066, and
those two facts look contradictory until the distribution is counted:

| | phrases in 3+ scenes | phrases in 8+ scenes | worst |
|---|---:|---:|---:|
| 1. capped | 188 | 3 | 15 |
| 2. stratified | 246 | 2 | 10 |
| 3. + supersede | 208 | **0** | 7 |

**No phrase appears in eight or more scenes any more**, down from three such phrases in the first
run. The repetition did not get worse; it stopped concentrating. A book with two hundred mild
echoes and no dominant one reads less repetitively than a book with a phrase in 15 of its 71
scenes, and the aggregate measure cannot tell those apart. This is the first place in the project
where `duplication_ratio` and the reading disagree, and the distribution is why.

## Still not measured, and one thing untested

The causal question — does the middle earn the ending — remains unmeasured after four attempts,
all recorded in `docs/MEASUREMENTS.md`.

And the fact cap now enforced in code (15, cutting by durability) landed *after* this run started,
so run 3 has the prompt's range but not the ceiling: it averages 17.6 facts per scene against
14.7, with the low end opened up to a minimum of 8. What a run with both looks like is untested.
