"""The planner: premise in, auditable plan out.

Division of labour with `schedule.py`, which is the whole point of this module's shape:

* `schedule.py` decides **which scene moves which thread to which state** — and therefore owns
  both acceptance markers, satisfying them by construction.
* This module asks a model for **threads, cast, world, voice, and what each scene is about** —
  the judgements that are genuinely creative and that code has no business making.

The consequence is that the planner does not need a generate-audit-retry loop over structure. It
retries only when the *content* proposal is degenerate in a way code cannot repair — no subplot
proposed at all, say — and those cases are named explicitly in the retry prompt rather than
handled by resampling and hoping.

Expansion order is CONCOCT's vaguest-first (docs/RESEARCH.md section 8), and the skeleton is
fleshed out in overlapping chunks rather than one call per scene so that adjacent scenes are
proposed with each other in view — a plan whose scenes were each invented in isolation has the
seam problem before a word of prose exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import checks
from .llm import LLMError, Models, parse_json
from .models import (Beat, Character, SceneSpec, StorySpec, StyleContract, Thread, ThreadKind,
                     Transition, Violation, Severity)
from .schedule import (DEFAULT_SCENE_WORDS, scene_count, schedule_threads, score_spec,
                       to_scene_specs, vaguest_first)

JSON_ONLY = ("Reply with JSON only. No preamble, no commentary outside the JSON.")

CHUNK = 5
"""Scenes proposed per call. Small enough that the model holds them all in view, large enough
that adjacent scenes are invented together."""

# The name-like entries from data/slop_phrases.txt — given names and place names measured as
# over-represented in LLM-generated fiction (sam-paech/antislop-sampler). Told to the planner
# because `checks.check_slop` exempts character names by necessity: a protagonist called Elara
# would otherwise trip the check in every scene forever. Cheaper to not choose the name.
SLOP_NAMES = ("Elara", "Elysia", "Lyra", "Eira", "Eluned", "Elian", "Elias", "Elianore",
              "Aria", "Eitan", "Kael", "Jaxon", "Numeria", "Eldoria", "Atheria", "Zephyria",
              "Oakhaven", "Whisperwood", "Ravenswood", "Moonwhisper")


# ======================================================================================
# 1. the story: threads, cast, world, voice
# ======================================================================================

STORY_PROMPT = """You are planning a novel from a premise. Produce its structural bible — not \
an outline of events, the *machinery*: who is in it, what rules the world runs on, what \
through-lines run through it, and what the prose sounds like.

PREMISE:
{premise}

{extra}

THREADS are the most important part. A thread is a through-line with an explicit state machine, \
and the plan will be checked mechanically against these rules:

- Exactly ONE thread of kind "main".
- At least one thread of kind "subplot" that has NO CAUSAL DEPENDENCY on the main thread. It \
must be able to be resolved without the main plot happening at all. This is not decoration: \
machine-written fiction has no subplots in 79% of cases against 57% for human fiction, and a \
"subplot" that only ever serves the main plot is the main plot with extra scenes.
- 4 to 6 states per thread, in order, first state being the un-started one (e.g. "dormant"). \
State names should describe the thread's condition, not events — "suspected", "cost_named", \
"forced" rather than "she finds the letter".
- Every thread declares what is CONCEALED from the reader. Tension is downstream of hidden \
information; a thread with nothing withheld generates predictable scenes.
- Every thread declares its PAYOFF: what resolution looks like. Not "it is resolved".
- Prefer a terminal state that costs something. A thread whose ending is simply a win is the \
easiest thing to write and the least worth reading.

NAMES: do not use any of these for a character or a place. They are measured as \
over-represented in machine-written fiction, and a cast drawn from this list marks the book as \
generated before anyone reads a sentence. Names should suit the setting instead.
{slop_names}

