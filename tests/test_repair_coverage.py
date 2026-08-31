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


class TestChecksReportEveryInstance(unittest.TestCase):
    """A repair can only reach what a violation points at.

    `_surgical` rewrites or deletes the sentence a violation's quote falls in. So a check that
    finds five defects and reports one violation quoting the first gets one sentence repaired
    per round, while the check keeps firing on the other four — the scene burns its whole budget
    and commits nothing.

    This has now been found four separate times in live runs: `check_somatic` (three somatic
    beats), `check_brief_leak` (seven copied runs), `check_style_leak` (seven again), and
    `check_thematic_gloss` (five gloss constructions). Each was fixed on its own and the lesson
    did not generalise, so it is asserted here instead of remembered.
    """

    def _scene(self, text: str):
        from redthread.models import Scene
        return Scene(spec_id="s01", index=1, text=text)

    def test_somatic_reports_each_beat(self):
        text = ("Her chest tightened at the door. His stomach dropped when he read it. "
                "Something twisted in her throat. She said nothing at all.")
        found = checks.check_somatic(self._scene(text))
        self.assertGreaterEqual(len(found), 2)
        self.assertEqual(len({v.quote for v in found}), len(found))

    def test_thematic_gloss_reports_each_construction(self):
        text = ("She realised then that the founders had known. The stove ticked. "
                "In that moment, she understood the cost. He put the cup down. "
                "That was what it meant to keep a port working.")
        found = checks.check_thematic_gloss(self._scene(text))
        self.assertGreaterEqual(len(found), 2)
        self.assertEqual(len({v.quote for v in found}), len(found))

    def test_brief_leak_reports_each_copied_run(self):
        from redthread.models import Beat, SceneSpec
        spec = SceneSpec(id="s01", index=1, beats=[
            Beat("Sofie copies the altered column into the spare ledger"),
            Beat("Sofie initials the bottom of the berth allocation sheet")])
        text = ("Sofie copies the altered column into the spare ledger. The gate rattled. "
                "Sofie initials the bottom of the berth allocation sheet.")
        found = checks.check_brief_leak(self._scene(text), spec)
        self.assertGreaterEqual(len(found), 2)
        self.assertEqual(len({v.quote for v in found}), len(found))

    def test_style_leak_reports_each_copied_run(self):
        from redthread.models import StorySpec, StyleContract
        # Two different samples, each copied once. Copying one sample twice gives two runs with
        # identical text, and a repair can only locate the first of those.
        first = "The gate had dropped on its hinge and neither of them had fixed it since."
        second = "A queue at the counter moves at the speed of its slowest question."
        story = StorySpec(title="t", premise="p",
                          style=StyleContract(samples=[first, second]))
        text = "She waited. " + first + " The stove ticked. " + second
        found = checks.check_style_leak(self._scene(text), story)
        self.assertGreaterEqual(len(found), 2)
        self.assertEqual(len({v.quote for v in found}), len(found))

    def test_forbidden_phrase_reports_each_sentence(self):
        from redthread.models import StorySpec, StyleContract
        story = StorySpec(title="t", premise="p",
                          style=StyleContract(forbidden_phrases=["the truth"]))
        text = ("He wanted the truth and she had none. The stove ticked. "
                "Nobody said the truth out loud again.")
        found = checks.check_forbidden(self._scene(text), story)
        self.assertEqual(len(found), 2)
        self.assertEqual(len({v.quote for v in found}), 2)

    def test_pov_reports_each_offending_sentence(self):
        """Reported as a bare count with no quote, this routed to whole-scene repair — the only
        thing left when nothing can be located — and scene 2 of a clean-slate run was held by
        three instances of a generic "you" that surgery could have taken one at a time."""
        from redthread.models import StorySpec, StyleContract
        text = ("She put the book down. The fact was not something you simply told. "
                "It was something you carried. He said, \"You know that.\" "
                "Something you waited for. The stove ticked.")
        story = StorySpec(title="t", premise="p", style=StyleContract(pov="third limited"))
        found = checks.check_pov(self._scene(text), story)
        self.assertGreaterEqual(len(found), 2)
        self.assertEqual(len({v.quote for v in found}), len(found))
        self.assertTrue(all(v.quote for v in found), "a violation with no quote cannot be fixed")

    def test_every_reported_quote_locates_in_the_scene(self):
        """A quote a repair cannot find is a violation a repair cannot reach."""
        from redthread.models import Beat, SceneSpec, StorySpec, StyleContract
        text = ("Her chest tightened at the door. She realised then that the founders had "
                "known. He wanted the truth and she had none. Something twisted in her throat. "
                "It was something you carried, something you waited for, something you knew.")
        story = StorySpec(title="t", premise="p",
                          style=StyleContract(pov="third limited",
                                              forbidden_phrases=["the truth"]))
        spec = SceneSpec(id="s01", index=1, beats=[Beat("a beat")])
        found = (checks.check_somatic(self._scene(text))
                 + checks.check_thematic_gloss(self._scene(text))
                 + checks.check_forbidden(self._scene(text), story)
                 + checks.check_pov(self._scene(text), story))
        self.assertTrue(found)
        for v in found:
            with self.subTest(kind=v.kind, quote=v.quote[:40]):
                self.assertIsNotNone(checks.locate_quote(text, v.quote))


