# Two mechanisms, ablated

*1 September 2026. Four control runs and two per condition, same plan, same code, one switch
flipped. Ten GPU-hours, no API calls. The first time a mechanism in this project has been tested
against its own absence.*

Both mechanisms were built on a single-run observation and shipped without evidence. Phase 1
existed to confirm or delete them, and it did one of each.

## Step 5 — the refrain feedback stays

Naming a book's own repeated phrases in the next scene's brief.

| measure | feedback on | **off** | floor | |
|---|---:|---:|---:|---|
| `repetition_concentration` | .030 | **.047** | 38% | **clears at 44%** |
| `worst_refrain` | 9.8 | **20.5** | 52% | clears at 71% |
| `somatic_share` | .373 | .486 | 19% | clears at 26% |
| `duplication_manuscript` | .052 | .058 | 19% | inside |
| `gesture_rate` | 1.88 | 2.04 | 22% | inside |
| `dialogue_share` | .202 | .207 | 11% | inside |

**The kill criterion was concentration inside the floor. It is outside, at 44% against 38%, so
the mechanism stays.** Turning the feedback off makes repetition measurably worse, and it is the
measure the criterion named rather than one chosen afterwards.

`worst_refrain` doubling from 9.8 to 20.5 points the same way and is the more visible number —
which is exactly why it is not the one the verdict rests on. Rule III: it is a maximum, it swings
52% between identical runs, and the plan wrote the criterion against concentration for that
reason before any of this was measured.

*`somatic_share` also cleared, which nobody predicted and no mechanism explains. With three
measures clearing out of eleven and a floor from one plan, one unexplained mover is what chance
looks like. Recorded, not interpreted.*

## Step 6 — the gesture feedback: criterion failed, mechanism kept

Naming a book's own repeated small movements in the next scene's brief.

| measure | feedback on | **off** | floor | |
|---|---:|---:|---:|---|
| `gesture_rate` | 1.88 | **2.00** | 22% | **inside, at 6%** |
| `somatic_share` | .373 | .391 | 19% | inside |
| `recap_grammar` | .035 | .038 | 59% | inside |

**The kill criterion was a difference inside the floor. It is inside, at 6% against 22%.** The
mechanism has machinery, prompt weight in every brief, and no measurable return.

Two caveats, both of which weaken the test rather than the verdict:

**The ablated runs are shorter.** Both halted — at 66 and 48 scenes of 71 — so the comparison is
71 against a mean of 56. `gesture_rate` is a per-scene mean and does not grow with length, but the
*feedback's* effect should: it only names a movement once it has recurred across four scenes, so
a 48-scene book received less of the treatment than a 71-scene one. **This is a weaker test than
intended, and in the direction of finding nothing.**

**`dialogue_share` cleared its floor here** (.202 → .230, 13% against 11%), which no story about
gesture feedback explains and which the length difference could easily produce. It is not evidence
for the mechanism and it is not evidence against it.

On this statistic the mechanism earns nothing, and that was the criterion. What happened next is
in the section below: the caveat turned out to be real, and the whole-book mean cannot see the
effect the mechanism was designed to have. **The kill stands on its own criterion; the deletion
is suspended.**

## Step 6 again: the verdict is suspended, and why that is not moving the goalposts

After recording the kill, I checked whether the caveat above was real — whether a mechanism that
only names a movement *after four recurrences* shows an effect that grows across a book. It does,
and the whole-book mean cannot see it.

| run | gesture rate, Q1 → Q4 | feedback |
|---|---:|---|
| floor1 | **−23%** | on |
| floor2 | **−42%** | on |
| floor3 | **−42%** | on |
| floor4 | **−54%** | on |
| norefrain1 | +1% | on |
| norefrain2 | **−33%** | on |
| nogesture1 | +11% | **off** |
| nogesture2 | −12% | **off** |

Six runs with the feedback on fall by **32% on average** from first quarter to last. The two
without it are flat, −1%. Both off-runs rank 6th and 8th of the eight; the chance of that by
coincidence is about **11%**.

**Suggestive, not established, and post-hoc.** The overlapping ranges are the problem — one
feedback-on run rose 1% and one feedback-off run fell 12% — and n=2 on the ablated side cannot
carry it. More importantly, **this statistic was chosen after the pre-registered one failed**,
which is the shape of every result this project has had to retract.

Two things keep it from being goalpost-moving, and they should be weighed rather than accepted:

- The accumulation prediction follows from **how the mechanism is built**, not from the data. It
  names a movement only once it has recurred across four scenes, so an effect that grows with book
  length is what it was designed to produce. That is a prediction one could have written down
  first — and nobody did.
- It is being treated as a **new hypothesis requiring its own test**, not as a result. The kill
  criterion is not being reinterpreted and the mechanism is not being declared to work.

