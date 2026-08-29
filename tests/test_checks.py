"""Deterministic checks must catch injected defects, not merely pass clean prose.

A check that never fires is indistinguishable from a check that does not work, so every test
here injects the specific defect the check exists to find and asserts it comes back.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from redthread import checks
from redthread.models import (Beat, Character, Scene, SceneSpec, Severity, StorySpec,
                              StyleContract, Transition)

from . import fakes


def make_story(**kwargs) -> StorySpec:
    defaults = dict(
        title="Test",
        premise="A premise.",
        characters=[Character("siv", "Siv Alderman"), Character("otto", "Otto Renner")],
        style=StyleContract(forbidden_phrases=["everything changed"]),
    )
    defaults.update(kwargs)
    return StorySpec(**defaults)


def make_spec(**kwargs) -> SceneSpec:
    defaults = dict(id="s01", index=1, word_target=100, pov="siv",
                    characters=["siv"], beats=[Beat("a beat")])
    defaults.update(kwargs)
    return SceneSpec(**defaults)


def scene(text: str, index: int = 1) -> Scene:
    return Scene(spec_id="s01", index=index, text=text)


def kinds(violations) -> set[str]:
    return {v.kind for v in violations}


class TestFormat(unittest.TestCase):
    def test_markdown_heading_is_a_blocker(self):
        found = checks.check_format(scene("## Chapter One\n\nShe walked in."))
        self.assertIn("format", kinds(found))
        self.assertEqual(found[0].severity, Severity.BLOCKER)

    def test_assistant_preamble_caught(self):
        found = checks.check_format(scene("Here is the scene you asked for. She walked in."))
        self.assertIn("format", kinds(found))

    def test_meta_narration_caught(self):
        found = checks.check_format(scene("In this scene, Siv finds the branch."))
        self.assertIn("format", kinds(found))

    def test_clean_prose_passes(self):
        self.assertEqual(checks.check_format(scene("She turned the coupling. It held.")), [])


class TestLength(unittest.TestCase):
    def test_short_scene_is_major(self):
        found = checks.check_length(scene("word " * 50), make_spec(word_target=1000))
        self.assertEqual(found[0].severity, Severity.MAJOR)

    def test_modest_overrun_is_only_minor(self):
        found = checks.check_length(scene("word " * 1300), make_spec(word_target=1000))
        self.assertEqual(found[0].severity, Severity.MINOR)
        self.assertEqual(found[0].kind, "length")

    def test_runaway_overrun_is_major(self):
        """A real run produced 5878 words against a 900 target and, because overrun was MINOR,
        that draft won candidate selection over a correctly-sized one."""
        found = checks.check_length(scene("word " * 5878), make_spec(word_target=900))
        self.assertEqual(found[0].kind, "length_runaway")
        self.assertEqual(found[0].severity, Severity.MAJOR)

    def test_a_runaway_draft_cannot_outscore_a_correct_one(self):
        spec = make_spec(word_target=900)
        story = make_story()
        runaway = checks.run_all(scene("word " * 5878), spec, story)
        correct = checks.run_all(scene(" ".join(["word"] * 900)), spec, story)
        majors = lambda vs: sum(1 for v in vs if v.severity is Severity.MAJOR)
        self.assertGreater(majors(runaway), majors(correct))

    def test_within_tolerance_passes(self):
        self.assertEqual(checks.check_length(scene("word " * 1000),
                                             make_spec(word_target=1000)), [])


class TestSomatic(unittest.TestCase):
    """StoryScope: emotion via bodily metaphor in 81% of AI stories vs 38% of human ones."""

    def test_each_excess_somatic_beat_is_its_own_violation(self):
        """One violation per excess instance, each with its own quote. As a single violation
        quoting only the first beat, surgical repair fixed one sentence per round while the
        check re-fired on the rest — a real scene with three beats burned its whole repair
        budget that way."""
        text = (
            "Her chest tightened as she read the line number. "
            "His stomach dropped when the log came up empty. "
            "Something twisted in her throat. "
            "She let out a breath she didn't know she was holding."
        )
        found = checks.check_somatic(scene(text))
        self.assertEqual(len(found), 3, "four beats minus the one-beat allowance")
        self.assertTrue(all(v.severity is Severity.MAJOR for v in found))
        quotes = [v.quote for v in found]
        self.assertEqual(len(set(quotes)), 3, "each violation must locate its own beat")
        for q in quotes:
            self.assertIn(q.split()[-1], text)

    def test_an_object_held_is_not_an_emotion_beat(self):
        """The noun-in-a-body-part pattern matched any noun, so "the pages in her hands" read as
        emotion via bodily metaphor. Scene 5 of a live run spent five repair rounds on it — the
        surgical rewrite kept the pages, because the pages were the point of the sentence."""
        for text in ("She squared the pages in her hands and set them down.",
                     "He turned the pen in his fingers and wrote nothing.",
                     "The bucket of couplings in her hands was heavier than it looked."):
            with self.subTest(text=text):
                self.assertEqual(checks.check_somatic(scene(text), max_allowed=0), [])

    def test_a_sensation_in_a_body_part_still_fires(self):
        for text in ("There was a knot in her stomach that would not go.",
                     "She felt a tightness in his chest and looked away.",
                     "The weight in her chest did not shift."):
            with self.subTest(text=text):
                self.assertTrue(checks.check_somatic(scene(text), max_allowed=0))

    def test_one_somatic_beat_allowed(self):
        self.assertEqual(
            checks.check_somatic(scene("Her chest tightened. She wrote the number down.")), [])

    def test_behavioural_emotion_passes(self):
        text = ("She wrote the number down twice, then crossed out the first one because the "
                "handwriting was bad. Otto did not ask what she was writing.")
        self.assertEqual(checks.check_somatic(scene(text)), [])


class TestThematicGloss(unittest.TestCase):
    """StoryScope: narrator explicitly explains the theme in 77% of AI stories vs 52% human."""

    def test_realisation_construction_flagged(self):
        text = "She realised then that the founders had known all along."
        found = checks.check_thematic_gloss(scene(text))
        self.assertIn("thematic_gloss", kinds(found))

    def test_that_was_what_it_meant_flagged(self):
        found = checks.check_thematic_gloss(
            scene("That was what it meant to keep a town alive."))
        self.assertIn("thematic_gloss", kinds(found))

    def test_in_that_moment_flagged(self):
        found = checks.check_thematic_gloss(
            scene("In that moment, she understood the cost."))
        self.assertIn("thematic_gloss", kinds(found))

    def test_dramatised_passes(self):
        text = ("The figure was written in the margin in pencil. Four hundred. She checked it "
                "against the census sheet and the census sheet said four thousand and six.")
        self.assertEqual(checks.check_thematic_gloss(scene(text)), [])


class TestSeam(unittest.TestCase):
    """Cohesion, in STORYTELLER's sense: does the scene join the previous one?"""

    def test_echoed_opening_flagged(self):
        tail = ("she wrote the line number in the notebook and closed it and went out "
                "into the yard where the trucks were")
        text = ("She wrote the line number in the notebook and closed it. The yard was empty.")
        found = checks.check_seam(scene(text), tail)
        self.assertIn("seam_echo", kinds(found))
        self.assertEqual([v for v in found if v.kind == "seam_echo"][0].severity,
                         Severity.MAJOR)

    def test_weather_opening_flagged_when_continuing(self):
        found = checks.check_seam(scene("The rain had stopped by then."), "some previous text")
        self.assertIn("seam_reset", kinds(found))

    def test_waking_opening_flagged(self):
        found = checks.check_seam(scene("Siv woke to the sound of the intake pump."),
                                  "some previous text")
        self.assertIn("seam_reset", kinds(found))

    def test_no_previous_text_means_no_seam_complaint(self):
        found = checks.check_seam(scene("The rain had stopped."), "")
        self.assertEqual(found, [])

    def test_continuing_opening_passes(self):
        tail = "she wrote the line number in the notebook and closed it"
        found = checks.check_seam(scene("Otto was still under the intake housing."), tail)
        self.assertEqual(found, [])

    def test_empty_scene_is_a_blocker(self):
        found = checks.check_seam(scene("   "), "tail")
        self.assertEqual(found[0].severity, Severity.BLOCKER)


