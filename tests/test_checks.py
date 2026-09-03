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

    def test_the_allowance_rises_with_dialogue(self):
        """The first threshold was flat and calibrated on a biased sample.

        It was set at 3.0 per thousand words from a five-scene clean cohort, four of which
        contain no dialogue at all because they are cold opening scenes. Applied to a book that
        is 15% dialogue it fired on 34 of 71 scenes, and the scenes it fired on had *higher*
        dialogue than the ones it spared — penalising exactly the scenes that had improved.

        Dialogue carries physical business: across 160 scenes of four books, r = +0.303 between
        dialogue share and gesture rate, with group means 1.9 silent to 3.5 dialogue-led.
        """
        # Four gestures in about nine hundred words — 4.5 per thousand, over the 3.0 a silent
        # scene is allowed and under the 4.2 a scene at 10% dialogue is given.
        filler = "She counted the crates and wrote the number on the docket. " * 80
        gestures = ("Her fingers traced the rail. He tilted his head. Her jaw tightened. "
                    "His hand hovered over the ledger. ")
        speech = " ".join(
            f'"{line}," she said.' for line in
            ("The ledger is in the drawer and it has been since Tuesday morning",
             "You signed it yourself and then you told the inspector you had not",
             "I did not ask you that and you know perfectly well what I asked",
             "Then say what you did ask, and say it the way you said it to him",
             "It was never about the money and I am not going to pretend it was",
             "You can put that in the report or you can leave it out entirely",
             "The inspector will read it either way and he will know what is missing"))
        silent = gestures + filler
        talky = gestures + filler + " " + speech

        self.assertAlmostEqual(checks.gesture_rate(silent), 4.5, delta=0.3)
        self.assertTrue(checks.check_gesture_density(self._scene(silent)),
                        "this rate in a silent scene is over the allowance")
        self.assertEqual(checks.check_gesture_density(self._scene(talky)), [],
                         "the same gestures in a dialogue scene are the beats between its lines")

    def test_stillness_is_not_a_movement(self):
        """"steady" was the commonest thing this detector matched — 184 of roughly 1,100 across
        every book in the project — and "her voice steady" describes stillness. "pressure" is a
        noun the verb pattern was catching. Both inflated every gesture rate measured before
        they were removed."""
        self.assertEqual(checks.gesture_pairs("Her voice steady, she read the number out."), [])
        self.assertEqual(checks.gesture_pairs("His hand steady on the rail, he waited."), [])
        self.assertEqual(checks.gesture_pairs("She felt the pressure of his hand pressure."), [])
        # the real movements still register
        self.assertTrue(checks.gesture_pairs("His hand pressed flat against the desk."))
        self.assertTrue(checks.gesture_pairs("Her fingers traced the rail."))

    def test_within_scene_variety_is_not_the_signal(self):
        """Recorded because it was measured and refuted. Distinct gesture pairs over total
        gestures sits at ~1.0 across four books — the repetition is between scenes, not inside
        them, which is why this check cannot see the gesture that appears in nine of them."""
        pairs = [(p, v) for p, v, _ in checks.gesture_pairs(self.FIDGET)]
        self.assertGreaterEqual(len(set(pairs)) / len(pairs), 0.9)

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


