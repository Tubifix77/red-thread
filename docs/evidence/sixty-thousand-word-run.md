# The Debt of Years at 60,000 words

*30 August 2026. 71 scenes, 61,733 words, `qwen3:8b` in every role, RTX 3080 10GB, zero API
calls. All four threads at terminal state.*

The scale test this project has been listing as its largest gap since the first manuscript. A
known premise was used deliberately, so the experiment measures *length* rather than confounding
it with novelty. Twice the longest previous run and eight times the length of the book written
the day before.

## What it found

Four halts, and the interesting thing is that three of them are one bug.

**Scenes 37 and 49 — the ledger arguing with the story.** A BLOCKER on `Vael | is carrying | a
blade` from scene 27 against `carrying | a bundle`, and twelve scenes later on `Vael | is |
holding a dagger` against `is | touching the hilt`. Ten and twenty-two scenes apart, a character
who has put one thing down and picked another up is not a contradiction; it is the story. The
judge was asked and said contradiction, which is what a judge will always say to two different
objects — it has no notion of elapsed time.

`is_moveable_pair` already made this argument for where a thing *is*; `is_possession_pair` now
makes it for who is *holding* it, matched across the predicate and object together. The first
version read only the predicate, which is why the same run halted on it twice. Measured through
the real grouping over every ledger in the project: 2,868 candidate pairs reach the judge without
the guard, 2,849 with it — 19 suppressed, 0.7%.

**Why only at this length.** Across every ledger in the project there are 35 possession facts and
three subject-and-predicate keys carrying more than one object. A nine-scene book never meets
one; a character barely has time to put something down. This is what the cross-scene machinery
looks like when it is finally under load.

**Scene 68 — not a defect at all.** Rejected on three uses of "you" outside dialogue. Re-run with
the same brief, plan and settings, it committed in three drafts with no repairs. Nothing had
changed but the sampling. `write_all` now gives a held-back scene one second whole attempt before
stopping — one, never a loop, because a scene that fails twice is failing for a reason and
grinding is how an unattended run spends the night on scene 40.

## The finding that only length could produce

| | per scene | across the manuscript |
|---|---:|---:|
| duplication, 9-scene book | .000 | .015 |
| duplication, this book | **.001** | **.041** |

Forty times higher across the book than within any scene in it. **Every scene is individually
clean and the book is repetitive.** "The blade at his side" appeared in 8 separate scenes,
"in the space between them" in 6, "the hilt of the blade" in 5.

No per-scene check can see this and no repair can fix it: nothing applied to scene 37 removes a
phrase from scenes 4, 9 and 22. So `manuscript_refrains` now feeds the book's own emerging
refrains into the next scene's brief — prevention, in the only shape a cross-scene defect allows.
It landed at scene 49 of this run, which makes the run its own experiment.

### It works, and it is not enough

Of the ten phrases handed to scene 49 onward, **seven never appeared again**, and the other three
collapsed:

| phrase | scenes 1–48 | scenes 49–71 |
|---|---:|---:|
| the blade at his side | 8 | **0** |
| in the space between them | 6 | 2 |
| around the edge of the | 5 | **0** |
| the hilt of the blade | 5 | 1 |
| a pause stretched between them | 4 | **0** |
| casting long shadows across the | 4 | **0** |

And yet, comparing equal 23-scene windows so the counts are comparable:

| window | refrains | duplication across the window |
|---|---:|---:|
| scenes 1–23 | 11 | .027 |
| scenes 24–46 | 5 | .019 |
| scenes 49–71 *(with the fix)* | **12** | .022 |

The window with the fix has the most refrains of the three. Twelve new ones formed —
"the scar along his wrist" in 6 scenes, "the weight of thirty years" in 6 — none of them on the
list, because none had any history to be listed from.

**Lowering the threshold does not help, and this was tested rather than assumed.** Rebuilding the
list at scene 48 with a threshold of two scenes and a cap of sixty entries would have caught
**1 of the 12** refrains that later formed. They are genuinely new phrasings, unpredictable from
what came before.

So the honest reading: naming a book's current refrains suppresses those refrains and the model
settles into different ones. The mechanism is worth keeping — it stopped a phrase that had
reached 8 scenes, and a book with 12 refrains of 6 is better than one with 33 including one of 8
— but it is not a solution to manuscript repetitiveness. That remains open, and it is the same
shape as the gesture finding from the day before: ban the phrase and the model rewords the image.

## Prose across the whole book

| | this book | reference drafts |
|---|---:|---:|
| duplication, per scene | .001 | .009 |
| recap grammar | .075 | .105 |
| blocks of recap, all 71 scenes | **0** | 0 |
| gesture rate | **2.3** per 1k | 1.3–1.4 |
| scenes with a gesture tic | **0** of 71 | 0 |
| duplication, manuscript-wide | **.041** | — |

Every per-scene measure at or below the reference band, including gesture density, which sits
inside the clean cohort's range of 2.5 — notably better than the 4.1 measured in the nine-scene
book written before the gesture checks existed. The single figure that is not good is the last
one, and it is the one this run exists to have found.

## What is still not established

The middle. Seventy-one scenes is enough for a sagging middle to exist and nothing here measures
whether this one sags — the threads reach their terminal states on schedule because
`schedule.py` makes them, which is a structural guarantee and not a dramatic one. Whether anyone
wants to know what happens in scene 40 is not measured here or anywhere else in this project.
