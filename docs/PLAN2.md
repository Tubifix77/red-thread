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
Reader-facing quality work was gated on step 21's human sheet, because both the external evidence
and this project's own dry run said the proxies are unproven. Within every budget, cheapest
information first.

***Superseded 3 September: that gate never opened and never will.*** *Step 21 and the whole of
phase 10 are **cut** — three reader instruments failed on the unit rather than the confounds
([evidence/no-human-rater.md](evidence/no-human-rater.md)), and the model panel built to replace
them did not clear its own pre-registered bar
([evidence/rater-panel.md](evidence/rater-panel.md)). Every "gated on step 21/33" sentence below
therefore describes a gate that is now closed permanently. The phase text is kept unedited
because its branch tables are exactly what can no longer be evaluated.*

The rules of [PLAN.md](PLAN.md) apply to every step here unchanged. Rule VII is applied at
design time: each experiment below names its statistic *and the statistic's type*, so a per-scene
mean is never again asked to see an accumulating effect.

**This plan also produced rule VIII, at its own step 29:** *before measuring a difference in
something, confirm the something ever happens.* Every ablation below now states what fraction of
the target corpus its mechanism acts on, checked with `scripts/mechanism_coverage.py` before any
GPU-hour is committed.

---

## What the milestone leaves broken, measured

| # | weakness | evidence |
|---|---|---|
| W1 | 3 of 14 unattended runs halt; all three audited halts ended in repair failing to converge within its attempt budget (two of them on genuine contradictions). ~~No record exists of which rung fires~~ — **step 31 closed that**: `candidates_drafted`, `repairs`, a rung-level `repair_log` and `halts.json` are now persisted | [STATUS.md](STATUS.md); [evidence/repair-backfill.md](evidence/repair-backfill.md) |
| W2 | The noise floor is one novel's: 3 of 11 measures land outside it on a fresh premise with nothing ablated | [fresh-premise-panel.md](evidence/fresh-premise-panel.md) |
| W3 | No measure in the panel is known to correspond to a reading; the dry run predicts none does | [machine-rating.md](evidence/sentences/machine-rating.md); step 21 blank |
| W4 | Manuscript-level duplication grows with length: .066 across a book vs .002 within any scene | [STATUS.md](STATUS.md) |
| W5 | **Two of six mechanisms are inert on the measured corpus** — the re-people pass (gated at 15%, plan at 14.08%) and `drop_unavoidable_bans` (0 of 3 phrases). Ablating either compares a condition against itself | [evidence/mechanism-coverage.md](evidence/mechanism-coverage.md) |
| W6 | 22 of 39 runs are one premise; every strong verdict is *The Debt of Years* at 71 scenes | corpus count, [MEASUREMENTS.md](MEASUREMENTS.md) |

---

## The one hard ordering — satisfied, and then spent

**Every GPU step that reused existing runs as its control (28, 29, 30) had to finish before any
write-path change landed (31, 32).** The floor, both phase 1 ablations and the step 25 runs all
shared a writer, verified by `scripts/same_code.py`; the first commit to `pipeline.py` ended that
era, and after it every comparison against those runs would differ by more than its switch.