Anything you put in "forbidden_phrases" binds YOU as well. Do not list a word and then use it in \
the premise, a thread, or a world rule — every scene brief is built from that text, so a \
prohibited term sitting there is injected into all of them.

CONSTRAINTS STATED IN THE PREMISE ARE BINDING. If the premise says what the story must avoid — a \
trope, a comparison, a kind of antagonist — honour it, and put the vocabulary of the thing it must \
avoid into "forbidden_phrases". A premise calling a system "adaptive" does not license a sentient \
one. Drifting toward the familiar version of a premise is the specific failure this plan is \
checked against, so read the premise for what it rules out as carefully as for what it asks for.

STYLE: the samples must be NEW sentences you write in the target register, demonstrating rhythm \
and diction. Do not quote the premise, and DO NOT put any character or place name from this \
story in them — a sample that reads like a line from the book gets absorbed into the prose \
verbatim; write them about something unrelated (weather on a road, a tool being cleaned, a queue \
at a counter) in the book's voice. Three sentences of varied length. Give the voice of each \
character as how they speak and evade, not as an adjective.

{json_only}
Schema:
{{"title": "...",
  "premise": "one or two sentences, the premise sharpened",
  "world_rules": ["concrete and mechanical; 3-6 of them; short"],
  "characters": [{{"id": "lowercase_short", "name": "Full Name",
                   "description": "age, role, what they want, one concrete habit",
                   "voice": "how they talk and how they deflect"}}],
  "threads": [{{"id": "T-SHORT", "name": "...", "kind": "main|subplot|relationship|mystery|thematic",
                "states": ["dormant", "...", "..."],
                "concealment": "what the reader must not yet understand",
                "concealment_ends_at_state": "the state from your list whose arrival DISCLOSES it",
                "payoff": "what resolution looks like, and what it costs"}}],
  "style": {{"pov": "third limited", "tense": "past",
             "samples": ["...", "...", "..."],
             "forbidden_phrases": ["phrases this book must never use"],
             "notes": "register, and how emotion is conveyed"}}}}"""


def _slug(value: str, prefix: str = "T") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "")).strip("-").upper()
    return cleaned or prefix


def _character_id(value: str, name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", str(value or name or "c").lower()).strip("_")
    base = base or "c"
    candidate, n = base, 2
    while candidate in taken:
        candidate, n = f"{base}{n}", n + 1
    return candidate


def parse_story(data: dict) -> StorySpec:
    """Build a StorySpec from a model proposal, repairing what code can repair.

    Mechanical problems get fixed here rather than sent back for a retry: a missing `main` kind or
    a two-state thread costs a round trip to re-ask and nothing to correct. Only genuinely
    creative gaps — no independent subplot exists at all — are worth a retry, and
    `story_problems` reports those separately.
    """
    taken: set[str] = set()
    characters: list[Character] = []
    for row in data.get("characters") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        cid = _character_id(row.get("id"), name, taken)
        taken.add(cid)
        characters.append(Character(id=cid, name=name,
                                    description=str(row.get("description") or "").strip(),
                                    voice=str(row.get("voice") or "").strip()))

    threads: list[Thread] = []
    thread_ids: set[str] = set()
    for row in data.get("threads") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        tid = _slug(row.get("id") or name)
        while tid in thread_ids:
            tid += "-B"
        thread_ids.add(tid)

        try:
            kind = ThreadKind(str(row.get("kind", "subplot")).strip().lower())
        except ValueError:
            kind = ThreadKind.SUBPLOT

        states = [str(s).strip() for s in (row.get("states") or []) if str(s).strip()]
        # De-duplicate while preserving order: a repeated state would make the arc re-enter a
        # state it already occupied, which is precisely what marker 2 forbids.
        seen: set[str] = set()
        states = [s for s in states if not (s in seen or seen.add(s))]
        if len(states) < 2:
            states = ["dormant", "resolved"]

        reveal_state = str(row.get("concealment_ends_at_state") or "").strip() or None
        if reveal_state and reveal_state not in states:
            reveal_state = None
        threads.append(Thread(id=tid, name=name, kind=kind, states=states,
                              concealment=str(row.get("concealment") or "").strip(),
                              reveal_state=reveal_state,
                              payoff=str(row.get("payoff") or "").strip()))

    # Exactly one main thread. Code can settle this; asking again cannot do it better.
    mains = [t for t in threads if t.kind is ThreadKind.MAIN]
    if not mains and threads:
        threads[0].kind = ThreadKind.MAIN
    for extra in mains[1:]:
        extra.kind = ThreadKind.SUBPLOT

    style_raw = data.get("style") or {}
    style = StyleContract(
        pov=str(style_raw.get("pov") or "third limited").strip(),
        tense=str(style_raw.get("tense") or "past").strip(),
        samples=[str(s).strip() for s in (style_raw.get("samples") or []) if str(s).strip()],
        forbidden_phrases=[str(s).strip().lower()
                           for s in (style_raw.get("forbidden_phrases") or []) if str(s).strip()],
        notes=str(style_raw.get("notes") or "").strip(),
    )

    return StorySpec(
        title=str(data.get("title") or "Untitled").strip(),
        premise=str(data.get("premise") or "").strip(),
        world_rules=[str(r).strip() for r in (data.get("world_rules") or []) if str(r).strip()],
        characters=characters,
        threads=threads,
        style=style,
    )


def story_problems(story: StorySpec) -> list[str]:
    """Gaps a retry might actually fix, phrased as instructions rather than complaints."""
    problems: list[str] = []
    if len(story.threads) < 2:
        problems.append("Propose at least three threads. One through-line is not a structure.")
    if not [t for t in story.threads if t.kind is not ThreadKind.MAIN]:
        problems.append(
            "Every thread is the main plot. Add at least one subplot that could be resolved "
            "without the main plot happening at all.")
    if len(story.characters) < 3:
        # Was `< 2` while the message said "three", which is how a real run came back with a
        # two-hander for a premise about two competing teams and nothing objected.
        problems.append("Propose at least three characters with distinct wants.")
    missing_concealment = [t.id for t in story.threads if not t.concealment]
    if missing_concealment:
        problems.append(
            f"These threads declare nothing concealed from the reader: "
            f"{', '.join(missing_concealment)}. A thread with nothing withheld produces "
            f"predictable scenes — say what the reader must not yet understand.")
    missing_payoff = [t.id for t in story.threads if not t.payoff]
    if missing_payoff:
        problems.append(f"These threads do not say what resolution looks like: "
                        f"{', '.join(missing_payoff)}.")
    if len(story.style.samples) < 2:
        problems.append("Give at least three style samples: new sentences you write in the "
                        "target register, of varied length.")
    name_tokens = {t for c in story.characters
                   for t in re.split(r"[^a-z]+", c.name.lower()) if len(t) > 2}
    if any(name_tokens & set(re.split(r"[^a-z]+", sample.lower()))
           for sample in story.style.samples):
        # A sample naming the cast reads as a line from the book, and the writer absorbs it
        # verbatim: a real scene shared twelve 6-word runs with one. Register, not content.
        problems.append(
            "Your style samples mention story characters or places. Rewrite all samples about "
            "something unrelated to this story (weather, a tool, a queue at a counter) in the "
            "same voice — samples demonstrate register, and anything story-shaped in them ends "
            "up copied into the prose.")

    # A retry can fix these, and fixing them here is far better than catching them at audit:
    # every scene brief is built from this text, so a self-violation propagates everywhere.
    for violation in checks.check_spec_self_consistency([], story):
        problems.append(
            f'You listed "{violation.quote}" in forbidden_phrases and then used it in your own '
            f'premise, threads or world rules. Either stop using it or stop forbidding it.')
    for violation in checks.check_cast_names([], story):
        problems.append(
            f"{violation.detail} Choose a different name that suits the setting.")
    return problems


def propose_story(premise: str, models: Models, attempts: int = 3) -> StorySpec:
    """Ask for the structural bible, retrying only on gaps code cannot repair."""
    extra = ""
    last: StorySpec | None = None
    for _ in range(max(1, attempts)):
        prompt = STORY_PROMPT.format(premise=premise.strip(), extra=extra,
                                     slop_names=", ".join(SLOP_NAMES), json_only=JSON_ONLY)
        reply = models.critic.complete(prompt, max_tokens=6000, temperature=0.9,
                                       json_mode=True)
        # A parse failure must consume an attempt, not kill the run. This was the one parse in
        # the planner outside its own retry loop, and a single bad sample at temperature 0.9
        # crashed a real `plan` command straight through make_plan.
        try:
            data = parse_json(reply.text)
        except LLMError:
            extra = ("Your previous reply was not valid JSON. Return exactly the schema below, "
                     "one JSON object, nothing else.")
            continue
        if not isinstance(data, dict):
            extra = "Your previous reply was not a JSON object. Return the schema exactly."
            continue
        story = parse_story(data)
        last = story
        problems = story_problems(story)
        if not problems:
            return story
        extra = ("Your previous attempt had these problems. Fix them and keep everything else:\n"
                 + "\n".join(f"- {p}" for p in problems))
    if last is None:
        raise LLMError("the planner could not obtain a usable story proposal")
    return last


# ======================================================================================
# 2. scene content, into the scheduled skeleton
# ======================================================================================

SCENES_PROMPT = """You are filling in scenes of a novel whose structure is already fixed. \
Do not change the structure. Each scene below tells you which threads it must move and to which \
state; your job is to decide what actually happens.

