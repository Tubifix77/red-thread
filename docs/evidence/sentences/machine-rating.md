# The panel against a reader — with a machine standing in for the reader

*1 September 2026. Step 21's analysis, run on ratings produced by Claude rather than by a person.*

**This is not step 21 and it does not close it.** Step 21 asks whether the panel corresponds to
what *a reader* notices; the rater here is an LLM, and [the blank sheet](sentences.md) is
untouched and still waiting for Tue. What this run is worth: the analysis path is exercised
end to end on real ratings, and it produces two results specific enough to be checked against a
human rating later — which makes them predictions rather than findings.

The ratings are in [sentences-claude.md](sentences-claude.md). They were made blind — the key was
not opened until the sheet was complete — in one pass, first reaction, as the sheet instructs.
Distribution: 18 threes, 52 twos, 30 ones.

## Result 1: the eras are distinguishable in single sentences

| | mean rating | 95% bootstrap | n |
|---|---:|---|---:|
| current-era | **2.12** | [1.94, 2.30] | 50 |
| pre-prose-work | **1.67** | [1.50, 1.83] | 48 |

Non-overlapping, and it survives both controls that could have produced it artificially:

- **Dialogue.** The two eras differ enormously in dialogue share — 21 of 50 current-era sentences
  are spoken against 6 of 50 pre-prose-work — and a rater who simply prefers dialogue would
  produce this gap for free. On the narrated sentences only: **2.14 against 1.59** (n=29, n=44).
  The gap is not the dialogue.
- **Duplicates.** One sentence appears three times, all three in the pre-prose-work half, all
  three rated 1 — *"He had made his choice, and now it was time to live with it."* Counting it once
  moves the figure from 1.64 to 1.67 and the intervals still do not overlap. The gap is not one bad
  sentence counted three times.

So the prose work is detectable with no context, one sentence at a time, by a blind rater. That is
the strongest statement this project has yet had about its output, and the reason it is not
banked is entirely the identity of the rater — see the caveat below.

## Result 2: no per-sentence measure in the panel corresponds to the rating

| signal | r |
|---|---:|
| `past_perfect` | −0.282 |
| `gesture` | +0.185 |
| `spoken` | +0.173 |
| `words` | +0.100 |
| `gloss` | −0.080 |
| `somatic` | +0.018 |
| `slop` | +0.018 |

Nothing reaches r = 0.3. And the one that came closest is **rule II** — a measure scored against
something it should not match:

    past perfect, share of sentences      current-era     0 of 50
                                          pre-prose-work 28 of 50

`summary_distance` feeds candidate selection — the pipeline prefers the draft that is happening
over the draft that is recapping — so the current era suppresses past perfect *structurally*. The
measure is therefore a perfect era marker, and its correlation with the rating is the era gap of
result 1 arriving through a different door.

Within the only era where it varies, it does nothing:

| pre-prose-work only | mean rating | 95% bootstrap | n |
|---|---:|---|---:|
| past perfect | 1.57 | [1.32, 1.82] | 28 |
| simple past | 1.73 | [1.50, 1.95] | 22 |

Fully overlapping. **So the honest count is zero of seven, not one of seven.** The strongest
apparent signal in the panel, against a reading, is a confound.

## What the sheet cannot test, and why that matters here

Duplication, refrains, cross-scene gesture repeats and repetition concentration are properties of
a *manuscript*. They cannot be asked of one sentence, and they are where most of this project's
effort has gone — including both mechanisms phase 1 kept. **A hundred loose sentences can never
test them.** The r < 0.3 result applies to the seven per-sentence signals and to nothing else.

It is also worth noticing which side of the ledger each result lands on. Result 1 says the writing
changed in a way a blind reader can see. Result 2 says the instruments cannot see what the reader
saw. Both can be true, and if they are, the panel's value is as a *regression detector within one
plan* — which is exactly what [phase 1](../phase1-ablations.md) used it as and all it was shown to
do there.

## The caveat, which is the whole caveat

**An LLM rated prose written by an LLM.** Both are qwen-family or Claude-family transformers
trained on overlapping text, and a machine rating may measure fluency-under-a-language-model
rather than whether a person turns the page. The direction and size of that bias are unknown, and
nothing above should be read as evidence about human readers.

Two specific ways this could be wrong rather than merely uncertain:

- The rater may be detecting *era* by some stylistic tell and rating the tell, not the prose. The
  dialogue control removes the obvious candidate and the past-perfect finding removes another —
  but a third tell would look exactly like result 1.
- The rater has read this codebase, its docs, and its evidence files. It has no access to the key,
  but it is not a naive reader, and "which era is this" is a question it has reason to have an
  opinion about.

*Update, 2 September: the "not a naive reader" caveat has since been tested — a context-free
rater keeps the direction and loses the separation (2.16 against 2.04, overlapping), while the
zero-of-seven signals finding holds on the second rater too
([inspector-method.md](../inspector-method.md), experiment B). Both machine data points now stand
for the human sheet to adjudicate.*

The thing that resolves both is a person filling in the same sheet from the same shuffle. The
strong prediction to check it against: **the human means will separate in the same direction, and
none of the seven signals will reach r = 0.3.**
