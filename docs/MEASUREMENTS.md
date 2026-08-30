# What has been measured, and what turned out not to measure anything

Every threshold in this project is set from a corpus rather than from taste, which means a lot of
candidate measures get built, tested and thrown away. This file is the record of both halves.
The refuted list is the more useful one: it is what stops the same afternoon being spent twice.

Corpus as of 30 August 2026: 17 completed books, 482 scenes, `qwen3:8b` in every role. Reference
band is three cold single scenes from `gemma3:12b`, `phi4:14b` and `qwen3:8b` with no
orchestration, in `docs/evidence`.

**The corpus has two eras, and most figures below mix them.** Ten books predate the prose work of
29–30 August; seven were written after it. The difference is not incremental:

| | scenes | duplication | recap | gestures | a run of 3+ | a run of 4+ | gloss |
|---|---:|---:|---:|---:|---:|---:|---:|
| pre-prose-work | 109 | .279 | .380 | 3.4 | 75% | 61% | 47% |
| current era | 373 | **.002** | **.047** | 2.2 | **4%** | **0%** | **0%** |

Any threshold in this project derived from "the committed corpus" was derived mostly from the top
row. That is correct for a threshold meant to catch the defect — you calibrate on prose that has
it — and misleading for any sentence of the form "scenes in this project run to X". Where it
matters below, the era is named.

One consequence worth stating: `check_recap_block` now never fires. Zero of 373 current-era scenes
carry a run of four consecutive past-perfect sentences, against 61% before. The check did its job
and the sampler fix removed the cause; it is kept for the same reason `midpoint_stall` is, and
lowering it to three was considered and rejected — 16 blocks exist across the whole current
corpus and several are unquoted reported speech, where past perfect is doing legitimate work.

---

## Measures that discriminate

| measure | what separates | where it is used |
|---|---|---|
| `duplication_ratio` | .009 reference vs .340 early corpus | selection, and the signal the sampler fix was found with |
| `summary_distance` | .105 reference vs .420 early corpus | advisory; selection |
| `recap_blocks` | reference tops out at 2 consecutive; corpus reaches 46 | MAJOR, with two repairs |
| gesture rate | 1.4 reference vs 3.8 early corpus | advisory; selection. Allowance rises with dialogue |
| cross-scene gesture repeats | 0 in a 9-scene book; 13 scenes in a 71-scene one | fed into the next brief |
| `manuscript_refrains` | .015 book-wide at 9 scenes, .055 at 71 | fed into the next brief |
| dialogue share | .077 vs .223 between two books of the same plan | advisory; selection |
| beats naming a spoken act | r = +0.446 with dialogue in the prose, over 538 scenes | the planner prompt |
| `refusal_rate` | 0.32 to 1.01 across books; 22% between identical runs | the panel |
| `refusal_per_ask` | .037 to .833 across books; 37% between identical runs | the panel |

*The spoken-act correlation was reported here as r = +0.672. That was measured on 108 scenes; the
same measure over 538 gives **+0.446**. The direction and the ranking hold — it is still, by a
factor of two, the strongest plan-to-prose link in the project — and the magnitude does not. A
correlation from a hundred scenes is not a constant, which this project has now been caught by
twice.*

## Measures that did not

**Facts extracted per scene.** Flat across a 71-scene book — 14.9 / 15.7 / 15.4 / 14.9 by
quarter, with a floor of 14. It measures the extractor's output budget, not the story.

**New vocabulary per fact.** Declines monotonically, .416 → .131 across a book. That is what any
coherent novel does when its first quarter names the cast and the setting. Without a reference
curve from a book known to be good, the number says nothing, and there is no such curve.

**Scenes ending on a portent.** 56% in one book against 33% in the reference drafts (n = 3) and
**0%** in another cohort of this project's own scenes. Too noisy to build on.

**POV agency.** Share of sentences where the point-of-view character leads, and the share of
those where they are only perceiving. Flat at 0.13–0.20 in every quarter of every book. Built as
a proxy for "does a character want something" and it discriminates nothing.