THE BOOK
Title: {title}
Premise: {premise}
World rules:
{world_rules}

CAST
{cast}

THREADS
{threads}

{context}

SCENES TO FILL — the thread obligations are fixed and non-negotiable:
{scenes}

For each scene give:
- "summary": one sentence, concrete, what happens. Name things.
- "setting" and "time": specific places and specific moments, not "later" or "a room".
- "pov": the id of the character whose head we are in.
- "characters": ids of everyone present.
- "beats": 2 to 4 beats, in order. Each is roughly half a page of story and must be an event or a
  turn, not a feeling. A beat that could be summarised as "she reflects on X" is not a beat.
- "threads": for each thread id this scene must move, what the scene must BRING ABOUT ("post",
  1-3 concrete statements) and what it must NOT do ("forbid", 1-3 statements). Forbids are where
  premature reveals get prevented — use them.
  Every "forbid" entry NAMES THE EVENT THAT MUST NOT HAPPEN, as a positive statement. Write
  "Dain learns who ordered the purge", never "Dain does not learn who ordered the purge".
  A forbid containing "not", "never" or "no longer" says the opposite of what you mean and will
  be rejected: read literally, "the purpose is not revealed" forbids concealing it.

Hard rules:
- A scene that only advances the main thread must not include subplot threads it was not given.
- Where a thread has no target state in a scene, it is present but does not turn: say what it is
  owed there anyway.
