# The remaining seven, and the order they have to be done in

*31 August 2026. Illustrated version:
<https://claude.ai/code/artifact/79ab4f28-db0c-4e86-80ce-c74d837b4c53>*

Four of the seven open items need an instrument that does not exist. Two are built and unproven.
One is a design decision. **Nothing here can be evaluated at all until phase 0 is done**, because
four mechanisms are currently shipped with no way to turn them off and the noise floor rests on a
single replicate pair.

**Progress.** Each step below is marked ✅ done, ⏳ running, or left unmarked. A step is only
done when its code is committed, its tests pass, and — where it makes a claim — the claim has
been through `checks.clears_noise`.

| phase | done | state |
|---|---|---|
| 0 — trustworthy instruments | 3 of 4 | step 2 needs GPU hours; 1, 3, 4 shipped |
| 1 — confirm what exists | 1 of 4 | **step 7 found the pass 90% broken**; 5, 6, 8 queued |
| 2 — tension on embeddings | 3 of 5 | **step 11 fired its kill criterion**; 12 needs its replicate |
| 3 — dependency graph | 2 of 3 | step 16 needs a plan carrying the new field |
| 4 — want, obstacle, cost | 3 of 3 | **stopped at step 18 by its own kill criterion** (r = 0.130 vs a 0.4 bar) |
| 5 — the sentence | 2 of 3 | **step 21 needs Tue for twenty minutes** — the sheet is built |
| 6 — write the rule down | 2 of 3 | step 25 is the final panel; needs phase 1 |

---

## Six rules this plan obeys

Each was learned by breaking it. Most of the steps below exist because of one of them.

| | |
|---|---|
| **I** | **Two runs of one plan, or no claim.** A single-run comparison can motivate a change and cannot confirm one. Three claims were retracted for want of this. |
| **II** | **Score every measure against something it should not match.** Five findings were nearly shipped that were properties of the apparatus. The control is cheap and goes first, not last. |
| **III** | **Never quote a maximum.** Worst-refrain and worst-gesture swing 44% between identical runs; dialogue share and word count hold to 4%. |
| **IV** | **A check over a scheduler-guaranteed field only confirms the scheduler.** Four checks are quiet for this reason and read as coverage. |
| **V** | **Test every new plan check against the hand-authored reference plan first.** Four have been reverted for firing on it, each matching vocabulary rather than the property. |
| **VI** | **Quality is addressed at the plan, never at the gate.** Gating on a model's reading of a story is the rule this project exists to keep; the plan is the lever that rule leaves open. |

---

## Phase 0 — make the instruments trustworthy  *(~3 h GPU)*

**1. Build a replicate harness.** ✅ `redthread replicate <run> --runs N` writes N books from one
plan into sibling directories and prints every measure as mean and range. Nothing else is worth
starting first.

*Shipped as `redthread/replicate.py` plus two commands. `replicate` copies story and plan into
siblings and writes them; it rewinds thread state on the way, because a finished run's story.json
holds every thread at its terminal state and a verbatim copy would open on a book that believes
it has already happened — same plan, different briefs, which is the one thing a replicate exists
to rule out. It resumes rather than restarts, since a set is several GPU-hours.*

*`redthread measures <runs…> --against <runs…>` is the half that gets used most: it reports the
panel for a group as mean and range, and puts every between-group difference through
`clears_noise`. Ablation flags are on `replicate` too, because with one switch flipped a
replicate set and an experiment are the same object.*

**2. Take the noise floor from n=2 to n=4.** ⏳ Two runs give a range, not a distribution, and a
range from two samples systematically understates the spread.

*Running: four fresh replicates of the 71-scene* Debt of Years *plan at current HEAD. The
existing pair (`runs/current`, `runs/replicate`) cannot simply be extended — `ledgerfix` and
`tally6` share its plan and story hashes exactly, but had different code, so they are three
conditions and not four replicates.*

**3. Make the floor impossible to ignore.** ✅ `checks.clears_noise(measure, a, b)` returns false
when a difference sits inside the published floor. The point is not the arithmetic — it is that
stating a difference should require passing through a function that knows what a difference is
worth.

*Shipped with `checks.manuscript_measures`, one function returning the whole panel, and
`NOISE_FLOOR` keyed identically — a test asserts the two sets match in both directions, so a
measure cannot be reported without an error bar or keep one after it is deleted.*

