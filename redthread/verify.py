"""LLM-backed verification. The half of the guardrail that needs reading comprehension.

Division of labour with `checks.py`: anything countable is counted there for free. This module
spends tokens only on judgements that genuinely require understanding the prose — did the scene
actually effect the thread transition it was told to, does this new fact contradict that old
one, is the narrator explaining the point.

Every probe here is a single-purpose call with a fixed rubric and JSON output. That is
deliberate: one call that asks "is this scene good?" produces agreeable mush, while five calls
that each ask one falsifiable question produce answers you can act on. Re3 uses separate
purpose-built rerankers for exactly this reason (docs/RESEARCH.md section 1).
"""

from __future__ import annotations

from .ledger import Ledger
from .llm import LLMError, Models, parse_json
from .models import (Fact, FactKind, Scene, SceneSpec, Severity, StorySpec, Thread,
                     Violation)

STRUCTURED_BUDGET = 8000
"""Output budget for every structured probe.

Generous on purpose. A thinking model spends tokens on reasoning before it emits the JSON, and a
budget sized for the JSON alone gets a truncated object — which reads as "the model could not do
it" when in fact it was cut off mid-answer. Cheap insurance: these calls emit small objects, so a
high ceiling costs nothing when it is not needed.
"""

JSON_ONLY = ("Reply with JSON only. No preamble, no explanation outside the JSON, no code "
             "fence commentary.")


def _clip(text: str, words: int = 1800) -> str:
    parts = text.split()
    return " ".join(parts[:words]) + (" […]" if len(parts) > words else "")


# ======================================================================================
# 1. fact extraction — prose into quadruples
# ======================================================================================

EXTRACT_PROMPT = """You are a continuity clerk for a novel. Read the scene and record what it \
established, as structured facts. You are not judging the writing.

Record a fact for anything a later scene could contradict. Four kinds:

- "state"     — something now true that stays true until something changes it.
                (a door is welded shut, a character is limping, it is raining in the city)
- "knowledge" — a specific character now knows a specific thing. Subject MUST be the character's
                name. This is the most important kind: later scenes must not let a character act
                on what they do not know, nor be surprised by what they were told.
- "detail"    — a concrete particular the prose has now fixed and cannot change.
                (the scar is on the left hand, the truck is a green Hilux)
- "event"     — something that happened. Use this only when it is not better recorded as a state.

Rules:
- Subject is a proper name or a specific thing, never a pronoun. Resolve every pronoun.
- Object is short and literal. No interpretation, no theme, no atmosphere.
- Do not record what a character feels or believes unless the prose states it as fact.
- Do not record anything the scene did not actually establish. Inventing facts here is worse \
than missing them, because an invented fact becomes a constraint on every later scene.
- BE SPARING. Record only what a later scene could actually contradict. Atmosphere is not a fact: \
"the screen was flickering", "the room was cold", "her fingers were calloused" are description, \
and recording them turns every later scene into an argument with the weather. Ten durable facts \
are worth more than forty transient ones — everything here constrains the rest of the book and is \
fed into every later brief.

SCENE {index} of "{title}":
---
{text}
---

{json_only}
Schema:
{{"facts": [{{"subject": "...", "predicate": "...", "object": "...", "kind": "state|knowledge|detail|event"}}]}}"""


def extract_facts(scene: Scene, story: StorySpec, models: Models,
                  max_facts: int = 30) -> list[Fact]:
    """Prose into quadruples.

    The cap is a backstop against over-recording, not a target. A real run on a local model
    returned 59 facts for a 689-word scene, mostly atmosphere, and that compounds badly: the
    ledger fills with transient description, every later brief is padded with it, and
    `conflict_candidates` starts manufacturing contradictions out of how the light was falling.
    """
    prompt = EXTRACT_PROMPT.format(index=scene.index, title=story.title,
                                   text=_clip(scene.text, 2500), json_only=JSON_ONLY)
    reply = models.extractor.complete(prompt, max_tokens=STRUCTURED_BUDGET, temperature=0.0)
    data = parse_json(reply.text)
    rows = data.get("facts", []) if isinstance(data, dict) else data

    facts: list[Fact] = []
    for row in rows[:max_facts]:
        if not isinstance(row, dict):
            continue
        subject = str(row.get("subject", "")).strip()
        predicate = str(row.get("predicate", "")).strip()
        obj = str(row.get("object", "")).strip()
        if not (subject and predicate):
            continue
        try:
            kind = FactKind(str(row.get("kind", "event")).strip().lower())
        except ValueError:
            kind = FactKind.EVENT
        facts.append(Fact(subject, predicate, obj, scene.index, kind))
    return facts