*Its replacement works and its plan-side lever does not.* `refusal_rate` and `refusal_per_ask`
pass the bar POV agency failed — 94% and 221% between-book spread against 22% and 37% floors — so
what they separate is books rather than samplings. But an outline naming a refusal predicts them
at only **r = +0.130**, against a 0.4 bar and against +0.446 for the one lever that worked. So the
measures are kept and the intervention is not built. Full result, with its controls, in
[evidence/want-obstacle-cost.md](evidence/want-obstacle-cost.md).

**A plan naming a price.** r = +0.032 against refusal in the prose. Same corpus, same method,
and the weakest of the three plan features tried.

### A measure that said it was narrow, and was not

Both refusal regexes were audited hours after shipping, by counting what they matched rather than
trusting the intent behind them, and both were **56% contaminated**. `_REFUSAL` matched `won't`,
`wouldn't`, `would not` and `will not` — 409 of 714 matches, mostly ordinary negated futures like
*"whatever lay beyond this door would not be easy"*. `_ASKED` matched `wanted`, `needed` and
`meant to` — 493 of 873, internal desire rather than a request anyone could refuse.

The docstring said in as many words that the measure excluded "could not" and "did not" so as not
to measure English. It was measuring English through a different door, and the assertion was
convincing enough to have stopped anyone checking.

Narrowing halved the correlation, from +0.217 to +0.130, and **withdrew a headline claim**:
`refusal_per_ask` was reported as the steadiest measure in the panel at 0.3% between identical
runs. Both halves of that ratio were dominated by ordinary English, which is very stable.
Narrowed, it moves 37% — one of the noisiest measures here.

**Count what a pattern actually matched before publishing anything computed from it, and read a
sample in context.** Both audits took minutes.

**Within-scene gesture variety.** Distinct gesture pairs over total gestures sits at ~1.0 across
four books. Gestures are already varied *inside* a scene; the repetition is between scenes, which
is why `manuscript_gestures` exists and `check_gesture_density` cannot see it.

**A stated pronoun as a cure for gender drift.** Reading a late scene found Vay Sorel called
"her" in one book and "He" in another, and the bibles say nothing about gender — so the theory was
that an unstated pronoun lets each scene guess. Measured: characters *with* a pronoun in their
description drift at 9.1% (n = 29) and those without at 6.6% (n = 7). The wrong way round, and
Otto Renner in the reference plan has no stated pronoun and 0% drift.

The measurement is also unsound, which is the more useful half. It counts pronouns within ninety
characters after a character's name, and cannot tell that character's pronoun from a nearby one's:
the passage that prompted it reads "Vay stood nearby … back to **Kai's** face. He said nothing",
where "He" is genuinely ambiguous to a reader too. Any number built this way inherits that
ambiguity. Nothing was shipped.

**Forecastability as a measure of tension.** The `--forecast` probe asks a model to predict the
next scene from the story so far, then scores the guess against what the scene actually contained.
Rebuilt so the prediction is blind — the old version had the scene in the prompt and let the model
mark its own work — and then calibrated over 35 scenes of a finished novel. The distribution looks
plausible: mean .538, range .26 to .73.

The control kills it. Each prediction scored against **the scene it was predicting** gives .540;
against **a random other scene from the same book**, .492. The scene actually predicted scores
higher only **41% of the time**, worse than chance. Weighting by rarity across the book, so cast
names and recurring objects count for less, moves it to 51%. Still chance.

A two-sentence prediction and an eight-hundred-word scene share too little distinctive vocabulary
for lexical overlap to separate a right guess from a wrong one, and what they do share is the
book's furniture. Left in the codebase, off, with the control result in its docstring — the idea
is sourced and one book is one book, but this implementation reports noise.

**Inert beats as a cause of recap.** r = 0.141 across 108 scenes. The same beat property
correlates with *dialogue* at r = +0.672, so the hypothesis was not wrong in kind — it was
pointed at the wrong outcome.

