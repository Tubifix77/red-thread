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

from . import checks as _checks
from .ledger import Ledger, content_tokens
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
- HOW MANY. Most scenes establish between three and eight things a later scene could actually \
contradict. Record those and stop. Past ten you have started recording description, and a padded \
fact is worse than a missing one because it takes a place in every later brief that a real fact \
needed. NEVER MORE THAN 15. That is a hard limit and also not a target — a scene that establishes \
four things should return four.
- Atmosphere is not a fact. "the screen was flickering", "the room was cold", "her fingers were \
calloused" are description, and recording them turns every later scene into an argument with the \
weather. Everything here constrains the rest of the book and is fed into every later brief, so ten \
durable facts are worth more than forty transient ones.

SCENE {index} of "{title}":
---
{text}
---

{json_only}
Schema:
{{"facts": [{{"subject": "...", "predicate": "...", "object": "...", "kind": "state|knowledge|detail|event"}}]}}"""


# Knowledge first when the cap has to cut, because the prompt calls it "the most important kind"
# and a character acting on what they do not know is the failure the ledger exists to prevent.
# Details are fixed particulars and cannot be re-established later; states change but are what a
# later scene contradicts; an event is the kind the prompt says to use only when nothing else fits.
_FACT_PRIORITY = {FactKind.KNOWLEDGE: 0, FactKind.DETAIL: 1, FactKind.STATE: 2, FactKind.EVENT: 3}


def extract_facts(scene: Scene, story: StorySpec, models: Models,
                  max_facts: int = 15) -> list[Fact]:
    """Prose into quadruples.

    The cap is a backstop against over-recording, not a target. A real run on a local model
    returned 59 facts for a 689-word scene, mostly atmosphere, and that compounds badly: the
    ledger fills with transient description, every later brief is padded with it, and
    `conflict_candidates` starts manufacturing contradictions out of how the light was falling.

    **It is 15 because the prompt says 15**, and it said 30 while the prompt said 15 for as long
    as both have existed. The prompt's limit is the one that was being ignored: on a live run,
    11 of 46 scenes came back with 23 to 30 facts. Asking a model for a count and then not
    enforcing it is the one thing this project says never to do, in the one place it was doing it.

    When the cap has to cut, it cuts by durability rather than by whatever order the model
    happened to emit — see `_FACT_PRIORITY`.
    """
    prompt = EXTRACT_PROMPT.format(index=scene.index, title=story.title,
                                   text=_clip(scene.text, 2500), json_only=JSON_ONLY)
    # A tighter budget than the other probes, on purpose. Thirty facts is a small object, and an
    # unbounded budget does not stop a model that wants to enumerate: one run spent all 8000
    # tokens listing 258 facts for a 762-word scene and was truncated mid-object. Salvage in
    # `parse_json` recovers the complete elements either way; the cap keeps the cost bounded.
    reply = models.extractor.complete(prompt, max_tokens=3000,
                                      temperature=0.0, json_mode=True)
    data = parse_json(reply.text)
    rows = data.get("facts", []) if isinstance(data, dict) else data

    facts: list[Fact] = []
    for row in rows:
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

    if len(facts) <= max_facts:
        return facts
    # Stable within a priority band, so the model's own ordering still decides between two
    # facts of the same kind.
    keep = sorted(range(len(facts)), key=lambda i: (_FACT_PRIORITY[facts[i].kind], i))[:max_facts]
    return [facts[i] for i in sorted(keep)]


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
- the SAME fact recorded twice in different words — "X | has | read the records" and
  "X | has read | records" are one fact, not two, and repetition is never a contradiction
- one fact being more specific than the other ("carries a notebook", "carries a green notebook")
- WHERE something or someone is. A register on the table in one scene and in a drawer in another
  is a register somebody moved; a character in the office and later at the pass is a character
  who walked there. Position is never a contradiction.
- WHAT SOMEBODY IS HOLDING. A character carrying a blade in one scene and a bundle in another
  put one down and picked the other up. Carrying, holding, wearing, gripping, touching — none of
  these is a contradiction, for the same reason position is not.
- a transient physical description — warm, cold, damp, dusty, dark. Those change by the hour.

Each fact is labelled with the scene it comes from. Facts many scenes apart have had a great deal
of story in between; assume time passed unless the pair is from adjacent scenes.

A contradiction:
- the same unchanging detail given two different values (eye colour, a scar's location, a name)
- a character knowing something before the scene where they learn it
- a physical state that could not have changed between two ADJACENT scenes

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
    reply = models.critic.complete(prompt, max_tokens=STRUCTURED_BUDGET,
                                   temperature=0.0, json_mode=True)

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
    # One finding per pair. The same pair can be forwarded twice — once on the exact-key branch
    # and once on the near-synonym branch of `conflict_candidates` — and a live scene was held by
    # three blockers of which two were the same claim, each demanding its own repair round.
    seen: set[str] = set()
    unique: list[Violation] = []
    for violation in out:
        if violation.detail in seen:
            continue
        seen.add(violation.detail)
        unique.append(violation)
    return unique


# ======================================================================================
# 3. thread satisfaction — did the scene do its job?
# ======================================================================================

THREAD_PROMPT = """You are checking whether a scene fulfilled its brief. Judge only what the \
prose actually does, not what it seems to intend.