# ======================================================================================
# 2. contradiction judgement — stage 2 of DOME's detection
# ======================================================================================

CONFLICT_PROMPT = """You are checking a novel for continuity errors. Below are pairs of \
established facts that share a subject and a similar predicate, so they MIGHT contradict. Most \
pairs will not.

For each pair decide: can both be true of the same story, in this order?

Not a contradiction:
- a state that legitimately changed over time (a door unlocked in scene 3, locked again in scene 9)
- different facts that merely sound similar
- a character learning something they did not know before

A contradiction:
- the same unchanging detail given two different values (eye colour, a scar's location, a name)
- a character knowing something before the scene where they learn it
- a physical state that cannot have changed in the time available

FACT PAIRS:
{pairs}

{json_only}
Schema:
{{"judgements": [{{"pair": 0, "contradiction": true, "why": "one short sentence"}}]}}"""


def judge_conflicts(new_facts: list[Fact], ledger: Ledger, models: Models,
                    max_pairs: int = 25) -> list[Violation]:
    """Ask a model only about the pairs the deterministic grouping already flagged.

    DOME groups structurally-similar quadruples first and only then applies LLM judgement
    (docs/RESEARCH.md section 3). The grouping is what keeps this affordable: without it, this
    would be a quadratic comparison against the whole manuscript.
    """
    pairs = ledger.conflict_candidates(new_facts)[:max_pairs]
    if not pairs:
        return []

    rendered = "\n".join(
        f"{i}. EARLIER {old.as_line()}\n   NEW     {new.as_line()}"
        for i, (old, new) in enumerate(pairs))
    prompt = CONFLICT_PROMPT.format(pairs=rendered, json_only=JSON_ONLY)
    reply = models.critic.complete(prompt, max_tokens=STRUCTURED_BUDGET, temperature=0.0)

    try:
        data = parse_json(reply.text)
    except LLMError as exc:
        # A failed judgement must not silently pass. Surfacing the candidates as MINOR keeps
        # them visible to a human without blocking the run on a parse failure.
        return [Violation("conflict_check_failed", Severity.MINOR,
                          f"{len(pairs)} candidate pair(s) could not be judged: {exc}",
                          "llm:judge_conflicts")]

    rows = data.get("judgements", []) if isinstance(data, dict) else data
    out: list[Violation] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("contradiction"):
            continue
        try:
            old, new = pairs[int(row.get("pair", -1))]
        except (ValueError, TypeError, IndexError):
            continue
        out.append(Violation(
            "continuity_contradiction", Severity.BLOCKER,
            f"{row.get('why', 'contradicts established state')} — earlier: "
            f"{old.as_line()}; now: {new.as_line()}",
            "llm:judge_conflicts", new.object))
    return out


# ======================================================================================
# 3. thread satisfaction — did the scene do its job?
# ======================================================================================

THREAD_PROMPT = """You are checking whether a scene fulfilled its brief. Judge only what the \
prose actually does, not what it seems to intend.

For each requirement, answer:
- "met"     — the scene brings this about, on the page
- "partial" — gestured at but not actually accomplished
- "missed"  — did not happen

For each prohibition, answer whether the scene violated it.

Be strict about "met". A scene that mentions a thing has not accomplished it. If a requirement \
says a character decides something, a reader must be able to point at the decision.

REQUIREMENTS:
{required}

PROHIBITIONS:
{forbidden}

SCENE:
---
{text}
---

{json_only}
Schema:
{{"requirements": [{{"n": 0, "verdict": "met|partial|missed", "evidence": "short quote or ''"}}],
  "prohibitions": [{{"n": 0, "violated": false, "quote": ""}}]}}"""


