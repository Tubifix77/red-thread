# The second axis, and why it was not built

*31 August 2026. Phase 4 of `docs/PLAN.md`, stopped at step 18 by its own kill criterion.*

Exactly one quality axis in this project has ever moved. Dialogue went from .077 to .223 by a
route with three parts: find a countable prose property, find its plan-level correlate, change
one line of the planner prompt. Phase 4 tried the same route on a second axis — does anything in
these books stand in the way of what a character wants — and it does not carry.

## Step 17: two measures that vary

An earlier proxy was refuted for the opposite reason. POV-as-sentence-subject sits at .13 to .20
in every quarter of every book, and a measure that does not vary cannot be improved.

| | what it counts | why |
|---|---|---|
| `refusal_rate` | refusals **performed**, per thousand words | a head shaken, a request declined, a "won't" |
| `refusal_per_ask` | the same, divided by asks | ten requests and ten grants is a scene of errands |

The narrowness is the design. "Could not" and "did not" catch every negated verb in the language,
and a measure that fires on *she did not sit down* is measuring English.

Both vary, and not just in the sampler:

```
   538 committed scenes          25% contain no refusal at all
                                 median 1.41 per thousand words, max 12.55

   two identical runs of one plan     refusal_rate     14%
                                      refusal_per_ask   0.3%   ← steadiest in the panel
   eight books                        refusal_rate     0.83 - 2.29
                                      refusal_per_ask  .343 - .973
```

What they separate is books, not samplings. Both are now in `checks.manuscript_measures` with
floors, so any future claim about them has to pass through `clears_noise`.

## Step 18: the plan is not the lever

Across 538 committed scenes from 16 runs, with the plan-side feature read from each scene's own
summary, beats, posts and forbids:

| the outline names | against | r |
|---|---|---:|
| a refusal | refusal rate | **+0.217** |
| a refusal | refusal per ask | +0.200 |
| a price | refusal rate | +0.075 |
| a spoken act | dialogue share | **+0.446** |
| a refusal | *gesture rate* — control | +0.001 |
| a price | *gesture rate* — control | −0.021 |

The bar was 0.4. It is not met.

**The controls are what make this a result rather than a broken instrument.** The plan features
score +0.001 and −0.021 against gesture rate, so they are not merely predicting how busy a scene
is. And the method is not at fault: on the identical corpus, with the same crude regex over the
same fields, the intervention that *did* work reproduces at +0.446. The axis that moved still
scores twice what this one does.

The effect is real and small. Scenes whose plan names a refusal average **2.25** refusals per
thousand words against **1.54**, and 16% contain none against 30%. The plan moves this axis about
half as hard as it moves dialogue.

## Step 19: not built

Adding `want`, `obstacle` and `cost` to every scene spec on r = 0.217 would be building the
intervention the evidence says will not carry. The fields are cheap and the brief they would
swell is not — everything in there arrives in every one of seventy scenes, and this project
already has a rule about that.

If the axis is worth another attempt, the next move is a better prose measure or a different
lever, not this one on weaker evidence. `plan_names_a_refusal`'s docstring carries the number so
that attempt starts from "this scored 0.217" rather than from the same hypothesis unexamined.

## One correction in passing

`r = +0.672` for spoken acts against dialogue was measured on 108 scenes. The same measure on 538
gives **+0.446**. The direction and the ranking hold; the magnitude does not. A correlation from
a hundred scenes is not a constant, and this project has now been caught by that twice.
