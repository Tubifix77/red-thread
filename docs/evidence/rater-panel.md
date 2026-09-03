# Do model raters of unrelated lineage separate the two prose eras? Pre-registered

*3 September 2026. Committed before the panel is run. Thresholds below cannot move afterwards.*

## Why this exists, and what it replaces

The human sheet is cut ([no-human-rater.md](no-human-rater.md)). Tue's proposal in its place —
*"we can strategically take outputs to other LLMs like i did with chatgpt"* — is aimed here at
the one mode that measured as useful, and away from the two that measured as noise.

|what the one model rater tried so far was asked | result |
|---|---|
| which would you read on from | p = 0.229, and it picked the first option 23 times in 29 |
| which feels human, which feels AI | 8/10 against 8/10, Fisher p = 1.000 |
| *which sentences it singled out at all* | 16 of 20, p = 0.006 |
| *what is wrong with this prose* | three defects named, all confirmed by measurement |

Three things are changed from every design that has failed:

1. **Passages, not sentences.** Tue's diagnosis of why he could not rate the sheets applies to a
   model rater identically — a decontextualised sentence has no job, so its fitness cannot be
   judged. It is also the reason the sheets could never have worked: the largest measured defect
   here, `the weight of` in ~72% of scenes, is invisible in any single sentence because every
   instance reads fine.
2. **Order counterbalanced.** Every pair is asked twice with the sides swapped. Position bias was
   the *dominant* signal in the only rater tried so far, so it is designed out rather than
   controlled for: a pair counts only if the model picks the same **passage** in both orders. Same
   **letter** twice is position-bound and excluded.
3. **Unrelated lineages, with the writer as the control.** `qwen3:8b` wrote this prose, so it is
   the rater that *should* show self-preference (rule II). It is a control, not a panel member.

## Design, fixed now

- **32 pairs**, one current-era passage against one `debt` passage, ~110-160 words each, matched
  within 15% on word count, drawn mid-scene so no scene opening competes with continuous prose.
  Premise held fixed at *The Debt of Years*.
- **Panel:** `gemma3:12b`, `gemma4:12b` (Google), `phi4:14b` (Microsoft), `deepseek-r1:8b`
  (DeepSeek). **Control:** `qwen3:8b`.
- Each pair asked twice per model, sides swapped, temperature 0.
- Usable pairs = order-consistent ones. Two-sided binomial per model on its own usable count.

## Thresholds, and the exclusion rule stated in advance

- **Positive:** at least **3 of the 4 unrelated families** reach p < 0.05 **in the same
  direction**. Two of four is not a result; a split direction is not a result.
- **Reliability exclusion, fixed here so it cannot be applied after the fact:** a rater whose
  position-bound rate exceeds **50%** is declared unusable and drops out of the panel count. Its
  exclusion is reported, and if it leaves fewer than 3 usable panel members **the test is void,
  not negative** — an unreliable panel measures nothing either way.
- **Self-preference verdict:** if `qwen3:8b` is the only rater reaching significance, or its
  effect size exceeds every panel member's, the result is reported as self-preference and **not**
  as a property of the prose.
- **Null:** fewer than 3 of 4 → the eras are not separable by model raters on passages. That is
  a useful outcome and cheaper to believe than the alternative: it would retire the several
  speculative mechanisms in PLAN2 that assume the eras are perceptibly different.

## What a positive result would and would not license

**Would:** "model families of different lineage consistently prefer current-era passages."

**Would not:** that the prose is *better*, or that a *reader* would prefer it. A unanimous panel
of models can still share a trained bias toward elaborate writing — which is exactly the property
[cross-scene-tics.md](cross-scene-tics.md) measured at 65-82% scene incidence and found no reason
to call good. **Distinctiveness is detectable and its sign is not**, which is already the measured
result from the one rater tried, and a bigger panel does not change the kind of thing being
measured.

**A limitation inherited from the corpus, not chosen:** *The Debt of Years* has exactly one
pre-prose-work book, `debt` at 27 scenes. The whole old side comes from it, so a result speaks
for `debt` against the current era and not for the era in general. Book-level variance cannot be
estimated from one book.

---

