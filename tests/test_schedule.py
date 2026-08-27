"""The deterministic scheduler.

The central claim of `redthread.schedule` is that both acceptance markers hold *by construction*
— that no generate-and-retry loop is needed because the structure is computed rather than
proposed. The way to test a claim like that is not one example but a sweep: every plausible
combination of manuscript length and thread mix must come out of the scheduler audit-clean.

If this file goes red, the planner has stopped being able to trust its own output and has to fall
back to checking-and-repairing, which is exactly the design this module exists to avoid.
"""

from __future__ import annotations

import itertools
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import checks
from redthread.models import Beat, SceneSpec, Severity, StorySpec, Thread, ThreadKind
from redthread.schedule import (Schedule, chapter_of, concreteness, midpoint_window,
                                scene_count, schedule_threads, score_spec, to_scene_specs,
                                vaguest_first, word_targets)

FIVE = ["dormant", "planted", "complicated", "escalated", "paid_off"]
CHOICE = ["dormant", "visible", "costed", "forced", "chosen"]


def thread(tid: str, kind: ThreadKind, states: list[str] | None = None,
           deadline: int | None = None) -> Thread:
    return Thread(id=tid, name=f"Thread {tid}", kind=kind, states=list(states or FIVE),
                  concealment="something withheld", payoff="something resolved",
                  deadline_scene=deadline)


def thread_mix(subplots: int = 1, relationships: int = 0, thematic: int = 0) -> list[Thread]:
    out = [thread("MAIN", ThreadKind.MAIN)]
    out += [thread(f"SUB{i}", ThreadKind.SUBPLOT) for i in range(subplots)]
    out += [thread(f"REL{i}", ThreadKind.RELATIONSHIP) for i in range(relationships)]
    out += [thread(f"THM{i}", ThreadKind.THEMATIC, CHOICE) for i in range(thematic)]
    return out


def plan_for(threads: list[Thread], n_scenes: int) -> tuple[StorySpec, list[SceneSpec]]:
    story = StorySpec(title="Sweep", premise="A premise.", threads=threads)
    schedule = schedule_threads(threads, n_scenes)
    return story, to_scene_specs(schedule, threads, n_scenes * 1100)


def serious(violations) -> list:
    return [v for v in violations if v.severity is not Severity.MINOR]


