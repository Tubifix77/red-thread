# The human rating is cut, deliberately — and what the project may no longer claim

*3 September 2026. Tue's decision, after three instrument designs failed for the same reason.
Recorded as a scoping decision rather than a gap, because a gap implies someone will fill it.*

## The decision

Asked which unit would let him answer, having twice tried and stopped, Tue chose to stop being
asked. **Phase 10 is cut.** The hundred-sentence sheet and both pair sheets stay in the
repository as built instruments and as the record of why they did not work; none of them will be
rated.

This is his call to make and it is the right one on the evidence below. What follows is the cost,
stated precisely, so that nobody later mistakes a decision for an oversight.

## Three instruments, one flaw

| instrument | why it failed |
|---|---|
| `sentences.md` — 100 sentences, absolute 1/2/3 | No anchor to rate against, and the pool carried a confound its own key warned about: 12% dialogue on one side against 42%, and splitting to control for it leaves n=6 in a cell |
| `pairs.md` — 29 forced-choice sentence pairs | Removed the anchor and the confound, but a sentence with no context cannot be judged for fitness |
| `pairs2.md` — 40 pairs, premise/form/length controlled | Same flaw, better controlled. Controlling the confounds did not touch the real problem |

Tue's own account of why is the clearest statement of it, and it is worth quoting because it is a
better diagnosis than the designs it killed:

> *it's like I need to choose a police cruiser or a fire engine — without knowing if I should
> take it to a party, a fire or a crime*

A sentence's quality is fitness for the job it is doing, and a blind sentence has no job. A plain
functional line is right in its place and dull in isolation; an ornate one is striking alone and
exhausting in aggregate.

**And the measurements taken the same day say he is right, not merely uncomfortable.**
[cross-scene-tics.md](cross-scene-tics.md) found `the weight of` in roughly 72% of scenes and
`as if` in 70-82%. **Every single instance of those reads perfectly well.** The defect exists only
in aggregate, across scenes. A sentence-level instrument is therefore structurally incapable of
detecting the largest measured defect in this prose — so the three failures above are not three
accidents of design. The unit was wrong, and no amount of confound control fixes a wrong unit.

*The machine raters agree from the other side. Seven per-sentence signals reached nothing above
r = 0.3; a holistic model rater scored p = 0.229 on forced choice, mostly position bias; and its
"feels human" and "feels AI" lists were both 8/10 current-era, Fisher p = 1.000
([machine-rating.md](sentences/machine-rating.md)). Nobody, human or model, has been able to rate
a decontextualised sentence of this corpus usefully.*

## What the project may no longer claim

This is the part that matters, and it is a narrowing rather than a loss.

**Unavailable from here on:**

- That current-era prose is **better**. There is no rater, so there is no direction. Every
  comparison between the eras is a comparison of *measured defect rates*, and that is all it is.
- That any change **improved the writing**. A change removed a named defect, or it did not.
- Any claim of the form "**readers** would prefer X". Nothing in this repository has ever
  measured a human reader, and now nothing will. A model panel (below) can license "models
  consistently prefer X", which is a different and smaller claim, and the two must not be
  conflated.

**Still available, and unaffected:**

- Defect rates, measured deterministically and audited: duplication, recap density, gesture
  rates, gloss, wandering marks, homophone errors, cross-premise tics.
- That the eras **differ**, which is measured and large — 140-fold in within-scene duplication,
  8-fold in recap density. Different is not better.
- That a mechanism fires or is inert; that a fix moves a named measure or does not.
- One genuinely interesting reader-adjacent result, because it needed no human: a model reader
  reliably identifies which revision wrote a sentence (16 of 20 self-selected items, p = 0.006)
  and assigns the valence at chance. **Distinctiveness is detectable; its sign is not.**

So the honest framing of this project's quality work is: **it measures defects, not quality, and
it does not claim the second.** That is a smaller claim than "the prose got better" and it is one
the evidence actually supports. Every past sentence of the second kind is a bug.

## Consequences for the plans

- **PLAN.md step 21** — closed as CUT, not open. Its closing prediction, that step 21 was the
  highest-value item on the list, is withdrawn: the item was not merely expensive in human time,
  it was unanswerable in the form asked.
- **PLAN2 phase 10 (steps 33-35)** — cut. Steps 34 and 35 were explicitly gated on step 33
  confirming that the eras separate for a person, so they fall with it rather than becoming
  independently open.
- **`docs/evidence/README.md`** — the sentence sheets are relabelled from "the open step" to
  retired instruments.
- **Nothing else moves.** No deterministic measure, no check, no pre-registration and no verdict
  in this repository depended on a human rating. That is worth noting: the project has been
  running on defect measurement all along, and phase 10 was an addition to it, never a
  foundation.

## What replaces it: a cross-family model panel on passages

*Tue's proposal, made as this was being written: "we can strategically take outputs to other LLMs
like i did with chatgpt". It is the right move, and today's data says precisely how to aim it.*

The ChatGPT results split cleanly into a mode that works and a mode that does not:

| what it was asked | result |
|---|---|
| which would you read on from | p = 0.229, mostly position bias — **no signal** |
| which feels human, which feels AI | 8/10 against 8/10, Fisher p = 1.000 — **no signal** |
| *which sentences it singled out at all* | 16 of 20, p = 0.006 — **real signal** |
| *what is wrong with this prose* | named three defects, all confirmed by measurement — **real signal** |

**So a model rater is useless as a judge of quality and good as a detector of defects.** That is
the protocol: ask what is wrong, not which is better. The verdict stays with the deterministic
measures; the model supplies candidates for those measures to test.

And **Tue's context critique applies to the model raters too** — ChatGPT was rating
decontextualised sentences, the same wrong unit. Passages are the untested variable, and unlike a
human sheet they cost nothing to try at scale.

Two things make this worth pre-registering rather than merely trying:

- **A cross-family panel is available locally.** `gemma3:12b` and `gemma4:12b` (Google),
  `phi4:14b` (Microsoft), `deepseek-r1:8b` (DeepSeek) — four unrelated families, no API, no
  human cost.
- **Rule II comes free.** `qwen3:8b` wrote the prose, so it is the control that *should* show
  self-preference. If only qwen3 favours the current era, the effect is self-preference and not
  a property of the prose. If four unrelated families agree, it is not.

**The claim it could support, stated in advance:** "four model families of different lineage
consistently prefer current-era passages" — not "the prose is better", and not "readers prefer
it". A unanimous panel of models could still share a bias toward elaborate writing, which is
exactly the property [cross-scene-tics.md](cross-scene-tics.md) measured and did **not** find a
reason to call good. Distinctiveness is detectable; its sign is not, and a model panel does not
change that.

A null is equally useful and cheaper to believe: if four families cannot separate the eras on
passages, the case that they are perceptibly different weakens considerably, and several
speculative mechanisms retire with it.

*And if a human unit is ever revisited: not another sheet. The unit would have to be large enough
for aggregate defects to be felt — several excerpts from different scenes side by side, so a
recurring tic reads as recurrence rather than as one good sentence. That was the fourth design and
it was not built, because being asked a fourth time was the thing declined. **Build it for a rater
who has not already been asked three times.***