class TestRepetition(unittest.TestCase):
    def test_ngram_reused_from_earlier_scene_flagged(self):
        earlier = ["The light came off the water in flat sheets that morning."]
        found = checks.check_repetition(
            scene("Again the light came off the water in flat sheets."), earlier)
        self.assertIn("repetition", kinds(found))

    def test_novel_prose_passes(self):
        earlier = ["The light came off the water in flat sheets."]
        found = checks.check_repetition(scene("Otto turned the coupling a quarter turn."),
                                        earlier)
        self.assertEqual(found, [])

    def test_internal_repetition_flagged(self):
        text = ("a quarter turn and back " * 3) + "then he stopped."
        found = checks.check_internal_repetition(scene(text))
        self.assertIn("internal_repetition", kinds(found))


class TestRhythm(unittest.TestCase):
    def test_metronomic_sentences_flagged(self):
        text = " ".join(["She walked to the pump house door."] * 10)
        found = checks.check_rhythm(scene(text))
        self.assertIn("rhythm", kinds(found))

    def test_varied_sentences_pass(self):
        text = ("She stopped. The intake housing had been opened and closed so many times over "
                "twenty-two years that the bolt heads were rounded off and Otto kept a spare "
                "set in a coffee tin under the bench, which he had never once mentioned to "
                "anyone. Nobody asked. It held.")
        self.assertEqual(checks.check_rhythm(scene(text)), [])


class TestSlopAndForbidden(unittest.TestCase):
    def test_slop_phrase_flagged(self):
        found = checks.check_slop(scene("The valley was a tapestry of light."), make_story())
        self.assertIn("slop", kinds(found))

    def test_character_name_exempt_from_slop_list(self):
        """`elara` is on the antislop list. A story whose character is named Elara must not
        trip the check on every scene."""
        story = make_story(characters=[Character("elara", "Elara Voss")])
        self.assertEqual(checks.check_slop(scene("Elara opened the hatch."), story), [])

    def test_single_word_entries_match_on_word_boundaries(self):
        """Regression: 'aria' matched inside 'variance' on a real gemma3:12b draft.

        The list is full of short single-word entries — shall, realm, canvas, depths — each of
        which fires inside longer words under plain substring matching.
        """
        story = make_story()
        self.assertEqual(
            checks.check_slop(scene("The variance was within tolerance."), story,
                              slop=["aria"]), [])
        self.assertIn(
            "slop",
            kinds(checks.check_slop(scene("Aria closed the hatch."), story, slop=["aria"])))

    def test_multiword_phrases_still_match_as_substrings(self):
        found = checks.check_slop(scene("It was a testament to her patience."), make_story(),
                                  slop=["testament to"])
        self.assertIn("slop", kinds(found))

    def test_style_contract_forbidden_phrase_is_major(self):
        found = checks.check_forbidden(scene("And everything changed after that."), make_story())
        self.assertEqual(found[0].severity, Severity.MAJOR)

    def test_slop_sample_prefers_multiword_phrases(self):
        sample = checks.slop_sample(10)
        self.assertTrue(sample, "slop list should be populated from data/")
        self.assertTrue(all(" " in phrase for phrase in sample),
                        f"single-word entries leaked into the brief sample: {sample}")