if __name__ == "__main__":
    unittest.main()


class TestADeletableSpanMustBeNarration(unittest.TestCase):
    """If the repair for a kind is "delete this span", the span cannot be a character's line.

    The structural lesson of a lost overnight run. `check_thematic_gloss` fired on
    `Kai narrowed his eyes. "This isn't just about punishment."` — a MAJOR, whose remedy is in
    DELETE_KINDS, pointing at a line of dialogue. You cannot delete a character's speech without
    breaking the scene, so the repair failed five times and `write_all` halted the book at scene
    22 of 71. One of two runs of four lost that way.

    The invariant that would have caught it: a kind that is both *deleted* and *blocking* must
    come from a check that excludes dialogue. The set is pinned rather than inferred, so adding a
    blocking delete-kind fails here and whoever adds it has to answer the question.
    """

    def test_only_one_delete_kind_can_block_a_commit(self):
        blocking = set()
        for source in (Path(checks.__file__), Path(checks.__file__).with_name("verify.py")):
            text = source.read_text(encoding="utf-8")
            for kind in DELETE_KINDS:
                pattern = r'Violation\(\s*"' + kind + r'",\s*Severity\.(MAJOR|BLOCKER)'
                if __import__("re").search(pattern, text):
                    blocking.add(kind)
        self.assertEqual(
            blocking, {"thematic_gloss"},
            "a delete-repaired kind that can block a commit must come from a check that excludes "
            "dialogue — a character's line cannot be deleted, and the repair will not converge. "
            "If you are adding one, exclude dialogue as check_thematic_gloss does and then widen "
            "this assertion.")

    def test_the_blocking_delete_kind_excludes_dialogue(self):
        from redthread.models import Scene
        spoken = Scene(spec_id="s", index=1,
                       text='Kai narrowed his eyes. "This isn\'t just about punishment."')
        self.assertEqual(checks.check_thematic_gloss(spoken), [],
                         "the kind whose repair is deletion must never point at speech")

    def test_the_other_delete_kinds_are_advisory(self):
        # thread_prohibition and tell_thematic_gloss are MINOR, so a quote of theirs falling in
        # dialogue costs a wasted repair round rather than a halted book. Recorded so the
        # asymmetry is deliberate rather than lucky.
        self.assertEqual(len(DELETE_KINDS), 3)
        self.assertIn("thread_prohibition", DELETE_KINDS)
        self.assertIn("tell_thematic_gloss", DELETE_KINDS)
