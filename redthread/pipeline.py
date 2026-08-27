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
                max_tokens=min(32000, int(spec.word_target * 3) + 1000),
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

    scored.sort(key=lambda row: row[0])
    _, scene, det_violations = scored[0]
    result.scene = scene
    if len(scored) > 1:
        result.notes.append(
            f"selected best of {len(scored)} candidates (scores: "
            + ", ".join(str(s) for s, _, _ in scored) + ")")

    # ---------------------------------------------------------------- verify
    story_so_far = "\n\n".join(t[-800:] for t in committed_texts[-3:])
    facts, llm_violations = verify.verify_scene(
        scene, spec, project.story, project.ledger, models, story_so_far,
        with_forecast=config.with_forecast)
    scene.facts = facts
    result.violations = det_violations + llm_violations
    blockers, majors, minors = _score(result.violations)
    progress.stage("verify", f"{len(facts)} facts extracted · {blockers}B/{majors}M/{minors}m")

    # ---------------------------------------------------------------- localised repair
    for _ in range(config.max_repairs):
        fixable = [v for v in result.violations
                   if v.severity in (Severity.BLOCKER, Severity.MAJOR)]
        if not fixable:
            break

        # A short scene cannot be fixed by the repair prompt, which forbids changing the length.
        # Sending it there produced a real run where 564 words "repaired" to 591 and the scene
        # was held back anyway. Under-length is an expansion job, and it goes first: once the
        # scene is the right size, the remaining problems are repairable in place.
        short = next((v for v in fixable if v.kind == "length"
                      and scene.word_count() < spec.word_target), None)
        if short is not None:
            repaired = _expand(scene, spec, models)
            action = "expand"
        else:
            repaired = _repair(scene, fixable, models, config)
            action = "repair"

        if repaired is None:
            result.notes.append(f"{action} call failed; keeping previous draft")
            progress.stage(f"{action} {result.repairs + 1}", "call failed or unusable")
            break
        result.repairs += 1

        candidate, det_violations = run_deterministic(repaired)
        try:
            facts, llm_violations = verify.verify_scene(
                candidate, spec, project.story, project.ledger, models, story_so_far,
                with_forecast=False)
        except LLMError as exc:
            result.notes.append(f"re-verify failed: {exc}")
            break
        candidate.facts = facts
        new_violations = det_violations + llm_violations

        # Only accept the repair if it actually improved things. A repair that trades one
        # blocker for another is not progress, and accepting it is how oscillation starts.
        if _score(new_violations) >= _score(result.violations):
            result.notes.append("repair did not improve the scene; reverted")
            progress.stage(f"{action} {result.repairs}", "no improvement · reverted")
            break
        scene, result.scene = candidate, candidate
        result.violations = new_violations
        blockers, majors, minors = _score(new_violations)
        progress.stage(f"{action} {result.repairs}",
                       f"{candidate.word_count()}w · {blockers}B/{majors}M/{minors}m")

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
        lines.append(f"{i}. [{v.kind}] {v.detail}")
        if v.quote:
            lines.append(f"   Offending text: \"{v.quote}\"")
    prompt = REPAIR_PROMPT.format(problems="\n".join(lines), text=scene.text)
    try:
        reply = models.writer.complete(prompt, system=WRITER_SYSTEM,
                                        max_tokens=min(32000, len(scene.text) // 2 + 2000),
                                        temperature=0.6)
    except LLMError:
        return None
    text = strip_reasoning(reply.text)
    # A "repair" that returns a third of the scene has rewritten, not repaired.
    if len(text.split()) < scene.word_count() * 0.6:
        return None
    return text


def _expand(scene: Scene, spec: SceneSpec, models: Models) -> str | None:
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
            max_tokens=min(32000, int(spec.word_target * 3) + 1000), temperature=0.8)
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