- Do not have any scene explain what the story means. Dramatise.
- Do not route every outcome through the protagonist deciding and acting.

{json_only}
Schema:
{{"scenes": [{{"index": 1, "summary": "...", "setting": "...", "time": "...",
  "pov": "character_id", "characters": ["id", "id"],
  "beats": ["...", "..."],
  "threads": {{"T-ID": {{"post": ["..."], "forbid": ["..."]}}}}}}]}}"""


def _render_threads(story: StorySpec) -> str:
    lines = []
    for t in story.threads:
        lines.append(f"- {t.id} ({t.kind.value}) {t.name}")
        lines.append(f"    states: {' -> '.join(t.states)}")
        if t.concealment:
            lines.append(f"    concealed from the reader: {t.concealment}")
        if t.payoff:
            lines.append(f"    payoff: {t.payoff}")
    return "\n".join(lines)


def _render_cast(story: StorySpec) -> str:
    return "\n".join(
        f"- {c.id}: {c.name} — {c.description}" + (f" [speech: {c.voice}]" if c.voice else "")
        for c in story.characters) or "(none proposed)"


def _render_scene_slots(specs: list[SceneSpec], story: StorySpec) -> str:
    lines = []
    for spec in specs:
        obligations = []
        for tid, op in spec.thread_ops.items():
            thread = story.thread(tid)
            label = thread.name if thread else tid
            if op.to_state:
                obligations.append(f"{tid} ({label}) must reach state '{op.to_state}'")
            else:
                obligations.append(f"{tid} ({label}) is present but does not turn")
        lines.append(f"Scene {spec.index} (chapter {spec.chapter}, ~{spec.word_target} words): "
                     + "; ".join(obligations))
    return "\n".join(lines)


def _apply_scene_content(spec: SceneSpec, row: dict, story: StorySpec) -> None:
    """Write proposed content onto a spec without letting it touch the structure.

    `to_state` is never read from the model here. The scheduler owns it, and a model that
    "helpfully" reassigns a state would break the guarantee that the plan audits clean.
    """
    valid_ids = {c.id for c in story.characters}
    spec.summary = str(row.get("summary") or spec.summary).strip()
    spec.setting = str(row.get("setting") or spec.setting).strip()
    spec.time = str(row.get("time") or spec.time).strip()

    def to_id(value) -> str | None:
        # The schema asks for ids, but a model answers with names ("Dain Korr") or fragments
        # ("dain") as readily — and a real plan silently lost POV and cast on all 27 scenes
        # because unmatched values were dropped without a sound. Match ids exactly first, then
        # names by token overlap.
        value = str(value or "").strip()
        if not value:
            return None
        if value in valid_ids:
            return value
        value_tokens = {t for t in re.split(r"[^a-z]+", value.lower()) if t}
        for c in story.characters:
            name_tokens = {t for t in re.split(r"[^a-z]+", c.name.lower()) if t}
            if value.lower() == c.name.lower() or (value_tokens & name_tokens):
                return c.id
        return None

    pov = to_id(row.get("pov"))
    if pov:
        spec.pov = pov
    present = [cid for cid in (to_id(c) for c in (row.get("characters") or [])) if cid]
    present = list(dict.fromkeys(present))
    if spec.pov and spec.pov not in present:
        present.insert(0, spec.pov)
    if present:
        spec.characters = present
    elif spec.pov:
        spec.characters = [spec.pov]

    beats = [str(b).strip() for b in (row.get("beats") or []) if str(b).strip()]
    if beats:
        spec.beats = [Beat(summary=b, concreteness=0.0) for b in beats]

    for tid, payload in (row.get("threads") or {}).items():
        op = spec.thread_ops.get(tid)
        if op is None or not isinstance(payload, dict):
            continue
        post = [str(p).strip() for p in (payload.get("post") or []) if str(p).strip()]
        forbid = [str(p).strip() for p in (payload.get("forbid") or []) if str(p).strip()]
        if post:
            op.post = post[:4]
        if forbid:
            # Repair the phrasing here rather than letting it into the plan. The prompt asks for
            # positive forbids and a live 8B wrote every one of a 27-scene plan as a negation
            # anyway — "the true purpose is not revealed" — which reads as a demand for the
            # reveal. Inverting at parse time means the stored plan says what it means, so the
            # brief, the judge and the author all read the same rule.
            op.forbid = [checks.positive_prohibition(f) if checks.is_negated_prohibition(f)
                         else f for f in forbid[:4]]

    spec.concreteness = score_spec(spec)


def flesh_scenes(specs: list[SceneSpec], story: StorySpec, models: Models,
                 chunk: int = CHUNK, on_chunk=None) -> None:
    """Fill scene content in overlapping chunks, in place.

    Each call sees the summaries already settled for earlier scenes, so the plan is built forward
    from what it has already committed to rather than as a set of independently invented scenes.
    That is DOME's dynamic expansion applied at plan level (docs/RESEARCH.md section 2), and it is
    also the earliest point at which the seam problem can be attacked — before any prose exists.
    """
    ordered = sorted(specs, key=lambda s: s.index)
    for start in range(0, len(ordered), max(1, chunk)):
        window = ordered[start:start + max(1, chunk)]
        earlier = ordered[max(0, start - 3):start]
        context = ("SCENES ALREADY SETTLED (do not restate or contradict; continue from them):\n"
                   + "\n".join(f"Scene {s.index}: {s.summary}" for s in earlier if s.summary)
                   ) if earlier else "This is the opening of the book."

        prompt = SCENES_PROMPT.format(
            title=story.title, premise=story.premise,
            world_rules="\n".join(f"- {r}" for r in story.world_rules) or "(none)",
            cast=_render_cast(story), threads=_render_threads(story),
            context=context, scenes=_render_scene_slots(window, story),
            json_only=JSON_ONLY)

        reply = models.critic.complete(prompt, max_tokens=8000, temperature=0.8,
                                       json_mode=True)
        try:
            data = parse_json(reply.text)
        except LLMError:
            if on_chunk:
                on_chunk(window, False)
            continue

        rows = data.get("scenes") if isinstance(data, dict) else data
        by_index = {s.index: s for s in window}
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            try:
                spec = by_index.get(int(row.get("index", -1)))
            except (TypeError, ValueError):
                spec = None
            if spec is not None:
                _apply_scene_content(spec, row, story)
        if on_chunk:
            on_chunk(window, True)


# ======================================================================================
# 3. vaguest-first beat expansion
# ======================================================================================

BEATS_PROMPT = """These scenes of a novel are under-specified: their beats are too vague to write \
from. Sharpen them.

