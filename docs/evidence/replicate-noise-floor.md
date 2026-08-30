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