class TestManuscriptRefrains(unittest.TestCase):
    """A refrain is the manuscript's defect, not any scene's, so it is prevented not repaired.

    Found by running 71 scenes instead of nine. Every scene of that book was individually clean
    — duplication .001 per scene — while the manuscript measured .030, with "the blade at his
    side" appearing in 8 separate scenes of 37. `check_repetition` finds this and reporting is
    all it can do: no repair applied to scene 37 removes a phrase from scenes 4, 9 and 22. The
    only place to act on it is the brief for the scene not yet written.
    """

    # Every scene needs its own filler. A shared one is itself a refrain across the fixture,
    # which the first version of this test discovered by ranking its own scaffolding first.
    _FILLER = ["she counted the crates twice", "the pump cycled and caught", "rain came sideways",
               "he signed the docket", "the ferry was late again", "someone had moved the stove",
               "the tide turned early", "a gull went over", "the kettle was still going",
               "the lamp needed trimming", "he wound the clock", "the yard door stuck"]

    def _scenes(self, phrase, count, offset=0):
        return [f"{phrase}, and {self._FILLER[(i + offset) % len(self._FILLER)]}."
                for i in range(count)]

    def test_a_phrase_in_three_scenes_is_a_refrain(self):
        found = checks.manuscript_refrains(self._scenes("the blade at his side", 3))
        self.assertTrue(any("blade at his side" in p for p, _ in found))

    def test_two_scenes_is_not_yet_a_refrain(self):
        """It has to be a pattern before it is worth spending brief space on."""
        found = checks.manuscript_refrains(self._scenes("the blade at his side", 2))
        self.assertEqual(found, [])

    def test_nothing_to_report_before_there_is_a_manuscript(self):
        self.assertEqual(checks.manuscript_refrains([]), [])

    def test_the_count_is_scenes_not_occurrences(self):
        """Ten uses in one scene is `check_internal_repetition`'s problem and has a repair.
        This is the other axis: a phrase used once each in many scenes, which has none."""
        one_scene = ["the blade at his side. " * 10]
        self.assertEqual(checks.manuscript_refrains(one_scene), [])

    def test_the_list_is_capped_and_ordered_worst_first(self):
        texts = (self._scenes("the blade at his side", 8)
                 + self._scenes("a pause stretched between them", 4, offset=8))
        found = checks.manuscript_refrains(texts, limit=3)
        self.assertLessEqual(len(found), 3)
        self.assertEqual(found[0][1], 8)
        self.assertTrue(all(found[i][1] >= found[i+1][1] for i in range(len(found)-1)))

    def test_it_reaches_the_brief(self):
        from redthread import brief as briefmod
        from redthread.ledger import Ledger
        text = briefmod.render_brief(
            make_spec(), make_story(), Ledger(),
            refrains=[("the blade at his side", 8)])
        self.assertIn("the blade at his side", text)
        self.assertIn("refrain", text.lower())


class TestSceneIsPeopled(unittest.TestCase):
    """The spec put two people in the room and the prose gave them nothing to say.

    Found by reading the middle of a 71-scene book. Scene 38 is one character alone in a ruin,
    touching statues and remembering, and every check passed it — including `summary_distance`,
    because the flashback it becomes is narrated in simple past.

    The measurement then showed the emptying-out is a shape rather than a level: dialogue runs at
    21% of words across the opening eighteen scenes, 15% in the next, 10% in the third and 9% in
    the last, with silent scenes going from 2 of 18 to 9 of 18. Twenty of the 71 were populated
    by the plan and silent on the page, including all four three-character scenes of the climax.
    """

    SILENT = ("Vael walked between the statues. The air smelled of dust. He crouched beside one "
              "and traced the ridges of it. The memory came back to him slowly, the way water "
              "seeps through a crack, and he stayed there a while longer than he meant to.")
    SPOKEN = ("Vael crouched beside the statue. “You said the records were burned,” he "
              "said. Sera did not look up from the ledger. “I said they were filed. Those "
              "are different words and you know it.” He put the blade down on the stone.")

    def _spec(self, *characters):
        return make_spec(characters=list(characters))

    def test_two_characters_and_no_dialogue_is_reported(self):
        found = checks.check_scene_is_peopled(self._spec("vael", "sera"), scene(self.SILENT))
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].kind, "unpeopled_scene")

    def test_it_is_advisory(self):
        """Two people can share a scene in silence, and no corpus here says what rate is normal
        in good fiction. It must not gate on a number nobody has calibrated."""
        found = checks.check_scene_is_peopled(self._spec("vael", "sera"), scene(self.SILENT))
        self.assertIs(found[0].severity, Severity.MINOR)

    def test_a_scene_where_they_speak_is_clean(self):
        self.assertEqual(
            checks.check_scene_is_peopled(self._spec("vael", "sera"), scene(self.SPOKEN)), [])

    def test_one_character_alone_is_not_flagged(self):
        """A solitary scene the plan asked for is the plan's business, not the prose's."""
        self.assertEqual(
            checks.check_scene_is_peopled(self._spec("vael"), scene(self.SILENT)), [])

    def test_dialogue_share_counts_spoken_words(self):
        self.assertGreater(checks.dialogue_share(self.SPOKEN), 0.2)
        self.assertEqual(checks.dialogue_share(self.SILENT), 0.0)
        self.assertEqual(checks.dialogue_share(""), 0.0)

    def test_it_runs_as_part_of_the_scene_checks(self):
        found = checks.run_all(scene(self.SILENT),
                               make_spec(word_target=50, characters=["vael", "sera"]),
                               make_story())
        self.assertIn("unpeopled_scene", {v.kind for v in found})