*Two things fell out of building it. `clears_noise` **raises** on a measure with no measured
floor rather than returning a verdict: "I have not measured this" and "this is not different"
are different sentences, and confusing them is what three retracted claims were made of. And the
first draft of the table failed its own self-test — four measures of the very pair it was
derived from were reported as clearing it, because the published figures had been rounded down
for the write-up. The floor now holds the observed values, and a test asserts that a difference
exactly the size of a measure's own floor is never a result. `repetition_concentration` had been
given a floor of .20 by guesswork; the pair says .28.*

*Two more corrections followed from running the tool rather than reading it, and both were the
same species of error the step exists to prevent.*

*A **floor of 0.00 because both replicates were zero is not a floor of 0.00.** `recap_block_share`
reads 0.00 twice because zero of 373 current-era scenes carry a run of four consecutive
past-perfect sentences — so a later condition reading 0.05 would have been reported as clearing a
floor nobody measured. `DEGENERATE_FLOOR` names those, and the report now says "differs, but NO
FLOOR WAS MEASURED" rather than "clears the 0% floor", which reads as a strong result and is the
weakest one available. A test asserts every zero floor is declared, which is the direction that
matters.*

*And **two books of different lengths do not compare on a manuscript-wide measure.** Running
`measures runs/current --against runs/keeper` put 71 scenes against 9 and reported
`duplication_manuscript` as clearing its floor by 126% — true, and entirely the length.
`LENGTH_SENSITIVE` names the five, the comparison warns before the table rather than after it,
and drops them from the verdict. That comparison goes from ten survivors to six.*

**4. Add ablation switches for everything already built.** ✅ `--no-refrain-feedback`,
`--no-gesture-feedback`, `--no-repeople`, `--no-model-refrains`. This converts "I built it" into
"it can be evaluated", and should have existed before any of them were built.

*The three prose-side switches are `Config` fields read in `write_scene`; `repeople` is a
`make_plan` parameter. All four default to on, and tests pin the defaults — an ablation switch
that quietly defaults to off changes the shipped product instead of measuring it.*

## Phase 1 — confirm or delete what exists  *(~10 h GPU)*

⏳ **Queued and running unattended** as `scripts/phase1.sh`, which waits for the floor set and
then writes both ablation pairs in order. Every `replicate` call resumes rather than restarts, so
an interruption costs the current scene and re-running the script picks up where it stopped.

**5. Ablate the refrain feedback.** Two runs each way. Compare on *concentration* and mean
recurrence, never the worst refrain (rule III). One piece of evidence already survives the floor
and should be kept either way: of ten phrases named to a brief mid-book, seven never appeared
again *in that same book* — a within-book before-and-after that needs no replicate.
**Kill criterion:** concentration inside the floor means the feedback is prompt weight with no
return, and comes out.

**6. Ablate the gesture feedback.** Same design. Measure the mean gesture rate across four runs,
not the first-fire scene, which is a maximum in disguise. **Kill criterion:** difference inside
the 31% floor.

**7. Run the re-people pass against a live plan for the first time.** ✅ **It was broken, and
this is what found it.** It is tested only against a scripted backend. Generate plans until one
comes back solo-heavy — the count is bimodal, so roughly one in three — then verify the rewritten
scenes keep their thread obligations. The prompt holds summary, setting and posts fixed and
nothing currently checks that it obeyed.

*The first live plan came back 38% solo, nine scenes. The pass fixed **one**. Not because the
model refused: asked to repeople scenes 2, 4, 5, 6 and 8, `qwen3:8b` returned rows numbered
**1, 3 and 4** — positions in the list it had been shown, not the indices printed beside them.
Matching by index discarded almost everything, and the single success was a coincidence, scene 4
being both a real index and a returned position.*

*The yield was the smaller half. **A row meant for the third item, labelled 3, would have been
applied to scene 3** had scene 3 been in the window — the wrong rewrite landing silently on the
wrong scene.*

