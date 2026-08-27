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
