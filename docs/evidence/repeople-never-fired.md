# The re-people pass has never run on a book this project measured

*2 September 2026. PLAN2 step 29, stage 1 — and the stage killed the step's design before a
GPU-second was spent on it. Zero GPU; the answer was arithmetic over plans already on disk.*

## The pass has a gate, and the gate is the whole story

`repeople_solo_scenes` re-asks the planner for scenes it left with one character in them. It is
not unconditional: below a threshold it returns immediately, and `make_plan` calls it with the
default ([planner.py](../../redthread/planner.py)).

    if not ordered or len(solo) / len(ordered) <= limit:   # limit = 0.15
        return 0

The reasoning is sound and is quoted in the function itself — *"a handful of solo scenes is a
novel, not a defect."* The consequence had not been checked.

## The plan every measured book was written from sits below it

Counting solo scenes across all 56 plans on disk:

| plan | scenes | solo | share | gate fires? |
|---|---:|---:|---:|---|
| **`current` and every phase 1 / phase 8 replicate** | 71 | **10** | **14.1%** | **no** |
| `solo-b2` and its panels (step 25's fresh premise) | 24 | 0 | 0% | no |
| `var3`, `var4` | 71 | 5 | 7% | no |
| `book3`, `var1`, `var2`, `var5`, `tally7`, `scale60b/c` | 71 | 17–34 | 24–48% | yes |
| `solo-a1`, `solo-a3`, `solo-b3`, `solo-b4`, … | 24 | 5–9 | 17–38% | yes |

10 of 71 is **14.08%**. The gate opens above 15%. **One more solo scene — 11 of 71, 15.5% —
and it would have fired.**

So: every book in the phase 1 corpus, every ablation, the four-run floor, and both step 25 panels
were written from plans on which **this mechanism returned 0 without doing anything.** The gate
would fire on 16 of the 56 stored plans (29%), so the pass is not dead code — it is simply absent
from everything this project has ever measured.

## What that does to step 29

The step was designed to ablate the pass on the *Debt* plan. **That experiment is a no-op:**
`--no-repeople` would switch off a pass that does not run, and two conditions would differ by
nothing at all. Both the original design (an ablation flag on `replicate`, which does not exist)
and its first correction (a transform of the *Debt* plan, which the gate refuses) are dead.

The design that can actually work needs a plan where the gate opens:

- take a solo-heavy plan — `solo-a1` at 9 of 24 (38%) is the strongest, `solo-a3` at 25% the
  nearest to the boundary;
- produce a re-peopled twin with `redthread repeople --write`, which is one model call over a
  fixed plan rather than a regenerated plan;
- write n=2 from each, 24 scenes apiece, ~3 GPU-h;
- statistic `dialogue_share` (floor 11%, a share — rule VII typed), within one premise, because
  step 26 established `dialogue_share` is not portable across books.

Stage 1's own deliverable stands on its own, though, and it is the more useful half: **before
asking whether the pass improves prose, it was worth asking whether it ever ran.**

## Why this was invisible

Three things hid it, and each is a pattern rather than an accident:

1. **The mechanism has an off switch, so it looked measurable.** PLAN2's W5 called it "never
   ablated". It is worse than untested — it is *inert on the entire measured corpus*, and an
   ablation would have returned "no difference" for a reason that has nothing to do with whether
   the mechanism works.
2. **A gate is invisible in the artefact it gates.** A plan that was re-peopled and a plan the
   pass declined to touch look identical on disk: both are just plans. Only re-deriving the
   share from the scene list distinguishes them.
3. **The bimodality was known and its consequence was not.** PLAN.md step 8 already recorded that
   six plans of one premise gave 5, 5, 22, 24, 10 and 28 solo scenes and called the total
   bimodal. `current` is the 10. The corpus was written from the low mode **by draw, not by
   design** — and nothing in the project noticed that this put it on the quiet side of a gate.

The generalisation, which is rule IV's shape pointed at a mechanism rather than a check: *a
mechanism that is gated has two failure modes, not one — it can do nothing when it runs, and it
can never run.* The second is cheaper to test and was never tested.

## A verification this analysis also produced

Checking whether the corpus shared a plan turned up a difference between `runs/current` and its
replicates — `depends_on` is `null` in the older source plan and `[]` in the copies, a
serialisation change from the dependency-graph work. It is not load-bearing: `depends_on` appears
nowhere in `brief.py` or `pipeline.py`, and **all twelve phase 1 and phase 8 conditions hold
byte-identical plans**. One plan, one switch, confirmed rather than assumed.
