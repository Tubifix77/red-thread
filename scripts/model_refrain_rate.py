"""How often does a book use the constructions its brief told it not to?

Step 28's *secondary, targeted* statistic, pre-registered in
`docs/evidence/step28-preregistration.md` while the ablated runs stood at 10 of 142 scenes.

**This file was written before the data existed**, which is the point. The primary kill criterion
is unchanged and lives in PLAN2 (`duplication_manuscript` and `repetition_concentration` against
their floors); this exists because those are manuscript-wide aggregates while the mechanism has
exactly three named targets, and a panel measure can miss an effect confined to three phrases.

Counts occurrences of every phrase in `data/model_refrains.txt` per 10,000 words of committed
prose. Manuscript-level aggregate, so accumulation is already in the number (rule VII typed).

Control, measured from the four floor runs with the list ON, before any ablated run was read:
**mean 5.59 per 10k, range 4.74-6.16, spread 25% of mean (n=4)**. The prediction on record is
that ablated runs sit *higher*, outside that 25% floor, i.e. above about 7.0.

    python scripts/model_refrain_rate.py <run> [run ...] [--against <run> ...]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import checks  # noqa: E402
from redthread.replicate import committed_texts  # noqa: E402

CONTROL_FLOOR = 0.25
"""Spread of this statistic across the four floor runs, measured before any ablation was read."""


def rate(run: str, phrases: list[str]) -> tuple[float, int, int, dict[str, int]]:
    """Hits per 10k words, plus the raw counts, for one run's committed prose."""
    texts = committed_texts(run)
    words = sum(len(t.split()) for t in texts)
    hits = {p: sum(len(re.findall(re.escape(p), t, flags=re.I)) for t in texts)
            for p in phrases}
    total = sum(hits.values())
    return (total / words * 10000 if words else 0.0), total, words, hits


def group(label: str, runs: list[str], phrases: list[str]) -> float | None:
    present = [r for r in runs if committed_texts(r)]
    if not present:
        print(f"\n{label}: no committed scenes in any of {', '.join(runs)}")
        return None
    print(f"\n{label} — {len(present)} run(s)")
    print(f"  {'run':<28} {'hits':>5} {'words':>8} {'per 10k':>8}")
    vals = []
    for r in present:
        per10k, total, words, _hits = rate(r, phrases)
        vals.append(per10k)
        print(f"  {Path(r).name:<28} {total:>5} {words:>8} {per10k:>8.2f}")
    mean = sum(vals) / len(vals)
    spread = (max(vals) - min(vals)) / mean if mean else 0.0
    print(f"  {'mean':<28} {'':>5} {'':>8} {mean:>8.2f}   "
          f"range {min(vals):.2f}-{max(vals):.2f}, spread {spread:.0%}")
    return mean


def main(argv: list[str]) -> int:
    if "--against" in argv:
        i = argv.index("--against")
        a, b = argv[1:i], argv[i + 1:]
    else:
        a, b = argv[1:], []
    if not a:
        print(__doc__)
        return 2

    phrases = checks.load_model_refrains()
    if not phrases:
        print("data/model_refrains.txt is empty — nothing to count, and nothing to conclude.")
        return 2
    print(f"Counting {len(phrases)} phrase(s) the brief names in every scene: "
          + ", ".join(f'"{p}"' for p in phrases))

    mean_a = group("Group A", a, phrases)
    if not b:
        return 0
    mean_b = group("Group B", b, phrases)
    if mean_a is None or mean_b is None:
        return 1

    rel = abs(mean_a - mean_b) / ((mean_a + mean_b) / 2)
    print(f"\n  difference {rel:.0%} of mean, against the {CONTROL_FLOOR:.0%} control spread")
    if rel > CONTROL_FLOOR:
        higher = "A" if mean_a > mean_b else "B"
        print(f"  OUTSIDE the control spread — group {higher} uses these phrases more.")
        print("  Read this against the pre-registration, not on its own: a mechanism confirmed\n"
              "  at suppressing three phrases is a smaller claim than the one its brief text\n"
              "  makes, and PLAN2's primary criterion is the panel, not this.")
    else:
        print("  INSIDE the control spread. This statistic cannot separate them, which is not\n"
              "  the same as their being the same.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
