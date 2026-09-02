# Test protocol

Two acceptance markers govern this project. Both are structural failures, both are checkable
before a word of prose is generated, and both fall out of the thread state machine for free.

The premises they are tested against are kept private — publishing a story premise gives it away —
but nothing in the protocol depends on them. Drop your own into `examples/` and the checks apply
unchanged.

---

## Marker 1 — distinct sub-arcs, not famous three-act beats

> Does the plan invent distinct sub-arcs, or default to famous three-act beats — shoehorning in a
> "mentor death" scene?

This is the same failure StoryScope measures as the largest structural gap between AI and human
fiction: no subplots in 79% of AI stories against 57% of human ones
([RESEARCH.md §6](RESEARCH.md)). A plan can look subplot-rich while containing none, because a
"subplot" that only ever advances the main plot is the main plot with extra scenes.

Checked by `checks.check_subplot_independence`:

- at least one non-`main` thread must exist, and
- at least one thread must own scenes the main thread does not touch.

A thread whose every appearance coincides with a main-thread beat is reported as a decorative
subplot. Stock-beat detection (the mentor death, the training montage, the darkest hour before the
final push) is a plan-level LLM probe rather than a regex, because the beat can be present without
any of its vocabulary.

## Marker 2 — the midpoint must shift stakes, not repeat them

> How does it manage the mid-point complication? Weak models repeat early conflict instead of
> shifting the narrative stakes.

This one turns out to be decidable from thread state history alone, which is the strongest single
argument for making thread state a machine rather than a description.

Checked by `checks.check_stakes_progression`:

- **repeat** — a thread asked to enter a state it has already occupied. The story is circling.
- **regression** — a thread moving backwards through its states for no recorded reason.
- **midpoint stall** — no state index increases across the middle third. If that holds for most
  threads, the manuscript's middle is treading water.

Plus the two hygiene failures that only a state machine can see: an **unpaid thread** that never
reaches its terminal state, and a **missed deadline** on a thread that declared one.

No model call and no reading required.

---

## The other half of the audit: rules a judge can answer

The two markers are about whether the *story* is shaped right. Seven more plan checks exist for a
different reason, and they came entirely from running a book: a malformed **rule** produces a scene
that cannot be written and cannot be repaired. The prose is fine; the requirement is broken. No
scene-level check can see this, because nothing is wrong with the scene.

| check | catches | what it cost before it existed |
|---|---|---|
| `check_prohibition_phrasing` | a `forbid` phrased as a negation | "the decision is not finalized" reads as a demand for the reveal; 50 of one 27-scene plan's rules were written this way, and the scene obeying the plan was the one blocked |
| `check_post_is_an_event` | a `post` naming a thread state, or naming an absence | "The Allegiance reaches 'reoriented'" asks the judge about bookkeeping the prose cannot contain; "neither resolved nor abandoned" and "left unspoken" can never be evidenced, so they are reported missed however the scene goes |
| `check_stale_prohibitions` | "do not reveal X" after the schedule discloses X | a scene held back for revealing an enclave the plan itself unsealed three scenes earlier |
| `check_beats_are_intent` | a beat written as finished prose | the writer copies it back and `check_brief_leak` is right to flag the copy; one scene had ten such beats and never committed at any repair budget |
| `check_spec_self_consistency` | the plan using a phrase it forbids | every brief is built from this text, so a banned word here is injected into all of them |
| `check_concealment` | a thread with nothing withheld | tension is downstream of hidden information |
| `check_cast_names` | names measured as over-represented in machine fiction | `check_slop` must exempt character names, so this is where that exemption is paid for |

Where the intent is unambiguous the plan is repaired rather than merely reported — a negated
prohibition is inverted into the event it forbids, and prose beats are rewritten into intent — but
the check still fires, so the next plan is written correctly instead of repaired forever.

The general rule these share is worth stating on its own: **a constraint the judge cannot answer is
worse than no constraint at all.** An absent rule costs you the thing it would have prevented. An
unanswerable rule costs you the scene, the repair budget, and — because `write_all` halts at the
first rejection — the rest of the book.

## What a fixture suite cannot test

Every check in this project is tested by injecting the defect it exists to find, and that is worth
doing. It is also not sufficient, for a reason that took a second manuscript to surface.

