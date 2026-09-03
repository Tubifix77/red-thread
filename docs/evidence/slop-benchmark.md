# Where does this prose sit on an external benchmark? Pre-registered

*3 September 2026. Committed before red-thread's own score is computed. Thresholds and the
non-comparability list below cannot move afterwards.*

## Why this is the only external comparison available

Everything measured in this project so far is internal — red-thread against red-thread. The one
external instrument that fits the constraints is **EQ-Bench's slop score**
([eqbench.com/slop-score.html](https://eqbench.com/slop-score.html),
[sam-paech/slop-score](https://github.com/sam-paech/slop-score)):

- **Deterministic.** No LLM judge, so it needs no API key — and it is not the quality measurement
  this project cut ([no-human-rater.md](no-human-rater.md)). It counts words.
- **Computable on external text.** Their harness is not required; the lists and the algorithm are
  public, so red-thread's existing 1.6M words can be scored as they stand.
- **It publishes a human baseline**, which almost nothing else here has.

**Their sibling "repetition" metric is deliberately excluded.** It is *not* this project's
`duplication_ratio` despite the shared word: theirs sums the over-representation of top
words/bigrams/trigrams against the `wordfreq` English corpus across a whole multi-prompt corpus;
ours is the fraction of one scene's 4-grams that repeat. Putting our `.002` beside their column
would be precisely the error rule II exists for, and it was only avoided by reading
`core/metrics.py` rather than the column heading.

## The algorithm, read from source rather than described

From `js/metrics.js`: tokenise to lowercase `[a-z]+(?:'[a-z]+)?`, then

    wordScore    = (tokens present in slop_list.json)          / total_tokens * 1000
    trigramScore = (consecutive 3-token windows in trigram list)/ total_tokens * 1000

Whole-token matching, every occurrence counted. Lists as downloaded 3 September:
**1,648 words** and **430 trigrams**. *(A fetched summary of the same file claimed 1,874 words;
the count above is from the file. A summary of data is not the data.)*

## The comparison set, and the circularity that makes one arm mandatory

Their published `slop_list_matches_per_1k_words`, from `data/leaderboard_results.json`
(generated 2025-11-07, 23 models):

| model | slop/1k |
|---|---:|
| `gemma-3-27b-it-antislop` | **5.61** |
| **human baseline** | **6.90** |
| claude-sonnet-4-5 | 9.72 |
| gpt-5-mini | 15.44 |
| o3 | 19.89 |
| **qwen3-4b** — nearest relative of our writer | **23.63** |
| mistral-nemo | 26.41 |
| gemma-3-27b-it | 32.27 |
| gemma-3-12b-it — *we run this locally* | 36.35 |
| gemini-2.5-flash / deepseek-r1 | 40.16 |
| gemma-3-4b-it | 40.44 |

**Look at the top row.** An antislop-tuned model scores *better than human* because it was trained
to suppress this exact list. **red-thread is in the same position**: `checks.check_slop` enforces
138 phrases from `sam-paech/antislop-sampler`, the same author's list, and four of six probed
terms (`kaleidoscope`, `delve`, `elara`, `tapestry`) appear in both. A good full-list score would
therefore be partly a measurement of our own gate.

So two arms, and only one of them is reportable as evidence:

- **FULL** — their 1,648 words. Circular on the overlap, reported for completeness only.
- **HELD-OUT** — their list minus every phrase red-thread enforces. **This is the arm that
  counts**, and it is rule II applied to an external benchmark: score against what the system was
  not built to match.

## A calibration gate that can void the whole exercise

Their 23 published scores were produced by their code. Mine is a reimplementation, so **before
any red-thread number is computed or reported, my implementation must reproduce their published
figure for three models whose raw outputs I re-score with it**: `qwen3-4b`,
`gemma-3-12b-it` and `claude-sonnet-4-5`.

- **Pass:** every one of the three within **±5%** of the published value.
- **Fail:** the implementation is wrong, and **no comparison is reported at all** — not a
  corrected one, not a caveated one. A reimplementation that cannot reproduce known values is
  measuring something else, and this project has shipped that mistake before.

## The prediction, fixed now

On the **held-out** list, red-thread lands **between the human baseline (6.90) and raw qwen3-4b
(23.63)**. Reasoning stated so it can be wrong for a nameable reason: our slop gate covers 138 of
1,648 terms, so the great majority of the held-out list is entirely unaddressed by anything in
this codebase, and the pipeline's other pressures do not push against it.

**The falsifier, and it is a live possibility:** if red-thread's held-out score is **worse than
qwen3-4b's held-out score**, the pipeline *adds* slop rather than removing it. Best-of-three
candidate selection optimises for other things and could plausibly favour the more ornate draft —
which is exactly the direction [cross-scene-tics.md](cross-scene-tics.md) found this writer
leaning, with `as if` in 70-82% of scenes and `the weight of` in ~72%.

## What this can and cannot claim — written before the number exists

**Cannot, and this is the whole of Tue's own framing of it:** *"they would never accept our
result as directly comparable."* Correct, and for a reason bigger than corpus differences:

- **Their samples are single-pass raw model output. red-thread's are gated, repaired, and
  best-of-three selected.** This compares a *pipeline* to *bare models*, and it favours the
  pipeline. It is not a model-versus-model result and must never be quoted as one.
- **Content differs.** Their 300 samples per model span many prompts and genres; ours is 11
  premises dominated by one novel replicated 22 times. Slop rates are content-sensitive.
- **The writer is not the listed model.** Ours is `qwen3:8b`; their nearest is `qwen3-4b` — a
  different size and vintage.
- **Length and unit differ.** Their samples are short pieces; ours are 71-scene books.

**Can:** "red-thread's committed prose, scored with EQ-Bench's slop list and algorithm, sits at
X per 1,000 words on the held-out portion of that list — against a human baseline of 6.90 and
bare qwen3-4b at 23.63 — where the comparison is a gated pipeline against ungated single-pass
generation."

That is a narrow claim and it is the first external one this project has ever been able to make.

---

*Result appended below after the calibration gate and the scoring run. Nothing above changes.*