For each requirement, answer:
- "met"     — the scene brings this about, on the page
- "partial" — gestured at but not actually accomplished
- "missed"  — did not happen

If you are torn between "met" and "partial", decide it like this: could a reader point at the place where it happens? If yes, it is met. "Partial" is not for imperfect execution, it is for requirements whose substance is genuinely absent.

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
            # A post line that only names a state asks the judge the very question `to_state` is
            # withheld to avoid — whether the prose "reaches 'reoriented'". The commit applies
            # the state change either way; an unanswerable obligation only costs a scene.
            if thread and _checks.is_state_restatement(item, thread):
                continue
            # A post phrased as an absence is a prohibition wearing a requirement's clothes.
            # Scene 24 of a live run was told to bring about "the allegiances are neither
            # resolved nor abandoned", and no prose can evidence a thing not happening, so the
            # judge reported it missed however the scene went. Inverted, it becomes the pair of
            # events that must not happen — which is answerable, and is what it meant.
            if _checks.is_absence_post(item):
                inverted = _checks.positive_prohibition(item)
                if inverted:
                    forbidden.append((tid, f"[{label}] {inverted}"))
                continue
            # "Sofie makes the change without detection" is an event with an absence hung off
            # it. The event is confirmable by reading; the absence is not, and a live run
            # reported the whole line missed however the scene went.
            required.append((tid, f"[{label}] {_checks.verifiable_post(item)}"))
        # op.to_state is deliberately NOT given to the judge. State names are this system's
        # bookkeeping labels ("chosen", "paid_off"), not textual events — a judge asked whether
        # prose "ends the thread in state paid_off" can only hallucinate the mapping, and a real
        # finale was held back on exactly that. The concrete post lines above are the checkable
        # rendering of the transition; the state change itself is applied by Project.commit.
        for item in op.forbid:
            # A negated Forbid asks the judge an unanswerable question — "was 'X is not
            # finalized' violated?" — and a live run blocked scene 8 for doing exactly what its
            # own post line required. The planner means these as invariants, so strip the
            # negation and hand over the event they actually forbid.
            # `check_prohibition_phrasing` reports the plan so the next one is written right.
            if _checks.is_negated_prohibition(item):
                item = _checks.positive_prohibition(item)
                if not item:
                    continue
            # A disclosure prohibition on a thread whose concealment the schedule has already
            # lifted is the planner's stale copy of that concealment. `Thread.reveal_scene` is
            # the authority on when the reader may know; asking the judge to enforce the
            # opposite held scene 13 of a live run back for revealing what scene 10 unsealed.
            if (thread and thread.reveal_scene is not None
                    and spec.index >= thread.reveal_scene
                    and _checks.is_disclosure_prohibition(item)):
                continue
            forbidden.append((tid, f"[{label}] {item}"))
        if (thread and thread.concealment
                and (thread.reveal_scene is None or spec.index < thread.reveal_scene)):
            forbidden.append(
                (tid, f"[{label}] must NOT reveal to the reader: {thread.concealment}"))

    if not required and not forbidden:
        return []

    prompt = THREAD_PROMPT.format(
        required="\n".join(f"{i}. {text}" for i, (_, text) in enumerate(required)) or "(none)",
        forbidden="\n".join(f"{i}. {text}" for i, (_, text) in enumerate(forbidden)) or "(none)",
        text=_clip(scene.text, 2500), json_only=JSON_ONLY)
    reply = models.critic.complete(prompt, max_tokens=STRUCTURED_BUDGET,
                                   temperature=0.0, json_mode=True)

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
        # Advisory, not a gate. "Did this scene accomplish what it was for?" is a reading, not
        # a measurement — an authorial judgement wearing a verifier's clothes. Gating on a small
        # model's answer to it produced two failure modes and no successes: scenes held back for
        # obligations they had met, and — worse — a plan quietly rewritten until its instructions
        # were mechanically checkable. "Nils ignores the thermometer's reading" is a perfectly
        # writable beat that was deleted from a live plan because a judge could not confirm it
        # afterwards.
        #
        # So the verdict is reported to the author and the repair loop still tries to act on it,
        # but it cannot stop the book. The orchestrator gates on what code can check; the story
        # is the author's.
        out.append(Violation(
            "thread_obligation", Severity.MINOR,
            f"{verdict}: {text}", "llm:check_threads", str(row.get("evidence", ""))[:200]))

    for row in (data.get("prohibitions") or []):
        if not isinstance(row, dict) or not row.get("violated"):
            continue
        try:
            tid, text = forbidden[int(row.get("n", -1))]
        except (ValueError, TypeError, IndexError):
            continue
        # Also advisory, and this one was the most expensive to learn. The asymmetry is real —
        # once the reader knows, no later scene can un-know it — but the *detection* is a
        # reading, and an 8B reading for an absence is the least reliable judgement in the
        # system. As a BLOCKER it halted whole books on scenes that had disclosed nothing, and
        # every attempt to make it safe narrowed what the plan was allowed to say.
        #
        # The quote still matters: an evidenced leak names the sentence, which is what
        # `_surgical` and `_excise_leak` act on. It is reported prominently and repaired
        # best-effort; the author decides whether it really leaked.
        quote = str(row.get("quote", ""))[:200]
        evidenced = bool(quote) and _checks.locate_quote(scene.text, quote) is not None
        out.append(Violation(
            "thread_prohibition", Severity.MINOR,
            f"violated: {text}" + ("" if evidenced else " (judge gave no locatable quote)"),
            "llm:check_threads", quote if evidenced else ""))
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
    reply = models.critic.complete(prompt, max_tokens=STRUCTURED_BUDGET,
                                   temperature=0.0, json_mode=True)
    try:
        data = parse_json(reply.text)
    except LLMError:
        return []

    out: list[Violation] = []
    for row in (data.get("findings") if isinstance(data, dict) else data) or []:
        if not isinstance(row, dict) or not row.get("present"):
            continue
        tell = str(row.get("tell", "unknown"))
        quote = str(row.get("quote", ""))[:240]
        # Evidence check. A judge — a local one especially — will sometimes flag a tell and
        # "quote" a paraphrase of its own reasoning rather than the scene ("The narration
        # explicitly states the theme of…"). If the quoted words are not in the text, the
        # evidence was invented and the finding is not actionable: drop it entirely rather than
        # let a hallucinated judgement burn a repair round or hold a scene back.
        if quote and _checks.locate_quote(scene.text, quote) is None:
            continue
        # Advisory, always. Calibrated on the target judge (qwen3:8b, temperature 0, three
        # samples each): it flags the glossy fixture correctly 3/3 — and also flags "The tally
        # sheet had been photocopied so often that the column headings had closed up", a pure
        # physical description, as thematic gloss 3/3. A judge with a hard false-positive floor
        # will find a MAJOR in any scene, which as a blocking gate means nothing ever commits.
        # Blocking power for gloss belongs to the deterministic check, which passes the clean
        # fixture and catches the glossy one; these findings are kept as MINOR so a human
        # reading scenes/NNNN.json still sees them.
        out.append(Violation(
            f"tell_{tell}", Severity.MINOR,
            f"{_TELL_LABELS.get(tell, tell)}: {row.get('why', '')}",
            "llm:probe_tells", quote))
    return out