class TestManuscriptGestures(unittest.TestCase):
    """The refrain the phrase check cannot see, because the words differ every time.

    Two 71-scene books measured: the first has a jaw tightening in 13 separate scenes; the
    second, written after the dialogue fix, has eyes flicking in 13, a gaze lingering in 12 and
    fingers curling in 10 — and 11 distinct gestures reaching four or more scenes, against 5 in
    the first. More dialogue means more beats between lines and the model draws them from the
    same short stock. A nine-scene book has none of these, so like the phrase refrains it is a
    defect that only appears with length.
    """

    def _scenes(self, gesture, count, other="She counted the crates and signed the docket."):
        return [f"{gesture} {other} Scene {i} of the book." for i in range(count)]

    def test_a_gesture_in_four_scenes_is_reported(self):
        # Worded differently every time, so nothing that counts n-grams sees it.
        scenes = ["Her jaw tightened as she read it.",
                  "His jaw was tightening before she finished the sentence.",
                  "His jaw tightened and he said nothing at all.",
                  "Her jaw tightened once, then let go."]
        found = checks.manuscript_gestures(scenes)
        self.assertTrue(any(p.startswith("jaw tight") for p, _ in found), found)
        # The label must be a word somebody could have written, not the five-character
        # stem used to group inflections: a brief telling a model to stop writing
        # "jaw tighte" asks it to avoid a word nobody wrote.
        self.assertTrue(any(p in ("jaw tightened", "jaw tightening")
                            for p, _ in found), found)
        self.assertEqual(checks.manuscript_refrains(scenes), [],
                         "the phrase check must see nothing here — that is the whole point")

    def test_three_scenes_is_not_yet_a_pattern(self):
        self.assertEqual(checks.manuscript_gestures(self._scenes("Her jaw tightened.", 3)), [])

    def test_nothing_before_there_is_a_manuscript(self):
        self.assertEqual(checks.manuscript_gestures([]), [])

    def test_the_list_is_capped_and_worst_first(self):
        scenes = (self._scenes("Her jaw tightened.", 9)
                  + self._scenes("Her fingers traced the rail.", 5))
        found = checks.manuscript_gestures(scenes, limit=2)
        self.assertLessEqual(len(found), 2)
        self.assertEqual(found[0][1], 9)

    def test_it_reaches_the_brief_and_refuses_the_synonym(self):
        from redthread import brief as briefmod
        from redthread.ledger import Ledger
        text = briefmod.render_brief(make_spec(), make_story(), Ledger(),
                                     gestures=[("jaw tightened", 13)])
        self.assertIn("jaw tightened", text)
        self.assertIn("same movement", text)


class TestModelRefrains(unittest.TestCase):
    """A habit the writer brings to every book, which no per-book check can see.

    `manuscript_refrains` reads one manuscript. Measured across seven completed books with seven
    different premises, "the edge of the" is a refrain — three or more scenes — in **all seven**,
    and "the weight of the" in six. Neither stands out inside any single book, which is exactly
    why looking inside one cannot find them.

    The control that produced this is the one worth keeping: 77% of what `manuscript_refrains`
    reports is genuinely book-specific and does not appear in a book with a different premise.
    The 23% that leaks is this list.
    """

    def test_the_list_loads(self):
        phrases = checks.load_model_refrains()
        self.assertIn("the edge of the", phrases)
        self.assertTrue(all(p == p.lower().strip() for p in phrases))
        self.assertTrue(all(len(p.split()) >= 3 for p in phrases),
                        "short entries are the unavoidable-ban problem; these must be routable")

    def test_a_missing_file_is_not_an_error(self):
        self.assertEqual(checks.load_model_refrains(Path("does-not-exist.txt")), [])

    def test_comments_and_counts_do_not_leak_into_the_phrases(self):
        for p in checks.load_model_refrains():
            self.assertNotIn("#", p)
            self.assertFalse(any(ch.isdigit() for ch in p))

    def test_it_reaches_the_brief_separately_from_this_book_s_refrains(self):
        from redthread import brief as briefmod
        from redthread.ledger import Ledger
        text = briefmod.render_brief(
            make_spec(), make_story(), Ledger(),
            refrains=[("the blade at his side", 8)],
            model_refrains=["the edge of the"])
        self.assertIn("the blade at his side", text)
        self.assertIn("the edge of the", text)
        self.assertIn("every book you write", text,
                      "the two are different claims and must not be presented as one")