class TestPointOfView(unittest.TestCase):
    """Found by running a real local model: gemma3:12b wrote an entire scene in the first person
    against a third-limited contract, and every other check passed it."""

    def test_wholesale_first_person_is_a_blocker(self):
        text = ("I closed the notebook and stood up. I trusted it more than the Provision's "
                "memory. My hands were filthy. I would flag the readings again in the morning, "
                "and right now I was going home. I did not look back at my bench.")
        found = checks.check_pov(scene(text), make_story())
        self.assertIn("pov_person", kinds(found))
        self.assertEqual(found[0].severity, Severity.BLOCKER)

    def test_third_person_narration_passes(self):
        text = ("She closed the notebook and stood up. Otto did not look up from the housing. "
                "Her hands were filthy and she wiped them on the cloth by the bench.")
        self.assertEqual(checks.check_pov(scene(text), make_story()), [])

    def test_first_person_inside_dialogue_is_fine(self):
        """Characters say 'I'. Counting dialogue would fire on every scene with a conversation."""
        text = ('"I told you the log was wrong," Otto said. "I checked it myself, twice." '
                'She said nothing. He wiped his hands and put the cloth back on the nail. '
                '"My guess is the valve," he added. "But I have been wrong before."')
        self.assertEqual(checks.check_pov(scene(text), make_story()), [])

    def test_a_couple_of_slips_are_major_not_blocking(self):
        """Free indirect discourse legitimately admits the occasional first-person thought."""
        text = (" ".join(["She walked the fence line and counted the splices."] * 30)
                + " I should have fixed this, she thought. I never did. My fault, then. Mine.")
        found = checks.check_pov(scene(text), make_story())
        self.assertIn("pov_person", kinds(found))
        self.assertEqual(found[0].severity, Severity.MAJOR)

    def test_second_person_address_flagged(self):
        text = " ".join(["You walk into the pump house and you see the terminal."] * 4)
        found = checks.check_pov(scene(text), make_story())
        self.assertIn("pov_person", kinds(found))

    def test_first_person_contract_wants_first_person(self):
        story = make_story(style=StyleContract(pov="first person"))
        found = checks.check_pov(
            scene("She closed the notebook and stood up. Otto said nothing at all."), story)
        self.assertIn("pov_person", kinds(found))

    def test_strip_dialogue_removes_typographic_quotes(self):
        self.assertNotIn("I told you", checks.strip_dialogue('“I told you,” he said.'))


class TestBriefLeakage(unittest.TestCase):
    """Found by running a real local model: qwen3:8b opened scene one with the style contract's
    own sample sentence, and reused a second sample later in the same draft."""

    def test_style_sample_reproduced_is_major(self):
        story = make_story(style=StyleContract(samples=[
            "The pump had been running eleven minutes longer than the log said it had."]))
        found = checks.check_style_leak(
            scene("The pump had been running eleven minutes longer than the log said it had. "
                  "Siv leaned against the bulkhead."), story)
        self.assertIn("style_leak", kinds(found))
        self.assertEqual(found[0].severity, Severity.MAJOR)

    def test_prose_in_the_same_register_passes(self):
        story = make_story(style=StyleContract(samples=[
            "The pump had been running eleven minutes longer than the log said it had."]))
        found = checks.check_style_leak(
            scene("The intake had been drawing two degrees warmer than the sheet claimed."),
            story)
        self.assertEqual(found, [])

    def test_every_copied_run_gets_its_own_violation(self):
        """The third check to need this, after `check_somatic` and `check_brief_leak`. Scene 6 of
        a live run spent four rounds rewriting one sentence of a seven-run leak."""
        sample = ("The gate had dropped on its hinge in the spring and neither of them had "
                  "fixed it since.")
        story = make_story(style=StyleContract(samples=[sample]))
        found = checks.check_style_leak(scene("She waited. " + sample + " She went in."), story)
        self.assertGreater(len(found), 1)
        self.assertEqual(len({v.quote for v in found}), len(found))

    def test_no_samples_means_no_check(self):
        self.assertEqual(checks.check_style_leak(scene("Anything at all."), make_story()), [])

    def test_beat_summary_reproduced_is_major(self):
        spec = make_spec(beats=[Beat("She finds an unreachable branch in the founders' code "
                                     "and writes the line number down")])
        found = checks.check_brief_leak(
            scene("She finds an unreachable branch in the founders' code and writes the line "
                  "number down, then goes home."), spec)
        self.assertIn("brief_leak", kinds(found))

    def test_every_copied_run_gets_its_own_violation(self):
        """`_surgical` rewrites the sentence a quote falls in. One violation carrying one of
        seven copied runs gets one sentence rewritten and the check fires again on the other
        six — which is how scene 26 of a live run spent every repair round it had."""
        spec = make_spec(beats=[Beat("She finds an unreachable branch in the founders' code "
                                     "and writes the line number down before going home")])
        found = checks.check_brief_leak(
            scene("She finds an unreachable branch in the founders' code and writes the line "
                  "number down before going home."), spec)
        self.assertGreater(len(found), 1)
        self.assertEqual(len({v.quote for v in found}), len(found),
                         "each violation must point at a different run")

    def test_one_grammar_heavy_run_is_not_a_leak(self):
        """From a live run: scene 4 was held back, unrepairably, for a single shared run —
        "his back to the council the", four of whose six tokens are function words. The scene
        was doing exactly what the beat told it to do."""
        spec = make_spec(beats=[Beat("Dain turns his back to the council and walks out")])
        found = checks.check_brief_leak(
            scene("He turned his back to the council the way a man leaves a room he has already "
                  "decided about, and the door took its time closing behind him."), spec)
        self.assertEqual(found, [])

    def test_dramatised_beat_passes(self):
        spec = make_spec(beats=[Beat("She finds an unreachable branch in the founders' code "
                                     "and writes the line number down")])
        found = checks.check_brief_leak(
            scene("Line 4471 could not be reached. She copied the number into the notebook, "
                  "closed it, and went out to the truck."), spec)
        self.assertEqual(found, [])