---

## Measurements that were really measuring the instrument

Three times a promising result turned out to be a property of the measuring apparatus. All three
were caught by asking "what would this look like if the code were wrong", and all three would
have shipped as findings otherwise.

**"Every scene is load-bearing."** Zero scenes in 70 contributed facts that were never retrieved
again — because `Ledger.about` retrieves by subject-name overlap and the cast recurs. It measures
entity overlap, not dependency.

**"The ending never reaches past the last three scenes."** Median retrieval distance of 2 scenes,
nothing beyond 20. True, and a description of `Ledger.about`'s recency cap rather than of the
book. At scene 71, 888 facts matched the scene's subjects and 40 survived, the oldest from scene
68. Fixed by stratifying the slice; the measure is now meaningless for the reason it was built.

**Gesture density against a "clean cohort".** The threshold was set at a flat 3.0 per thousand
words from five reference scenes — four of which contain *no dialogue at all*, being cold opening
scenes. Applied to a book that is 15% dialogue it fired on 34 of 71 scenes, and the scenes it
fired on had higher dialogue than the ones it spared. It was penalising the scenes that had
improved.

---

## Which checks actually fire

`tests/test_checks.py` opens by saying a check that never fires is indistinguishable from a
check that does not work. Run every check over all 373 committed scenes and all 13 plans, and
**20 of the 48 violation kinds have never fired once**. None of them is broken, and the reasons
are worth separating.

**Blocking kinds are absent from committed scenes by construction.** `pov_person`,
`somatic_emotion`, `forbidden_phrase`, `style_leak`, `format`, `truncated_scene`,
`length_runaway`, `seam` — every one of these either blocks a commit or is repaired before it.
Measuring them on committed prose measures the survivors. Their absence is the gate working.

**Some plan checks are guaranteed by construction rather than checked.** `check_subplot_independence`
has never reported a decorative subplot, and measuring the actual overlap says why: median
overlap between a subplot's scenes and the main thread's is **33%**, and only 2 of 56 subplots
across every plan reach the 0.80 threshold. `schedule.py` assigns which scene moves which thread,
so independence is structural. The same holds for `state_regression`, `state_repeat` and
`unknown_state` — the scheduler cannot emit an illegal transition, so the checks that would catch
one are permanently quiet.

**`midpoint_stall` is the sharpest case, and it deserves its own paragraph.** It exists to catch
a manuscript whose middle restates its opening rather than raising the stakes — the sagging
middle, named in `STATUS.md` as one of the things nothing measures. It fires when more than half
the active threads gain no ground in the middle third.

Across all 28 plans in the project, **zero threads stall in the middle third of any of them.**
Not one, ever. Because `schedule.py` assigns which scene moves which thread to which state, every
thread gains ground in every third by construction. The check cannot fire.

So the project has a check named for the sagging middle that is structurally incapable of
detecting one, and its presence in the audit implies a watch that is not being kept. Detecting a
sag would mean measuring the *prose* — and the two prose measures tried for it, fact accumulation
and vocabulary novelty, are recorded above as refuted. Dialogue share is the only one that ever
showed the shape, and it now sits at .157/.130/.175/.162 by quarter, flat.

`check_somatic` is blind for a third reason: nothing ever exceeds its threshold. Across 456
committed scenes **no scene contains more than one somatic beat**, and the check fires above one.
The brief tells the writer "at most one somatic beat in this scene" and the writer complies, so
the check confirms an instruction rather than catching a violation.

What it cannot see is a corpus-level drift — and the attempt to show one here failed. The share
of scenes carrying a somatic beat reads 45% in the current era against 27% before the prose work,
which looks like movement in the wrong direction on a tell measured at 81% AI against 38% human.

Three runs of **one identical plan**, differing only in ledger changes unrelated to bodily
description, give **38%, 59% and 42%**. The between-run swing is wider than the between-era gap.
The gap establishes nothing, and the r = +0.44 correlation with dialogue share across eight books
has its own counterexample: `scale60` carries old-era dialogue at .077 and new-era somatic at 44%.