# ======================================================================================
# 5. forecastability — tension as unpredictability  (RESEARCH.md section 9)
# ======================================================================================

FORECAST_PROMPT = """Here is a novel's story so far, in summary.

Write what you think happens in the very next scene. Two or three sentences: who is there, what they do, and how it ends. Commit to a specific answer — the most likely continuation, not a hedge covering several.

STORY SO FAR:
{context}

{json_only}
Schema:
{{"prediction": "what happens next, 2-3 sentences"}}"""


def _stems(text: str) -> set[str]:
    """Content words with their commonest inflections stripped.

    Crude on purpose, and necessary: a prediction saying "demands the ledger" against a scene
    saying "demanded the ledger back" scored 0.71 without this, because two of its seven content
    words were the same verb in a different tense. Untensed comparison is not optional when one
    side is a forecast and the other is the past-tense prose that fulfilled it — every miss it
    invents biases the measure the same way, toward calling a predicted scene unpredictable.
    """
    out = set()
    for word in content_tokens(text):
        for suffix in ("ing", "ed", "es", "s"):
            if len(word) > len(suffix) + 2 and word.endswith(suffix):
                word = word[: -len(suffix)]
                break
        out.add(word)
    return out


def forecast_overlap(prediction: str, scene_text: str) -> float:
    """How much of a blind prediction the scene actually delivered, 0 to 1.

    Content words only, and scored as a share of the *prediction* rather than a symmetric
    similarity: a two-sentence guess against an eight-hundred-word scene can never be
    symmetrically similar to it, and what matters is whether the guess came true.
    """
    guess = _stems(prediction)
    if not guess:
        return 0.0
    return len(guess & _stems(scene_text)) / len(guess)


