# Where this stands

*Measured 1 September 2026, after phase 1 and step 25. All figures from `runs/` and
`docs/evidence`; nothing here is an estimate — but read "What a day of measuring changed" below
before trusting any single one, and read the one-line warning under question 2 before carrying
any of them to another book.*

A percentage would be a lie, because three separate things are being built and they are at very
different places. This document is the honest read on each.

Illustrated version, **a 30 August snapshot and not current**:
<https://claude.ai/code/artifact/9ef610d1-1ca6-4a0f-a937-1529ad68978c>. The plan, illustrated and
current to 1 September: <https://claude.ai/code/artifact/79ab4f28-db0c-4e86-80ce-c74d837b4c53>

What to do next, in order, with kill criteria: **[PLAN2.md](PLAN2.md)** (PLAN.md is complete except step 21, which PLAN2 inherits as its gate).

---

## Three questions, not ten steps

| | Question | State |
|---|---|---|
| 1 | Can it get to the end of a book without help? | **usually — 11 of 14 unattended; halts are resumable, and two of three were resumed to the end** |
| 2 | Is the prose free of the obvious machine tells? | **per scene, yes — but the floor those figures rest on is one novel's, and a permanent physical detail wanders in 4 of 5 long books** |
| 3 | Is the finished book worth reading? | **one of five axes started, and no measure yet matches a reading** |

**1 — Yes, at novel length.** **Eleven distinct premises** across **39 runs with committed
scenes** — 1,631 scenes, 1,424,274 words, zero API calls. The gap between those numbers is
deliberate: twenty-two of the runs are *The Debt of Years* rewritten to test code changes, which
is how anything here gets attributed to a change rather than to luck.

**And there is now a rate rather than a run of luck.** Fourteen 71-scene runs written under one
code revision, across phases 1 and 8 — one plan, one switch at a time, nothing else varying:

    control, nothing ablated      4 of 4 reached 71
    refrain feedback off          2 of 2
    gesture feedback off          1 of 4   — halted at 66, 48 and 33
    model refrains off            4 of 4

**Eleven of fourteen reached scene 71 unattended.** That is a real rate rather than "four consecutive
runs finished", which was true and selected from the runs that finished.

**The more useful fact is that all three halts were resumable, and two were resumed to 71.** A
halt is not a crash: `write_all` stops rather than write later scenes against a ledger missing a
scene's facts, so it leaves a short book and not a broken one, and re-running picks up at the
scene that failed. So the cost of a halt is a resume, not a book. What it is not yet is
*unattended* — something has to notice and press the button.

*Only `current-nogesture4` is still short, at 33 of 71, halted on a genuine
`continuity_contradiction` after four repair attempts.*

The causes are worth naming, because none is the same:

    scene 66   somatic_emotion + thematic_gloss, five repair attempts, no convergence
    scene 48   continuity_contradiction — "a watch with a cracked face" at scene 10
               against "a watch with age spots" at scene 48
    scene 33   continuity_contradiction, four attempts

**Two of the three are the system working.** A writer with no memory contradicted itself forty
scenes later, the ledger caught it, and the gate refused. The first is a repair that could not fix
a true positive, which is the open problem: **the halt rate is mostly a repair-convergence
problem, not a detection one.**

*Two of these three halts report as `length` in `replicate`'s own log, which is not what either
scene record says: `SceneResult.violations` and `Scene.violations` are separate lists and the halt
report read the wrong one. A log that disagrees with the file on disk is worse than no log — this
one nearly bought a false story about the ablation causing length failures.*

*An earlier set, before `check_thematic_gloss` stopped reading dialogue as narration, lost two of
four. That one check was firing on lines like* "This isn't just about punishment" *— a character
speaking — and its remedy is to delete the offending clause, which cannot be done to a line of
dialogue. Fixing it took the rate from 2-of-4 to 7-of-10.*

The scale test this document listed as its largest gap is done: *The Debt of Years* at
**71 scenes and 61,733 words**, twice the longest previous run, all four threads terminal. It halted four times. Three of those were one bug — the ledger calling
a character who puts something down and picks something else up a contradiction — which only
exists at length, because across every ledger in the project there are just three
subject-and-predicate keys carrying more than one object. The fourth was not a defect at all:
a scene rejected on sampling that committed on a second whole attempt with nothing changed.
Full record in [evidence/sixty-thousand-word-run.md](evidence/sixty-thousand-word-run.md).

