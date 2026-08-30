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

    # A clean audit is not the same as a covered one. Six of these checks can only confirm the
    # scheduler on a plan the scheduler built, and saying so beside the result is the difference
    # between a green audit and a green audit that has been read correctly.
    quiet = checks.quiet_checks()
    print(f"\n  {len(quiet)} of these checks cannot fire on a generated plan — they test "
          f"properties\n  the scheduler or the brief already guarantees. See "
          f"docs/MEASUREMENTS.md. A clean\n  audit is not coverage of: "
          + ", ".join(sorted(quiet)))

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

    if args.emit_floor:
        # Step 2's deliverable, as something to paste rather than something to retype. Rounding
        # up matters and is not cosmetic: the first floor table was built from figures rounded
        # *down* for a write-up, and four measures of the very pair it came from were then
        # reported as clearing it.
        from .replicate import group_panel, observed_floor
        import math
        if len(runs) < 2:
            raise SystemExit("--emit-floor needs at least two runs of one plan")
        floor = observed_floor(runs)
        panel = group_panel(runs)
        print(f"\n# Observed across {len(runs)} runs of one plan, rounded up.")
        print("NOISE_FLOOR: dict[str, float] = {")
        for name, value in floor.items():
            print(f'    "{name}": {math.ceil(value * 100) / 100:.2f},')
        print("}")
        # Emitted alongside, because a floor of exactly zero means "every run gave the same
        # value" and not "this measure was measured to be perfectly stable". For a continuous
        # measure that is not luck — it means the measure was constant across the set, either
        # because nothing moved it (`recap_block_share` is zero in every current-era scene) or
        # because it cannot move within one plan at all (`scenes`). Pasting the floor without
        # this set would let any later difference read as clearing a floor nobody measured,
        # which is the exact bug that reached the first table.
        print("\nDEGENERATE_FLOOR: frozenset[str] = frozenset({")
        for name in sorted(n for n, v in floor.items() if v == 0.0):
            values = panel[name]
            print(f'    "{name}",'
                  f'{"" if values[0] else "   # zero in every run"}')
        print("})")
        print(f"\n  Paste both into checks.py and set NOISE_FLOOR_N = {len(runs)}. Only do this "
              f"for a "
              f"\n  set with nothing varying between its runs — a set with an ablation flag "
              f"\n  flipped yields an effect size, and the arithmetic cannot tell the "
              f"difference.\n")

    if not args.against:
        return 0

    other = [(Path(p).name, committed_texts(p)) for p in args.against]
    other = [(name, texts) for name, texts in other if texts]
    if not other:
        raise SystemExit("no committed scenes in any --against run")
    other_means = print_group(args.against_label or "Group B", other)

    print(f"\nDifference, against a floor from {checks.NOISE_FLOOR_N} identical runs "
          f"({checks.NOISE_FLOOR_SOURCE})")

    # Comparing two books of different lengths on a manuscript-wide measure compares their
    # lengths. Said before the table rather than after it, because the table is what gets quoted.
    ratio = (max(means["scenes"], other_means["scenes"])
             / max(1e-9, min(means["scenes"], other_means["scenes"])))
    mismatched = ratio > 1.25
    if mismatched:
        print(f"  ⚠ {means['scenes']:.0f} scenes against {other_means['scenes']:.0f}. "
              f"These do not compare on "
              f"{', '.join(sorted(checks.LENGTH_SENSITIVE - {'scenes'}))} —"
              f"\n    those grow with the length of the book, so the difference is the length.")
    survived = []
    for name in checks.NOISE_FLOOR:
        line = checks.describe_difference(name, means[name], other_means[name])
        if mismatched and name in checks.LENGTH_SENSITIVE:
            line += "   [length]"
        print("  " + line)
        if checks.clears_noise(name, means[name], other_means[name]):
            if mismatched and name in checks.LENGTH_SENSITIVE:
                continue
            survived.append(name)
    unestablished = [n for n in survived if not checks.floor_is_established(n)]
    survived = [n for n in survived if checks.floor_is_established(n)]
    if survived:
        print(f"\n  Clears the floor: {', '.join(survived)}")
        print("  A floor measured from two runs understates the true spread, so read these as "
              "\n  the most generous reading of the evidence rather than as settled.")
    if unestablished:
        print(f"\n  Differs, with no floor to clear: {', '.join(unestablished)}")
        print("  Both replicates were identically zero on these, so nothing is known about how "
              "\n  much they move on their own. The difference may be real; this cannot say so.")
    if not survived and not unestablished:
        print("\n  Nothing clears the floor. This instrument cannot tell these two apart, "
              "\n  which is not the same as their being the same.")
    return 0


