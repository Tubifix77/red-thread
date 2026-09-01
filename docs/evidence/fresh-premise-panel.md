# The panel on a book it was not tuned on

*1 September 2026. Step 25, the last of the plan. Two runs of a premise never written before,
against the four-run floor built on* The Debt of Years*. Nothing was ablated between them: this is
two books, not an experiment.*

The plan said: *"Whatever it says then is the state of the project — and the first time that
sentence will be true."* What it says is less comfortable than expected.

## The floor does not transfer

Three of eleven measures put the new book **outside** the floor measured on the old one.

| measure | fresh premise | *Debt of Years* | floor | |
|---|---:|---:|---:|---|
| `gesture_rate` | **2.81** | 1.88 | 22% | 40% — outside |
| `recap_grammar` | **.064** | .035 | 59% | 59% — outside |
| `dialogue_share` | .169 | .202 | 11% | 18% — outside |
| `somatic_share` | .312 | .373 | 19% | 18% — inside, barely |
| `refusal_rate` | 1.24 | 0.76 | 69% | 47% — inside |
| `refusal_per_ask` | .944 | .644 | 53% | 38% — inside |

Nothing was ablated. Two different novels, written by the same code at the same revision, differ
by more than the noise of four identical runs on a third of the panel.

**So every figure in `checks.NOISE_FLOOR` is the noise of one novel at 71 scenes, not the noise of
this system.** That was flagged as a caveat before the runs were written; it is now a measurement.
It limits every comparison the panel has made, including both phase 1 verdicts — those compared
conditions *within* one plan, which is the right design and the reason they survive this, but it
means neither result can be assumed to hold for another book.

The two length-sensitive rows are excluded above and in the tool's own output: the fresh book is
24 scenes against 71, and `words`, `duplication_manuscript`, `repetition_concentration` and
`worst_refrain` all grow with length.

## What it does not mean

It does not mean the measures are wrong. A book with more physical description will have a higher
gesture rate, and that is the measure working. The error would be reading `gesture_rate 2.81` as
*worse prose* rather than *a different book* — the same error as reading a floor built on one
novel as a property of the writer.

Nor does it invalidate the phase 1 ablations. Those held the plan fixed and flipped one switch,
so the floor they used is the right one. What transfers is the *method*, not the numbers.

## What it costs

A floor per book is expensive: four runs is roughly five GPU-hours before any experiment starts.
The cheaper reading is that **a comparison must live inside one plan**, which is what the replicate
harness was built to do anyway, and that cross-book statements need the measure to be one that
survives the crossing — `recap_block_share` at zero everywhere, or a share rather than a rate.

The honest summary of the project's instrument panel, after all of this:

- It can compare two conditions on one plan, with error bars, and refuse a difference it cannot
  support. That works, and phase 1 is what it looks like working.
- It cannot yet say whether a book is better than another book. Three of eleven measures move
  between two premises for reasons that are not quality.
- And whether any of it corresponds to what a reader notices is still unanswered, because that is
  [step 21](sentences/sentences.md) and it needs a person.
