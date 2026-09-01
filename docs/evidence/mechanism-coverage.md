# Which mechanisms actually fire

*2 September 2026, during phase 8. Zero GPU — every row replayed against artefacts already on
disk. [MEASUREMENTS.md](../MEASUREMENTS.md) has long carried an audit of which **checks** fire.
Nobody had run the same audit on the **mechanisms**, and it finds two of six doing nothing at all
on the corpus every published verdict rests on.*

## The audit

Each mechanism replayed against exactly the input it saw: brief-side ones by rebuilding each
floor book's committed prefix scene by scene, plan-side ones against each run's stored
`story.json` or `plan.json`.

| mechanism | fires on the corpus plan? | fires anywhere? |
|---|---|---|
| refrain feedback | **yes** — names something in 77–96% of scenes | yes |
| gesture feedback | **yes** — 62–83% of scenes, first fire scene 13–28 | yes |
| model-refrain list | **yes** — unconditional, in every brief of every scene | yes |
| `drop_story_shaped_samples` | **yes** — drops 1 of 3 style samples | 7 of 19 stories (37%) |
| **re-people pass** | **NO** — gated at 15% solo, plan sits at 14.08% | 16 of 56 plans (29%) |
| **`drop_unavoidable_bans`** | **NO** — drops 0 of 3 forbidden phrases | 2 of 19 stories (11%) |

**Two of six mechanisms are inert on every book this project has measured.** Neither is dead code
— each fires elsewhere in the corpus — but neither has touched the floor runs, the phase 1
ablations, or the step 25 panels. The re-people case is worked through in
[repeople-never-fired.md](repeople-never-fired.md); `drop_unavoidable_bans` is the same shape,
found by the same question, and it fires only on `register` (2 phrases) and `unattended` (4).

## Why this is a different failure from an untested mechanism

PLAN2's W5 listed two mechanisms as "never ablated". That framing assumed the only thing missing
was the experiment. For these two the experiment is not merely missing, it is **unrunnable on the
corpus**: switching off something that never runs produces two identical conditions, and the
result would read as "no difference" for a reason having nothing to do with the mechanism.

An ablation that cannot distinguish *"this does nothing"* from *"this never ran"* is not a weak
experiment. It is a measurement of the wrong thing, and it would have been reported with error
bars and a kill criterion.

## The generalisation

Rule IV says a check over a scheduler-guaranteed field only confirms the scheduler. This is the
same defect one level up:

> **A gated mechanism has two failure modes, not one — it can do nothing when it runs, and it can
> never run. The second is far cheaper to test, and until tonight had never been tested.**

Three things make it easy to miss, and all three are structural rather than careless:

1. **A gate is invisible in the artefact it gates.** A plan the re-people pass rewrote and a plan
   it declined to touch are both just plans. A story whose bans were filtered and one whose were
   not are both just stories. Only re-deriving the gate's input distinguishes them.
2. **An off switch makes a mechanism look measurable.** All four ablation flags exist, so all four
   mechanisms appeared equally ready to test. Two were not.
3. **The gates are individually reasonable.** *"A handful of solo scenes is a novel, not a
   defect"* is correct. Nothing here argues the thresholds are wrong — only that nobody checked
   which side of them the corpus sat on.

## The cheap check this earns

Before designing any ablation, ask what fraction of the target corpus the mechanism actually acts
on. It is arithmetic over files already on disk, it costs nothing, and tonight it saved roughly
three GPU-hours that step 29 was about to spend comparing a condition against itself.

The same question asked of the mechanism now on the GPU — the model-refrain list — returned
*unconditional, every brief, every scene*, which is why step 28 was left running
([step28-preregistration.md](step28-preregistration.md)).
