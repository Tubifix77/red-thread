# Where this stands

*Measured 30 August 2026. All figures from `runs/` and `docs/evidence`; nothing here is
an estimate — but read "What a day of measuring changed" below before trusting any single one.*

A percentage would be a lie, because three separate things are being built and they are at very
different places. This document is the honest read on each.

Illustrated version: <https://claude.ai/code/artifact/9ef610d1-1ca6-4a0f-a937-1529ad68978c>

What to do next, in order, with kill criteria: **[PLAN.md](PLAN.md)**.

---

## Three questions, not ten steps

| | Question | State |
|---|---|---|
| 1 | Can it get to the end of a book without help? | **yes, at novel length** |
| 2 | Is the prose free of the obvious machine tells? | **per scene, yes** |
| 3 | Is the finished book worth reading? | **one of five axes started** |

**1 — Yes, at novel length.** **Eight distinct books** across **15 completed runs** — 467 scenes,
426,614 words, zero API calls. The gap between those two numbers is deliberate: five runs are one
premise rewritten to test code changes, which is how anything here gets attributed to a change
rather than to luck.

**Four consecutive 71-scene runs have gone start to finish with no halt and no intervention**, the
last three from an identical plan.

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

**3 — One of five axes started.** Dialogue stopped being unmeasurable and moved — .077 to .223,
scenes where the plan put people in a room and the prose left them silent from 23 of 71 to zero.
The other four are untouched, and the instrument built for one of them (forecastability) was
calibrated and found to report noise.

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
| **8** | distinct books finished |
| **426,614** | words drafted locally |
| **467** | scenes committed |
| **0** | API calls |
| **578** | tests passing |

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

**There are no error bars.** Every comparison here is one run against one run. Across three runs
of one plan, dialogue share and recap grammar move about 6% of their own value — small enough to
trust — while the worst-refrain count moves 75% and per-scene duplication 153%. Those three runs
*are* the conditions being compared, so effect and noise cannot be separated from them. A true
replicate is running for the first time.

## The short answer

The orchestrator is close to shippable. The writer is not. What remains is not a list of bugs — it
is one unanswered question about whether a plan can be made dramatic enough that a small local
model has something worth writing about. Everything measured says the plumbing works. Nothing
measured says the book is good, because nothing measures that.