The fixtures in `tests/fakes.py` are prose written to pass the checks. One comment in that file
says so directly: the fixture closings are kept distinct *so `check_seam` does not fire on the
fixture's own filler*. Test data shaped around a failure mode cannot detect that failure mode. The
first manuscript did not help either — it was a clean run, so almost no check fired, so almost no
**repair path** ever executed. Every defect the second book found lives in a repair path.

Two practices came out of that, and both are cheap:

1. **Assert structural properties of the checks, not only their behaviour.**
   `tests/test_repair_coverage.py` parses `checks.py` with `ast`, enumerates every BLOCKER/MAJOR
   kind the scene-level checks can emit, and fails if any of them has no repair that can reach it.
   That assertion is fixture-independent, and it caught a real gap on its first run.

2. **Before calling a pipeline change done, write at least two consecutive scenes on a real model
   against a plan that was not tuned to pass.** Read the held-back scene's `scenes/NNNN.json` for
   the actual violations rather than inferring from the progress line. A green suite tells you the
   machinery composes; only this tells you the repairs converge.

---

## Designing a premise that actually tests something

Choose premises **adjacent to** shapes the models have seen thousands of times without being those
shapes. The interesting failures are the ones where a planner quietly drifts back toward the
familiar version — and you only see that drift if the brief was one step away from it to begin
with.

Three axes worth covering across a test set, because they break different parts of the system:

1. **A dilemma with no clean win.** The core conflict must be a choice whose terminal states are
   both costly. Model it as a thread whose final state is `chosen` rather than `resolved`. A plan
   in which the protagonist is straightforwardly right has failed the premise regardless of prose
   quality. Watch for absent antagonists being resurrected as characters: a system is harder to
   write than a villain.

2. **State rewritten by a third party.** A world that changes on its own — a door that was open is
   locked, a route that worked in scene four is gone by scene nine — is what stresses the ledger.
   It demands `STATE` facts that supersede correctly and it makes `conflict_candidates` earn its
   keep. Add two factions and it stresses character-scoped `KNOWLEDGE` too: the classic failure is
   a rival reacting to information nobody told them.

3. **A motivation reversal across the midpoint.** The protagonist's first-half goal is the thing
   they must abandon in the second. This is the hardest case for a hierarchical planner, which is
   inclined to produce escalating obstacles toward a fixed objective. Two failure modes to watch:
   the reveal landing early (mark it in `Thread.concealment`, and check that the forecastability
   probe shows *low* predictability across the midpoint), and the reversal happening entirely
   inside the discovery scene — which is a plot twist, not a character change. Require the
   allegiance thread to pass through a non-collapsible intermediate state: knowing, and not yet
   acting.

## World-rule discipline

Keep `world_rules` short and mechanical. Every added rule is a chance for a later scene to
contradict an earlier one, and a rule invented in scene twelve is not a rule — it is a
contradiction with a good excuse. Let the ledger carry everything else as facts the prose
established.

---

## Running it

From a premise of your own:

```bash
python -m redthread plan my-premise.md --out runs/mystory --words 30000 --local qwen3:8b
```

Or from the hand-authored reference plan, which needs no model at all:

```bash
python examples/build_inherited_glitch.py runs/mystory
```

```bash
python -m redthread audit runs/mystory
```

```bash
python -m redthread write runs/mystory --local qwen3:8b
```

`audit` sits deliberately between planning and writing. Both markers are plan-level failures, and
generating 90,000 words before discovering that the midpoint repeats the opening is the expensive
way to learn it.

## The suite runs before a push

`.githooks/pre-push` runs `pytest` and refuses the push if it fails. Enable it once per clone:

```bash
git config core.hooksPath .githooks
```

It exists because a red suite reached the remote twice on 30 August, both times from the same
shape of command:

```bash
python -m pytest -q | tail -3 && git commit -m "..." && git push
```

A pipeline takes the exit status of its **last** element, and `tail` always succeeds. The suite
was red, the `&&` did not care, and the summary line scrolled past unread inside a longer chain.
Neither time was the mistake noticing a failure and pushing anyway; both times the failure was
invisible to the command that was supposed to catch it.

`--no-verify` bypasses the hook, for when a red push is deliberate.

## A check that never fires, and a check that always does

`tests/test_checks.py` opens by saying a check that never fires is indistinguishable from a check
that does not work. Running every check over all 562 committed scenes turns that principle on the
suite itself: **20 of 48 violation kinds have never fired once**, and the reasons divide three
ways.