**So the deletion is suspended pending two more ablation runs**, taking that side from n=2 to
n=4. Deleting is cheap to do later; deleting something that works, and then reversing a
documented verdict, is not. If the trajectory difference does not survive n=4, the mechanism goes
on the original criterion.

### The n=4 result: it survives, and the mechanism stays

*Written after the paragraph above was committed and before the confirming runs existed, which is
what makes the rest of this section a test rather than a story.*

Two more ablations were written, and resuming the two that had halted completed them at 71 scenes
each — so the length confound is gone as well. **Their published figures changed in the process**:
nogesture1 went from +11% to +14% and nogesture2 from −12% to +24% once they reached full length.
The tables above are the 66- and 48-scene versions and are left as they were.

| | gesture rate, Q1 → Q4 |
|---|---|
| feedback on (n=6) | −23, −42, −42, −54, +1, −33 · **mean −32%** |
| feedback off (n=4) | +14, +24, −22, +4 · **mean +5%** |

The four off-runs rank **6th, 8th, 9th and 10th of ten**. Exact one-sided rank-sum **p = 0.010**,
and **p = 0.024** if the run that halted at 32 scenes is dropped for having only a third of a book
to show a trajectory across.

Meanwhile the pre-registered statistic still says nothing: whole-book `gesture_rate` 1.88 against
2.13, a 12% difference inside the 22% floor, at n=4 as at n=2.

**So the mechanism stays.** Not because the criterion was reinterpreted after the fact — it
failed, and it is recorded as having failed — but because a second hypothesis was written down,
its test specified, and then confirmed on data collected afterwards.

*The one thing that would make this untrustworthy is if the second statistic had been tuned. It
was not: `(Q4 − Q1) / Q1` on quarters is what the earlier section describes and what this
computes, unchanged.*

*What this really exposes is a gap in the plan rather than in the mechanism: the criterion named
a statistic that could not see the effect the mechanism was designed to have. A kill criterion is
only as good as the measure it names, and choosing that measure is the part that has to be got
right before the GPU hours are spent, not after.*

## Why one criterion saw its effect and the other could not

The two mechanisms are built the same way: each names a thing in the next brief only *after* it
has recurred a few times. So both should produce an effect that grows across a book. One criterion
saw that and the other did not, and the difference is not the mechanism.

    step 5   repetition_concentration   a manuscript-level measure — it aggregates across
                                        every scene, so accumulation is already in the number
    step 6   gesture_rate               a mean of per-scene rates — which averages the
                                        accumulation away by construction

Checking the refrain feedback through the same accumulation lens confirms it, weakly: concentration
rises 7% from first quarter to last with the feedback on and 34% with it off, across the same eight
runs. Directionally right, far too noisy to rest anything on, and it does not need to be — **the
pre-registered whole-book comparison already cleared the floor.** That is what a well-chosen
statistic buys.

**The generalisation:** a mechanism that acts by accumulation needs a measure that accumulates. A
per-scene mean is the wrong instrument for it however carefully the floor is measured, and no
amount of replication fixes a statistic that cannot see the effect. This is now rule VII.

## The halts, and a log that lied

Two of eight post-fix runs halted, both in the gesture condition — 0 of 4 control, 0 of 2 refrain,
2 of 2 gesture. That looks alarming and the causes say otherwise:

    nogesture1  scene 66   somatic_emotion + thematic_gloss, 5 attempts
    nogesture2  scene 48   continuity_contradiction — "a watch with a cracked face"
                           at scene 10 against "a watch with age spots" at scene 48

Neither is a gesture. The second is the system working exactly as designed: a genuine
contradiction the writer introduced, caught by the ledger, refused rather than committed. And
the length distributions are indistinguishable across all six runs — mean 1.03 to 1.05 of target,
6–9% over tolerance — so the ablation did not make scenes run long.

**And `replicate` reported both halts as `length`, which is not what either record says.**
`SceneResult.violations` and `Scene.violations` are separate lists, and it is the scene's that
`Project.save` writes; the halt report read the other one. A log that disagrees with the file on
disk is worse than no log, because it sends you looking in the wrong place — this one nearly
bought a false story about the ablation causing length failures.

## What phase 1 establishes

**Both mechanisms stay, and one of them nearly did not.**

The refrain feedback was confirmed on the statistic its criterion named. The gesture feedback
*failed* the statistic its criterion named, and was saved by a second one — written down before
the confirming runs existed, and significant at p = 0.010 on them.

That is what the phase was for, and it is the first evidence either mechanism has ever had. It is
also the strongest argument in this project for rule VII: had the plan named a per-scene mean and
stopped there, a working mechanism would have been deleted with a clean conscience and a
documented criterion.

What it does not establish: that either result transfers to another book. The floor, the control
and both conditions are all *The Debt of Years* at 71 scenes.
