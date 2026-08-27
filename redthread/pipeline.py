"""The scene pipeline: the deterministic state machine that writes one scene.

    brief → draft N candidates → deterministic checks → pick → LLM verify
          → localised repair (bounded) → commit gate

Three properties this shape guarantees, each borrowed from a source in docs/RESEARCH.md:

1. **Nothing enters dynamic memory until it passes.** ConWriter updates memory only after a
   scene clears its checks, so a bad scene leaves no residue for later scenes to build on. The
   commit gate lives in `Project.commit`; this module never touches the ledger directly.
2. **Repair is local.** ConWriter revises only the conflict-bearing sentences rather than
   regenerating the scene. Regeneration throws away the good prose along with the bad and, worse,
   resamples every other check.
3. **Candidates then selection.** Re3 generates multiple continuations and reranks them. Here the
   ranking is done by the deterministic checks, which cost nothing — so drafting three
   candidates and keeping the cleanest is cheaper than one draft plus two repair rounds.

The orchestrator is code, not an agent. Agents' Room uses an LLM orchestrator with a scratchpad;
we use a state machine with a store, because the whole point is that state survives the session.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import checks, verify
from .brief import render_brief, tail_of
from .llm import LLMError, Models, strip_reasoning
from .models import Scene, SceneSpec, Severity, Violation
from .progress import Progress
from .project import Project

WRITER_SYSTEM = (
    "You are a novelist writing one scene of a longer book. You will be given a brief that is "
    "binding: the continuity facts are what the reader already knows, the thread requirements "
    "are what this scene must accomplish, and the prohibitions are absolute. Write prose only. "
    "Do not summarise, do not comment on your work, do not use headings. Trust the brief — if "
    "something is not in it, it has not happened yet."
)

REPAIR_PROMPT = """Below is a scene from a novel, followed by specific problems found in it.

Fix ONLY the problems listed. Rewrite the smallest span of text that fixes each one — a phrase, a
sentence, at most two sentences. Everything else must come back word for word identical.

Do not improve prose that was not flagged. Do not add or remove events. Do not change the length
by more than a few words. If fixing a problem would require restructuring the scene, leave that
problem and fix the others.

PROBLEMS:
{problems}

SCENE:
---
{text}
---

Return the complete corrected scene as prose, nothing else."""

# What to actually *do* about each kind of violation. The checks are good at saying what is wrong
# and were saying nothing about the remedy, which left a weak model to infer it — and a real run
# spent all three repair attempts returning prose that had not changed. A violation with an
# instruction attached is a task; one without is a complaint.
REMEDIES = {
    "style_leak": ("Find the sentence lifted from the style samples and write a different "
                   "sentence in the same rhythm. The samples show the register to match, not "
                   "text to reuse."),
    "brief_leak": ("Replace the sentence that restates the brief with the thing itself: the "
                   "action, the object, the words spoken."),
    "tell_thematic_gloss": ("Delete the sentence that names what the scene means. Do not replace "
                            "it with anything. The scene means it without saying so."),
    "thematic_gloss": ("Delete the realisation or summary clause. Keep only what a camera could "
                       "record."),
    "somatic_emotion": ("Replace the bodily-sensation lines with what the character does, or "
                        "refuses to do. Keep at most one."),
    "forbidden_phrase": "Rewrite the phrase. Any wording will do except that one.",
    "pov_person": ("Convert the narration to the contracted person. Dialogue keeps its own "
                   "pronouns."),
    "format": "Delete the heading, label, or commentary. Return prose only.",
    "seam_echo": ("Rewrite the opening so it continues from the previous scene instead of "
                  "restating its ending."),
    "seam_reset": "Replace the opening move; do not start with weather, waking, or a time label.",
    "thread_obligation": ("This did not happen on the page. Make it happen, concretely, in the "
                          "smallest number of sentences that will carry it."),
    "thread_prohibition": "Remove what was revealed. The reader must not learn it in this scene.",
    "continuity_contradiction": "Change the new detail to match what was established earlier.",
    "truncated_scene": ("The scene was cut off mid-sentence. End it properly at its last "
                        "complete beat instead."),
    "internal_repetition": "Vary the repeated phrasing.",
    "slop": "Replace the flagged phrasing with something plainer.",
}

# Violation kinds whose remedy is deletion of the offending sentence. For these, when the quote
# locates in the text, no model is needed at all: the sentence is spliced out in code. That is
# the cheapest possible repair and — for narrator-gloss, which lives in self-contained sentences
# like "And she knew that no one else would ever see it." — usually the correct one.
DELETE_KINDS = {"thematic_gloss", "tell_thematic_gloss"}

SENTENCE_PROMPT = """One sentence in a novel scene must be rewritten.