def cmd_sample(args) -> int:
    """Print random sentences with no context and no scores, or build a blind rating sheet.

    The one command here that asks a person a question. Everything else in this project measures
    whether the prose scores better; a hundred sentences read blind is the only thing that can
    say whether it reads better, and it is deliberately incapable of scoring anything itself.
    """
    from .replicate import committed_texts
    from .sample import blind_sheet, draw, render_key, render_sheet

    groups = [(Path(p).name, committed_texts(p)) for p in args.runs]
    groups = [(name, texts) for name, texts in groups if texts]
    if not groups:
        raise SystemExit("no committed scenes in any of the given runs")

    if not args.against:
        pool = [t for _name, texts in groups for t in texts]
        for sentence in draw(pool, args.n, seed=args.seed, min_words=args.min_words):
            print(sentence)
        return 0

    other = [(Path(p).name, committed_texts(p)) for p in args.against]
    other = [(name, texts) for name, texts in other if texts]
    if not other:
        raise SystemExit("no committed scenes in any --against run")

    pair = [(args.label or "A", [t for _n, ts in groups for t in ts]),
            (args.against_label or "B", [t for _n, ts in other for t in ts])]
    sheet, key = blind_sheet(pair, args.n, seed=args.seed, min_words=args.min_words)

    out = Path(args.out or ".")
    out.mkdir(parents=True, exist_ok=True)
    sheet_path, key_path = out / "sentences.md", out / "sentences-key.md"
    # Two files, never one. A key beside the sheet is not a blind, and the person who has to
    # resist reading it is the same person who wrote the thing being rated.
    sheet_path.write_text(render_sheet(sheet), encoding="utf-8")
    key_path.write_text(render_key(key), encoding="utf-8")
    print(f"\n  {len(sheet)} sentences, {args.n} from each side, shuffled")
    print(f"  sheet:  {sheet_path}")
    print(f"  key:    {key_path}   (do not open it until the sheet is filled in)")

    # A control on the sheet itself, printed rather than filtered. The sentence splitter breaks
    # after a closing quote, so a drawn "sentence" is sometimes a speech tag joined to the line
    # after it — and the two eras of this project differ in dialogue share by nearly threefold.
    # Dropping quoted sentences would therefore bias the sheet differentially against the axis
    # that has moved most, so nothing is dropped and the imbalance is reported instead. If one
    # side arrives markedly more spoken than the other, a rating difference may be a preference
    # about dialogue rather than about prose.
    print("\n  Control — share of drawn sentences containing speech:")
    for label, rows in ((pair[0][0], [s for n, lbl, s in key if lbl == pair[0][0]]),
                        (pair[1][0], [s for n, lbl, s in key if lbl == pair[1][0]])):
        spoken = sum(1 for s in rows if '"' in s or "“" in s or "”" in s)
        print(f"    {label:<18} {spoken}/{len(rows)}  ({spoken / len(rows):.0%})"
              if rows else f"    {label:<18} none drawn")
    print()
    return 0


