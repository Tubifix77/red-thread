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

### Repair is local, not regenerative

A failing scene is not rewritten. Each violation carries the offending span verbatim, and repair
rewrites only those spans, within a bounded retry budget, and is **reverted if it does not
measurably improve the violation score**. Regeneration throws away the good prose with the bad and
resamples every check you had already passed.

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
| [`checks.py`](redthread/checks.py) | 14 scene checks + a 3-part plan audit. No model calls | StoryScope, Antislop |
| [`verify.py`](redthread/verify.py) | 5 single-purpose LLM probes: extraction, contradiction, thread satisfaction, anti-tells, tension | DOME, ConWriter, Re3 |
| [`pipeline.py`](redthread/pipeline.py) | The state machine and the commit gate | ConWriter, Re3 |
| [`schedule.py`](redthread/schedule.py) | Deterministic thread scheduling — both markers by construction | CONCOCT |
| [`planner.py`](redthread/planner.py) | Premise → threads, cast, world, voice, scene content | CONCOCT, DOME, StoryScope |
| [`project.py`](redthread/project.py) | Plain-file state, diffable, resumable | — |
| [`llm.py`](redthread/llm.py) | Anthropic + OpenAI-compatible backends, role split, reasoning-block stripping | — |
| [`ollama.py`](redthread/ollama.py) | Discovery: what is installed, what plausibly fits, name resolution | — |
| [`progress.py`](redthread/progress.py) | Orchestrator view — stages, timings, thread state | — |
| [`cli.py`](redthread/cli.py) | `plan` `audit` `brief` `check` `write` `models` `bench` `status` `ledger` `manuscript` | — |

**227 tests, no dependencies beyond the standard library.** Every check is tested by injecting the
defect it exists to find — a check that never fires is indistinguishable from a check that does
not work.

Three commands need no API key, and they are the ones that tell you whether the architecture is
sound: `brief` (read what a session will actually be told), `check` (run the deterministic checks
against any prose), `audit` (plan-level failures, before a word is generated).

---

## Try it

Plan a book from a premise:

```bash
python -m redthread plan "A harbour inspector finds the tide tables have been altered." --out runs/tide --words 60000
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

Then, with `ANTHROPIC_API_KEY` set:

```bash
python -m redthread write runs/glitch --scene 1
```

### Running local

See what Ollama actually has, and which models plausibly fit your card:

```bash
python -m redthread models runs/glitch --vram 10
```

Local prose with a hosted critic — the hybrid this project expects to want:

```bash
python -m redthread write runs/glitch --local qwen3:8b
```

The roles are split deliberately. Prose generation is forgiving and dominates token spend, so it
is the natural place for a local model. Extraction, contradiction judgement and the anti-tell
probes need reliable JSON and careful reading, and they fail *silently* — a malformed extraction
does not error, it just quietly stops protecting continuity. `--all-local` puts every role on the
local model if you want to run with no API at all; that is the configuration most likely to
degrade without telling you.

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

**Not proven, and only a real model can settle it:**

1. **Whether the prose is good.** The test suite uses fixture prose. Nothing here has yet produced
   a scene worth reading.
2. **Whether the seams actually disappear.** The chunk-buffer technique is validated in a different
   modality only (long-form speech), not for prose. `check_seam` catches mechanical echo; whether a
   reader feels the join is a different question.
3. **Whether bottom-up amendment helps.** DOME shows dynamic outlining beats rigid outlining on
   conflict rate, but nothing found isolates prose amending its own spec as a quality win. Not yet
   implemented — the spec tree is currently hand-authored.
4. **Local-model viability for the structured stages.** Untested. The hybrid is reasoning, not a
   measured result.
5. **The generation-unit size.** Re3 drafts 256-token passages, ConWriter works at scene level; no
   source compares unit sizes for reader-perceived quality. Scene-sized units with beat-sized specs
   is a judgement call.

## Next

- **A real full run** end to end, then a manuscript long enough for the cross-corpus checks to bite.
- **Sampler-level slop suppression** via `antislop-vllm` against a local endpoint, replacing the
  post-hoc phrase check — suppressing at sample time costs nothing, checking afterwards costs a
  repair round trip.
- **The forecastability probe on midpoint scenes**, which is where under-tensioned writing hides.
