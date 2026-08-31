# Three ways of measuring tension, and what each one turned out to measure

*31 August 2026. Phase 2 of `docs/PLAN.md`, steps 9 to 13, run locally on 35 scenes of a finished
71-scene novel. 350 model calls, no API calls.*

The idea is sourced. Narrative tension is downstream of hidden information, so a scene a model can
call from the story so far has none, and the entropy of a forecasting distribution meters it
(`RESEARCH.md` section 9). Three implementations have now been tried. None of them measures the
book.

## What each attempt actually compared

| | comparison | result |
|---|---|---|
| lexical overlap | prediction against the scene, by shared words | **51%** win rate against a random other scene |
| embedding cosine | prediction against the scene, by meaning | **54%** |
| prediction spread | k predictions against *each other*, never the scene | ranks reproduce at **r = +0.337** |

The bar for the first two was 65%. Neither reaches it.

## Steps 10 and 11: meaning fails where words failed

```
   scorer              on target   on control   win rate
   lexical overlap         0.549        0.543        51%
   embedding cosine        0.749        0.739        54%
```

**Read the absolute cosines, not the win rate.** `.749` against `.739` — a prediction resembles a
random scene from the same novel almost exactly as much as it resembles the scene it was
predicting. A raw similarity between any two passages of one book is high and says nothing at all,
which is why nothing in `redthread/forecast.py` prints one as a result.

So the failure was never the *representation*. It is the comparison. A two-sentence prediction and
an eight-hundred-word scene from one book are dominated by the book — in meaning as much as in
words — and a better encoder does not remove that. `nomic-embed-text` works: two related sentences
score .798 and two unrelated ones .427. It is being asked the wrong question.

*Two corrections were made to the control before believing it, both toward the predictor.* The
decoy pool now excludes the three scenes `story_so_far` had just put in front of the model — a
prediction necessarily echoes its own input, so drawing a decoy from there scores the model
against what it had just read. That moved lexical from 40% to exactly chance and left embeddings
where they were. A result that still fails after its control has been made fairer fails for real.

## Step 12: the version the paper actually describes

Measuring how much k blind predictions disagree *with each other* never touches the scene, so the
shared vocabulary that killed both earlier attempts cannot reach it. That is the whole reason it
was worth trying after two failures.

The distribution looks reasonable: **mean spread .130, range .060 to .266** across 35 scenes, with
three scenes standing out as ones the model can call. Lexical overlap's distribution looked
reasonable too — mean .538, range .26 to .73 — and was noise.

So the replicate rule applies one level down: **do two independent sets of predictions agree about
which scenes are predictable?** A second set of 175 calls, same scenes, same k, different sampling.

**r = +0.337.** About a ninth of the variance shared.

That is not a refutation and it is not a result. At k = 5 the spread is dominated by the sampling
rather than by the scene, and step 13 — plotting tension across a manuscript to look for a sagging
middle — has nothing stable to plot. Whether a larger k recovers a scene-level signal is untested,
and is the obvious next move: the noise in a mean of pairwise distances falls with k, and five is
a small number.

## The finding that outlasts all three

The plan said the 35 predictions from the first calibration were on disk and a re-score would be
free. **They were not.** `probe_forecast` records a Violation only when overlap clears its
threshold; across the whole corpus none ever did; the calibration lived in a throwaway script and
left nothing behind. The generation had to be paid for twice.

**An experiment whose only output is a pass/fail verdict cannot be re-analysed**, and this
project's most expensive negative result was stored that way.

Predictions are now persisted with the context that produced them, so a re-score cannot silently
change what the model was shown. The value of that showed up within the hour: re-scoring with the
corrected decoy pool cost **six embedding calls against 309 served from cache**, and no
regeneration at all.

## What is left of the idea

The concealment field ships and works — it is what stops a scene disclosing what a thread is still
hiding, and it is derived from the schedule rather than guessed.

What does not work is any attempt to *score* tension after the fact by comparing a prediction to
prose. Three implementations, three controls, three failures, and the reason is the same each
time: two passages of one novel are mostly that novel. The only version with a route left is the
one that never looks at the scene, and it needs more samples per scene than five before anyone
can say whether it sees anything.
