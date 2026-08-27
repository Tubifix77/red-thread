# Data dependencies

## slop_phrases.txt

A seed list of statistically over-represented phrasings in LLM prose. Checked by
`redthread.checks.check_slop` at MINOR severity.

**Provenance.** Entries are verbatim from
[`sam-paech/antislop-sampler`](https://github.com/sam-paech/antislop-sampler/blob/main/slop_phrase_prob_adjustments.json)
(MIT licence), retrieved 2026-08-27. The repo README states the file is "mostly auto-generated
by computing over-represented words in a large LLM-generated story dataset". The Antislop paper
(Paech, Roush, Goldfeder, Shwartz-Ziv — [arXiv 2510.15061](https://arxiv.org/abs/2510.15061))
reports the full framework suppressing 8000+ patterns with roughly a 90% reduction in repetitive
output while holding GSM8K and MMLU steady.

**Why not hand-write this.** Over-representation is defined against a human baseline. A list
assembled from intuition about what "sounds like AI" measures the author's ear, not the
distribution. Project-specific bans belong in `StyleContract.forbidden_phrases`.

### Getting the full list

```bash
curl -sSL https://raw.githubusercontent.com/sam-paech/antislop-sampler/main/slop_phrase_prob_adjustments.json -o data/slop_full.json
python -c "import json,pathlib; d=json.loads(pathlib.Path('data/slop_full.json').read_text()); pathlib.Path('data/slop_phrases.txt').write_text('\n'.join(k for k in (d if isinstance(d,dict) else [x[0] for x in d])), encoding='utf-8')"
```

Inspect the JSON's shape before trusting the one-liner — it has been both a dict and a list of
pairs across revisions.

### Known wrinkle: names

The list includes given names that are over-represented in LLM fiction (`elara`, `lyra`, `kael`,
`aria`, …). If your story legitimately uses one, `check_slop` skips any entry that appears in a
`StorySpec` character name, so no action is needed — but the collision is worth knowing about
before you name a protagonist Elara.

### The eventual upgrade

Post-hoc phrase checking is the weak version. Antislop's sampler suppresses these strings
*during* decoding by backtracking, and `antislop-vllm` works against any OpenAI-compatible
`/v1/completions` endpoint that returns top logprobs — which is the local-model path for this
project. Checking after the fact costs a repair round trip; suppressing at sample time costs
nothing.