*This is the only planner call that shows a model a non-contiguous set. `flesh_scenes` and
`expand_beats` show contiguous ranges and are unaffected — a model asked for scenes 6 to 10
returns 6 to 10, and every scene in every generated plan has beats and a summary. The fix removes
the ambiguity rather than instructing around it: the window is numbered 1..N, real indices never
appear as labels, and code owns the mapping back. **Live on the same plan: 1 of 9 becomes 7 of
9.***

*The scripted fixtures echoed correct indices back, which is why 780 green tests could never have
caught this.*

*And the obligation check the step asked for now runs and passes: thread ops, settings and
declared dependencies are all intact through the pass, snapshotted and restored rather than
trusted. One further thing it caught — the rewrite reached for a phrase the plan forbids.
`make_plan` scrubs after this pass and so absorbs it; `redthread repeople` standalone now does
the same, or the plan it writes is not the plan `make_plan` would have produced.*

**8. Decide whether the bimodality is the planner or the premise.** Six plans of one premise gave
5, 5, 22, 24, 10, 28 solo scenes. Generate six of a *different* premise. If the split persists it
is the planner; if one premise clusters low and another high, it is the story asking for solitude.

## Phase 2 — rebuild tension on meaning rather than words  *(~5 h GPU)*

The forecast probe fails because a two-sentence prediction and an 800-word scene share too little
*vocabulary* for lexical overlap to separate a right guess from a wrong one. `nomic-embed-text`
has been installed on the target machine the whole time and never used.

**9. Add an embedding backend.** ✅ Ollama's `/api/embed`, cached by text hash, no new dependency.

*`redthread/embed.py`. Verified live: 768 dimensions, batching endpoint, disk cache keyed by
model **and** text — sharing a cache across embedding models would produce cosines between two
different vector spaces, which is a number that looks exactly like a measurement. Two related
sentences score .798 and two unrelated ones .427, which is the reason nothing here ever prints a
raw cosine as a result: only a difference between two of them means anything.*

**10. Re-score the existing 35 predictions semantically.** ⚠️ **The premise was wrong — they were
never on disk.** ~~They are already on disk — a free repeat of a failed experiment with one
variable changed.~~

*`probe_forecast` only records a Violation when the overlap clears its threshold, and across the
whole corpus none ever did, so the original calibration ran in a throwaway script and left
nothing behind. The re-score was not free; the generation had to be paid for a second time.*

*That is the more useful half of the finding, and it is now fixed rather than worked around:
`redthread/forecast.py` persists each prediction **with the context that produced it**, so a
re-score cannot silently change what the model was shown. An experiment whose only output is a
pass/fail verdict cannot be re-analysed, and this project's most expensive negative result was
stored that way.*

**11. Run the control before believing anything.** ⛔ **Kill criterion fired.** Predicted scene
against a random other scene from the same book. Lexical overlap won 41% of the time, worse than
chance. **Kill criterion:** below about 65% and embeddings have failed the same way words did —
go to step 12, not to a threshold.

*Run on 35 scenes of a finished 71-scene novel, k = 5 each, 175 local calls:*

| scorer | on target | on control | win rate |
|---|---:|---:|---:|
| lexical overlap | 0.549 | 0.543 | **51%** |
| embedding cosine | 0.749 | 0.739 | **54%** |

*Neither reaches 65%. **Meaning overlap fails the same way word overlap did.** A prediction and a
scene from one novel share the novel, and what is left over will not separate a right guess from
a wrong one.*

*Look at the absolute cosines rather than the win rate: **.749 against .739.** A raw similarity
between any two scenes of one book is high and says nothing, which is why nothing in this module
prints one as a result.*

*Two incidental confirmations. Re-scoring with the corrected decoy pool — which excludes the
three scenes the model was actually shown — moved lexical from 40% to exactly chance and left
embeddings unmoved. And that re-score cost **six embedding calls against 309 served from cache**,
with no regeneration at all: the persistence fix earning its place within an hour of being
written, on the very failure it was built for.*

**12. If one prediction is not enough, measure the spread of several.** ⏳ The cited work measures
the *entropy of a forecasting distribution*, not the accuracy of one sample. Generate k
predictions and measure how much they disagree with each other. A scene the model can call has low
spread. This never needs the actual scene, so the book's shared vocabulary cannot confound it.

*First distribution: mean spread **.130**, range .060 to .266 across 35 scenes. Plausible — and
so was lexical overlap's, which was noise. A distribution is not evidence.*