The one that mattered most is *The Keeper's Fourth Book*, planned and written from a
premise the system had never seen, to test the standing claim that every new premise costs one
to three code fixes. **It cost one, and the plan gate caught it before a word was generated** —
the planner had banned "truth", "right", "memory" and "silence", which are words a novel is made
of. After that: nine scenes, 8,359 words, 8m35s, all committed, no held-back scenes, no
redrafts, no code fixes during writing, and the only two repairs were deterministic ones needing
no model call. Full record in
[evidence/keepers-fourth-book-run.md](evidence/keepers-fourth-book-run.md).

So it has now finished a brand-new book unassisted, once, at novella length.

**2 — Per scene, yes. Per manuscript, no.** Every countable per-scene tell now sits at or below
the reference band: duplication .002, recap .047, and none of the three prose tells in any of the
373 scenes written since the sampler fix. What does not hold is the book: duplication across a
whole manuscript is .066 against .002 within any scene of it, and that gap widens with length.

**Read this before carrying any figure here to another book.** Step 25 ran the whole panel on a
premise never written before, with *nothing ablated*, and **three of eleven measures landed outside
the four-run floor** — `gesture_rate` 2.81 against 1.88, `recap_grammar` .064 against .035,
`dialogue_share` .169 against .202. So every number in `checks.NOISE_FLOOR` is the noise of **one
novel at 71 scenes**, not the noise of this system. It does not mean the measures are wrong — a
book with more physical description has a higher gesture rate, and that is the measure working —
but it means a comparison has to live inside one plan. Which is what the replicate harness was
built for, and what both phase 1 verdicts did.
([record](evidence/fresh-premise-panel.md))

**3 — One of five axes started, and the panel now has a reason to distrust itself here.**
Dialogue stopped being unmeasurable and moved — .077 to .223, scenes where the plan put people in
a room and the prose left them silent from 23 of 71 to zero. The other four are untouched, the
instrument built for one of them (forecastability) was calibrated and found to report noise, and a
second (`want`/`obstacle`/`cost`) was stopped by its own kill criterion at r = 0.130 against a 0.4
bar.

**The open question is whether any of it corresponds to what a reader notices, and it is still
open.** [The hundred-sentence sheet](evidence/sentences/sentences.md) is built and blank and needs
a person for twenty minutes; it is the last item in the plan. A machine has filled in a separate
copy as a dry run of the analysis
([record](evidence/sentences/machine-rating.md)), and it says two things worth treating as
predictions rather than results: the two eras separate under a blind rating (2.12 against 1.67,
surviving the dialogue control), and **zero of seven per-sentence signals correlate with the
rating**. The one that appeared to — past perfect, r = −0.282 — turned out to be a perfect era
marker, because that measure feeds candidate selection. An LLM rating LLM prose may be measuring
fluency-under-a-language-model rather than whether a person turns the page, so none of that is
evidence about readers.

---

## The defect that only appears at length, again

*Found 2 September while validating a session-side inspector; full trail in
[MEASUREMENTS.md](MEASUREMENTS.md) and [evidence/inconsistency-finder.md](evidence/inconsistency-finder.md).*

**A permanent physical mark drifts across body regions in 15 of 19 runs of 60+ scenes, against 1
of 20 shorter ones — though every 60+ scene book in the corpus is the same premise, so length and
premise cannot be separated here.** In the shipped *Debt of Years*, Kai's scar is on his palm (11–16, 46–47),
his arm (31–32), his wrist (53) and his temple (40, 42, 56, 57, 66, 68, 70). The extraction
prompt's own example of a fixed detail is *"the scar is on the left hand"*.

Traced to a single dropped fact rather than guessed at: scene 15 established both
`[detail] Kai has a scar along his palm` and `[state] Kai feels the scar still burns faintly`, and
the stratified slice kept the state and dropped the detail. **The writer was told there was a scar
and not where it was.**

