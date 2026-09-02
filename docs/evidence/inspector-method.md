# The focused-inspector method, pre-registered before any inspector ran

*2 September 2026, evening. Tue's suggestion, taken as a design problem: "an alternative test
method, like a high-model subagent inspector with certain focuses." This file is committed before
a single inspector call is made; results will be appended below the line, and the thresholds here
cannot move after it.*

## What an inspector is, and is not

A **focused inspector** is a high-capability model (a Claude subagent inside the development
session — the *writer* stays `qwen3:8b` on Ollama, unchanged) asked one narrow, falsifiable
question about one artefact, whose answer must carry located evidence. It is **not** a judge of
quality. The distinction is load-bearing and comes from the sources already in the ledger:

- Zero-shot LLM *preference* judging is a measured ceiling — 73% agreement with human preference,
  the strongest off-the-shelf judge ([LitBench](https://arxiv.org/abs/2507.00769)). Nothing here
  asks a model whether prose is good.
- Self-correction works when **reliable external feedback** exists and fails as self-critique
  ([Kamoi et al., TACL 2024](https://arxiv.org/html/2406.01297v3)). An inspector validated on
  seeded ground truth *is* external feedback with a measured error rate; an inspector trusted on
  its own authority is self-critique with better marketing.

**Rule VI is absolute and inherited:** nothing an inspector says ever gates a commit. Inspectors
are session-side instruments for auditing, triage and hypothesis generation. And rule II is the
admission price: **an inspector may not be used on any live question until it has been scored on
material where the right answer is known** — the same discipline as the check suite, where every
check is tested by injecting its defect.

## Experiment A — a continuity inspector, validated on seeded contradictions

**Focus:** given facts the book established earlier and one scene's text, does the scene
contradict a listed fact? This is the triage question step 32 will face (two of three audited
halts were genuine contradictions), and the audit question the ledger's code checks cannot ask
semantically.

**Design — paired, blind, independent:**

- 10 (fact-sheet, scene) pairs are built from `runs/current`: each sheet holds ~12 durable facts
  established in *earlier* scenes, one of which is restated near-verbatim in the target scene's
  text (62 such candidates exist; 10 were chosen for having a clean, checkable restatement).
- Each pair yields **two trials**: one **mutated** (the restated fact is rewritten by hand to
  state something the scene is incompatible with — an attribute flipped, never a grammar break)
  and one **control** (the sheet untouched). 20 trials.
- Each trial goes to a **fresh subagent** (Fable-class, no project context, tools forbidden,
  judging only the text in its prompt). No subagent sees more than one trial. The prompt states
  that a contradiction *may or may not* be present, that absence of a detail is not a
  contradiction, and demands `VERDICT: CONTRADICTION|CLEAN` plus, on CONTRADICTION, the fact and
  the shortest scene quote.

**Scoring, strict:** a **hit** is CONTRADICTION on a mutated trial *naming the mutated fact*; a
CONTRADICTION naming any other fact is a false alarm even on a mutated trial. A **false alarm** is
any CONTRADICTION on a control trial.

**Thresholds, fixed now:**

- **Adopt as an advisory instrument:** hits ≥ 8 of 10 AND false alarms ≤ 1 of 10.
- **Park:** hits ≥ 8 but false alarms ≥ 2 (it sees真 but cries wolf — unusable for triage), or
  hits 6–7 with 0 false alarms (promising, needs a bigger set before use).
- **Reject:** anything else. Recorded either way.

*(A ceiling to keep in mind, stated before results: 10/10 with 0/10 false alarms on n=10 pairs is
still only n=10. Adoption means "may be used advisorily while accumulating a live error record",
not "trusted".)*

## Experiment B — a context-free rater on the hundred sentences

The machine dry run ([machine-rating.md](sentences/machine-rating.md)) carried its own caveat:
*the rater has read this codebase — it is not a naive reader.* A fresh subagent with **zero
project context** — given only the sheet's own instructions and the 100 shuffled sentences inline,
forbidden to read anything — removes that specific confound. It does not remove the deeper one (an
LLM rating LLM prose), which only Tue's twenty minutes can.

**Pre-registered predictions, fixed now:**

1. The naive rater separates the eras in the same direction (current-era mean above
   pre-prose-work).
2. No per-sentence panel signal reaches |r| ≥ 0.3 against its ratings.
3. Descriptive, no threshold: inter-rater agreement between the naive rater and the dry run —
   the first measurement of machine-rater consistency on this sheet, recorded whatever it is.

The blank sheet stays blank; the naive ratings go to their own file, and the key stays unopened by
the subagent (it receives only the sheet, which contains neither eras nor sources).

## What adoption would and would not change

Adopted inspectors join the toolbox the way `scripts/portability.py` did: instruments with
documented scope. Candidate uses, all advisory — auditing committed books for contradictions the
ledger's string-matching missed; triaging future halts (genuine contradiction vs repair failure)
for step 32; second-opinion on `same_code`-style questions. **Not** candidate uses: gating,
scoring prose quality, replacing the panel, or anything in the unattended write path — the product
must keep running with zero Claude calls, on the standing constraint that red-thread runs on local
models only.

---

*Results follow below this line, appended after the trials ran. Nothing above it changes.*
