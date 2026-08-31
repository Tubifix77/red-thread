"""The declared dependency graph.

Phase 3 of docs/PLAN.md, and the cheapest phase in it: a plan-level answer to a prose question,
deterministic, with no model in the loop and nothing to calibrate.

The design constraint is rule V. Four plan checks have been built and deleted for firing on the
hand-authored reference plan, every one of them because it compared two fields by shared words —
and a well-written plan deliberately echoes its own language. This check reads integers, and the
reference plan predates the field entirely, so most of these tests are about what it does when
nothing has been declared.
"""

from __future__ import annotations

import json
import unittest

from redthread import checks
from redthread.models import Beat, SceneSpec, StorySpec, Thread, ThreadKind


def spec(index: int, depends_on=None) -> SceneSpec:
    return SceneSpec(id=f"s{index}", index=index, summary=f"scene {index}",
                     setting="a room", pov="a", characters=["a", "b"],
                     beats=[Beat(summary="something happens")],
                     depends_on=list(depends_on or []))


def story() -> StorySpec:
    return StorySpec(title="T", premise="p",
                     threads=[Thread(id="t1", name="n", kind=ThreadKind.MAIN,
                                     states=["a", "b"])])


class TestAncestors(unittest.TestCase):
    def test_direct_edges(self):
        plan = [spec(1), spec(2), spec(3, [1, 2])]
        self.assertEqual(checks.ancestors(plan, 3), {1, 2})

    def test_is_transitive(self):
        # The point of asking rather than inferring: a scene that depends on scene 60, which
        # depends on scene 3, reaches scene 3 — and an ending's closure is what says whether the
        # middle is load-bearing.
        plan = [spec(1), spec(2, [1]), spec(3, [2])]
        self.assertEqual(checks.ancestors(plan, 3), {1, 2})

    def test_a_scene_with_no_edges_reaches_nothing(self):
        self.assertEqual(checks.ancestors([spec(1), spec(2)], 2), set())

    def test_an_unknown_index_reaches_nothing(self):
        self.assertEqual(checks.ancestors([spec(1)], 99), set())

    def test_a_diamond_counts_each_scene_once(self):
        plan = [spec(1), spec(2, [1]), spec(3, [1]), spec(4, [2, 3])]
        self.assertEqual(checks.ancestors(plan, 4), {1, 2, 3})

    def test_a_hand_edited_cycle_terminates(self):
        # The planner cannot produce this — forward edges are filtered before they reach a spec —
        # but a hand-edited plan.json can, and a traversal that loops forever is worse than one
        # that reports a violation.
        plan = [spec(1, [2]), spec(2, [1])]
        self.assertEqual(checks.ancestors(plan, 2), {1, 2})


class TestEndingReach(unittest.TestCase):
    def test_an_ending_that_needs_the_whole_book(self):
        plan = [spec(1), spec(2, [1]), spec(3, [2]), spec(4, [3])]
        self.assertEqual(checks.ending_reach(plan), 1.0)

    def test_an_ending_that_needs_only_its_neighbour(self):
        plan = [spec(1), spec(2), spec(3), spec(4, [3])]
        self.assertAlmostEqual(checks.ending_reach(plan), 1 / 3)

    def test_a_plan_that_declares_nothing_is_zero_rather_than_perfect(self):
        # Zero here means "nobody said", and the distinction matters: an undeclared plan must not
        # read as an ending that depends on nothing, nor as one that depends on everything.
        self.assertEqual(checks.ending_reach([spec(1), spec(2), spec(3)]), 0.0)

    def test_an_empty_plan_is_zero(self):
        self.assertEqual(checks.ending_reach([]), 0.0)


class TestCheckDependencyGraph(unittest.TestCase):
    def test_a_plan_that_declares_nothing_is_silent(self):
        # Rule V, in its strongest form: the hand-authored reference plan predates this field.
        # A check that fires on it is wrong, and "nobody was asked" is not a defect.
        plan = [spec(i) for i in range(1, 20)]
        self.assertEqual(checks.check_dependency_graph(plan, story()), [])

    def test_a_healthy_graph_is_clean(self):
        plan = [spec(1)] + [spec(i, [i - 1]) for i in range(2, 20)]
        self.assertEqual(checks.check_dependency_graph(plan, story()), [])

    def test_a_forward_edge_is_a_major(self):
        plan = [spec(1), spec(2, [5]), spec(3), spec(4), spec(5)]
        found = checks.check_dependency_graph(plan, story())
        self.assertEqual([v.kind for v in found], ["dependency_not_backwards"])

    def test_a_self_edge_is_a_major(self):
        plan = [spec(1), spec(2, [2])]
        self.assertEqual([v.kind for v in checks.check_dependency_graph(plan, story())],
                         ["dependency_not_backwards"])

    def test_an_edge_to_a_scene_that_does_not_exist(self):
        plan = [spec(1), spec(2, [99])]
        self.assertEqual([v.kind for v in checks.check_dependency_graph(plan, story())],
                         ["dependency_unknown_scene"])

    def test_a_shallow_ending_is_reported(self):
        plan = [spec(i) for i in range(1, 20)]
        plan[-1] = spec(19, [18])
        plan[17] = spec(18, [17])
        found = checks.check_dependency_graph(plan, story())
        self.assertIn("ending_reaches_shallow", [v.kind for v in found])

    def test_a_deep_ending_is_not_reported(self):
        plan = [spec(1)] + [spec(i, [i - 1]) for i in range(2, 20)]
        self.assertNotIn("ending_reaches_shallow",
                         [v.kind for v in checks.check_dependency_graph(plan, story())])

    def test_a_short_plan_is_not_judged_on_reach(self):
        # Under nine scenes "the ending only needs the last few" describes a novella, not a sag.
        plan = [spec(1), spec(2), spec(3, [2])]
        self.assertNotIn("ending_reaches_shallow",
                         [v.kind for v in checks.check_dependency_graph(plan, story())])

    def test_it_runs_inside_the_plan_audit(self):
        plan = [spec(1), spec(2, [2])]
        kinds = [v.kind for v in checks.audit_plan(plan, story())]
        self.assertIn("dependency_not_backwards", kinds)


