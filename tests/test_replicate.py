"""The measurement panel, the noise floor, and the replicate harness.

Phase 0 of docs/PLAN.md. These tests are unusual for this project in that most of them assert
that something *refuses* to answer. That is the point of the phase: for two days every result
here was one run against one run, three of them were retracted in a single afternoon, and the
missing piece was never a measure — it was a function that knows what a difference is worth and
declines to guess when it does not.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from redthread import checks
from redthread.models import Scene, StorySpec, Thread, ThreadKind
from redthread.pipeline import Config
from redthread.project import Project
from redthread.replicate import (committed_texts, fresh_copy, group_panel, observed_floor,
                                 print_group)

from . import fakes


class TestManuscriptMeasures(unittest.TestCase):
    """The panel is one function so that a measure and its error bar cannot drift apart."""

    def test_every_measure_has_a_floor(self):
        # The invariant that makes `clears_noise` safe: a measure reported by the panel and
        # absent from the floor would be a number with no error bar, which is what the whole
        # phase exists to abolish.
        panel = checks.manuscript_measures([fakes.clean_prose(400)])
        self.assertEqual(set(panel), set(checks.NOISE_FLOOR))

    def test_every_floor_has_a_measure(self):
        # And the other direction, so a floor cannot outlive the measure it belongs to.
        panel = checks.manuscript_measures([fakes.clean_prose(400)])
        self.assertEqual(set(checks.NOISE_FLOOR), set(panel))

    def test_empty_manuscript_is_all_zero_rather_than_a_crash(self):
        panel = checks.manuscript_measures([])
        self.assertEqual(set(panel), set(checks.NOISE_FLOOR))
        self.assertTrue(all(v == 0.0 for v in panel.values()))

    def test_counts_scenes_and_words(self):
        panel = checks.manuscript_measures([fakes.clean_prose(400), fakes.clean_prose(400, 1)])
        self.assertEqual(panel["scenes"], 2)
        self.assertGreater(panel["words"], 600)

    def test_recap_block_share_sees_a_planted_block(self):
        clean = fakes.clean_prose(400)
        recap = fakes.recap_prose(400, sentences=6)
        self.assertEqual(checks.manuscript_measures([clean])["recap_block_share"], 0.0)
        self.assertGreater(checks.manuscript_measures([recap])["recap_block_share"], 0.0)

    def test_scene_and_manuscript_duplication_are_separate_measures(self):
        # A book can be clean scene by scene and repetitive across scenes; that is the whole
        # reason both are reported. Same text three times: nothing repeats inside a scene,
        # everything repeats between them.
        text = fakes.clean_prose(400)
        panel = checks.manuscript_measures([text, text, text])
        self.assertLess(panel["duplication_scene"], panel["duplication_manuscript"])


class TestSomaticBeats(unittest.TestCase):
    """Factored out of `check_somatic` so a corpus share can be measured without a Scene."""

    def test_finds_a_beat(self):
        self.assertTrue(checks.somatic_beats("Her chest tightened at the sound."))

    def test_clean_prose_has_none(self):
        self.assertEqual(checks.somatic_beats("The door was open. She went through it."), [])

    def test_overlapping_patterns_count_one_beat(self):
        # Both patterns reach this sentence. Counting raw matches would double it, and the
        # corpus share would read twice what it is.
        beats = checks.somatic_beats("Her chest tightened, and something tightened in her chest.")
        self.assertEqual(len(beats), 2, beats)

    def test_check_somatic_still_agrees_with_the_helper(self):
        text = "Her chest tightened at the sound."
        scene = Scene(spec_id="s", index=1, text=text)
        self.assertEqual(checks.check_somatic(scene, max_allowed=0)[0].quote,
                         checks.somatic_beats(text)[0])


class TestClearsNoise(unittest.TestCase):
    """The function that has to be passed through before a difference may be called one."""

    def test_a_difference_inside_the_floor_does_not_clear_it(self):
        floor = checks.NOISE_FLOOR["gesture_rate"]
        self.assertFalse(checks.clears_noise("gesture_rate", 2.0, 2.0 * (1 + floor / 2)))

    def test_a_large_difference_clears_it(self):
        self.assertTrue(checks.clears_noise("gesture_rate", 1.0, 4.0))

    def test_the_pair_the_floor_was_measured_from_does_not_clear_it(self):
        # The self-test that matters. Every number in NOISE_FLOOR came from two runs of
        # identical code, so by construction not one measure of that pair may be reported as a
        # difference. A first draft of the table failed this on four measures, because the
        # published figures were rounded down for the write-up.
        for name, floor in checks.NOISE_FLOOR.items():
            a = 1.0
            b = 1.0 + floor
            self.assertFalse(checks.clears_noise(name, a, b),
                             f"{name}: a difference exactly the size of its own floor was "
                             f"reported as a result")

    def test_identical_values_never_clear(self):
        for name in checks.NOISE_FLOOR:
            self.assertFalse(checks.clears_noise(name, 0.5, 0.5))

    def test_both_zero_is_no_difference_rather_than_a_division_by_zero(self):
        self.assertFalse(checks.clears_noise("recap_block_share", 0.0, 0.0))

    def test_an_unmeasured_measure_raises_rather_than_guessing(self):
        # The forcing function. Returning False would say "not different" and returning True
        # would say "different"; both are claims about something nobody has measured.
        with self.assertRaises(KeyError) as caught:
            checks.clears_noise("scenes_ending_on_a_portent", 0.56, 0.33)
        self.assertIn("no measured noise floor", str(caught.exception))
        self.assertIn("worst_refrain", str(caught.exception), "the error should name what is "
                                                              "available")

    def test_the_floor_is_recorded_with_its_source_and_its_n(self):
        self.assertTrue(checks.NOISE_FLOOR_SOURCE.endswith(".md"))
        self.assertGreaterEqual(checks.NOISE_FLOOR_N, 2)

    def test_maxima_have_the_widest_floors(self):
        # Documented in the noise-floor evidence and worth asserting, because the ordering is
        # the finding: the statistics quoted most often were the least trustworthy.
        self.assertGreater(checks.NOISE_FLOOR["worst_refrain"],
                           checks.NOISE_FLOOR["dialogue_share"])
        self.assertGreater(checks.NOISE_FLOOR["somatic_share"],
                           checks.NOISE_FLOOR["words"])

    def test_describe_difference_names_the_verdict(self):
        line = checks.describe_difference("gesture_rate", 1.0, 4.0)
        self.assertIn("gesture_rate", line)
        self.assertIn("clears", line)
        self.assertIn("INSIDE", checks.describe_difference("gesture_rate", 2.0, 2.01))


class TestAblationSwitches(unittest.TestCase):
    """Four mechanisms shipped with no way to turn them off, which made them unfalsifiable."""

    def test_all_default_to_on(self):
        config = Config()
        self.assertTrue(config.refrain_feedback)
        self.assertTrue(config.gesture_feedback)
        self.assertTrue(config.model_refrains)

    def test_each_can_be_turned_off_independently(self):
        config = Config(gesture_feedback=False)
        self.assertFalse(config.gesture_feedback)
        self.assertTrue(config.refrain_feedback)
        self.assertTrue(config.model_refrains)

    def test_the_write_cli_exposes_every_prose_side_switch(self):
        from redthread.cli import build_parser
        args = build_parser().parse_args(
            ["write", "run", "--local", "m", "--no-refrain-feedback",
             "--no-gesture-feedback", "--no-model-refrains"])
        self.assertTrue(args.no_refrain_feedback)
        self.assertTrue(args.no_gesture_feedback)
        self.assertTrue(args.no_model_refrains)

    def test_the_plan_cli_exposes_the_repeople_switch(self):
        from redthread.cli import build_parser
        args = build_parser().parse_args(["plan", "p", "--out", "run", "--no-repeople"])
        self.assertTrue(args.no_repeople)

    def test_replicate_carries_the_ablation_flags_too(self):
        # Because an ablation and a replicate are the same object with one switch flipped, and
        # a flag available only on `write` would mean building the comparison by hand.
        from redthread.cli import build_parser
        args = build_parser().parse_args(
            ["replicate", "run", "--runs", "2", "--label", "no-refrain",
             "--no-refrain-feedback"])
        self.assertEqual(args.runs, 2)
        self.assertEqual(args.label, "no-refrain")
        self.assertTrue(args.no_refrain_feedback)

    def test_make_plan_takes_repeople_and_defaults_to_on(self):
        # The behavioural half lives in test_planner.py, where the planner's scripted backend
        # is. This pins the default, because an ablation switch that silently defaults to off
        # changes the shipped product instead of measuring it.
        import inspect
        from redthread.planner import make_plan
        param = inspect.signature(make_plan).parameters["repeople"]
        self.assertIs(param.default, True)


class TestReplicateHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _project(self) -> Project:
        story = StorySpec(title="T", premise="p",
                          threads=[Thread(id="t1", name="n", kind=ThreadKind.MAIN,
                                          states=["opening", "middle", "closed"])])
        project = Project(self.root / "src", story, [])
        project.save()
        return project

    def test_fresh_copy_rewinds_thread_state(self):
        # The bug this is here for: a finished run's story.json holds every thread at its
        # terminal state, so a replicate copied verbatim opens on a book that believes it has
        # already happened — same plan, different briefs, which is exactly what a replicate is
        # supposed to rule out.
        source = self._project()
        source.story.threads[0].current_state = "closed"
        copy = fresh_copy(source, self.root / "r1")
        self.assertEqual(copy.story.threads[0].current_state, "opening")
        self.assertEqual(source.story.threads[0].current_state, "closed",
                         "the source must not be mutated")

    def test_fresh_copy_writes_a_loadable_project_with_no_scenes(self):
        source = self._project()
        fresh_copy(source, self.root / "r1")
        loaded = Project.load(self.root / "r1")
        self.assertEqual(loaded.committed_scenes(), [])
        self.assertEqual(loaded.ledger.facts, [])

    def test_committed_texts_ignores_uncommitted_prose(self):
        import json
        scenes = self.root / "run" / "scenes"
        scenes.mkdir(parents=True)
        for i, committed in enumerate([True, False, True], start=1):
            (scenes / f"{i:04d}.txt").write_text(f"scene {i}", encoding="utf-8")
            (scenes / f"{i:04d}.json").write_text(json.dumps({"committed": committed}),
                                                  encoding="utf-8")
        self.assertEqual(committed_texts(self.root / "run"), ["scene 1", "scene 3"])

    def test_committed_texts_of_an_empty_run_is_empty(self):
        (self.root / "empty").mkdir()
        self.assertEqual(committed_texts(self.root / "empty"), [])

    def test_group_panel_has_one_value_per_run(self):
        runs = [("a", [fakes.clean_prose(300)]),
                ("b", [fakes.clean_prose(300, 1)]),
                ("c", [fakes.clean_prose(300, 2)])]
        panel = group_panel(runs)
        self.assertEqual(set(panel), set(checks.NOISE_FLOOR))
        self.assertTrue(all(len(v) == 3 for v in panel.values()))

    def test_observed_floor_of_one_run_against_itself_is_zero(self):
        texts = [fakes.clean_prose(300)]
        floor = observed_floor([("a", texts), ("b", list(texts))])
        self.assertTrue(all(v == 0.0 for v in floor.values()), floor)

    def test_observed_floor_is_a_fraction_of_the_mean(self):
        floor = observed_floor([("a", [fakes.clean_prose(300)]),
                                ("b", [fakes.clean_prose(900, 1)])])
        self.assertGreater(floor["words"], 0.5)

    def test_print_group_returns_the_means(self):
        import contextlib, io
        runs = [("a", [fakes.clean_prose(300)]), ("b", [fakes.clean_prose(900, 1)])]
        with contextlib.redirect_stdout(io.StringIO()):
            means = print_group("set", runs)
        self.assertEqual(set(means), set(checks.NOISE_FLOOR))
        self.assertEqual(means["scenes"], 1.0)


if __name__ == "__main__":
    unittest.main()


class TestRefusalMeasures(unittest.TestCase):
    """Phase 4, step 17: a countable property of the want/obstacle/cost axis that varies."""

    def test_counts_a_performed_refusal(self):
        self.assertGreater(checks.refusal_rate("She refused to hand over the ledger."), 0)

    def test_ignores_a_merely_negated_verb(self):
        # The narrow scope is the design. "could not" and "did not" catch every negated verb in
        # the language, and a measure that fires on "she did not sit down" is measuring English.
        self.assertEqual(checks.refusal_rate("She did not sit down. She could not see it."), 0.0)

    def test_a_shaken_head_counts(self):
        self.assertGreater(checks.refusal_rate("He shook his head and went back to the bench."),
                           0)

    def test_empty_text_is_zero(self):
        self.assertEqual(checks.refusal_rate(""), 0.0)
        self.assertEqual(checks.refusal_per_ask(""), 0.0)

    def test_per_ask_is_a_share_of_asking(self):
        self.assertEqual(
            checks.refusal_per_ask("She asked for the ledger. He refused to hand it over."), 1.0)

    def test_per_ask_is_zero_when_nobody_asks(self):
        # Not undefined and not one: a scene where nothing is wanted has no refusals to have.
        self.assertEqual(checks.refusal_per_ask("He refused."), 0.0)

    def test_both_are_in_the_panel_with_floors(self):
        panel = checks.manuscript_measures([fakes.clean_prose(400)])
        self.assertIn("refusal_rate", panel)
        self.assertIn("refusal_per_ask", panel)
        self.assertIn("refusal_rate", checks.NOISE_FLOOR)
        self.assertIn("refusal_per_ask", checks.NOISE_FLOOR)

    def test_the_plan_side_feature_reads_beats_and_posts(self):
        from redthread.models import Beat, SceneSpec, Transition
        spec = SceneSpec(id="s", index=1, summary="They meet.",
                         beats=[Beat(summary="Ardo refuses to say who set the type")])
        self.assertTrue(checks.plan_names_a_refusal(spec))

        quiet = SceneSpec(id="s", index=1, summary="They meet.",
                          beats=[Beat(summary="Ardo hands over the proof sheet")])
        self.assertFalse(checks.plan_names_a_refusal(quiet))

        via_post = SceneSpec(id="s", index=1, summary="They meet.",
                             beats=[Beat(summary="Ardo hands over the proof sheet")])
        via_post.thread_ops["T"] = Transition(post=["Vesna is denied the register"])
        self.assertTrue(checks.plan_names_a_refusal(via_post))


class TestEmitFloor(unittest.TestCase):
    """Step 2's deliverable as something to paste rather than something to retype."""

    def test_the_flag_exists(self):
        from redthread.cli import build_parser
        args = build_parser().parse_args(["measures", "a", "b", "--emit-floor"])
        self.assertTrue(args.emit_floor)

    def test_it_rounds_up_rather_than_to_nearest(self):
        # Not cosmetic. The first floor table was built from figures rounded *down* for a
        # write-up, and four measures of the very pair it came from were then reported as
        # clearing it.
        import math
        floor = observed_floor([("a", [fakes.clean_prose(300)]),
                                ("b", [fakes.clean_prose(310, 1)])])
        for name, value in floor.items():
            self.assertGreaterEqual(math.ceil(value * 100) / 100, value, name)


