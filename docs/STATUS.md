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
| 2 | Is the prose free of the obvious machine tells? | **mostly** |
| 3 | Is the finished book worth reading? | **not started** |

**1 — Close.** Five books, 65 scenes, 74,156 words, zero API calls. It plans, drafts, checks,
repairs, commits, and resumes after a crash. Each *new premise* has still cost one to three code
fixes; the most recent five scenes needed none. It finishes books. It has not yet finished a
brand-new book unassisted.

**2 — Mostly.** Three tells that fired in roughly half of all early scenes now fire in none.
Repeated phrasing is down 65%. One measured axis has barely moved.

**3 — Not started.** Nothing in 28 checks and 446 tests has an opinion about whether a scene is
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
| Recap grammar (`summary_distance`) | .28 | **.25** | .10 |

Four of the five are closed or nearly closed. The fifth is the honest one: **past perfect is
measured, is named in the brief with the numbers attached, and it barely moved.** The model is
told not to write recap and writes it anyway. That is a missing repair route, not a missing check
— it is the only measured axis with no way to fix what it finds.

---

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
| Scene checks | built | 28 checks; thresholds set from a 91-scene corpus, never from taste |
| Repair ladder | built | 10 rungs, narrowest first; a test asserts every blocking kind has a repair that can reach it |
| Resume after failure | built | five books finished; restart picks up at the last committed scene |
| Candidate selection | partial | ranks on violations, then duplication, then recap, then length — blind to repair cost |
| Redraft on exhaustion | partial | fires, but a fresh draft is not reliably better than the one it replaces |
| Recap-grammar repair | **missing** | the one measured axis with no route to fix it |
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
| **446** | tests passing |

The longest is 30,147 words — a novella, not a novel. Nothing here has been run at 60,000 words,
and the failure modes that matter at that length (a thread that quietly stops mattering, a middle
that sags for eight scenes) are exactly the ones no check can see.

---

## The short answer

The orchestrator is close to shippable. The writer is not. What remains is not a list of bugs — it
is one unanswered question about whether a plan can be made dramatic enough that a small local
model has something worth writing about. Everything measured says the plumbing works. Nothing
measured says the book is good, because nothing measures that.
