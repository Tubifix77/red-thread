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

# Results: recall passes, and the run found a bug in the instrument that was measuring it

*20 packets, 20 fresh Fable-class subagents, one packet each, zero GPU.*

## Recall: 8 of 10, which meets the bar

| seeded category | found and correctly categorised |
|---|---|
| `SCENE_CONTRADICTS_FACT` (4) | 3 — A1, A2, A4 |
| `FACT_MISREADS_SOURCE` (3) | **3** — B1, B2, B3 |
| `SCENE_INTERNALLY_INCOHERENT` (3) | 2 — C2, C3 |
| **total** | **8 of 10 — passes the ≥ 8 threshold** |

Every one of the eight named the seeded item and assigned the right category. The new
`FACT_MISREADS_SOURCE` category worked perfectly on the class it was invented for: all three
seeds caught, each quoting the source sentence against the fact.

**Both misses are my measurement design, not the finder's reading.** The prompt asks for *"the
single most serious inconsistency"*, and in both misses the finder found a **genuine defect that
outranked my seed**:

- **A3** ignored a seeded vial mutation and flagged *"[scene 57] Kai has watch in coat pocket"*
  against scene 61's *"the watch hidden beneath his sleeve"*.
- **C1** ignored a seeded injected clause and flagged a one-palm scar appearing across both palms.

Asking for one finding when the material contains several makes seed-recall unmeasurable whenever
reality outranks the seed. The finder is penalised for prioritising correctly. **Fix for any
future round: ask for all findings, not the most serious one.** That is the third
experimenter-side error in this line of work — after round 1's invalid seed and round 2's
mechanically-distorted seeds — and the first that is a *measurement* design error rather than a
seed-validity one.

## Precision: the controls were never clean, and that is the headline

**Nine of ten "clean" packets flagged.** By the letter of the threshold — spurious ≤ 3 — this
fails badly. By audit, almost none of it is spurious:

| packet | finding | verified |
|---|---|---|
| N1 | fact *"Kai knows the world has changed"* whose source attributes the line to **Vay** | real |
| N2 | Kai holds the vial from line one, yet Vay slides it across the table to him | real |
| N3 | *"Kai is considering stealing years"* from a source merely calling it theft | real |
| N4 | *"has a map in his shirt pocket"* from a source saying he **imagined** it there | real |
| N5 | Kai retrieves a street-level parchment while still on the rooftop | real |
| N7 | the theft is *thirty years* in one line and *thirty days* a few paragraphs later | real |
| N10 | the file is in Kai's hands and in Vay's in the same scene | real |
| N6, N8, N9 | *"Kai has scar"* cited to a sentence with no scar in it | **my bug — see below** |

**A negative control cannot be created by assuming a scene is clean.** Real prose and a real
ledger contain real defects at a rate high enough that a randomly drawn packet is usually *not* a
negative control. The pre-registered threshold "spurious ≤ 3 of 10 clean packets" was therefore
unmeasurable as written — not because the finder misbehaved, but because the word *clean* was
doing work no one had earned.

## The bug the instrument found in its own harness

N6, N8 and N9 — three independent agents — reported that *"[scene 23] Kai has scar"* was sourced
to a sentence about *"discarded watches, cracked and smudged"*, which contains no scar.

They were right, and the fault was **mine**: `locate_source` tested `word in sentence`, and
**di·scar·ded contains "scar"**. This project's oldest defect class — the refusal regex that was
56% ordinary English, the vacuous model-index scan — reappearing in the tool built to audit
everything else, on the very first run.

Fixed to a word-boundary *prefix* match (`scar`), which blocks `discarded` while keeping
ordinary inflection: a full `…` match would have lost "mean"→"meant" and "stiff"→
"stiffened". Over 254 durable facts the two variants disagree on 9. After the fix,
*"Kai has scar"* locates to *"His scar ran along his palm"*, and 193 of 254 durable facts (76%)
have a locatable source.

**Three subagents found a bug that three rounds of my own reading had not.** That is the single
strongest argument in these two evenings for the instrument, and it arrived as a threshold failure.

## Verdict

**Recall passes: 8 of 10 with correct category, and 3 of 3 on the new category.** The precision
threshold is **unmeasurable as pre-registered**, because its negative controls were not negative.

Per the pre-registration's own terms — adopt iff recall ≥ 8/10 **and** spurious ≤ 3/10 — the
second condition cannot be evaluated, so **adoption is not claimed.** The instrument is
**conditionally usable for exactly one thing, stated narrowly:** producing a triage list a person
reads, where the operating assumption is that most flags are real and none is authoritative. On
tonight's evidence that assumption held — 7 of 10 clean-packet flags verified real, 3 traced to a
tool bug now fixed, 0 hallucinated.

**What must happen before any precision claim:** the blind adjudication this file promised, on a
set where clean truly means clean — which now looks like it requires *hand-verified* clean packets
rather than randomly drawn ones. That is a bigger job than one evening and is not smuggled into
this verdict.

## Real defects in a committed book, found as a by-product

Independently verified against the prose, none previously known:

**1. The wandering scar.** Kai's scar is on his **palm** (scenes 11, 14, 15, 16, 46, 47), his
**arm** (31, 32), his **wrist** (53), and his **temple** (40, 42, 56, 57, 66, 68, 70).
`check_threads` and the continuity checks are blind to this **by construction**: they key on
subject+predicate+object strings, so *"scar on palm"* and *"scar on his temple"* never collide as
the same claim. A wandering attribute is invisible to a string-keyed ledger check.

**2. The watch.** Beneath his shirt (30), beneath his sleeve (40, 60, 61), in his coat pocket
(57).

**3. Thirty years vs thirty days** inside scene 58, and **the file in two pairs of hands** inside
scene 39.

These are the most valuable output of the whole inspector line, and none of them came from a
verdict. They came from auditing flags instead of scoring them.