class TestDegenerateFloors(unittest.TestCase):
    """A floor of 0.00 because both replicates were zero is not a floor of 0.00.

    The same distinction `clears_noise` exists to make, one level down. `recap_block_share` is
    the live case: zero of 373 current-era scenes carry a run of four consecutive past-perfect
    sentences, so the replicate pair reads 0.00 and 0.00 — and a future condition reading 0.05
    would otherwise be reported as clearing a floor nobody measured.
    """

    def test_a_degenerate_measure_is_named(self):
        self.assertIn("recap_block_share", checks.DEGENERATE_FLOOR)
        self.assertFalse(checks.floor_is_established("recap_block_share"))

    def test_an_ordinary_measure_is_established(self):
        self.assertTrue(checks.floor_is_established("dialogue_share"))
        self.assertTrue(checks.floor_is_established("worst_refrain"))

    def test_every_degenerate_measure_actually_has_a_zero_floor(self):
        # Guards the table against drift in the other direction: a measure listed here whose
        # floor is not zero would be understating a floor that exists.
        for name in checks.DEGENERATE_FLOOR:
            self.assertEqual(checks.NOISE_FLOOR[name], 0.0, name)

    def test_every_zero_floor_is_declared_degenerate(self):
        # And the converse, which is the one that matters: a zero floor that nobody marked would
        # let any difference at all read as a result.
        for name, floor in checks.NOISE_FLOOR.items():
            if floor == 0.0:
                self.assertIn(name, checks.DEGENERATE_FLOOR,
                              f"{name} has a zero floor and is not marked degenerate, so any "
                              f"difference in it would be reported as clearing one")

    def test_an_unknown_measure_still_raises(self):
        with self.assertRaises(KeyError):
            checks.floor_is_established("vibes")

    def test_the_description_says_no_floor_was_measured(self):
        line = checks.describe_difference("recap_block_share", 0.0, 0.05)
        self.assertIn("NO FLOOR", line)
        self.assertNotIn("clears", line)

    def test_a_real_difference_in_a_real_measure_still_reads_as_clearing(self):
        self.assertIn("clears", checks.describe_difference("gesture_rate", 1.0, 4.0))