*Result appended below after the run. Nothing above changes.*
## Run 1: VOID by the registered rule

*3 September. 32 pairs, word gap median 6, max 17. Reported in full before any amendment.*

| rater | lab | usable | current-era | position-bound | p | registered verdict |
|---|---|---:|---:|---:|---:|---|
| gemma3:12b | Google | 15/32 | 13/15 | 17 — **53%** | 0.007 | **EXCLUDED**, over the 50% bar |
| gemma4:12b | Google | 29/32 | 26/29 | 3 — 9% | **0.000** | usable |
| phi4:14b | Microsoft | 18/32 | 13/18 | 14 — 44% | 0.096 | usable, not significant |
| deepseek-r1:8b | DeepSeek | 0/32 | — | 0 | — | **UNUSABLE**, no parseable answer |
| qwen3:8b | *control, wrote the prose* | 20/32 | 12/20 | 12 — 38% | 0.503 | — |

Two usable panel members where the registration requires three. **The registered rule says that
is VOID, not negative**, and it says so precisely because an unreliable panel measures nothing in
either direction. The appealing reading — *two of two usable raters favour current-era at p=0.007
and p<0.001* — is not available, and the pre-registration exists to make it unavailable.

### Why it voided: one real rater property and one bug of mine

- **gemma3 at 53% position-bound is a fact about gemma3.** It answered by position on more than
  half the pairs. It sits two pairs over the bar, so its exclusion could flip on noise, and that
  fragility is worth naming rather than smoothing.
- **deepseek-r1 produced nothing because I starved it.** Diagnosed rather than assumed: it
  **ignores `think=False`** — verified directly against `/api/chat` with `think` false, null and
  true, all three returning empty `content` with `done_reason: length` while `thinking` fills up.
  At `num_predict` 8, 64, 512 and 1024 it is still reasoning when the budget ends; at 4096 it
  stops and answers, having spent 10,557 characters of scratchpad to produce one letter.

  **An 8-token budget silently produced no data from an entire rater for a whole run** — no error,
  no answer, and nothing in the output distinguishing "declined" from "never got to speak". That
  is the same failure class as `wandering_details` reporting clean when it could not read its
  input, found this morning. The script now sets the budget per model and prints `unparsed`
  separately from `position-bound`, so this cannot be silent again.

### One result from the void run worth keeping, because it is the control

**`qwen3:8b` — the model that wrote the prose — showed no preference at all: 12/20, p = 0.503.**
Self-preference was the artefact this control exists to catch, and it is absent. That is the
opposite of what a self-flattery explanation predicts, and it survives the void because it is a
null on a rater whose reliability (38% position-bound) passed the bar.

## Amendments before run 2, with the criterion untouched

**The pass criterion does not move**: at least 3 usable panel raters significant at p < 0.05 in
the same direction, >50% position-bound excludes a rater, and fewer than 3 usable panel raters
voids rather than fails. Three changes, all of which I would make had run 1 gone the other way:

1. **Per-model token budget** (`REASONING_BUDGET = 4096`). A bug fix, not a design change.
2. **60 pairs instead of 32.** Usable rates of 44-56% mean 32 pairs yields 15-20 usable, which is
   thin. More pairs raises power and cannot bias direction.
3. **A correction to my own registered wording, which tightens the bar against me.** It said "at
   least 3 of the 4 **unrelated families**" and then listed gemma3 *and* gemma4 — which are two
   generations from **one lab**, not two lineages. As written, "3 of 4" could be satisfied by
   gemma3 + gemma4 + one other and pass on essentially two labs. **Run 2 therefore also requires
   the significant raters to span at least 2 distinct labs.** This is stricter than what was
   registered and is applied knowing it makes a pass harder.

**The risk, stated rather than buried:** run 2 is not blind — I have seen that both Google models
favour current-era. The protections are that the criterion is unchanged, the tightening runs
against my interest, and run 1 is reported above in full including the numbers that would have
looked better left out. A void caused by a harness bug is the case the registration anticipated
when it wrote "void, not negative"; it is not a licence to keep running until the answer is nice,
and **if run 2 voids again the answer is that this panel cannot measure it, not run 3.**