def cmd_rate(args) -> int:
    """Read a filled-in sheet and say what a hundred hand ratings establish, if anything.

    Written to be able to return "nothing". If no signal in the panel correlates with the
    ratings, that is the finding — it says the instrument panel is orthogonal to what a reader
    notices, and most of it needs rethinking rather than extending.
    """
    from .sample import (bootstrap_ci, correlate, is_spoken, parse_key, parse_ratings,
                         sentence_signals)

    ratings = parse_ratings(Path(args.sheet).read_text(encoding="utf-8"))
    key = parse_key(Path(args.key).read_text(encoding="utf-8"))
    if not ratings:
        raise SystemExit(f"no ratings filled in on {args.sheet} — write a digit in each [ ]")

    # The sentence text lives in the key, so the sheet stays a sheet.
    sentences: dict[int, str] = {}
    for line in Path(args.key).read_text(encoding="utf-8").splitlines():
        parts = line.split(None, 3)
        if len(parts) == 4 and parts[0].isdigit():
            sentences[int(parts[0])] = parts[3]

    rated = [(n, r) for n, r in sorted(ratings.items()) if n in key]
    missing = len(key) - len(rated)
    print(f"\n  {len(rated)} of {len(key)} sentences rated"
          + (f", {missing} left blank" if missing else ""))

    groups: dict[str, list[float]] = {}
    for n, r in rated:
        groups.setdefault(key[n][0], []).append(float(r))

    print("\n  Mean rating, with a 95% bootstrap interval")
    intervals = {}
    for label, values in sorted(groups.items()):
        lo, hi = bootstrap_ci(values, seed=args.seed)
        intervals[label] = (lo, hi)
        print(f"    {label:<18} {sum(values) / len(values):.2f}  "
              f"[{lo:.2f}, {hi:.2f}]   n={len(values)}")

    if len(intervals) == 2:
        (a, (alo, ahi)), (b, (blo, bhi)) = sorted(intervals.items())
        overlap = alo <= bhi and blo <= ahi
        print(f"\n  The intervals {'overlap' if overlap else 'do not overlap'}: "
              f"{'this cannot separate the two sides' if overlap else f'{a} and {b} differ'}.")

    # Split on the control. The two sides of a sheet from this project came back 12% and 42%
    # spoken, and dialogue share is the axis that has moved most here — so a difference that
    # disappears inside one of these halves was a preference about dialogue.
    print("\n  Split on the speech control")
    for kind in ("narrated", "spoken"):
        print(f"    {kind}")
        for label in sorted(groups):
            values = [float(r) for n, r in rated
                      if key[n][0] == label and key[n][1] == kind]
            if not values:
                print(f"      {label:<16} none drawn")
                continue
            lo, hi = bootstrap_ci(values, seed=args.seed)
            # A cell this small has an interval wider than any effect worth finding. Saying so
            # beside the number beats leaving a reader to notice the n themselves, which is how
            # a 6-sentence cell gets quoted as a result.
            thin = "  — too few to read" if len(values) < 15 else ""
            print(f"      {label:<16} {sum(values) / len(values):.2f}  "
                  f"[{lo:.2f}, {hi:.2f}]   n={len(values)}{thin}")

    print("\n  Every per-sentence signal in the panel, against the ratings")
    scored = [(sentence_signals(sentences.get(n, "")), float(r)) for n, r in rated
              if sentences.get(n)]
    if scored:
        ys = [r for _s, r in scored]
        rows = []
        for name in scored[0][0]:
            xs = [s[name] for s, _r in scored]
            rows.append((abs(correlate(xs, ys)), name, correlate(xs, ys)))
        for _absr, name, r in sorted(rows, reverse=True):
            verdict = "" if abs(r) >= 0.3 else "   (nothing)"
            print(f"    {name:<14} r = {r:+.3f}{verdict}")
        best = max(rows)[0]
        if best < 0.3:
            print("\n  Nothing in the panel reaches r = 0.3 against a human reading. That is "
                  "\n  the finding: these measures are orthogonal to what a reader notices, and "
                  "\n  extending them will not change that.")
    print("\n  Note: duplication, refrains and cross-scene gesture repeats are properties of a "
          "\n  manuscript and cannot be asked of one sentence. A sheet like this can never test "
          "\n  the measures this project has spent most of its effort on.\n")
    return 0