*So `spread_stability` applies the replicate rule one level down: do two independent prediction
sets agree about which scenes are predictable? If they rank the scenes differently, the spread
measures the sampling rather than the scene, and step 13 has nothing to plot. A second set is
generating.*

**13. Only now, look at the middle.** Plot tension across a manuscript; a sagging middle should
appear as a run of low-spread scenes. First honest test of what four earlier attempts could not
reach.

## Phase 3 — let the middle earn the ending  *(~1 h GPU)*

**14. Make dependency explicit instead of inferring it.** ✅ Add `depends_on: list[int]` to
`SceneSpec` and the planner schema. Inference by subject overlap failed because the cast recurs;
asking is cheap and the answer is checkable.

*Forward and self edges are filtered in `_apply_scene_content` before they reach a spec, for the
same reason `to_state` is never read from the model: an edge is a structural claim and structure
is not the model's to make.*

**15. Check the graph is a graph.** ✅ Deterministic, no model: dependencies point backwards, no
cycles, and the final scene's ancestor set is reported as a fraction of the book. An ending that
depends only on its last five scenes is visible before a word is written. **Before shipping:** run
it against the reference plan (rule V), which has no such field — decide what absence means rather
than failing it.

*Absence means unknown. `check_dependency_graph` returns nothing at all until some scene has
declared something, because "nobody was asked" and "there are none" are different states and it
cannot tell them apart — the reference plan predates the field, and rule V says a check that
fires on it is wrong. `redthread depends <run>` prints the shape and says exactly that on an old
plan.*

*Cycle detection turned out to need no code. Every edge must point strictly backwards, and a
graph in which every edge points backwards cannot contain a cycle, so the one check subsumes it —
`ancestors` is still written to terminate on a hand-edited cycle, with a test, because a
traversal that loops forever is worse than one that reports a violation.*

**16. Test whether declared dependency shows up in the prose.** ⏳ *(built; needs a plan that
declares some)* Does scene N sit closer to its declared ancestors than to a random earlier scene?
If a declared dependency leaves no trace, the field is bookkeeping.

*`redthread depends <run> --prose`. Same result-plus-control shape as the forecast scorers,
because an absolute similarity between two scenes of one novel is a property of the novel's
vocabulary — two scenes with the same cast in the same town will always look alike, and the
question is whether the declared ones look more alike than that. No plan on disk declares
dependencies yet, so this runs when the next book is planned.*

## Phase 4 — want, obstacle, cost  *(~4 h GPU)*

Exactly one quality axis has moved, and it moved by finding a countable prose property, finding
its plan-level correlate, and changing one line of the planner prompt. Do not deviate.

**17. Find the countable property first** — the symptom, not the fix. ✅ Candidates: how often
the POV character's action is negated or refused; how often a scene's outcome differs from what
they sought. One proxy is already refuted: POV-as-sentence-subject is flat at .13–.20 everywhere.
**Kill criterion:** a measure that does not vary cannot be improved.

*Two measures pass, both now in the panel with floors. `refusal_rate` counts a refusal being
**performed at somebody** — a head shaken, a request declined, a no said aloud. `refusal_per_ask`
divides by the asking, because a scene with ten requests and ten grants is a scene of errands
however busy it is.*

*⚠ **Both were audited hours after shipping and both were 56% contaminated.** `_REFUSAL` also
matched `won't`/`wouldn't`/`would not`/`will not` — 409 of 714 matches, mostly ordinary negated
futures like "whatever lay beyond this door would not be easy". `_ASKED` also matched
`wanted`/`needed`/`meant to` — 493 of 873, internal desire rather than a request anyone could
refuse. The docstring asserted in as many words that the measure did not do this. **Every figure
first published here was the contaminated version's.***

*Corrected: 50% of 444 scenes contain no refusal at all (not 25%), median 0.00 and maximum 3.74
(not 1.41 and 12.55), floors of 22% and **37%** (not 14% and 0.3%). The claim that
`refusal_per_ask` was the steadiest measure in the panel is **withdrawn** — both halves of that
ratio were dominated by ordinary English, which is very stable. It is one of the noisiest.*

*What survives step 17's bar: 94% between-book spread against a 22% floor, and 221% against 37%.
They separate books rather than samplings. They are coarser than first reported, and being zero
in half of all scenes is a real limit on what can be built from them.*