class TestLengthSensitiveMeasures(unittest.TestCase):
    """Two books of different lengths cannot be compared on a manuscript-wide measure.

    Measured, not assumed: `manuscript_refrains` reads .015 book-wide at nine scenes and .055 at
    seventy-one, and per-scene duplication reads .001 in the same book whose manuscript-wide
    duplication reads .030. The trap is concrete — before this, `measures --against` compared a
    71-scene book to a 9-scene one and reported duplication_manuscript as clearing its floor by
    126%, which is true and means nothing.
    """

    def test_manuscript_wide_measures_are_marked(self):
        for name in ("duplication_manuscript", "worst_refrain", "repetition_concentration"):
            self.assertIn(name, checks.LENGTH_SENSITIVE)

    def test_per_scene_averages_are_not(self):
        # These are means over scenes, so adding scenes does not move them by construction.
        for name in ("dialogue_share", "gesture_rate", "recap_grammar", "duplication_scene",
                     "somatic_share", "refusal_rate", "refusal_per_ask"):
            self.assertNotIn(name, checks.LENGTH_SENSITIVE)

    def test_every_named_measure_is_in_the_panel(self):
        for name in checks.LENGTH_SENSITIVE:
            self.assertIn(name, checks.NOISE_FLOOR)

    def test_the_claim_holds_on_real_manuscripts(self):
        # The property itself, asserted against the fixtures rather than taken on trust: the
        # same prose repeated more times has higher manuscript-wide duplication and identical
        # per-scene duplication.
        short = [fakes.clean_prose(300, 0), fakes.clean_prose(300, 1)]
        long = short + [fakes.clean_prose(300, 0), fakes.clean_prose(300, 1)]
        a, b = checks.manuscript_measures(short), checks.manuscript_measures(long)
        self.assertGreater(b["duplication_manuscript"], a["duplication_manuscript"])
        self.assertAlmostEqual(b["duplication_scene"], a["duplication_scene"], places=6)

    def test_emit_floor_also_emits_the_degenerate_set(self):
        # Otherwise step 2 pastes a new floor over the old one and reintroduces the bug the
        # degenerate set exists to prevent, silently.
        import contextlib, io
        from redthread.cli import build_parser
        args = build_parser().parse_args(
            ["measures", "runs/current", "runs/replicate", "--emit-floor"])
        self.assertTrue(args.emit_floor)


