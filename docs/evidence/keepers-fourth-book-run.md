# The Keeper's Fourth Book — a fresh premise, start to finish

*30 August 2026. `qwen3:8b` in every role, RTX 3080 10GB, zero API calls.*

The first book planned and written after the sampler work, on a premise the system had never
seen — a lighthouse keeper's unofficial fourth logbook and the surveyor sent to catalogue it.
Written specifically to test the standing claim in `STATUS.md` that **every new premise has cost
between one and three code fixes**.

It cost one, and the plan gate caught it before a word was generated.

## The one fix

`plan` produced a story bible and the audit refused it: **0 blockers, 5 majors**. All five were
one bug. Asked to name the vocabulary its premise rules out, the planner got the good half right
— `conspiracy`, `hacker`, `sentient` — and then added `truth`, `right`, `memory`, `silence`.
Those are words a novel is made of. Every scene would have tripped `check_forbidden` several
times over, each trip costing a repair round, on words the story is actually about.

`STORY_PROMPT` already names those four words as ones a novel needs. The planner listed all four
anyway, which is the argument for checking rather than asking, in the one place it applies.

The fix drops them from the *proposal*, inside the planner's retry loop. It does not touch
`parse_story`, so a `story.json` a person wrote still reaches the audit intact and still stops
the run — `check_ban_is_avoidable` says in its own docstring that the plan is not edited, and
that stays true. An existing test, `TestBansAreReportedNotDropped`, caught the first attempt at
this, which had put the filter in the wrong place and would have silently rewritten a
hand-authored file on every load.

Re-planned: **0 blockers, 0 majors, 6 minors.**

## The run

Nine scenes, 8,359 words, 8 minutes 35 seconds.

| | |
|---|---|
| scenes committed | 9 of 9 |
| held back | 0 |
| repair rounds | 2 |
| repairs needing a model call | **0** |
| redrafts | 0 |
| code fixes during writing | **0** |
| threads at terminal state | 3 of 3 |

Both repairs were `surgical: deleted the thematic_gloss sentence (no model call)` — the
deterministic path, where a gloss sentence is cut rather than rewritten.

## Prose

| | this book | reference drafts |
|---|---:|---:|
| duplication, per scene | **.000** | .009 |
| duplication, manuscript-wide | .015 | — |
| recap grammar | **.084** | .105 |
| blocks of recap, whole book | **0** | 0 |
| longest past-perfect run | 3 sentences | 1–2 |
| stacked absolutes | 0% of scenes | 0% |
| rhetorical triples | 0% | 0% |
| narrator glossing the theme | 0% | 0% |

Every countable axis at or below the reference band, which is three cold single scenes from
`gemma3:12b`, `phi4:14b` and `qwen3:8b` with no orchestration at all.

## What reading it found that the checks did not

The numbers cannot say whether the prose is worth reading, and the honest note is that this is
competent 8B prose rather than good prose. One concrete thing did come out of reading it:

> *"The room felt different today. Not unfamiliar, but altered somehow, as though the walls
> themselves held their breath between her steps."*

That is the `as if the X itself` gloss the checks already look for, missed twice over — the
shipped pattern covered `as though` but only with `the`, and did not cover the plural
`themselves` at all. Measured across 119 committed scenes the shipped form catches 8 hits in 7
scenes and the two missed variants catch 6 more in 5, at the same rate and with the same zero
occurrences in the reference drafts. Widened, not added: it is one tell, not three.

## What this does and does not establish

**Does:** the pipeline planned and wrote a complete book from an unseen premise with no
intervention after the plan gate, and the prose came out below the reference band on everything
countable. That is the first time.

**Does not:** 8,359 words is a novella-length test at best, and nine scenes is not where the
cross-corpus checks earn their keep. Whether the book is *good* — whether anyone wants what
happens next — is not measured here or anywhere else in this project, and reading it says it is
competent rather than compelling. The plan-gate fix is also n=1 as a fix: it removed the obstacle
this premise hit, and the next premise may hit a different one.
