"""Deterministic checks must catch injected defects, not merely pass clean prose.

A check that never fires is indistinguishable from a check that does not work, so every test
here injects the specific defect the check exists to find and asserts it comes back.
"""

from __future__ import annotations

import unittest

from redthread import checks
from redthread.models import (Beat, Character, Scene, SceneSpec, Severity, StorySpec,
                              StyleContract, Transition)


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
