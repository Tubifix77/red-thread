# Evidence

The raw material behind the claims in [../MODELS.md](../MODELS.md), kept so they can be checked
rather than taken on trust.

**Two files here supersede figures in the others.** `replicate-noise-floor.md` says what each
measure does between two runs that differ in nothing, and retracts three claims made before it
existed. `fresh-premise-panel.md` then says that floor is **one novel's**, so no figure here
transfers to another book without being re-measured.

**Start with `replicate-noise-floor.md`.** It measures what each figure in these files does
between two runs that differ in nothing, and it retracts three claims made in the others. A
difference smaller than the floor is a coin, and several here are.

| File | What it is |
|---|---|
| `scene01-brief.md` | The exact brief handed to each model — assembled by `redthread brief`, not written by hand |
| `scene01-qwen3-8b.txt` | 948 words. On target. Opens with the style contract's own sample sentence, verbatim |
| `scene01-gemma3-12b.txt` | 542 words. Written entirely in the first person against a `third limited` contract |
| `scene01-phi4-14b.txt` | 506 words. Complete but short; closes on thematic gloss |
| `manuscript-run.md` | The first completed manuscript: seam audit and cross-scene repetition verdict |
| `manuscript-status.txt` | `redthread status` after the run — every thread at its terminal state |
| `manuscript-scene04-reveal.txt` | The committed reveal scene, exactly as the gate accepted it |
| `debt-of-years-run.md` | The second manuscript: planner-driven, 27 scenes, and the twelve defects it found with 292 tests green |
| `keepers-fourth-book-run.md` | First book from an unseen premise with no intervention after the plan gate |
| `sixty-thousand-word-run.md` | The scale test: 71 scenes, 61,733 words, and the three failures that only exist at length |
| `ledger-slice-ab.md` | Three runs of one plan while the ledger changed — including a section retracted by the noise floor |
| `replicate-noise-floor.md` | **Read this before any other file here.** Two runs, identical code, nothing changed: what every measure does when nothing does |
| `tension-on-embeddings.md` | Three ways of measuring tension and what each turned out to measure — 51%, 54%, and r = +0.337, all against their own controls |
| `want-obstacle-cost.md` | A second quality axis, measured and then not built: two prose measures that vary, a plan-side lever that scores r = 0.130 against a 0.4 bar, and the audit that found both measures 56% contaminated |
| `phase1-ablations.md` | **The first time a mechanism here was tested against its own absence.** Ten runs, one plan, one switch. Both mechanisms kept — and one failed the statistic its kill criterion named before a second one, written down first, saved it at p = 0.010 |
| `fresh-premise-panel.md` | The panel run on a book it was not tuned on. Three of eleven measures put a fresh premise outside the old floor with nothing ablated, so the floor is one novel's and not the system's |
| `portable-measures.md` | PLAN2 step 26: which measures hold their values across books. 3 of 13 do, now enforced as `checks.PORTABLE`; two pre-registered expectations failed on contact |
| `two-run-screen.md` | PLAN2 step 27: a 2-run floor is half a 4-run floor and all its errors are false claims — so n=2 may kill, never confirm |
| `mechanism-coverage.md` | Which of the six mechanisms actually fire. Two of six are inert on the corpus every published verdict rests on |
| `repeople-never-fired.md` | PLAN2 step 29 stage 1: the re-people pass is gated at 15% solo scenes and the corpus plan sits at 14.08% — so it has never run on any measured book, and two experiment designs died before any GPU was spent |
| `repair-backfill.md` | PLAN2 step 31's backfill: 72.5% of scenes commit with no repair, and the one repair field on disk is a sum of two quantities only one of which is interesting |
| `step28-model-refrains.md` | Step 28's result: the criterion fired, and the miss was 0.34 phrase occurrences across two books, on a design that could not have confirmed |
| `step28-preregistration.md` | A targeted statistic for step 28, its control measured and its reading decided, committed while the ablated runs were a quarter written |
| `code-drift-floor.md` | Four books sharing one plan across four code revisions: no mean moves beyond the sampling floor, but somatic_share's spread widens 5x |
| `inconsistency-finder.md` | The rejected inspector's successor: recall passes, precision proves unmeasurable because 'clean' controls were not clean, and the run finds a substring bug in its own harness plus four real defects in a committed book |
| `inspector-method.md` | The focused-inspector method: pre-registered thresholds, a continuity inspector that caught 9/9 seeded contradictions exactly and still got parked for crying wolf twice, and a naive rater that kept the eras' direction but lost their separation |
| `sentences/sentences.md` | A hundred sentences, half from each era, shuffled and unlabelled. **RETIRED unrated 3 September** — see `no-human-rater.md`. Kept as a built instrument and as the record of why the unit was wrong |
| `sentences/pairs.md`, `pairs2.md` | Two later forced-choice designs, 29 and 40 pairs, with the confounds of the first fixed. **Also retired unrated** — controlling confounds did not touch the flaw, which was the unit |
| `no-human-rater.md` | Why the human rating is cut, and precisely which claims the project may no longer make. Read before writing any sentence about prose *quality* |
| `rater-panel.md` | What replaces it: a cross-family model panel on passages, order-counterbalanced, with the writer's own model as the self-preference control |
| `sentences/sentences-key.md` | Its key, deliberately a separate file. Do not open it before the sheet is filled in |
| `sentences/sentences-claude.md` | The same sheet filled in by Claude, blind, into a separate file so the blank one stays blind. A dry run of the analysis, not the step |
| `sentences/machine-rating.md` | What that dry run says: the eras separate at 2.12 against 1.67, and **zero of seven** per-sentence signals correlate — the one that appeared to was a perfect era marker. Both are predictions to check the human rating against |

The `sentences/` files and `want-obstacle-cost.md` postdate the rest and answer a different kind
of question. The first files here ask *how does this prose score*; `want-obstacle-cost.md` asks
*is the plan a lever for this* and concludes no; `sentences/` asks *would you read it again*,
which no measurement in this project can reach — and the machine dry run does not reach it either,
because an LLM rating LLM prose may be measuring fluency-under-a-language-model rather than
whether a person turns the page.

Generated 2026-08-27 on an RTX 3080 10GB via Ollama, one draft per model, temperature 1.0, from
`examples/build_inherited_glitch.py` scene 1 (900-word target).

Reproduce the scoring against any of them without a model or an API key:

```bash
python -m redthread check runs/glitch --scene 1 --file docs/evidence/scene01-gemma3-12b.txt
```

Four checks — `check_pov`, `check_style_leak`, `check_brief_leak`, and the word-boundary fix in
`check_slop` — exist because of what these three files did. That is the argument for the `bench`
command: the failures that mattered were in the interaction between this project's brief and a
specific model, and no external benchmark could have surfaced them.

`debt-of-years-run.md` is the same argument at manuscript scale, and the more important document
of the two. The manuscripts themselves are not committed — `runs/` is gitignored, and the premises
behind them are the author's — so what is kept here is the record: which scene failed, what the
violation actually said, and which commit answered it.
