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
from .llm import LLMError, Models, parse_json, strip_reasoning
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

Ban the vocabulary of the thing the premise is avoiding — "conspiracy", "hacker", "sentient" — \
never a word the prose is made of. "truth", "right", "memory", "silence" and their like are words \
a novel needs; banning one does not shape the book, it starts a fight the prose loses in every \
scene, and each loss costs a repair round.

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
character as how they speak and evade, not as an adjective — and never as a line they repeat. \
"Often uses the phrase X" puts X into every brief that character appears in; one such phrase \
reached 23 scenes of a 71-scene book, while the same briefs were listing it as a refrain to \
avoid. Rhythm, what they will not say, what they change the subject to. Not a catchphrase. \nAnd what they deflect TO must sit outside the plot — the weather, a tool, a queue. A character written as always steering back to the story's own central object makes the book name its own subject in every scene they are in: one such line put a phrase in 17 scenes of 71, and another in 15 of 15.

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


def drop_story_shaped_samples(story: StorySpec) -> StorySpec:
    """Remove style samples that name the cast, when the retry loop could not get rid of them.

    `story_problems` already reports this and the planner is asked three times to fix it. Three
    times is not always enough: a 71-scene book shipped with the sample "The sun hung low,
    casting long shadows over the road, and **Kai** felt **the weight of the years** he had lost
    pressing against his ribs." The check fired on every attempt and the plan was accepted
    anyway, because a loop that gives up returns its last try.

    That sample then sat in every brief of the book, and "the weight of thirty years" ended up in
    15 of 71 scenes — the manuscript's worst refrain, seeded by the thing that was supposed to be
    demonstrating rhythm. `check_style_leak` did not catch it either: it looks for a shared run
    of six words and the prose paraphrased rather than copied, sharing five.

    So this is the same shape as `drop_unavoidable_bans` and exists for the same reason. Asking
    is the first move and code is the fallback, because an unattended run has nobody to notice
    that the model refused three times.

    A sample is only dropped when others survive: two thin samples demonstrate the voice better
    than none, and a story left with nothing here is a worse failure than the one being fixed.
    """
    if not story.style.samples:
        return story
    tokens = {t for c in story.characters
              for t in re.split(r"[^a-z]+", c.name.lower()) if len(t) > 2}
    if not tokens:
        return story
    keep = [s for s in story.style.samples
            if not (tokens & set(re.split(r"[^a-z]+", s.lower())))]
    if not keep or len(keep) == len(story.style.samples):
        return story
    story.style.samples = keep
    return story


def drop_unavoidable_bans(story: StorySpec) -> StorySpec:
    """Remove forbidden phrases the prose cannot avoid — from a *proposal*, never from a plan.

    The planner is asked to name the vocabulary its premise rules out, and it does that part
    well: a lighthouse story correctly banned "conspiracy", "hacker" and "sentient". Then it
    added "truth", "right", "memory" and "silence", which are words a novel is made of. Every
    scene of that book would trip `check_forbidden` several times and every trip costs a repair
    round on a word the story is actually about.

    `check_ban_is_avoidable` already gates on this, and its docstring is explicit that the plan
    is not edited — `write` refuses and the author decides. That stays exactly true. This runs
    one step earlier and on the other kind of input: a model's proposal, still inside the retry
    loop, before it has become a contract anything is held to. A `story.json` a person wrote is
    parsed by `parse_story` and is never touched, so a hand-written ban still reaches the audit
    and still stops the run.

    Every fresh premise tried has produced at least one of these, which makes it the single
    largest obstacle to a run nobody is watching.
    """
    keep = [p for p in story.style.forbidden_phrases if not checks.is_unavoidable_ban(p)]
    if len(keep) == len(story.style.forbidden_phrases):
        return story
    story.style.forbidden_phrases = keep
    return story


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


_CATCHPHRASE = re.compile(
    r"\b(?:often|always|habitually|repeatedly|frequently|constantly|invariably|routinely|"
    r"catchphrase|signature phrase|favourite phrase|favorite phrase|tends? to say|"
    r"has a habit of|is fond of saying|likes to say|keeps saying)\b"
    r"[^.!?]{0,60}[\'\"“‘]([^\'\"”’]{8,160})[\'\"”’]",
    re.IGNORECASE)


