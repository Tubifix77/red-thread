# Step 28 — the model-refrain list: killed at n=2, kept at n=4

*2 September 2026, 02:35. Two ablated runs of the *Debt of Years* plan, 71 scenes each, no halts,
against the four-run floor. Guard verified on disk and in git before launch. Pre-registration:
[step28-preregistration.md](step28-preregistration.md), committed while the runs stood at 10 of
142 scenes.*

## The pre-registered criterion fired

| measure | list ON | **OFF** | floor | |
|---|---:|---:|---:|---|
| `duplication_manuscript` | .052 | .058 | 19% | **inside, at 11%** |
| `repetition_concentration` | .030 | .037 | 38% | **inside, at 21%** |

**Both inside. The kill criterion fires, and it is recorded as having fired.**

The secondary targeted statistic, also pre-registered, agrees:

| | per 10k words |
|---|---|
| list ON (n=4) | 5.61, 5.87, 4.74, 6.16 · **mean 5.59** |
| list OFF (n=2) | 6.73, 7.59 · **mean 7.16** |

Difference **24.61%** against a **25.00%** floor. Inside.

*Everything else in the panel points the same way and none of it clears: `worst_refrain` 9.75 →
14.00 (36% against a 52% floor — and rule III forbids resting anything on a maximum), and
`dialogue_share` cleared at 13% against 11%, which no story about a three-phrase prohibition
explains and which is the same unexplained mover that appeared in step 6's ablation.*

## An error in my own pre-registration, named before anything else

The prediction was written two ways that do not agree: *"by more than the 25% floor"* and
*"i.e. above ~7.0 per 10k"*. The second is wrong arithmetic. Solving the floor test properly, the
ablated mean had to exceed **7.187**; the observed 7.159 is above 7.0 and below 7.187.

The operative form is the floor test — it is what `clears_noise` does everywhere in this project
and what the criterion names. The gloss was a convenience that happened to be generous by
0.19 per 10k. **A pre-registration stated twice is a pre-registration that can be read two ways
afterwards, and this one was.** State one form next time.

## Why the deletion is suspended rather than executed

Two facts about the margin, and neither is an argument that the mechanism works.

**The miss is smaller than one occurrence of one phrase.** To clear, the two ablated books would
have needed a combined **0.34 more** uses of *"the edge of the"*, *"the weight of the"* or *"eyes
fixed on the"* — across 121,536 words. A verdict that turns on a third of a single phrase is a
statement about the instrument's resolution, not about the mechanism.

**The design could not have confirmed, by construction.** With four control runs and two ablated,
a rank test's *smallest achievable* one-sided p is 1/C(6,2) = **0.067**. The data give perfect
separation — every ablated run exceeds every control run — and perfect separation still cannot
reach 0.05 here. So on that statistic the experiment had exactly one possible outcome before it
was run.

That is [step 27](two-run-screen.md)'s protocol arriving four hours too late for its own plan:
**an n=2 screen may kill and may never confirm.** Step 28 was designed before step 27 was
measured, and it is an n=2 screen. The kill it produced is exactly the outcome such a screen is
licensed to produce — which is why the kill is recorded, and why acting on it before n=4 would be
treating a screen as a confirmation in the one direction the protocol does not warn about.

**So: the criterion fired, the verdict is recorded, and the deletion waits for two more runs.**
Precedent is step 6, where a documented kill was suspended and then reversed at n=4; the lesson
recorded there was that deleting is cheap later and reversing a published deletion is not. Two
runs are about two GPU-hours.

## What n=4 decides — written now, before those runs exist

This is the whole point of writing it before the data, and it is deliberately unfavourable to the
mechanism:

- **Targeted rate still inside the 25% floor at n=4** → the list comes out of the brief. No third
  look. The data file stays as a measurement.
- **Targeted rate outside at n=4, panel still inside** → the list stays, restated honestly as a
  *narrow three-phrase filter* and not a repetition mechanism, and PLAN2's claim for it shrinks to
  that. This is the outcome the pre-registration already anticipated and it does not become a
  quality result.