THE BOOK
Title: {title}
Premise: {premise}

CAST
{cast}

SCENES:
{scenes}

For each scene, rewrite its beats so that a writer with no other context could produce the scene. \
Each beat must name a place, an object, an action, or a specific thing said. Replace any beat that \
describes an interior state with the behaviour that shows it. Keep the same number of beats and \
the same events — you are specifying, not re-plotting.

{json_only}
Schema:
{{"scenes": [{{"index": 1, "beats": ["...", "..."], "setting": "...", "time": "..."}}]}}"""


def expand_beats(specs: list[SceneSpec], story: StorySpec, models: Models,
                 rounds: int = 1, batch: int = CHUNK, threshold: float = 0.55,
                 on_batch=None) -> int:
    """Sharpen the vaguest specs first, until concreteness is roughly uniform.

    CONCOCT's finding is that expanding the vaguest frontier item — rather than expanding
    depth-first to a fixed depth — produces measurably more even pacing (RESEARCH.md section 8).
    The concreteness score ordering the frontier here is a deterministic proxy, not their trained
    evaluator; it only has to rank, which is all the algorithm asks of it.

    Returns how many scenes were rewritten.
    """
    touched = 0
    for _ in range(max(1, rounds)):
        frontier = [s for s in vaguest_first(specs) if score_spec(s) < threshold]
        if not frontier:
            break
        window = frontier[:batch]
        rendered = "\n\n".join(
            f"Scene {s.index} (~{s.word_target} words)\n"
            f"  summary: {s.summary or '(none)'}\n"
            f"  setting: {s.setting or '(unspecified)'} / {s.time or '(unspecified)'}\n"
            f"  beats:\n" + ("\n".join(f"    - {b.summary}" for b in s.beats) or "    (none)")
            for s in window)

        prompt = BEATS_PROMPT.format(title=story.title, premise=story.premise,
                                     cast=_render_cast(story), scenes=rendered,
                                     json_only=JSON_ONLY)
        reply = models.critic.complete(prompt, max_tokens=6000, temperature=0.7,
                                       json_mode=True)
        try:
            data = parse_json(reply.text)
        except LLMError:
            # Reporting matters here: silence would leave the plan vague with nothing saying why.
            # `make_plan` surfaces the consequence separately, from specs with no beats.
            if on_batch:
                on_batch(window)
            break

        by_index = {s.index: s for s in window}
        for row in (data.get("scenes") if isinstance(data, dict) else data) or []:
            if not isinstance(row, dict):
                continue
            try:
                spec = by_index.get(int(row.get("index", -1)))
            except (TypeError, ValueError):
                continue
            if spec is None:
                continue
            beats = [str(b).strip() for b in (row.get("beats") or []) if str(b).strip()]
            before = score_spec(spec)
            if beats:
                spec.beats = [Beat(summary=b) for b in beats]
            spec.setting = str(row.get("setting") or spec.setting).strip()
            spec.time = str(row.get("time") or spec.time).strip()
            spec.concreteness = score_spec(spec)
            # Only count it if it actually got sharper. A "sharpening" that scored worse is a
            # regression, and silently accepting it is how quality drifts downward.
            if spec.concreteness > before:
                touched += 1
        if on_batch:
            on_batch(window)
    return touched


# ======================================================================================
# 3b. forbidden-phrase scrub — the plan must obey its own style contract
# ======================================================================================

SCRUB_PROMPT = """Rewrite this one outline line so that it does not use the word or phrase {phrases} in any form. Keep the meaning and keep it the same length. Plain register, no synonym-of-the-week — just say the thing another way.