_HABITUAL_TOPIC = re.compile(
    r"(?:about|subject to|onto|back to|to talk(?:ing)? about|returns? to)\s+"
    r"(?:the\s+)?([a-z][a-z ']{3,26}?)(?=[.,;]|$)", re.IGNORECASE)

_TOPIC_STOP = {"a", "an", "the", "of", "to", "in", "on", "at", "for", "with", "and", "or", "is",
               "was", "be", "been", "her", "his", "their", "its", "that", "this", "it", "as",
               "by", "from", "not", "no", "but", "they", "he", "she", "him", "them", "who",
               "what", "when", "where", "which", "about"}


def _significant(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z']+", str(text).lower())
            if len(w) > 3 and w not in _TOPIC_STOP}


def scripted_topics(story: StorySpec) -> list[tuple[str, str]]:
    """Characters told to keep steering the conversation to the story's own central object.

    The catchphrase problem without the quotation marks, and `_CATCHPHRASE` cannot see it
    because there is nothing quoted to see. A live bible said of one character: "Mir rarely
    speaks, but when he does, it is always about the Ledger of Time", and "deflects by changing
    the subject to the Ledger of Time". That description reaches every brief he appears in, and
    "ledger of time" landed in 17 of 71 scenes. Another book scripted a character toward "the
    register" and the phrase appears in 15 scenes of 15.

    The discriminator is whether the topic comes from the story's own vocabulary, and it is
    sharp. Neutral deflections — "deflects by changing the subject to the weather", "deflects by
    listing legal clauses" — never reached four scenes in any book measured. Steering a character
    at the premise's central noun is what turns a habit into a refrain.

    Deflection itself is good characterisation and is not what this objects to. It objects to
    deflecting *toward the thing the book is about*, which guarantees the book says its own
    subject aloud in every scene that character is in.
    """
    world = _significant(story.premise) | _significant(" ".join(story.world_rules))
    world |= _significant(" ".join(t.name or "" for t in story.threads))
    if not world:
        return []
    out: list[tuple[str, str]] = []
    for c in story.characters:
        for m in _HABITUAL_TOPIC.finditer(f"{c.description} {c.voice}"):
            topic = m.group(1).strip()
            if _significant(topic) & world:
                out.append((c.name, topic))
                break
    return out


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

    # A catchphrase written into a character's voice is repeated by the whole book.
    #
    # A 71-scene run gave Vaylen Korr the voice "he speaks in clipped, precise sentences,
    # deflecting with dry humor, often using the phrase 'this is not a matter of morality.'"
    # That description goes into every brief the character appears in, so the phrase landed in
    # 23 of 71 scenes — and the same briefs were simultaneously listing it as a refrain to
    # avoid, because `manuscript_refrains` had correctly identified it. Characterisation beat
    # prohibition, which it will, because one is what the character *is* and the other is a rule.
    #
    # The distinction is habitual repetition, not quotation. Another plan gave a character the
    # voice "The light is on. The tide is out. The snow is falling." as an illustration of
    # clipped rhythm, and none of it appeared in the prose at all — 0 of 9 scenes. It is
    # "often using the phrase" that does the damage.
    scripted = scripted_topics(story)
    if scripted:
        problems.append(
            "These characters are steered at the story's own central subject: "
            + "; ".join(f'{name} ("{topic}")' for name, topic in scripted)
            + ". A voice reaches every brief that character appears in, so a habit of raising "
            "the thing the book is about makes the book say its own subject aloud in every "
            "scene they are in — one such line put a phrase in 17 scenes of 71 and another in "
            "15 of 15. Deflection is good; deflect toward something outside the plot, the way "
            "somebody changes the subject to the weather.")

    catchphrases = [c.name for c in story.characters
                    if _CATCHPHRASE.search(f"{c.voice} {c.description}")]
    if catchphrases:
        problems.append(
            f"These characters are given a phrase they repeat: {', '.join(catchphrases)}. "
            f"A line written into a voice is injected into every brief that character appears "
            f"in, and one such phrase reached 23 scenes of a 71-scene book. Describe HOW they "
            f"speak — rhythm, what they evade, what they will not say — and never give them a "
            f"line to repeat.")
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
        story = drop_unavoidable_bans(parse_story(data))
        last = story
        problems = story_problems(story)
        if not problems:
            return story
        extra = ("Your previous attempt had these problems. Fix them and keep everything else:\n"
                 + "\n".join(f"- {p}" for p in problems))
    if last is None:
        raise LLMError("the planner could not obtain a usable story proposal")
    # The loop is out of attempts and `last` still has problems. Repair deterministically what
    # can be repaired deterministically rather than shipping a bible nobody will read before a
    # book is written from it.
    return drop_story_shaped_samples(last)


