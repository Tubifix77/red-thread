# Plan 2 — from measured to better

*1 September 2026. The successor to [PLAN.md](PLAN.md), written at its 24-of-25 milestone. Drafted
under the zero-assumption contract: every external claim below carries a source fetched live
today or a still-verified ledger row (`.claude/zero-assumption/memory.md`); every internal claim
cites a file in this repository. Nothing is from model memory.*

PLAN.md built the instruments and audited what exists. This plan spends them. Its thesis comes
from forcing three opposed readings of the milestone to coexist:

- *the reader-firsters:* nothing in the panel is known to track what a person feels — the machine
  dry run predicts **zero of seven** per-sentence signals correlate
  ([machine-rating.md](evidence/sentences/machine-rating.md)), and the strongest off-the-shelf
  LLM judge reaches only **73%** agreement with human preference on creative writing
  ([LitBench](https://arxiv.org/abs/2507.00769)) — so quality work on top of unvalidated proxies
  is Goodhart's law with a GPU bill.
- *the reliability engineers:* the writer stops 3 times in 10 ([STATUS.md](STATUS.md)) and nothing
  on disk records which repair rung ever fired ([PLAN.md](PLAN.md), step 7's open question) — and
  this lane needs no human validation, because its ground truth is code-checkable.
- *the economists:* 33 finished runs sit in `runs/` and most of the questions below can be asked
  of them for zero GPU-hours before any new book is written.

**So: three budgets, one gate.** Reliability and Instrument work is ungated and starts now.
Reader-facing quality work is gated on step 21's human sheet, because both the external evidence
and this project's own dry run say the proxies are unproven. Within every budget, cheapest
information first.

The seven rules of [PLAN.md](PLAN.md) apply to every step here unchanged. Rule VII is applied at
design time: each experiment below names its statistic *and the statistic's type*, so a per-scene
mean is never again asked to see an accumulating effect.

---

## What the milestone leaves broken, measured

| # | weakness | evidence |
|---|---|---|
| W1 | 3 of 10 unattended runs halt; all three audited halts ended in repair failing to converge within its attempt budget (two of them on genuine contradictions), and no record exists of which rung fires or converges | [STATUS.md](STATUS.md); [PLAN.md](PLAN.md) step 7; `scenes/*.json` stores only an `attempts` count ([project.py](../redthread/project.py)) |
| W2 | The noise floor is one novel's: 3 of 11 measures land outside it on a fresh premise with nothing ablated | [fresh-premise-panel.md](evidence/fresh-premise-panel.md) |
| W3 | No measure in the panel is known to correspond to a reading; the dry run predicts none does | [machine-rating.md](evidence/sentences/machine-rating.md); step 21 blank |
| W4 | Manuscript-level duplication grows with length: .066 across a book vs .002 within any scene | [STATUS.md](STATUS.md) |
| W5 | Two of four mechanism switches have never been ablated: `--no-repeople`, `--no-model-refrains` | [cli.py](../redthread/cli.py); phase 1 tested the other two ([phase1-ablations.md](evidence/phase1-ablations.md)) |
| W6 | 18 of 33 runs are one premise; every strong verdict is *The Debt of Years* at 71 scenes | corpus count, [MEASUREMENTS.md](MEASUREMENTS.md) |

---

## The one hard ordering

**Every GPU step that reuses existing runs as its control (28, 29, 30) must finish before any
write-path change lands (31, 32).** The floor, both phase 1 ablations and the step 25 runs all
share a writer, verified by `scripts/same_code.py`; the first commit to `pipeline.py` ends that
era, and after it every comparison against those runs differs by more than its switch. PLAN.md
learned this as a freeze; here it is a sequencing rule. The zero-GPU steps (26, 27) and the human
step (33) are unaffected.

---

## Phase 7 — Instrument, from the shelf  *(0 GPU-h)*

**26. Mine the cross-book floor out of the corpus that already exists.** Four premises in `runs/`
have true replicates (*Debt of Years* ×18, *Four-Minute Tide* ×4, *Keeper's Fourth Book* ×2,
*Ink of the Drowned* ×2). For every measure in the panel: within-premise spread vs between-premise
spread, from disk. The deliverable is a **portable subset** — the measures whose between-premise
movement stays inside their within-premise floor — published as `checks.PORTABLE`, with
`clears_noise` refusing cross-book comparisons on any measure outside it.

*Pre-registered expectation, written before the analysis runs: step 25 already puts
`gesture_rate`, `recap_grammar` and `dialogue_share` outside; the candidates it left standing are
shares and zero-anchored counts (`recap_block_share` at zero everywhere). If fewer than three
measures are portable, that is the finding — cross-book claims become impossible in code, not
merely discouraged.*

**Kill criterion:** none — this is calibration, and both outcomes are deliverables.

*One honesty constraint carried from PLAN.md: the 18 Debt runs span several code eras
([MEASUREMENTS.md](MEASUREMENTS.md) names the split), so within-premise spread is computed only
over same-era replicates, never pooled across eras — pooling would inflate the within-premise
floor and launder unportable measures into the subset.*

**27. Price the two-run screen.** A four-run floor costs ~5 GPU-h before an experiment starts
([phase1.sh](../scripts/phase1.sh)); if an n=2 floor predicts the n=4 verdict often enough, cheap
screening becomes honest. From the two existing four-run sets (floor, gesture-at-n=4): bootstrap
every 2-subsample floor, count how often the 2-run floor would have flipped a phase 1 verdict.
Deliverable: a stated error rate and a written protocol — *screen at n=2, confirm at n=4, never
publish from a screen* — or, if the error rate is bad, a sentence in MEASUREMENTS.md saying n=2
screening is dead and why.

---

## Phase 8 — the last two switches, against the floor that exists  *(~6 GPU-h, before any write-path change)*

**28. Ablate the model-refrain list** (`--no-model-refrains`, [cli.py](../redthread/cli.py)).
Two runs of the *Debt* plan, off, against the four floor runs. The list exists because 23% of a
book's refrains are the model's own constructions, found in all seven books then measured
([MEASUREMENTS.md](MEASUREMENTS.md), controls section).

- **Statistic:** `duplication_manuscript` (floor 19%) and `repetition_concentration` (floor 38%)
  — both manuscript-level aggregates, so accumulation is already in the number (rule VII typed).
- **Kill criterion:** both inside the floor → the list is prompt weight with no measurable return;
  it comes out of the brief (the data file stays, as measurement).

**29. Ablate the re-people pass** (`--no-repeople`). Two runs, off, same design. This pass was 90%
broken behind a green suite until step 7 rebuilt it; it has never been tested against its absence.

- **Statistic, two-stage:** first the deterministic one — solo-scene count in the written book's
  plan (the pass acts on the plan, so its first-order effect is countable before a word of prose
  is judged); then `dialogue_share` (floor 11%, a share — rule VII typed) for the prose-level
  claim.
- **Kill criterion:** if solo-scene count does not move, the pass does nothing and comes out
  regardless of prose measures. If it moves but `dialogue_share` stays inside the floor, the pass
  is doing plan work with no prose consequence — it stays, restated as a plan-repair tool rather
  than a quality mechanism.

**30. Extend the premise-B floor to n=4** (+2 runs of the 24-scene `solo-b2` plan, ~1.5 GPU-h,
sharing the frozen writer with the two step 25 runs). This is the first full floor on a second
book, and it tests step 27's screening protocol out of sample: the protocol predicts the n=4
floor from the n=2 half; here is an n=4 floor it has never seen.

---

## Phase 9 — Reliability  *(instrumentation first; the fix is designed from its data)*

**31. Instrument the repair ladder.** The change PLAN.md deliberately deferred: `pipeline.py`
records, per scene, which repair kinds were attempted, which converged, and at which rung the
scene committed or halted. Backfill what the corpus can give (the `attempts` distribution over
1,299 scenes — already on disk); everything rung-level starts accruing from the first
instrumented run. Zero experiments, zero claims — observability only, and the write-path change
that ends the frozen era, which is why phase 8 precedes it.

**32. Fix repair convergence, as an experiment.** Designed *after* 31's first table exists —
committing to a mechanism before seeing which rung fails is how the gesture criterion nearly
deleted a working mechanism. The candidate space, each traced to evidence:

- **Inject the check's own evidence span into the repair prompt** (localized, sentence-level
  repair). The self-correction literature is unambiguous about why this direction and not
  critique: self-correction works when *reliable external feedback* exists and "the bottleneck is
  in feedback generation" ([Kamoi et al., TACL 2024](https://arxiv.org/html/2406.01297v3)) —
  red-thread's checks *are* reliable external feedback, already located to spans; ConWriter's
  localized bounded-retry repair is the published shape of this
  ([ConWriter](https://arxiv.org/html/2608.05169v1), ledger row 2026-08-27).
- **Fresh-draft-after-k policy.** The scale test recorded a scene that failed five repairs and
  committed on a second whole attempt with nothing changed
  ([sixty-thousand-word-run.md](evidence/sixty-thousand-word-run.md)) — sometimes the ladder is
  the wrong tool and the sampler is the right one.
- **What is explicitly out:** adding an LLM self-critique rung. Same source, same sentence — no
  demonstrated success from prompted-LLM feedback outside tasks suited to it.

Design constraints:

- **Statistic, pre-registered now:** attempts-to-commit distribution per scene (Mann–Whitney,
  new runs vs the four floor runs' backfilled distribution) as primary — attempts are per-scene
  and independent, so a distribution over scenes is the right instrument, stated per rule VII.
  Halt rate as secondary only (binomial; at a 3-in-10 base rate, n=4 cannot make it primary).
- **Control caveat, stated before anyone runs it:** the floor runs predate the instrumentation,
  so the comparison is valid only on fields the backfill actually has (`attempts`); rung-level
  claims get no control until a post-31 baseline set exists. Two comparisons, two eras, never
  mixed.
- **Kill criterion:** if 31's data shows halts dominated by *true* contradictions (the ledger
  catching real state violations — the system working, per the audited halts in
  [phase1-ablations.md](evidence/phase1-ablations.md)), then convergence is not the problem,
  this step closes as "halts are correct behavior", and the honest work is the resume button:
  `replicate --resume-halted-once`, an engineering item, not an experiment.

---

## Phase 10 — Reader  *(gated on step 21; nothing here starts before the sheet is rated)*

**33. Score the human sheet** — PLAN.md's step 21, unchanged, twenty minutes of Tue. The two
machine predictions are already committed and falsifiable
([machine-rating.md](evidence/sentences/machine-rating.md)): the eras separate in the same
direction, and no per-sentence signal reaches r = 0.3. Every branch is actionable:

| human result | consequence |
|---|---|
| eras separate, signals still < 0.3 | the prose work is real to a reader and the panel is a regression detector, never a quality claim — written into checks.py as a comment on the panel itself |
| eras do not separate | two days of measurable improvement produced prose no reader prefers; phase 10 stops here and the panel's purpose is re-argued from zero |
| any signal ≥ 0.3 | the dry run's central caveat (an LLM rating LLM prose) is demonstrated live, and the signal that did it becomes the panel's first validated member |

**34. A trained judge, advisory only — feasibility before commitment.** The external evidence
says zero-shot judging is a ceiling (73%) and *trained* preference models beat it (78%,
[LitBench](https://arxiv.org/abs/2507.00769)); at book length, an 8B summary-based judge
(NovelCritique) outperforms GPT-4o in aligning with human evaluations
([LongStoryEval](https://arxiv.org/abs/2512.12839)). Both are open releases; whether either runs
under Ollama on a 10GB card is **unverified until tried** — the feasibility check is the first
half of this step and its only committed part. If feasible: pre-registered pairwise test, judge
prefers current-era over pre-prose-work *Debt* chapters in ≥ k of n pairs (k set by binomial
power before the runs, not after). **Rule VI stands: nothing model-judged ever gates a commit.**
Advisory scoring only, and only if step 33 confirmed the eras separate for a person — a trained
judge calibrated against a direction no human endorsed would be Goodhart with better paperwork.
One more inherited rule applies if it ever scores anything: the judge must not be the writer —
"generally best practice to use a different model to evaluate than the model used to generate"
([Anthropic, define success](https://platform.claude.com/docs/en/test-and-evaluate/define-success))
— which `qwen3:8b`-judging-`qwen3:8b` would violate twice over.

**35. Only then: new prose mechanisms.** The two StoryScope idiosyncrasy families red-thread has
never touched — reduced intertextuality (named references 24% AI vs 47% human) and structural
linearity (no-subplots 79% vs 57%) ([StoryScope](https://arxiv.org/html/2604.03136v1), ledger row
2026-08-27) — are the shelf. Each would enter as a phase-1-shaped ablation: switch built first,
statistic typed per rule VII, floor named, kill criterion before GPU. Deliberately not designed
further here: mechanisms sketched before step 33's verdict would be designs for a panel nobody
has validated.

---

## What this plan refuses to do

- **Swap the writer.** `qwen3:8b` in every role stays; orchestration is the product and its
  levers are not exhausted ([MODELS.md](MODELS.md); the sampler-default finding in
  [MEASUREMENTS.md](MEASUREMENTS.md)).
- **Build a logit-level anti-slop sampler.** Verified today: Ollama exposes no logprobs on any
  documented endpoint — not `/v1/chat/completions`, not `/v1/completions`, not the native API —
  and the request for it is closed as not planned
  ([docs](https://docs.ollama.com/api/openai-compatibility),
  [api.md](https://github.com/ollama/ollama/blob/main/docs/api.md),
  [#16117](https://github.com/ollama/ollama/issues/16117)). String-level machinery
  (step 28's list, the refrain feedback) is the honest local ceiling; FTPO-style token work
  would need a different serving stack and is out of scope.
- **Extend the measure panel before step 33.** The dry run predicts the panel is orthogonal to
  reading; building measure #12 before a human confirms or refutes that is effort spent on the
  wrong side of the gate.
- **Compare across books on non-portable measures.** After step 26, `clears_noise` enforces this
  rather than a doc pleading for it.

## Shape of it

| phase | steps | GPU | gate | most likely outcome |
|---|---|---:|---|---|
| 7 — instrument, from the shelf | 26–27 | 0 h | none | a portable subset exists and it is small |
| 8 — the last two switches | 28–30 | ~6 h | before any write-path change | at least one of the two mechanisms comes out |
| 9 — reliability | 31–32 | ~5 h | after phase 8 | the ladder's real convergence rates, then one targeted fix — or the finding that halts are correct |
| 10 — reader | 33–35 | ~2 h + Tue | **step 33 is the gate** | the panel becomes either validated or explicitly regression-only |

**Sequencing:** 26, 27 anytime. 28–30 next and before 31. 33 whenever Tue has twenty minutes —
it blocks nothing before phase 10 and everything in it. The single most valuable hour on this
list is still the human one, and this plan inherits PLAN.md's closing prediction unchanged.