The structural point survives the retraction: a per-scene cap cannot detect a distributional
shift, and this check would not report one if it happened. That is worth knowing separately from
whether one has.

`uniform_scene_length` is blind the same way and more obviously: it fires only when every scene
in a plan carries an identical word target, and `schedule.word_targets` varies them by seed — ten
scenes come back with eight distinct values. Zero of 28 plans are uniform. It can only ever
confirm the scheduler.

**Two are untested rather than blind**: `cohesion_cut` and `missed_deadline`. These have unit
tests and no live instance in 373 scenes, so nothing is known about their false-positive rate on
real prose. Not broken, not exercised.

### The rule this suggests

**A check over a field the scheduler constructs can only ever confirm the scheduler.** Six
checks in this project are quiet for that reason — subplot independence, the three state-legality
kinds, midpoint stall and uniform scene length — and all six read as coverage in an audit that
lists them.

*They are now named in code, as `checks.SCHEDULER_GUARANTEED`, with `check_somatic` in a separate
`INSTRUCTION_CONFIRMING` table because its guarantee is different in kind: the scheduler's holds
because code makes it hold, and the brief's holds because a model is complying, which could stop
being true at any time without anything here changing. `redthread audit` prints both beside its
own result, and a test asserts every named kind is still one the codebase can emit — so a rename
cannot leave the disclaimer pointing at nothing.* They are
worth keeping for hand-authored plans, where the property is not guaranteed, and worth discounting
entirely when reading a generated one.

The corollary is the uncomfortable half: every property `schedule.py` guarantees is a property
nothing verifies in the prose. Threads reach their terminal states because the schedule says so.
Whether the *book* earns them is not checked anywhere, and `midpoint_stall` is the check that
looks like it does.

The distinction matters when reading a green suite. A check that is quiet because the gate
upstream of it works is doing its job; a check that is quiet because nothing has ever tested it
is an unknown wearing the same colour.

### The slop list, checked and left alone

`slop` fires on 56% of scenes, and the most-flagged entry across every run is **"nodded"** with
119 of 395 hits. Characters nod; banning the word looked like the mistake
`check_ban_is_avoidable` exists to prevent — a word the prose is made of, fought in every scene.

Measured against the corpus, that reading is wrong. Share of the 472 committed scenes each
single-word entry appears in:

```
   25%  nodded
   14%  flickered
    5%  glinting
    2%  thrummed, nestled
   <1%  everything else
```

**Zero entries appear in 30% or more of scenes, and 70 of the 75 single-word entries appear in
under 5%.** The list is well targeted. It is one word, not a systemic problem, and the entry is
externally measured — antislop's data says "nodded" is over-represented in machine fiction, and
25% of scenes is not the same as unavoidable.

Nothing changed. Recorded because the hypothesis was reasonable, the fix would have been easy,
and the data did not support it.

### The other end: checks that are constants

The mirror of a check that never fires. Measured over the 392 scene records every run has left
behind, five kinds fire on more than half of all scenes and are carried into the commit almost
every time:

| kind | fires on | committed carrying it |
|---|---:|---:|
| `repetition` | 94% | 369 of 369 |
| `tell_thematic_gloss` | 84% | 330 of 331 |
| `tell_summarised` | 76% | 296 of 297 |
| `internal_repetition` | 57% | 221 of 222 |
| `slop` | 56% | 218 of 218 |

None of this is a defect, and two of them are documented as expected. `probe_tells` has a known
false-positive floor — its own docstring records that qwen3:8b flags "The tally sheet had been
photocopied so often that the column headings had closed up", a pure physical description, as
thematic gloss 3 times out of 3 — which is exactly why it is advisory. And the research it
implements puts thematic over-explanation in 77% of machine-written stories, so an 84% detection
rate may be *accurate*. A property present in four scenes out of five does not discriminate
between them either way.