class TestAuditCleanBySweep(unittest.TestCase):
    """The load-bearing test. Both markers, across the space of realistic manuscripts."""

    LENGTHS = [6, 8, 10, 12, 15, 20, 30, 45, 60, 90]
    MIXES = [(1, 0, 0), (1, 1, 0), (1, 0, 1), (2, 1, 1), (3, 1, 1), (4, 2, 1), (2, 0, 0)]

    def test_every_length_and_mix_is_audit_clean(self):
        failures = []
        for n_scenes, mix in itertools.product(self.LENGTHS, self.MIXES):
            story, specs = plan_for(thread_mix(*mix), n_scenes)
            found = serious(checks.audit_plan(specs, story))
            if found:
                failures.append(f"n={n_scenes} mix={mix}: "
                                + "; ".join(v.kind for v in found))
        self.assertEqual(failures, [], "\n".join(failures))

    def test_deadlines_are_respected(self):
        for n_scenes in (12, 20, 40):
            for deadline in (max(4, n_scenes // 2), n_scenes - 2, n_scenes):
                threads = thread_mix(1, 1)
                threads[0] = thread("MAIN", ThreadKind.MAIN, deadline=deadline)
                story, specs = plan_for(threads, n_scenes)
                found = serious(checks.audit_plan(specs, story))
                self.assertEqual(found, [],
                                 f"n={n_scenes} deadline={deadline}: "
                                 + "; ".join(v.kind for v in found))


class TestArcIntegrity(unittest.TestCase):
    def test_each_thread_walks_its_states_in_order_once(self):
        threads = thread_mix(2, 1, 1)
        story, specs = plan_for(threads, 20)
        for t in threads:
            seq = [state for _, state in checks.planned_state_sequence(specs, t.id)]
            self.assertEqual(seq, t.states[1:],
                             f"{t.id} did not walk its states in order exactly once")

    def test_terminal_state_is_always_reached(self):
        for n_scenes in (6, 13, 27):
            threads = thread_mix(2, 1)
            story, specs = plan_for(threads, n_scenes)
            for t in threads:
                seq = checks.planned_state_sequence(specs, t.id)
                self.assertEqual(seq[-1][1], t.states[-1], f"{t.id} unpaid at n={n_scenes}")

    def test_each_thread_transitions_at_most_once_per_scene(self):
        """Two transitions of one thread in a scene would collapse into a single state change
        and silently lose a beat of the arc.

        Note this is about one thread, not one scene: two *different* threads both reaching
        'complicated' in the same scene is normal and fine.
        """
        threads = thread_mix(3, 1, 1)
        schedule = schedule_threads(threads, 9)
        for t in threads:
            scenes = [i for i, _ in schedule.transitions_for(t.id)]
            self.assertEqual(scenes, sorted(set(scenes)),
                             f"{t.id} transitions more than once in some scene: {scenes}")

    def test_every_thread_advances_through_the_midpoint(self):
        """Marker 2 stated positively rather than as the absence of a violation."""
        n_scenes = 18
        mid_start, mid_end = midpoint_window(n_scenes)
        threads = thread_mix(2, 1, 1)
        story, specs = plan_for(threads, n_scenes)
        for t in threads:
            seq = checks.planned_state_sequence(specs, t.id)
            before = max((t.state_index(s) for i, s in seq if i < mid_start), default=-1)
            during = max((t.state_index(s) for i, s in seq if mid_start <= i <= mid_end),
                         default=-1)
            self.assertGreater(during, before,
                               f"{t.id} gains nothing between scenes {mid_start}-{mid_end}")


class TestSubplotIndependence(unittest.TestCase):
    """Marker 1 stated positively: some thread must own scenes the main thread does not."""

    def test_every_non_main_thread_owns_a_scene_of_its_own(self):
        for n_scenes in (8, 12, 20, 35):
            threads = thread_mix(2, 1, 1)
            schedule = schedule_threads(threads, n_scenes)
            main_scenes = set(schedule.scenes_for("MAIN"))
            for t in threads[1:]:
                own = set(schedule.scenes_for(t.id))
                self.assertTrue(own - main_scenes,
                                f"{t.id} shares every scene with the main thread at "
                                f"n={n_scenes} — a subplot that never has the page to itself")

    def test_falls_back_gracefully_when_there_is_no_room(self):
        """With very few scenes there may be no free slot. The scheduler must still produce a
        usable plan rather than raise or loop."""
        threads = thread_mix(3, 2, 1)
        schedule = schedule_threads(threads, 3)
        self.assertTrue(schedule.moves)
        self.assertLessEqual(max(schedule.moves), 3)


class TestSceneCoverage(unittest.TestCase):
    def test_no_scene_is_left_without_a_job(self):
        """A scene with no thread_ops reaches the writer with nothing to accomplish, and the
        brief says as much. Every scene must serve something."""
        for n_scenes in (7, 11, 24, 50):
            schedule = schedule_threads(thread_mix(2, 1), n_scenes)
            missing = [i for i in range(1, n_scenes + 1) if not schedule.moves.get(i)]
            self.assertEqual(missing, [], f"scenes with no job at n={n_scenes}: {missing}")

    def test_filler_appearances_carry_no_state_change(self):
        schedule = schedule_threads(thread_mix(1), 12)
        specs = to_scene_specs(schedule, thread_mix(1), 12000)
        # Every spec has at least one thread; some carry to_state=None.
        self.assertTrue(all(s.thread_ops for s in specs))
        self.assertTrue(any(op.to_state is None
                            for s in specs for op in s.thread_ops.values()))

    def test_preconditions_are_filled_from_the_schedule(self):
        """`pre` is free information the writing session cannot infer, so the scheduler supplies
        it rather than asking a model to restate it."""
        threads = thread_mix(1)
        story, specs = plan_for(threads, 12)
        later = [s for s in specs if s.index > 4 and s.thread_ops]
        self.assertTrue(any(op.pre for s in later for op in s.thread_ops.values()))

    def test_indices_and_chapters_are_sane(self):
        story, specs = plan_for(thread_mix(1), 13)
        self.assertEqual([s.index for s in specs], list(range(1, 14)))
        self.assertEqual(chapter_of(1), 1)
        self.assertEqual(chapter_of(3), 1)
        self.assertEqual(chapter_of(4), 2)
        self.assertTrue(all(s.chapter >= 1 for s in specs))


class TestShape(unittest.TestCase):
    def test_scene_count_tracks_length(self):
        self.assertEqual(scene_count(11000, 1100), 10)
        self.assertEqual(scene_count(90000, 1500), 60)
        self.assertGreaterEqual(scene_count(500), 3, "never fewer than three scenes")

    def test_word_targets_vary(self):
        targets = word_targets(12, 13200)
        self.assertGreater(len(set(targets)), 4, "uniform scene length is a pacing tell")

    def test_word_targets_total_near_the_request(self):
        for n, total in ((10, 11000), (30, 45000), (60, 90000)):
            targets = word_targets(n, total)
            self.assertAlmostEqual(sum(targets) / total, 1.0, delta=0.08)

    def test_word_targets_are_reproducible(self):
        self.assertEqual(word_targets(12, 13200, seed=3), word_targets(12, 13200, seed=3))

    def test_no_scene_target_is_unwritably_small(self):
        self.assertTrue(all(t >= 400 for t in word_targets(40, 20000)))

    def test_uniform_length_would_have_been_flagged(self):
        """Guard on the guard: confirm `audit_plan` really does catch uniform targets, so the
        variation above is doing something."""
        story, specs = plan_for(thread_mix(1), 12)
        for spec in specs:
            spec.word_target = 1100
        self.assertIn("uniform_scene_length",
                      {v.kind for v in checks.audit_plan(specs, story)})


class TestConcreteness(unittest.TestCase):
    """A proxy for CONCOCT's trained evaluator. It only has to *order* a frontier."""

    def test_concrete_prose_outranks_abstraction(self):
        concrete = ("Siv finds line 4471 unreachable and writes the number in her notebook "
                    "at the bench in substation four")
        abstract = ("The protagonist comes to an understanding about the nature of the "
                    "relationship and its implications")
        self.assertGreater(concreteness(concrete), concreteness(abstract))

    def test_empty_text_scores_zero(self):
        self.assertEqual(concreteness(""), 0.0)
        self.assertEqual(concreteness("   "), 0.0)

    def test_score_is_bounded(self):
        for text in ("", "a", "Siv 4471 door bench truck valve key letter Hallowmere 02:17",
                     "understanding meaning significance identity relationship tension"):
            self.assertGreaterEqual(concreteness(text), 0.0)
            self.assertLessEqual(concreteness(text), 1.0)

    def test_a_spec_without_beats_scores_below_one_with_beats(self):
        bare = SceneSpec(id="a", index=1, summary="Siv finds the branch at the bench.")
        filled = SceneSpec(id="b", index=2, summary="Siv finds the branch at the bench.",
                           beats=[Beat("She checks the log twice against the terminal.")])
        self.assertLess(score_spec(bare), score_spec(filled))

    def test_vaguest_first_puts_the_least_specified_first(self):
        vague = SceneSpec(id="v", index=1, summary="Something significant happens.")
        sharp = SceneSpec(id="s", index=2,
                          summary="Otto opens the number-two intake housing at 06:40.",
                          beats=[Beat("He sets the coupling on the bench, threads up.")])
        order = vaguest_first([sharp, vague])
        self.assertEqual([s.id for s in order], ["v", "s"])

    def test_vaguest_first_is_stable_on_ties(self):
        a = SceneSpec(id="a", index=1)
        b = SceneSpec(id="b", index=2)
        self.assertEqual([s.id for s in vaguest_first([b, a])], ["a", "b"])


class TestMidpointWindow(unittest.TestCase):
    def test_matches_the_checkers_arithmetic(self):
        """Duplicated arithmetic is a liability. Confirm the scheduler and the checker agree."""
        for n in (6, 9, 10, 12, 13, 20, 31):
            specs = [SceneSpec(id=f"s{i}", index=i) for i in range(1, n + 1)]
            indices = sorted(s.index for s in specs)
            lo, hi = indices[0], indices[-1]
            span = hi - lo + 1
            expected = (lo + span // 3, lo + (2 * span) // 3)
            self.assertEqual(midpoint_window(n), expected, f"n={n}")


class TestEdgeCases(unittest.TestCase):
    def test_no_threads_yields_an_empty_schedule(self):
        self.assertEqual(schedule_threads([], 10), Schedule(n_scenes=10))

    def test_zero_scenes_is_handled(self):
        self.assertEqual(schedule_threads(thread_mix(1), 0).moves, {})

    def test_single_state_thread_does_not_crash(self):
        threads = [thread("MAIN", ThreadKind.MAIN, states=["only"])]
        schedule = schedule_threads(threads, 5)
        self.assertTrue(schedule.moves)

    def test_two_state_thread_reaches_its_terminal(self):
        threads = [thread("MAIN", ThreadKind.MAIN, states=["dormant", "done"])]
        story, specs = plan_for(threads, 8)
        seq = checks.planned_state_sequence(specs, "MAIN")
        self.assertEqual(seq[-1][1], "done")

    def test_more_transitions_than_scenes_does_not_hang(self):
        threads = [thread("MAIN", ThreadKind.MAIN,
                          states=[f"s{i}" for i in range(12)])]
        schedule = schedule_threads(threads, 4)
        self.assertTrue(schedule.moves)
        self.assertLessEqual(max(schedule.moves), 4)


if __name__ == "__main__":
    unittest.main()