class TestSentenceSpans(unittest.TestCase):
    """The splice primitive. Every localised repair addresses text by these offsets."""

    def test_spans_cover_the_text_in_order(self):
        text = "She read it. He did not. The stove ticked."
        spans = checks.sentence_spans(text)
        self.assertEqual([text[a:b].strip() for a, b in spans],
                         ["She read it.", "He did not.", "The stove ticked."])

    def test_trailing_text_without_a_terminator_is_a_final_span(self):
        text = "She read it. And then"
        spans = checks.sentence_spans(text)
        self.assertEqual(text[spans[-1][0]:spans[-1][1]].strip(), "And then")

    def test_unpunctuated_text_is_linear_not_quadratic(self):
        """The original pattern matched whole sentences with `[^.!?…]*[.!?…]+`, which on text
        with no terminator consumes to the end at every start position and backtracks the whole
        way: 3.7 seconds for four thousand words. A truncated draft is exactly that shape, and
        `check_truncated` and `_surgical` both land here."""
        import time
        text = "word " * 8000
        start = time.perf_counter()
        spans = checks.sentence_spans(text)
        elapsed = time.perf_counter() - start
        self.assertEqual(len(spans), 1)
        self.assertLess(elapsed, 0.5, f"took {elapsed:.2f}s — the quadratic path is back")


class TestDuplicationRatio(unittest.TestCase):
    """Repeated phrasing is the clearest quality signal this project can count, and it was not
    being counted.

    Measured over 84 committed scenes plus the three single-scene model comparisons in
    `docs/evidence`: the phi4 and gemma drafts duplicate 0.0–0.2% of their 4-grams, the median
    scene an 8B commits duplicates 29%, and a quarter of scenes are more than half repeated
    material. Nothing else in `checks.py` separates prose like that.

    It stays advisory, and `check_internal_repetition`'s docstring says why: 29% duplication is
    the model's whole register, not six bad sentences, so no sentence-local repair reaches it and
    gating would halt books over something nothing can mend. Candidate selection uses it instead,
    where it is free and cannot deadlock.
    """

    LOOPING = ("She checked the gauge and wrote the number in the book. " * 30) + "Then it ended."
    FRESH = ("She checked the gauge. He signed the sheet without reading it. The kettle clicked "
             "off in the far room. A truck went past on the access road. Nobody said anything.")

    def test_looping_prose_scores_near_one(self):
        self.assertGreater(checks.duplication_ratio(self.LOOPING), 0.9)

    def test_fresh_prose_scores_near_zero(self):
        self.assertLess(checks.duplication_ratio(self.FRESH), 0.05)

    def test_it_counts_occurrences_not_distinct_phrases(self):
        """The first version counted distinct repeated phrases, which scored a page saying one
        sentence thirty times as *cleaner* than varied prose — backwards, and caught by its own
        test."""
        many_phrases_twice = " ".join(
            f"The {noun} had been left where it was. The {noun} had been left where it was."
            for noun in ("ledger", "gauge", "kettle", "docket", "hasp"))
        self.assertGreater(checks.duplication_ratio(self.LOOPING),
                           checks.duplication_ratio(many_phrases_twice))

    # Many different phrases, each repeated twice: a register, with no single phrase reaching the
    # tic threshold.
    DIFFUSE = " ".join(
        f"{a} the {noun} and said nothing. {a} the {noun} and said nothing."
        for a, noun in (("She lifted", "ledger"), ("He turned", "gauge"),
                        ("They emptied", "kettle"), ("Somebody stamped", "docket"),
                        ("She unscrewed", "hasp"), ("He amended", "roster"),
                        ("They recounted", "tally")))

    # One phrase, many sentences: a tic, and each carrier is a different sentence a repair can
    # reach. This is the shape real prose takes — a live scene said "the way she always" five
    # times in five different sentences.
    TIC = " ".join(
        f"She noticed the way he always {verb} before the shift ended."
        for verb in ("checked the log", "wiped the bench", "counted the tickets",
                     "closed the hatch", "signed the sheet", "moved the crate",
                     "read the gauge"))

    def test_diffuse_duplication_stays_advisory(self):
        """No single sentence carries it, so nothing local can repair it."""
        found = checks.check_internal_repetition(scene(self.DIFFUSE))
        self.assertTrue(found)
        self.assertIn("repeated material", found[0].detail)
        self.assertTrue(all(v.severity is Severity.MINOR for v in found))

    def test_a_concentrated_tic_is_repairable(self):
        """One phrase across seven sentences is seven places a repair can go."""
        found = checks.check_internal_repetition(scene(self.TIC))
        self.assertTrue(found)
        self.assertTrue(all(v.severity is Severity.MAJOR for v in found))
        self.assertGreater(len(found), 1)
        self.assertEqual(len({v.quote for v in found}), len(found))
        for v in found:
            self.assertIsNotNone(checks.locate_quote(self.TIC, v.quote))

    def test_it_leaves_the_allowance_alone(self):
        """It reduces to the allowance, not to one: demanding a model never repeat a four-word
        run would churn every scene without reaching it."""
        found = checks.check_internal_repetition(scene(self.TIC))
        self.assertEqual(len(found), 7 - 5 + 1)