What the table is for is cost. `tell_thematic_gloss` and `tell_summarised` are the output of one
model call per scene, and that call has earned its place as a *discovery* tool — findings it
surfaced became `_GLOSS_PATTERNS` entries that now run for free. As a per-scene signal it is a
constant.

---

## Four checks reverted for firing on the reference plan

The hand-authored reference plan in the test suite is the calibration standard: it is the one
plan in the project written by a person, and `TestReferencePlan.test_audit_is_clean` asserts that
every plan-level check passes it. Four checks have now been built, measured, and deleted because
they did not.

The reason has been the same every time — **matching vocabulary rather than the property**.

| the check | what it flagged on the reference plan |
|---|---|
| `check_scene_is_not_the_concealment` | two scenes, on an earlier corpus |
| the cross-scene refrain MAJOR | fired unavoidably on fixtures |
| `check_scene_has_an_exchange` | "She leaves with a form and no remedy, and takes it out on the wrong person" — interaction described without a verb from the list |
| `check_post_reveals_the_concealment` | "the reader sees that Otto has noticed something and chose not to look" |

The last is the sharpest illustration. The check flagged posts sharing words with a still-active
concealment, and there *are* real instances: a generated plan asked a scene to bring about "Kai
is torn between his duty and the enclave's survival" while concealing "the reader must not know
that Kai is torn between his duty and the truth about the enclave". Near-verbatim, and
unsatisfiable.

But no threshold separates it from good craft. The reference plan's worst case reuses **0.67** of
its concealment's words; the real contradiction reuses **0.60**. A well-written plan deliberately
echoes the concealment's language while withholding the disclosure — that *is* the technique. A
word-overlap check cannot tell "hints at the secret" from "states the secret", and never will.

**The rule this suggests:** a plan-level check that compares two fields by shared words is
measuring a habit of the generator, not a property of the plan. The three plan checks that
survive — unwritable bans, catchphrases, story-shaped style samples — all test a *field against
itself or against a fixed list*, never one field against another.

---

## How much does a measure move when nothing changes?

Two findings were retracted on 30 August within an hour of each other, both for the same reason:
a difference was measured before anyone measured how much the same thing varies against itself.
Long speeches "rose" from 1% to 4%; somatic beats "rose" from 27% to 45%. Neither survived.

Across the three runs of one plan that differ only in ledger changes — which have nothing to do
with prose register — the measures move like this:

| measure | run 1 | run 2 | run 3 | spread / mean |
|---|---:|---:|---:|---:|
| dialogue share | .223 | .211 | .211 | **6%** |
| recap grammar | .042 | .041 | .044 | **7%** |
| duplication, book-wide | .055 | .065 | .066 | 17% |
| gesture rate | 2.09 | 1.90 | 1.73 | 19% |
| somatic share | 38% | 59% | 42% | 45% |
| rhythm fires on | 2.8% | 2.8% | 1.4% | 60% |
| worst refrain | 15 | 10 | 7 | **75%** |
| gesture density fires on | 2.8% | 1.4% | 4.2% | 100% |
| duplication, per scene | .001 | .003 | .001 | **153%** |

Read that table carefully, because it does not say what it first appears to. Those three runs
**are** the conditions being compared, so the spread is effect and noise together and cannot
separate them. There is no true replicate in this project — no two runs of the same plan with no
change between them.

What it does establish: dialogue share and recap grammar barely moved across three sets of ledger
changes, so they are stable enough that a difference in them means something. And the headline
result of the ledger work — the worst refrain falling 15 → 10 → 7 — has a range identical to its
own claimed effect. It may be real; nothing here shows it is.

*A replicate has since been run, and it retracts three claims made the same day.* The floor is
in [evidence/replicate-noise-floor.md](evidence/replicate-noise-floor.md): dialogue share and word
count are stable to within 4% between identical runs, duplication and recap to within a third, and
**anything counting a maximum — worst refrain, worst gesture — swings by half its own value**.
Maxima are the least trustworthy statistic in this project and were the ones quoted most often.