*That count was taken over 562 scenes. The corpus is now 1,631, and at least one of the twenty —
`cohesion_cut` — has since fired, so **20 is an upper bound and has not been recomputed.** It is
left as measured rather than rebased, because the kind universe spans scene checks and plan checks
and only the scene half is recoverable from `runs/*/scenes/*.json`; a quick recount over the wrong
denominator is how the last three retracted numbers happened.*

- **Blocking kinds are absent from committed prose by construction.** `pov_person`,
  `somatic_emotion`, `forbidden_phrase`, `style_leak`, `format`, `truncated_scene`,
  `length_runaway`, `seam` — every one either blocks a commit or is repaired before it. Measuring
  them on committed scenes measures the survivors, and their silence is the gate working.
- **Seven test a property something upstream already guarantees.** Subplot independence, the
  three state-legality kinds, midpoint stall, uniform scene length, and somatic. `schedule.py`
  assigns which scene moves which thread, so no thread stalls in a middle third and no plan has
  uniform word targets; the brief tells the writer "at most one somatic beat" and it complies.
  These read as coverage in an audit that lists them and provide none.

  They are now named in code — `checks.SCHEDULER_GUARANTEED` and `checks.INSTRUCTION_CONFIRMING`,
  split because the two guarantees fail differently: the scheduler's holds because code makes it
  hold, and the brief's holds because a model is complying, which could stop being true at any
  time without anything here changing. `redthread audit` prints both beside its own result, and
  `tests/test_rule.py` asserts every named kind is one the codebase can still emit.
- **One is still untested by any run.** `missed_deadline` has unit tests and **no live instance in
  1,631 committed scenes**, so nothing is known about its false-positive rate on real prose.
- **`cohesion_cut` has since fired, 27 times, and what it found is a property of the plan.** All 27
  are `minor`, and they cluster on *the same scene in every run of a plan* — scene 48 of *The Debt
  of Years* fires in every one of its fourteen runs, because the plan puts a full cast cut there.
  So its rate is 1.7% of scenes, its detection is correct, and it is reporting on **the plan rather than the
  prose**: rule IV's shape without being rule IV's case, since nothing guarantees the field, but a
  check whose firing is fixed by the plan tells you nothing about the writing that run produced.

The mirror matters too. Four kinds fire on more than half of all scenes and are carried into the
commit almost every time — `repetition` at 95%, `tell_thematic_gloss` at 78%, `tell_summarised` at
70%, `slop` at 57%. A constant is as uninformative as a silence, and two of those cost a model call
per scene.

*Rates recomputed 2 September 2026 over all 1,631 committed scene records. They were within a
few points at 562 scenes and again at 1,299, which is the only reason the earlier figures were
safe to have quoted — and the reason to keep re-deriving rather than assuming.*

Full tables in [MEASUREMENTS.md](MEASUREMENTS.md).

## Tests that check the measuring rather than the machinery

Three of the newer files do something the rest of the suite does not: they assert that this
project cannot make a claim it has not earned. They exist because every one of them caught a real
error within minutes of being written.

**`tests/test_rule.py`** walks the source tree with a regex for every `Severity.BLOCKER` and
refuses any whose source is not in `checks.BLOCKER_SOURCES` with a note on what a person could
check by hand. A blocker stops an unattended run at three in the morning, so adding one now means
writing that sentence.

It sharpened the rule twice while being written. It caught a source labelled from memory —
`no_threads` comes from `check_subplot_independence`, not `audit_plan` — and it refuted the claim
that exactly one blocker comes from a model. There are two: `llm:extract_facts` blocks as well.
That is not a counterexample but a better statement of the rule, because neither refuses a scene
for **how it reads** — one answers a binary question about two ledger rows code selected and
quotes both, and the other fires because a call returned nothing parseable.

**`tests/test_replicate.py`** asserts that a difference exactly the size of a measure's own noise
floor is never reported as a result. The first floor table failed this on four measures, because
the figures had been rounded down for the write-up and the code used the rounded ones. It also
asserts the measure panel and the floor table have identical keys in both directions, so a number
cannot be reported without an error bar.

**`tests/test_sample.py`** asserts the blind stays blind: no label reaches the rendered sheet,
the key is a separate object, and the sheet mentions none of the panel's vocabulary. The person
who has to resist reading the key is the person who wrote the prose.
