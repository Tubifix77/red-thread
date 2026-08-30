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
