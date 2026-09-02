# The inconsistency finder, pre-registered before any run

*2 September 2026. The successor the previous verdict specified, and it inherits none of that
verdict — a rejected instrument's replacement has to earn its own. Committed before a single
finder call is made; results append below the line and nothing above it changes.*

## Why this is a different instrument, not a third attempt

The predecessor was rejected after two pre-registered rounds
([inspector-method.md](inspector-method.md)) with a diagnosis attached: **19 of 19 seeded
contradictions caught exactly, every flag in 40 trials pointing at something genuinely wrong, and
two false alarms per round against a ceiling of 1.** It failed on specification, not capability.
It was asked one binary question and kept correctly answering a broader one, with nowhere to put
the answer.

Three changes, each traceable to a specific finding rather than to taste:

**1. Categories, derived from the six real findings.** Not invented — enumerated from what the 40
trials actually turned up:

| category | exists because |
|---|---|
| `SCENE_CONTRADICTS_FACT` | the original target; 19 of these were caught |
| `FACT_MISREADS_SOURCE` | the ledger recorded *"the donor was dead"* from prose reading *"dead anyway. Not literally, not exactly"* |
| `SCENE_INTERNALLY_INCOHERENT` | a scene restated its fact correctly, then put a temple scar *"beneath his shirt collar"* |
| `CLEAN` | — |

**2. Every fact travels with the sentence it came from.** The ledger does not store it, so
`scripts/inconsistency_finder.py` locates it: the sentence in the fact's own scene carrying ≥ 60%
of the fact's content words. Below that the packet says **`[source sentence not locatable]`** and
forbids the `FACT_MISREADS_SOURCE` judgement on that fact. A source located by guesswork would
manufacture the exact defect class this tool exists to find. In practice 5–10 of 12 facts per
packet locate cleanly, and the count is printed.

**3. Recall is the metric. Precision is a triage budget.** The predecessor's 1-in-10 false-alarm
ceiling is the specification error itself, and is not carried over.

**4. Adjudication is blind and not mine.** This is the fix for the weakest joint in the last
verdict: that verdict hinged on *my* judgement that one flag was a real ledger defect rather than
a false alarm, and I said so at the time. Here **every flag goes to a second, independent subagent
that is not told whether its packet was seeded or clean**, and is asked only whether the cited
incompatibility is real. My own reading is recorded beside it and does not override it. Where
they disagree, the disagreement is the finding.

## The validation set

20 packets from `runs/current`, built by the script above:

- **10 seeded**, distributed across the three defect categories — 4 `SCENE_CONTRADICTS_FACT`,
  3 `FACT_MISREADS_SOURCE`, 3 `SCENE_INTERNALLY_INCOHERENT`.
- **10 clean**, untouched.
- Every seed is **validated programmatically before its trial exists**: the harness asserts the
  text it depends on is literally present, and refuses to build the trial otherwise. This is the
  fix for round 1's P1, where *"smells burnt wood"* became *"smells of citrus"*, flipped perceiver
  to emitter, and contradicted nothing.
- One fresh Fable-class subagent per packet, no project context, one Read and no other tool. No
  agent sees more than one packet.

## Thresholds, fixed now

**Primary — recall with correct category: ≥ 8 of 10 seeded defects found *and* assigned the right
category.** Category counts here, unlike in the predecessor, because the categories are the
redesign; a finder that spots everything and labels it wrongly has not fixed the problem it was
built to fix.

**Secondary — spurious flags: ≤ 3 across the 10 clean packets**, where *spurious* means the blind
adjudicator judges the cited incompatibility not real. Deliberately three times looser than the
ceiling that rejected the predecessor, because a human reads this output and a wrong flag costs
one paragraph of reading.

**Reported, never gated:** flags per packet (triage cost), the category confusion matrix, and
every adjudicator/experimenter disagreement.

- **Adopt** iff recall ≥ 8/10 with correct category AND spurious ≤ 3/10.
- **Reject** otherwise — and a rejection here is a result about the *approach*, not this
  configuration: it would mean session-side inspectors do not clear this project's bar, and the
  honest conclusion would be to stop building them rather than to iterate a third design.

*What adoption buys, stated narrowly in advance:* it may be run over committed books to produce a
triage list a person reads, and over halted scenes to classify a halt as a genuine contradiction
versus a repair failure — which is the discrimination [PLAN2](../PLAN2.md) step 32 needs. It may
**not** gate a commit, score prose quality, replace the panel, or run in the product. **Rule VI is
unchanged: the writer stays `qwen3:8b` on Ollama with zero Claude calls**, which is why the tool
prepares packets and tallies answers rather than calling any model itself.

## One limitation that no threshold covers

Both the finder and its adjudicator are Claude subagents. They may share a blind spot, and an
agreement between them is weaker evidence than it looks — the same structural caveat as an LLM
rating LLM prose, which this project already has two data points on and one outstanding human
tiebreak. Nothing here is evidence about what a person would call an inconsistency; it is evidence
about whether a checkable, recall-weighted instrument can be built at all.

---

*Results follow below this line. Nothing above it changes.*