**It held.** Phase 8 closed on 2 September at 03:15 with the guard passing at the start of every
chain, and the three write-path changes landed afterwards. The ordering is now history rather than
a constraint — see [Picking this up](#picking-this-up) for what it cost, which is that the four
floor runs no longer describe this writer.

*A hole in the guard was found and closed on the way: both checks compared git against git while
Python imports the working tree, so an uncommitted edit to `pipeline.py` passed them both. That
was open for the whole of phase 1 and nothing appears to have fallen through it — the chains were
launched from clean trees — but the guard had been refusing on the strength of a comparison it was
not making.*

---

## Phase 7 — Instrument, from the shelf  *(0 GPU-h)*

**26. Mine the cross-book floor out of the corpus that already exists.** ✅ **Done, same day —
3 of 13 measures are portable at n=2, corrected to 2 of 13 at n=4: `refusal_rate` and
`refusal_per_ask`.** `somatic_share` was in the set for four hours and [step 30](#) removed it —
its *spread* widened once four runs existed to measure it over, which is
[step 27](evidence/two-run-screen.md)'s protocol arriving from the other side. `checks.PORTABLE`
holds two. Published as
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

✅ **Killed at n=2, kept at n=4 — and the screen that killed it was wrong.** The primary
criterion fires at both n: `duplication_manuscript` 12% against 19%, `repetition_concentration`
14% against 38%. **The list does not move book-level repetition.** But the pre-registered
*targeted* statistic reverses — 5.59 with the list on against **8.99** with it off, a **46.6%**
difference against a 25% floor, perfect separation, exact rank-sum **p = 0.0143**.

Per the reading committed before those runs existed: **the list stays, restated as a narrow
three-phrase filter and not a repetition mechanism.** Its claim in this plan shrinks to exactly
that. Full record: [evidence/step28-model-refrains.md](evidence/step28-model-refrains.md).

*The methodological result is larger than the mechanism.* Step 27's protocol licensed a kill at
n=2, and that kill was a **false negative** — the ablated mean moved 7.16 → 8.99 with two more
runs, on a 60% spread. Step 27's analysis only ever varied the **control floor**, never the
condition group, so its licence has been corrected at source: *a two-run **floor** may kill; a
two-run **condition** may not be used for anything.* What prevented the deletion was step 6's
precedent, not the protocol — the second time a documented kill has been suspended on that
precedent and the second time the re-test reversed it.

**29. Test the re-people pass.** ❌ **Stage 2 DROPPED permanently, 3 September.** Stage 1's result settled it: the pass is **inert** on every book this project has measured, so there is nothing for stage 2 to measure a difference in — rule VIII, confirm the something happens before measuring a difference in it. Stage 2 would need a fresh premise-A plan *and* a floor for that premise, several GPU-hours, to characterise a mechanism already known not to fire. **Stage 1 stands as the answer.**

*Stage 1, for the record.* ⚠️ **Zero GPU — and it killed two designs. The
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

**30. Extend the premise-B floor to n=4.** ✅ **Done — and it removed a measure from
`checks.PORTABLE`.** Four panels at 24 scenes, no halts. `somatic_share` drops out: not on value
(its two books' means differ by 14%, inside its 19% floor) but on **spread within the second
book — 52%, nearly three times that floor**, which only four runs could show. **`PORTABLE` is now
two of thirteen: `refusal_rate`, `refusal_per_ask`.**

*It also tested step 27's protocol out of sample and found its number book-specific. Going n=2 →
n=4 on this 24-scene book widened spreads by a median of **3.7×**, and `refusal_per_ask` by
**13×**; step 27 measured ~2× on the 71-scene* Debt *floor. The protocol holds a fortiori — a
screen may kill, never confirm — but "half the floor" is one book's figure, not a constant.
Both rounds in [evidence/portable-measures.md](evidence/portable-measures.md).*

---

## Phase 9 — Reliability  *(instrumentation first; the fix is designed from its data)*

**31. Instrument the repair ladder.** ✅ **Done — backfill 2 September morning, code the same
evening, verified against live Ollama before committing.** Every scene record now carries
`candidates_drafted` and `repairs` separately (the sum stays as `attempts`, so the two eras remain
comparable), plus a `repair_log` of ladder events — `{phase, action, round, targets, outcome}` for
both the deterministic ladder and the post-verify response passes — and a halt now writes
`halts.json` in the run directory from the same `result` the halt decision used, closing the
log-that-lied gap. Old records load with absent-means-not-recorded defaults. Five new tests; the
live smoke's first scene committed at attempts 4 = 3 + 1 with its `fulfil` event on disk.** Full analysis in [evidence/repair-backfill.md](evidence/repair-backfill.md).

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

**32. Fix repair convergence, as an experiment.** ❌ **DROPPED permanently, 3 September** — step 31's instrumentation landed and its first table says repair need looks like a property of the *draft* rather than the scene, which makes the fix a sampler question rather than a ladder question. Five GPU-hours for an increment on a writer that already completes 71 scenes with zero halts. Not worth it, and the exploratory hypothesis stays on record with its falsifier for anyone who revisits.

*Original design follows.* Designed *after* 31's first table exists —
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

## Phase 10 — Reader  *(CUT 3 September — [evidence/no-human-rater.md](evidence/no-human-rater.md))*

**The whole phase is cut, and steps 34 and 35 fall with it rather than becoming independently
open** — both were explicitly gated on step 33 confirming the eras separate for a person. Three
instruments failed for one reason: a sentence with no context has no job, so its fitness cannot
be judged, and the largest measured defect in this prose is invisible at sentence level because
every single instance of it reads fine. The record below is kept as written, unedited, because
the branch table is exactly what can no longer be evaluated.

**Replaced by** [evidence/rater-panel.md](evidence/rater-panel.md): a cross-family model panel on
*passages*, order-counterbalanced, with the writer's own model as the self-preference control. It
can license "model families of different lineage prefer X". It cannot license "readers prefer X",
and nothing here will.

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

**36. The focused-inspector method** *(added 2 September at Tue's suggestion; pre-registered,
run, and verdict applied the same evening — [evidence/inspector-method.md](evidence/inspector-method.md)).*
A high-model subagent asked one narrow, falsifiable question with located evidence — never a
quality judge, never gating (rule VI), never in the product loop, validated on seeded ground truth
before touching anything live (rule II).

- **Continuity inspector: REJECTED on its own evidence, after re-validation.** Round 1: 9 of 9
  valid seeds caught, 2 false alarms on transient `state` facts. Round 2 with the fix applied
  (durable-fact sheets, one instruction line, and mutations validated against scene text):
  **10 of 10 detection, exact fact and quote every time — 19 of 19 across both rounds — and 2
  new false alarms**, against a ceiling of 1. Failed, and the pre-registration allowed no third
  chance, so nothing in this project consults it.
  *The failure is diagnostic rather than noise: across 40 trials **every flag pointed at something
  genuinely wrong**, including a ledger mis-extraction (the book's "dead — not literally, not
  exactly" recorded flat) and an anatomically impossible sentence (a temple scar "beneath his
  shirt collar") in a committed book. The instrument answers a broader question than it is given,
  which makes a 1-in-10 false-alarm ceiling the wrong specification for it. The successor — an
  inconsistency **finder**, triaged by a person, recall-weighted, fed the ledger as well as the
  prose — is a different instrument and needs its own pre-registration.*
- **Naive-rater replication: the dry run's caveat is funded.** A context-free rater keeps the
  era *direction* and loses the *separation* (2.16 vs 2.04, overlapping); the 0-of-7-signals
  finding held on its second independent rater; inter-rater r = 0.518 with the compression all at
  the bottom of the scale. Step 33's prediction is weakened accordingly: direction firm,
  separation uncertain, human tiebreak unchanged as the only one that counts.
- **The method's own validation caught three things before any live use:** a defective seed
  (mine), a task-definition gap (time-indexed states), and inter-agent inconsistency exactly where
  the definition was silent. That is what the pre-registration was for.

**37. The inconsistency finder** *(built, pre-registered and run 2 September —
[evidence/inconsistency-finder.md](evidence/inconsistency-finder.md); tool at
`scripts/inconsistency_finder.py`).* The successor the rejection specified: categories instead of
a verdict, every fact carrying the sentence it was extracted from, recall as the metric.

- **Recall passes — 8 of 10 with correct category, 3 of 3 on the new `FACT_MISREADS_SOURCE`
  class.** Both misses are my measurement design: the prompt asked for "the single most serious"
  finding, and in both cases the finder found a **real defect that outranked my seed**.
- **Precision was unmeasurable as pre-registered.** Nine of ten "clean" packets flagged, and
  7 of those flags verify as real defects in the book or ledger. **A negative control cannot be
  created by assuming a scene is clean** — real prose contains real defects at a rate that makes
  a randomly drawn packet usually not negative. Adoption is therefore *not* claimed; the tool is
  conditionally usable for triage lists a person reads, and nothing else.
- **The run found a bug in its own harness.** Three independent agents reported a fact sourced to
  a sentence containing no scar. They were right: `locate_source` used substring matching, and
  *di·scar·ded* contains "scar". Fixed to a word-boundary prefix match. **This project's oldest
  defect class, inside the tool built to audit everything else, on its first run.**
- **Four real defects in a committed book, none previously known** — the wandering scar (palm →
  arm → wrist → temple), the watch's three locations, thirty-years-vs-thirty-days inside one
  scene, and one file in two people's hands.
- **A claim I published about those defects was wrong, and correcting it found a bigger gap.** I
  wrote that the continuity checks are "blind by construction" to a wandering attribute. They are
  not — `conflict_candidates` keys on (subject, predicate) and *does* pair the palm and temple
  scars. The real defect is that **`judge_conflicts` truncates at `max_pairs = 25`, silently
  dropping 86% of all candidate pairs** across this book (9,560 generated, 1,302 judged; 66% of
  scenes exceed the cap; one scene produced 979). The scar pair was inside the cap and the judge
  missed it anyway, so there are two independent causes
  ([MEASUREMENTS.md](MEASUREMENTS.md)).
- **The truncation half is fixed.** `Ledger._latest_only` reduces the same book from 9,560
  candidates to 571 (median 6, max 33, one scene over the cap instead of 46), and
  `judge_conflicts` now emits a MINOR `conflict_check_truncated` when the cap still bites.
  Live-verified on `qwen3:8b`.
- **And the judge half is fixed by not using a judge.** `checks.wandering_details` groups `detail`
  facts by (subject, mark) and reports any mark placed in more than one body *region* —
  deterministic, no model call, surfaced in `redthread audit` as advisory. It finds Kai's scar in
  three regions. Narrow on purpose (regions not parts, so palm-vs-hand is silent; spans excluded;
  `detail` only, since a `state` may change), because rule V's four reverted plan checks all died
  of matching vocabulary instead of meaning.
- **Run over the whole corpus: 12 of 19 books at ≥60 scenes carry one, against 1 of 19 shorter
  ones (63% vs 5%) — but "long" and "one premise" are the same set.** Every 60+ scene book in
  `runs/` is *The Debt of Years*, and the longest book of any other premise is 24 scenes, so this
  cannot separate a length defect from a premise defect. Calling it a length defect, as this line
  first did, went past the evidence. Settling it costs one 71-scene run of another premise
  (~1.5 GPU-h) and is not yet on this plan. Same shape as the scale test's ledger
  bug — a defect that does not exist below about forty scenes — and presumably the same mechanism:
  a detail fixed at scene 15 is far outside the recency window by scene 42, so nothing but the
  ledger remembers it. Calibrating the check cost four nouns: `bruise`, `burn`, `callus` and
  `mark` came out, because three bruises in four scenes is a man being knocked about.
- **Traced to its cause and fixed at the brief, not the gate.** The slice was handing the writer
  `[s15] Kai feels the scar still burns faintly` — a scar with no location — while dropping
  `[detail] Kai has a scar along his palm` from the same scene. Old-band slots are now won by
  kind, then specificity, then recency (5.0 → 15.9 details per slice), and permanent marks get a
  reserved floor of `limit // 5` slots the way `knows` gets its own accessor (73% → 96% of scenes
  carry a fixed mark; mean 1.5 → 6.7). **Scene 40's brief now shows the palm scar beside the arm
  variants**, so the writer sees the conflict rather than inventing around it. Live-verified on
  `qwen3:8b`; nine new tests.

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
- **Extend the measure panel on the strength of a reading claim.** There is no reader and there
  will not be one ([evidence/no-human-rater.md](evidence/no-human-rater.md)), so "the panel is
  orthogonal to reading" can no longer be confirmed or refuted by a person. Build measure #12
  when a *named defect* wants measuring, never to chase perceived quality.
- **Compare across books on non-portable measures.** After step 26, `clears_noise` enforces this
  rather than a doc pleading for it.

## Shape of it

| phase | steps | GPU spent | state |
|---|---|---:|---|
| 7 — instrument, from the shelf | 26 ✅ 27 ✅ | 0 h | **closed.** 2 of 13 measures portable; a two-run *floor* may kill, never confirm |
| 8 — the last two switches | 28 ✅ 29 ⚠️ 30 ✅ | ~7 h | **closed.** 28 killed at n=2, kept at n=4, claim reduced to a three-phrase filter; 29 unrunnable on this corpus; 30 removed `somatic_share` from `PORTABLE` |
| 9 — reliability | 31 ✅ 32 ⬜ | ~0 h | **31 done and live-verified.** Every future run pays rung-level data; 32 waits for the first instrumented book |
| 10 — reader | 33 ⬜ 34 ◐ 35 ⬜ | — | **blocked on the human sheet.** 34's feasibility done: no cheap trained-judge path; step 36's naive rater weakened the separation prediction |
| 37 — inconsistency finder | built, run | 0 h | none | recall passes 8/10; precision unmeasurable (controls were not clean); found a substring bug in its own harness and four real defects in the book |
| 36 — inspectors | A **rejected**, B run | 0 h | none | 19/19 detection across two rounds, exact every time; 2 false alarms both rounds against a ceiling of 1. Rejected as designed; successor must be an inconsistency finder, separately pre-registered |

## Picking this up

**Three write-path changes landed on 2 September, so the frozen-writer era is definitively over.**
`runs/.floor-commit` no longer describes this writer:

1. **Step 31's instrumentation** — `candidates_drafted`, `repairs` and a rung-level `repair_log`
   persisted per scene, plus `halts.json`.
2. **`Ledger._latest_only`** — the conflict judge stopped silently discarding 86% of its
   candidates, and a MINOR `conflict_check_truncated` now fires when the cap still bites.
3. **The slice** — old-band slots ranked by kind → specificity → recency, and permanent marks
   given a reserved floor of `limit // 5`.

**What that costs, stated plainly:** no panel measure from a run written after 2 September may be
compared against `checks.NOISE_FLOOR`, and the four floor runs are now historical. A fresh
four-run floor is ~5 GPU-h and is the price of the next continuous-measure comparison. Binary
outcomes — like the wandering-mark test — need no floor and are unaffected.

### Next, in order

1. **DONE 3 September — the mark pre-flag.** ✅ `checks.mark_conflicts_against` decides the
   wandering-mark pair class deterministically, before the model is asked, and
   `judge_conflicts` emits it as a `checks:mark_conflict` BLOCKER. Measured across the 28 books
   of 20+ scenes in `runs/`: it fires in **all 13** the book-level check calls wandering and in
   **none of the 15** it calls clean — 28 of 28, **zero false blockers** — and on the shipped
   book it fires at **scene 40**, the exact point where `temple` entered the ledger and the
   model judge said no. It also scans the whole ledger rather than the candidate list, because
   routing it through candidates lost 3 of 13 books to a location-free row displacing a
   location-bearing one: the original defect wearing a different hat.

   **The 4-run wandering re-test is ❌ DROPPED permanently.** It was going to ask whether the
   *brief-side* fix works. That question is now moot — the defect is caught deterministically at
   the point of introduction, with perfect precision on the corpus and no model call — and five
   GPU-hours to characterise a superseded lever buys nothing.

   *The failed test that led here, for the record.*
   Both 71-scene runs wandered under the unchanged check
   ([evidence/wandering-mark-fix.md](evidence/wandering-mark-fix.md)) - the outcome the
   pre-registration named in advance as the important one. Auditing those flags then found two
   defects in the check itself, plural mark nouns and `wrist`/`forearm` split across the
   `hand`/`arm` boundary, worth 16 points of the published rate (79% to 63%). Both fixed, pinned
   by five regression tests, and corrected everywhere the figure appeared.

   **A re-test needs four runs, not two.** The corrected clean rate is 0.368 against the control
   and 0.429 across the corpus; n=2 buys p>0.13 either way and only n=4 clears 0.05. It also
   needs *fresh* runs: under the corrected check both existing runs read clean and the shipped
   book still wanders across three regions, but the correction was derived from those runs' own
   flags, so re-reading them with it is exactly what step 28 exists to forbid. ~5 GPU-hours,
   pre-registration not yet written.
2. **Step 32** — design the repair-convergence fix *from* step 31's first instrumented table, not
   before it. An exploratory hypothesis is on record with its falsifier: repair need looks like a
   property of the draft, not the scene.
3. **A new four-run floor** — kept, but only as a *precondition*, not as work. Five GPU-hours
   that buys nothing until there is a continuous-measure comparison someone actually wants. With
   steps 12, 29b, 32 and the tic fix all dropped, there is currently no such comparison on the
   board, so this is dormant rather than pending.
4. **Step 29 stage 2** — needs a plan where the 15% gate opens (`solo-a1` at 38%) *and* a floor
   for that premise. Most expensive item left, least urgent.
5. **The rater panel** — [evidence/rater-panel.md](evidence/rater-panel.md), pre-registered and
   running. Replaces the cut step 33. Costs no human time and no GPU beyond a few hundred short
   judgements, and a null is as useful as a positive: if four unrelated model families cannot
   separate the eras on passages, the speculative mechanisms above that assume the eras are
   perceptibly different retire with it.

### What is permanently dropped, and why — so it is not re-proposed

Recorded as decisions, not gaps. Each was dropped for a stated reason, and the reason is the
thing to argue with if anyone wants it back.

| dropped | reason |
|---|---|
| **PLAN.md step 12** — prediction spread | Fed step 13's plot, and the whole predictability line existed to find a *quality* correlate. No quality instrument exists or will |
| **PLAN.md step 21** — hundred sentences | Unanswerable in the form asked; three instruments failed on the unit, not the confounds |
| **Phase 10, steps 33-35** — reader | 34 and 35 were gated on 33, which is cut. Replaced by a model panel that did not clear its own bar |
| **Step 29 stage 2** — re-people | The pass is inert. Rule VIII: nothing to measure a difference in |
| **Step 32** — repair convergence | Step 31's data points at the sampler, not the ladder. Five GPU-hours for an increment on a writer that already completes 71 scenes with zero halts |
| **Step 38's fix** — tic suppression | Rule VII: the only available measure is blind to the defect, and there is no arbiter of whether the result reads better. The *measurement* stands |
| **The 4-run wandering re-test** | Asked whether the brief-side lever works. Superseded — the defect is now caught deterministically at the point of introduction |

**What that leaves:** nothing that needs GPU, and nothing that needs a person. The writer
completes 71-scene books unattended with zero halts, and the two defects worth closing were
closed on 3 September — the mark pre-flag and the homophone check, both deterministic, both with
their precision measured against the corpus rather than asserted.

### Read before designing anything

- **A two-run *condition* may not be used for anything** — step 28's false negative. A two-run
  *floor* may kill. And a **binary** outcome with a known base rate is the one exception, with the
  arithmetic shown rather than asserted (`scripts/wandering_audit.py`).
- **Run `scripts/mechanism_coverage.py` before designing an ablation** — rule VIII. Two of six
  mechanisms are inert on the corpus.
- **Run `scripts/wandering_audit.py` after any change to the slice, the extractor or the mark
  list** — the 12-of-19 figure is a claim and claims nobody re-derives rot.
- **`checks.PORTABLE` is two measures**, and `clears_noise(..., cross_book=True)` raises on
  anything else.

**The single most valuable hour on this list is still the human one**, and this plan inherits
PLAN.md's closing prediction unchanged.

### Step 38 — this model's own tics (measured; fix not yet designed)

Found 3 September ([evidence/cross-scene-tics.md](evidence/cross-scene-tics.md)). `as if` in
70-82% of scenes, `the weight of` in 65-72%, across every premise in the corpus. Neither the
per-scene `duplication_ratio` nor the externally-sourced antislop list can see any of it - the
first is per-scene by construction, the second is other models' stock phrases.

- **Measured and reproducible.** `scripts/tic_audit.py` separates tic from premise vocabulary by
  cross-premise recurrence, the `checks.PORTABLE` logic applied to phrasing. It under-reports:
  a tic carrying a character name lands premise-bound.
- **The lever is the slop list, not a gate** (rule VI). The external list is sound and simply
  aimed elsewhere; the proposal is to extend it with this model's measured tics.
- **Blocked on a measure, not on GPU.** Rule VII: a criterion is only as good as the measure it
  names, and the measure that would judge this fix is `duplication_ratio`, which is blind to the
  thing being fixed. Suppressing `the weight of` could easily make the prose worse - the phrase
  is not wrong, only overused. **Finding the measure is the work; pre-registration comes after.**
- **The homophone check is DONE, 3 September.** `checks.check_homophones`, MAJOR, registered
  in the scene panel with a `REMEDIES` line worded to change the one word and nothing else.
  Fires exactly 8 times across 1,773 scenes - the 8 audited errors, no others - and is silent on
  every correct usage tested, `he had taught her to read` and `the reins of the horse` included.
  One entry is validated; thirteen have never fired and say so in their own violation text,
  because the fifteenth pattern audited returned two matches that were **both false positives**
  (`born of necessity` is correct idiom) and is absent for that reason.
- **The tic fix itself is ❌ DROPPED permanently, 3 September.** The *measurement* stands and is
  the finding. The fix does not happen, for the reason rule VII exists: a criterion is only as
  good as the measure it names, and the only measure that could judge suppressing `the weight of`
  is `duplication_ratio`, which is per-scene and structurally blind to a cross-scene tic. There
  is also no reader instrument to say whether the result reads better
  ([evidence/no-human-rater.md](evidence/no-human-rater.md)), and the phrase is not wrong, only
  overused - so suppressing it could as easily make the prose worse. **A fix with no measure and
  no arbiter is not a step, it is a hope.**
