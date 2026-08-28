# Evidence

The raw material behind the claims in [../MODELS.md](../MODELS.md), kept so they can be checked
rather than taken on trust.

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
