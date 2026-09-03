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