Problem with it: {detail}
How to fix it: {remedy}

It sits in this context:

  …{before}
  >>> {sentence}
  {after}…

Write the replacement sentence only. No quotation marks around it, no commentary, no restating
the context sentences. Match the voice of the context. One sentence, two at most."""


def _surgical(scene: Scene, spec: SceneSpec, violations: list[Violation], models: Models,
              notes: list[str], samples: list[str] | None = None,
              round_no: int = 0) -> str | None:
    """Sentence-local repair: splice out or rewrite only the offending sentences.

    This is what ConWriter's repair actually is — "revising only the conflict-bearing
    sentences" — and what the whole-scene REPAIR_PROMPT merely asked for. The difference
    matters on small local models: asked to return a full scene minus one flaw, an 8B
    regenerates the flaw or drifts elsewhere, and five consecutive whole-scene repairs on a
    real run changed nothing. Asked for one replacement sentence between two context
    sentences, the same model manages fine — and for DELETE_KINDS no model is needed at all.

    Returns the repaired text, or None when no violation's quote locates in the scene.
    """
    rank = {Severity.BLOCKER: 0, Severity.MAJOR: 1, Severity.MINOR: 2}
    spans: list[tuple[int, int, Violation]] = []
    for v in sorted(violations, key=lambda v: rank[v.severity]):
        if not v.quote:
            continue
        located = checks.locate_quote(scene.text, v.quote)
        if located is None:
            continue
        lo, hi = checks.sentence_covering(scene.text, located)
        # Skip a span already claimed by an earlier violation: two edits to one sentence
        # cannot both be applied, and the first is the more severe by sort order.
        if any(not (hi <= s_lo or lo >= s_hi) for s_lo, s_hi, _ in spans):
            continue
        spans.append((lo, hi, v))

    if not spans:
        return None

    text = scene.text
    # Deleting is free but costs words, and a real run deleted its way from 918 words to 772 —
    # under the length floor — while the judge kept finding new gloss. Delete only while the
    # scene can afford it; once at or below target, gloss sentences are rewritten into something
    # concrete instead, which holds the length while removing the tell.
    can_delete = scene.word_count() > spec.word_target
    for lo, hi, v in sorted(spans, key=lambda s: s[0], reverse=True):
        original = text[lo:hi].strip()
        if v.kind in DELETE_KINDS and can_delete:
            replacement = ""
            notes.append(f"surgical: deleted the {v.kind} sentence (no model call)")
        else:
            before = text[max(0, lo - 160):lo].strip()[-140:]
            after = text[hi:hi + 160].strip()[:140]
            remedy = REMEDIES.get(v.kind, "Rewrite it.")
            if v.kind == "forbidden_phrase":
                remedy = (f'The words "{v.quote}" must not appear in your sentence, in any '
                          f'form. Say the thing another way entirely.')
            if v.kind in DELETE_KINDS:
                remedy = ("Replace it with one concrete sentence: a physical action, a thing "
                          "seen, or words spoken. No meaning, no realisation, no summary.")
            prompt = SENTENCE_PROMPT.format(
                detail=v.detail[:220], remedy=remedy,
                before=before, sentence=original, after=after)
            try:
                # The temperature climbs with the round, past identical-prompt caching: a real
                # run got the same failed rewrite back in 0 seconds three rounds straight,
                # because nothing about the request had changed.
                reply = models.writer.complete(prompt, max_tokens=300,
                                               temperature=min(1.0, 0.6 + 0.15 * round_no))
            except LLMError:
                continue
            replacement = strip_reasoning(reply.text).strip().strip('"').strip()
            # A replacement three times the original has ignored the instruction; an empty one
            # is a deletion the kind did not ask for.
            if not replacement or len(replacement.split()) > 3 * max(4, len(original.split())):
                continue
            # Code-verified splices, wherever a deterministic test exists for the kind: the
            # writer that produced a flaw once tends to reproduce it inside its own "fix". A
            # real run rewrote a leaked sentence into one still sharing four 6-grams with the
            # sample, and rewrote gloss into fresh gloss. The checker decides, not the model's
            # promise; an unfixed replacement falls back to deletion when the length affords
            # it, else the span is skipped this round.
            failed_verify = False
            if v.kind == "style_leak" and samples:
                rep_grams = set(checks.ngrams(checks.words(replacement), 6))
                failed_verify = any(
                    rep_grams & set(checks.ngrams(checks.words(sample), 6))
                    for sample in samples)
            elif v.kind in DELETE_KINDS:
                # Verified in context, not in isolation: a replacement can pass alone and still
                # form a fresh gloss construction across the splice seam — a real run spliced a
                # clean sentence after "…, but because" and produced "because she knew that…".
                spliced_region = (text[max(0, lo - 80):lo] + replacement
                                  + text[hi:hi + 80])
                probe = Scene(spec_id=scene.spec_id, index=scene.index, text=spliced_region)
                failed_verify = bool(checks.check_thematic_gloss(probe))
            elif v.kind == "forbidden_phrase":
                # Told "any wording will do except that one", a real run's writer returned the
                # sentence with the banned phrase intact, four rounds straight, each served
                # instantly from cache. The phrase's absence is checkable in one line.
                failed_verify = v.quote.lower() in replacement.lower()
            if failed_verify:
                if can_delete:
                    # A sentence that fails verification twice is better gone than kept, and
                    # the length budget says the scene can afford it.
                    replacement = ""
                    notes.append(f"surgical: {v.kind} rewrite failed verification; deleted")
                else:
                    notes.append(f"surgical: {v.kind} rewrite failed verification; skipped")
                    continue
            notes.append(f"surgical: rewrote the {v.kind} sentence")
        gap = " " if replacement else ""
        text = (text[:lo].rstrip() + gap + replacement + gap
                + text[hi:].lstrip()) if replacement else (
                text[:lo].rstrip() + " " + text[hi:].lstrip())

    text = text.strip()
    return text if text != scene.text.strip() else None


TRIM_PROMPT = """This scene is {actual} words. Its target is {target} words, so it has run
about {over} words past its brief — usually by continuing past where the scene should stop, or
by staging material that belongs to later scenes.