- **Panel measures outside at n=4** → the primary criterion answers on its own terms.

No other statistic will be introduced. In particular the rank test is **not** promoted to primary:
it is reported because perfect separation is worth seeing, and at n=4 vs n=4 its floor becomes
1/C(8,4) = 0.014, which is the only reason a rank test is worth computing at all at that point.

## The n=4 result: the list stays, and the screen was wrong

*Written after the section above was committed and before these runs existed — which is what makes
this a test rather than a story. Two more ablations, 71 scenes each, no halts, guard re-checked at
their own start rather than inherited from the earlier chain.*

**Primary criterion, unchanged in its verdict:** `duplication_manuscript` 12% against a 19% floor,
`repetition_concentration` 14% against 38%. Both still inside. Nothing in the panel clears.
**The list does not move book-level repetition, and that is now settled at n=4.**

**Secondary, targeted — and it reverses:**

| | per 10k words |
|---|---|
| list ON (n=4) | 5.61, 5.87, 4.74, 6.16 · **mean 5.59**, spread 25% |
| list OFF (n=4) | 6.73, 7.59, **12.15**, **9.48** · **mean 8.99**, spread 60% |

Difference **46.6%** against the 25% floor — **outside**. Perfect separation again, and now it
means something: exact one-sided rank-sum **p = 0.0143**, where at n=2 the smallest achievable
value had been 0.067.

Per the reading committed in advance: *panel inside, targeted rate outside → the list stays,
restated honestly as a narrow three-phrase filter and not a repetition mechanism.* **That is the
verdict. The list stays, and PLAN2's claim for it shrinks to what was measured: it suppresses its
own three constructions and does nothing detectable to how much the book repeats itself.**

### The screen produced a false negative, and the protocol said it could not

This is the uncomfortable part and it belongs at the top of the correction, not the bottom.

[Step 27](two-run-screen.md) concluded *an n=2 screen may kill and may never confirm*, on 72
verdict tests with **15 false positives and 0 false negatives**. Step 28 at n=2 killed. Step 28 at
n=4 confirms. **That is a false negative from exactly the kind of screen the protocol licensed to
kill.**

The protocol is not wrong; **my application of it was**, and the flaw is visible in step 27's own
method. That analysis varied the *control floor* — every 2-run subsample of the four control runs
— while computing each condition's mean from its **full** group. It measured what a two-run
**floor** does. It never varied the **condition** group size, and never could have: the
conditions it had were the ones on disk.

Step 28's n=2 was on the **condition** side. Its ablated mean was estimated from two books at 6.73
and 7.59; the other two came back at 12.15 and 9.48. The mean moved 7.16 → 8.99 and the spread
came out at 60%, well over twice the control's. A two-run estimate of a mean that unstable is not
a screen at all.

**So the protocol's scope is narrower than its wording:** *a two-run **floor** may be used to kill;
a two-run **condition** may not be used for anything.* Step 27's sentence has been corrected
there.

### What saved it was precedent, not the protocol

Acting on the protocol as written would have deleted a mechanism that demonstrably does the narrow
thing it was built to do. What prevented that was step 6's precedent — *deleting is cheap later,
reversing a published deletion is not* — applied because the margin was 0.34 phrase occurrences
and the design could not have confirmed. **Both of those were reasons to distrust the design, not
reasons to believe the mechanism**, and they were enough.

That is now twice a documented kill has been suspended on that precedent and twice the re-test
reversed it. A third instance would stop being a happy accident and start being evidence that
kill criteria in this project are systematically underpowered at n=2.

## What is already settled, whatever n=4 says

**With the list on, its own three phrases still appear 5.59 times per 10,000 words** — about once
every two scenes. The prohibition is explicit, it arrives in every brief of every scene, and it is
not obeyed. Whatever the difference turns out to be, the absolute level says this mechanism is at
best partial, and that needed no ablation to see.