class TestSummaryDistance(unittest.TestCase):
    """Past perfect is the grammar of recap, and it is countable.

    StoryScope's "narrated at summary distance" tell fired on all eight scenes of a live book,
    and only the LLM probe could see it — which by this project's calibration policy makes it
    advisory and therefore invisible. The grammar behind it is not: the reference drafts in
    `docs/evidence` narrate 7–13% of their sentences in past perfect, while the scenes this
    project has committed run to a median of 27% and a maximum of 60%.
    """

    HAPPENING = ("She set the gauge on the bench. Tomas came in without knocking and put the "
                 "kettle on. Neither of them mentioned the letter. Outside, a van reversed up "
                 "to the doors and stopped.")
    RECAPPING = ("She had set the gauge on the bench earlier. Tomas had come in without "
                 "knocking and had put the kettle on. Neither of them had mentioned the "
                 "letter. A van had reversed up to the doors and had stopped.")

    def test_a_scene_that_happens_scores_low(self):
        self.assertLess(checks.summary_distance(self.HAPPENING), 0.1)
        self.assertEqual(checks.check_summary_distance(scene(self.HAPPENING)), [])

    def test_a_scene_that_recaps_is_reported(self):
        self.assertGreater(checks.summary_distance(self.RECAPPING), 0.9)
        found = checks.check_summary_distance(scene(self.RECAPPING))
        self.assertIn("summary_distance", kinds(found))

    def test_it_stays_advisory(self):
        """Past perfect is how the whole passage is narrated, not a few sentences that could be
        rewritten — switching one to simple past leaves the register unchanged. Selection uses
        it instead."""
        found = checks.check_summary_distance(scene(self.RECAPPING))
        self.assertTrue(all(v.severity is Severity.MINOR for v in found))

    def test_one_clause_of_backstory_is_not_recap(self):
        text = ("She set the gauge down. The last person to touch it had left in March. "
                "Tomas came in and put the kettle on. Nobody said anything for a while.")
        self.assertEqual(checks.check_summary_distance(scene(text)), [])


class TestManuscriptRefrain(unittest.TestCase):
    """The aggregate count hides the thing worth knowing.

    Some overlap between scenes of one book is the book. What matters is one phrase turning up
    scene after scene, and a live 15-scene run produced "she had not meant to" in ten of them,
    "the register was more than a ledger" in six. Reported as "128 5-grams already used earlier",
    none of that is visible to anyone reading the report.
    """

    def _corpus(self, phrase: str, scenes: int) -> list[str]:
        return [f"Scene {i} went by. {phrase} and then the shift ended at {i} o'clock."
                for i in range(scenes)]

    def test_the_worst_refrain_is_named(self):
        earlier = self._corpus("She had not meant to look", 6)
        current = "The gate stood open. She had not meant to look at it again that morning."
        found = checks.check_repetition(scene(current), earlier)
        self.assertTrue(found)
        # Which of the overlapping 5-grams wins is incidental; that a refrain is named, and how
        # far it has spread, is the point.
        self.assertIn("has now appeared in 7 scenes", found[0].detail)
        self.assertIn("not meant to", found[0].detail)

    def test_ordinary_overlap_lists_examples_instead(self):
        earlier = ["She put the ledger on the bench and went out to the yard."]
        current = "She put the ledger on the bench and left it there."
        found = checks.check_repetition(scene(current), earlier)
        self.assertTrue(found)
        self.assertNotIn("has now appeared", found[0].detail)

    def test_it_stays_advisory(self):
        """Every refrain measured in a live book was stylistic rather than the book's own
        vocabulary, so gating is probably right for real prose — but any fixture assembled from a
        pool of components repeats those components across scenes as a matter of arithmetic, and
        a gate the suite cannot represent is how a green suite comes to prove nothing."""
        earlier = self._corpus("She had not meant to look", 8)
        current = "She had not meant to look, and the door was open anyway."
        found = checks.check_repetition(scene(current), earlier)
        self.assertTrue(all(v.severity is Severity.MINOR for v in found))


class TestStackedAbsolutes(unittest.TestCase):
    """The dominant tic in this project's prose, and the one that survived every other check.

    Measured across 91 committed scenes and the three reference drafts in `docs/evidence`:
    sentences hanging two or more possessive absolutes off commas appear in 71 of the 91 and in
    none of the three, median 2 per scene, maximum 13.
    """

    ONE = ("She turned back to the screen, her fingers moving over the keys. The kettle clicked "
           "off. Nobody said anything for a while.")
    STACKED = ("She waited, her fingers curled around the cabinet, her eyes fixed on his head. "
               "He did not look up, his back to her, his shoulders set. "
               "Sofie watched him, her hands still, her nails pressing into the wood.")

    def test_one_absolute_is_ordinary_writing(self):
        self.assertEqual(checks.check_absolute_stack(scene(self.ONE)), [])

    def test_a_habit_of_stacking_is_flagged(self):
        found = checks.check_absolute_stack(scene(self.STACKED))
        self.assertIn("stacked_absolutes", kinds(found))
        self.assertTrue(all(v.severity is Severity.MAJOR for v in found))

    def test_two_stacked_sentences_read_as_deliberate(self):
        """The threshold is three, where it stops being a moment and becomes a habit."""
        two = ("She waited, her fingers curled around the cabinet, her eyes fixed on his head. "
               "The gate stood open. He did not look up, his back to her, his shoulders set.")
        self.assertEqual(checks.check_absolute_stack(scene(two)), [])

    def test_each_violation_quotes_a_sentence_a_repair_can_reach(self):
        found = checks.check_absolute_stack(scene(self.STACKED))
        self.assertEqual(len({v.quote for v in found}), len(found))
        for v in found:
            self.assertIsNotNone(checks.locate_quote(self.STACKED, v.quote))


class TestAnaphora(unittest.TestCase):
    """The rhetorical triple: one phrase opening three clauses of a single sentence.

    Measured across 91 committed scenes it appears in 31 of them, and in none of the three
    reference drafts in `docs/evidence`. It survived the tic check because the continuations
    differ — "the way his back remained straight, the way his fingers did not falter, the way
    the hum continued" shares only "the way" — and it survived the duplication ratio because
    three repeats of two words is nothing against a whole scene.
    """

    def test_a_triple_is_flagged(self):
        text = ("She watched him, the way his back remained straight, the way his fingers did "
                "not falter, the way the hum continued underneath it all.")
        found = checks.check_anaphora(scene(text))
        self.assertIn("anaphora", kinds(found))
        self.assertIn("the way", found[0].detail)

    def test_the_quote_is_the_sentence_a_repair_can_reach(self):
        text = ("The gate stood open. They were coming for the years he had taken, the years "
                "he had lost, the years he had never meant to steal. Nobody moved.")
        found = checks.check_anaphora(scene(text))
        self.assertTrue(found)
        self.assertIsNotNone(checks.locate_quote(text, found[0].quote))
        self.assertNotIn("The gate stood open", found[0].quote)

    def test_two_parallel_clauses_are_not_a_triple(self):
        """Two is a pair and reads as deliberate; three is the tell."""
        text = "She noticed the way he stood, the way he held the clipboard, and said nothing."
        self.assertEqual(checks.check_anaphora(scene(text)), [])

    def test_repetition_across_sentences_is_not_this(self):
        """`check_internal_repetition` owns that. This is one sentence turning on itself."""
        text = ("She noticed the way he stood. He put the clipboard down. She noticed the way "
                "he waited. The kettle clicked off. She noticed the way he left.")
        self.assertEqual(checks.check_anaphora(scene(text)), [])


