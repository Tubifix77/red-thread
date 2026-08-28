"""Plan-level audit: the project's two acceptance markers (docs/TESTING.md).

Marker 1 — distinct sub-arcs rather than famous three-act beats.
Marker 2 — the midpoint shifts stakes rather than repeating the opening conflict.

Both must catch a plan that fails them, and both must leave a good plan alone. The reference
plan in `examples/build_inherited_glitch.py` is asserted clean here, so a regression in either
check shows up as a failing test rather than as a quietly worse manuscript.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import checks
from redthread.models import (SceneSpec, StorySpec, Thread, ThreadKind, Transition)


def thread(tid: str, kind: ThreadKind = ThreadKind.SUBPLOT, **kwargs) -> Thread:
    return Thread(id=tid, name=tid, kind=kind,
                  states=["dormant", "planted", "complicated", "escalated", "paid_off"],
                  **kwargs)


def sc(index: int, ops: dict[str, str | None]) -> SceneSpec:
    """A scene spec carrying only what the plan-level checks read: thread target states."""
    return SceneSpec(
        id=f"s{index:02d}", index=index, pov="a", characters=["a"],
        thread_ops={tid: Transition(to_state=state) for tid, state in ops.items()})


def kinds(violations) -> set[str]:
    return {v.kind for v in violations}


# A plan that passes both markers: MAIN owns 1/4/7/9, SUB owns 3/6/8/10 outright, and every
# thread gains state between scenes 4 and 7 (the middle third of a 1..10 span).
def good_plan() -> tuple[StorySpec, list[SceneSpec]]:
    story = StorySpec(title="T", premise="p", threads=[
        thread("MAIN", ThreadKind.MAIN, concealment="c", payoff="p"),
        thread("SUB", ThreadKind.SUBPLOT, concealment="c", payoff="p"),
    ])
    plan = [
        sc(1, {"MAIN": "planted"}),
        sc(3, {"SUB": "planted"}),
        sc(4, {"MAIN": "complicated"}),
        sc(6, {"SUB": "complicated"}),
        sc(7, {"MAIN": "escalated"}),
        sc(8, {"SUB": "escalated"}),
        sc(9, {"MAIN": "paid_off"}),
        sc(10, {"SUB": "paid_off"}),
    ]
    return story, plan


class TestMarker1SubplotIndependence(unittest.TestCase):
    def test_good_plan_is_clean(self):
        story, plan = good_plan()
        found = checks.check_subplot_independence(plan, story)
        self.assertEqual(found, [], f"good plan flagged: {[str(v) for v in found]}")

    def test_all_threads_main_is_flagged(self):
        story = StorySpec(title="T", premise="p", threads=[
            thread("A", ThreadKind.MAIN), thread("B", ThreadKind.MAIN)])
        plan = [sc(1, {"A": "planted"}), sc(2, {"B": "planted"})]
        self.assertIn("no_subplots", kinds(checks.check_subplot_independence(plan, story)))

    def test_subplot_riding_along_with_main_is_flagged(self):
        """The failure that looks like success: a subplot that never has the page to itself."""
        story = StorySpec(title="T", premise="p", threads=[
            thread("MAIN", ThreadKind.MAIN), thread("SUB", ThreadKind.SUBPLOT)])
        plan = [sc(i, {"MAIN": "planted", "SUB": "planted"}) for i in (1, 2, 3, 4)]
        found = checks.check_subplot_independence(plan, story)
        self.assertIn("decorative_subplots", kinds(found))

    def test_partial_overlap_is_accepted(self):
        story = StorySpec(title="T", premise="p", threads=[
            thread("MAIN", ThreadKind.MAIN), thread("SUB", ThreadKind.SUBPLOT)])
        plan = [sc(1, {"MAIN": "planted"}), sc(2, {"MAIN": "complicated", "SUB": "planted"}),
                sc(3, {"SUB": "complicated"}), sc(4, {"SUB": "escalated"})]
        found = checks.check_subplot_independence(plan, story)
        self.assertNotIn("decorative_subplots", kinds(found))

    def test_empty_plan_is_a_blocker(self):
        story = StorySpec(title="T", premise="p", threads=[thread("MAIN", ThreadKind.MAIN)])
        self.assertIn("no_threads", kinds(checks.check_subplot_independence([], story)))


class TestMarker2StakesProgression(unittest.TestCase):
    def test_good_plan_is_clean(self):
        story, plan = good_plan()
        found = checks.check_stakes_progression(plan, story)
        self.assertEqual(found, [], f"good plan flagged: {[str(v) for v in found]}")

    def test_reentering_a_state_is_flagged_as_a_repeat(self):
        """The author's marker: weak models repeat early conflict instead of complicating it."""
        story = StorySpec(title="T", premise="p", threads=[thread("A", ThreadKind.MAIN)])
        plan = [sc(1, {"A": "planted"}), sc(2, {"A": "complicated"}),
                sc(3, {"A": "complicated"}), sc(4, {"A": "paid_off"})]
        found = checks.check_stakes_progression(plan, story)
        self.assertIn("state_repeat", kinds(found))

    def test_backwards_state_move_is_flagged(self):
        story = StorySpec(title="T", premise="p", threads=[thread("A", ThreadKind.MAIN)])
        plan = [sc(1, {"A": "escalated"}), sc(2, {"A": "planted"}), sc(3, {"A": "paid_off"})]
        self.assertIn("state_regression", kinds(checks.check_stakes_progression(plan, story)))

    def test_midpoint_stall_is_flagged(self):
        """Everything happens at the ends; the middle third treads water."""
        story = StorySpec(title="T", premise="p", threads=[
            thread("A", ThreadKind.MAIN), thread("B", ThreadKind.SUBPLOT)])
        plan = [sc(1, {"A": "planted", "B": "planted"}),
                sc(2, {"A": "complicated", "B": "complicated"}),
                sc(3, {}), sc(4, {}), sc(5, {}), sc(6, {}), sc(7, {}),
                sc(9, {"A": "escalated", "B": "escalated"}),
                sc(10, {"A": "paid_off", "B": "paid_off"})]
        found = checks.check_stakes_progression(plan, story)
        self.assertIn("midpoint_stall", kinds(found))

    def test_unpaid_thread_is_flagged(self):
        story = StorySpec(title="T", premise="p", threads=[thread("A", ThreadKind.MAIN)])
        plan = [sc(1, {"A": "planted"}), sc(2, {"A": "complicated"})]
        self.assertIn("unpaid_thread", kinds(checks.check_stakes_progression(plan, story)))

    def test_missed_deadline_is_flagged(self):
        story = StorySpec(title="T", premise="p", threads=[
            thread("A", ThreadKind.MAIN, deadline_scene=3)])
        plan = [sc(1, {"A": "planted"}), sc(2, {"A": "complicated"}),
                sc(3, {"A": "escalated"}), sc(9, {"A": "paid_off"})]
        self.assertIn("missed_deadline", kinds(checks.check_stakes_progression(plan, story)))

    def test_state_outside_the_machine_is_a_blocker(self):
        story = StorySpec(title="T", premise="p", threads=[thread("A", ThreadKind.MAIN)])
        plan = [sc(1, {"A": "planted"}), sc(2, {"A": "gone_sideways"}),
                sc(3, {"A": "paid_off"})]
        found = checks.check_stakes_progression(plan, story)
        self.assertIn("unknown_state", kinds(found))
        self.assertTrue(any(v.kind == "unknown_state" and v.severity.value == "blocker"
                            for v in found))