Three changes followed, all measured, all live-verified on `qwen3:8b`:

| | before | after |
|---|---:|---:|
| conflict candidates judged (of 9,560) | 1,302 — **86% silently dropped** | 571 generated, **0 dropped** |
| details per brief slice | 5.0 | **15.9** |
| scenes whose slice carries a fixed mark | 73% | **96%** |

Plus `checks.wandering_details`, a deterministic report surfaced in `redthread audit`, and a
MINOR `conflict_check_truncated` so the cap can never bite silently again.

**Whether any of it stops the drift is under test at n=2 right now**, pre-registered — the outcome
is binary per book with a 0.211 clean rate, so two clean runs is p = 0.044
([record](evidence/wandering-mark-fix.md)).

---

## What the checks can see

Four cohorts:

- **before** — n = 50 scenes across *The Debt of Years*, *The Register of Kvitmyr* and the first
  unattended run, drafted before the prose checks landed. Mean scene length 1,126 words.
- **checks** — n = 5 scenes written under the full check set but with the sampler untouched
  (`runs/now`, scenes 4–8).
- **+ sampler** — n = 3 scenes with the same checks and the writer's repetition penalty set
  from measurement (`runs/recap`, scenes 9–11). The two prose-tell rows below carry over from
  the `checks` cohort, which is where they were closed; the sampler did not touch them.
- **reference** — n = 3 single cold scenes from gemma3:12b, phi4:14b and qwen3:8b with no
  orchestration at all (`docs/evidence`). Mean length 665 words. A reference, not a ceiling.

| Signal | before | checks | + sampler | reference |
|---|---:|---:|---:|---:|
| Narrator glossing the theme (share of scenes) | 58% | **0%** | 0% | 0% |
| Stacked possessive absolutes (share of scenes) | 52% | **0%** | 0% | 0% |
| Rhetorical triples (share of scenes) | 42% | **0%** | 0% | 0% |
| Repeated phrasing (`duplication_ratio`) | .340 | .118 | **.004** | .009 |
| Recap grammar (`summary_distance`) | .420 | .376 | **.078** | .105 |
| Scenes carrying a block of 4+ past-perfect sentences | 70% | 60% | **0%** | 0% |

The three prose tells were closed by checks and repairs. The bottom three were not — they barely
moved under the whole check set, and they closed in one pass when a sampler default was
corrected. Both halves of that are worth keeping in view: the checks are what made the failure
*visible and countable*, and a setting underneath them is what actually fixed it.

### Correction, 29 August

The first version of this page reported recap grammar at .28 → .25. That was measured with a
regex that missed two whole classes of past perfect: an adverb between the auxiliary and the
participle (*had never seen*, *had already gone*), and irregular participles that were simply
absent from the list (*had hung*, *had held*, *had stood* — the last of which one live scene
repeated nine times). Corrected, the corpus *as it then stood* sits at a median of **.382**, not .245,
and the worst scene narrates 97.9% of its sentences at distance.

So the axis did not "barely move". It **has not meaningfully moved at all**, and it is the
dominant remaining defect in the prose. The numbers above are the corrected ones.

### What was done about it

The register really is unrepairable — switching one sentence to simple past leaves the other
forty alone — but that was the whole of the analysis, and it hid the half that is reachable.
Measuring the *distribution* rather than the density splits the problem: past perfect arrives in
**blocks**. 68 of 107 committed scenes carry a run of four or more consecutive past-perfect
sentences; one carries forty-six; the three reference drafts top out at two, and none reaches
three. A run has edges, so a passage repair can replace it.

`check_recap_block` (MAJOR, one violation per block) now finds them, and two repairs reach them:

- **`unrecap`** rewrites the block as scene, verified by the check that flagged it. Confirmed
  against Ollama on a live scene: two blocks down to one, density .415 → .360.
- **`cutrecap`** deletes the block outright, no model call, when the rewrite fails — which it
  does, because told in four numbered rules not to use past perfect, qwen3:8b returns past
  perfect. A block of recap is by definition not the scene, so what is lost is length, and
  length has a repair of its own. It refuses to cut a scene below 75% of its words: past that
  point the draft is the problem and the redraft path is the right answer.