class TestCopiedRuns(unittest.TestCase):
    """One copied phrase is one leak, however many n-grams fit inside it."""

    SCENE = ("She waited by the sill. Ingrid exhales visible breath through the window and "
             "turns back. The stove ticked.")

    def test_overlapping_ngrams_merge_into_one_run(self):
        """Seven copied words are two overlapping six-grams. Counted separately they read as two
        leaks and tripped a threshold meant to require two, which held scene 9 of a live run on
        a single copied phrase."""
        runs = checks.copied_runs(self.SCENE,
                                  "Ingrid exhales visible breath through the window.", 6, 4)
        self.assertEqual(runs, ["ingrid exhales visible breath through the window"])

    def test_separated_copies_stay_separate(self):
        scene = ("Ingrid exhales visible breath through the window. The stove ticked twice and "
                 "then stopped. She crosses her fingers without noticing the register pages.")
        source = ("Ingrid exhales visible breath through the window. She crosses her fingers "
                  "without noticing the register pages.")
        self.assertEqual(len(checks.copied_runs(scene, source, 6, 4)), 2)

    def test_a_grammar_heavy_run_does_not_count(self):
        runs = checks.copied_runs("He turned his back to the council the way a man leaves.",
                                  "Dain turns his back to the council and walks out", 6, 4)
        self.assertEqual(runs, [])

    def test_nothing_shared_is_no_runs(self):
        self.assertEqual(checks.copied_runs(self.SCENE, "An unrelated sentence entirely.", 6, 4),
                         [])


class TestForbiddenPhrase(unittest.TestCase):
    """The quote has to be something a repair can find and rewrite."""

    STORY = None

    def _story(self):
        return make_story(style=StyleContract(forbidden_phrases=["truth", "everything changed"]))

    TEXT = ("She put the ledger down. He wanted the truth and she did not have it. "
            "The stove ticked. After that everything changed for the two of them. "
            "Nobody said the truth out loud again.")

    def test_every_occurrence_gets_its_own_violation(self):
        found = checks.check_forbidden(scene(self.TEXT), self._story())
        self.assertEqual(len(found), 3)
        self.assertEqual(len({v.quote for v in found}), 3)

    def test_each_quote_locates_in_the_scene(self):
        """A five-letter ban like "truth" is shorter than `locate_quote`'s floor, so quoting the
        phrase produced a violation no repair could reach — it fell through to whole-scene repair
        and held scene 1 of a live book."""
        for v in checks.check_forbidden(scene(self.TEXT), self._story()):
            with self.subTest(quote=v.quote):
                self.assertIsNotNone(checks.locate_quote(self.TEXT, v.quote))

    def test_the_detail_still_names_the_phrase(self):
        found = checks.check_forbidden(scene(self.TEXT), self._story())
        self.assertTrue(any('"truth"' in v.detail for v in found))

    def test_clean_prose_passes(self):
        self.assertEqual(checks.check_forbidden(scene("She put the ledger down."),
                                                self._story()), [])


class TestBeatIsProse(unittest.TestCase):
    """A beat written as prose is prose the writer copies back. Only quoted dialogue is checked,
    because that is the unambiguous mark — and the ambiguous one bit immediately."""

    def _plan(self, beat: str):
        from redthread.models import Thread, Transition
        spec = make_spec(beats=[Beat(beat)],
                         thread_ops={"T": Transition(post=["something happens"])})
        story = make_story(threads=[Thread(id="T", name="A thread")])
        return checks.check_beats_are_intent([spec], story)

    def test_written_dialogue_is_flagged(self):
        for beat in ("Dain speaks, his words cutting through the silence, "
                     "'You will not take these years.'",
                     'Varyn says, "Return the years, or face the consequences."'):
            with self.subTest(beat=beat):
                self.assertIn("beat_is_prose", kinds(self._plan(beat)))

    def test_possessive_apostrophes_are_not_dialogue(self):
        """From a live plan: "She connects pass's history to register's altered entries" has two
        apostrophes twenty characters apart, and was flagged as a line of dialogue."""
        for beat in ("She connects pass's history to register's altered entries",
                     "Ingrid's hand shakes as she reads her mother's column of safe-days",
                     "The villagers' meeting ends without a vote on the pass's closure"):
            with self.subTest(beat=beat):
                self.assertEqual(self._plan(beat), [])


class TestCharacterOverlap(unittest.TestCase):
    def test_full_cast_cut_flagged(self):
        found = checks.check_character_overlap(make_spec(characters=["beata"]), ["siv", "otto"])
        self.assertIn("cohesion_cut", kinds(found))

    def test_shared_character_passes(self):
        found = checks.check_character_overlap(make_spec(characters=["siv"]), ["siv", "otto"])
        self.assertEqual(found, [])

    def test_first_scene_passes(self):
        self.assertEqual(checks.check_character_overlap(make_spec(), []), [])


