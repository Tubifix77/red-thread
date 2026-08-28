"""Every blocking violation a scene check emits must have a repair that can reach it.

This file exists because of a bug the other 292 tests could not have caught. `check_seam` gained
a `seam_tail_copy` violation; nothing gained a repair for it. It fell through to sentence-local
surgery, which rewrites the one sentence a quote falls in — while the check compares the whole
final 25 words. On a live 27-scene run, scene 4 ended in two sentences copied verbatim from
scene 3, surgery rewrote one of them per round, the check re-fired, and the scene burned its
entire repair budget without ever converging.

The tests that existed were all of the form "given this input, this check fires" and "given this
violation, this repair fixes it". None of them asked the structural question: *is there a repair
for every violation at all?* This one does, by reading the checks' own source, so a new check
without a repair route fails the suite the day it is added rather than the day it is run.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import checks
from redthread.pipeline import DEDICATED_REPAIRS, DELETE_KINDS, NO_REPAIR, REMEDIES

CHECKS_SOURCE = Path(checks.__file__).read_text(encoding="utf-8")


def _scene_check_functions() -> list[str]:
    """The check functions `checks.run_all` actually calls on a drafted scene.

    Read from the source rather than hardcoded, so adding a check to `run_all` brings it under
    this test automatically. Plan-level checks (`audit_plan`) are excluded on purpose: their
    violations are answered by revising the plan, not by repairing prose.
    """
    tree = ast.parse(CHECKS_SOURCE)
    run_all = next(n for n in tree.body
                   if isinstance(n, ast.FunctionDef) and n.name == "run_all")
    return [n.func.id for n in ast.walk(run_all)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id.startswith("check_")]


def _blocking_kinds() -> dict[str, str]:
    """kind -> the function that emits it, for every BLOCKER/MAJOR a scene check can raise.

    MINOR violations are excluded because they are advisory by policy: they are logged and do
    not hold a scene back, so an unrepairable MINOR costs nothing.
    """
    tree = ast.parse(CHECKS_SOURCE)
    wanted = set(_scene_check_functions())
    found: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in wanted:
            continue
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                    and call.func.id == "Violation" and len(call.args) >= 2):
                continue
            kind, severity = call.args[0], call.args[1]
            if not isinstance(kind, ast.Constant):
                continue
            # The severity is sometimes a conditional — `check_seam` grades an echo MAJOR at
            # three shared runs and MINOR at two — so walk the expression rather than expecting
            # a bare attribute. Reading only bare attributes silently skipped `seam_echo`.
            levels = {n.attr for n in ast.walk(severity) if isinstance(n, ast.Attribute)}
            if levels & {"BLOCKER", "MAJOR"}:
                found[kind.value] = node.name
    return found


class TestEveryBlockingKindHasARepair(unittest.TestCase):
    def test_run_all_is_readable(self):
        """If this fails the parser is wrong, and every other test here is vacuous."""
        functions = _scene_check_functions()
        self.assertIn("check_seam", functions)
        self.assertIn("check_length", functions)
        self.assertGreater(len(functions), 10)

    def test_the_scan_finds_the_kind_that_caused_this_file_to_exist(self):
        kinds = _blocking_kinds()
        self.assertEqual(kinds.get("seam_tail_copy"), "check_seam")
        self.assertNotIn("seam_reset", kinds, "MINOR, and so advisory by policy")

    def test_every_blocking_kind_is_routed_somewhere(self):
        unrouted = {kind: fn for kind, fn in _blocking_kinds().items()
                    if kind not in REMEDIES and kind not in DEDICATED_REPAIRS
                    and kind not in DELETE_KINDS and kind not in NO_REPAIR}
        self.assertEqual(unrouted, {}, (
            "these checks can hold a scene back and no repair addresses them, so a scene that "
            "trips one will spend its whole budget and never commit: "
            f"{sorted(unrouted)}. Add a REMEDIES line, a dedicated action, or — if nothing can "
            "repair it — an entry in NO_REPAIR saying so."))

    def test_a_region_check_is_not_left_to_sentence_local_repair(self):
        """The specific failure mode: a check whose scope is wider than surgery's reach.

        Surgery rewrites the single sentence containing a violation's quote. A check that
        compares a *region* — the first 60 words, the last 25 — can keep firing after that
        sentence is replaced, because the rest of the region still matches. Those kinds need a
        repair whose unit is the region, and `DEDICATED_REPAIRS` is where that is declared.
        """
        for kind in ("seam_echo", "seam_tail_copy"):
            with self.subTest(kind=kind):
                self.assertIn(kind, DEDICATED_REPAIRS)

    def test_nothing_claims_a_repair_for_a_kind_that_no_longer_exists(self):
        """A stale route is a quieter bug than a missing one, but still a lie about coverage."""
        from redthread import verify
        emitted = set(_blocking_kinds())
        emitted |= {k for k in REMEDIES
                    if k in Path(verify.__file__).read_text(encoding="utf-8")}
        # MINOR kinds may legitimately carry a remedy; only the dedicated actions are asserted,
        # since each one is a branch of live routing code.
        for kind in DEDICATED_REPAIRS:
            with self.subTest(kind=kind):
                self.assertIn(kind, emitted | {"length"},
                              f"{kind} has a dedicated repair but no check emits it")


if __name__ == "__main__":
    unittest.main()