LINE: {line}

Reply with the rewritten line only."""


def _contains_phrase(text: str, phrase: str) -> bool:
    needle = phrase.strip().lower()
    if not needle:
        return False
    if " " in needle:
        return needle in text.lower()
    return re.search(r"\b" + re.escape(needle) + r"\b", text.lower()) is not None


def scrub_forbidden(plan: list[SceneSpec], story: StorySpec, models: Models) -> int:
    """Rewrite plan text that violates the plan's own forbidden_phrases.

    The story proposal is checked for self-consistency inside the retry loop, but the *scene
    content* is filled afterwards, and a real run banned "fate" in its bible and then wrote
    "the enclave's fate hangs in the balance" into a scene summary. Every brief is built from
    this text, so a banned word here is injected into every scene of the book.

    Each offending line gets one targeted rewrite, code-verified — a fix that still contains
    the phrase is discarded, and the audit's `spec_self_violation` remains the honest backstop
    for anything the scrub could not convert. Returns the number of lines fixed.
    """
    banned = [p for p in story.style.forbidden_phrases if p.strip()]
    if not banned:
        return 0

    def fix(text: str) -> str | None:
        hits = [p for p in banned if _contains_phrase(text, p)]
        if not hits:
            return None
        prompt = SCRUB_PROMPT.format(
            phrases=", ".join(f'"{h}"' for h in hits), line=text.strip())
        try:
            reply = models.critic.complete(prompt, max_tokens=200, temperature=0.4)
        except LLMError:
            return None
        line = reply.text.strip().strip('"').strip()
        if not line or len(line.split()) > 2 * max(6, len(text.split())):
            return None
        if any(_contains_phrase(line, p) for p in banned):
            return None
        return line

    fixed = 0
    for spec in plan:
        for attr in ("summary", "setting", "time", "notes"):
            replacement = fix(getattr(spec, attr) or "")
            if replacement is not None:
                setattr(spec, attr, replacement)
                fixed += 1
        for beat in spec.beats:
            replacement = fix(beat.summary)
            if replacement is not None:
                beat.summary = replacement
                fixed += 1
        for op in spec.thread_ops.values():
            for items in (op.pre, op.post, op.forbid):
                for i, item in enumerate(items):
                    replacement = fix(item)
                    if replacement is not None:
                        items[i] = replacement
                        fixed += 1
    return fixed


# ======================================================================================
# 4. orchestration
# ======================================================================================

@dataclass
class PlanResult:
    story: StorySpec
    plan: list[SceneSpec]
    violations: list[Violation] = field(default_factory=list)
    story_retries: int = 0
    beats_sharpened: int = 0
    notes: list[str] = field(default_factory=list)

    def is_clean(self) -> bool:
        return not [v for v in self.violations if v.severity is not Severity.MINOR]

    def mean_concreteness(self) -> float:
        return (sum(score_spec(s) for s in self.plan) / len(self.plan)) if self.plan else 0.0


def make_plan(premise: str, models: Models, total_words: int = 60000,
              avg_scene_words: int = DEFAULT_SCENE_WORDS, scenes: int | None = None,
              sharpen_rounds: int = 2, seed: int = 0,
              progress=None) -> PlanResult:
    """Premise in, auditable plan out.

    The order matters. Structure is scheduled *before* any scene content is proposed, so the model
    is never in a position to break marker 1 or marker 2 — it is answering "what happens in a
    scene that must move this thread to that state", which is a much better-posed question than
    "outline a novel".
    """
    def stage(name: str, detail: str = "") -> None:
        if progress is not None:
            progress.stage(name, detail)

    story = propose_story(premise, models)
    stage("story", f"{len(story.threads)} threads, {len(story.characters)} characters")

    n_scenes = scenes or scene_count(total_words, avg_scene_words)
    schedule = schedule_threads(story.threads, n_scenes)
    specs = to_scene_specs(schedule, story.threads, total_words, seed=seed)

    # Concealment timing is derived, never guessed: the planner names the state that discloses
    # each concealment, the scheduler knows which scene that state lands in, so the prohibition
    # is enforced exactly up to that scene. A concealment with no declared reveal state ends at
    # the thread's terminal state — payoffs disclose — rather than never, because "never" made a
    # planner-made brief order a discovery its own prohibition forbade.
    for thread in story.threads:
        if not thread.concealment:
            continue
        target = thread.reveal_state or (thread.states[-1] if thread.states else None)
        landing = [i for i, state in schedule.transitions_for(thread.id) if state == target]
        if landing:
            thread.reveal_scene = landing[0]
    stage("schedule", f"{n_scenes} scenes, "
                      f"{sum(1 for m in schedule.moves.values() for s in m.values() if s)} "
                      f"thread moves")

    flesh_scenes(specs, story, models,
                 on_chunk=lambda window, ok: stage(
                     f"scenes {window[0].index}-{window[-1].index}",
                     "filled" if ok else "PROPOSAL UNPARSEABLE — left blank"))

    result = PlanResult(story=story, plan=specs)
    scrubbed = scrub_forbidden(specs, story, models)
    if scrubbed:
        stage("scrub", f"{scrubbed} line(s) used a phrase the plan itself forbids; rewritten")

    result.beats_sharpened = expand_beats(
        specs, story, models, rounds=sharpen_rounds,
        on_batch=lambda window: stage(
            "sharpen", f"scenes {', '.join(str(s.index) for s in window)}"))
    if result.beats_sharpened:
        stage("sharpen", f"{result.beats_sharpened} scene(s) improved")

    result.violations = checks.audit_plan(specs, story)
    stage("audit", "clean" if result.is_clean()
          else f"{len(result.violations)} finding(s)")

    blank = [s.index for s in specs if not s.beats]
    if blank:
        result.notes.append(
            f"{len(blank)} scene(s) have no beats and cannot be written yet: {blank}. "
            f"Re-run the planner or fill them by hand.")
    result.notes.append(f"mean concreteness {result.mean_concreteness():.2f}")
    return result