class TestPlannerAcceptsDependencies(unittest.TestCase):
    """Structure is not the model's to break — the same guarantee as `to_state`."""

    def _apply(self, row):
        from redthread.planner import _apply_scene_content
        target = spec(5)
        story_spec = StorySpec(title="T", premise="p")
        _apply_scene_content(target, row, story_spec)
        return target

    def test_backwards_edges_are_kept(self):
        self.assertEqual(self._apply({"depends_on": [2, 3]}).depends_on, [2, 3])

    def test_forward_edges_are_dropped(self):
        self.assertEqual(self._apply({"depends_on": [7, 2]}).depends_on, [2])

    def test_a_self_edge_is_dropped(self):
        self.assertEqual(self._apply({"depends_on": [5]}).depends_on, [])

    def test_junk_is_dropped_rather_than_raising(self):
        self.assertEqual(self._apply({"depends_on": ["scene three", None, 2]}).depends_on, [2])

    def test_duplicates_collapse_and_the_result_is_ordered(self):
        self.assertEqual(self._apply({"depends_on": [3, 2, 3]}).depends_on, [2, 3])

    def test_an_absent_field_leaves_the_spec_alone(self):
        self.assertEqual(self._apply({"summary": "x"}).depends_on, [])

    def test_the_schema_asks_for_it(self):
        from redthread.planner import SCENES_PROMPT
        self.assertIn("depends_on", SCENES_PROMPT)

    def test_it_survives_a_save_and_load(self):
        from redthread.models import _from_jsonable, _to_jsonable
        original = spec(4, [1, 2])
        rebuilt = _from_jsonable(SceneSpec, json.loads(json.dumps(_to_jsonable(original))))
        self.assertEqual(rebuilt.depends_on, [1, 2])

    def test_a_plan_written_before_the_field_still_loads(self):
        row = {"id": "s1", "index": 1, "summary": "x"}
        self.assertEqual(_from_jsonable_spec(row).depends_on, [])


def _from_jsonable_spec(row):
    from redthread.models import _from_jsonable
    return _from_jsonable(SceneSpec, row)


if __name__ == "__main__":
    unittest.main()


class TestAnEndingThatDeclaresNothing(unittest.TestCase):
    """An ending that declared nothing and an ending that depends on nothing both read as a
    reach of zero, and they are not the same finding.

    A live plan produced the case within an hour of the check shipping: `solo-b5` had 22 of its
    24 scenes declaring dependencies and its *final* scene declaring none, and was reported as
    having a middle the reader could skip. Nothing was known about its middle either way — which
    is the conflation this check already rejects one level up, where a plan declaring nothing at
    all is passed over in silence.
    """

    def _plan(self, final_deps):
        plan = [spec(1)] + [spec(i, [i - 1]) for i in range(2, 20)]
        plan[-1] = spec(19, final_deps)
        return plan

    def test_a_silent_ending_is_reported_as_silent(self):
        kinds = [v.kind for v in checks.check_dependency_graph(self._plan([]), story())]
        self.assertIn("ending_declares_nothing", kinds)
        self.assertNotIn("ending_reaches_shallow", kinds)

    def test_a_genuinely_shallow_ending_is_still_reported_as_shallow(self):
        plan = [spec(i) for i in range(1, 20)]
        plan[17] = spec(18, [17])
        plan[-1] = spec(19, [18])
        kinds = [v.kind for v in checks.check_dependency_graph(plan, story())]
        self.assertIn("ending_reaches_shallow", kinds)
        self.assertNotIn("ending_declares_nothing", kinds)

    def test_a_deep_ending_reports_neither(self):
        kinds = [v.kind for v in checks.check_dependency_graph(self._plan([18]), story())]
        self.assertNotIn("ending_declares_nothing", kinds)
        self.assertNotIn("ending_reaches_shallow", kinds)

    def test_a_plan_declaring_nothing_at_all_still_says_nothing(self):
        # The rule one level up, unchanged: silence from everybody is not a finding about the
        # ending either.
        plan = [spec(i) for i in range(1, 20)]
        self.assertEqual(checks.check_dependency_graph(plan, story()), [])

    def test_a_short_plan_is_not_judged_on_its_ending(self):
        plan = [spec(1), spec(2, [1]), spec(3)]
        self.assertEqual([v.kind for v in checks.check_dependency_graph(plan, story())], [])