class TestRepetitionConcentration(unittest.TestCase):
    """`duplication_ratio` cannot tell many mild echoes from one dominant refrain.

    Across five runs of one plan the aggregate rose while the book got better:

        run                      duplication   top 1% share   worst phrase
        before the dialogue fix      .041           2.8%           8 scenes
        + dialogue fix               .061           6.5%          28
        + catchphrase fix            .055           3.1%          15
        latest                       .066           2.4%           7

    The two books that matter most are the extremes: the one with a phrase in 28 scenes has
    *lower* duplication than the one whose worst phrase is in 7. Reporting duplication alone
    inverts the ranking a reader would give them.
    """

    # No two base scenes may share a five-word run, or the scaffolding is itself the refrain.
    # Two earlier versions of this fixture reported a worst phrase of 20 scenes in both arms,
    # once from a shared sentence and once from a shared template.
    def _book(self, refrain=None, refrain_scenes=0, n=20):
        words = ("alder birch cedar dogwood elm fir gorse hazel ivy juniper larch maple "
                 "nettle oak pine quince rowan sallow thorn willow yew ash beech cherry "
                 "damson elder fig gean holly").split()
        scenes = []
        for i in range(n):
            w = [words[(i * 7 + k) % len(words)] for k in range(12)]
            scenes.append(" ".join(w) + ".")
        for i in range(refrain_scenes):
            scenes[i] += f" {refrain}"
        return scenes

    def test_one_dominant_refrain_concentrates(self):
        spread = self._book()
        peaked = self._book("the blade at his side glinted", 12)
        _, worst_spread = checks.repetition_concentration(spread)
        conc_peak, worst_peak = checks.repetition_concentration(peaked)
        self.assertGreater(worst_peak, worst_spread)
        self.assertGreater(conc_peak, 0.0)

    def test_it_reports_the_worst_phrase_scene_count(self):
        _, worst = checks.repetition_concentration(
            self._book("the blade at his side glinted", 9))
        self.assertGreaterEqual(worst, 9)

    def test_nothing_to_report_without_a_manuscript(self):
        self.assertEqual(checks.repetition_concentration([]), (0.0, 0))
        self.assertEqual(checks.repetition_concentration(["one scene only."])[1], 0)

    def test_it_disagrees_with_duplication_where_it_should(self):
        """The whole reason it exists: a book can have less duplication and a worse refrain."""
        many_mild = self._book(n=40)
        one_bad = self._book("the blade at his side glinted in the low sun", 15, n=20)
        self.assertGreater(checks.repetition_concentration(one_bad)[1],
                           checks.repetition_concentration(many_mild)[1])


class TestInternalRepetitionThreshold(unittest.TestCase):
    """A four-word run appearing twice in eight hundred words is English, not a defect.

    `max_repeats` was 1 until the prose improved past it. On the 373 scenes written since the
    sampler fix that fires on 39% of them, and the findings say so themselves: "1 phrase(s)
    repeated within the scene (0% of it is repeated material)".

        max_repeats   current era   pre-prose-work
             1            39%            100%
             2             2%             99%
             3             0%             94%
    """

    # Filler must not repeat, or the scaffolding is the finding. This file has now made that
    # mistake three times in one day with three hand-rolled generators; `fakes.clean_prose` is
    # maintained for exactly this and has a test asserting its own duplication stays low.
    def _filler(self):
        return " " + fakes.clean_prose(700, 0) + " "

    def _scene(self, text):
        return Scene(spec_id="s", index=1, text=text)

    def test_a_phrase_twice_is_not_reported(self):
        text = ("She looked at it for a moment and then went out. " + self._filler()
                + "He looked at it for a moment too.")
        self.assertEqual(checks.check_internal_repetition(self._scene(text)), [])

    def test_a_phrase_three_times_is(self):
        text = ("She looked at it for a moment. " + self._filler()
                + "He looked at it for a moment. They looked at it for a moment.")
        self.assertTrue(checks.check_internal_repetition(self._scene(text)))

    def test_the_tic_arm_is_untouched(self):
        """Five uses is still a tic with its own MAJOR, which is the arm that repairs."""
        text = "She turned it over in her hands. " * 6 + "The kettle boiled and she took it off."
        found = checks.check_internal_repetition(self._scene(text))
        self.assertTrue(any(v.severity is Severity.MAJOR for v in found))


