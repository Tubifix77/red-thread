# Where this stands

*Measured 29 August 2026. All figures from `runs/` and `docs/evidence`; nothing here is an estimate.*

A percentage would be a lie, because three separate things are being built and they are at very
different places. This document is the honest read on each.

Illustrated version: <https://claude.ai/code/artifact/9ef610d1-1ca6-4a0f-a937-1529ad68978c>

---

## Three questions, not ten steps

| | Question | State |
|---|---|---|
| 1 | Can it get to the end of a book without help? | **close** |
| 2 | Is the prose free of the obvious machine tells? | **partly** |
| 3 | Is the finished book worth reading? | **not started** |

**1 — Close.** Five books, 65 scenes, 74,156 words, zero API calls. It plans, drafts, checks,
repairs, commits, and resumes after a crash. Each *new premise* has still cost one to three code
fixes; the most recent five scenes needed none. It finishes books. It has not yet finished a
brand-new book unassisted.

**2 — Partly.** Three tells that fired in roughly half of all early scenes now fire in none,
and repeated phrasing is down 65%. Recap grammar has not moved, was being under-measured, and is
now the dominant defect — it has repairs as of today but no evidence yet that they close it.

**3 — Not started.** Nothing in 29 checks and 458 tests has an opinion about whether a scene is
interesting. This is the distance.

---

## What the checks can see

Three cohorts:

- **before** — n = 50 scenes across *The Debt of Years*, *The Register of Kvitmyr* and the first
  unattended run, drafted before the prose checks landed. Mean scene length 1,126 words.
- **now** — n = 5 scenes written under the full check set (`runs/now`, scenes 4–8).
- **reference** — n = 3 single cold scenes from gemma3:12b, phi4:14b and qwen3:8b with no
  orchestration at all (`docs/evidence`). Mean length 665 words. A reference, not a ceiling.

| Signal | before | now | reference |
|---|---:|---:|---:|
| Narrator glossing the theme (share of scenes) | 58% | **0%** | 0% |
| Stacked possessive absolutes (share of scenes) | 52% | **0%** | 0% |
| Rhetorical triples (share of scenes) | 42% | **0%** | 0% |
| Repeated phrasing (`duplication_ratio`) | .340 | **.118** | .009 |
| Recap grammar (`summary_distance`) | .420 | **.376** | .105 |
| Scenes carrying a block of 4+ past-perfect sentences | 70% | **60%** | 0% |

Three tells are gone and repeated phrasing is down 65%. Recap grammar is the honest one, and it
is worse than this document first claimed.

### Correction, 29 August

The first version of this page reported recap grammar at .28 → .25. That was measured with a
regex that missed two whole classes of past perfect: an adverb between the auxiliary and the
participle (*had never seen*, *had already gone*), and irregular participles that were simply
absent from the list (*had hung*, *had held*, *had stood* — the last of which one live scene
repeated nine times). Corrected, the committed corpus sits at a median of **.382**, not .245,
and the worst scene narrates 97.9% of its sentences at distance.

So the axis did not "barely move". It **has not meaningfully moved at all**, and it is the
dominant remaining defect in the prose. The numbers above are the corrected ones.

### What was done about it

The register really is unrepairable — switching one sentence to simple past leaves the other
forty alone — but that was the whole of the analysis, and it hid the half that is reachable.
Measuring the *distribution* rather than the density splits the problem: past perfect arrives in
**blocks**. 68 of 107 committed scenes carry a run of four or more consecutive past-perfect
sentences; one carries forty-six; the three reference drafts top out at two, and none reaches
three. A run has edges, so a passage repair can replace it.

`check_recap_block` (MAJOR, one violation per block) now finds them, and two repairs reach them:

- **`unrecap`** rewrites the block as scene, verified by the check that flagged it. Confirmed
  against Ollama on a live scene: two blocks down to one, density .415 → .360.
- **`cutrecap`** deletes the block outright, no model call, when the rewrite fails — which it
  does, because told in four numbered rules not to use past perfect, qwen3:8b returns past
  perfect. A block of recap is by definition not the scene, so what is lost is length, and
  length has a repair of its own. It refuses to cut a scene below 75% of its words: past that
  point the draft is the problem and the redraft path is the right answer.

Finding this route surfaced three pipeline bugs that had nothing to do with recap:

