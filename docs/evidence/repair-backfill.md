# What the corpus can already say about repair — and what it cannot

*2 September 2026. PLAN2 step 31, the backfill half — the part that needs no code change and no
GPU. It produces step 32's control distribution, and it specifies what the instrumentation must
record, because the corpus turns out to be one subtraction short of answering.*

## The one field on disk, and what it actually counts

Each committed scene record stores `attempts` ([project.py](../../redthread/project.py)), and
`pipeline.py` sets it as:

    scene.attempts = result.candidates_drafted + result.repairs

**It is a sum, and only the sum is persisted.** `candidates_drafted` and `repairs` are both
discarded at save time. That single fact is the whole limit of this backfill.

## The distribution, over 1,304 scene records

    attempts   scenes    share    cumulative
       2           25     1.9%       1.9%
       3          898    68.9%      70.8%
       4          269    20.6%      91.4%
       5           93     7.1%      98.5%
       6           17     1.3%      99.8%
       7            1     0.1%      99.9%
       9            1     0.1%     100.0%

    mean 3.377   median 3   max 9

And the four floor runs alone — the control step 32 will be measured against, all written at
`--candidates 3`:

    attempts   scenes    share
       3          206    72.5%
       4           58    20.4%
       5           19     6.7%
       6            1     0.4%

    n = 284   mean 3.349   median 3   max 6

## Reading it correctly, which the first reading did not

The naive line — *"scenes needing more than one attempt: 1,304 of 1,304 (100%)"* — is true and
meaningless. `attempts` starts at the candidate count, so every scene has at least two by
construction. The number says nothing about repair.

Subtracting the candidate count instead, for runs written at the default `--candidates 3`:

| repairs | floor runs | share |
|---:|---:|---:|
| 0 | 206 | **72.5%** |
| 1 | 58 | 20.4% |
| 2 | 19 | 6.7% |
| 3 | 1 | 0.4% |

**About 72% of scenes commit with no repair at all, and 7% need two or more.** The repair ladder
is exercised on roughly one scene in four.

That subtraction is an *inference*, not a measurement. It assumes `candidates_drafted` was
exactly 3 on every scene — which is the flag's default and what `phase1.sh` runs, but the 25
records at `attempts = 2` prove the assumption is not universal: something drafted fewer than
three candidates there, and no field on disk says whether that was a short draft loop or an early
commit.

## What step 31 must therefore record

The backfill's real deliverable is a specification, and it is sharper than "record which rungs
fire":

1. **`candidates_drafted` and `repairs` as separate persisted fields.** Their sum is the one
   number kept today, and it is the one number that cannot be interpreted. This is the smallest
   change with the largest return.
2. **Which repair kinds were attempted, per scene**, and which converged — the rung-level question
   PLAN.md left open.
3. **The terminal state**: committed, or halted on which violation after how many attempts.

## What this does to step 32's pre-registered statistic

PLAN2 named "attempts-to-commit distribution per scene (Mann–Whitney)". That statistic is
**still correct but was described imprecisely**, and the description is now fixed rather than the
statistic swapped after seeing data:

- The comparison remains attempts-to-commit, per scene, Mann–Whitney against the four floor runs'
  distribution above (n = 284). Attempts are per-scene and independent, so a distribution over
  scenes is the right instrument (rule VII typed).
- **Its resolution is the tail, not the bulk.** 72.5% of the control sits on a single value, so
  the test is powered by the ~27% of scenes that repair at all. An intervention that halves
  repairs moves 78 scenes of 284 — detectable — while one that only speeds up already-clean
  scenes moves nothing this statistic can see. Stated now so that a null result is read as
  "no effect on the repairing quarter" rather than "no effect".
- Because both eras are compared on the *sum*, this comparison stays valid across the
  instrumentation change. The new fields give a second, finer comparison that has no pre-31
  control — those two are never mixed, as PLAN2 already requires.

## The pattern

The panel has an eleven-measure instrument for prose and, for the machinery that decides whether
prose is committed at all, one integer that adds two unrelated quantities together. Repair is the
mechanism this project's halts are blamed on, and it has been observed only through a sum whose
larger term is a constant set by a command-line flag.