def cmd_forecast(args) -> int:
    """Generate blind predictions for a finished book, or score ones already generated.

    Two modes on purpose. The first calibration of this idea ran in a throwaway script and its
    predictions were never written down, so a semantic re-score — which the plan assumed was
    free — had to pay for the generation a second time. Predictions are data now.
    """
    from .embed import Embedder
    from .forecast import (generate, lexical_scorer, load, prediction_spread, save, score,
                           semantic_scorer)
    from .replicate import committed_texts

    root = Path(args.project)
    texts = committed_texts(root)
    if len(texts) < 10:
        raise SystemExit(f"{root} has {len(texts)} committed scenes; this needs a finished book")
    store = Path(args.out) if args.out else root / "forecast.json"

    if not args.score_only:
        models, _writer, critic = _build_models(args)
        print(f"\n  Predicting {args.scenes} scenes of {len(texts)}, k={args.k}, "
              f"critic {critic}")
        if args.k > 1 and args.temperature == 0.0:
            # k samples at temperature 0 are one sample repeated, and the spread step 12
            # measures would be identically zero — a clean-looking result meaning nothing.
            raise SystemExit("--k above 1 needs --temperature above 0, or the k predictions "
                             "are one prediction repeated")
        predictions = generate(
            texts, models, wanted=args.scenes, k=args.k, temperature=args.temperature,
            store=store,
            on_scene=lambda i, g: print(f"    scene {i + 1:>3}  "
                                        f"{(g[0][:64] + '…') if g else 'no prediction'}",
                                        flush=True))
        save(predictions, store)
        print(f"\n  {len(predictions)} predictions written to {store}")
    else:
        if not store.exists():
            raise SystemExit(f"no predictions at {store} — run without --score-only first")
        predictions = load(store)
        print(f"\n  {len(predictions)} predictions loaded from {store}")

    embedder = Embedder(args.embed_model, args.base_url,
                        cache_dir=root / ".embeddings")
    results = [score(predictions, texts, lexical_scorer, "lexical overlap", seed=args.seed),
               score(predictions, texts, semantic_scorer(embedder), "embedding cosine",
                     seed=args.seed)]

    print("\n  Each prediction scored against the scene it predicted, and against a random")
    print("  other scene from the same book. The win rate is the only comparable column —")
    print("  an absolute similarity is a property of the book's vocabulary.\n")
    print(f"  {'scorer':<20} {'on target':>10} {'on control':>11} {'win rate':>9}  verdict")
    for result in results:
        print(f"  {result.name:<20} {result.on_target:>10.3f} {result.on_control:>11.3f} "
              f"{result.win_rate:>8.0%}  {result.verdict(args.floor)}")

    best = max(results, key=lambda r: r.win_rate)
    if best.win_rate < args.floor:
        print(f"\n  Neither scorer reaches {args.floor:.0%}. Meaning overlap has failed the same "
              f"way\n  word overlap did, and the answer is not a different threshold — it is to "
              f"stop\n  comparing a prediction against a scene at all. See --k above 1.")

    if any(len(p.predictions) > 1 for p in predictions):
        # Step 12. This never touches the actual scene, so the shared vocabulary that killed
        # both earlier attempts cannot reach it.
        spreads = [(p.index, prediction_spread(p, embedder))
                   for p in predictions if len(p.predictions) > 1]
        values = [s for _i, s in spreads]
        mean = sum(values) / len(values)
        print(f"\n  Disagreement among the k predictions for each scene "
              f"(higher = less predictable)")
        print(f"    mean {mean:.3f}   range {min(values):.3f} to {max(values):.3f}   "
              f"n={len(values)}")
        flat = [i for i, s in spreads if s < mean * 0.6]
        if flat:
            print(f"    lowest-spread scenes (the model can call these): "
                  f"{', '.join(str(i + 1) for i in flat[:12])}")
        print("    This is a distribution, not a verdict. It needs the same control everything "
              "\n    else here does before any scene is called slack.")

    print(f"\n  {embedder.calls} embedding call(s), {embedder.cached} served from cache\n")
    return 0


