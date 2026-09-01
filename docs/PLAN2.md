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
| W5 | **Two of six mechanisms are inert on the measured corpus** — the re-people pass (gated at 15%, plan at 14.08%) and `drop_unavoidable_bans` (0 of 3 phrases). Ablating either compares a condition against itself | [evidence/mechanism-coverage.md](evidence/mechanism-coverage.md) |
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

**26. Mine the cross-book floor out of the corpus that already exists.** ✅ **Done, same day —
3 of 13 measures are portable: `refusal_rate`, `refusal_per_ask`, `somatic_share`.** Published as
`checks.PORTABLE` and enforced: `clears_noise(..., cross_book=True)` raises on everything else,
and `redthread measures` detects differing titles itself. Full table in
[evidence/portable-measures.md](evidence/portable-measures.md).

*The step was designed believing four premises had replicates; measurement corrected it before
anything was computed. The Four-Minute Tide ×4 are four different plans, and `keeper`/`keeper2`
differ in both plan and story — so the real groups are two, Debt n=4 and Ink n=2, and the
between-premise estimate is one premise pair until step 30. Of the pre-registered expectations,
the three step-25 failures failed again as predicted; `recap_block_share` turned out vacuous
rather than portable (zero everywhere has no floor to transfer); and `dialogue_share` — a share,
the predicted class — fails its own floor on the second book. The unpredicted finding:
the refusal pair phase 4 was stopped over is the most premise-stable part of the panel.*

*The pre-registered expectation and its scoring are preserved verbatim in
[evidence/portable-measures.md](evidence/portable-measures.md) — kept because a pre-registration
that quietly vanishes when partly wrong is worse than none.*

**27. Price the two-run screen.** ✅ **Done, same day — a 2-run floor is half the 4-run floor,
and every one of its errors is a false claim.** Across 72 verdict tests (both phase 1 comparisons
× every live measure × all 6 two-run control floors): 15 flips, **all 15 false positives, 0 false
negatives** — step 6's 12.6% difference would have been called a real effect by 3 of the 6
possible n=2 floors. The protocol the numbers wrote: **an n=2 screen may kill and may never
confirm** — a difference inside a 2-run floor may be dropped (~2.5 GPU-h instead of ~5, exception
rate 0 in 72), a difference outside one decides only where the next GPU-hours go, and nothing
publishable ever comes from a screen. Full table and limits in
[evidence/two-run-screen.md](evidence/two-run-screen.md); re-run against the premise-B n=4 floor
after step 30 before trusting it off *The Debt of Years*.

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

**29. Test the re-people pass.** ⚠️ **Stage 1 done, zero GPU — and it killed two designs. The
pass has never run on any book this project has measured.** It is gated: below a 15% solo share
it returns 0 immediately. The plan every phase 1 run, the four-run floor and both step 25 panels
were written from sits at **10 solo of 71 = 14.08%**, one scene under the gate. Full derivation
in [evidence/repeople-never-fired.md](evidence/repeople-never-fired.md).

*So W5 understates this: the pass is not merely un-ablated, it is **inert on the entire measured
corpus**, and an ablation on the* Debt *plan would have returned "no difference" for a reason
having nothing to do with whether the mechanism works. Both earlier designs are dead — the
original (an ablation flag on `replicate`, which does not exist) and its first correction (a
transform of the* Debt *plan, which the gate declines).*

**Stage 2, the only design the gate permits (~3 GPU-h, deferred):** use a plan where the gate
opens — `solo-a1` at 9 of 24 (38%) is the strongest, `solo-a3` at 25% the nearest the boundary.
Produce a re-peopled twin with `redthread repeople --write` (one model call over a fixed plan,
not a regenerated plan), write n=2 from each.

- **Statistic:** `dialogue_share` (floor 11%, a share — rule VII typed), within one premise,
  because step 26 established `dialogue_share` is *not* portable across books.
- **Kill criterion:** inside the floor → the pass stays as a plan-repair tool and the prose-quality
  claim is dropped.
- **Prerequisite, and the reason this is deferred:** the floor for a 24-scene premise-B plan does
  not exist yet at n=4, and `solo-a1` is a *third* premise with no floor at all. This runs after
  step 30, or it has nothing to be judged against.

