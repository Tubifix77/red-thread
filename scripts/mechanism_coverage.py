"""Which mechanisms actually fire, on which runs?

`docs/MEASUREMENTS.md` has long carried an audit of which *checks* fire. This is the same
question asked of the *mechanisms*, and the first time it was asked it found two of six doing
nothing at all on the corpus every published verdict rests on: the re-people pass (gated at a 15%
solo-scene share, while the corpus plan sits at 14.08%) and `drop_unavoidable_bans`.

**Why this needs to be a script and not a note.** A gate is invisible in the artefact it gates —
a plan the re-people pass rewrote and a plan it declined to touch are both just plans on disk, and
a story whose bans were filtered looks exactly like one whose were not. The only way to tell is to
re-derive each gate's input from the artefact, which is what this does.

Run it before designing any ablation. An ablation of a mechanism that never fires on the target
corpus compares a condition against itself and reports "no difference" with error bars and a kill
criterion attached — which is not a weak experiment but a measurement of the wrong thing. Asking
this question first cost nothing and saved about three GPU-hours the night it was written.

    python scripts/mechanism_coverage.py [--deep] [run ...]

`--deep` adds the brief-side mechanisms, which must replay each book's committed prefix scene by
scene and therefore take a minute or two per run.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import checks, planner  # noqa: E402
from redthread.project import Project  # noqa: E402

SOLO_GATE = 0.15
"""`repeople_solo_scenes`'s default `limit`, and the value `make_plan` calls it with."""


def _runs(argv: list[str]) -> list[Path]:
    named = [Path(a) for a in argv if not a.startswith("-")]
    if named:
        return named
    return sorted(p for p in Path("runs").iterdir()
                  if p.is_dir() and (p / "story.json").is_file())


def plan_side(root: Path) -> dict[str, object] | None:
    """The three plan-time mechanisms, replayed against this run's own stored artefacts."""
    try:
        project = Project.load(root)
    except Exception:
        return None
    story, plan = project.story, sorted(project.plan, key=lambda s: s.index)
    if not plan:
        return None

    solo = [s for s in plan if len(s.characters) < 2]
    share = len(solo) / len(plan)

    dropped_samples = (len(story.style.samples)
                       - len(planner.drop_story_shaped_samples(copy.deepcopy(story))
                             .style.samples))
    dropped_bans = (len(story.style.forbidden_phrases)
                    - len(planner.drop_unavoidable_bans(copy.deepcopy(story))
                          .style.forbidden_phrases))
    return {
        "scenes": len(plan),
        "solo": len(solo),
        "share": share,
        # The gate is strictly greater-than, matching planner.repeople_solo_scenes.
        "repeople_fires": share > SOLO_GATE,
        "samples_dropped": dropped_samples,
        "bans_dropped": dropped_bans,
        "written": len(list((root / "scenes").glob("*.txt"))),
    }


def brief_side(root: Path) -> dict[str, object] | None:
    """The two feedback mechanisms, by rebuilding what each scene's brief was actually told.

    `manuscript_refrains` and `manuscript_gestures` are deterministic over a committed prefix, so
    running them on `texts[:i]` reproduces exactly what scene *i*'s brief received. Empty means
    the mechanism had nothing to say, which is indistinguishable, in the finished book, from the
    mechanism being switched off.
    """
    from redthread.replicate import committed_texts

    texts = committed_texts(str(root))
    if not texts:
        return None
    first_r = first_g = None
    fired_r = fired_g = 0
    for i in range(1, len(texts) + 1):
        if checks.manuscript_refrains(texts[:i]):
            fired_r += 1
            first_r = first_r or i
        if checks.manuscript_gestures(texts[:i]):
            fired_g += 1
            first_g = first_g or i
    n = len(texts)
    return {"n": n, "refrain_scenes": fired_r, "refrain_first": first_r,
            "gesture_scenes": fired_g, "gesture_first": first_g}


def main(argv: list[str]) -> int:
    deep = "--deep" in argv
    roots = _runs(argv[1:])

    print(f"{'run':<24} {'scenes':>6} {'solo':>5} {'share':>6} {'repeople':>9} "
          f"{'samples':>8} {'bans':>5}")
    inert_repeople: list[str] = []
    inert_bans: list[str] = []
    seen = 0
    for root in roots:
        row = plan_side(root)
        if row is None:
            continue
        seen += 1
        if not row["repeople_fires"]:
            inert_repeople.append(root.name)
        if not row["bans_dropped"]:
            inert_bans.append(root.name)
        print(f"{root.name:<24} {row['scenes']:>6} {row['solo']:>5} {row['share']:>5.0%} "
              f"{('FIRES' if row['repeople_fires'] else '-'):>9} "
              f"{row['samples_dropped']:>8} {row['bans_dropped']:>5}")

    if not seen:
        print("\n  No loadable runs. This printed nothing, which is not the same as a result —\n"
              "  a scan that matches nothing is the failure this project keeps re-learning.")
        return 2

    print(f"\n  {seen} run(s) examined.")
    print(f"  re-people pass inert on {len(inert_repeople)} of {seen}")
    print(f"  drop_unavoidable_bans inert on {len(inert_bans)} of {seen}")
    print("\n  The model-refrain list is unconditional: pipeline.py loads it whenever the config\n"
          "  says so and brief.py injects it whenever it is non-empty, so it fires in every\n"
          "  brief of every scene and needs no row here.")

    if deep:
        print("\n  Brief-side feedback, by replaying each committed prefix:")
        for root in roots:
            row = brief_side(root)
            if row is None:
                continue
            print(f"  {root.name}: refrain named something in "
                  f"{row['refrain_scenes']}/{row['n']} scenes (first at {row['refrain_first']}); "
                  f"gesture in {row['gesture_scenes']}/{row['n']} (first at {row['gesture_first']})")
        print("\n  The gesture feedback's late first fire is not a defect: it needs four\n"
              "  recurrences before it can name anything, so the opening of every book is\n"
              "  untreated by construction. That is why its effect is visible in a\n"
              "  first-quarter-to-last-quarter statistic and invisible in a whole-book mean.")
    else:
        print("\n  Pass --deep to add the brief-side feedback mechanisms (slower).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
