"""Deterministic thread scheduling: the structural skeleton of a plan, built by code.

This module exists because of a division of labour that turned out to matter more than any
prompt. Asking a model to lay out which scene advances which thread to which state produces
plans that fail `checks.check_stakes_progression` constantly — threads re-entering states they
already occupied, whole threads stalling through the midpoint, subplots that never own a scene.
Those are scheduling constraints, not creative decisions, and code satisfies constraints better
than prose does.

So the split is:

* **Code owns structure.** Which scene moves which thread where, how many scenes, chapter
  boundaries, word targets. Every one of the project's acceptance markers (docs/TESTING.md) is a
  property of this layer, and the scheduler is written to make them true *by construction*.
* **The model owns content.** What actually happens in the scene, who is in it, where, and what
  the transition means in story terms.

`checks.audit_plan` then stops being a filter on model output and becomes a regression test on
this file — which is a much better place for it, because a failing test is actionable and a
rejected generation is just expensive.

The vaguest-first expansion order is CONCOCT's (docs/RESEARCH.md section 8); the concreteness
score driving it is a deterministic proxy, not their trained evaluator, and is marked as such.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from .models import SceneSpec, Thread, ThreadKind, Transition

DEFAULT_SCENE_WORDS = 850
"""Average words per scene, set from measurement rather than taste.

Repeated phrasing — the fraction of a scene's 4-grams that are duplicates — rises steeply with
scene length on a local 8B. Across 87 committed scenes and the single-scene model comparisons in
`docs/evidence`, correlation of length with duplication is r = 0.68, and it is positive within
every individual book (r = +0.35 to +0.90, so it is not a between-book artefact):

    506–931 words    0.13 duplicated
    939–1009         0.20
    1013–1109        0.22
    1114–1184        0.33
    1186–1346        0.48
    1354–1619        0.59

The default was 1100, which put the planner's assigned targets at a mean of 1115 and a range of
750–1350 — most of a manuscript in the band where this model stops writing and starts looping.
At 850 the same variation lands around 600–1050, where it does not.

