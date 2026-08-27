# Evidence

The raw material behind the claims in [../MODELS.md](../MODELS.md), kept so they can be checked
rather than taken on trust.

| File | What it is |
|---|---|
| `scene01-brief.md` | The exact brief handed to each model — assembled by `redthread brief`, not written by hand |
| `scene01-qwen3-8b.txt` | 948 words. On target. Opens with the style contract's own sample sentence, verbatim |
| `scene01-gemma3-12b.txt` | 542 words. Written entirely in the first person against a `third limited` contract |
| `scene01-phi4-14b.txt` | 506 words. Complete but short; closes on thematic gloss |

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