# ======================================================================================
# 2. scene content, into the scheduled skeleton
# ======================================================================================

# The "something passing between them" rule in the beats section below is the best-evidenced
# instruction in this file, and it is worth writing down why rather than leaving it as taste.
#
# Reading the middle of a 71-scene book found scene 38: one character alone in a ruin, touching
# statues and remembering. Every check passed it, `summary_distance` included, because the
# flashback it becomes is narrated in simple past. Measuring outward from that scene found the
# emptying-out is a shape — dialogue runs at 21% of words across the opening eighteen scenes,
# 15% in the next, 10% in the third, 9% in the last — and that 20 of the 71 scenes the plan had
# populated with two or three characters came back with no dialogue at all.
#
# The cause is not the writer. Across those 70 two-character scenes, correlation between the
# share of beats naming a spoken act and the share of prose that is dialogue is r = +0.672:
#
#     beats naming something said     scenes   mean dialogue   came back silent
#     none                              33         .029           20 of 33
#     one                               27         .101            6 of 27
#     two or more                       10         .203            0 of 10
#
# Not one scene whose spec named two spoken acts came back silent. The model writes what it is
# asked for; told "Vael reflects on the enclave's purpose" it writes reflection.
#
# A check for this was built and then removed. It flagged three scenes of the hand-authored
# reference plan — "She leaves with a form and no remedy, and takes it out on the wrong person",
# "The sisters, at the well, not resolving" — which are better beats than the planner writes and
# describe interaction without any verb from a list. The correlation was measured on
# planner-generated beats and does not transfer to a human's. The instruction is where the
# leverage is; the check was pattern-matching the phrasing rather than the property.
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
- "characters": ids of everyone present, and there are nearly always two or more. A novel is
  people doing things to each other; a character by themselves has nobody to be surprised by.
- "beats": 2 to 4 beats, in order. Each is roughly half a page of story and must be an event or a
  turn, not a feeling. A beat that could be summarised as "she reflects on X" is not a beat.
  A beat NAMES what happens; it is not the prose. Write "Dain refuses to hand over the vial",
  never "Dain steps forward, his boots crunching over dry leaves, his voice steady and low" and
  never a line of dialogue in quotation marks. The scene is written from the beat, so a beat
  written as prose is prose the scene will copy back word for word.
  At least one beat per scene must name something PASSING BETWEEN two people — a question asked,
  a demand refused, an accusation, a lie, an offer taken back. Name the act, not the words:
  "Sera refuses to say who filed the record", never the line itself. A scene where nothing passes
  between anybody comes out as one character walking through a place having thoughts about it.
