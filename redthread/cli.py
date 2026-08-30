"""Command line interface.

Deliberately, three of these commands need no API key at all — `brief`, `check` and `audit`.
Those are the ones that tell you whether the architecture is working. If the brief does not
read as a complete, unambiguous instruction to a writer who has amnesia, no model will save it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import checks
from .brief import render_brief, tail_of
from .models import Scene, Severity
from .schedule import DEFAULT_SCENE_WORDS
from .ollama import DEFAULT_OPENAI_BASE as DEFAULT_OLLAMA_BASE
from .project import Project


def _load(path: str) -> Project:
    root = Path(path)
    if not (root / "story.json").exists():
        raise SystemExit(f"no project at {root} (expected story.json)")
    return Project.load(root)


def _print_violations(violations, header: str) -> int:
    order = {Severity.BLOCKER: 0, Severity.MAJOR: 1, Severity.MINOR: 2}
    violations = sorted(violations, key=lambda v: order[v.severity])
    print(f"\n{header}")
    if not violations:
        print("  clean")
        return 0
    for v in violations:
        print(f"  {v}")
    blockers = sum(1 for v in violations if v.severity is Severity.BLOCKER)
    majors = sum(1 for v in violations if v.severity is Severity.MAJOR)
    minors = len(violations) - blockers - majors
    print(f"\n  {blockers} blocker, {majors} major, {minors} minor")
    return blockers + majors


# --------------------------------------------------------------------------------------

def cmd_audit(args) -> int:
    """Plan-level checks. Both acceptance markers, before a word is generated."""
    project = _load(args.project)
    violations = checks.audit_plan(project.plan, project.story, project.history)
    problems = _print_violations(violations, f"Plan audit — {project.story.title}")

    print("\nThread coverage:")
    scene_map = checks.thread_scene_map(project.plan)
    for thread in project.story.threads:
        scenes = scene_map.get(thread.id, [])
        seq = checks.planned_state_sequence(project.plan, thread.id)
        arc = " → ".join(s for _, s in seq) or "(no state changes)"
        print(f"  {thread.id:14} {thread.kind.value:12} scenes {scenes or '—'}")
        print(f"  {'':14} {arc}")
    return 1 if problems else 0


def cmd_brief(args) -> int:
    """Print a scene brief. No model call — this is the inspection tool."""
    project = _load(args.project)
    spec = project.spec_at(args.scene)
    if spec is None:
        raise SystemExit(f"no scene {args.scene} in the plan")

    previous = project.previous_committed(spec.index)
    previous_spec = project.spec(previous.spec_id) if previous else None
    brief = render_brief(
        spec, project.story, project.ledger,
        tail_of(previous.text) if previous else "",
        previous_spec.characters if previous_spec else [],
        checks.slop_sample(12))
    print(brief)
    if args.out:
        Path(args.out).write_text(brief, encoding="utf-8")
        print(f"\n[written to {args.out}]", file=sys.stderr)
    return 0


def cmd_check(args) -> int:
    """Run the deterministic checks against prose from a file. No model call.

    This is how you test the checks themselves: hand it a passage with a deliberate
    contradiction or four tightening chests and confirm the right violations come back.
    """
    project = _load(args.project)
    spec = project.spec_at(args.scene)
    if spec is None:
        raise SystemExit(f"no scene {args.scene} in the plan")

    text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
    scene = Scene(spec_id=spec.id, index=spec.index, text=text.strip())

    previous = project.previous_committed(spec.index)
    previous_spec = project.spec(previous.spec_id) if previous else None
    violations = checks.run_all(
        scene, spec, project.story,
        tail_of(previous.text) if previous else "",
        previous_spec.characters if previous_spec else [],
        project.committed_texts(before=spec.index))
    problems = _print_violations(
        violations, f"Deterministic checks — scene {spec.index} ({scene.word_count()} words)")
    return 1 if problems else 0


def cmd_models(args) -> int:
    """What is actually installed in Ollama. No guessing about model names."""
    from .ollama import OllamaUnavailable, list_installed

    try:
        installed = list_installed(args.base_url)
    except OllamaUnavailable as exc:
        print(f"{exc}")
        return 1

    if not installed:
        print("Ollama is running but no models are installed.")
        print("  ollama pull qwen3:8b")
        return 1

    print(f"\nInstalled in Ollama ({args.base_url}):\n")
    for model in installed:
        tags = []
        if args.vram:
            tags.append("fits" if model.fits_in(args.vram) else "TOO LARGE")
        if model.is_embedding:
            tags.append("embedding, not a writer")
        suffix = f"   [{', '.join(tags)}]" if tags else ""
        print(f"  {model.describe()}{suffix}")

    if args.vram:
        print(f"\n  Fit is weights + 1.5 GB headroom against {args.vram} GB, and it ignores "
              f"the KV cache,\n  which grows with context length. Treat it as a shortlist, not "
              f"a guarantee — confirm by loading.")

    # Suggest the largest *generative* model that plausibly fits, not merely the first row —
    # which on a typical install is an embedding model and cannot write anything.
    usable = [m for m in installed
              if not m.is_embedding and (not args.vram or m.fits_in(args.vram))]
    if usable:
        print(f"\n  Use one:  python -m redthread write {args.project} "
              f"--local {usable[-1].name}")
        print(f"  Compare:  python -m redthread bench {args.project} --scene 1 "
              f"--local {usable[-1].name} --local {usable[0].name}\n")
    return 0


def _build_models(args):
    """Resolve the model configuration, failing early on a name Ollama does not have."""
    from .llm import Models
    from .ollama import OllamaUnavailable, resolve

    if args.local or args.all_local:
        name = args.local or args.all_local
        try:
            name = resolve(name, args.base_url)
        except OllamaUnavailable as exc:
            raise SystemExit(f"{exc}")
        # Ollama's native API by default: it takes `think`, and returns any reasoning in its own
        # field instead of inline. --openai-compat is the escape hatch for vLLM, LM Studio and
        # llama.cpp, which lose both.
        native = not getattr(args, "openai_compat", False)

        # A second local model for the critic and extractor roles. They want different things
        # from the writer: careful reading and reliable structure rather than a good ear, and a
        # critic that cannot repair what it flags stalls the whole loop.
        critic_name = getattr(args, "local_critic", None)
        if critic_name:
            try:
                critic_name = resolve(critic_name, args.base_url)
            except OllamaUnavailable as exc:
                raise SystemExit(f"{exc}")
        return (Models.local(name, critic_name, args.base_url, native=native),
                name, critic_name or name)

    if getattr(args, "hosted", None) is None and not getattr(args, "writer", None):
        raise SystemExit("give --local MODEL (see: python -m redthread models .)")
    return Models.anthropic(args.writer, args.critic), args.writer, args.critic


def cmd_write(args) -> int:
    from .pipeline import Config, write_all, write_scene
    from .progress import Progress

    project = _load(args.project)

    # `audit` sits between planning and writing precisely so a structural failure is found
    # before the hours are spent, and nothing was enforcing that. A live plan came back with one
    # thread and no subplot — the audit said so, `plan` exited non-zero, and `write` started
    # anyway and spent three scenes on it. Generating a manuscript against a plan the audit has
    # already rejected is the expensive way to learn what it told you for free.
    findings = [v for v in checks.audit_plan(project.plan, project.story, project.history)
                if v.severity is not Severity.MINOR]
    if findings and not args.force:
        _print_violations(findings, f"Plan audit — {project.story.title}")
        print()
        print("The plan has unresolved structural findings. Fix them, re-plan, or pass "
              "--force to write anyway.")
        return 2

    models, writer_name, critic_name = _build_models(args)

    config = Config(candidates=args.candidates, max_repairs=args.repairs,
                    with_forecast=args.forecast,
                    allow_commit_with_majors=args.force,
                    refrain_feedback=not args.no_refrain_feedback,
                    gesture_feedback=not args.no_gesture_feedback,
                    model_refrains=not args.no_model_refrains)

    progress = Progress.for_project(project, quiet=args.quiet)
    progress.run_header(project.story, writer_name, critic_name)

    if args.scene is not None:
        spec = project.spec_at(args.scene)
        if spec is None:
            raise SystemExit(f"no scene {args.scene} in the plan")
        progress.scene_start(spec, project.story)
        result = write_scene(project, spec, models, config, progress)
        project.save()
        project.write_manuscript()
        progress.scene_done(result)
        progress.summary(project.story)
        return 0 if result.committed else 1

    results = write_all(project, models, config, start=args.start, stop=args.stop,
                        progress=progress)
    return 1 if any(not r.committed for r in results) else 0


def cmd_bench(args) -> int:
    """Draft one real scene with several models and score brief adherence.

    This measures the axis no public benchmark covers: can a model hold the prohibition list and
    the word target for a scene of this project. It deliberately runs no judge model and no LLM
    probes, so it costs nothing but GPU time — and it says nothing at all about whether the prose
    is any good. Read the drafts it saves.
    """
    from .llm import AnthropicBackend, LLMError, OpenAICompatBackend, strip_reasoning
    from .models import Scene
    from .ollama import OllamaUnavailable, resolve
    from .pipeline import WRITER_SYSTEM

    project = _load(args.project)
    spec = project.spec_at(args.scene)
    if spec is None:
        raise SystemExit(f"no scene {args.scene} in the plan")

    # (name, is_local). Carrying the flag beats inferring it later from list membership.
    candidates: list[tuple[str, bool]] = []
    for raw in args.local or []:
        try:
            candidates.append((resolve(raw, args.base_url), True))
        except OllamaUnavailable as exc:
            print(f"  skipping {raw}: {exc}")
    candidates.extend((name, False) for name in (args.hosted or []))
    if not candidates:
        raise SystemExit("give at least one --local MODEL (or --hosted MODEL for an API model)")

    previous = project.previous_committed(spec.index)
    previous_spec = project.spec(previous.spec_id) if previous else None
    previous_tail = tail_of(previous.text) if previous else ""
    previous_characters = previous_spec.characters if previous_spec else []
    committed = project.committed_texts(before=spec.index)

    brief = render_brief(spec, project.story, project.ledger, previous_tail,
                         previous_characters, checks.slop_sample(12))

    out_dir = Path(args.out or (Path(args.project) / "bench"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"brief-{spec.index:04d}.md").write_text(brief, encoding="utf-8")

    print(f"\nScene {spec.index} · target {spec.word_target}w · "
          f"{args.candidates} draft(s) per model\n")
    header = f"  {'model':<30} {'words':>7} {'B':>3} {'M':>3} {'m':>3}  worst finding"
    print(header)
    print("  " + "─" * (len(header) + 20))

    rows = []
    for name, is_local in candidates:
        try:
            # No retries here, and a shorter timeout than a real run: bench is interactive and
            # a model that needs ten minutes for one scene has already answered the question.
            backend = (OpenAICompatBackend(name, args.base_url, timeout=args.timeout, retries=0)
                       if is_local else AnthropicBackend(name, timeout=args.timeout, retries=0))
        except LLMError as exc:
            print(f"  {name:<30} unavailable: {exc}")
            continue
        best = None
        for attempt in range(args.candidates):
            try:
                reply = backend.complete(
                    brief, system=WRITER_SYSTEM,
                    max_tokens=min(32000, int(spec.word_target * 3) + 1000),
                    temperature=1.0)
            except LLMError as exc:
                print(f"  {name:<30} failed: {exc}")
                best = None
                break
            scene = Scene(spec_id=spec.id, index=spec.index,
                          text=strip_reasoning(reply.text))
            found = checks.run_all(scene, spec, project.story, previous_tail,
                                   previous_characters, committed)
            score = (sum(1 for v in found if v.severity is Severity.BLOCKER),
                     sum(1 for v in found if v.severity is Severity.MAJOR),
                     sum(1 for v in found if v.severity is Severity.MINOR))
            (out_dir / f"{name.replace(':', '-').replace('/', '-')}"
                       f"-s{spec.index:04d}-{attempt + 1}.txt").write_text(
                scene.text, encoding="utf-8")
            if best is None or score < best[0]:
                best = (score, scene, found)

        if best is None:
            continue
        (blockers, majors, minors), scene, found = best
        serious = [v for v in found if v.severity is not Severity.MINOR]
        worst = serious[0].kind if serious else (found[0].kind if found else "clean")
        # A reply under 40% of target is not a draft with a length problem — it is not a draft.
        # Without this floor an 11-word reply won a real bench: one length major beats one style
        # major plus minors on violation count, which is the wrong lesson to teach.
        usable = scene.word_count() >= spec.word_target * 0.4
        label = worst if usable else "UNUSABLE (empty or truncated reply)"
        print(f"  {name:<30} {scene.word_count():>7} {blockers:>3} {majors:>3} {minors:>3}"
              f"  {label}")
        rows.append((name, not usable, blockers, majors, minors))

    if rows:
        rows.sort(key=lambda r: (r[1], r[2], r[3], r[4]))
        if rows[0][1]:
            print("\n  No model produced a usable draft.")
        else:
            print(f"\n  Best adherence: {rows[0][0]}")
    print(f"\n  Drafts written to {out_dir}")
    print("  This scores adherence only. Read the drafts — a compliant model that writes")
    print("  lifelessly is the wrong choice and no check here will tell you that.\n")
    return 0


def cmd_plan(args) -> int:
    """Premise in, auditable plan out. The only command that creates a project."""
    from .planner import make_plan
    from .progress import Progress

    premise_path = Path(args.premise)
    premise = (premise_path.read_text(encoding="utf-8") if premise_path.exists()
               else args.premise)
    if not premise.strip():
        raise SystemExit("give a premise, either as text or as a path to a file")

    root = Path(args.out)
    if (root / "story.json").exists() and not args.force:
        raise SystemExit(
            f"{root} already holds a project. Use --force to overwrite, but note that discards "
            f"its ledger and any committed scenes.")

    models, _writer_name, critic_name = _build_models(args)
    progress = Progress(quiet=args.quiet)
    print(f"\n  Planning from: {premise.strip()[:70]}…")
    print(f"  planner: {critic_name}")
    print("  " + "-" * 74)

    result = make_plan(premise, models, total_words=args.words,
                       avg_scene_words=args.scene_words, scenes=args.scenes,
                       sharpen_rounds=args.sharpen, seed=args.seed,
                       repeople=not args.no_repeople, progress=progress)

    Project(root, result.story, result.plan).save()

    print(f"\n  {result.story.title}")
    print(f"  {len(result.plan)} scenes, "
          f"{sum(s.word_target for s in result.plan):,} target words")
    print(f"  {len(result.story.threads)} threads, "
          f"{len(result.story.characters)} characters")
    for note in result.notes:
        print(f"  · {note}")

    _print_violations(result.violations, "Plan audit")
    print(f"\n  written to {root}")
    print(f"  next:  python -m redthread brief {root} --scene 1")
    return 0 if result.is_clean() else 1


def cmd_status(args) -> int:
    project = _load(args.project)
    for key, value in project.status().items():
        print(f"{key:20} {value}")
    # Manuscript-level prose measures. Neither can be a scene check — they are properties of the
    # whole book — and the second is here because the first misleads on its own: duplication
    # cannot tell two hundred mild echoes from one phrase in fifteen scenes, and across five
    # runs of one plan it rose while the worst refrain fell from 28 scenes to 7.
    texts = project.committed_texts()
    if len(texts) > 3:
        concentration, worst = checks.repetition_concentration(texts)
        print(f"{'duplication':20} {checks.duplication_ratio(chr(10).join(texts)):.3f} "
              f"across the manuscript")
        print(f"{'worst refrain':20} one phrase in {worst} scenes; the worst 1% of phrases "
              f"carry {concentration:.0%} of all repetition")

    print("\nThreads:")
    for t in project.story.threads:
        mark = "✓" if t.is_resolved() else " "
        print(f"  [{mark}] {t.id:14} {t.current_state:14} {t.name}")
    if project.history:
        print("\nThread moves:")
        for m in project.history:
            print(f"  s{m.scene:<4} {m.thread_id:14} {m.from_state} → {m.to_state}")
    return 0


def cmd_ledger(args) -> int:
    project = _load(args.project)
    facts = project.ledger.facts
    if args.subject:
        facts = project.ledger.about([args.subject], 10**6)
    if args.character:
        facts = project.ledger.knows(args.character, 10**6)
    print(project.ledger.render(facts))
    print(f"\n{len(facts)} fact(s)")
    return 0


def cmd_manuscript(args) -> int:
    project = _load(args.project)
    path = project.write_manuscript()
    words = sum(s.word_count() for s in project.committed_scenes())
    print(f"{path} — {words} words, {len(project.committed_scenes())} scene(s)")
    return 0


def cmd_replicate(args) -> int:
    """Write N books from one plan, changing nothing, and report the spread.

    This is the control the whole measurement panel rests on, and it is also — with one ablation
    flag — how a mechanism is tested against its own absence. Same plan, same code, one switch.
    Nothing else in this project was worth building before it existed.
    """
    from .pipeline import Config, write_all
    from .progress import Progress
    from .replicate import committed_texts, fresh_copy, print_group

    source = _load(args.project)
    if not source.plan:
        raise SystemExit(f"{args.project} has no plan.json to replicate")

    root = Path(args.project)
    suffix = f"-{args.label}" if args.label else "-r"
    targets = [root.parent / f"{root.name}{suffix}{i + 1}" for i in range(args.runs)]

    ablated = [name for name, off in (("refrain-feedback", args.no_refrain_feedback),
                                      ("gesture-feedback", args.no_gesture_feedback),
                                      ("model-refrains", args.no_model_refrains)) if off]
    print(f"\n  Replicating {source.story.title} — {len(source.plan)} scenes "
          f"x {args.runs} run(s)")
    print(f"  ablated: {', '.join(ablated) if ablated else 'nothing (a true replicate)'}")
    for target in targets:
        print(f"    {target}")

    if args.measure_only:
        missing = [str(t) for t in targets if not t.exists()]
        if missing:
            raise SystemExit(f"--measure-only, but these do not exist: {', '.join(missing)}")
    else:
        models, writer_name, critic_name = _build_models(args)
        config = Config(candidates=args.candidates, max_repairs=args.repairs,
                        refrain_feedback=not args.no_refrain_feedback,
                        gesture_feedback=not args.no_gesture_feedback,
                        model_refrains=not args.no_model_refrains)
        for i, target in enumerate(targets, start=1):
            # Resume rather than restart. A replicate set is several GPU-hours; one that had to
            # begin again after an interruption would simply never be finished.
            project = (Project.load(target) if (target / "story.json").exists()
                       else fresh_copy(source, target))
            done = len(project.committed_scenes())
            if done >= len(project.plan):
                print(f"\n  [{i}/{len(targets)}] {target.name}: complete already, skipping")
                continue
            print(f"\n  [{i}/{len(targets)}] {target.name}: {done} of {len(project.plan)} "
                  f"scenes already written")
            progress = Progress.for_project(project, quiet=args.quiet)
            progress.run_header(project.story, writer_name, critic_name)
            write_all(project, models, config, progress=progress)
            project.write_manuscript()

    runs = [(t.name, committed_texts(t)) for t in targets if t.exists()]
    runs = [(name, texts) for name, texts in runs if texts]
    if not runs:
        print("\n  No committed scenes in any replicate. Nothing to measure.")
        return 1
    print_group("Replicate set", runs)
    if ablated:
        print("\n  A switch was flipped, so this spread is effect and noise together. Compare "
              "\n  it against a true replicate set with `measures --against`.\n")
    else:
        print("\n  These are error bars, not a result. Any claim about a difference between "
              "\n  two conditions has to be larger than the spread above.\n")
    return 0


def cmd_measures(args) -> int:
    """The manuscript panel for a group of runs, or a comparison of two groups.

    With `--against`, every difference goes through `checks.clears_noise` before it is reported,
    and a measure with no published floor raises rather than returning a verdict. That is the
    whole point: "I have not measured this" and "this is not different" are different sentences,
    and confusing them is what three retracted claims were made of.
    """
    from .replicate import committed_texts, print_group

    runs = [(Path(p).name, committed_texts(p)) for p in args.runs]
    for name, texts in runs:
        if not texts:
            print(f"  no committed scenes in {name}")
    runs = [(name, texts) for name, texts in runs if texts]
    if not runs:
        raise SystemExit("no committed scenes in any of the given runs")

    means = print_group(args.label or "Group A", runs)
    if not args.against:
        return 0

    other = [(Path(p).name, committed_texts(p)) for p in args.against]
    other = [(name, texts) for name, texts in other if texts]
    if not other:
        raise SystemExit("no committed scenes in any --against run")
    other_means = print_group(args.against_label or "Group B", other)

    print(f"\nDifference, against a floor from {checks.NOISE_FLOOR_N} identical runs "
          f"({checks.NOISE_FLOOR_SOURCE})")
    survived = []
    for name in checks.NOISE_FLOOR:
        print("  " + checks.describe_difference(name, means[name], other_means[name]))
        if checks.clears_noise(name, means[name], other_means[name]):
            survived.append(name)
    if survived:
        print(f"\n  Clears the floor: {', '.join(survived)}")
        print("  A floor measured from two runs understates the true spread, so read these as "
              "\n  the most generous reading of the evidence rather than as settled.")
    else:
        print("\n  Nothing clears the floor. This instrument cannot tell these two apart, "
              "\n  which is not the same as their being the same.")
    return 0


# --------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="redthread",
        description="Orchestrated long-form fiction: a spec tree, a fact ledger, and a "
                    "verifier that refuses to commit prose that broke its brief.")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_project(p):
        p.add_argument("project", help="path to the run directory (contains story.json)")
        return p

    p = sub.add_parser("plan", help="generate a plan from a premise")
    p.add_argument("premise", help="the premise, as text or a path to a file")
    p.add_argument("--out", required=True, help="run directory to create")
    p.add_argument("--words", type=int, default=60000, help="target manuscript length")
    p.add_argument("--scene-words", type=int, default=DEFAULT_SCENE_WORDS,
                   help="average scene length (default is measured; see schedule.py)")
    p.add_argument("--scenes", type=int, default=None, help="override the scene count")
    p.add_argument("--sharpen", type=int, default=2,
                   help="rounds of vaguest-first beat expansion")
    p.add_argument("--seed", type=int, default=0, help="seed for word-target variation")
    p.add_argument("--no-repeople", action="store_true",
                   help="ablation: skip the pass that re-asks for scenes left with one person "
                        "in them")
    p.add_argument("--force", action="store_true", help="overwrite an existing project")
    p.add_argument("--writer", default="claude-opus-5")
    p.add_argument("--critic", default="claude-sonnet-5")
    p.add_argument("--local", metavar="MODEL", help="plan with a local model")
    p.add_argument("--all-local", metavar="MODEL",
                   help="alias for --local (kept for older invocations)")
    p.add_argument("--local-critic", metavar="MODEL",
                   help="a second local model for the critic and extractor roles; defaults to "
                        "the writer model")
    p.add_argument("--base-url", default=DEFAULT_OLLAMA_BASE)
    p.add_argument("--openai-compat", action="store_true",
                   help="use the OpenAI-compatible endpoint instead of Ollama's native API "
                        "(for vLLM, LM Studio, llama.cpp)")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_plan)

    add_project(sub.add_parser("audit", help="plan-level checks (no model call)")) \
        .set_defaults(func=cmd_audit)

    p = add_project(sub.add_parser("brief", help="print a scene brief (no model call)"))
    p.add_argument("--scene", type=int, required=True)
    p.add_argument("--out", help="also write the brief to this path")
    p.set_defaults(func=cmd_brief)

    p = add_project(sub.add_parser("check", help="run deterministic checks on prose"))
    p.add_argument("--scene", type=int, required=True)
    p.add_argument("--file", help="prose file; omit to read stdin")
    p.set_defaults(func=cmd_check)

    p = add_project(sub.add_parser("write", help="generate scenes"))
    p.add_argument("--scene", type=int, help="write one scene; omit to write all pending")
    p.add_argument("--start", type=int, default=1)
    p.add_argument("--stop", type=int, default=None)
    p.add_argument("--candidates", type=int, default=3)
    p.add_argument("--repairs", type=int, default=2)
    p.add_argument("--writer", default="claude-opus-5")
    p.add_argument("--critic", default="claude-sonnet-5")
    p.add_argument("--local", metavar="MODEL",
                   help="local model for prose, hosted critic (the hybrid)")
    p.add_argument("--all-local", metavar="MODEL",
                   help="alias for --local (kept for older invocations)")
    p.add_argument("--local-critic", metavar="MODEL",
                   help="a second local model for the critic and extractor roles; defaults to "
                        "the writer model")
    p.add_argument("--base-url", default=DEFAULT_OLLAMA_BASE)
    p.add_argument("--openai-compat", action="store_true",
                   help="use the OpenAI-compatible endpoint instead of Ollama's native API "
                        "(for vLLM, LM Studio, llama.cpp)")
    p.add_argument("--forecast", action="store_true",
                   help="run the tension probe (one extra call per scene)")
    # Ablation switches. Each turns off one prompt-side mechanism so it can be run against its
    # own absence on the same plan; see Config in pipeline.py for why they exist.
    p.add_argument("--no-refrain-feedback", action="store_true",
                   help="ablation: do not name this book's repeated phrases in the brief")
    p.add_argument("--no-gesture-feedback", action="store_true",
                   help="ablation: do not name this book's repeated movements in the brief")
    p.add_argument("--no-model-refrains", action="store_true",
                   help="ablation: do not name the model's cross-book constructions")
    p.add_argument("--force", action="store_true",
                   help="commit even with MAJOR violations outstanding")
    p.add_argument("--quiet", action="store_true", help="suppress the progress display")
    p.set_defaults(func=cmd_write)

    p = add_project(sub.add_parser("models", help="list models installed in Ollama"))
    p.add_argument("--base-url", default=DEFAULT_OLLAMA_BASE)
    p.add_argument("--openai-compat", action="store_true",
                   help="use the OpenAI-compatible endpoint instead of Ollama's native API "
                        "(for vLLM, LM Studio, llama.cpp)")
    p.add_argument("--vram", type=float, metavar="GB",
                   help="flag which installed models plausibly fit this much VRAM")
    p.set_defaults(func=cmd_models)

    p = add_project(sub.add_parser(
        "bench", help="draft one scene with several models and score brief adherence"))
    p.add_argument("--scene", type=int, required=True)
    p.add_argument("--local", action="append", metavar="MODEL",
                   help="an Ollama model to test; repeat for several")
    p.add_argument("--hosted", action="append", metavar="MODEL",
                   help="an Anthropic API model to test; repeat for several")
    p.add_argument("--candidates", type=int, default=1,
                   help="drafts per model; the best-scoring one is reported")
    p.add_argument("--base-url", default=DEFAULT_OLLAMA_BASE)
    p.add_argument("--openai-compat", action="store_true",
                   help="use the OpenAI-compatible endpoint instead of Ollama's native API "
                        "(for vLLM, LM Studio, llama.cpp)")
    p.add_argument("--out", help="where to write the drafts (default <project>/bench)")
    p.add_argument("--timeout", type=int, default=300, metavar="SECONDS",
                   help="give up on a model after this long (default 300, no retries)")
    p.set_defaults(func=cmd_bench)

    p = add_project(sub.add_parser(
        "replicate", help="write N books from one plan and report the spread"))
    p.add_argument("--runs", type=int, default=2,
                   help="how many replicates (two give a range, not a distribution)")
    p.add_argument("--label", help="suffix for the sibling directories; names the condition")
    p.add_argument("--measure-only", action="store_true",
                   help="do not generate; measure replicates that already exist")
    p.add_argument("--candidates", type=int, default=3)
    p.add_argument("--repairs", type=int, default=2)
    p.add_argument("--no-refrain-feedback", action="store_true",
                   help="ablation: do not name this book's repeated phrases in the brief")
    p.add_argument("--no-gesture-feedback", action="store_true",
                   help="ablation: do not name this book's repeated movements in the brief")
    p.add_argument("--no-model-refrains", action="store_true",
                   help="ablation: do not name the model's cross-book constructions")
    p.add_argument("--writer", default="claude-opus-5")
    p.add_argument("--critic", default="claude-sonnet-5")
    p.add_argument("--local", metavar="MODEL", help="local model for prose")
    p.add_argument("--all-local", metavar="MODEL", help="alias for --local")
    p.add_argument("--local-critic", metavar="MODEL",
                   help="a second local model for the critic and extractor roles")
    p.add_argument("--base-url", default=DEFAULT_OLLAMA_BASE)
    p.add_argument("--openai-compat", action="store_true",
                   help="use the OpenAI-compatible endpoint instead of Ollama's native API")
    p.add_argument("--quiet", action="store_true")
    p.set_defaults(func=cmd_replicate)

    p = sub.add_parser("measures",
                       help="manuscript measures for a group of runs, with error bars")
    p.add_argument("runs", nargs="+", help="one or more run directories")
    p.add_argument("--against", nargs="+", metavar="RUN",
                   help="a second group; differences are reported against the noise floor")
    p.add_argument("--label", help="name for the first group")
    p.add_argument("--against-label", help="name for the second group")
    p.set_defaults(func=cmd_measures)

    add_project(sub.add_parser("status", help="progress and thread state")) \
        .set_defaults(func=cmd_status)

    p = add_project(sub.add_parser("ledger", help="dump the fact ledger"))
    p.add_argument("--subject", help="filter to facts touching this subject")
    p.add_argument("--character", help="show what this character knows")
    p.set_defaults(func=cmd_ledger)

    add_project(sub.add_parser("manuscript", help="assemble manuscript.md")) \
        .set_defaults(func=cmd_manuscript)

    return parser


def _force_utf8() -> None:
    """Windows consoles default to cp1252, which cannot encode the arrows and dashes this
    output uses. Reconfiguring beats degrading the output to ASCII everywhere."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    args = build_parser().parse_args(argv)
    return args.func(args)