class TestRunAll(unittest.TestCase):
    def test_worst_severity_reported(self):
        found = checks.run_all(
            scene("## Heading\n\nHer chest tightened. Her stomach dropped. Her throat closed."),
            make_spec(word_target=1000), make_story())
        self.assertEqual(checks.worst(found), Severity.BLOCKER)

    def test_clean_scene_has_no_blockers_or_majors(self):
        text = ("Otto had the intake housing open and both hands inside it. He did not look up. "
                "Siv put the notebook on the bench where he would see it and did not open it. "
                "The pump cycled, caught, and settled. She counted eleven seconds before it "
                "cycled again, which was two seconds longer than the log claimed, and she wrote "
                "that down as well. Outside, a truck went past on the access road without "
                "slowing. Otto asked her to pass the smaller wrench. She passed him the "
                "smaller wrench.")
        found = checks.run_all(scene(text), make_spec(word_target=len(text.split())),
                               make_story())
        serious = [v for v in found if v.severity is not Severity.MINOR]
        self.assertEqual(serious, [], f"clean prose produced: {[str(v) for v in serious]}")


if __name__ == "__main__":
    unittest.main()


class TestTruncated(unittest.TestCase):
    """The counterpart of the bounded output budget: a capped runaway ends mid-sentence."""

    def test_mid_sentence_ending_is_flagged(self):
        found = checks.check_truncated(scene("She walked to the bench and picked up the"))
        self.assertEqual(found[0].kind, "truncated_scene")
        self.assertEqual(found[0].severity, Severity.MAJOR)

    def test_terminal_punctuation_passes(self):
        for ending in ("It held.", "Did it hold?", "It held!", "It held…",
                       '"It held."', "It held.”"):
            self.assertEqual(checks.check_truncated(scene("Some prose. " + ending)), [],
                             ending)

    def test_empty_scene_is_not_double_flagged(self):
        self.assertEqual(checks.check_truncated(scene("   ")), [])


class TestSeamTailCopy(unittest.TestCase):
    """From the first complete manuscript: scene 2 re-used scene 1's closing sentence as its
    own ending, verbatim — the tail its brief handed it as context, copied forward."""

    def test_copied_ending_is_major(self):
        tail = ("she did not know why the provision had done what it had done and "
                "she only needed to remember it now")
        text = ("Otto said nothing else worth keeping. " * 30
                + "She did not know why the Provision had done what it had done and she "
                  "only needed to remember it now.")
        found = checks.check_seam(scene(text), tail)
        self.assertIn("seam_tail_copy", kinds(found))

    def test_fresh_ending_passes(self):
        tail = "she wrote the number down and closed the book on it for the night"
        text = ("Otto said nothing else worth keeping. " * 30
                + "The truck pulled out of the yard with its lights off.")
        found = checks.check_seam(scene(text), tail)
        self.assertNotIn("seam_tail_copy", kinds(found))

    def test_name_stance_opening_is_flagged_as_reset(self):
        found = checks.check_seam(
            scene("Siv Alderman stood in the maintenance yard with the notebook."),
            "some previous text here")
        self.assertIn("seam_reset", kinds(found))


class TestRecapBlock(unittest.TestCase):
    """The repairable half of summary distance.

    `check_summary_distance` measures a register and stays advisory, which was correct and was
    also the end of the analysis for a week: the number moved .28 to .25 across a whole prose
    pass while the brief named it and quoted the target. Measuring the distribution instead of
    the density splits the problem — past perfect arrives in blocks, and a block has edges.
    """

    def _scene(self, text):
        return Scene(spec_id="s", index=1, text=text)

    def test_a_run_of_four_is_a_block(self):
        text = ("The kettle clicked off. She had come to the depot in the spring. The office had "
                "been three rooms then. Nobody had told her what the second ledger was for. She "
                "had asked twice and been given the same answer. He put the cup down.")
        blocks = checks.recap_blocks(text)
        self.assertEqual([c for _, _, c in blocks], [4])
        lo, hi, _ = blocks[0]
        self.assertTrue(text[lo:hi].strip().startswith("She had come"))
        self.assertTrue(text[lo:hi].strip().endswith("same answer."))

    def test_three_in_a_row_is_not_a_block(self):
        """The reference drafts reach two. Three is the median committed scene, so the floor
        sits above it — a check that fires on the median is a check that fires on everything."""
        text = ("The kettle clicked off. She had come to the depot in the spring. The office had "
                "been three rooms then. Nobody had told her about it. He put the cup down.")
        self.assertEqual(checks.recap_blocks(text), [])

    def test_a_run_broken_by_scene_is_two_short_runs(self):
        text = ("She had come in spring. The office had been three rooms. She opened the door. "
                "Nobody had told her. She had asked twice. It had stayed that way. He waited.")
        self.assertEqual(checks.recap_blocks(text), [])

    def test_the_violation_is_major_and_quotes_the_whole_block(self):
        scene = self._scene(fakes.recap_prose(700, 0))
        found = checks.check_recap_block(scene)
        self.assertEqual(len(found), 1)
        self.assertIs(found[0].severity, Severity.MAJOR)
        self.assertEqual(found[0].kind, "recap_block")
        # The quote must locate, or the repair cannot find what to replace.
        self.assertIsNotNone(checks.locate_quote(scene.text, found[0].quote))
        self.assertGreaterEqual(len(checks.sentence_spans(found[0].quote)), 4)

    def test_clean_prose_carries_no_block(self):
        for variant in (0, 1, 2):
            with self.subTest(variant=variant):
                scene = self._scene(fakes.clean_prose(900, variant))
                self.assertEqual(checks.check_recap_block(scene), [])

    def test_the_reference_drafts_carry_no_block(self):
        """The threshold's whole justification. gemma3:12b, phi4:14b and qwen3:8b writing one
        cold scene each reach runs of 1, 1 and 2 — none of them reaches three, while 41 of 99
        scenes this project committed carry a run of four or more."""
        drafts = sorted(Path("docs/evidence").glob("scene01-*.txt"))
        self.assertEqual(len(drafts), 3, "the reference corpus moved; re-measure the threshold")
        for draft in drafts:
            with self.subTest(draft=draft.name):
                text = draft.read_text(encoding="utf-8")
                self.assertEqual(checks.recap_blocks(text, run=3), [],
                                 "a reference draft reached three in a row")

    def test_it_runs_as_part_of_the_scene_checks(self):
        found = checks.run_all(self._scene(fakes.recap_prose(700, 0)),
                               make_spec(word_target=700), make_story())
        self.assertIn("recap_block", {v.kind for v in found})