class TestGlossIsAboutNarrationNotSpeech(unittest.TestCase):
    """A character saying it is characterisation; the narrator saying it is the tell.

    This cost an unattended run. `check_thematic_gloss` is a MAJOR whose repair is to delete the
    offending clause, and a line of dialogue cannot be deleted without breaking the scene — so
    the repair failed five times and `write_all` halted the book. Scene 22 of a 71-scene
    replicate died there, one of two runs of four lost overnight.
    """

    def _scene(self, text):
        from redthread.models import Scene
        return Scene(spec_id="s", index=1, text=text)

    def test_the_narrator_naming_the_point_still_fires(self):
        found = checks.check_thematic_gloss(
            self._scene("She set the ledger down. This was not just about the money, and she "
                        "had known it since the beginning."))
        self.assertEqual(len(found), 1)

    def test_a_character_saying_it_does_not(self):
        # The exact line that killed the run.
        found = checks.check_thematic_gloss(
            self._scene('Kai narrowed his eyes. "This isn\'t just about punishment. If the '
                        'fugitive gets away, others will follow."'))
        self.assertEqual(found, [])

    def test_curly_quotes_are_excluded_too(self):
        found = checks.check_thematic_gloss(
            self._scene("Kai narrowed his eyes. “This isn’t just about punishment.”"))
        self.assertEqual(found, [])

    def test_narration_after_a_quote_still_fires(self):
        # Excluding speech must not excuse the sentence that follows it.
        found = checks.check_thematic_gloss(
            self._scene('"Go," she said. It was not just about the money to him, not any more.'))
        self.assertEqual(len(found), 1)

    def test_the_quote_still_locates_in_the_original_text(self):
        # Offsets must survive the exclusion, or the repair cannot find what to delete —
        # which is why dialogue spans are computed rather than `strip_dialogue` being used.
        text = ('"Go," she said. She looked at the door. It was not just about the money to '
                'him, not any more.')
        found = checks.check_thematic_gloss(self._scene(text))
        self.assertTrue(found)
        for violation in found:
            self.assertIsNotNone(checks.locate_quote(text, violation.quote),
                                 f"a repair cannot delete what it cannot find: {violation.quote!r}")

    def test_dialogue_spans_are_offsets_into_the_original(self):
        text = 'He paused. "Not this." She waited.'
        spans = checks.dialogue_spans(text)
        self.assertEqual(len(spans), 1)
        lo, hi = spans[0]
        self.assertEqual(text[lo:hi], '"Not this."')

    def test_the_reference_drafts_stay_clean(self):
        # rule V's spirit, applied to a prose check: the three cold drafts in docs/evidence are
        # the calibration standard, and a widened or narrowed check must not move them.
        from pathlib import Path
        root = Path(__file__).resolve().parent.parent / "docs" / "evidence"
        for draft in sorted(root.glob("scene01-*.txt")):
            self.assertEqual(
                checks.check_thematic_gloss(
                    self._scene(draft.read_text(encoding="utf-8"))), [],
                f"{draft.name} should stay clean")


class _F:
    """Minimal stand-in for a ledger Fact, so these tests need no Ledger machinery."""

    def __init__(self, subject, obj, scene, kind="detail"):
        self.subject, self.object, self.scene, self.kind = subject, obj, scene, kind
        self.predicate = "has"