Finding this route surfaced three pipeline bugs that had nothing to do with recap:

1. **Progress was measured by kind, not count.** A repair counted as having done its job only if
   its target kind vanished entirely. `unrecap` correctly cleared one of two blocks and was
   discarded as "no improvement", twice, then sidelined. Now the count has to fall, not the kind
   disappear.
2. **A capped check cannot be used to measure progress.** `check_recap_block` originally reported
   at most three blocks. A live scene held seven, so deleting one still reported three, and every
   correct repair looked like a no-op. It is now uncapped — the only per-occurrence check here
   that is.
3. **Passage-scoped kinds could still reach sentence surgery.** Once `unrecap` was sidelined,
   `recap_block` fell through the ladder to `surgical`, which rewrote one sentence of a
   six-sentence run three times over. Seams had been guarded against exactly this by an early
   return since a run in July; `PASSAGE_SCOPED` is the general form of that guard.

### One hypothesis, refuted

Scene 9 of a live run collapsed completely on qwen3:8b — "she had not asked" 77 times in 1,490
words, a 46-sentence run of past perfect, every draft unusable. Its four beats are *watches and
notes*, *admits*, *reflects on*, and *is revealed to be*: nobody does anything. The obvious
reading is that a beat with no event gives the model nothing to dramatise, so it recaps.

Measured across all 108 scenes that have both a spec and prose, the correlation between the share
of a scene's beats using a cognition or state verb and its recap density is **r = 0.141** — the
group means move in the right direction (.378 → .410 → .466) but the top group is n = 3 and the
relationship is negligible. Against duplication it is r = 0.006.

Not enough to build a plan check on, so nothing was built.

### What actually explained it

The same spec, the same brief, the same orchestrator, one draft, `gemma3:12b` instead of
`qwen3:8b`:

| scene 9, one draft | qwen3:8b | gemma3:12b |
|---|---:|---:|
| repeated phrasing | .29 | **.015** |
| recap grammar | .98 | **.046** |
| longest past-perfect run | 46 sentences | **1 sentence** |
| blocks of recap | 7 | **0** |
| outcome | held back after 4 drafts and 6 repairs | committed, 2 minors |

Reference quality, on the spec that destroyed the 8B, from a model that fits the same 10GB card.
Scene 10 went the same way: one draft, zero majors, zero repairs, duplication .002. The plan was
not inert and the brief was not at fault — the writer model was at its ceiling.

Scene 11 then held back on `gemma3:12b` with 35 first-person uses against a third-limited
contract, which is this model's signature failure and was already in `docs/MODELS.md` from the
scene-1 bench. So both models fail; the difference is that recap is a MAJOR a scene can commit
carrying, and a POV break is a BLOCKER nothing gets past. A loud failure the gate catches is
worth more than a quiet one it half-catches. The full comparison, including the eight-fold speed
cost, is in [MODELS.md](MODELS.md).

That looked like it reframed what "close to shippable" means. It did not, and the correction
came within the hour.

### The sampler was the ceiling, not the model

**Ollama's `repeat_penalty` defaults to 1.0, which is disabled**, and `qwen3:8b`'s own Modelfile
pins it there with `PARAMETER repeat_penalty 1`. The companion `repeat_last_n` defaults to 64
tokens — about forty-five words. So every scene this project has ever generated was sampled with
no repetition penalty and a window far too short to see a phrase recurring every twenty words.

Nothing in the brief and nothing in 32 checks could reach that, because the cause sat underneath
both of them.

Swept on the two scenes that failed worst, two seeds each: penalty 1.20 is the lowest value that
cleared every draft, and 1.30 was rejected on evidence — character names fell from ~17 per scene
to 5, which is a penalty suppressing the legitimate repetition a scene is made of. Scenes 9–11
then ran on `qwen3:8b` with `repeat_penalty 1.2`, `repeat_last_n 512`, `num_ctx 8192` on the
writer role only:

| | duplication | recap | longest run | blocks |
|---|---:|---:|---:|---:|
| qwen3:8b, before | .118 | .376 | 4.4 | 2.0 |
| **qwen3:8b, after** | **.004** | **.078** | **1.3** | **0.0** |
| reference drafts | .009 | .105 | ≤2 | 0 |
| gemma3:12b, 8× slower | .002–.015 | .046–.058 | 1 | 0 |