class TestConcealmentAndPacing(unittest.TestCase):
    def test_main_thread_without_concealment_flagged(self):
        story = StorySpec(title="T", premise="p", threads=[
            thread("A", ThreadKind.MAIN, payoff="p")])
        self.assertIn("no_concealment", kinds(checks.check_concealment([], story)))

    def test_thread_without_payoff_flagged(self):
        story = StorySpec(title="T", premise="p", threads=[
            thread("A", ThreadKind.SUBPLOT, concealment="c")])
        self.assertIn("no_payoff", kinds(checks.check_concealment([], story)))

    def test_uniform_scene_length_flagged(self):
        story, plan = good_plan()
        for spec in plan:
            spec.word_target = 1000
        self.assertIn("uniform_scene_length", kinds(checks.audit_plan(plan, story)))

    def test_varied_scene_length_not_flagged(self):
        story, plan = good_plan()
        for i, spec in enumerate(plan):
            spec.word_target = 800 + i * 100
        self.assertNotIn("uniform_scene_length", kinds(checks.audit_plan(plan, story)))


class TestReferencePlan(unittest.TestCase):
    """The hand-authored Concept 1 plan must pass both markers.

    This is the fixture the rest of the system is developed against, so if a check regresses or
    the plan is edited into a degenerate shape, this test is where it surfaces.
    """

    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "examples"))
        import build_inherited_glitch as builder
        self.story = builder.build_story()
        self.plan = builder.build_plan()

    def test_audit_is_clean(self):
        found = checks.audit_plan(self.plan, self.story)
        self.assertEqual(found, [],
                         "reference plan should pass every plan-level check: "
                         + "; ".join(str(v) for v in found))

    def test_subplot_owns_scenes_the_main_thread_does_not(self):
        scene_map = checks.thread_scene_map(self.plan)
        main_scenes = set(scene_map["T-CODE"])
        well_scenes = set(scene_map["T-WELL"])
        self.assertTrue(well_scenes - main_scenes,
                        "T-WELL must own at least one scene of its own")
        self.assertFalse(well_scenes & main_scenes,
                         "T-WELL was designed to share no scene with the main thread")

    def test_every_thread_advances_through_the_midpoint(self):
        found = checks.check_stakes_progression(self.plan, self.story)
        self.assertNotIn("midpoint_stall", kinds(found))
        self.assertNotIn("state_repeat", kinds(found))

    def test_every_thread_is_paid_off(self):
        for t in self.story.threads:
            seq = checks.planned_state_sequence(self.plan, t.id)
            self.assertTrue(seq, f"{t.id} has no planned state changes")
            self.assertEqual(seq[-1][1], t.states[-1], f"{t.id} is never paid off")