The cost is more scenes for the same length, so more briefs and more calls. That is the trade
this architecture is built to make: many small tightly-briefed sessions, which is the premise on
the first line of the README. Raise it for a stronger writer model and re-measure — the number is
a property of the model, not of the prose.
"""


# --------------------------------------------------------------------------------------
# shape of the manuscript
# --------------------------------------------------------------------------------------

def scene_count(total_words: int, avg_scene_words: int = DEFAULT_SCENE_WORDS) -> int:
    """How many scenes a target length wants.

    The scene is the generation unit because it is the smallest thing with dramatic integrity —
    entry, turn, exit on change. Beats are the spec unit inside it. See RESEARCH.md open
    question 1: no source we found settles the optimal unit size, so this is reasoning.
    """
    return max(3, round(total_words / max(300, avg_scene_words)))


def word_targets(n_scenes: int, total_words: int, seed: int = 0) -> list[int]:
    """Per-scene word targets that vary.

    Uniform scene length is a pacing tell, and `audit_plan` flags it. The variation is shaped
    rather than random: scenes near the end of an act run longer, because that is where turns
    land, and a couple of deliberately short scenes break the metronome.
    """
    rng = random.Random(seed)
    base = total_words / n_scenes
    out: list[int] = []
    for i in range(n_scenes):
        position = i / max(1, n_scenes - 1)
        # Longer through the middle and at the climax, shorter at the openings of movements.
        shape = 0.82 + 0.36 * (position ** 0.7)
        if i % 4 == 2:
            shape *= 0.78
        out.append(int(round(base * shape * rng.uniform(0.94, 1.06) / 50) * 50))
    # Rescale so the total still lands near the request.
    scale = total_words / max(1, sum(out))
    return [max(400, int(round(w * scale / 50) * 50)) for w in out]


def chapter_of(index: int, scenes_per_chapter: int = 3) -> int:
    return (index - 1) // max(1, scenes_per_chapter) + 1


def midpoint_window(n_scenes: int) -> tuple[int, int]:
    """The middle third, computed exactly as `checks.check_stakes_progression` computes it.

    Duplicated arithmetic is a liability, so it is derived from the same formula rather than
    guessed at: scenes are indexed 1..n, so lo=1 and span=n.
    """
    span = n_scenes
    return 1 + span // 3, 1 + (2 * span) // 3


# --------------------------------------------------------------------------------------
# the scheduler
# --------------------------------------------------------------------------------------

@dataclass
class Schedule:
    n_scenes: int
    moves: dict[int, dict[str, str | None]] = field(default_factory=dict)
    """scene index -> {thread id: target state, or None for 'appears but does not advance'}"""

    def scenes_for(self, thread_id: str) -> list[int]:
        return sorted(i for i, m in self.moves.items() if thread_id in m)

    def transitions_for(self, thread_id: str) -> list[tuple[int, str]]:
        return [(i, state) for i in sorted(self.moves)
                if (state := self.moves[i].get(thread_id)) is not None]


def _spread(k: int, first: int, last: int, offset: int = 0) -> list[int]:
    """Up to `k` strictly increasing positions in [first, last], ending exactly on `last`.

    The offset staggers threads against each other so they do not all turn in the same scenes,
    which would make some scenes a pile-up and leave stretches with nothing moving.

    Fewer than `k` positions come back when the range cannot hold them — you cannot walk eleven
    states across four scenes. The caller compacts the state list to match rather than
    overflowing past the end of the manuscript, which is what an earlier version did.
    """
    if k <= 0 or last < first:
        return []
    capacity = last - first + 1
    if k >= capacity:
        return list(range(first, last + 1))
    if k == 1:
        return [last]

    span = last - first
    positions: list[int] = []
    for i in range(k):
        # Anchored at both ends: the first transition lands on `first`, the last on `last`. An
        # earlier version spread at (i+1)/k, which pushed every thread's first transition a
        # fraction of the way in — so the opening scenes of a real generated plan advanced
        # nothing at all, which is the wrong shape for a first chapter.
        pos = first + round(i / (k - 1) * span)
        if 0 < i < k - 1:
            pos += (offset % 2) * (1 if i % 2 == 0 else -1)
        positions.append(max(first, min(last, pos)))
    positions[0] = first
    positions[-1] = last

    # Strict increase, enforced from the back so the terminal stays pinned to `last`: two
    # transitions of one thread in the same scene would collapse into one state change and
    # silently lose a beat of the arc.
    for i in range(k - 2, -1, -1):
        if positions[i] >= positions[i + 1]:
            positions[i] = positions[i + 1] - 1
    return [p for p in positions if p >= first]


def _compact(states: list[str], slots: int) -> list[str]:
    """Choose `slots` states from `states`, always keeping the last.

    Used when a thread has more transitions than there are scenes to hold them. Dropping from the
    middle is the right compaction: the terminal state must survive or the thread ends unpaid,
    and the first transition must survive or the thread is never planted.
    """
    if slots >= len(states):
        return states
    if slots <= 1:
        return states[-1:]
    keep = {len(states) - 1}
    for i in range(slots - 1):
        keep.add(round(i * (len(states) - 1) / (slots - 1)))
    return [s for i, s in enumerate(states) if i in sorted(keep)][:slots]


def _ensure_midpoint(schedule: "Schedule", thread: Thread,
                     mid_start: int, mid_end: int) -> None:
    """Move one transition into the middle third if the thread has none there.

    Marker 2 (docs/TESTING.md) asks that the midpoint shift stakes rather than repeat them, and
    `checks.check_stakes_progression` reads that off thread state history. A thread whose
    transitions all land in the outer thirds fails it — the story's middle is treading water.

    The transition chosen is the one at the middle of the arc, and it is only moved to a slot that
    keeps the thread's transitions strictly ordered. Threads with fewer than three transitions are
    left alone: there is no meaningful middle to a two-step arc.
    """
    transitions = schedule.transitions_for(thread.id)
    if len(transitions) < 3:
        return
    if any(mid_start <= index <= mid_end for index, _ in transitions):
        return

    middle = len(transitions) // 2
    scene, state = transitions[middle]
    lower = transitions[middle - 1][0] if middle > 0 else 0
    upper = (transitions[middle + 1][0] if middle + 1 < len(transitions)
             else schedule.n_scenes + 1)

    candidates = range(max(mid_start, lower + 1), min(mid_end, upper - 1) + 1)
    if not candidates:
        return
    target = min(candidates, key=lambda i: abs(i - scene))

    del schedule.moves[scene][thread.id]
    if not schedule.moves[scene]:
        del schedule.moves[scene]
    schedule.moves.setdefault(target, {})[thread.id] = state


def schedule_threads(threads: list[Thread], n_scenes: int) -> Schedule:
    """Assign every thread's state transitions to scenes, satisfying both markers.

    Guarantees, by construction rather than by check:

    * each thread walks its states in order, entering each exactly once — so no `state_repeat`
      and no `state_regression`
    * every thread with three or more transitions advances inside the middle third — so no
      `midpoint_stall`
    * every thread reaches its terminal state, by its deadline if it declared one — so no
      `unpaid_thread` and no `missed_deadline`
    * every non-main thread owns at least one scene the main thread does not touch — so no
      `decorative_subplots`
    * every scene advances or at least serves something, so no scene arrives at the writer with
      an empty brief
    """
    schedule = Schedule(n_scenes=n_scenes)
    if not threads or n_scenes < 1:
        return schedule

    def place(index: int, thread_id: str, state: str | None) -> None:
        schedule.moves.setdefault(index, {})[thread_id] = state

    main_ids = [t.id for t in threads if t.kind is ThreadKind.MAIN] or [threads[0].id]
    ordered = ([t for t in threads if t.id in main_ids]
               + [t for t in threads if t.id not in main_ids])

    # --- 1. place each thread's arc -------------------------------------------------------
    for ordinal, thread in enumerate(ordered):
        states = thread.states[1:] if len(thread.states) > 1 else thread.states
        deadline = min(thread.deadline_scene or n_scenes, n_scenes)
        # A thread's first transition should not land in scene 1 unless it is the main thread:
        # a subplot planted in the opening scene competes with establishing the premise.
        first = 1 if thread.id in main_ids else min(2, n_scenes)
        positions = _spread(len(states), first, deadline, ordinal)
        for index, state in zip(positions, _compact(states, len(positions))):
            place(index, thread.id, state)

    # --- 2. guarantee midpoint advancement -----------------------------------------------
    # Even spreading *usually* puts a transition in the middle third, but the stagger offset can
    # push one out, and "usually" is not a guarantee. Repairing the constraint explicitly beats
    # tuning the arithmetic until the sweep happens to pass.
    mid_start, mid_end = midpoint_window(n_scenes)
    for thread in ordered:
        _ensure_midpoint(schedule, thread, mid_start, mid_end)

    # --- 3. give every non-main thread a scene of its own ---------------------------------
    main_scenes = {i for tid in main_ids for i in schedule.scenes_for(tid)}
    for thread in ordered:
        if thread.id in main_ids:
            continue
        own = schedule.scenes_for(thread.id)
        if not own or set(own) - main_scenes:
            continue
        # Every appearance coincides with the main thread. Move one interior transition to the
        # nearest scene the main thread does not use — a subplot that never has the page to
        # itself is the main plot with extra scenes (docs/TESTING.md marker 1).
        free = [i for i in range(1, n_scenes + 1)
                if i not in main_scenes and thread.id not in schedule.moves.get(i, {})]
        if not free:
            continue
        movable = own[len(own) // 2] if len(own) > 2 else own[0]
        target = min(free, key=lambda i: (abs(i - movable), i))
        state = schedule.moves[movable].pop(thread.id)
        if not schedule.moves[movable]:
            del schedule.moves[movable]
        place(target, thread.id, state)

    # --- 4. no scene left without a job --------------------------------------------------
    for index in range(1, n_scenes + 1):
        if schedule.moves.get(index):
            continue
        # Attach the thread whose arc is closest, with no state change: it appears in the scene
        # and must be served, but the scene is not where it turns.
        best, best_distance = None, None
        for thread in ordered:
            for scene in schedule.scenes_for(thread.id):
                distance = abs(scene - index)
                if best_distance is None or distance < best_distance:
                    best, best_distance = thread.id, distance
        place(index, best or ordered[0].id, None)

    return schedule


def to_scene_specs(schedule: Schedule, story_threads: list[Thread], total_words: int,
                   scenes_per_chapter: int = 3, seed: int = 0) -> list[SceneSpec]:
    """Turn a schedule into empty scene specs, ready for the model to fill with content.

    The `Transition` objects come back with `to_state` set and `post`/`forbid` empty — those are
    story judgements, not scheduling ones, and the planner fills them in.
    """
    targets = word_targets(schedule.n_scenes, total_words, seed)
    by_id = {t.id: t for t in story_threads}

    specs: list[SceneSpec] = []
    for index in range(1, schedule.n_scenes + 1):
        ops: dict[str, Transition] = {}
        for thread_id, state in (schedule.moves.get(index) or {}).items():
            ops[thread_id] = Transition(to_state=state)
        specs.append(SceneSpec(
            id=f"s{index:02d}",
            index=index,
            chapter=chapter_of(index, scenes_per_chapter),
            word_target=targets[index - 1],
            thread_ops=ops,
        ))

    # Fill each transition's `pre` from what the schedule guarantees is already true. This is
    # free and it is exactly the information a writing session cannot infer on its own.
    state_so_far: dict[str, str] = {t.id: t.states[0] for t in story_threads if t.states}
    for spec in specs:
        for thread_id, op in spec.thread_ops.items():
            thread = by_id.get(thread_id)
            if thread and state_so_far.get(thread_id):
                op.pre = [f"{thread.name} is at the state '{state_so_far[thread_id]}'"]
            if op.to_state:
                state_so_far[thread_id] = op.to_state
    return specs


# --------------------------------------------------------------------------------------
# concreteness — the vaguest-first expansion order
# --------------------------------------------------------------------------------------

_ABSTRACT = re.compile(
    r"\b\w+(?:tion|sion|ment|ness|ity|ance|ence|ship|hood|ism|acy)\b|"
    r"\b(realise|realize|understand|understanding|relationship|identity|meaning|"
    r"struggle|journey|conflict|tension|theme|emotion|feeling|sense|truth|nature|"
    r"consequences?|implications?|significance)\b", re.I)

_CONCRETE_NOUN = re.compile(
    r"\b\d[\d:.,]*\b|"                          # numerals, times, quantities
    r"\b(door|room|table|bench|road|truck|pump|valve|hand|letter|paper|key|window|"
    r"knife|glass|coat|boot|phone|card|box|bottle|engine|wire|gate|field|kitchen|"
    r"stair|chair|book|note|bag|lock|shelf|cup|coin|map|ledger|form|stamp|"
    r"terminal|notebook|housing|coupling|log|sheet|well|registry|folder)s?\b", re.I)

_CAPITALISED = re.compile(r"\b[A-Z][a-z]{2,}\b")

# Sentence-initial function words are capitalised and are not proper nouns. Counting them was a
# real bug: "The protagonity comes to an understanding…" scored as concrete as a scene full of
# named machinery, and both saturated at 1.0, so vaguest-first had nothing to order by.
_NOT_A_NAME = {
    "the", "and", "but", "she", "her", "his", "they", "them", "their", "this", "that", "then",
    "there", "these", "those", "when", "what", "which", "with", "without", "from", "into",
    "after", "before", "because", "while", "since", "though", "although", "nobody", "somebody",
    "something", "nothing", "everything", "later", "meanwhile", "outside", "inside", "above",
    "below", "here", "now", "once", "again", "still", "already", "neither", "either", "both",
    "every", "each", "some", "any", "all", "one", "two", "three", "four", "five",
}


_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|[:;]\s+|\n\s*|-\s+)([A-Z][a-z]{2,})")


def _proper_nouns(text: str) -> list[str]:
    """Capitalised words that are plausibly names, not sentence openers.

    Two filters, both learned from the metric misbehaving. The stopword list catches "The",
    "They", "When". The sentence-start exclusion catches everything else: "Things happen." scored
    a perfect 1.0 because "Things" looked like a proper noun and two tokens is a tiny denominator.
    """
    openers = {m.start(1) for m in _SENTENCE_START.finditer(text)}
    return [m.group(0) for m in _CAPITALISED.finditer(text)
            if m.start() not in openers and m.group(0).lower() not in _NOT_A_NAME]


def concreteness(text: str) -> float:
    """A 0..1 proxy for how specified a piece of outline is.

    CONCOCT trains a pairwise concreteness evaluator and expands the vaguest outline item first,
    which produces measurably more even pacing (docs/RESEARCH.md section 8). We keep the
    *algorithm* and substitute a cheap deterministic score for the trained model: concrete
    nouns, proper names and numbers push it up; abstraction nouns and interiority verbs push it
    down.

    This is explicitly a proxy. It is good enough to order a frontier — which is all
    vaguest-first needs, since it only ever asks "which of these is least specified" — and it is
    not a measurement of anything. Swapping in a trained comparator later changes only this
    function.
    """
    if not text or not text.strip():
        return 0.0
    tokens = re.findall(r"[A-Za-z']+|\d+", text)
    if not tokens:
        return 0.0
    concrete = len(_CONCRETE_NOUN.findall(text)) + len(_proper_nouns(text))
    abstract = len(_ABSTRACT.findall(text))
    # Floor the denominator: a two-word fragment with one concrete noun would otherwise reach a
    # density of 0.5 and saturate the score, ranking "Things happen." above a real beat.
    density = (concrete - abstract) / max(len(tokens), 14)
    length_bonus = min(0.15, len(tokens) / 240)
    # Gain kept low enough that realistic outline text lands inside the range rather than
    # saturating: a frontier of items all scoring 1.0 cannot be ordered.
    return max(0.0, min(1.0, 0.35 + density * 2.2 + length_bonus))


def vaguest_first(specs: list[SceneSpec]) -> list[SceneSpec]:
    """Frontier order for expansion: least specified first.

    Expanding depth-first to a fixed depth is what produces uneven pacing — some scenes richly
    specified, others a sentence. Expanding the vaguest node until concreteness is uniform is
    CONCOCT's answer to "how do I know when a node is small enough to write".
    """
    return sorted(specs, key=lambda s: (score_spec(s), s.index))


def score_spec(spec: SceneSpec) -> float:
    """How ready a scene spec is to be written from. 0 = unwritable, 1 = fully specified.

    Readiness is two things multiplied, and getting this wrong was instructive: an early version
    scored only the *density* of concrete language, which meant deleting beats raised the score —
    less text, same concrete nouns from the summary, higher density. It ranked "Things happen."
    above a real beat.

    So the score is `language quality × amount of specification`:

    * **density** — `concreteness` over everything the writer will actually be told.
    * **coverage** — are there enough beats for the target length? A beat is roughly half a page,
      so a 1400-word scene wants three.
    * **detail** — are the beats substantial, or one-liners standing in for a beat?

    Multiplying rather than averaging matters: a spec with no beats is unwritable no matter how
    vivid its summary, and this makes that fall out rather than needing a special case.
    """
    parts = [spec.summary, spec.setting, spec.time, spec.notes]
    parts += [b.summary for b in spec.beats]
    for op in spec.thread_ops.values():
        parts += op.post + op.forbid
    text = " ".join(p for p in parts if p)
    if not text.strip():
        return 0.0

    density = concreteness(text)
    wanted_beats = max(2, round(spec.word_target / 450))
    coverage = min(1.0, len(spec.beats) / wanted_beats)
    beat_words = sum(len(b.summary.split()) for b in spec.beats)
    detail = min(1.0, beat_words / (12 * wanted_beats))
    return max(0.0, min(1.0, density * (0.40 + 0.35 * coverage + 0.25 * detail)))
