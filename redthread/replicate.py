"""Replication and measurement: what a difference has to beat before it is one.

This module exists because of a specific two-day failure. Every result in this project was one
run against one run, and on 30 August three of them were retracted in a single afternoon — the
worst refrain "falling" 15 → 10 → 7, the gesture rate "falling" 2.1 → 1.9 → 1.7, gesture
feedback "delaying" the first repeat from scene 15 to 37. None survived contact with two runs of
identical code, which differ by 44%, 31% and four scenes respectively.

So there are two operations here and they are deliberately separate:

    replicate   write N books from one plan with nothing varying but the sampling
    measures    report the panel for a group of runs, and between two groups, refuse to
                state a difference the floor cannot support

The second is the one that gets used most, because with an ablation switch a "replicate set" and
an "experiment" are the same object: same plan, same code, one flag.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from . import checks
from .project import Project


def committed_texts(root: Path | str) -> list[str]:
    """Committed prose from a run directory, without loading the whole Project.

    Reading the scene records directly rather than through `Project.load` means a dozen finished
    books can be measured in a second, and a half-written or abandoned run contributes exactly
    the scenes that committed — which is the right behaviour, since an abandoned run's uncommitted
    prose never reached a reader or a check.
    """
    root = Path(root)
    out: list[str] = []
    for txt in sorted((root / "scenes").glob("*.txt")):
        meta = txt.with_suffix(".json")
        if not meta.exists():
            continue
        if json.loads(meta.read_text(encoding="utf-8")).get("committed"):
            out.append(txt.read_text(encoding="utf-8"))
    return out


def fresh_copy(source: Project, root: Path) -> Project:
    """A new project with the same story and plan, and nothing written.

    Thread state has to be rewound explicitly, and this is the part that is easy to get wrong: a
    finished run's story.json holds every thread at its *terminal* state. Copied verbatim, the
    replicate would open on a book that believes it has already happened, and scene 1 would be
    asked to move a thread it is already past — so the plan would be the same and the briefs
    would not, which is precisely the thing a replicate exists to rule out.
    """
    story = copy.deepcopy(source.story)
    for thread in story.threads:
        if thread.states:
            thread.current_state = thread.states[0]
    project = Project(root, story, copy.deepcopy(source.plan))
    project.save()
    return project


def common_prefix(runs: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    """Every run truncated to the shortest one's scene count.

    A replicate set writes one plan in one order, so scenes 1..k of every run are the same
    assignments and are comparable. Runs of unequal length are not: `words` and
    `duplication_manuscript` grow with the book, so a set of 71, 71, 44 and 22 scenes reports a
    "spread" of 106% in words that is almost entirely length.

    That is not hypothetical. An overnight four-run floor came back at exactly those lengths —
    two runs halted on a scene the repair loop could not fix — and `replicate` printed the panel
    without a word of complaint. The guard for it already existed in `measures --against` and had
    simply not been put here.

    Truncating rather than discarding is the better trade: a 22-scene floor from four runs is
    weaker than a 71-scene one and is still a floor, where two usable runs of four are not.
    """
    shortest = min(len(texts) for _name, texts in runs)
    return [(name, texts[:shortest]) for name, texts in runs]


def group_panel(runs: list[tuple[str, list[str]]]) -> dict[str, list[float]]:
    """Every measure across a group of runs, as name -> one value per run."""
    panels = [checks.manuscript_measures(texts) for _name, texts in runs]
    return {name: [p[name] for p in panels] for name in checks.NOISE_FLOOR}


def print_group(label: str, runs: list[tuple[str, list[str]]]) -> dict[str, float]:
    """Print mean and range for a group, and return the means.

    Range rather than standard deviation, because at n=2 or n=4 a standard deviation implies a
    distribution nobody has sampled. And never a single run's value: a maximum is the least
    trustworthy statistic in this project and was the one quoted most often.
    """
    panel = group_panel(runs)
    print(f"\n{label} — {len(runs)} run(s): {', '.join(n for n, _ in runs)}")
    print(f"  {'measure':<26} {'mean':>10} {'min':>10} {'max':>10} {'spread':>8}")
    means: dict[str, float] = {}
    for name, values in panel.items():
        mean = sum(values) / len(values)
        means[name] = mean
        spread = (max(values) - min(values)) / mean if mean else 0.0
        print(f"  {name:<26} {mean:>10.3f} {min(values):>10.3f} {max(values):>10.3f} "
              f"{spread:>7.0%}")
    return means


def observed_floor(runs: list[tuple[str, list[str]]]) -> dict[str, float]:
    """The spread of each measure across a group, as a fraction of its mean.

    This is what a replicate set *produces*: a candidate `checks.NOISE_FLOOR`. It is only a
    noise floor if nothing differed between the runs, which is why `replicate` prints what it
    ablated at the top — a set with a switch flipped yields an effect size, not a floor, and the
    arithmetic cannot tell the difference.
    """
    out: dict[str, float] = {}
    for name, values in group_panel(runs).items():
        mean = sum(values) / len(values)
        out[name] = (max(values) - min(values)) / mean if mean else 0.0
    return out