def cmd_depends(args) -> int:
    """The declared dependency graph: its shape, and whether it shows up in the prose.

    The first half needs no model and no prose — an ending that only reaches its last five
    scenes is visible before a word is written. The second half asks whether a declared
    dependency is anything more than bookkeeping.
    """
    from .replicate import committed_texts

    project = _load(args.project)
    plan = sorted(project.plan, key=lambda s: s.index)
    declared = [s for s in plan if s.depends_on]

    print(f"\n  {project.story.title} — {len(plan)} scenes")
    if not declared:
        # Not a failure. The field postdates most of this project's plans, and "nobody was
        # asked" and "there are none" are different states that this cannot tell apart.
        print("\n  No scene declares a dependency. This plan predates the field, or the "
              "\n  planner returned none — nothing here can tell those apart, so nothing "
              "\n  below is reported.\n")
        return 0

    edges = sum(len(s.depends_on) for s in declared)
    print(f"  {len(declared)} scenes declare {edges} dependencies "
          f"({edges / len(declared):.1f} each)")
    reach = checks.ending_reach(plan)
    reached = checks.ancestors(plan, plan[-1].index)
    print(f"  the final scene depends, transitively, on {len(reached)} of "
          f"{len(plan) - 1} earlier scenes ({reach:.0%})")

    orphans = [s.index for s in plan[1:] if not s.depends_on]
    if orphans:
        print(f"  {len(orphans)} scenes declare nothing: "
              f"{', '.join(str(i) for i in orphans[:15])}"
              + (" …" if len(orphans) > 15 else ""))
    unreached = [s.index for s in plan[:-1] if s.index not in reached]
    if unreached:
        print(f"  {len(unreached)} scenes the ending does not reach: "
              f"{', '.join(str(i) for i in unreached[:15])}"
              + (" …" if len(unreached) > 15 else ""))

    _print_violations(checks.check_dependency_graph(plan, project.story), "Graph audit")

    texts = committed_texts(args.project)
    if len(texts) < 10 or not args.prose:
        print("\n  Pass --prose on a finished book to test whether a declared dependency "
              "\n  leaves any trace in the writing.\n")
        return 0

    from .embed import Embedder
    from .forecast import declared_vs_random
    embedder = Embedder(args.embed_model, args.base_url,
                        cache_dir=Path(args.project) / ".embeddings")
    result = declared_vs_random(plan, texts, embedder, seed=args.seed)
    print(f"\n  Does a declared dependency show up in the prose?")
    print(f"    scene against its declared ancestor   {result.on_target:.3f}")
    print(f"    scene against a random earlier scene  {result.on_control:.3f}")
    print(f"    the declared one is closer            {result.win_rate:.0%}   n={result.n}")
    print(f"    {result.verdict(args.floor)}")
    if result.win_rate < args.floor:
        print("\n  A declared dependency that leaves no trace makes the field bookkeeping: "
              "\n  the graph audit would then be measuring the planner, not the book.\n")
    else:
        print()
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

    p = sub.add_parser("sample",
                       help="random sentences with no context and no scores")
    p.add_argument("runs", nargs="+", help="one or more run directories")
    p.add_argument("--n", type=int, default=30,
                   help="sentences to draw (per side, when --against is given)")
    p.add_argument("--against", nargs="+", metavar="RUN",
                   help="a second group; produces a shuffled blind sheet and a separate key")
    p.add_argument("--label", help="name for the first group, used only in the key")
    p.add_argument("--against-label", help="name for the second group, used only in the key")
    p.add_argument("--min-words", type=int, default=8,
                   help="skip sentences shorter than this; below eight they are mostly "
                        "dialogue fragments, which are exchange rather than craft")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", help="directory for the sheet and key (default: here)")
    p.set_defaults(func=cmd_sample)

    p = add_project(sub.add_parser(
        "forecast", help="blind predictions for a finished book, scored against a control"))
    p.add_argument("--scenes", type=int, default=35, help="how many scenes to predict")
    p.add_argument("--k", type=int, default=1,
                   help="predictions per scene; above 1 enables the disagreement measure")
    p.add_argument("--temperature", type=float, default=0.0,
                   help="must be above 0 when --k is above 1")
    p.add_argument("--score-only", action="store_true",
                   help="score predictions already on disk instead of generating them")
    p.add_argument("--out", help="where the predictions live (default <run>/forecast.json)")
    p.add_argument("--embed-model", default="nomic-embed-text")
    p.add_argument("--floor", type=float, default=0.65,
                   help="win rate below which a scorer has failed (default 0.65)")
    p.add_argument("--seed", type=int, default=0, help="seed for the control's random scene")
    p.add_argument("--writer", default="claude-opus-5")
    p.add_argument("--critic", default="claude-sonnet-5")
    p.add_argument("--local", metavar="MODEL", help="local model")
    p.add_argument("--all-local", metavar="MODEL", help="alias for --local")
    p.add_argument("--local-critic", metavar="MODEL", help="a second local model")
    p.add_argument("--base-url", default=DEFAULT_OLLAMA_BASE)
    p.add_argument("--openai-compat", action="store_true")
    p.set_defaults(func=cmd_forecast)

    p = add_project(sub.add_parser(
        "depends", help="the declared dependency graph, and whether the prose shows it"))
    p.add_argument("--prose", action="store_true",
                   help="also test declared dependencies against the written scenes")
    p.add_argument("--embed-model", default="nomic-embed-text")
    p.add_argument("--floor", type=float, default=0.65)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--base-url", default=DEFAULT_OLLAMA_BASE)
    p.set_defaults(func=cmd_depends)

    p = sub.add_parser("rate", help="read a filled-in sentence sheet and report what it shows")
    p.add_argument("sheet", help="the filled-in sheet")
    p.add_argument("--key", required=True, help="the key written alongside it")
    p.add_argument("--seed", type=int, default=0, help="seed for the bootstrap")
    p.set_defaults(func=cmd_rate)

    p = sub.add_parser("measures",
                       help="manuscript measures for a group of runs, with error bars")
    p.add_argument("runs", nargs="+", help="one or more run directories")
    p.add_argument("--against", nargs="+", metavar="RUN",
                   help="a second group; differences are reported against the noise floor")
    p.add_argument("--label", help="name for the first group")
    p.add_argument("--against-label", help="name for the second group")
    p.add_argument("--emit-floor", action="store_true",
                   help="print a NOISE_FLOOR table from these runs; only valid when nothing "
                        "varied between them")
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
