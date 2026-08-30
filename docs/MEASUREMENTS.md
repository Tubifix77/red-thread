# What has been measured, and what turned out not to measure anything

Every threshold in this project is set from a corpus rather than from taste, which means a lot of
candidate measures get built, tested and thrown away. This file is the record of both halves.
The refuted list is the more useful one: it is what stops the same afternoon being spent twice.

Corpus as of 30 August 2026: 13 completed books, 325 scenes, 307,060 words, `qwen3:8b` in every
role. Reference band is three cold single scenes from `gemma3:12b`, `phi4:14b` and `qwen3:8b`
with no orchestration, in `docs/evidence`.

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
| beats naming a spoken act | r = +0.672 with dialogue in the prose | the planner prompt |

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

**Within-scene gesture variety.** Distinct gesture pairs over total gestures sits at ~1.0 across
four books. Gestures are already varied *inside* a scene; the repetition is between scenes, which
is why `manuscript_gestures` exists and `check_gesture_density` cannot see it.

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

`uniform_scene_length` is blind the same way and more obviously: it fires only when every scene
in a plan carries an identical word target, and `schedule.word_targets` varies them by seed — ten
scenes come back with eight distinct values. Zero of 28 plans are uniform. It can only ever
confirm the scheduler.

**Two are untested rather than blind**: `cohesion_cut` and `missed_deadline`. These have unit
tests and no live instance in 373 scenes, so nothing is known about their false-positive rate on
real prose. Not broken, not exercised.

### The rule this suggests

**A check over a field the scheduler constructs can only ever confirm the scheduler.** Four
checks in this project are quiet for that reason — subplot independence, state legality, midpoint
stall, uniform scene length — and all four read as coverage in an audit that lists them. They are
worth keeping for hand-authored plans, where the property is not guaranteed, and worth discounting
entirely when reading a generated one.

The corollary is the uncomfortable half: every property `schedule.py` guarantees is a property
nothing verifies in the prose. Threads reach their terminal states because the schedule says so.
Whether the *book* earns them is not checked anywhere, and `midpoint_stall` is the check that
looks like it does.

The distinction matters when reading a green suite. A check that is quiet because the gate
upstream of it works is doing its job; a check that is quiet because nothing has ever tested it
is an unknown wearing the same colour.

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