- "threads": for each thread id this scene must move, what the scene must BRING ABOUT ("post",
  1-3 concrete statements) and what it must NOT do ("forbid", 1-3 statements). Forbids are where
  premature reveals get prevented — use them.
  Every "post" entry NAMES SOMETHING THAT HAPPENS ON THE PAGE. Never a thread state: write
  "Dain hands the vial back", never "The Allegiance reaches 'reoriented'", which names our
  bookkeeping rather than an event. Never an absence either — "the past is left unspoken",
  "neither resolved nor abandoned" — because nothing a scene shows can satisfy them.
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
        # Stored exactly as proposed. Earlier versions rewrote these here — absences moved to
        # the forbid list, negations inverted — so that a checker could cope, and the cost was
        # paid by the writer: the brief is built from this text, and a live plan lost "Nils
        # ignores the thermometer's reading", which is a perfectly writable beat, because a
        # judge could not confirm it afterwards. The audit reports rules that look unwritable;
        # the author decides. `verify` narrows what it asks the judge, which is its own business
        # and invisible here.
        if post:
            op.post = post[:4]
        if forbid:
            op.forbid = forbid[:4]

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

        # Solo scenes arrive in runs, not at random, and the chunk context is why: it carries the
        # last three summaries and nothing about who was in them, so a planner that has just
        # written six one-character scenes has no way to know. Measured across four 71-scene
        # plans, the solo count is bimodal — 5, 5, 22, 24 — and the difference is drift: the good
        # plan's longest unbroken run of solo scenes is 1, the bad ones' are 6 and 7, with
        # scenes 13–18 and 58–64 solo end to end.
        #
        # A running tally is the smallest thing that supplies the missing global view. It is
        # added only when the share is already high, and says nothing about when a solo scene is
        # justified: three sentences explaining that exception, in an earlier version of the
        # instruction below, quadrupled the number of them.
        settled = [s for s in ordered[:start] if s.characters]
        solo = [s for s in settled if len(s.characters) < 2]
        if settled and len(solo) / len(settled) > 0.15 and len(solo) >= 2:
            context += (
                f"\n\nSO FAR: {len(solo)} of the {len(settled)} scenes you have settled have "
                f"only one character in them. That is too many. Put people in the same room in "
                f"the scenes below.")

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


REPEOPLE_PROMPT = """These scenes of a novel each have only one character in them, and there are too many such scenes in this plan. A novel is people doing things to each other; a character by themselves has nobody to be surprised by.

Rewrite each one so somebody else is present and something passes between them — a question asked, a demand refused, an accusation, a lie. Keep what the scene is FOR: its summary, its setting, and the thread work it does must survive. Change who is in the room and what happens between them.

THE CAST
{cast}

SCENES TO REPEOPLE
{scenes}

{json_only}
Schema:
{{"scenes": [{{"index": 0, "summary": "...", "characters": ["id", "id"],
  "beats": ["...", "...", "..."]}}]}}"""


def repeople_solo_scenes(specs: list[SceneSpec], story: StorySpec, models: Models,
                         limit: float = 0.15, on_batch=None) -> int:
    """Re-ask for the scenes a plan left with one character in them.

    The planner is *told* that scenes nearly always have two or more people in them, and a
    running tally tells it how many it has already left empty. Both help and neither controls the
    total: across six plans of one premise the solo count came out 5, 5, 22, 24, 10 and 28. The
    instruction moves the shape within a plan — one went from 6 solo in its first fifth to 0 in
    its last — and the total stays bimodal.

    So this is the same move as `drop_unavoidable_bans` and the fact cap: ask first, then act in
    code when asking did not work. Unlike those it cannot be deterministic — inventing who is in
    a room is authorship — so it re-asks, but only for the scenes that are wrong and only when
    there are enough of them to matter. Below `limit` the plan is left alone: a handful of solo
    scenes is a novel, not a defect.

    The scene's summary, setting and thread work are held fixed in the prompt. What changes is
    who is present and what passes between them.
    """
    ordered = sorted(specs, key=lambda s: s.index)
    solo = [s for s in ordered if len(s.characters) < 2]
    if not ordered or len(solo) / len(ordered) <= limit:
        return 0

    fixed = 0
    for start in range(0, len(solo), CHUNK):
        window = solo[start:start + CHUNK]
        rendered = "\n\n".join(
            f"Scene {s.index}: {s.summary}\n  setting: {s.setting}\n"
            f"  currently present: {', '.join(s.characters) or '(nobody named)'}\n"
            f"  must bring about: "
            + "; ".join(p for op in s.thread_ops.values() for p in op.post)
            for s in window)
        prompt = REPEOPLE_PROMPT.format(cast=_render_cast(story), scenes=rendered,
                                        json_only=JSON_ONLY)
        try:
            reply = models.critic.complete(prompt, max_tokens=4000, temperature=0.7,
                                           json_mode=True)
            data = parse_json(reply.text)
        except LLMError:
            continue
        rows = data.get("scenes") if isinstance(data, dict) else data
        by_index = {s.index: s for s in window}
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            try:
                spec = by_index.get(int(row.get("index", -1)))
            except (TypeError, ValueError):
                continue
            if spec is None:
                continue
            before = list(spec.characters)
            _apply_scene_content(spec, row, story)
            # Only counted, and only kept, if it actually put somebody else in the room. A
            # rewrite that comes back solo has cost a call and changed nothing, and must not be
            # reported as a fix.
            if len(spec.characters) >= 2:
                fixed += 1
            elif not spec.characters:
                spec.characters = before
        if on_batch:
            on_batch(window)
    return fixed


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
Each beat must name a place, an object, an action, or what is settled by something said. Replace any beat that \
describes an interior state with the behaviour that shows it. Keep the same number of beats and \
the same events — you are specifying, not re-plotting.

