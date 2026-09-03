# A defect class nothing in the panel can see

*3 September 2026. Prompted by an outside reader, verified deterministically here.*

## Where this came from, and what the outside reader got wrong

Tue pasted the hundred-sentence sheet into ChatGPT and asked it which sentences were
AI-generated. Its answer was wrong in the way that matters and right in two ways that were worth
more than the answer.

**Wrong:** every sentence in that sheet is machine-written. Both halves are `qwen3:8b` - the
sheet compares two revisions of *this* writer, `pre-prose-work` against `current-era`, and the
rating task is "would I read another page", not authorship. So an estimate of "65-80% AI
involvement" is a 100% rate, under-called.

**Right, first:** it identified the duplicate sentences exactly - #10/#36/#67 are verbatim
identical and so are #14/#95. All six sentences involved, in both clusters, are
`pre-prose-work`; not one is `current-era`. That is a real signal, and it independently
rediscovered the largest already-measured difference between the two eras: within-scene
duplication .279 against .002 ([MEASUREMENTS.md](../MEASUREMENTS.md)). Not a new finding, but a
genuine external check on that measure - it was found blind, from 100 shuffled sentences, with no
access to the key.

**Right, second, and this is the valuable part:** its two main stylistic complaints - "the weight
of" as an emotional abstraction, and "as if" comparisons - are real, large, and measured by
nothing in this project.

## Was the sheet contaminated by being shown to a model?

Asked first, because if the answer were yes the sheet would be dead and nothing else here would
matter. It is not. Splitting ChatGPT's own buckets by the condition it could not see:

| its bucket | n | pre-prose-work | current-era |
|---|---:|---:|---:|
| "very AI-like" | 69 | 49% | 51% |
| "ambiguous" | 16 | 50% | 50% |
| "more natural" | 22 | 55% | 45% |
| its "top 15 most suspicious" | 15 | 40% | 60% |

**Indistinguishable from chance in every bucket**, against two eras that differ 140-fold in
duplication and 8-fold in recap density. Its stylistic judgement carries no information about
which revision wrote a sentence. Two further signs it is measuring something else: the "more
natural" bucket is simply *shorter* (12.0 words per sentence against 18.3 for "very AI-like"),
and nine sentences appear in both "very AI-like" and "more natural" at once.

So the priming is non-differential. A rater who has seen that assessment carries extra noise into
the sheet, not extra bias, and only a skew would have wrecked the comparison. **The sheet is still
usable.** This is recorded because "we showed the instrument to a model first" is the kind of fact
that is worthless discovered after the ratings exist.

## The blind spot, stated mechanically

Two things could have caught stock phrasing and neither can.

- **`duplication_ratio(text)` takes one scene.** It measures repeated 4-grams *inside* a scene.
  A phrase the writer returns to once every ten scenes scores 0.00 in every one of them. The
  current-era .002 is a per-scene figure and is not evidence about the book.
- **The 138-phrase antislop list is another model's tics.** It is externally sourced from
  sam-paech/antislop-sampler, which this project treats as a virtue and still is. Measured
  against the phrases `qwen3:8b` actually repeats, it covers **none** of them - not `weight`,
  `edge of`, `as if`, `as though`, `space between`, `taut` or `tilted`.

Between them: repetition inside a scene is measured, and a list of someone else's stock phrases
is enforced. The phrase this writer reaches for every fifth scene falls between the two.

## Telling a tic from a story's own vocabulary

The hard part is not counting. "the ledger of time" recurs in 14% of *Debt of Years* scenes and
**must** - it is the novel's central object. "the weight of the" recurs in 22% and should not. No
frequency threshold separates those, and a threshold-only measure is how this project shipped two
contaminated ones.

The separator needs no external corpus: **a phrase that also recurs in books of a different
premise cannot be this story's vocabulary.** The same logic as `checks.PORTABLE` and
`clears_noise(cross_book=True)`, applied to phrasing. 1,552 *Debt of Years* scenes against 221
scenes across ten unrelated premises (`scripts/tic_audit.py`).