All three committed. Scene 9 — held back on three separate attempts, once after four drafts and
six repairs — committed in 1m37s with one deterministic repair, and every thread reached its
terminal state. The 8B is now **below the reference band on both axes**, and it committed the
scene `gemma3:12b` failed.

So the model swap is off, and the reason matters more than the result: a small model under
strict orchestration and a large model under light orchestration are different products, and
only the first is worth building here. Reaching for a bigger model is the move that makes the
checks redundant. The `gemma3:12b` comparison still earned its place — it is what established
how much of the defect was model-attributable, and the answer turned out to be almost none of
it, once the sampler was right.

One thing to watch: type-token ratio at penalty 1.20 is .572 against gemma's .474–.478 — above
the healthy band, well short of the .810 damage point, and unmeasured as to whether it reads as
rich or as restless. Full sweep and caveats in [MODELS.md](MODELS.md).

## What nothing can see

These are not failing checks. There are no checks. Each is decided by whichever local model
happened to draft the scene, with no gate, no repair, and no record of whether it went well.

- Does a character want something, and act on wanting it?
- Does the middle earn the ending — causally, not just sequentially?
- Is a scene interesting? Would a reader turn the page?
- Is any sentence worth rereading?
- Does the book have a subject beyond restating its premise?

### The first real purchase on this half — 30 August

Reading the middle of the 71-scene book found scene 38: one character alone in a ruin, touching
statues and remembering. Every check passed it, `summary_distance` included, because the
flashback it becomes is narrated in simple past.

Measuring outward from that scene found the emptying-out is a **shape**. Dialogue runs at 21% of
words across the opening eighteen scenes, then 15%, 10%, 9% — and 20 of the 71 scenes the plan
had populated with two or three characters came back with no dialogue at all, clustered in the
second half, including all four three-character scenes of the climax.

The cause is upstream of the prose. Across those 70 two-character scenes:

| beats naming something said | scenes | mean dialogue | came back silent |
|---|---:|---:|---:|
| none | 33 | .029 | **20 of 33** |
| one | 27 | .101 | 6 of 27 |
| two or more | 10 | .203 | **0 of 10** |

r = **+0.672**, against the r = 0.141 that refuted the earlier "inert beats cause recap"
hypothesis. Not one scene whose spec named two spoken acts came back silent. The model writes
what it is asked for.

Selection cannot reach it, and that was measured rather than assumed: three fresh candidates for
two of the silent scenes came back at .003/.006/.008 and .001/.009/.001. There is nothing to
choose between.

So the fix is one line in `SCENES_PROMPT`. Replanning the same premise moved the beats — 7 of 9
peopled scenes name a spoken act, up from 5 — and rewriting the book took silent-but-peopled
scenes from **3 of 9 to 1 of 9**. Mean dialogue did not move (.103 to .104): it lifted the floor,
not the ceiling. Nine scenes is a weak test and the run is confounded by the gesture checks
landing at the same time; the 70-scene correlation is the evidence, not this.

A check for it was built and removed — it flagged three scenes of the hand-authored reference
plan, whose beats describe interaction without any verb from a list. The correlation was measured
on planner-generated beats and does not transfer to a human's. Third check reverted in this
project for firing on that plan, and the invariant is worth more than the check.

> Everything measurable about the prose is close to done. Everything that makes prose worth
> reading has no measurement at all.

That asymmetry *is* the answer to "how far". These rows are empty **by design**: the rule that
keeps the orchestrator honest — never gate on something code cannot check — also forbids gating
on quality, and it is right to. A small model's opinion of a story does not get to stop the book.

So the way through is probably not a checker. It is the **plan**. If a scene spec carries real
want, real obstacle and real cost, the drafting model has something to dramatise. Right now the
planner emits beats that are structurally valid and dramatically inert, and no test can tell the
difference.

---

## Machinery

