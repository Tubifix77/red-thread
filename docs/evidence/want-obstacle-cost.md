# The second axis, and why it was not built

*31 August 2026. Phase 4 of `docs/PLAN.md`, stopped at step 18 by its own kill criterion.*

Exactly one quality axis in this project has ever moved. Dialogue went from .077 to .223 by a
route with three parts: find a countable prose property, find its plan-level correlate, change
one line of the planner prompt. Phase 4 tried the same route on a second axis — does anything in
these books stand in the way of what a character wants — and it does not carry.

## Step 17: two measures that vary — and the audit that halved them

An earlier proxy was refuted for the opposite reason. POV-as-sentence-subject sits at .13 to .20
in every quarter of every book, and a measure that does not vary cannot be improved.

| | what it counts | why |
|---|---|---|
| `refusal_rate` | refusals **performed at somebody**, per thousand words | a head shaken, a request declined, a no said aloud |
| `refusal_per_ask` | the same, divided by asks made of somebody | ten requests and ten grants is a scene of errands |

The narrowness is the design. "Could not" and "did not" catch every negated verb in the language,
and a measure that fires on *she did not sit down* is measuring English.

### The first version said that and then did it anyway

Both regexes were audited a few hours after they shipped, by counting what they actually matched
across 400 committed scenes rather than trusting the intent behind them. Both were contaminated,
and by almost exactly the same amount.

| | contaminating forms | share of all matches |
|---|---|---:|
| `_REFUSAL` | `won't`, `wouldn't`, `would not`, `will not` | **409 of 714 — 56%** |
| `_ASKED` | `wanted`, `needed`, `meant to` | **493 of 873 — 56%** |

Reading them settled it. *"whatever lay beyond this door would not be easy"*, *"voice low so the
others wouldn't hear"*, *"it wouldn't end with a decision"* — ordinary negated futures, not
refusals. And *"He wanted to press harder"* is not a request anybody can say no to.

**Every figure first published for these measures came from the contaminated version.** Both are
now narrowed to a speech act performed at another person, which is the only thing that can be
refused. The corrected numbers:

```
   444 committed scenes          50% contain no refusal at all   (was reported as 25%)
                                 median 0.00, max 3.74           (was 1.41 and 12.55)

   two identical runs of one plan     refusal_rate     22%       (was 14%)
                                      refusal_per_ask  37%       (was 0.3%)
   eight books                        refusal_rate     0.32 - 1.01
                                      refusal_per_ask  .037 - .833
```

**The claim that `refusal_per_ask` was the steadiest measure in the panel is withdrawn.** It moved
0.3% between identical runs because both its numerator and its denominator were dominated by
ordinary English, which is very stable. Narrowed, it moves 37% — one of the *noisiest* measures
here, not the steadiest.

What survives: both still vary far more between books than between runs of one plan — 94% against
a 22% floor, and 221% against a 37% floor. They pass step 17's bar. They are coarser than first
reported, and `refusal_rate` being zero in half of all scenes is a real limitation of what can be
built on it.

## Step 18: the plan is not the lever

Across 538 committed scenes from 16 runs, with the plan-side feature read from each scene's own
summary, beats, posts and forbids:

| the outline names | against | r |
|---|---|---:|
| a refusal | refusal rate | **+0.130** |
| a refusal | refusal per ask | +0.063 |
| a price | refusal rate | +0.032 |
| a spoken act | dialogue share | **+0.446** |
| a refusal | *gesture rate* — control | +0.001 |
| a price | *gesture rate* — control | −0.021 |

The bar was 0.4. It is not met, and it is missed by four times over.

*Published first as +0.217 and +0.200, against the contaminated prose measures above. Narrowing
them took the correlation to +0.111; auditing the plan-side pattern the same way took it back to
+0.130. The conclusion did not change and the margin got wider — the only direction in which a
correction to one's own negative result is comfortable, and worth saying out loud precisely
because it is.*

*The plan-side pattern was audited too, and was largely clean: 103 of its 119 matches across 300
scene specs are `refus*`. It lost the same two alternatives that ruined the prose measure —
`will not` and `won't`, six matches, about half of them the system rather than a person — and a
bare `bars`, which matches iron ones. **Recording that this one was audited matters as much as
the change**, because an unaudited pattern and a clean one look identical from the outside. That
is how the prose measure shipped.*

**The controls are what make this a result rather than a broken instrument.** The plan features
score +0.001 and −0.021 against gesture rate, so they are not merely predicting how busy a scene
is. And the method is not at fault: on the identical corpus, with the same crude regex over the
same fields, the intervention that *did* work reproduces at +0.446. The axis that moved still
scores twice what this one does.

The effect is real and small. Scenes whose plan names a refusal average **0.78** refusals per
thousand words against **0.58**, and 50% contain none against 60%. The plan moves this axis about
a quarter as hard as it moves dialogue.

## Step 19: not built

Adding `want`, `obstacle` and `cost` to every scene spec on r = 0.130 would be building the
intervention the evidence says will not carry. The fields are cheap and the brief they would
swell is not — everything in there arrives in every one of seventy scenes, and this project
already has a rule about that.

If the axis is worth another attempt, the next move is a better prose measure or a different
lever, not this one on weaker evidence. `plan_names_a_refusal`'s docstring carries the number so
that attempt starts from "this scored 0.130" rather than from the same hypothesis unexamined.

## The lesson that outlasts the result

The measures were audited only because a spare half-hour went into counting what they matched
instead of reading what they were meant to match. Nothing forced that. The docstring asserting
the measure was narrow was written by the same person who then failed to check, and it was
persuasive enough to have stopped anyone else checking either.

**Count what a pattern actually matched before publishing anything computed from it**, and read a
sample of the matches in context. Both audits took minutes and both found a 56% contamination.

## One correction in passing

`r = +0.672` for spoken acts against dialogue was measured on 108 scenes. The same measure on 538
gives **+0.446**. The direction and the ranking hold; the magnitude does not. A correlation from
a hundred scenes is not a constant, and this project has now been caught by that twice.
