# red-thread

[![tests](https://github.com/Tubifix77/red-thread/actions/workflows/tests.yml/badge.svg)](https://github.com/Tubifix77/red-thread/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Orchestrated long-form fiction. The thing this produces is **not prose** — it is a spec tree plus
a fact ledger, and the prose is a rendering of them.

That inversion is the whole design. Coherence across a manuscript is not a property of the model
or of its context window; it is a property of what each small writing session is handed, and what
a verifier refuses to accept back. Hundreds of tightly-briefed sessions with a commit gate between
them, rather than one long generation hoping to stay consistent.

Every architectural decision traces to a cited source in **[docs/RESEARCH.md](docs/RESEARCH.md)**,
fetched live under the zero-assumption contract. Nothing here is from model memory.

How close this is to being an unassisted writer — measured, not estimated — is in
**[docs/STATUS.md](docs/STATUS.md)**, and what has been measured, what discriminates and what
was tried and thrown away is in **[docs/MEASUREMENTS.md](docs/MEASUREMENTS.md)**. Short version: the orchestrator is close to shippable, the
writer is not, and the gap is everything no check can see.

---

## The shape

```
                    ┌──────────────────────────────────────┐
   static memory    │  StorySpec: premise, world rules,    │   immutable for a run
                    │  characters, style contract, threads │
                    └──────────────────┬───────────────────┘
                                       │
   spec tree        ┌──────────────────▼───────────────────┐
                    │  SceneSpec × N — beats, and a        │
                    │  Transition per thread it must move  │
                    └──────────────────┬───────────────────┘
                                       │
                    ┌──────────────────▼───────────────────┐
   one session      │  brief  →  draft ×3  →  checks  →    │
   per scene        │  verify  →  local repair  →  GATE    │
                    └──────────────────┬───────────────────┘
                                       │ only if it passes
   dynamic memory   ┌──────────────────▼───────────────────┐
                    │  Ledger: ⟨subject, predicate,        │
                    │  object, scene⟩ + thread state       │
                    └──────────────────────────────────────┘
                                       │
                                  next scene's brief
```

### A red thread is a state machine

The central borrow, from ConWriter: a scene must induce a valid **state transition**, expressed as
symbolic operators — preconditions, postconditions, forbidden states. So a thread is not a note
about a subplot, it is a record with an explicit arc:

```python
Thread(id="T-CODE", name="The dead line in the founders' code", kind=ThreadKind.MAIN,
       states=["dormant", "planted", "complicated", "escalated", "paid_off"],
       concealment="that the error is deliberate — the reader must not know before scene 4",
       payoff="proof that is unambiguous to her and unreadable to everyone else",
       deadline_scene=9)
```

and a scene spec says, mechanically, what it owes:

```python
thread_ops={"T-CODE": Transition(
    pre=["Siv has recorded the unreachable branch's line number"],
    post=["the reader now knows the error is deliberate",
          "Siv holds a physical document she could show someone"],
    forbid=["the narration explaining what this means for the town",
            "a founder appearing as a character"],
    to_state="complicated")}
```

Now "did this scene do its job?" is a set of falsifiable questions, and "is this manuscript
coherent?" decomposes into checks that run one at a time.

### The commit gate

Nothing enters dynamic memory until the scene passes. A rejected scene leaves no facts, no thread
movement, no residue for later scenes to build on — `Project.commit` is the only path into the
ledger, and `write_all` halts at the first rejection rather than writing scene 8 against a state
that never happened.

### Structure is scheduled, not proposed

The planner's central decision. Asking a model to lay out which scene advances which thread to
which state produces plans that fail the audit constantly — threads re-entering states, whole
threads stalling through the midpoint, subplots that never own a scene. Those are *scheduling
constraints*, not creative decisions.

So [`schedule.py`](redthread/schedule.py) computes the structure and
[`planner.py`](redthread/planner.py) asks the model only what happens in a scene that must move a
given thread to a given state — a far better-posed question than "outline a novel". Both
acceptance markers then hold **by construction**, verified across 70 combinations of manuscript
length and thread mix. `audit_plan` stops being a filter on model output and becomes a regression
test on the scheduler, which is a much better place for it: a failing test is actionable, a
rejected generation is just expensive.

A model that misbehaves — reassigning thread states, inventing thread ids, returning junk — can
degrade the plan's *content* and cannot touch its structure. That is asserted directly in
[`tests/test_planner.py`](tests/test_planner.py).

### Repair is a ladder, and its rungs are sized like the checks

A failing scene is not rewritten. Each violation carries the offending span verbatim, repair
touches only what the check complained about, and it is reverted if it does not measurably improve
the violation score. Regeneration throws away the good prose with the bad and resamples every
check you had already passed.

Which rung matters as much as the locality, because **a repair whose reach is narrower than its
check's scope can never converge.** `check_seam` compares a scene's last twenty-five words against
the previous scene's ending; sentence-local surgery rewrites the one sentence a quote falls in.
Point the first at the second and a scene that copied two sentences forward spends its whole
repair budget having one of them rewritten, round after round. That is exactly what happened, in a
real book, at scene 4.

So each kind is routed to a repair sized like the check that raised it, cheapest first:

| rung | model calls | for |
|---|---|---|
| `deseam` | none | a copied seam — delete the duplicated block, verify with `check_seam` itself |
| delete | none | narrator gloss, which lives in self-contained sentences |
| `snap` | none | a truncated draft — cut back to the last complete sentence |
| `surgical` | one per sentence | anything carrying a quote that locates in the text |
| `reseam` | one | a seam that deletion could not clear |
| `trim` | one | a runaway draft |
| `expand` | one | an under-length scene — grow the thinnest passage, splice it back |
| `fulfil` | one | a missed obligation, which has no quote to point at — write the beat |
| `repair` | one | last resort: the whole scene, which a small model does badly |

The three that need no model are the ones that cannot fail in the interesting way. Asked not to
reuse the previous scene's ending — and shown that ending under a heading saying so — an 8B handed
it straight back, twice, in about a second each time. Showing a small model the text it must avoid
is showing it the text to produce, so the copied block is deleted in code instead.

Once every action that could address the remaining violations has failed twice, the loop stops
rather than spending the rest of its budget re-running them.

[`tests/test_repair_coverage.py`](tests/test_repair_coverage.py) keeps this honest. It reads
`checks.py` with `ast`, collects every BLOCKER/MAJOR kind the scene-level checks can emit, and
asserts each one has a route to a repair that can reach it. A new check without a repair fails the
suite the day it is added rather than the day a book runs into it.

### A rule the judge cannot answer is worse than no rule

The plan audit is not only about structure. Half its checks exist because a malformed *rule*
produces a scene that cannot be written and cannot be repaired — the scene is fine, the
requirement is broken:

- a prohibition phrased as a negation (`forbid: "the decision is not finalized"`) reads as a
  demand for the very thing it means to prevent;
- an obligation that names a thread state (`post: "The Allegiance reaches 'reoriented'"`) asks the
  judge about bookkeeping the prose cannot contain;
- an obligation that names an absence (`post: "the past is left unspoken"`) can never be evidenced,
  so it is reported missed however the scene goes;
- a beat written as finished prose is prose the writer copies back, and `check_brief_leak` is right
  to flag the copy;
- a "do not reveal X" on a thread whose concealment the schedule already lifted contradicts the
  schedule.

Each is caught by `python -m redthread audit` before a word is generated, and where the intent is
unambiguous it is repaired rather than reported — a negated prohibition is inverted into the event
it forbids, prose beats are rewritten into intent at plan time.

---

## The finding that changed the design

Continuity is the obvious problem, and the literature shows it is largely solvable — DOME reports
a 0.56% conflict rate against Re3's 0.77%.

But StoryScope measures what actually makes AI fiction *recognisable*, and it is not continuity:

| | AI | Human |
|---|---|---|
| narrator explicitly explains the theme | 77% | 52% |
| **no subplots** | **79%** | **57%** |
| emotion via physical sensation / bodily metaphor | 81% | 38% |
| named references (rather than vague allusion) | 24% | 47% |
| resolution favours protagonist agency | 69% | 46% |

Narrative features alone classify human vs AI at **93.2% macro-F1**, and still 93.9% *after* style
artifacts are scrubbed. The tell is structural. Polishing prose does not remove it.

So the verifier is built as much from **prohibitions** as from requirements, and subplots are a
hard structural obligation rather than a nice-to-have. The 79%/57% row is the strongest single
argument for this project's premise: a thread architecture *is* a subplot architecture.

---

## What is built

| Module | Does | Source |
|---|---|---|
| [`models.py`](redthread/models.py) | Threads, transitions, specs, quadruple facts, violations | ConWriter, DOME |
| [`ledger.py`](redthread/ledger.py) | Fact store, scoped retrieval, character knowledge, conflict candidates | DOME |
| [`brief.py`](redthread/brief.py) | The scene brief — the most important file here | Liu et al., STORYTELLER, StoryScope |
| [`checks.py`](redthread/checks.py) | 15 scene checks + a 10-part plan audit. No model calls | StoryScope, Antislop |
| [`verify.py`](redthread/verify.py) | 5 single-purpose LLM probes: extraction, contradiction, thread satisfaction, anti-tells, tension | DOME, ConWriter, Re3 |
| [`pipeline.py`](redthread/pipeline.py) | The state machine and the commit gate | ConWriter, Re3 |
| [`schedule.py`](redthread/schedule.py) | Deterministic thread scheduling — both markers by construction | CONCOCT |
| [`planner.py`](redthread/planner.py) | Premise → threads, cast, world, voice, scene content | CONCOCT, DOME, StoryScope |
| [`project.py`](redthread/project.py) | Plain-file state, diffable, resumable | — |
| [`llm.py`](redthread/llm.py) | Native Ollama backend (thinking control, JSON mode), OpenAI-compat + Anthropic, role split, truncation salvage | — |
| [`ollama.py`](redthread/ollama.py) | Discovery: what is installed, what plausibly fits, name resolution | — |
| [`progress.py`](redthread/progress.py) | Orchestrator view — stages, timings, thread state | — |
| [`cli.py`](redthread/cli.py) | `plan` `audit` `brief` `check` `write` `models` `bench` `status` `ledger` `manuscript` | — |

**421 tests, no dependencies beyond the standard library.** Every check is tested by injecting the
defect it exists to find — a check that never fires is indistinguishable from a check that does
not work.

They still cannot be the last word, and it is worth saying why. The fixtures in `tests/fakes.py`
are prose *I* wrote, and I wrote it to pass the checks — one comment in there says outright that
the fixture closings are kept distinct so `check_seam` does not fire on the fixture's own filler.
Test data built around a failure mode cannot detect it. The suite proves the machinery composes;
only running a book on a real model proves the repairs converge, and the second book found twelve
defects with 292 green tests behind it. `tests/test_repair_coverage.py` exists because a
*structural* assertion about the checks is the part that generalises.

Three commands need no API key, and they are the ones that tell you whether the architecture is
sound: `brief` (read what a session will actually be told), `check` (run the deterministic checks
against any prose), `audit` (plan-level failures, before a word is generated).

---

## Try it

It is two commands, and they are separable on purpose. `plan` turns a premise into a run directory
— the bible, the schedule, and every scene's spec — and costs a few minutes. `write` walks that
plan scene by scene and costs hours. In between, `audit` and `brief` tell you whether the plan is
worth the hours, without spending them. A run directory holds one book; run `plan` twice with
different `--out` values and both sit there until you write them.

Plan a book from a premise (text on the command line, or a path to a file):

```bash
python -m redthread plan "A harbour inspector finds the tide tables have been altered." --out runs/tide --words 60000 --local qwen3:8b
```

Or start from the hand-authored reference plan, which needs no model at all:

```bash
python examples/build_inherited_glitch.py runs/glitch
```

```bash
python -m redthread audit runs/glitch
```

```bash
python -m redthread brief runs/glitch --scene 4
```

### Running it

Everything runs against local models through Ollama. See what you have, and what fits your card:

```bash
python -m redthread models runs/glitch --vram 10
```

```bash
python -m redthread write runs/glitch --local qwen3:8b
```

The roles are split, and they want different things. Prose generation is forgiving and dominates
the token spend. Extraction, contradiction judgement and the anti-tell probes need careful reading
and reliable structure, and they fail *silently* — a malformed extraction does not error, it just
quietly stops protecting continuity. `--local-critic MODEL` puts those roles on a second model.

**On VRAM, from measurement rather than theory:** two models alternating does not work on a 10GB
card. An 8B writer beside a 14B critic put the critic at 7.8 of 9.5 GB on the GPU — 18% spilled to
CPU — and evicted the writer between every call. Pick one model that fits entirely, and use
`bench` to choose it.

Model names are resolved against what is installed before any generation starts, so a typo fails
in a second rather than after a 400-token draft. Reasoning blocks from thinking models (`<think>…`)
are stripped from drafts — left in they wreck the word count, trip the format check, and end up in
the manuscript.

Which local model to pick, and the research behind it, is in **[docs/MODELS.md](docs/MODELS.md)**.
To measure candidates on your own hardware against the axis that matters — can it hold the brief:

```bash
python -m redthread bench runs/glitch --scene 1 --local qwen3:8b --local phi4:14b
```

No judge model and no API key, so it costs nothing but GPU time. It scores adherence only; read
the drafts it saves for whether the prose is any good.

### Watching a run

`write` prints an orchestrator view: overall percentage and word count, then per scene the stage
transitions with timings and violation counts, then a thread-state summary.

```
  ██████░░░░░░░░░░░░░░░░░░░░  23.1%  3/13 scenes, 3,142 words, 6m41s
  ▸ scene   4  ch2  1400w  pov:Siv Alderman  threads:T-CODE
      Siv finds the founders' own note about the branch. It is deliberate, i
      · brief                 0s  1,318 words in, 6 facts available
      · draft 1/3           1m12s  1405w · 0B/1M/2m
      · draft 2/3           1m08s  1362w · 0B/0M/3m
      · verify               22s  9 facts extracted · 0B/0M/3m
      · commit                0s  9 facts into the ledger
      ✓ committed - 1362 words in 2m51s, 3 draft(s), 0 repair(s)
```

Line-based rather than a redrawn dashboard, on purpose: when scene 34 is held back you want to
read what happened at scene 31, and a spinner that overwrote itself has thrown that away. The
project is saved after every scene, so an interrupted run resumes from where it stopped.

---

## The acceptance markers

Two markers govern the project, both structural, both checkable before a word is generated. The
full protocol — including how to design a premise that actually tests something — is in
[docs/TESTING.md](docs/TESTING.md).

**Marker 1 — real sub-arcs, not famous three-act beats.** `check_subplot_independence` requires
some thread to own scenes the main thread does not touch. A subplot that never has the page to
itself is the main plot with extra scenes.

**Marker 2 — the midpoint shifts stakes rather than repeating them.** `check_stakes_progression`
reads thread state history: a thread asked to re-enter a state it already occupied is a story
circling its own conflict, and if most threads gain no ground across the middle third, the
manuscript's middle is treading water. No model call, no reading — it falls out of the state
machine for free.

The reference plan in `examples/build_inherited_glitch.py` is asserted clean on both, so a
regression in either check surfaces as a failing test rather than as a quietly worse manuscript.

Test premises themselves are kept out of this repo on purpose: publishing a story premise gives it
away. Nothing in the protocol depends on them.

---

## What is proven, and what is not

**Proven, by the test suite:** the machinery composes. Ten scenes commit in sequence, the ledger
accumulates and survives reload, threads reach their final states, the seam is fed forward
verbatim, a mid-run rejection halts cleanly with nothing from the failed scene in dynamic memory,
and a re-run resumes from the gap. Every check catches its defect.

**Proven by running it to completion, all local, zero API calls:** seven manuscripts exist —
145 scenes and 144,248 words drafted on `qwen3:8b`, the longest of them **71 scenes and 61,733
words** ([record](docs/evidence/sixty-thousand-word-run.md)). The sixth, *The Keeper's Fourth Book*, is the
first written from a premise the system had never seen with **no intervention after the plan
gate**: nine scenes, 8,359 words, 8m35s, every scene committed, every thread terminal, and every
countable prose measure at or below the reference band
([record](docs/evidence/keepers-fourth-book-run.md)). Two are written up in full below; the other
three (*The Book of Safe Days*, *The List*, *The Night Baker's Schedule*) were regression runs
against fresh premises, and each one cost between one and three code fixes. That number is the
real measure of how unattended this is, and it is not yet zero.

*The Inherited Glitch* — 10 scenes, 12,169 words, from the hand-authored reference plan, generated
end to end on `qwen3:8b` in every role on a 10GB card. Every thread walked its state machine to its
terminal state on schedule; 148 facts accumulated in the ledger and fed every later brief;
concealments were enforced and released at their declared reveal scenes; the commit gate refused
twenty-odd bad versions along the way and nothing it refused ever contaminated dynamic memory. The
run record, seam audit, and a sample scene are in
[docs/evidence/manuscript-run.md](docs/evidence/manuscript-run.md).

*The Debt of Years* — **27 scenes, 30,046 words, premise in and book out.** The planner wrote the
bible, the cast, the voice and every scene's content from one page of premise; the scheduler laid
out the structure; the pipeline wrote it. 397 facts in the ledger, 75 of them character knowledge,
all four threads at their terminal state. This is the run that mattered, because it was two and a
half times longer than the first and — unlike the first — it was *not* clean. Full record in
[docs/evidence/debt-of-years-run.md](docs/evidence/debt-of-years-run.md).

Between them the two runs surfaced about thirty defects no test had caught, every one now a test.
The mechanism-level findings are written up in [docs/MODELS.md](docs/MODELS.md) and the addenda in
[docs/RESEARCH.md](docs/RESEARCH.md). Two are worth repeating here:

**"The local model can't do it" is a hypothesis, not an observation.** A scene reported `0 facts
extracted`, which read exactly like "an 8B can't do structured output". The same model on the same
text extracts 18 clean facts. The bug was ours.

**A green suite against fixtures you wrote proves less than one book against a real model.** Six
of the second run's twelve defects are one mistake in different places — a check whose scope is
wider than its repair's reach — and `check_somatic` had already been fixed for exactly that shape,
earlier in the same project, without the lesson generalising. It generalises now, as an assertion
rather than as a habit.

**Not proven, and the honest list:**

1. **Whether the prose is *good*.** The structure held; the sentences are an 8B's, and the longer
   book made that plainer rather than less so — most of its scenes committed carrying six or
   seven minors, and one draft repeated "he had no right" four times inside a single scene. The
   system's own cross-corpus audit is where this shows up, by design: committed-with-minors is
   the intended behaviour and the per-scene reports carry the full list for a human pass. A
   better local writer slots in with one flag.
2. **Whether scheduling structure costs anything creatively.** Making both markers hold by
   construction removes a class of failure and also removes the model's freedom to put a turn
   where it wants one. No source compares scheduled against proposed structure for
   reader-perceived quality. This is the largest unexamined assumption in the project.
3. **Whether the seams actually disappear for a reader.** Mechanically they hold, and the second
   run put real pressure on that: five of its 27 scenes opened or closed on the previous scene's
   words and were repaired. Whether a reader *feels* the joins in the repaired result is a
   different question, and two manuscripts are two data points.
4. **Whether bottom-up amendment helps.** Prose amending its own spec — the difference between an
   outline-filler and a writing tool. Unbuilt.
5. **The generation-unit size.** Re3 drafts 256-token passages, ConWriter works at scene level; no
   source compares unit sizes for reader-perceived quality. Scene-sized units with beat-sized
   specs is a judgement call.

## Next

The two items measurement actually points at, in order:

- **A repair for recap grammar.** `summary_distance` is measured, the brief names it with the
  numbers attached, and it moved .28 → .25 across the whole prose pass — the only measured axis
  with no route to fix what it finds. Every other check that fires has a repair sized to its
  scope; this one has an opinion and nothing else.
- **Dramatic planning.** The planner emits beats that are structurally valid and dramatically
  inert. Want, obstacle and cost are not modelled anywhere, so a beat that says *she checks the
  register* and a beat that says *she checks the register knowing what she will find* are
  indistinguishable to every test in the suite. This is where the unmeasured half of
  [docs/STATUS.md](docs/STATUS.md) has to be attacked, because it cannot be attacked with a
  checker without breaking the rule that keeps the orchestrator honest.

Then:

- **A 60,000-word manuscript.** Thirty thousand words across 27 scenes is where the cross-corpus
  checks started earning their keep; at twice that, `check_repetition` and the cast-wide rhythm
  check are doing the work they were built for rather than sampling it.
- **Candidate selection that can see a repair coming.** Selection currently ranks drafts by
  violation score alone, so it picked a 995-word draft over a 1,519-word one and then watched
  `deseam` cut it under its target. The cost of the repair a violation implies belongs in the
  score.
- **A better local writer.** The structure held on an 8B; the sentence ceiling is the writer
  model. Re-run `bench` as stronger models land that fit in 10GB — the swap is one flag.
- **Sampler-level slop suppression** via `antislop-vllm` against a local endpoint, replacing the
  post-hoc phrase check — suppressing at sample time costs nothing, checking afterwards costs a
  repair round trip.
- **The forecastability probe on midpoint scenes** (`--forecast`), which is where under-tensioned
  writing hides.
- **Bottom-up amendment** — prose amending its own spec, the difference between an outline-filler
  and a writing tool.