| Part | State | Note |
|---|---|---|
| Plan & thread state machines | built | Pre / Post / Forbid per scene, audited before a word is written |
| Commit gate & ledger | built | nothing enters memory until the scene passes |
| Scene checks | built | 32 checks; thresholds calibrated on prose that had the defect, which is now a different corpus from the one the project writes |
| Repair ladder | built | 12 rungs, narrowest first; a test asserts every blocking kind has a repair that can reach it |
| Resume after failure | built | eight books finished; a held-back scene gets one whole second attempt before the run stops |
| Ledger slice reaches back | built | stratified so an ending can see its own beginning; effect on the prose is a wash ([A/B](evidence/ledger-slice-ab.md)) |
| Recap-grammar repair | built | `unrecap` rewrites a block, `cutrecap` deletes it; now never fires, because the sampler fix removed the cause |
| Cross-scene feedback | built | the book's refrains and repeated gestures, and the model's own cross-book constructions, go into the next brief |
| Planner self-repair | built | unwritable bans, catchphrases, topic-steering and story-shaped samples fixed in code; solo-heavy plans re-asked |
| Candidate selection | built | ranks on violations, duplication, recap, gestures, dialogue, then length *projected after implied deletions* |
| Redraft on exhaustion | partial | fires, but a fresh draft is not reliably better than the one it replaces |
| Manuscript-wide repetition | partial | suppresses the refrains it names; new ones form that no threshold predicts |
| Solo-scene drift | partial | prompt, running tally and a re-ask pass; the total stayed bimodal across six plans and the re-ask is untested live |
| Four checks that cannot fire | **known** | subplot independence, midpoint stall, uniform scene length and somatic each test a property the scheduler or the brief already guarantees; they read as coverage and provide none |
| Error bars on any of this | **missing** | no two runs of one plan with no change between them, so effect and noise are not separable ([detail](MEASUREMENTS.md)) |
| Dramatic planning | **missing** | want, obstacle and cost are not modelled; the dialogue instruction is the one lever found |
| Any judgement of quality | **missing** | by design, and the design is now the constraint |

---

## On the board

| | |
|---:|---|
| **11** | distinct premises written |
| **39** | runs with committed scenes |
| **1,424,274** | words drafted locally |
| **1,631** | scenes committed |
| **0** | API calls |
| **891** | tests passing |

The longest is now 61,733 words, and running it found exactly what was predicted: defects that
do not exist below about forty scenes. What it also found is the one measure that gets *worse*
with length — duplication across the manuscript is .041 against .001 within any scene of it, so
a book of individually clean scenes is repetitive. Feeding the book's own refrains forward
suppresses the ones it names (seven of ten never appeared again) and does not reduce the total,
because new ones form that no threshold could have predicted. That is open.

The other half of the prediction is untouched. A middle that sags for eight scenes is now
possible in a way it was not at nine scenes, and nothing here measures whether this one does.

---

## What a day of measuring changed about how to read this

Five findings were nearly shipped that turned out to be properties of the measuring apparatus,
and two more were published and retracted the same evening. The corrective, recorded in
[MEASUREMENTS.md](MEASUREMENTS.md), is a control: score a measure against something it has no
business matching and see whether it notices.

Two consequences for every number on this page.

**The corpus is two populations.** Ten books predate the prose work of 29–30 August and seven
follow it, and the gap is not incremental — duplication .279 against .002, recap .380 against
.047, scenes with a run of four past-perfect sentences 61% against 0%. Thresholds calibrated on
"the committed corpus" were calibrated on the first group, which is correct for catching a defect
and wrong as a description of what this project now writes.

**There were no error bars. Now there are, and they are enforced.** Every comparison here used
to be one run against one run. Across three runs of one plan, dialogue share and recap grammar
move about 6% of their own value — small enough to trust — while the worst-refrain count moves
75% and per-scene duplication 153%. Those three runs *are* the conditions being compared, so
effect and noise cannot be separated from them.

A true replicate has since been run and its floor lives in `checks.NOISE_FLOOR`, keyed identically
to the measure panel and asserted in both directions, so a number cannot be reported here without
one. `checks.clears_noise` is the gate a difference has to pass through, and it **raises** on a
measure nobody has measured a floor for — because *"I have not measured this"* and *"this is not
different"* are different sentences, and confusing them is what three retracted claims were made
of. **The four-run floor is measured and in `checks.NOISE_FLOOR`** — and step 25 then established
that it describes one novel at 71 scenes rather than this system, which is a limit on every
comparison above rather than a reason to distrust the mechanism.

