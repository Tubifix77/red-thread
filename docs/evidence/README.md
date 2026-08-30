# Evidence

The raw material behind the claims in [../MODELS.md](../MODELS.md), kept so they can be checked
rather than taken on trust.

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
| `want-obstacle-cost.md` | A second quality axis, measured and then not built: two prose measures that vary, a plan-side lever that scores r = 0.111 against a 0.4 bar, and the audit that found both measures 56% contaminated |
| `sentences/sentences.md` | A hundred sentences, half from each era, shuffled and unlabelled — the one thing here that needs a person rather than a measurement |
| `sentences/sentences-key.md` | Its key, deliberately a separate file. Do not open it before the sheet is filled in |

The last three postdate the rest and answer a different kind of question. The first two files
here ask *how does this prose score*; `want-obstacle-cost.md` asks *is the plan a lever for this*
and concludes no; `sentences/` asks *would you read it again*, which no measurement in this
project can reach.

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