def check_threads(scene: Scene, spec: SceneSpec, story: StorySpec,
                  models: Models) -> list[Violation]:
    """The core guardrail: verify the ConWriter (Post, Forbid) operators actually held."""
    required: list[tuple[str, str]] = []
    forbidden: list[tuple[str, str]] = []
    for tid, op in spec.thread_ops.items():
        thread: Thread | None = story.thread(tid)
        label = thread.name if thread else tid
        for item in op.post:
            required.append((tid, f"[{label}] {item}"))
        if op.to_state:
            required.append((tid, f"[{label}] the thread must end in the state: {op.to_state}"))
        for item in op.forbid:
            forbidden.append((tid, f"[{label}] {item}"))
        if thread and thread.concealment:
            forbidden.append(
                (tid, f"[{label}] must NOT reveal to the reader: {thread.concealment}"))

    if not required and not forbidden:
        return []

    prompt = THREAD_PROMPT.format(
        required="\n".join(f"{i}. {text}" for i, (_, text) in enumerate(required)) or "(none)",
        forbidden="\n".join(f"{i}. {text}" for i, (_, text) in enumerate(forbidden)) or "(none)",
        text=_clip(scene.text, 2500), json_only=JSON_ONLY)
    reply = models.critic.complete(prompt, max_tokens=STRUCTURED_BUDGET, temperature=0.0)

    try:
        data = parse_json(reply.text)
    except LLMError as exc:
        return [Violation("thread_check_failed", Severity.MAJOR,
                          f"could not verify thread obligations: {exc}", "llm:check_threads")]

    out: list[Violation] = []
    for row in (data.get("requirements") or []):
        if not isinstance(row, dict):
            continue
        verdict = str(row.get("verdict", "")).lower()
        if verdict == "met":
            continue
        try:
            tid, text = required[int(row.get("n", -1))]
        except (ValueError, TypeError, IndexError):
            continue
        out.append(Violation(
            "thread_obligation", Severity.MAJOR,
            f"{verdict}: {text}", "llm:check_threads", str(row.get("evidence", ""))[:200]))

    for row in (data.get("prohibitions") or []):
        if not isinstance(row, dict) or not row.get("violated"):
            continue
        try:
            tid, text = forbidden[int(row.get("n", -1))]
        except (ValueError, TypeError, IndexError):
            continue
        # A broken Forbid — a premature reveal especially — cannot be committed. Once the reader
        # knows, no later scene can un-know it.
        out.append(Violation(
            "thread_prohibition", Severity.BLOCKER,
            f"violated: {text}", "llm:check_threads", str(row.get("quote", ""))[:200]))
    return out


# ======================================================================================
# 4. the anti-tell probes  (RESEARCH.md section 6)
# ======================================================================================

TELLS_PROMPT = """You are auditing a scene from a novel for the specific ways machine-written \
fiction differs measurably from human-written fiction. These are not style preferences; each is \
a documented distributional difference.

Judge only this scene. Quote the worst instance of anything you flag.

1. THEMATIC OVER-EXPLANATION — does the narration state what the scene means, name its own
   theme, or draw the moral? (Present in 77% of AI stories vs 52% of human ones.) A character
   thinking an abstract summary of their own situation counts.
2. DIALOGUE AS DEBATE — are characters exchanging positions on ideas rather than trying to get
   something from each other? (59% vs 34%.)
3. VAGUE ALLUSION — does the scene gesture at unnamed books, songs, brands, places where naming
   them would be natural? (Named references: 24% AI vs 47% human.)
4. PROTAGONIST AGENCY RESOLUTION — is every outcome in this scene produced by the protagonist
   deciding and acting, with no room for circumstance, other people, or accident? (69% vs 46%.)
5. SUMMARY INSTEAD OF SCENE — does it narrate at a distance what should have been dramatised?

SCENE:
---
{text}
---

{json_only}
Schema:
{{"findings": [{{"tell": "thematic_gloss|dialogue_debate|vague_allusion|agency_resolution|summarised",
  "present": true, "severity": "major|minor", "quote": "...", "why": "one sentence"}}]}}"""

_TELL_LABELS = {
    "thematic_gloss": "the narration explains the scene's meaning",
    "dialogue_debate": "dialogue is a debate rather than a negotiation",
    "vague_allusion": "unnamed allusion where naming would be natural",
    "agency_resolution": "every outcome produced by protagonist decision",
    "summarised": "narrated at summary distance instead of dramatised",
}


def probe_tells(scene: Scene, models: Models) -> list[Violation]:
    """The subtle half of StoryScope's tells — the ones regex cannot reach.

    `checks.check_thematic_gloss` catches the loud constructions for free. This catches the
    quiet ones. Both layers exist because thematic over-explanation is the largest single gap in
    the StoryScope data, and the cheap layer only catches the phrasings, not the move.
    """
    prompt = TELLS_PROMPT.format(text=_clip(scene.text, 2500), json_only=JSON_ONLY)
    reply = models.critic.complete(prompt, max_tokens=STRUCTURED_BUDGET, temperature=0.0)
    try:
        data = parse_json(reply.text)
    except LLMError:
        return []

    out: list[Violation] = []
    for row in (data.get("findings") if isinstance(data, dict) else data) or []:
        if not isinstance(row, dict) or not row.get("present"):
            continue
        tell = str(row.get("tell", "unknown"))
        severity = (Severity.MAJOR if str(row.get("severity", "minor")).lower() == "major"
                    else Severity.MINOR)
        out.append(Violation(
            f"tell_{tell}", severity,
            f"{_TELL_LABELS.get(tell, tell)}: {row.get('why', '')}",
            "llm:probe_tells", str(row.get("quote", ""))[:240]))
    return out