**18. Correlate it against plan fields.** ⛔ **Kill criterion fired.** Beats naming a spoken act
correlated with dialogue at **r = +0.672**, against r = 0.141 for the hypothesis that was
discarded. **Kill criterion:** below about r = 0.4, the plan is not the lever for this axis. Say
so and stop.

*So: saying so and stopping.* Across 538 committed scenes from 16 runs, an outline naming a
refusal, a denial or a blocking correlates with `refusal_rate` at **r = +0.130** and with
`refusal_per_ask` at +0.063. An outline naming a price scores +0.032. All are below 0.4, and the
bar is missed by four times over.

*(First published as +0.217 and +0.200, against the contaminated measures. Narrowing them halved
the correlation. The conclusion did not change and the margin got wider — the only direction in
which a correction to one's own negative result is comfortable.)*

*The controls are clean, which is what makes this a result rather than a broken instrument: the
same plan features score +0.001 and −0.021 against gesture rate, so they are not simply
predicting how talkative a scene is. And the method is not at fault either — on the identical
corpus, "the outline names a spoken act" against dialogue share reproduces at **+0.446**, using
the same crude regex over the same fields. The one axis that moved still scores twice what this
one does.*

*The effect is real and small: scenes whose plan names a refusal average 0.78 refusals per
thousand words against 0.58, and 50% contain none against 60%. The plan moves this axis about a
quarter as hard as it moves dialogue. Recorded in `plan_names_a_refusal`'s docstring so a later
attempt starts from "this scored 0.130" rather than from the same hypothesis unexamined.*

*(The r = +0.672 figure was measured on 108 scenes; the same measure on 538 gives +0.446. The
direction and the ranking hold, the magnitude does not — one more reminder that a correlation
from a hundred scenes is not a constant.)*

**19. Add `want`, `obstacle` and `cost` to the scene spec.** ⛔ **Not done, by step 18's kill
criterion** (r = 0.130 against a 0.4 bar).** ~~Mirror the thread-operator shape: named fields with their own audit, not prose.~~

*Adding three fields to every scene spec on r = 0.130 would be building the intervention the
evidence says will not carry. The fields are cheap; the brief they would swell is not — everything
in there arrives in every one of seventy scenes, and this project already has a rule about that.
If this axis is worth another attempt, the next move is a better prose measure or a different
lever, not this one on weaker evidence.*

## Phase 5 — the sentence  *(no GPU, one human evening)*

**20. Build a sampler, not a metric.** ✅ `redthread sample <run> --n 30` prints random sentences
with no context and no scores.

*`redthread/sample.py`, and it is deliberately incapable of scoring anything. `--against` builds
a shuffled sheet from two conditions and writes the key to a **separate file**, because a key
beside the sheet is not a blind and the person who has to resist reading it is the one who wrote
the prose.*

**21. Rate a hundred sentences by hand, once.** ⏳ **The sheet is built and waiting for a
person.** Fifty from before the prose work, fifty from after, shuffled and unlabelled. Would you
read it again. This is the only ground truth this project will ever have on the question.

*[docs/evidence/sentences/sentences.md](evidence/sentences/sentences.md) — 100 sentences, one
digit per line, about twenty minutes. Both sides are* The Debt of Years*, so the premise is held
constant and only the era varies: `runs/debt` (duplication .319, a run of 4+ past-perfect in 67%
of scenes) against `runs/current` (.001 and 0%).*

*Building it surfaced a confound before anyone rated anything. The two sides came back **12% and
42% spoken** — dialogue share is the axis that has moved most here, from .077 to .223 — so a
rating difference could as easily be a preference about dialogue as a judgement about prose.
Balancing the draw would make the sheet unrepresentative of the books, so nothing is dropped:
the flag is recorded in the key and `rate` splits on it. This is the one item on the whole list
that cannot be done by the machine that wrote the sentences.*

**22. Only then look for a correlate.** ✅ *(the analysis; its input is step 21)* Test every
existing measure against the ratings. If none correlates, that is the finding — and a valuable
one, because it says the instrument panel is orthogonal to what a reader notices.

*`redthread rate <sheet> --key <key>` reports the mean per side with a 95% bootstrap interval
(hand-rolled — no runtime dependencies, and a three-point scale is not normal), splits on the
speech control, flags any cell under n=15 as too few to read, and correlates every per-sentence
signal against the ratings. Verified end to end on random ratings, where it correctly reports
that nothing reaches r = 0.3.*

*One limit is worth stating rather than discovering later: duplication, refrains and cross-scene
gesture repeats are properties of a manuscript and cannot be asked of a single sentence. A sheet
like this can never test the measures this project has spent most of its effort on.*

## Phase 6 — write the rule down  *(~3 h GPU)*

**23. Codify the distinction the project has been using without stating it.** ✅ The gate may
only refuse what code can check. The *plan* may be shaped by anything, including a model's
reading, because a bad plan costs a re-ask and a bad gate costs a book that never finishes. Every
quality gain here came through that door: the dialogue instruction, the catchphrase filter, the
re-people pass. None is a check.

*Written down as `checks.BLOCKER_SOURCES` and **enforced**: a test walks the source tree for
`Severity.BLOCKER` and insists the emitting source has recorded what a person could check by
hand. Adding a blocker now means writing that sentence, which is the only form a principle
survives in.*

*Writing the test sharpened the rule twice in five minutes. It caught a source mislabelled from
memory — `no_threads` comes from `check_subplot_independence`, not `audit_plan` — and it refuted
the claim that there is exactly one model-sourced blocker. There are two: `llm:extract_facts`
blocks as well. That is not a counterexample but a better statement of the rule — neither refuses
a scene for **how it reads**. One answers a binary question about two ledger rows code selected
and quotes both; the other fires because a call returned nothing parseable, which is a broken
call, not an opinion.*

**24. Audit the four checks that cannot fire.** ✅ *(six, in the end)* Subplot independence,
midpoint stall, uniform scene length and somatic each test a property the scheduler or the brief
already guarantees. Either give them a reason to exist or mark them so they never read as
coverage again.

*Marked, in code rather than only in prose: `SCHEDULER_GUARANTEED` (six kinds — the three state
legality checks belong with the other three) and `INSTRUCTION_CONFIRMING` (somatic, which is
quiet for a different reason: a model is complying with the brief, and that could stop being true
at any time without anything here changing). `redthread audit` now prints the list beside its
result, so a clean audit can never again read as coverage it does not provide. A test asserts
every named kind is one the codebase can still emit, so a rename cannot leave the disclaimer
pointing at nothing.*

**25. Re-run the whole panel on a fresh premise and publish the numbers.** Two runs, every measure
with its floor. Whatever it says then is the state of the project — and the first time that
sentence will be true.

---

## Shape of it

| phase | steps | GPU | most likely outcome |
|---|---|---:|---|
| 0 — trustworthy instruments | 1–4 | ~3 h | prerequisite; no result of its own |
| 1 — confirm what exists | 5–8 | ~10 h | at least one mechanism is deleted |
| 2 — tension on embeddings | 9–13 | ~5 h | step 12 works where step 11 does not |
| 3 — dependency graph | 14–16 | ~1 h | cheapest phase; a plan-level answer to a prose question |
| 4 — want, obstacle, cost | 17–19 | ~4 h | stalls at step 17 if nothing countable varies |
| 5 — the sentence | 20–22 | none | one human evening; the riskiest finding |
| 6 — write the rule down | 23–25 | ~3 h | closes the loop; nothing new is built |

**Half of these steps are designed to conclude that something does not work.** That is deliberate.
The last two days produced five findings that were properties of the apparatus and three claims
retracted for having no error bars, and every one cost more to unwind than a control would have
cost to run first. Phase 1 exists to delete things; steps 11, 17, 18 and 22 each have an explicit
condition under which the honest answer is to stop.

**Sequencing.** Phase 0 blocks everything. Phase 2 blocks step 16. Phase 5 depends on nothing and
could start tonight. Phases 1 and 4 are independent of each other and of everything after phase 0.

**The one prediction worth committing to:** step 21 is the highest-value item on this list and the
only one requiring a person. Everything else measures whether the prose *scores* better. A hundred
rated sentences is the only thing that can say whether it *is* better — and if the answer is no,
most of the panel needs rethinking rather than extending.