class TestPervasivePovIsNotQuoted(unittest.TestCase):
    """A quote is an invitation to sentence surgery, so a register must not carry one.

    gemma3:12b wrote scene 11 of a live run with 35 first-person uses outside a third-limited
    contract. The violation quoted the first of them, surgery took the bait, and the loop
    rewrote one sentence of thirty-five three times before the budget ran out. The check's own
    docstring already said narration in the wrong person "needs rewriting, not patching"; the
    quote was what stopped that from being true.
    """

    def _run(self, text):
        return checks.check_pov(scene(text), make_story(
            style=StyleContract(pov="third limited", tense="past")))

    def test_wholesale_first_person_is_a_blocker_with_no_quote(self):
        text = " ".join(
            f"I walked to the {n} and I put my hand on it and I waited." for n in
            ("door", "bench", "window", "gate", "stove", "table", "rail", "sink", "chair"))
        found = [v for v in self._run(text) if v.kind == "pov_person"]
        self.assertEqual(len(found), 1)
        self.assertIs(found[0].severity, Severity.BLOCKER)
        self.assertEqual(found[0].quote, "",
                         "a quote routes this to sentence surgery, which cannot converge on it")

    def test_a_handful_of_slips_still_carries_a_quote(self):
        """The other half of the distinction. A few first-person slips in close third *are*
        sentence-local, and taking their quote away would send them to whole-scene repair."""
        text = ("She crossed the yard and put her shoulder to the door. The hinge gave. "
                "I could not have said why she stopped there. She counted the crates twice "
                "and wrote the number on the back of her hand, then went back inside.")
        found = [v for v in self._run(text) if v.kind == "pov_person"]
        if found:
            self.assertIs(found[0].severity, Severity.MAJOR)
            self.assertTrue(found[0].quote, "a locatable slip should keep its quote")


class TestGesture(unittest.TestCase):
    """What repeats in a bad scene is often the movement, not the word for it.

    Found by reading a finished book instead of measuring one. *The Keeper's Fourth Book* scored
    .000 duplication and zero blocks of recap and still read as repetitive: fingers tracing,
    hovering and brushing, a jaw tightening, arms crossing and folding, a head tilting — the same
    small movements, freshly worded every time, invisible to every check here.

    The blindness is structural, not an oversight. `duplication_ratio` counts repeated n-grams
    and the sampler's repetition penalty suppresses repeated tokens; both push the model toward
    *rewording* what it keeps doing. The measured gesture rate went slightly up when the penalty
    landed (3.6 to 4.1 per thousand words) while duplication went to nearly zero.
    """

    def _scene(self, text):
        return Scene(spec_id="s", index=1, text=text)

    FIDGET = (
        "Her fingers traced the edge of the desk. He tilted his head. Her jaw tightened once. "
        "His hand hovered over the ledger. Her arms crossed. His gaze settled on the window. "
        "Her shoulders pressed back. His thumb brushed the spine of the book. Her brow "
        "narrowed. His knuckles whitened. She waited.")

    def test_the_rate_counts_movements_not_words(self):
        """Every gesture in the fixture is worded differently, so duplication sees nothing."""
        self.assertLess(checks.duplication_ratio(self.FIDGET), 0.05)
        self.assertGreater(checks.gesture_rate(self.FIDGET), 3.0)

    def test_density_is_advisory_because_it_is_a_register(self):
        """Cutting one hand-brush leaves the other eleven, so it must not hold the gate."""
        found = checks.check_gesture_density(self._scene(self.FIDGET))
        self.assertEqual(len(found), 1)
        self.assertIs(found[0].severity, Severity.MINOR)

    def test_the_clean_cohort_never_trips_the_density(self):
        """The threshold's justification: three reference drafts and the two scenes gemma3:12b
        committed inside this orchestrator top out at 2.5 per thousand words."""
        drafts = sorted(Path("docs/evidence").glob("scene01-*.txt"))
        self.assertEqual(len(drafts), 3, "the reference corpus moved; re-measure the threshold")
        for draft in drafts:
            with self.subTest(draft=draft.name):
                text = draft.read_text(encoding="utf-8")
                self.assertLess(checks.gesture_rate(text), 3.0)
                self.assertEqual(checks.check_gesture_density(self._scene(text)), [])

    def test_a_repeated_gesture_is_major_and_quoted(self):
        """The tic half. It sits in a sentence, so surgery can reach it — and it is a separate
        defect from the density: the Keeper book has a high rate and no scene in it repeats one
        gesture more than once, while 23 of 124 committed scenes do."""
        text = ("Her fingers traced the rail. She said nothing for a while. Her fingers traced "
                "the chart. The kettle boiled over. Her fingers traced the logbook spine.")
        found = checks.check_gesture_tic(self._scene(text))
        self.assertTrue(found)
        self.assertIs(found[0].severity, Severity.MAJOR)
        self.assertIsNotNone(checks.locate_quote(text, found[0].quote))

    def test_two_of_the_same_gesture_is_not_a_tic(self):
        text = ("Her fingers traced the rail. She said nothing. Her fingers traced the chart. "
                "The kettle boiled over and she took it off the ring.")
        self.assertEqual(checks.check_gesture_tic(self._scene(text)), [])

    def test_both_run_as_part_of_the_scene_checks(self):
        found = checks.run_all(self._scene(self.FIDGET),
                               make_spec(word_target=60), make_story())
        self.assertIn("gesture_density", {v.kind for v in found})
