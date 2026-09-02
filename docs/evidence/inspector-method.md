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

# Experiment A, results: 9 of 9 valid seeds caught exactly — and the verdict is still PARK

*20 trials, 20 fresh Fable-class subagents, one trial each, ~30–90 seconds apiece, zero GPU.*

## The raw tally

| | outcome |
|---|---|
| valid mutated trials | **9 of 9 flagged, every one naming the exact mutated fact with correct scene evidence** |
| invalid mutated trials | 1 — **my seed was defective**, see below |
| control trials | 9 of 10 CLEAN; 1 false alarm |
| false alarms total | **2** (one control, one on the invalid trial) |

Detection is not the problem. On every trial where a genuine incompatibility existed, the
inspector found it, named the right fact, and quoted the right span — attribute flips as quiet as
leather→cloth binding, glass→ceramic vial, silver→iron ring, aged→fresh ink.

## The two false alarms have one root cause, and it is mine

Both flagged **transient `state` facts from early scenes** against later scenes: *"Mir holds
ledger"* (scene 7) read as contradicted by Vay holding it in scene 20; *"Kai is holding a
satchel"* (scene 1) read as contradicted by a folder in his hand in scene 20. Possession moves;
neither is a genuine contradiction. The filler pool admitted `kind: state` facts, and the
instructions never said how to treat time-indexed states — while four other agents *did* reason
correctly about exactly this ("scene-state from earlier scenes is narrative progression, not
incompatibility"), so the behaviour is inconsistent where the task definition is silent.

## The invalid seed, named as the experimenter's error

P1's mutation turned *"Vay smells burnt wood and cedar"* (Vay perceives a scent) into *"Vay smells
of salt spray and citrus"* (Vay emits one). The scene's wind carrying a burnt-wood scent
contradicts neither. The inspector correctly declined to flag the seed — and then false-alarmed on
the satchel instead. The trial is excluded as invalid and not replaced tonight; the exclusion is
recorded here rather than the trial quietly redrawn.

## The verdict, per the thresholds fixed above

Hits clear the bar (9 of 9 valid ≥ 8-of-10 equivalent). **False alarms do not: 2 against a
ceiling of 1.** The pre-registered reading applies verbatim:

> **Park:** hits ≥ 8 but false alarms ≥ 2 — it sees truth but cries wolf; unusable for triage.

**PARKED.** Not adopted, not rejected. The fix is mechanical and named: sheets restricted to
durable facts (`detail`/`knowledge`, never bare `state`), and one instruction line telling the
inspector that early-scene states may have lapsed by the audited scene. Re-validation on fresh
pairs is required before any live use — the same thresholds, no third chance after that.

## What the night actually validated

Not the inspector — **the method**. One pre-registered validation run caught, before the inspector
touched a single live question: an experimenter's defective seed, a task-definition gap around
time-indexed facts, and inter-agent inconsistency exactly where the definition was silent. Every
one of those would otherwise have surfaced later as a mysterious wrong audit of real prose. The
cost was twenty subagent calls and an evening; LitBench's lesson — measure the judge before
believing it — held at every scale it was applied at.

# Experiment B, results: the direction survives a naive rater; the separation does not

*One fresh Fable-class subagent, zero project context, given only a key-stripped copy of the
sheet's own instructions and sentences. Ratings preserved in
[sentences/sentences-naive.md](sentences/sentences-naive.md); the blank sheet remains blank.*

| | current era | pre-prose-work | separates? |
|---|---:|---:|---|
| informed dry run (had read the codebase) | 2.12 [1.94, 2.30] | 1.64 [1.46, 1.82] | **yes** |
| naive rater (context-free) | 2.16 [2.00, 2.30] | 2.04 [1.96, 2.14] | **no — intervals overlap** |

**Prediction 1 half-holds and its wording was ambiguous — both recorded.** The direction is
preserved (current above pre, and again on the narrated-only split, 2.21 against 2.05). The
*separation* is gone. The pre-registration said the rater "separates the eras in the same
direction", which can be read as direction-only or as non-overlap; step 28's lesson about
pre-registrations stated two ways recurred here within the same day, in a single sentence. Scored
against the stricter reading: **failed**.

**Prediction 2 holds, on the second rater in a row:** no panel signal reaches |r| ≥ 0.3 — the
naive maximum is `words` at +0.12, and even `past_perfect`, the informed run's confounded
front-runner, collapses to +0.06. The 0-of-7 finding now stands on two independent machine raters.

**Prediction 3, the descriptive one:** inter-rater r = **0.518**, exact agreement 63/100. The
disagreement is structured, not noise: the naive rater compresses the bottom of the scale —
six 1s against the dry run's thirty (all six inside the dry run's thirty), 78 sentences parked at
2. The informed separation was carried by the low end, and a context-free rater will not go there.