# ======================================================================================
# 5. forecastability — tension as unpredictability  (RESEARCH.md section 9)
# ======================================================================================

FORECAST_PROMPT = """Here is a novel's story so far, in summary, followed by what actually \
happens next.

Before reading what happens next, predict it. Then score how close your prediction was.

STORY SO FAR:
{context}

WHAT HAPPENS NEXT:
{next_scene}

{json_only}
Schema:
{{"prediction": "what you would have predicted, 2 sentences",
  "closeness": 0.0, "obvious_beats": ["..."]}}

"closeness" is 0.0 if what happened was genuinely unforeseeable from the story so far, and 1.0 \
if it was the only thing that could have happened. Be honest — a high score is useful \
information, not a failure on your part."""


def probe_forecast(scene: Scene, story_so_far: str, models: Models,
                   threshold: float = 0.8) -> list[Violation]:
    """If a model can call the scene from the story so far, the scene has no tension.

    Narrative tension is downstream of hidden information, and it can be metered by how
    predictable upcoming events are (docs/RESEARCH.md section 9). The cited work measures the
    entropy of a forecasting distribution; this is a cruder single-sample proxy — one prediction
    and a self-reported closeness — because a self-scored number needs no logprobs and works
    against any backend. Treat it as a smell test, not the metric from the paper.
    """
    if not story_so_far.strip():
        return []
    prompt = FORECAST_PROMPT.format(context=_clip(story_so_far, 1200),
                                    next_scene=_clip(scene.text, 700),
                                    json_only=JSON_ONLY)
    reply = models.critic.complete(prompt, max_tokens=STRUCTURED_BUDGET, temperature=0.0)
    try:
        data = parse_json(reply.text)
    except LLMError:
        return []
    if not isinstance(data, dict):
        return []
    try:
        closeness = float(data.get("closeness", 0.0))
    except (TypeError, ValueError):
        return []
    if closeness < threshold:
        return []
    beats = ", ".join(str(b) for b in (data.get("obvious_beats") or [])[:4])
    return [Violation(
        "low_tension", Severity.MINOR,
        f"a model predicted this scene from the story so far at {closeness:.2f} closeness"
        + (f" (obvious: {beats})" if beats else "")
        + ". Consider what this thread is still concealing.",
        "llm:probe_forecast", str(data.get("prediction", ""))[:240])]


# ======================================================================================
# runner
# ======================================================================================

def verify_scene(scene: Scene, spec: SceneSpec, story: StorySpec, ledger: Ledger,
                 models: Models, story_so_far: str = "",
                 with_forecast: bool = False) -> tuple[list[Fact], list[Violation]]:
    """Extract facts and run every LLM probe. Returns (facts, violations).

    Order matters: extraction first, because the conflict judgement needs the new facts, and a
    scene whose facts cannot be extracted cannot be safely committed at all.
    """
    violations: list[Violation] = []

    try:
        facts = extract_facts(scene, story, models)
    except LLMError as exc:
        return [], [Violation("extraction_failed", Severity.BLOCKER,
                              f"could not extract facts, so continuity cannot be checked: {exc}",
                              "llm:extract_facts")]

    # An *empty* extraction is the dangerous case, and it used to pass silently. A real run on a
    # local 8B returned zero facts for a 591-word scene: the JSON parsed, so nothing errored, the
    # ledger stayed empty, and every later brief would have said "nothing established yet" while
    # the manuscript filled up. Continuity would fail with no error anywhere — the exact failure
    # mode the whole architecture exists to prevent.
    if not facts and scene.word_count() > 150:
        return facts, [Violation(
            "extraction_empty", Severity.BLOCKER,
            f"a {scene.word_count()}-word scene established no facts at all. Either the "
            f"extractor model is not up to structured output — try a stronger model for the "
            f"extractor role — or the scene genuinely establishes nothing, which is its own "
            f"problem. Committing it would leave the ledger blind to this scene.",
            "llm:extract_facts")]

    violations += judge_conflicts(facts, ledger, models)
    violations += check_threads(scene, spec, story, models)
    violations += probe_tells(scene, models)
    if with_forecast:
        violations += probe_forecast(scene, story_so_far, models)
    return facts, violations