1. **Progress was measured by kind, not count.** A repair counted as having done its job only if
   its target kind vanished entirely. `unrecap` correctly cleared one of two blocks and was
   discarded as "no improvement", twice, then sidelined. Now the count has to fall, not the kind
   disappear.
2. **A capped check cannot be used to measure progress.** `check_recap_block` originally reported
   at most three blocks. A live scene held seven, so deleting one still reported three, and every
   correct repair looked like a no-op. It is now uncapped — the only per-occurrence check here
   that is.
3. **Passage-scoped kinds could still reach sentence surgery.** Once `unrecap` was sidelined,
   `recap_block` fell through the ladder to `surgical`, which rewrote one sentence of a
   six-sentence run three times over. Seams had been guarded against exactly this by an early
   return since a run in July; `PASSAGE_SCOPED` is the general form of that guard.

### One hypothesis, refuted

Scene 9 of a live run collapsed completely on qwen3:8b — "she had not asked" 77 times in 1,490
words, a 46-sentence run of past perfect, every draft unusable. Its four beats are *watches and
notes*, *admits*, *reflects on*, and *is revealed to be*: nobody does anything. The obvious
reading is that a beat with no event gives the model nothing to dramatise, so it recaps.

Measured across all 108 scenes that have both a spec and prose, the correlation between the share
of a scene's beats using a cognition or state verb and its recap density is **r = 0.141** — the
group means move in the right direction (.378 → .410 → .466) but the top group is n = 3 and the
relationship is negligible. Against duplication it is r = 0.006.

Not enough to build a plan check on, so nothing was built. The scene 9 collapse remains
unexplained.

## What nothing can see

These are not failing checks. There are no checks. Each is decided by whichever local model
happened to draft the scene, with no gate, no repair, and no record of whether it went well.

- Does a character want something, and act on wanting it?
- Does the middle earn the ending — causally, not just sequentially?
- Is a scene interesting? Would a reader turn the page?
- Is any sentence worth rereading?
- Does the book have a subject beyond restating its premise?

> Everything measurable about the prose is close to done. Everything that makes prose worth
> reading has no measurement at all.

That asymmetry *is* the answer to "how far". These rows are empty **by design**: the rule that
keeps the orchestrator honest — never gate on something code cannot check — also forbids gating
on quality, and it is right to. A small model's opinion of a story does not get to stop the book.

So the way through is probably not a checker. It is the **plan**. If a scene spec carries real
want, real obstacle and real cost, the drafting model has something to dramatise. Right now the
planner emits beats that are structurally valid and dramatically inert, and no test can tell the
difference.

---

## Machinery

| Part | State | Note |
|---|---|---|
| Plan & thread state machines | built | Pre / Post / Forbid per scene, audited before a word is written |
| Commit gate & ledger | built | nothing enters memory until the scene passes |
| Scene checks | built | 29 checks; thresholds set from a 91-scene corpus, never from taste |
| Repair ladder | built | 10 rungs, narrowest first; a test asserts every blocking kind has a repair that can reach it |
| Resume after failure | built | five books finished; restart picks up at the last committed scene |
| Candidate selection | partial | ranks on violations, then duplication, then recap, then length — blind to repair cost |
| Redraft on exhaustion | partial | fires, but a fresh draft is not reliably better than the one it replaces |
| Recap-grammar repair | built | `unrecap` rewrites a block, `cutrecap` deletes it; verified live |
| Dramatic planning | **missing** | beats are valid and inert; want, obstacle and cost are not modelled |
| Any judgement of quality | **missing** | by design, and the design is now the constraint |

---

## On the board

| | |
|---:|---|
| **5** | books finished end to end |
| **74,156** | words drafted locally |
| **65** | scenes committed |
| **0** | API calls |
| **458** | tests passing |

The longest is 30,147 words — a novella, not a novel. Nothing here has been run at 60,000 words,
and the failure modes that matter at that length (a thread that quietly stops mattering, a middle
that sags for eight scenes) are exactly the ones no check can see.

---

## The short answer

The orchestrator is close to shippable. The writer is not. What remains is not a list of bugs — it
is one unanswered question about whether a plan can be made dramatic enough that a small local
model has something worth writing about. Everything measured says the plumbing works. Nothing
measured says the book is good, because nothing measures that.
