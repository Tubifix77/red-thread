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
that does not work. Running every check over all 467 committed scenes turns that principle on the
suite itself: **20 of 48 violation kinds have never fired once**, and the reasons divide three
ways.

- **Blocking kinds are absent from committed prose by construction.** `pov_person`,
  `somatic_emotion`, `forbidden_phrase`, `style_leak`, `format`, `truncated_scene`,
  `length_runaway`, `seam` — every one either blocks a commit or is repaired before it. Measuring
  them on committed scenes measures the survivors, and their silence is the gate working.
- **Four test a property something upstream already guarantees.** Subplot independence, midpoint
  stall, uniform scene length and somatic. `schedule.py` assigns which scene moves which thread,
  so no thread stalls in a middle third and no plan has uniform word targets; the brief tells the
  writer "at most one somatic beat" and it complies. These read as coverage in an audit that lists
  them and provide none.
- **Two are simply untested by any run.** `cohesion_cut` and `missed_deadline` have unit tests and
  no live instance in 467 scenes, so nothing is known about their false-positive rate on real
  prose.

The mirror matters too. Five kinds fire on more than half of all scenes and are carried into the
commit almost every time — `repetition` at 94%, `tell_thematic_gloss` at 84%, `tell_summarised` at
76%. A constant is as uninformative as a silence, and two of those cost a model call per scene.

Full tables in [MEASUREMENTS.md](MEASUREMENTS.md).
