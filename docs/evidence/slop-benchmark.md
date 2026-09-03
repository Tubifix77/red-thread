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
**1,648 raw word entries — 1,632 unique** once lowercased, since 16 appear twice in different
cases (`intricate`, `relentless`, `meticulously` among them) — and **430 trigrams**. The scoring
set is the 1,632, because matching is against a set of lowercased tokens.

*(Two counting notes, both worth keeping. A fetched summary of this same file claimed 1,874
entries — a summary of data is not the data. And the 1,648/1,632 gap is why the figure appears
twice in this document: the pre-registration above was written from the raw length before the
loader deduplicated it, and the result below reports what was actually matched against.)*

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

- **FULL** — their 1,632 unique words. Circular on the overlap, reported for completeness only.
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
1,632 terms, so the great majority of the held-out list is entirely unaddressed by anything in
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
## Result: calibration passed, and **the prediction failed**

*3 September. `scripts/slop_benchmark.py`, lists and leaderboard as downloaded the same day.*

### The calibration gate passed, so the numbers below are the same measure as theirs

| model | their published slop/1k | my reimplementation | delta |
|---|---:|---:|---:|
| qwen3-4b | 23.63 | 23.46 | 0.7% |
| gemma-3-12b-it | 36.35 | 36.20 | 0.4% |
| claude-sonnet-4-5 | 9.72 | 9.71 | **0.1%** |

Within 1% on all three, against a ±5% bar. The implementation reproduces theirs, so a difference
found below is a difference in the prose and not in the code.

### The result

| | full list | held-out list |
|---|---:|---:|
| claude-sonnet-4-5 *(bare)* | 9.71 | **9.26** |
| qwen3-4b *(bare)* | 23.46 | **22.18** |
| **red-thread** *(gated pipeline, qwen3:8b)* | 25.15 | **24.44** |
| gemma-3-12b-it *(bare)* | 36.20 | 32.87 |
| human baseline | 6.90 *(published; their corpus is not in the repo, so it cannot be re-scored held-out)* | — |

**The pre-registered prediction was that red-thread would land between 6.90 and 23.63. It landed
at 24.44 — outside that range, and above bare qwen3-4b.** The registered falsifier read: *"if
red-thread's held-out score is worse than qwen3-4b's held-out score, the pipeline adds slop rather
than removing it."* By the letter, it fired.

### By the letter, not by the spirit — and the distinction is measurable

The gap is 2.26 per 1,000 words. Our **book-to-book** spread on the same metric:

    38 books of 8+ scenes    min 5.31   median 23.59   max 32.90   sd 6.65

**A 2.26 gap sits comfortably inside a standard deviation of 6.65**, and 12 of our 38 books score
*at or below* bare qwen3-4b. So the honest reading is not "worse" but **"not distinguishable, and
certainly not better"**. Claiming a regression from 2.26 against that spread would be the same
error as reading a two-run difference as a result.

*Their side cannot be given the same treatment: `leaderboard_results.json` pools each model into
one figure, so no per-sample spread is available for them and a proper test is not possible in
either direction. That asymmetry is a limit of their published data, not a choice.*

### The pooled figure is confounded, in this project's oldest way

    correlation, scene count vs held-out slop/1k     r = +0.672
    The Debt of Years   n=24   median 25.35   (scenes median 71)
    every other premise n=14   median 17.64   (scenes median 10)

And length is inseparable from premise **again**: every 60+ scene book is *The Debt of Years*, and
no other premise has one. Since the pooled score is token-weighted, **24.44 is substantially "the
slop rate of The Debt of Years at 71 scenes", not "red-thread's slop rate"** — the same caveat
that withdrew the length attribution from the wandering-mark finding.

The range is the striking part. Our best book, `glitch` at **5.31**, would sit above the human
baseline of 6.90 on their leaderboard; our worst, `deps-book` at **32.90**, is near bare
gemma-3-12b. One pipeline spans nearly the whole leaderboard depending on which book you score,
which says this metric is dominated by content and length rather than by anything the pipeline
does.

### The circularity worry was real and turned out small

    red-thread enforces        138 phrases
    of those, on their list     42
    held-out                 1,590 of 1,632 words — 97% unaddressed by this codebase
    cost of the overlap        25.15 full vs 24.44 held-out = 0.71

Methodologically that is good news: the full-list figure is nearly honest, because our gate and
their list barely intersect. Substantively it is the opposite — **`check_slop` does almost nothing
about what this benchmark measures.** The gate was built from a 138-phrase list and the benchmark
uses 1,632; suppressing 42 words moves the score by less than one point.

### What this establishes

- **A first external comparison exists and this project is mid-field on it**, near a bare 4B model
  of its writer's own family and far from `claude-sonnet-4-5` at 9.26 or the 6.90 human baseline.
- **The pipeline does not reduce slop.** Gating, repair and best-of-three selection buy nothing
  measurable on this axis. That is a real negative about the architecture, not about the model.
- **It is still not a model-versus-model result**, and the pre-registration said so before the
  number existed: their samples are single-pass raw output, ours are gated and repaired, which
  favours us — and we came out no better anyway, which makes the negative harder to dismiss
  rather than easier.
- **The obvious lever is now named and cheap**: `check_slop` enforces 138 phrases against a
  public 1,632-word list by the same author. Extending it is a data change, not a design change.
  **That is a separate experiment and needs its own pre-registration** — and it would be scored
  on the held-out remainder, never on the words newly added, or it measures itself.