Specific is not the same as written. A beat still NAMES what happens; the scene is written
from it, so anything you write here comes back word for word in the prose and is flagged as a
leak. No dialogue in quotation marks, no cloaks or boots or wind, no describing how a voice
sounds. Write "Varyn demands the years back", never "Varyn says, 'Return the years.'"
Under fifteen words each.

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

Name the concrete thing instead of the abstraction. "the villagers react to the truth" becomes
"the villagers react to what the register says"; the banned word is usually standing in for an
object, a document, or a sentence somebody spoke, and that object is what belongs in the line.
{feedback}
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
        # Three attempts, at rising temperature, each told what the last one got wrong. The
        # verification is strict on purpose — a rewrite that still carries the phrase is
        # discarded rather than accepted — so a single shot leaves the plan carrying the word,
        # and a silent retry repeats the same mistake: two live plans banned "truth" and kept
        # beats saying "truth" because every attempt reached for it again. Naming the failure
        # is what breaks the loop, which is the same reason `REMEDIES` exists for scene repair.
        feedback = ""
        for attempt in range(3):
            prompt = SCRUB_PROMPT.format(
                phrases=", ".join(f'"{h}"' for h in hits), line=text.strip(),
                feedback=feedback)
            try:
                reply = models.critic.complete(prompt, max_tokens=200,
                                               temperature=0.3 + 0.3 * attempt)
            except LLMError:
                return None
            line = strip_reasoning(reply.text).strip().strip('"').strip()
            if not line or len(line.split()) > 2 * max(6, len(text.split())):
                feedback = ("\nYour last attempt was empty or far too long. Stay close to the "
                            "original length.\n")
                continue
            still = [p for p in banned if _contains_phrase(line, p)]
            if still:
                quoted = ", ".join(repr(p) for p in still)
                feedback = (f"\nYour last attempt was {line!r}, which still uses {quoted}. "
                            f"That word cannot appear in any form. Replace it with the "
                            f"thing it refers to.\n")
                continue
            return line
        return None

    fixed = 0
    # The story bible first. `check_spec_self_consistency` reads the story *and* the plan, so a
    # banned word in a character description is a permanent MAJOR that no amount of scene-level
    # scrubbing clears — and character descriptions go into every brief, which is the whole
    # reason the check exists. A live run banned "truth" and then wrote "he's too old to confront
    # the truth" into the father's description; five scene lines were fixed and that one was not.
    # Title and character names are left alone: those are identity, and renaming the book or the
    # cast is the author's call, so the audit keeps reporting them instead.
    for attr in ("premise",):
        replacement = fix(getattr(story, attr) or "")
        if replacement is not None:
            setattr(story, attr, replacement)
            fixed += 1
    for i, rule in enumerate(story.world_rules):
        replacement = fix(rule)
        if replacement is not None:
            story.world_rules[i] = replacement
            fixed += 1
    for character in story.characters:
        for attr in ("description", "voice"):
            replacement = fix(getattr(character, attr) or "")
            if replacement is not None:
                setattr(character, attr, replacement)
                fixed += 1
    for thread in story.threads:
        for attr in ("name", "concealment", "payoff"):
            replacement = fix(getattr(thread, attr) or "")
            if replacement is not None:
                setattr(thread, attr, replacement)
                fixed += 1
    replacement = fix(story.style.notes or "")
    if replacement is not None:
        story.style.notes = replacement
        fixed += 1
    for i, sample in enumerate(story.style.samples):
        replacement = fix(sample)
        if replacement is not None:
            story.style.samples[i] = replacement
            fixed += 1

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