Cut it to roughly {target} words. Rules:

- Remove whole sentences and whole passages; do not compress good sentences into worse ones.
- Anything after the scene's last required beat is the first candidate to go: find where the
  scene should have ended, and end it there.
- Keep every beat listed below. Do not add anything new.
- The sentences you keep must survive word for word.

The beats this scene owes, in order:
{beats}

SCENE:
---
{text}
---

Return the complete trimmed scene as prose, nothing else."""

EXPAND_PROMPT = """This scene is {actual} words. Its target is {target} words, so it is short by
about {short}. A short scene almost always means beats were skipped or summarised.

Expand it to the target. Rules:

- Keep every sentence already written. You are deepening, not rewriting.
- Add nothing new to the plot: no new events, no new characters, no new facts about the world.
  Anything you add must be a closer look at something already there.
- Spend the words on the beats that are thinnest — where the scene currently summarises an action
  in one line, stage it instead: the physical steps, what is said, what is not said.
- Do not pad with reflection or interiority. Do not explain what anything means.

The beats this scene owes, in order:
{beats}

SCENE:
---
{text}
---

Return the complete expanded scene as prose, nothing else."""


@dataclass
class SceneResult:
    scene: Scene
    violations: list[Violation] = field(default_factory=list)
    committed: bool = False
    attempts: int = 0
    candidates_drafted: int = 0
    repairs: int = 0
    notes: list[str] = field(default_factory=list)

    def blockers(self) -> list[Violation]:
        return [v for v in self.violations if v.severity is Severity.BLOCKER]

    def majors(self) -> list[Violation]:
        return [v for v in self.violations if v.severity is Severity.MAJOR]

    def summary(self) -> str:
        state = "committed" if self.committed else "REJECTED"
        counts = f"{len(self.blockers())} blocker, {len(self.majors())} major"
        return (f"scene {self.scene.index}: {state} — {self.scene.word_count()} words, "
                f"{counts}, {self.candidates_drafted} draft(s), {self.repairs} repair(s)")


@dataclass
class Config:
    candidates: int = 3
    """Drafts per scene. Selection is by deterministic check score, which is free."""
    max_repairs: int = 2
    """ConWriter repairs within bounded retry loops. Unbounded repair loops oscillate."""
    temperature: float = 1.0
    slop_sample: int = 12
    """How many slop phrases to name in the brief. The full list would swamp the prompt; the
    check catches the rest afterwards."""
    with_forecast: bool = False
    """The tension probe costs an extra call per scene. Off by default; worth running on
    midpoint scenes."""
    allow_commit_with_majors: bool = False
    """If a scene still has MAJOR violations after the repair budget, commit anyway or stop.
    Default is to stop: a manuscript that silently accumulates majors is the failure mode this
    whole architecture exists to prevent."""
    allow_out_of_order: bool = False
    """Write a scene whose predecessor is not committed. Off by default — see `write_scene`."""


def _prose_budget(words: int, backend=None) -> int:
    """Output budget for a call that must return a whole scene.

    Two tokens per word plus a small margin, and then whatever the backend needs for inline
    reasoning. Both halves came from real failures pulling in opposite directions: repair failed
    in twelve seconds on an 897-word scene because the budget covered the prose but not the
    reasoning that preceded it, and a draft ran to 5702 words against a 900-word target because a
    budget loose enough for reasoning is also loose enough to ramble — a minute of generation
    spent on a scene that was going to be rejected anyway.

    Asking the backend closes the gap: where reasoning is switched off, or returned in its own
    field, the overhead is zero and the budget can be tight.
    """
    overhead = getattr(backend, "reasoning_overhead", 4000) if backend is not None else 4000
    # 1.5 tokens per word puts the ceiling near 1.3x the target. That makes a 2x runaway
    # physically impossible — the climax scenes of a real run came back at 2973 and 3062 words
    # against a 1300 target, and five trims could not close a gap that size. A draft that hits
    # the ceiling ends mid-sentence instead, which `check_truncated` catches deterministically
    # and the trim path repairs at a sentence boundary. Bounded-and-detectable beats unbounded.
    return min(32000, int(words * 1.5) + 250 + overhead)


def _score(violations: list[Violation]) -> tuple[int, int, int]:
    """Sort key for candidate selection. Lower is better."""
    return (
        sum(1 for v in violations if v.severity is Severity.BLOCKER),
        sum(1 for v in violations if v.severity is Severity.MAJOR),
        sum(1 for v in violations if v.severity is Severity.MINOR),
    )


def _preceding_gap(project: Project, spec: SceneSpec) -> int | None:
    """The index of the nearest earlier planned scene that is not committed, if any."""
    earlier = [s for s in project.plan if s.index < spec.index]
    for candidate in sorted(earlier, key=lambda s: s.index, reverse=True):
        scene = project.scene(candidate.id)
        if scene is None or not scene.committed:
            return candidate.index
    return None


def write_scene(project: Project, spec: SceneSpec, models: Models,
                config: Config | None = None,
                progress: "Progress | None" = None) -> SceneResult:
    config = config or Config()
    # A quiet Progress rather than None-checks at every call site: the stage hooks are on the
    # hot path of a long run and littering them with `if progress:` obscures the pipeline.
    progress = progress or Progress(quiet=True)

    # Order matters more here than it looks. Every brief is assembled from committed state, so
    # writing scene 7 before scene 6 means writing against a ledger that is missing a scene's
    # facts and a seam that has no previous text — the two things this architecture exists to
    # supply. Fail loudly rather than produce a scene that looks fine and is unmoored.
    gap = _preceding_gap(project, spec)
    if gap is not None and not config.allow_out_of_order:
        result = SceneResult(scene=Scene(spec_id=spec.id, index=spec.index))
        result.violations = [Violation(
            "out_of_order", Severity.BLOCKER,
            f"scene {gap} is not committed, so scene {spec.index} would be written with no "
            f"previous text and an incomplete ledger. Write scenes in order, or set "
            f"allow_out_of_order if you know why you want this.", "pipeline")]
        result.scene.violations = result.violations
        return result

    previous = project.previous_committed(spec.index)
    previous_tail = tail_of(previous.text) if previous else ""
    previous_spec = project.spec(previous.spec_id) if previous else None
    previous_characters = previous_spec.characters if previous_spec else []
    committed_texts = project.committed_texts(before=spec.index)

    slop_sample = checks.slop_sample(config.slop_sample)

    brief = render_brief(spec, project.story, project.ledger, previous_tail,
                         previous_characters, slop_sample)
    progress.stage("brief", f"{len(brief.split()):,} words in, "
                            f"{len(project.ledger.as_of(spec.index - 1))} facts available")

    result = SceneResult(scene=Scene(spec_id=spec.id, index=spec.index))

    # ---------------------------------------------------------------- draft candidates
    def run_deterministic(text: str) -> tuple[Scene, list[Violation]]:
        candidate = Scene(spec_id=spec.id, index=spec.index, text=strip_reasoning(text))
        found = checks.run_all(candidate, spec, project.story, previous_tail,
                               previous_characters, committed_texts)
        return candidate, found

    scored: list[tuple[tuple[int, int, int], Scene, list[Violation]]] = []
    wanted = max(1, config.candidates)
    for attempt in range(wanted):
        try:
            reply = models.writer.complete(
                brief, system=WRITER_SYSTEM,
                max_tokens=_prose_budget(spec.word_target, models.writer),
                temperature=config.temperature)
        except LLMError as exc:
            result.notes.append(f"draft failed: {exc}")
            progress.stage(f"draft {attempt + 1}/{wanted}", f"failed: {exc}")
            continue
        result.candidates_drafted += 1
        candidate, found = run_deterministic(reply.text)
        scored.append((_score(found), candidate, found))
        blockers, majors, minors = _score(found)
        progress.stage(f"draft {attempt + 1}/{wanted}",
                       f"{candidate.word_count()}w · {blockers}B/{majors}M/{minors}m")

    if not scored:
        result.violations = [Violation("no_draft", Severity.BLOCKER,
                                       "every draft attempt failed", "pipeline")]
        result.scene.violations = result.violations
        return result

    # Violation tuples tie often (two drafts, one major each). Distance to the word target
    # breaks the tie — a real run kept a 2.4x runaway over an on-length draft because the sort
    # was stable and the runaway arrived first.
    scored.sort(key=lambda row: (row[0], abs(row[1].word_count() - spec.word_target)))
    _, scene, det_violations = scored[0]
    result.scene = scene
    if len(scored) > 1:
        result.notes.append(
            f"selected best of {len(scored)} candidates (scores: "
            + ", ".join(str(s) for s, _, _ in scored) + ")")

    # ------------------------------------------------- phase A: deterministic repair loop
    # The repair loop is driven by deterministic checks alone. It used to re-run the full LLM
    # verify after every attempt, and that shape deadlocked a real run four rounds straight: the
    # surgical fix removed the one deterministic major, then the judge — on near-identical
    # text — flipped a binary verdict it had passed before, injecting a fresh MAJOR that made
    # every attempt score as "no improvement". Judges are for judging, once; loops need stable
    # measures. This is also most of the scene's latency: one LLM verify instead of 1+N.
    story_so_far = "\n\n".join(t[-800:] for t in committed_texts[-3:])

    def attempt_fix(fixable: list[Violation]) -> str | None:
        short = next((v for v in fixable if v.kind == "length"
                      and scene.word_count() < spec.word_target), None)
        if short is not None:
            return _expand(scene, spec, models, round_no=result.repairs), "expand"
        if any(v.kind == "truncated_scene" for v in fixable):
            # Snap to the last complete sentence, in code. A truncated draft is the budget cap
            # doing its job; asking a model to "trim" it just regenerates at length — a real
            # finale burned four rounds that way. The cap sits near 1.3–1.5x target, so the
            # snapped scene lands in at worst minor-over territory.
            terminal = set('.!?…"\'') | {"”", "’"}
            complete = [hi for _, hi in checks.sentence_spans(scene.text)
                        if scene.text[:hi].rstrip()[-1:] in terminal]
            return (scene.text[:complete[-1]] if complete else None), "snap"
        if any(v.kind == "length_runaway" for v in fixable):
            return _trim(scene, spec, models, round_no=result.repairs), "trim"
        quoteless = [v for v in fixable
                     if not (v.quote and checks.locate_quote(scene.text, v.quote))]
        if quoteless:
            return _repair(scene, fixable, models, config), "repair"
        repaired = _surgical(scene, spec, fixable, models, result.notes,
                             samples=project.story.style.samples, round_no=result.repairs)
        if repaired is None:
            return _repair(scene, fixable, models, config), "repair"
        return repaired, "surgical"

    for _ in range(config.max_repairs):
        fixable = [v for v in det_violations
                   if v.severity in (Severity.BLOCKER, Severity.MAJOR)]
        if not fixable:
            break
        repaired, action = attempt_fix(fixable)
        if repaired is None:
            # Consume a round and try again with the temperature bumped, rather than forfeiting
            # the whole budget: a single unusable trim reply used to `break` here, leaving a
            # runaway scene unrepaired with three rounds still in hand.
            result.repairs += 1
            result.notes.append(f"{action} attempt {result.repairs} unusable; retrying")
            progress.stage(f"{action} {result.repairs}", "call failed or unusable · retrying")
            continue
        result.repairs += 1

        candidate, new_det = run_deterministic(repaired)
        improved = _score(new_det) < _score(det_violations)
        fixed_length = (
            (action == "expand"
             and any(v.kind == "length" for v in det_violations)
             and not any(v.kind == "length" for v in new_det))
            or (action in ("trim", "snap")
                and any(v.kind in ("length_runaway", "truncated_scene")
                        for v in det_violations)
                and not any(v.kind in ("length_runaway", "truncated_scene")
                            for v in new_det)))
        if not (improved or fixed_length):
            result.notes.append(f"{action} attempt {result.repairs} did not improve; discarded")
            progress.stage(f"{action} {result.repairs}", "no improvement · discarded")
            continue
        scene, result.scene = candidate, candidate
        det_violations = new_det
        blockers, majors, minors = _score(new_det)
        progress.stage(f"{action} {result.repairs}",
                       f"{candidate.word_count()}w · {blockers}B/{majors}M/{minors}m"
                       + ("  (length resolved)" if fixed_length and not improved else ""))

    # ------------------------------------------------- phase B: one LLM verify
    facts, llm_violations = verify.verify_scene(
        scene, spec, project.story, project.ledger, models, story_so_far,
        with_forecast=config.with_forecast)
    scene.facts = facts
    result.violations = det_violations + llm_violations
    blockers, majors, minors = _score(result.violations)
    progress.stage("verify", f"{len(facts)} facts extracted · {blockers}B/{majors}M/{minors}m")

    # ------------------------------------------------- phase C: one bounded response pass
    # The judge gets one answer, not a negotiation. Its evidence-located findings get a single
    # surgical pass plus one re-verify; quoteless "missed" obligations get one whole-scene
    # repair. Whatever remains after that decides the gate.
    serious = [v for v in llm_violations
               if v.severity in (Severity.BLOCKER, Severity.MAJOR)]
    if serious and config.max_repairs > 0:
        located = [v for v in serious
                   if v.quote and checks.locate_quote(scene.text, v.quote)]
        repaired = None
        if located:
            repaired = _surgical(scene, spec, serious, models, result.notes,
                                 samples=project.story.style.samples)
            action = "surgical"
        if repaired is None:
            repaired = _repair(scene, serious, models, config)
            action = "repair"
        if repaired is None:
            result.notes.append(f"{action} call failed; keeping previous draft")
            progress.stage(f"{action} {result.repairs + 1}", "call failed or unusable")
        if repaired is not None:
            result.repairs += 1
            candidate, new_det = run_deterministic(repaired)
            if not [v for v in new_det if v.severity is Severity.BLOCKER]:
                try:
                    facts, llm_violations = verify.verify_scene(
                        candidate, spec, project.story, project.ledger, models,
                        story_so_far, with_forecast=False)
                except LLMError as exc:
                    result.notes.append(f"re-verify failed: {exc}")
                else:
                    candidate.facts = facts
                    new_all = new_det + llm_violations
                    if _score(new_all) < _score(result.violations):
                        scene, result.scene = candidate, candidate
                        det_violations = new_det
                        result.violations = new_all
                        blockers, majors, minors = _score(new_all)
                        progress.stage(
                            f"{action} {result.repairs}",
                            f"{candidate.word_count()}w · "
                            f"{blockers}B/{majors}M/{minors}m")
                    else:
                        result.notes.append(
                            f"{action} response to the verify did not improve; discarded")
                        progress.stage(f"{action} {result.repairs}",
                                       "no improvement · discarded")

    # ---------------------------------------------------------------- commit gate
    scene.violations = result.violations
    scene.attempts = result.candidates_drafted + result.repairs
    result.attempts = scene.attempts

    if result.blockers():
        project.rollback(scene)
        project.put_scene(scene)
        return result
    if result.majors() and not config.allow_commit_with_majors:
        project.rollback(scene)
        project.put_scene(scene)
        result.notes.append(
            "held back: MAJOR violations remain after the repair budget. Re-run with a revised "
            "spec, or set allow_commit_with_majors to accept it.")
        return result

    project.commit(scene)
    result.committed = True
    progress.stage("commit", f"{len(scene.facts)} facts into the ledger")
    return result


def _repair(scene: Scene, violations: list[Violation], models: Models,
            config: Config) -> str | None:
    """Rewrite only the flagged spans.

    The quotes carried on each Violation are what make this possible — a violation that says
    "the prose explains the theme" is unactionable, while one that quotes the offending sentence
    localises the fix to a span. That is why `Violation.quote` exists.
    """
    lines = []
    for i, v in enumerate(violations, 1):
        lines.append(f"{i}. {v.detail}")
        if v.quote:
            lines.append(f'   Offending text: "{v.quote}"')
        remedy = REMEDIES.get(v.kind)
        if remedy:
            lines.append(f"   Fix: {remedy}")
    prompt = REPAIR_PROMPT.format(problems="\n".join(lines), text=scene.text)
    try:
        reply = models.writer.complete(prompt, system=WRITER_SYSTEM,
                                       max_tokens=_prose_budget(scene.word_count(), models.writer),
                                       temperature=0.6)
    except LLMError:
        return None
    text = strip_reasoning(reply.text)
    # A "repair" that returns a third of the scene has rewritten, not repaired.
    if len(text.split()) < scene.word_count() * 0.6:
        return None
    return text


def _trim(scene: Scene, spec: SceneSpec, models: Models, round_no: int = 0) -> str | None:
    """Shrink a runaway scene toward its target.

    The counterpart of `_expand`, and just as necessary: the whole-scene repair prompt forbids
    changing the length, so a runaway scene sent there is unfixable by construction — a real run
    burned four 52-second repairs on a 2.4x overrun that none of them were allowed to fix.
    """
    beats = "\n".join(f"  {i}. {b.summary}"
                      for i, b in enumerate(spec.beats, 1)) or "  (none)"
    prompt = TRIM_PROMPT.format(
        actual=scene.word_count(), target=spec.word_target,
        over=max(0, scene.word_count() - spec.word_target), beats=beats, text=scene.text)
    try:
        reply = models.writer.complete(
            prompt, system=WRITER_SYSTEM,
            max_tokens=_prose_budget(spec.word_target, models.writer),
            temperature=min(1.0, 0.4 + 0.2 * round_no))
    except LLMError:
        return None
    text = strip_reasoning(reply.text)
    # A "trim" that grew is not a trim. One that over-cut is still progress — the length checks
    # flag it and the expand path pulls it back up — so the floor is generous: a real run
    # rejected a usable trim, hit `break`, and forfeited the whole repair budget over it.
    if not (spec.word_target * 0.5 <= len(text.split()) < scene.word_count()):
        return None
    return text


def _expand(scene: Scene, spec: SceneSpec, models: Models, round_no: int = 0) -> str | None:
    """Grow an under-length scene toward its target without adding plot.

    Kept separate from `_repair` because the two instructions are contradictory: repair must not
    change the length, and this must. Conflating them meant a short scene could never be salvaged.
    """
    beats = "\n".join(f"  {i}. {b.summary}"
                      for i, b in enumerate(spec.beats, 1)) or "  (none)"
    prompt = EXPAND_PROMPT.format(
        actual=scene.word_count(), target=spec.word_target,
        short=max(0, spec.word_target - scene.word_count()), beats=beats, text=scene.text)
    try:
        reply = models.writer.complete(
            prompt, system=WRITER_SYSTEM,
            max_tokens=_prose_budget(spec.word_target, models.writer),
            temperature=min(1.0, 0.8 + 0.1 * round_no))
    except LLMError:
        return None
    text = strip_reasoning(reply.text)
    # An "expansion" that came back shorter has rewritten rather than expanded.
    if len(text.split()) <= scene.word_count():
        return None
    return text


def write_all(project: Project, models: Models, config: Config | None = None,
              start: int = 1, stop: int | None = None,
              on_result=None, progress: Progress | None = None) -> list[SceneResult]:
    """Write every planned scene in order, halting on the first scene that will not commit.

    Halting is deliberate. Every later scene's brief is built from committed state, so
    continuing past a rejected scene means writing against a ledger that is missing a scene's
    worth of facts — which manufactures exactly the incoherence the system is for.

    The project is saved after every scene, so an interrupted run resumes from where it stopped
    rather than starting over. On a manuscript-length run that is the difference between an
    inconvenience and losing hours of generation.
    """
    progress = progress or Progress.for_project(project, quiet=True)
    results: list[SceneResult] = []
    for spec in sorted(project.plan, key=lambda s: s.index):
        if spec.index < start or (stop is not None and spec.index > stop):
            continue
        existing = project.scene(spec.id)
        if existing and existing.committed:
            continue

        progress.scene_start(spec, project.story)
        result = write_scene(project, spec, models, config, progress)
        results.append(result)
        project.save()
        progress.scene_done(result)
        if on_result:
            on_result(result)
        if not result.committed:
            break
    project.write_manuscript()
    progress.summary(project.story)
    return results