### The floor now lives in code, and stating a difference has to pass through it

`checks.NOISE_FLOOR` holds it, keyed identically to `checks.manuscript_measures` — a test asserts
the two sets match in both directions, so a measure cannot be reported without an error bar, nor
keep one after it is deleted. `checks.clears_noise(measure, a, b)` is the gate, and it **raises**
on a measure with no measured floor rather than returning a verdict: *"I have not measured this"*
and *"this is not different"* are different sentences, and confusing them is what three retracted
claims were made of.

Two things fell out of building it, both worth recording because both were the same error in
different clothes.

**The first floor table failed its own self-test.** Four measures of the very pair the floor was
derived from came back as *clearing* it, because the figures published above had been rounded
down for the write-up and the code used the rounded ones. The table now holds observed values and
a test asserts that a difference exactly the size of a measure's own floor is never a result.

**`repetition_concentration` was given a floor of .20 by guesswork.** The pair says .28. That is
precisely the error the KeyError guard exists to prevent, committed by the person writing the
guard, in the same file, on the same afternoon.

---

## Controls: measures tested against something they should *not* match

Five findings this project nearly shipped turned out to be properties of the measuring apparatus.
The cheapest defence is a control — score the measure against something it has no business
matching, and see whether it notices. These are the ones that have had one.

**`manuscript_refrains` — passes, and the failures were the finding.** A book's reported refrains
were scored against books with *different premises by the same model*. 77% appear in no other
book, so the measure is mostly finding what it claims. The 23% that leak are the model's own
constructions rather than any book's: "the edge of the" is a refrain in **all seven** books,
"the weight of the" in six. Those now live in `data/model_refrains.txt`, because a check that
reads one manuscript is blind to them by construction.

**`manuscript_gestures` — passes cleanly.** The same control finds only two gestures recurring
across three or more books, and none across more. What a book repeats physically is that book's,
not a habit the model carries between premises. No model-level gesture list is warranted on that
evidence.

*Whether it works on what it names is unsettled.* In one book its list stays empty until scene
37, names "gaze flickered" at four scenes, and that gesture appears 0 times in the 34 scenes
after — against scene 15 in the book written before the feedback existed. That looked like the
mechanism working.

**A replicate of the same code and plan first fires at scene 19.** Against 15 without the
feedback, that is nothing, so the delay was run-to-run variation and not the feedback. One
suppressed gesture remains the only evidence, and it is one. See
[evidence/replicate-noise-floor.md](evidence/replicate-noise-floor.md).

**`dialogue_share` — passes, and raised a better question than the control did.** It counts words
inside quotation marks, so the risk is quoted documents or scare quotes. Sampling 1,403 spans:
every one is speech. The longest are 47-51 words and are speeches, not records; the shortest are
exchange fragments ("Gift?", "Recorded elsewhere?"), not emphasis. A speech-verb-proximity control
scored only 56% and is simply a bad control — good dialogue drops its tags.

What reading those long spans raised instead: the brief forbids *"dialogue as philosophical
debate"*, and a 48-word speech about whose voices the law depends on is exactly that. So did the
dialogue fix buy quantity at the cost of kind?

| | dialogue | spans | mean span | median | over 30 words |
|---|---:|---:|---:|---:|---:|
| before the fix | .077 | 579 | 7.6 | 5 | 1% |
| after | .211 | 1297 | 9.7 | 7 | 4% |

Mostly not. The increase is **more turns** — spans more than doubled — with modestly longer ones,
and a median of 7 words is an exchange rather than a speech. Monologues over 30 words did go from
1% to 4%, which is 52 of them where there were 6.

*A control was run and then withdrawn, which is worth recording as its own lesson.* The book
written from the hand-authored reference plan runs at 10.8% over thirty words against 3.8% in the
latest book, and that looked like a clean refutation for about ten minutes.