DEPROSE_PROMPT = """Rewrite this outline beat so that it NAMES what happens instead of writing it.

Rules:
- No dialogue. If the beat has a character say something, say what they do by saying it:
  "Varyn demands the years back", not "Varyn says, 'Return the years.'"
- No sensory or physical description. Cut cloaks, boots, wind, glow, and how a voice sounds.
- One clause if possible. Under fifteen words. Plain, flat, unliterary.

BEAT: {beat}

Reply with the rewritten beat only."""


# ", his boots crunching over dry leaves" — the absolute-participial construction is the
# signature of a beat that has stopped planning and started describing. Dialogue is the other
# signature, and `checks.check_beats_are_intent` reports that one at plan level.
_PARTICIPIAL = re.compile(r",\s+(?:his|her|its|their|the)\s+\w+\s+\w+", re.I)


def _is_written_out(beat: str) -> bool:
    return bool(checks._BEAT_PROSE.search(beat) or _PARTICIPIAL.search(beat)
                or len(beat.split()) > 18)


def scrub_prose_beats(plan: list[SceneSpec], models: Models) -> int:
    """Rewrite beats that were written as prose rather than as intent.

    A beat is what the scene must accomplish; the scene is written from it. So a beat written as
    finished prose is prose the writer copies back, and `check_brief_leak` is right to flag the
    copy — which leaves a scene nothing can repair, because its brief is the scene. Scene 26 of a
    live run had ten beats of the form "Dain steps forward, his boots crunching over dry leaves,
    his voice steady and low" and never committed however many rounds it was given.

    Each rewrite is code-verified: a replacement that still carries dialogue, or that grew, is
    discarded, and `checks.check_beats_are_intent` remains the honest backstop.
    """
    fixed = 0
    for spec in plan:
        for beat in spec.beats:
            if not _is_written_out(beat.summary):
                continue
            try:
                reply = models.critic.complete(
                    DEPROSE_PROMPT.format(beat=beat.summary), max_tokens=200, temperature=0.3)
            except LLMError:
                continue
            line = strip_reasoning(reply.text).strip().strip('"').strip()
            if not line or len(line.split()) > len(beat.summary.split()):
                continue
            if checks._BEAT_PROSE.search(line):
                continue
            beat.summary = line
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
              sharpen_rounds: int = 2, seed: int = 0, repeople: bool = True,
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

    # `repeople` is an ablation switch, not a feature toggle: the pass has only ever been run
    # against a scripted backend, so its effect on a live plan is unmeasured, and a mechanism
    # with no off switch cannot be measured at all. Defaults to on — the shipped behaviour.
    repeopled = repeople_solo_scenes(
        specs, story, models,
        on_batch=lambda w: stage("repeople",
                                 f"scenes {', '.join(str(s.index) for s in w)}")) if repeople else 0
    if repeopled:
        stage("repeople", f"{repeopled} solo scene(s) given somebody to talk to")
    elif not repeople:
        stage("repeople", "skipped (--no-repeople)")

    result = PlanResult(story=story, plan=specs)
    result.beats_sharpened = expand_beats(
        specs, story, models, rounds=sharpen_rounds,
        on_batch=lambda window: stage(
            "sharpen", f"scenes {', '.join(str(s.index) for s in window)}"))
    if result.beats_sharpened:
        stage("sharpen", f"{result.beats_sharpened} scene(s) improved")

    # After sharpening, not before. Sharpening is the step that pushes beats toward specificity,
    # so it is also the step that turns them into prose — running the scrub first leaves its work
    # to be undone by the very next call, which is how it was ordered when written.
    deprosed = scrub_prose_beats(specs, models)
    if deprosed:
        stage("beats", f"{deprosed} beat(s) were written as prose, not intent; rewritten")

    scrubbed = scrub_forbidden(specs, story, models)
    if scrubbed:
        stage("scrub", f"{scrubbed} line(s) used a phrase the plan itself forbids; rewritten")

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