**And every mechanism can now be switched off.** Four shipped in two days with no way to ablate
them, which made each unfalsifiable: the only available comparison was against a run from before
the code existed, with other changes in it. `--no-refrain-feedback`, `--no-gesture-feedback`,
`--no-model-refrains`, `--no-repeople`.

**Two of the four have now been asked and both were kept.** The refrain feedback cleared the
statistic its kill criterion named; the gesture feedback *failed* its criterion and was kept on a
second statistic written down before the confirming runs existed, at p = 0.010 — which is now
**rule VII**: an accumulating mechanism needs a measure that accumulates, and a per-scene mean
cannot see one however carefully its floor is measured
([record](evidence/phase1-ablations.md)).

**Of the other two, one is inert on everything measured.** An off switch made all four look
equally testable; they are not. The re-people pass is *gated* — below a 15% solo-scene share it
returns without doing anything — and the plan every floor run, every ablation and both step 25
panels were written from sits at **10 solo of 71 = 14.08%**. One scene under. So ablating it here
would compare a condition against itself and report "no difference" with error bars attached.
Auditing all six mechanisms the same way finds `drop_unavoidable_bans` in the same state, while
the model-refrain list is unconditional and the two feedback mechanisms fire in 62–96% of scenes
([record](evidence/mechanism-coverage.md), and `scripts/mechanism_coverage.py` to re-run it).

*The generalisation is rule IV aimed one level up, at mechanisms rather than checks: **a gated
mechanism has two failure modes, not one — it can do nothing when it runs, and it can never run.**
The second is far cheaper to test and had never been tested. Before designing an ablation, ask
what fraction of the target corpus the mechanism acts on.*

## What changed on 31 August

The instruments, and two answers.

**Phase 4 asked whether the plan is a lever for a second quality axis, and the answer is no.**
Two prose measures of refusal pass the bar the refuted POV-agency proxy failed: they vary 94%
and 221% between books against floors of 22% and 37%, so they separate books rather than
samplings. But an outline naming a refusal predicts them at only r = +0.130 against a 0.4 bar,
while the one lever that worked scores +0.446 on the same corpus with the same crude method. The
controls are clean, so this is a result and not a broken instrument. `want`, `obstacle` and
`cost` were **not** added to the scene spec.

Both measures were **56% contaminated** when first published, and were audited hours later by
counting what they matched rather than trusting the intent behind them. Every figure first
reported for them was wrong, a headline claim was withdrawn, and the correlation halved — which
widened the margin on the conclusion rather than narrowing it.
[evidence/want-obstacle-cost.md](evidence/want-obstacle-cost.md).

**The rule this project has been keeping is now written down and enforced by a test.** The gate
may refuse only on evidence code can locate; the plan may be shaped by anything, including a
model's reading. A bad plan costs one re-ask, a bad gate costs a book that never finishes.
`tests/test_rule.py` walks the source for every `Severity.BLOCKER` and refuses any whose source
has not recorded what a person could check by hand.

One thing found by accident is worth more than either. **`probe_forecast`'s calibration could not
be re-analysed** — it records a violation only above threshold, none ever cleared it, so the 35
predictions were never written down and the whole experiment had to be paid for twice. An
experiment whose only output is a pass/fail verdict cannot be re-analysed, and this project's
most expensive negative result was stored that way.

## The short answer

The orchestrator is close to shippable. The writer is not. What remains is not a list of bugs — it
is one unanswered question about whether a plan can be made dramatic enough that a small local
model has something worth writing about. Everything measured says the plumbing works. Nothing
measured says the book is good, because nothing measures that.

The one thing that could is a hundred sentences read blind, and the sheet is built and waiting:
[evidence/sentences/sentences.md](evidence/sentences/sentences.md). It needs twenty minutes of a
person, and it is the only item on the whole plan that the machine which wrote the sentences
cannot do for itself.