## What this does to the dry run's caveat

It funds it. *"The rater has read this codebase — it is not a naive reader"* was listed as a way
the dry run could be wrong, and the first context-free replication moved the era gap from
0.48 to 0.12 points. Two readings survive tonight, deliberately not adjudicated by a third machine
run: project knowledge sharpened (or biased) the informed ratings, or naive raters simply compress
three-point scales and lose power. **Both machine data points now sit on the record for the human
sheet to break the tie — which is the only adjudication that was ever going to count.** The
prediction carried forward for step 33 is correspondingly weakened: direction, firmly; separation,
now genuinely uncertain.

---

# Round 2: the re-validation, designed before it ran

*Committed with the trials built and validated but **no inspector called**. The thresholds from
the top of this file are unchanged and are the last word — the pre-registration said "no third
chance after that", so this run adopts or rejects.*

## The two fixes, both aimed at the false alarms rather than at detection

Detection was never the problem (9 of 9 valid seeds, exact fact and quote). Both false alarms were
transient `state` facts read as binding on a later scene, so:

1. **Sheets carry durable facts only.** The filler pool is restricted to `kind: detail` and
   `kind: knowledge`; bare `state` facts — a scene-1 satchel, a scene-7 ledger-holder — are
   excluded entirely. 73 distinct filler lines across the ten sheets.
2. **The instructions name the failure.** One line added: *"A fact that describes a passing
   moment in an earlier scene may simply have moved on; report a contradiction only about durable
   properties."* Four of round 1's agents reasoned this way unprompted and two did not, which is
   what a silent task definition produces.

A third fix addresses **my** error rather than the inspector's:

3. **Every mutation is validated against the scene text before the trial exists.** Round 1's P1
   turned "Vay smells burnt wood" (perceives) into "smells *of* citrus" (emits) and contradicted
   nothing. `build2.py` now asserts the scene literally contains the phrase the mutation
   contradicts, and refuses to build the trial otherwise.

## The ten fresh pairs

Fresh scenes (5, 6, 8, 26, 27, 29, 32, 35, 40, 42 — none used in round 1) and fresh objects, each
a concrete durable physical attribute the scene verifiably asserts:

| id | scene | fact as the book has it | mutated to |
|---|---:|---|---|
| Q1 | 5 | The speaker wears a threadbare coat, sleeves rolled up | The speaker wears a heavy fur-lined coat, its sleeves buttoned tight at the wrists |
| Q2 | 6 | The map is brittle and covered in symbols and markings | The map is blank on both sides, bearing no symbols or markings at all |
| Q3 | 8 | A clay lamp hangs near the ceiling of the room | The room has no lamp of any kind; its only light is a bare electric bulb |
| Q4 | 26 | Vay keeps vials among the stacks in the archive | Every vial was destroyed years ago; none remain anywhere in the archive |
| Q5 | 27 | The vial glows | The vial is dark and gives off no light whatsoever |
| Q6 | 35 | The iron ring is etched with markings | The ring is smooth gold, entirely unmarked |
| Q7 | 40 | The old ledger's parchment is brittle and crinkles when moved | The ledger's pages are supple modern vellum, silent when turned |
| Q8 | 42 | Kai has a scar running along his temple | Kai's face and temple are unmarked; he has no scar there |
| Q9 | 32 | The worn map rests on a low wooden stool | The map is pinned to the wall and never rests on furniture |
| Q10 | 29 | The official's collar hangs loose, frayed threads near the seam | The official's collar is starched stiff and immaculate, without a loose thread |