def probe_forecast(scene: Scene, story_so_far: str, models: Models,
                   threshold: float = 0.75) -> list[Violation]:
    """If a model can call the scene from the story so far, the scene has no tension.

    Narrative tension is downstream of hidden information and can be metered by how predictable
    upcoming events are (docs/RESEARCH.md section 9). The cited work measures the entropy of a
    forecasting distribution; this is a cruder single-sample proxy.

    **It had two flaws that made it worse than crude, and both are fixed here.** The prompt used
    to contain the actual scene and then ask the model to "predict it before reading what happens
    next" — the answer was in the question, so what came back was a rationalisation rather than a
    forecast. And the model then scored its own prediction, with the prompt pleading "be honest —
    a high score is useful information, not a failure on your part".

    Now the prediction is blind: the model sees the story so far and nothing else. The comparison
    is arithmetic — content-word overlap between what it guessed and what the scene contains —
    which is the same move `judge_conflicts` makes when it refuses a quote that does not locate.
    Ask the model for the thing only a model can produce, and do the measuring in code.

    **Calibrated against a corpus, and it does not discriminate. Do not enable this.**

    Run over 35 scenes of a finished 71-scene novel, the overlap distribution looks reasonable —
    mean .538, range .26 to .73. The control is what kills it. Scoring each prediction against
    the scene it was predicting gives .540; scoring the same prediction against a *random other
    scene from the same book* gives .492, and the scene actually predicted scores higher only
    **41% of the time**, which is worse than chance.

    Weighting words by rarity across the book — so cast names and recurring objects count for
    less — moves that to 51%. Still chance. A two-sentence prediction and an eight-hundred-word
    scene share too little distinctive vocabulary for lexical overlap to tell a correct forecast
    from a wrong one, and the words they do share are the book's furniture.

    Kept, off, and documented rather than deleted: the idea that tension is measurable as
    forecastability is sourced (RESEARCH.md section 9), the cited work measures the entropy of a
    forecasting distribution rather than one sample, and one book is one book. What is settled is
    that *this* implementation reports noise, and a number that looks like a measurement is worse
    than no number.
    """
    if not story_so_far.strip():
        return []
    prompt = FORECAST_PROMPT.format(context=_clip(story_so_far, 1200), json_only=JSON_ONLY)
    reply = models.critic.complete(prompt, max_tokens=STRUCTURED_BUDGET,
                                   temperature=0.0, json_mode=True)
    try:
        data = parse_json(reply.text)
    except LLMError:
        return []
    if not isinstance(data, dict):
        return []
    prediction = str(data.get("prediction", "")).strip()
    if not prediction:
        return []

    overlap = forecast_overlap(prediction, scene.text)
    if overlap < threshold:
        return []
    return [Violation(
        "low_tension", Severity.MINOR,
        f"a model shown only the story so far predicted {overlap:.0%} of this scene's content "
        f"without seeing it. Consider what this thread is still concealing.",
        "llm:probe_forecast", prediction[:240])]


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
