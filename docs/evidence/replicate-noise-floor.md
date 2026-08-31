# What changes when nothing changes

*30 August 2026. Two runs of one plan, identical code, nothing altered between them. 71 of 71
scenes each, all threads terminal, no halt.*

This project had made comparisons for two days without ever measuring what a comparison is worth.
Every result was one run against one run. This is the missing control.

## The noise floor

| measure | run A | run B | difference | as % of mean |
|---|---:|---:|---:|---:|
| words | 59,140 | 60,097 | 957 | **2%** |
| dialogue share | .211 | .203 | .008 | **4%** |
| duplication, manuscript-wide | .066 | .058 | .007 | 12% |
| duplication, per scene | .001 | .001 | .000 | 28% |
| gesture rate | 1.73 | 2.36 | .63 | **31%** |
| recap grammar | .044 | .031 | .013 | **33%** |
| worst refrain, in scenes | 7 | 11 | 4 | **44%** |
| somatic share | 42% | 21% | 21pp | **67%** |

## What this retracts

Three claims made earlier the same day do not survive it.

**"The worst refrain fell 15 → 10 → 7 across the ledger work."** Two runs of identical code give
7 and 11. The claimed effect and the noise floor are the same size. *Not established.*

**"The gesture rate fell 2.1 → 1.9 → 1.7."** That is a 20% trend against a 31% noise floor.
*Not established.*

**"Gesture feedback delays the first repeated gesture from scene 15 to scene 37."** The replicate
first fires at scene **19**. Against 15 without the feedback, that is nothing. *Not established.*

All three were reported as results of specific code changes. They may still be real — a noise
floor does not disprove an effect, it says the measurement cannot see one that size — but nothing
measured supports them, and they were stated as though something did.

## What survives

The large ones, comfortably.

| claim | change | noise floor |
|---|---:|---:|
| dialogue, before and after the planner instruction | .077 → .223 (2.9×) | 4% |
| recap, pre-prose-work era against current | .380 → .047 (8×) | 33% |
| duplication per scene, era against era | .279 → .002 (100×) | 28% |
| scenes peopled but silent | 23 of 71 → 0 | — |

An effect an order of magnitude larger than the noise is safe. An effect the same size as the
noise is a coin. Everything reported in this project sits in one of those two groups and, until
today, nothing distinguished them.

## The rule this produces

**Two runs of one plan, or no claim.** A single-run comparison can motivate a change and cannot
confirm one. The cost is about an hour of GPU per condition, which is affordable and was simply
never spent.

And the measures divide cleanly enough to be worth remembering: **dialogue share and word count
are stable to within 4%**, duplication and recap to within a third, and anything counting a
maximum — worst refrain, worst gesture — swings by half its own value between identical runs.
Maxima are the least trustworthy statistic here and were the ones quoted most often.

---

# The floor at n=4

*1 September 2026. Four runs of the same 71-scene plan, one revision, nothing varying but the
sampling. This supersedes the two-run floor above, which is kept because what it got wrong is the
point.*

| measure | n=2 | **n=4** | |
|---|---:|---:|---|
| words | 2% | **2%** | |
| dialogue_share | 5% | **11%** | wider |
| duplication_scene | 28% | **189%** | see below |
| duplication_manuscript | 12% | **19%** | wider |
| recap_grammar | 34% | **59%** | wider |
| gesture_rate | 31% | **22%** | *tighter* |
| somatic_share | 67% | **19%** | *much tighter* |
| repetition_concentration | 28% | **38%** | wider |
| worst_refrain | 45% | **52%** | wider |
| refusal_rate | 22% | **69%** | wider |
| refusal_per_ask | 37% | **53%** | wider |

The plan predicted the direction — *"a range from two samples systematically understates the
spread"* — and understated the size. Seven of eleven live measures widened, three by more than
double.

**But two tightened sharply, and that is the part worth keeping.** `somatic_share` went from 67%
to 19% and `gesture_rate` from 31% to 22%. A range from two samples is unstable in *both*
directions: the old floor was too generous on some measures and too harsh on others, and there
was no way to tell which from inside it. Four is still not many.

## One measure has exhausted itself

`duplication_scene` reads **.0007, .0005, .0005 and .0025** across the four runs. All effectively
zero — current-era prose has almost no within-scene duplication, which is what the sampler fix
achieved. In absolute terms the variation is nothing. As a fraction of the mean it is 189%.

This is the mirror of a degenerate floor and just as misleading. A floor of 0.00 means everything
clears it; a floor above 1.00 means **nothing ever will**, so the measure quietly stops being able
to support a claim while still printing "INSIDE the floor" — which reads as though the instrument
checked something. `checks.UNINFORMATIVE_FLOOR` names it and the report says *"no test possible"*
instead.

Worth stating plainly: the measure is not broken. It succeeded. Per-scene duplication was driven
from .279 to .0005 and there is no longer anything left in it to measure.

## And a halt rate, measured rather than assumed

The set answers a question it was not built for. **Four of four runs reached 71 scenes.** The
previous attempt, before `check_thematic_gloss` stopped reading dialogue, lost two of four — at
scenes 44 and 22 — to a MAJOR whose repair could not converge.

Eight runs, two conditions, and the difference is one check no longer firing on a character's
line. That is not proof of a rate, but it is the first time "can it reach the end of a book
unattended" has had anything but an anecdote attached to it.