class TestProhibitionPhrasing(unittest.TestCase):
    """A Forbid says what must not happen. A live plan wrote every concealment as a negation
    instead — "The fugitive's true purpose is not revealed" — and read literally that demands the
    reveal. Scene 8 of a 27-scene run was blocked for finalising a decision its own post line
    required, after seven scenes and an hour of generation had already been spent."""

    def _spec(self, *forbid: str) -> SceneSpec:
        return SceneSpec(id="s1", index=1, summary="x",
                         thread_ops={"T": Transition(post=["something happens"],
                                                     forbid=list(forbid))})

    def _story(self) -> StorySpec:
        return StorySpec(title="t", premise="p",
                         threads=[Thread(id="T", name="The Allegiance")])

    def test_a_negated_forbid_is_reported(self):
        found = checks.check_prohibition_phrasing(
            [self._spec("Dain's decision is not finalized")], self._story())
        self.assertIn("negated_prohibition", kinds(found))

    def test_a_positive_forbid_passes(self):
        found = checks.check_prohibition_phrasing(
            [self._spec("Dain learns who ordered the purge")], self._story())
        self.assertEqual(found, [])

    def test_an_empty_placeholder_is_not_a_negation(self):
        for placeholder in ("none", "nothing", "-", "N/A"):
            with self.subTest(placeholder=placeholder):
                self.assertFalse(checks.is_negated_prohibition(placeholder))

    def test_the_inversion_names_the_forbidden_event(self):
        cases = {
            "The fugitive's true purpose is not revealed.":
                "The fugitive's true purpose is revealed.",
            "The allegiance's full implications are not yet revealed.":
                "The allegiance's full implications are revealed.",
            "Dain is not told the full truth about his past":
                "Dain is told the full truth about his past",
            "The Bureau never explains its methods":
                "The Bureau explains its methods",
        }
        for negated, expected in cases.items():
            with self.subTest(negated=negated):
                self.assertEqual(checks.positive_prohibition(negated), expected)

    def test_a_positive_prohibition_is_left_alone(self):
        text = "Dain learns who ordered the purge"
        self.assertEqual(checks.positive_prohibition(text), text)

    def test_audit_surfaces_it(self):
        found = checks.audit_plan([self._spec("Riven's survival is not confirmed")],
                                  self._story())
        self.assertIn("negated_prohibition", kinds(found))


class TestStaleProhibitions(unittest.TestCase):
    """`Thread.reveal_scene` exists because a scene once got a brief that both required and
    forbade a reveal. Per-scene Forbid entries never got the same treatment: scene 13 of a live
    run was held back for revealing an enclave the plan's own schedule had unsealed at scene 10."""

    def _plan(self, index: int, forbid: str) -> list[SceneSpec]:
        return [SceneSpec(id="s", index=index, summary="x",
                          thread_ops={"T": Transition(forbid=[forbid])})]

    def _story(self, reveal_scene: int | None) -> StorySpec:
        return StorySpec(title="t", premise="p",
                         threads=[Thread(id="T", name="The Enclave", concealment="the enclave",
                                         reveal_scene=reveal_scene)])

    def test_a_disclosure_forbidden_after_its_own_reveal_is_stale(self):
        found = checks.check_stale_prohibitions(
            self._plan(13, "The enclave is revealed"), self._story(10))
        self.assertIn("stale_prohibition", kinds(found))

    def test_the_same_forbid_before_the_reveal_stands(self):
        found = checks.check_stale_prohibitions(
            self._plan(4, "The enclave is revealed"), self._story(10))
        self.assertEqual(found, [])

    def test_a_craft_rule_is_never_stale(self):
        """"the founders' motives being explained" is a rule against narrator gloss, not a
        concealment, and holds for the whole book however much the reader knows."""
        found = checks.check_stale_prohibitions(
            self._plan(13, "the founders' motives being explained"), self._story(2))
        self.assertEqual(found, [])

    def test_a_plot_rule_is_never_stale(self):
        found = checks.check_stale_prohibitions(
            self._plan(13, "Dain kills Riven"), self._story(2))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