class TestWanderingDetails(unittest.TestCase):
    """A fixed mark that moves body region across a book.

    The extraction prompt's own example of a `detail` is "the scar is on the left hand", and
    `is_moveable_pair` says a scar moving hands "is exactly the contradiction this system exists
    to catch". *The Debt of Years* shipped with Kai's scar on his hand, his arm and his temple —
    and the reason is measured, not guessed: `conflict_candidates` did pair the facts, the pair
    was inside `max_pairs`, and the model judge said no. This is the deterministic half.
    """

    def test_a_mark_in_two_regions_is_reported(self):
        found = checks.wandering_details([
            _F("Kai", "a scar along his palm", 15),
            _F("Kai", "a scar running along his temple", 42),
        ])
        self.assertEqual(len(found), 1)
        subject, noun, where = found[0]
        self.assertEqual((subject, noun), ("Kai", "scar"))
        self.assertEqual(sorted(where), ["hand", "head"])
        self.assertEqual(where["hand"], [15])

    def test_parts_of_the_same_region_are_silent(self):
        """`palm` and `hand` name one place at two resolutions.

        Reporting them would make the check fire on ordinary rephrasing, which is how the four
        plan checks this project has reverted all died (rule V).
        """
        self.assertEqual(checks.wandering_details([
            _F("Kai", "a scar on his hand", 3),
            _F("Kai", "a scar along his palm", 9),
            _F("Kai", "a scar across his knuckles", 20),
        ]), [])

    def test_a_span_across_regions_is_not_a_contradiction(self):
        """"A scar from wrist to elbow" names two regions in one phrase and is one scar."""
        self.assertEqual(checks.wandering_details([
            _F("Kai", "a scar from wrist to elbow", 4),
            _F("Kai", "a scar from wrist to elbow, pale now", 30),
        ]), [])

    def test_different_people_do_not_collide(self):
        self.assertEqual(checks.wandering_details([
            _F("Kai", "a scar on his palm", 5),
            _F("Mir", "a scar on his temple", 12),
        ]), [])

    def test_only_details_count(self):
        """A `state` may change; a `detail` is what the prose has fixed."""
        self.assertEqual(checks.wandering_details([
            _F("Kai", "a scar on his palm", 5, kind="state"),
            _F("Kai", "a scar on his temple", 12, kind="state"),
        ]), [])

    def test_the_one_validated_homophone_fires_and_the_correct_form_does_not(self):
        """`pulled taught` for `pulled taut` - 8 occurrences against 43 correct ones.

        A 16% error rate on that homophone across 7 books, and three of the eight get it right
        and wrong in the same sentence: "the silence stretches, taut as a string pulled taught".
        The only entry in the table whose matches have been read, hence the only one asserted
        positively here.
        """
        class Sc:
            def __init__(self, text):
                self.text = text
        fires = checks.check_homophones(Sc("The silence stretched, taut as a string pulled "
                                           "taught."))
        self.assertEqual(len(fires), 1)
        self.assertEqual(fires[0].kind, "homophone")
        self.assertIs(fires[0].severity, Severity.MAJOR)
        self.assertIn("taut", fires[0].detail)

    def test_no_homophone_pattern_fires_on_correct_usage(self):
        """The direction that would send good scenes back for repair.

        `taught` is a perfectly good word and most of these sentences contain the *right* member
        of the pair. Measured over 1,773 scenes the table returns 8 matches in total, all of them
        the one real error, so this pins the silence rather than hoping for it.
        """
        class Sc:
            def __init__(self, text):
                self.text = text
        for ok in ("The rope pulled taut.",
                   "He had taught her to read.",
                   "She taught school in the valley.",
                   "They waited with bated breath.",
                   "A horde of men came over the ridge.",
                   "He pored over the records for an hour.",
                   "She took up the reins of the horse.",
                   "He wondered if it mattered.",
                   "They wandered through the market.",
                   "The path had led him to the door.",
                   "They had passed through the gate."):
            with self.subTest(ok):
                self.assertEqual(checks.check_homophones(Sc(ok)), [],
                                 "correct usage must not send a scene back")

    def test_an_unvalidated_pattern_says_so_in_its_own_violation(self):
        """Thirteen of the fourteen patterns have never fired on this corpus.

        A pattern nobody has read the matches for is not yet a check - and this is not a
        hypothetical: the fifteenth pattern audited, `borne/born`, returned two matches and
        **both were false positives** (`born of necessity` is correct idiom). It is absent from
        the table for that reason. The rest carry the warning in the violation text so the first
        person to see one fire knows to read it before trusting it.
        """
        class Sc:
            def __init__(self, text):
                self.text = text
        fires = checks.check_homophones(Sc("They waited with baited breath."))
        self.assertEqual(len(fires), 1)
        self.assertIn("not yet validated", fires[0].detail)
        self.assertNotIn("not yet validated",
                         checks.check_homophones(Sc("a string pulled taught"))[0].detail)

    def test_born_of_necessity_is_not_flagged(self):
        """The false positive that was caught by reading the matches, pinned so it cannot return.

        `born of necessity` is correct English. The audit's patterns returned it as a `borne`
        error twice, which would have published 10 errors where there are 8 - a 25% overstatement
        behind a docstring claiming the patterns were narrow.
        """
        class Sc:
            def __init__(self, text):
                self.text = text
        for ok in ("It was an illusion born of necessity.",
                   "A crime born of necessity.",
                   "He was born of the enclave."):
            with self.subTest(ok):
                self.assertEqual(checks.check_homophones(Sc(ok)), [])

    def test_the_preflag_catches_the_shipped_defect_at_its_first_scene(self):
        """The founding defect, caught deterministically where the model judge said no.

        Scene 40 of `runs/current` is where `temple` entered the ledger and propagated to the end
        of the book. `conflict_candidates` did offer the pair, it was inside the cap, and the
        model answered no - measured at a 65% miss rate on this pair class
        (docs/evidence/judge-marks.md). No model call is involved here.
        """
        prior = ([_F("Kai", "a scar along his palm", 15), _F("Kai", "a scar on his palm", 16)]
                 + [_F("Kai", "scar on arm", s) for s in (31, 32)])
        found = checks.mark_conflicts_against(
            [_F("Kai", "a scar running along his temple", 40)], prior)
        self.assertEqual(len(found), 1, "one finding per conflict, not per pair")
        old, new, why = found[0]
        self.assertEqual(new.scene, 40)
        self.assertIn("cannot be in two places", why)

    def test_a_location_free_row_cannot_hide_a_wandering_mark(self):
        """The regression that made the pre-flag scan the ledger instead of the candidate list.

        `conflict_candidates` pairs a new fact against the *latest* matching row. In `var3` the
        latest scar row before scene 60 is `[s58] Mirra | has | scar` - no region - so the pair
        offered to the judge was unjudgeable, and the location-bearing `[s46] scar on left hand`
        never got compared. That is the original defect wearing a different hat: a location-free
        fact displacing a location-bearing one. Routing the pre-flag through candidates lost 3 of
        13 wandering books to exactly this; scanning the whole ledger recovers all three.
        """
        prior = [_F("Mirra", "scar on left hand", 46),
                 _F("Mirra", "scar", 52),
                 _F("Mirra", "a scarred hand", 54),
                 _F("Mirra", "scar", 58)]        # latest row, and it names no region
        found = checks.mark_conflicts_against([_F("Mirra", "a scar on her face", 60)], prior)
        self.assertEqual(len(found), 1)
        old, _new, _why = found[0]
        self.assertEqual(old.scene, 46, "must compare against the last row naming a region")

    def test_the_preflag_inherits_every_exclusion_the_book_check_learned(self):
        """Plural, adjacency and spans are let through here too, or the gate halts good scenes."""
        cases = [
            ("plural", [_F("Kai", "a scar along his inner elbow", 12)],
             _F("Kai", "old scars on his hands", 30)),
            ("adjacent regions", [_F("Kai", "a scar on his wrist", 51)],
             _F("Kai", "a scar on his forearm", 58)),
            ("same region", [_F("Kai", "a scar on his hand", 3)],
             _F("Kai", "a scar along his palm", 21)),
            ("a span", [_F("Kai", "a scar from wrist to elbow", 4)],
             _F("Kai", "a scar from wrist to elbow, pale now", 30)),
            ("another person", [_F("Mir", "a scar on his palm", 5)],
             _F("Kai", "a scar on his temple", 12)),
            ("a state, not a detail", [_F("Kai", "a scar on his palm", 5, kind="state")],
             _F("Kai", "a scar on his temple", 12, kind="state")),
        ]
        for label, prior, new in cases:
            with self.subTest(label):
                self.assertEqual(checks.mark_conflicts_against([new], prior), [],
                                 f"{label} must not raise a blocker")

    def test_a_later_row_cannot_be_the_earlier_one(self):
        """Order matters: the established row has to precede the new fact.

        Without the scene check a fact re-extracted in the same scene, or a ledger holding a
        later row, could be reported as contradicting something that has not happened yet.
        """
        self.assertEqual(
            checks.mark_conflicts_against([_F("Kai", "a scar on his palm", 10)],
                                          [_F("Kai", "a scar on his temple", 40)]), [])
        self.assertEqual(
            checks.mark_conflicts_against([_F("Kai", "a scar on his palm", 10)],
                                          [_F("Kai", "a scar on his temple", 10)]), [])

    def test_the_preflag_never_fires_where_the_book_check_is_silent(self):
        """Precision, asserted rather than hoped: it is a BLOCKER and it halts unattended runs.

        Measured across the 28 books of 20+ scenes in `runs/`: the pre-flag fires in all 13 the
        book-level check calls wandering and in none of the 15 it calls clean - 28 of 28
        agreement, zero false blockers. This pins the direction that would break a run.
        """
        clean = [_F("Kai", "a scar on his hand", 3), _F("Kai", "a scar along his palm", 9),
                 _F("Kai", "a scar across his knuckles", 20), _F("Kai", "scar", 25),
                 _F("Vay", "a tattoo on his forearm", 7), _F("Vay", "a tattoo on his wrist", 30)]
        for i in range(1, len(clean)):
            with self.subTest(scene=clean[i].scene):
                self.assertEqual(
                    checks.mark_conflicts_against([clean[i]], clean[:i]), [],
                    "no blocker may come from ordinary rephrasing of one mark")

    def test_a_dict_is_read_like_a_fact(self):
        """The signature promise, pinned — it was false and silently so.

        Fields were read with plain `getattr`, which a dict does not answer, so every field
        came back empty, no mark noun was ever found, and dict input returned `[]`. Not an
        error: a confident "no wandering marks" for the exact sequence this check exists to
        catch. `scripts/wandering_audit.py` had a `_Fact` wrapper for this reason without the
        reason being known, so no published number went through it — but a check that reports
        clean when it cannot read its input is the worst failure mode available to it.
        """
        rows = [
            {"kind": "detail", "subject": "Kai", "predicate": "has",
             "object": "a scar along his palm", "scene": 15},
            {"kind": "detail", "subject": "Kai", "predicate": "has",
             "object": "a scar running along his temple", "scene": 40},
        ]
        found = checks.wandering_details(rows)
        self.assertEqual(len(found), 1, "dict input must not report clean")
        self.assertEqual(sorted(found[0][2]), ["hand", "head"])
        self.assertEqual(found[0][2]["hand"], [15])
        self.assertEqual(checks.wandering_details([_F("Kai", "a scar along his palm", 15),
                                                   _F("Kai", "a scar running along his temple", 40)]),
                         found, "dicts and Facts must give the same answer")

    def test_a_plural_mark_noun_is_not_a_claim_about_one_mark(self):
        """"scars on his hands" is a remark in general, not a location for *the* scar.

        One of the two defects that inflated the published wandering rate from 63% to 79%
        (docs/evidence/wandering-mark-fix.md).
        """
        self.assertEqual(checks.wandering_details([
            _F("Kai", "a scar along his inner elbow", 12),
            _F("Kai", "old scars on his hands", 12),
        ]), [])

    def test_regions_meeting_at_a_joint_are_not_a_contradiction(self):
        """Across scenes, `wrist` and `forearm` can be one scar seen from either side.

        The within-phrase span is caught separately; this is the across-scene case, and it was
        the second rate-inflating defect. Non-adjacent pairs must still fire, so both halves
        are asserted together — a fix that silences everything is not a fix.
        """
        self.assertEqual(checks.wandering_details([
            _F("Kai", "a scar on his wrist", 51),
            _F("Kai", "a scar on his forearm", 58),
        ]), [])
        self.assertTrue(checks.wandering_details([
            _F("Kai", "a scar on his wrist", 51),
            _F("Kai", "a scar on his temple", 58),
        ]), "hand and head do not meet; this must still be reported")

    def test_three_regions_report_even_when_two_are_adjacent(self):
        """The exemption is for exactly two adjacent regions, never for a longer walk."""
        found = checks.wandering_details([
            _F("Kai", "a scar on his wrist", 5),
            _F("Kai", "a scar on his forearm", 20),
            _F("Kai", "a scar on his temple", 40),
        ])
        self.assertEqual(len(found), 1)
        self.assertEqual(sorted(found[0][2]), ["arm", "hand", "head"])

    def test_the_adjacency_table_holds_only_joints(self):
        """Every pair names two regions that actually meet, and no pair is a shortcut.

        The table was extended from `hand/arm` to all four pairs after checking the extension
        changes no classification across 21 long books. This pins the shape rather than that
        measurement: a later hand that adds `hand`/`head` to quiet a flag has to delete a test
        that says why it cannot.
        """
        self.assertEqual(checks._ADJACENT_REGIONS, frozenset({
            frozenset(("hand", "arm")), frozenset(("arm", "torso")),
            frozenset(("head", "torso")), frozenset(("torso", "leg")),
        }))
        for pair in checks._ADJACENT_REGIONS:
            self.assertEqual(len(pair), 2)
            for region in pair:
                self.assertIn(region, set(checks._BODY_REGIONS.values()))
        self.assertNotIn(frozenset(("hand", "head")), checks._ADJACENT_REGIONS)
        self.assertNotIn(frozenset(("arm", "leg")), checks._ADJACENT_REGIONS)

    def test_it_finds_the_real_defect_in_the_shipped_book(self):
        """Regression on the actual sequence, so a later change cannot quietly stop catching it."""
        found = checks.wandering_details(
            [_F("Kai", "a scar along his palm", s) for s in (15, 16, 46)]
            + [_F("Kai", "scar on arm", s) for s in (31, 32)]
            + [_F("Kai", "a scar running along his temple", s) for s in (40, 42, 56)])
        self.assertEqual(len(found), 1)
        self.assertEqual(sorted(found[0][2]), ["arm", "hand", "head"])