Same design otherwise: 20 trials, one fresh Fable-class subagent each, no agent sees more than one
trial, strict scoring (a hit must name the mutated fact).

## Round 2 results: 10 of 10 detection, 2 false alarms — REJECTED as designed

*All 20 trials returned. Scored against the thresholds fixed at the top of this file, which said
this run was the last.*

### Detection: perfect, for the second round running

| | |
|---|---|
| mutated trials flagged | **10 of 10** |
| naming the exact mutated fact | **10 of 10** |
| with a correct scene quote | **10 of 10** |

Across both rounds that is **19 of 19 valid seeded contradictions**, every one correctly attributed.
Blank-vs-symbol map, gold-vs-iron ring, vellum-vs-brittle-parchment, immaculate-vs-frayed collar —
none was missed and none was misattributed.

### The durable-fact fix worked, and a different failure took its place

**Zero** false alarms of round 1's kind: no transient-state fact was read as binding on a later
scene. That fix is confirmed.

Two controls flagged anyway, and neither is noise:

- **Q2-ctl** flagged *"Kai is aware of the donor is dead"* against scene 6's *"if I find the
  donor — if there even is one"*. Audited against the prose: scene 1 says the donor was dead
  *"anyway. **Not literally, not exactly**"*. **The ledger's own extraction dropped the hedge**
  and recorded a figurative line as a flat fact. The inspector found a real defect — in the fact
  ledger, not the prose.
- **Q8-ctl** flagged *"Kai has a scar running along his temple"*, which the scene restates
  verbatim — and then locates *"flaring faintly beneath his shirt collar"*. A temple scar cannot
  be under a collar. **The inspector found a real defect — an incoherent sentence.**

**Both score as false alarms, and that is the correct scoring.** The question asked was *does the
scene contradict a listed fact*. In Q8-ctl the scene asserts the listed fact; in Q2-ctl the
mismatch is between the ledger and the prose, not between the scene and a fact the book
established. Each answer is about something real and neither answers the question.

### The verdict

    hits         10 of 10   — clears the bar
    false alarms  2 of 10   — ceiling was 1

**Failed. And the pre-registration said no third chance, so the continuity inspector as designed
is REJECTED**, not parked. `checks.PORTABLE`-style adoption does not happen; nothing in this
project consults it.

*The one scoring that would flip this — excluding Q2-ctl as an invalid control, since its sheet
misrepresented the book — is available and is **not** taken. It would give 1 false alarm in 9 and
an adopt. But step 28's lesson was to score against the stricter reading of an ambiguous
pre-registration, and "any CONTRADICTION on a control trial" is not ambiguous. Recording that the
verdict hinges on this classification, and that the strict side was chosen.*

### Why the rejection is a design result and not a dead end

The failure mode is fully diagnosed, and it is not hallucination: **across 40 trials in two
rounds, every single flag pointed at something genuinely wrong.** Four pointed at transient facts
the sheet should not have contained, two at defects the question did not ask about. The instrument
does not invent problems; **it answers a broader question than the one it is given, and a
false-alarm ceiling of 1-in-10 is the wrong specification for that behaviour.**

So the successor is a different instrument, needing its own pre-registration and not inheriting
this one's adoption:

- an **inconsistency finder**, not a contradiction detector — output triaged by a person, with an
  explicitly loose precision target and recall as the metric that matters;
- fed the ledger *and* the prose, since two of the six real findings were about the ledger rather
  than the scene;
- never gating, per rule VI, which is unchanged.

### One real defect class, deliberately left unquantified

The donor case suggests the extractor flattens hedged prose into flat facts. A scan for facts
whose surrounding prose carries a hedge returned 116 candidates — **and auditing the sample shows
most are not mis-extractions at all** ("stepping aside" beside an unrelated *as if*). The scan is
loose, the way the vacuous ones in this project's history were loose. **One instance is verified;
the class is plausible and unmeasured, and no number for it is published here.**

### What the two evenings cost and bought

Forty subagent calls, zero GPU, one shipped instrument rejected on its own evidence — and along
the way: an experimenter's defective seed, a task-definition gap, inter-agent inconsistency, a
ledger mis-extraction, and an anatomically impossible sentence in a committed book. Every one of
those was found *because* the method insisted on scoring the judge before believing it.
