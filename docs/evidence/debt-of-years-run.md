# The Debt of Years — 27 scenes, 30,046 words, qwen3:8b

The second complete manuscript, and the one that found the bugs. Concept 3 of the author's test
set, planned and written entirely on one local 8B model with no API key and no hosted critic.

```
python -m redthread plan runs/debt --premise-file examples/concepts/concept-3-debt-of-years.md --local qwen3:8b
python -m redthread write runs/debt --local qwen3:8b --candidates 2 --repairs 5
```

Final state: 27/27 scenes committed, 30,046 words, 397 facts in the ledger (75 of them character
knowledge), all four threads at their terminal state.

| thread | kind | scenes | states |
| --- | --- | --- | --- |
| The Pursuit | main | 1, 10–18, 26, 27 | dormant → activated → in pursuit → cornered → captured |
| The Allegiance | subplot | 2–8, 19, 27 | dormant → known → compromised → reoriented → resolved |
| The Enclave | mystery | 2, 10, 19, 27 | dormant → discovered → threatened → revealed → erased |
| The Disgrace | relationship | 2, 9, 19, 27 | dormant → unresolved → exposed → burdened → forgotten |

## Why this run matters more than the first one

The first manuscript (*The Inherited Glitch*, 10 scenes) committed almost every scene on its
first or second draft. Very few checks fired, so very few **repair paths** ever executed — and
the 292 tests passing at the time were written against `tests/fakes.py`, whose fixtures were
built to *pass* the checks. `_CLOSINGS` still carries a comment saying the closings are kept
distinct so `check_seam` does not fire on the fixture's own filler.

Fixtures constructed to avoid a failure mode cannot detect it. Every bug below reached a live run
with a green suite behind it.

## What the run found

Nine defects, in the order the book hit them. Each has a regression test named after the scene
that produced it.

| scene | what happened | fix |
| --- | --- | --- |
| 4 | ended in two sentences copied verbatim from scene 3; surgical rewrote one per round, `check_seam` compares the whole last 25 words, five rounds, no progress | `_deseam` deletes the copied block in code and verifies with the check that flagged it |
| 4 | `check_brief_leak` blocked on one six-word run — "his back to the council the", four tokens of it grammar — while the scene did exactly what its beat said | two shared runs required, and only substantive ones count |
| 6 | `Dain \| has \| read the records` judged to contradict `Dain \| has read \| records`: one fact, extracted twice, split differently | `ledger.same_claim` keeps restatements away from the judge |
| 7 | reproduced 172 words of scene 6 before starting its own story; `_deseam` capped at four sentences could not reach it | the bound is the fraction of the scene duplicated, not a sentence count |
| 8 | blocked for finalising a decision its own `post` line required — the forbid read "Dain's decision is **not** finalized", which literally demands the reveal | negated forbids are inverted into the event they forbid; 50 of this plan's 27 scenes carried one |
| 12 | echoed at both ends; `_deseam` fixed the ending, then rejected its own work for not having also fixed the opening | one end per call, verified against that end only |
| 13 | held for revealing an enclave the plan unsealed at scene 10 | a disclosure prohibition past its thread's `reveal_scene` is stale and dropped |
| 19 | required to make prose "reach 'reoriented'" — the state label the judge is deliberately never shown, written into the post line instead | `check_post_is_an_event`; nine scenes carried one |
| 21 | `_deseam` cut 155 copied words, cleared the seam, and was discarded as "no improvement" because the shortfall it created was also a MAJOR | an action that cleared its own target is kept even on a tie |
| 24 | required to bring about "the allegiances are **neither** resolved **nor** abandoned" — an absence no prose can evidence | absence posts become prohibitions |
| 26 | ten beats written as finished prose ("his boots crunching over dry leaves"), so `check_brief_leak` fired on the scene doing what it was told | `scrub_prose_beats` rewrites them at plan time; 36 of this plan's beats were prose |
| 27 | a genuinely missed obligation, with no quote to point at and only whole-scene repair to fix it | `_fulfil` writes the missing beat and splices it in |

## The shape they share

Seven of the nine are the same mistake in different places: **a check whose scope is wider than
its repair's reach.** `check_seam` compares regions, surgery rewrites a sentence.
`check_brief_leak` counted seven runs and reported one. `check_somatic` had already been fixed for
this once, months of commits earlier, and nothing generalised the lesson.

`tests/test_repair_coverage.py` now does. It reads `checks.py` with `ast`, collects every
BLOCKER/MAJOR kind the scene-level checks can emit, and asserts each one has a route to a repair
that can reach it — so a new check without a repair fails the suite the day it is added rather
than the day a book runs into it.

The other two are the same mistake at plan level: **a rule the judge cannot answer.** A negated
forbid, a state label as an obligation, an absence as an event. Those are now caught by
`python -m redthread audit` before a word is generated.

## Cost

Zero API calls. One 8-billion-parameter model on one desktop GPU, doing the writing, the fact
extraction, the continuity judgement and the anti-tell audit.