**30. Extend the premise-B floor to n=4** (+2 runs of the 24-scene `solo-b2` plan, ~1.5 GPU-h,
sharing the frozen writer with the two step 25 runs). This is the first full floor on a second
book, and it tests step 27's screening protocol out of sample: the protocol predicts the n=4
floor from the n=2 half; here is an n=4 floor it has never seen.

---

## Phase 9 — Reliability  *(instrumentation first; the fix is designed from its data)*

**31. Instrument the repair ladder.** ◐ **Backfill done (zero GPU); the code change waits for
phase 8.** Full analysis in [evidence/repair-backfill.md](evidence/repair-backfill.md).

*The backfill produced a sharper specification than the step had.* `attempts` is the only repair
field on disk and it is **a sum of two unrelated quantities** — `candidates_drafted + repairs` —
of which only the sum is persisted, so repairs cannot be recovered exactly from any run ever
written. Subtracting the default candidate count gives the control anyway: across the four floor
runs, **72.5% of scenes commit with no repair, 20.4% take one, 7.1% take two or more** (n=284).

So `pipeline.py` must record, per scene: (1) **`candidates_drafted` and `repairs` separately** —
the smallest change with the largest return, and the one that makes every future run
interpretable; (2) which repair kinds were attempted and which converged; (3) the terminal state,
committed or halted-on-what-after-how-many. Observability only, zero claims — and the write-path
change that ends the frozen era, which is why phase 8 precedes it.

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
  new runs vs the four floor runs' backfilled distribution, n=284) as primary — attempts are
  per-scene and independent, so a distribution over scenes is the right instrument, stated per
  rule VII. Halt rate as secondary only (binomial; at a 3-in-10 base rate, n=4 cannot make it
  primary).
- **Its resolution is the tail, and that is now on the record before any result exists.** 72.5%
  of the control sits on one value, so the test is powered by the ~27% of scenes that repair at
  all. An intervention halving repairs moves 78 of 284 scenes and is detectable; one that only
  speeds up already-clean scenes is invisible to it. **A null result here means "no effect on the
  repairing quarter", not "no effect"** — written down now so it cannot be softened later.
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
([LongStoryEval](https://arxiv.org/abs/2512.12839)). **The feasibility half is now done, from the sources rather than from assumption, and it is
worse than "both are open releases" suggested:**

- **LitBench's reward models are not released.** Its HuggingFace collection holds three
  *datasets* — Train, Rationales, Test — and the paper. The Bradley–Terry and generative models
  that scored 78% are not there
  ([collection](https://huggingface.co/collections/SAA-Lab/litbench-68267b5da3aafe58f9e43461)).
  Reproducing them means training from the 43,827-pair corpus, which is a project, not a step.
- **NovelCritique's weights are released, with two catches.** It is Llama-3.1-8B-Instruct
  fine-tuned — a size the card can hold at Q4 — but the checkpoint is hosted on a *personal
  university SharePoint link*, and the README states **no licence**
  ([repo](https://github.com/DingyiYang/LongStoryEval)). Unlicensed weights from a personal link
  are not something to pull into this project, and it would additionally need GGUF conversion
  before Ollama could serve it.

**So the step as drafted has no cheap path, and that is the finding.** Both remaining options are
expensive: train a reward model from LitBench's released corpus, or ask the NovelCritique authors
for a licence. Neither is justified before step 33 says the direction is real. If feasible: pre-registered pairwise test, judge
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
| 7 — instrument, from the shelf | 26–27 ✅✅ | 0 h | none | done: 3 of 13 portable; n=2 screens may kill, never confirm |
| 8 — the last two switches | 28–30 | ~6 h | before any write-path change | at least one of the two mechanisms comes out |
| 9 — reliability | 31 ◐ –32 | ~5 h | after phase 8 | 31's backfill done: 72.5% of scenes commit with no repair; the ladder is exercised on one scene in four |
| 10 — reader | 33–35 | ~2 h + Tue | **step 33 is the gate** | the panel becomes either validated or explicitly regression-only |

**Sequencing:** 26, 27 anytime. 28–30 next and before 31. 33 whenever Tue has twenty minutes —
it blocks nothing before phase 10 and everything in it. The single most valuable hour on this
list is still the human one, and this plan inherits PLAN.md's closing prediction unchanged.
