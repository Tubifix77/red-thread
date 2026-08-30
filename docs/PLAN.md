# The remaining seven, and the order they have to be done in

*31 August 2026. Illustrated version:
<https://claude.ai/code/artifact/79ab4f28-db0c-4e86-80ce-c74d837b4c53>*

Four of the seven open items need an instrument that does not exist. Two are built and unproven.
One is a design decision. **Nothing here can be evaluated at all until phase 0 is done**, because
four mechanisms are currently shipped with no way to turn them off and the noise floor rests on a
single replicate pair.

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

**1. Build a replicate harness.** `redthread replicate <run> --runs N` writes N books from one
plan into sibling directories and prints every measure as mean and range. Nothing else is worth
starting first.

**2. Take the noise floor from n=2 to n=4.** Two runs give a range, not a distribution, and a
range from two samples systematically understates the spread.

**3. Make the floor impossible to ignore.** `checks.clears_noise(measure, a, b)` returns false
when a difference sits inside the published floor. The point is not the arithmetic — it is that
stating a difference should require passing through a function that knows what a difference is
worth.

**4. Add ablation switches for everything already built.** `--no-refrain-feedback`,
`--no-gesture-feedback`, `--no-repeople`, `--no-model-refrains`. This converts "I built it" into
"it can be evaluated", and should have existed before any of them were built.

## Phase 1 — confirm or delete what exists  *(~10 h GPU)*

**5. Ablate the refrain feedback.** Two runs each way. Compare on *concentration* and mean
recurrence, never the worst refrain (rule III). One piece of evidence already survives the floor
and should be kept either way: of ten phrases named to a brief mid-book, seven never appeared
again *in that same book* — a within-book before-and-after that needs no replicate.
**Kill criterion:** concentration inside the floor means the feedback is prompt weight with no
return, and comes out.

**6. Ablate the gesture feedback.** Same design. Measure the mean gesture rate across four runs,
not the first-fire scene, which is a maximum in disguise. **Kill criterion:** difference inside
the 31% floor.

**7. Run the re-people pass against a live plan for the first time.** It is tested only against a
scripted backend. Generate plans until one comes back solo-heavy — the count is bimodal, so
roughly one in three — then verify the rewritten scenes keep their thread obligations. The prompt
holds summary, setting and posts fixed and nothing currently checks that it obeyed.

**8. Decide whether the bimodality is the planner or the premise.** Six plans of one premise gave
5, 5, 22, 24, 10, 28 solo scenes. Generate six of a *different* premise. If the split persists it
is the planner; if one premise clusters low and another high, it is the story asking for solitude.

## Phase 2 — rebuild tension on meaning rather than words  *(~5 h GPU)*

The forecast probe fails because a two-sentence prediction and an 800-word scene share too little
*vocabulary* for lexical overlap to separate a right guess from a wrong one. `nomic-embed-text`
has been installed on the target machine the whole time and never used.

**9. Add an embedding backend.** Ollama's `/api/embed`, cached by text hash, no new dependency.

**10. Re-score the existing 35 predictions semantically.** They are already on disk — a free
repeat of a failed experiment with one variable changed.

**11. Run the control before believing anything.** Predicted scene against a random other scene
from the same book. Lexical overlap won 41% of the time, worse than chance. **Kill criterion:**
below about 65% and embeddings have failed the same way words did — go to step 12, not to a
threshold.

**12. If one prediction is not enough, measure the spread of several.** The cited work measures
the *entropy of a forecasting distribution*, not the accuracy of one sample. Generate k
predictions and measure how much they disagree with each other. A scene the model can call has low
spread. This never needs the actual scene, so the book's shared vocabulary cannot confound it.

**13. Only now, look at the middle.** Plot tension across a manuscript; a sagging middle should
appear as a run of low-spread scenes. First honest test of what four earlier attempts could not
reach.

## Phase 3 — let the middle earn the ending  *(~1 h GPU)*

**14. Make dependency explicit instead of inferring it.** Add `depends_on: list[int]` to
`SceneSpec` and the planner schema. Inference by subject overlap failed because the cast recurs;
asking is cheap and the answer is checkable.

**15. Check the graph is a graph.** Deterministic, no model: dependencies point backwards, no
cycles, and the final scene's ancestor set is reported as a fraction of the book. An ending that
depends only on its last five scenes is visible before a word is written. **Before shipping:** run
it against the reference plan (rule V), which has no such field — decide what absence means rather
than failing it.

**16. Test whether declared dependency shows up in the prose.** Does scene N sit closer to its
declared ancestors than to a random earlier scene? If a declared dependency leaves no trace, the
field is bookkeeping.

## Phase 4 — want, obstacle, cost  *(~4 h GPU)*

Exactly one quality axis has moved, and it moved by finding a countable prose property, finding
its plan-level correlate, and changing one line of the planner prompt. Do not deviate.

**17. Find the countable property first** — the symptom, not the fix. Candidates: how often the
POV character's action is negated or refused; how often a scene's outcome differs from what they
sought. One proxy is already refuted: POV-as-sentence-subject is flat at .13–.20 everywhere.
**Kill criterion:** a measure that does not vary cannot be improved.

**18. Correlate it against plan fields.** Beats naming a spoken act correlated with dialogue at
**r = +0.672**, against r = 0.141 for the hypothesis that was discarded. **Kill criterion:** below
about r = 0.4, the plan is not the lever for this axis. Say so and stop.

**19. Add `want`, `obstacle` and `cost` to the scene spec.** Mirror the thread-operator shape:
named fields with their own audit, not prose. Write the prompt instruction as an expectation and
stop — the conditional wording took solo scenes from 10 to 34, and explaining the exception
quadrupled it.

## Phase 5 — the sentence  *(no GPU, one human evening)*

**20. Build a sampler, not a metric.** `redthread sample <run> --n 30` prints random sentences
with no context and no scores.

**21. Rate a hundred sentences by hand, once.** Fifty from before the prose work, fifty from
after, shuffled and unlabelled. Would you read it again. This is the only ground truth this
project will ever have on the question.

**22. Only then look for a correlate.** Test every existing measure against the ratings. If none
correlates, that is the finding — and a valuable one, because it says the instrument panel is
orthogonal to what a reader notices.

## Phase 6 — write the rule down  *(~3 h GPU)*

**23. Codify the distinction the project has been using without stating it.** The gate may only
refuse what code can check. The *plan* may be shaped by anything, including a model's reading,
because a bad plan costs a re-ask and a bad gate costs a book that never finishes. Every quality
gain here came through that door: the dialogue instruction, the catchphrase filter, the re-people
pass. None is a check.

**24. Audit the four checks that cannot fire.** Subplot independence, midpoint stall, uniform
scene length and somatic each test a property the scheduler or the brief already guarantees.
Either give them a reason to exist or mark them so they never read as coverage again.

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