**It validates itself on the split.** Every name-bearing phrase landed premise-bound; every
abstraction landed cross-premise. And the leak is known and one-directional: a tic that happens to
carry a character name - `vay tilted his head`, 12.2% - is classified premise-bound, so this
**under-reports**. Every phrase it does report is cross-premise by construction.

### 4-grams recurring in 40+ Debt scenes, by their rate in unrelated premises

| phrase | Debt scenes | unrelated premises |
|---|---:|---:|
| the edge of the | 24.7% | **51.6%** |
| the weight of the | 22.1% | 28.5% |
| for the first time | 26.5% | 18.1% |
| the space between them | 22.2% | 16.3% |
| carried the weight of | 5.2% | 13.6% |
| tilted her head slightly | 3.1% | 11.3% |
| felt the weight of | 2.6% | 10.9% |
| the weight of something | 4.3% | 10.4% |

264 phrases cross premises; 124 are premise-bound. As whole constructions, per scene:

| construction | Debt scenes | unrelated premises | uses per scene |
|---|---:|---:|---:|
| `as if` | 70.2% | **82.4%** | 1.47 / 2.62 |
| `the weight of` | 72.2% | 65.2% | 1.14 / 1.83 |
| `as though` | 51.0% | 50.7% | 0.80 / 0.91 |
| `the space between` | 33.2% | 26.7% | 0.34 / 0.29 |
| `the edge of` | 33.8% | 59.3% | 0.39 / 1.00 |

**"the weight of" is in roughly seven scenes in ten, and "as if" in seven to eight.** Both of the
outside reader's headline complaints, confirmed at a scale nothing was watching.

**One of its pattern claims does not survive.** It named `"not X, not really - it was Y"` as a
recurring template, on the strength of sentence #30. Measured: **0.1%** of Debt scenes, 0.0%
elsewhere. It generalised a template from one instance it happened to see, which is the same error
as quoting a maximum (rule III) with extra steps.

## One outright error, and reading the matches paid again

`pulled taught` for `pulled taut` - **8 occurrences against 43 correct ones, a 16% error rate on
that homophone**, spread across 7 current-era books including `current` and `ledgerfix`. Not a
stylistic preference; a misspelling in finished prose, and nothing in the gate looks for it.

Three of the eight get it right and wrong in the same sentence - *"the silence stretches, taut as
a string pulled taught"*. And six of the eight are the same simile: `thread/string pulled taut`
recurs **48 times across 19 of 41 books**, which is the tic finding above arriving from a
different direction.

Fifteen homophone patterns were audited; thirteen found nothing. **One of the two that fired was a
false positive** - `born of necessity` is correct idiom, not `borne` - so the honest count is 8
errors, not the 10 the patterns returned. Had that number been published unread it would have been
25% wrong, which is the fourth time that rule has earned its place.

## What is not claimed, and the next lever

- **No fix is tested here.** Everything above is a measurement of the corpus as it stands.
- **The rates are not comparable across the two corpora as quality claims.** 1,552 scenes against
  221 is a 7:1 imbalance, and the unrelated-premise books are mostly short. The cross-premise
  column is used only as a *binary-ish* separator - does this phrase exist outside this story -
  which is what it is sound for. The higher `other` rates are consistent with short books
  spending proportionally more text on scene-setting, and are not read as "unrelated books are
  worse".
- **The natural lever is the slop list, not a gate.** Rule VI puts quality at the plan and not at
  the gate, and there is already sampler machinery for stock phrasing. The proposal is therefore
  to extend the antislop list with *this model's measured tics* rather than to add a check: the
  external list is sound and simply aimed at other models.
- **That proposal needs pre-registration before any run.** Suppressing `the weight of` could
  plainly make the prose worse rather than better - the phrase is not wrong, only overused - and
  the measure that would judge it is `duplication_ratio`, which cannot see the thing being fixed.
  A criterion has to name a measure that moves, which is rule VII, and finding that measure is the
  open work.