It is not one. That book was written from a human plan but with **old code** — before the sampler
fix and before every prose check in the project — and it shows: duplication .363 per scene against
.001, recap .370 against .044, thematic gloss in 30% of scenes against 0%, 25 blocks of recap
against none. Its dialogue habits are the old writer's, not a human standard, and using it as a
prose reference compares against a book this project spent two days learning to stop writing.

**A hand-authored plan does not make a prose reference.** The cold reference drafts contain no
dialogue at all, so there is no valid comparator for long-speech rate in this project. The worry
is neither confirmed nor refuted: 52 speeches over thirty words is a fact, and whether that is
many is unknown.

**`probe_forecast` — fails.** Scored against the scene it predicted versus a random other scene
from the same book, the real scene wins 41% of the time. Detail above.

*And the experiment could not be re-analysed, which turned out to matter more than the result.*
`probe_forecast` records a Violation only when the overlap clears its threshold, and across the
whole corpus none ever did — so the 35 predictions were never written anywhere, the calibration
lived in a throwaway script, and repeating it with embeddings instead of word overlap meant paying
for the generation a second time. **An experiment whose only output is a pass/fail verdict cannot
be re-analysed**, and this project's most expensive negative result was stored that way.
`redthread/forecast.py` now persists each prediction with the context that produced it, so a
re-score cannot silently change what the model was shown.

**`check_gesture_density` — failed on its calibration cohort**, four of whose five scenes contain
no dialogue. Detail above.

---

## A cap that was read as a quota

The extraction prompt said *"AT MOST 15 FACTS. A hard limit, not a guideline."* Across every book
in the project the distribution of facts per scene is:

```
     5 facts     1 scene
    14 facts    70 scenes
    15 facts   301 scenes
    30 facts     4 scenes
```

**100% of scenes produced 14 or more.** A spike sitting on the cap is not what extraction looks
like — scenes differ in how much they establish, and these did not. The padding is where
"Kai | is | in a room" and "Mir | is | inside" come from, in a ledger whose own prompt says
atmosphere is not a fact.

*Where the cost is, precisely.* Not in unreached facts: 83–91% of extracted facts reach a brief
at least once, so almost everything gets used eventually. The cost is per-brief. At scene 71 of a
71-scene novel, 888 facts match the scene's subjects and 40 are shown — if half the pool is
padding, half the forty are too, in the same forty slots that were stratified so an ending could
see the beginning of its own book.

*Not yet validated.* The prompt now gives a typical range of three to eight and frames fifteen as
a ceiling, but no book has been written with it.

---

## The pattern behind every surviving refrain

Chasing the worst repeated phrase in each of three novels found the same shape three times: not
the model inventing a tic, but the model faithfully repeating material the brief injects into
every scene.

| the phrase | scenes of 71 | its source |
|---|---:|---|
| "this is not a matter of morality" | 27 | a catchphrase the planner wrote into a character's voice |
| "the weight of thirty years" | 15 | a figure of speech in a style sample, paraphrased |
| jaw tightening, gaze lingering | 13 | the same movement, reworded every time |

The first is the sharpest: the brief was simultaneously telling the model that the character
*often uses the phrase* and listing that phrase as a refrain to avoid. Characterisation beats
prohibition, and always will — one is what the character is, the other is a rule about wording.

Auditing every field the brief injects, across two finished books, finds the residue:

```
  7 scenes  [premise]                 "stole thirty years"
  5 scenes  [style samples]           "casting long shadows"
  5 scenes  [style samples]           "pressing against ribs"
```

All three are paraphrases below `check_style_leak`'s six-word copy threshold. The premise one is
the story's own subject and is not fixable; the sample ones are, and are the reason
`drop_story_shaped_samples` exists. Sample leakage touches 1–11% of scenes depending on the book
and is spread evenly across it, so it is real and modest, and dropping samples later in a book
would not target it.

**The generalisation worth keeping:** before adding anything to the brief, ask what it will look
like repeated seventy times. Everything in there arrives in every scene.
