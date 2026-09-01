"""Which measures hold their values across books?

PLAN2 step 26, as a repeatable instrument rather than the one-off that produced `checks.PORTABLE`.
Derivation and limits: `docs/evidence/portable-measures.md`.

A measure is **portable** iff all four hold:

1. its floor is established and informative — not degenerate, not wider than its own mean;
2. it is not length-sensitive, since 24 scenes against 71 would compare lengths and not prose;
3. the second book's internal spread fits inside the floor — the floor's *size* transfers;
4. the gap between the two books' group means fits inside the floor — the *value* transfers.

Conditions 3 and 4 are separate on purpose. A measure can hold its value across two books while
being far noisier on one of them (`dialogue_share` fails 3 and 4 both), and a measure can be
tight on both while sitting at a different level on each (`gesture_rate` fails only 4). Either
failure makes a cross-book verdict meaningless, for different reasons.

**Both groups must be written at one code revision each.** This measures premise-portability with
the code held fixed, and that is all it measures: `somatic_share` is portable across these two
premises and swings 0.211 to 0.592 across four code revisions of the *same* plan. Mixing revisions
into a group would inflate its spread and launder unportable measures into the set.

    python scripts/portability.py <group-a-run> [...] --against <group-b-run> [...]

With no arguments it re-runs the published derivation: the four-run *Debt of Years* floor against
the *Ink of the Drowned* panels.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import checks  # noqa: E402
from redthread.replicate import group_panel, observed_floor  # noqa: E402

PUBLISHED_A = [f"runs/current-floor{i}" for i in (1, 2, 3, 4)]
PUBLISHED_B = ["runs/solo-b2-panel1", "runs/solo-b2-panel2"]


def _load(names: list[str]) -> list[tuple[str, list[str]]]:
    from redthread.replicate import committed_texts
    out = [(Path(n).name, committed_texts(n)) for n in names]
    return [(n, t) for n, t in out if t]


def main(argv: list[str]) -> int:
    if "--against" in argv:
        i = argv.index("--against")
        a_names, b_names = argv[1:i], argv[i + 1:]
    else:
        a_names, b_names = PUBLISHED_A, PUBLISHED_B
        print("No runs given — re-running the published derivation.\n")

    a, b = _load(a_names), _load(b_names)
    if len(a) < 2 or len(b) < 2:
        print("Each group needs at least two runs of one plan: a single run gives no spread,\n"
              "and a floor is the thing this whole comparison is judged against.")
        return 2

    a_panel, b_panel = group_panel(a), group_panel(b)
    b_spread = observed_floor(b)
    a_spread = observed_floor(a)
    print(f"Group A: {len(a)} run(s) — {', '.join(n for n, _ in a)}")
    print(f"Group B: {len(b)} run(s) — {', '.join(n for n, _ in b)}\n")
    if len(b) < 4:
        print(f"  Note: group B is n={len(b)}. A range from few samples systematically\n"
              f"  understates spread, so condition 3 is easier to pass than it should be.\n")

    print(f"{'measure':<26} {'A mean':>10} {'B mean':>10} {'B spr':>6} {'floor':>6} "
          f"{'between':>8}  verdict")
    portable: list[str] = []
    for name in sorted(checks.NOISE_FLOOR):
        floor = checks.NOISE_FLOOR[name]
        am = sum(a_panel[name]) / len(a_panel[name])
        bm = sum(b_panel[name]) / len(b_panel[name])
        mean = (abs(am) + abs(bm)) / 2
        between = abs(am - bm) / mean if mean else 0.0

        reasons = []
        if name in checks.LENGTH_SENSITIVE:
            reasons.append("length-sensitive")
        elif not checks.floor_is_established(name):
            reasons.append("floor degenerate — vacuous, not portable")
        elif not checks.floor_is_informative(name):
            reasons.append("floor uninformative")
        else:
            if b_spread[name] > floor:
                reasons.append(f"B spread {b_spread[name]:.0%} > floor")
            if between > floor:
                reasons.append(f"between {between:.0%} > floor")
        if not reasons:
            portable.append(name)
        print(f"{name:<26} {am:>10.3f} {bm:>10.3f} {b_spread[name]:>5.0%} {floor:>5.0%} "
              f"{between:>7.0%}  {'PORTABLE' if not reasons else '; '.join(reasons)}")

    print(f"\n  portable: {', '.join(portable) if portable else 'nothing'}")
    current = sorted(checks.PORTABLE)
    if sorted(portable) != current:
        print(f"  checks.PORTABLE currently says: {', '.join(current)}")
        print("  **These disagree.** Do not edit PORTABLE from this output alone — a change here\n"
              "  is a change to what the project is allowed to claim across books. Write down why\n"
              "  the set moved, in docs/evidence/portable-measures.md, before touching the code.")
    else:
        print("  matches checks.PORTABLE")

    print(f"\n  Group A internal spread, for reference (this is a floor only if nothing was\n"
          f"  ablated between its runs): "
          + ", ".join(f"{n} {a_spread[n]:.0%}" for n in sorted(portable)) if portable else "")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
