# What a two-run floor is worth

*1 September 2026. PLAN2 step 27, zero GPU — computed from the two four-run sets that exist
(the control floor and the gesture ablation at n=4), by taking every 2-run subsample of the
control set and asking whether phase 1's verdicts would have survived it.*

## The size of the understatement

Across every live measure, the median 2-run floor is **about half** the 4-run floor — the ratio
sits between 0.47 and 0.79, and at 0.50–0.53 for most of the panel:

| measure | F4 (recomputed) | F2 min | F2 median | F2 max | median ÷ F4 |
|---|---:|---:|---:|---:|---:|
| `dialogue_share` | 11% | 1% | 6% | 11% | 0.51 |
| `recap_grammar` | 59% | 7% | 31% | 61% | 0.53 |
| `gesture_rate` | 22% | 0% | 12% | 23% | 0.52 |
| `somatic_share` | 19% | 4% | 13% | 19% | 0.69 |
| `refusal_rate` | 68% | 7% | 34% | 66% | 0.50 |
| `refusal_per_ask` | 52% | 12% | 26% | 51% | 0.50 |
| `repetition_concentration` | 37% | 2% | 29% | 37% | 0.79 |
| `worst_refrain` | 51% | 0% | 24% | 48% | 0.47 |

*(F4 recomputed from the prefix-trimmed set; the published `NOISE_FLOOR` values are these,
rounded up. The verdict tests below use the published floors, because those are what the verdicts
used.)*

PLAN.md recorded the direction when the floor went from n=2 to n=4 — "a range from two samples
systematically understates the spread". This is the size: **half**.

## What that does to verdicts

Both phase 1 differences recomputed from disk first, as a self-check: step 5's
`repetition_concentration` difference comes back 44.1% (published 44%), step 6's `gesture_rate`
12.6% (published 12%). The instrument reproduces its own record.

Then, for each of the 6 possible 2-run control floors:

- **Step 5 never flips** — 0 of 6. Its 44% sits far enough above every floor either n gives.
- **Step 6 flips half the time** — 3 of 6 two-run floors put the 12.6% difference *outside*,
  i.e. an n=2 screen would have reported the gesture ablation as a real effect that the n=4
  floor says is noise. That is a false claim, on the exact measure phase 1's hardest verdict
  hung on.

Across both real comparisons and every live measure — 72 verdict tests — **15 flip, and all 15
flip the same way**:

    false positives (n=2 claims, n=4 refuses):  15
    false negatives (n=2 refuses, n=4 claims):   0

Zero false negatives is not luck; it is near-structure. A pair's range is a subset of the
four-run range, so a 2-run floor can exceed the 4-run floor only through mean shifts — observed
worst case +1 point (`gesture_rate`, 23% vs 22%). A difference inside a floor that is *half* the
true one is inside the true one with room to spare.

## The protocol, which the numbers wrote

**An n=2 screen may kill and may never confirm.**

- A difference **inside** an n=2 floor may be treated as inside the n=4 floor — measured
  exception rate 0 in 72 — so a mechanism can be *dropped* after two runs, at ~2.5 GPU-h instead
  of ~5.
- A difference **outside** an n=2 floor means nothing: 21% of such clearances were noise against
  the real floor, 50% on the one that mattered. Confirmation stays at n=4, always.
- Nothing publishable ever comes from a screen. The screen decides where the next GPU-hours go,
  and that is all it decides.

One-sidedness is the property this project's history demands: every retraction it has made was a
claim that should not have been made, never a kill that should not have been. A cheap instrument
that can only stop spending — and never start believing — cannot recreate the failure mode.

## Out of sample, hours later: the rule holds, the number does not

*Added 03:16 the same night, once step 30 had written the second book's floor at n=4 — the
re-run this section was written to demand.*

On the 24-scene *Ink of the Drowned*, going from two runs to four widened the observed spread far
more than it did here:

| measure | n=2 | n=4 | ×wider |
|---|---:|---:|---:|
| `refusal_per_ask` | 3% | 40% | **13.1×** |
| `refusal_rate` | 7% | 41% | 6.1× |
| `somatic_share` | 13% | 52% | 3.9× |
| `dialogue_share` | 13% | 43% | 3.5× |
| `gesture_rate` | 10% | 23% | 2.3× |
| `recap_grammar` | 10% | 21% | 2.2× |

Median **3.7×**, against roughly **2×** measured above on the 71-scene *Debt* plan.

**So "a two-run floor is half a four-run floor" is a figure for one book, not a constant** — on a
short book it is nearer a quarter, and for one measure a thirteenth. Quoting the 2× off *The Debt
of Years* would have understated the problem by a factor of two, which is the same mistake
[step 25](fresh-premise-panel.md) caught in the floor itself.

**The protocol is unaffected, and in fact strengthened.** Both halves of *an n=2 screen may kill
and may never confirm* rest on the n=2 floor being **too narrow**, and the second book says it is
narrower still: a difference that fits inside a two-run floor fits inside the four-run floor with
even more room to spare, and a difference that clears a two-run floor is even weaker evidence than
this page's 15-of-72 false-positive rate suggested. The rule survives its first out-of-sample
test; the constant attached to it does not travel and has been removed from the recommendation.

*It cost `somatic_share` its place in `checks.PORTABLE`, which had been granted on exactly the
two-run spread this page warns about ([portable-measures.md](portable-measures.md)).*

## Limits

- The subsample analysis reuses the four control runs, so the 6 pairs are not independent — this
  prices the floor's *understatement*, not a fresh experiment.
- The out-of-sample check above is a different kind of evidence: it compares n=2 against n=4 on a
  second book directly, rather than re-running the verdict-flip analysis there. Doing *that*
  would need ablations on the second premise, which do not exist.
