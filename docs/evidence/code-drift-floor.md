# How much does the panel move when only the code changes?

*2 September 2026, while phase 8 ran. Zero GPU — four 71-scene books that already existed turned
out to share the corpus plan byte-for-byte while having been written at four different code
revisions. Nobody had compared them.*

The frozen-writer discipline — `scripts/same_code.py`, the guards in `phase1.sh` and `phase8.sh`,
PLAN2's "one hard ordering" — all rest on an assumption that has never been measured: that
changing the code between a control and a condition moves the panel enough to matter. Here is the
measurement.

## The groups

`runs/current`, `runs/replicate`, `runs/ledgerfix` and `runs/tally6` hold **the same plan** as the
four floor runs (verified field-by-field, ignoring `depends_on`, which is a serialisation
difference that reaches neither `brief.py` nor `pipeline.py`), and all four wrote all 71 scenes.
They were written at four different revisions. The floor set was written at one.

- **NEW** = four runs, one plan, **one** revision → spread is pure sampling noise. This is the
  published `NOISE_FLOOR`.
- **OLD** = four runs, same plan, **four** revisions → spread is sampling noise *plus* code drift.

## The result

| measure | new spread | old spread | ratio | new mean | old mean | gap | gap clears floor? |
|---|---:|---:|---:|---:|---:|---:|---|
| `words` | 2% | 2% | 1.3 | 61207 | 60065 | 2% | no |
| `dialogue_share` | 11% | 10% | 0.9 | .202 | .212 | 5% | no |
| `duplication_manuscript` | 18% | 17% | 1.0 | .052 | .061 | 17% | no |
| `recap_grammar` | 59% | 32% | 0.5 | .035 | .040 | 13% | no |
| `gesture_rate` | 22% | 31% | 1.4 | 1.883 | 2.020 | 7% | no |
| **`somatic_share`** | 19% | **95%** | **5.0** | .373 | .401 | 7% | no |
| `repetition_concentration` | 37% | 27% | 0.7 | .030 | .029 | 1% | no |
| `worst_refrain` | 51% | 74% | 1.5 | 9.75 | 10.75 | 10% | no |
| `refusal_rate` | 68% | 21% | 0.3 | .763 | .777 | 2% | no |
| `refusal_per_ask` | 52% | 12% | 0.2 | .644 | .565 | 13% | no |

**Not one measure's era gap clears its own sampling floor.** At the mean, four revisions of drift
are indistinguishable from four draws of one revision.

## What this does and does not license

**It does not say the freeze is unnecessary.** Three reasons, and the third is the one that
matters:

1. All four OLD runs are *current-era* by [MEASUREMENTS.md](../MEASUREMENTS.md)'s own definition —
   post-sampler-fix. This measures drift **within** one era, not across the boundary that
   separates it from the era before it, where the same panel moved by orders of magnitude
   (per-scene duplication .319 → .001). Code changes demonstrably *can* move these measures. These
   particular ones did not.
2. n=4 against n=4 with floors this wide has little power to detect a modest shift.
3. **`somatic_share`'s spread is five times wider across revisions than within one** — 95% against
   19%. Its *mean* barely moves, so the table above says "no", but the measure has become
   unusable in the OLD group: a 95% floor cannot support any claim. **The freeze protects variance,
   not only means, and a comparison that checked only means would have missed this entirely.**
   `gesture_rate` (1.4×) and `worst_refrain` (1.5×) point the same way more quietly.

**What it does license** is a modest, tested statement: the reporting-level and
measurement-level changes made across these four revisions did not move the panel's *central
values* beyond sampling noise. That is mild reassurance that phase 1's verdicts were not fragile
to the exact revision they were pinned at — which is worth knowing, because the guard refused
three times during phase 1 and each refusal cost GPU-hours to satisfy.

**What it tempts and should not.** If code drift sits inside sampling noise, the four OLD runs
could join the floor group and take the *Debt* floor from n=4 to n=8, tightening every measure.
That is exactly the pooling [step 26](portable-measures.md) refused to do across eras, and
`somatic_share` is the reason to keep refusing: pooling groups with 19% and 95% spreads produces a
floor that describes neither. If this is ever attempted it needs its own pre-registration and a
per-measure test, not a blanket decision.

## The cheapest finding here

Four books, 244,000 words, written months apart at four revisions, sat in `runs/` for the whole
project answering a question nobody asked them. The plan-identity check that surfaced them cost
one comparison — and it was run for an unrelated reason, to confirm phase 1's conditions shared a
plan. **A corpus that is kept becomes an instrument; this one keeps proving it, and the recurring
cost of not asking is GPU-hours spent re-measuring what is already on disk.**