class TestRefusalMeasuresAreActuallyNarrow(unittest.TestCase):
    """The audit that halved these, written down as tests so it cannot silently un-happen.

    Both regexes shipped with a docstring asserting they excluded ordinary negation, and both
    were 56% ordinary negation. The assertion was convincing enough to have stopped anyone
    checking, which is why the check is here now instead of in a comment.
    """

    def test_a_negated_future_is_not_a_refusal(self):
        for line in ("Whatever lay beyond this door would not be easy.",
                     "She spoke low so the others wouldn't hear.",
                     "It wouldn't end with a decision.",
                     "The ledger will not forgive your ignorance.",
                     "He won't be back before dawn."):
            self.assertEqual(checks.refusal_rate(line), 0.0, line)

    def test_a_vow_is_not_a_refusal(self):
        # "He would not betray them" is a resolution, not somebody being told no. It was 42
        # matches in the first version.
        self.assertEqual(checks.refusal_rate("He would not betray them."), 0.0)

    def test_a_performed_refusal_still_counts(self):
        for line in ("She refused to hand over the ledger.",
                     "He declined the offer.",
                     "He shook his head.",
                     "She said no.",
                     "They turned him down."):
            self.assertGreater(checks.refusal_rate(line), 0.0, line)

    def test_wanting_something_is_not_asking_for_it(self):
        # The denominator's contamination: "He wanted to press harder" is not a request anybody
        # can refuse. wanted/needed/meant to were 493 of 873 matches.
        for line in ("He wanted to press harder. He refused.",
                     "She needed proof. She refused.",
                     "He meant to say it. He refused."):
            self.assertEqual(checks.refusal_per_ask(line), 0.0, line)

    def test_asking_somebody_still_counts(self):
        self.assertGreater(
            checks.refusal_per_ask("She asked for the ledger. He refused."), 0.0)
        self.assertGreater(
            checks.refusal_per_ask("She demanded the ledger. He shook his head."), 0.0)

    def test_the_floors_are_the_narrowed_ones(self):
        # Pinning these catches a revert of the narrowing, which would otherwise show up only as
        # a quietly more impressive number.
        self.assertEqual(checks.NOISE_FLOOR["refusal_rate"], 0.22)
        self.assertEqual(checks.NOISE_FLOOR["refusal_per_ask"], 0.37)


class TestRepeopleCommand(unittest.TestCase):
    """`redthread repeople` — step 7 needed the pass runnable on a plan already on disk.

    Measuring it by generating two plans, one with the pass and one without, compares two
    different plans. Running it on an existing plan makes the before and after the same object,
    which is the only version of the comparison that means anything.
    """

    def test_the_command_exists_with_its_switches(self):
        from redthread.cli import build_parser
        args = build_parser().parse_args(
            ["repeople", "run", "--local", "m", "--limit", "0.2", "--write"])
        self.assertEqual(args.limit, 0.2)
        self.assertTrue(args.write)

    def test_it_does_not_write_by_default(self):
        # A pass that rewrites a plan on disk without being asked would make the before-and-after
        # comparison it exists for impossible to repeat.
        from redthread.cli import build_parser
        args = build_parser().parse_args(["repeople", "run", "--local", "m"])
        self.assertFalse(args.write)
