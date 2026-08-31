"""The sentence sampler, and the blind it is built around.

Phase 5 of docs/PLAN.md. Almost every test here asserts an absence — that the sheet carries no
label, that the key is a separate object, that nothing is scored. The value of a hundred rated
sentences is entirely in the rater not knowing which side they are reading, and every convenience
that would break the blind is convenient in exactly the same way.
"""

from __future__ import annotations

import unittest

from redthread.sample import (blind_sheet, bootstrap_ci, correlate, draw, parse_key,
                              parse_ratings, render_key, render_sheet, restore_quotes,
                              sentence_signals, sentences_from)

from . import fakes


class TestSentencesFrom(unittest.TestCase):
    def test_pulls_whole_sentences(self):
        found = sentences_from(["The gauge read four inches. She wrote the number down."],
                               min_words=3)
        self.assertEqual(len(found), 2)
        self.assertTrue(found[0].startswith("The gauge"))

    def test_short_fragments_are_skipped_by_default(self):
        # "Gift?" is exchange, not craft. A rater asked whether they would read another page of
        # it has been asked nothing.
        found = sentences_from(["Gift? The relief driver had signed for it anyway, twice."])
        self.assertEqual(len(found), 1)

    def test_the_floor_can_be_lowered(self):
        found = sentences_from(["Gift? Recorded elsewhere?"], min_words=1)
        self.assertEqual(len(found), 2)

    def test_whitespace_is_normalised_but_wording_is_not_touched(self):
        found = sentences_from(["The  gauge\n  read four   inches exactly today."], min_words=3)
        self.assertEqual(found, ["The gauge read four inches exactly today."])

    def test_sentences_with_no_letters_are_dropped(self):
        self.assertEqual(sentences_from(["...  ", "1234567890 12345"], min_words=1), [])

    def test_reads_several_scenes(self):
        found = sentences_from([fakes.clean_prose(300), fakes.clean_prose(300, 1)])
        self.assertGreater(len(found), 10)


class TestDraw(unittest.TestCase):
    def test_draws_the_requested_number(self):
        self.assertEqual(len(draw([fakes.clean_prose(900)], 12)), 12)

    def test_is_deterministic_for_a_seed(self):
        texts = [fakes.clean_prose(900)]
        self.assertEqual(draw(texts, 8, seed=3), draw(texts, 8, seed=3))

    def test_different_seeds_draw_differently(self):
        texts = [fakes.clean_prose(900)]
        self.assertNotEqual(draw(texts, 8, seed=1), draw(texts, 8, seed=2))

    def test_draws_without_replacement(self):
        drawn = draw([fakes.clean_prose(900)], 20, seed=5)
        self.assertEqual(len(drawn), len(set(drawn)))

    def test_a_small_pool_returns_everything_rather_than_repeating(self):
        drawn = draw(["One sentence here, and it is long enough to count."], 30, min_words=3)
        self.assertEqual(len(drawn), 1)


class TestBlindSheet(unittest.TestCase):
    def _groups(self):
        # Labels chosen to be absent from the fixture prose. "before" and "after" both occur
        # in it, and a blind-leak test that matches ordinary English words fails on the prose
        # rather than on a leak.
        return [("ERAONE", [fakes.clean_prose(900)]),
                ("ERATWO", [fakes.clean_prose(900, 1)])]

    def test_draws_evenly_from_both_sides(self):
        sheet, key = blind_sheet(self._groups(), per_group=10)
        self.assertEqual(len(sheet), 20)
        self.assertEqual(sum(1 for _n, label, _s in key if label == "ERAONE"), 10)
        self.assertEqual(sum(1 for _n, label, _s in key if label == "ERATWO"), 10)

    def test_the_sheet_carries_no_label(self):
        sheet, _key = blind_sheet(self._groups(), per_group=10)
        rendered = render_sheet(sheet)
        self.assertNotIn("ERAONE", rendered)
        self.assertNotIn("ERATWO", rendered)

    def test_the_order_is_shuffled_rather_than_one_side_then_the_other(self):
        _sheet, key = blind_sheet(self._groups(), per_group=15, seed=7)
        labels = [label for _n, label, _s in key]
        self.assertNotEqual(labels, sorted(labels), "a sorted sheet is not a blind")

    def test_the_key_numbers_match_the_sheet_positions(self):
        sheet, key = blind_sheet(self._groups(), per_group=8)
        for number, _label, sentence in key:
            self.assertEqual(sheet[number - 1], sentence)

    def test_the_key_is_a_separate_object_from_the_sheet(self):
        # Structural, not cosmetic: the caller can only write them to one file by choosing to.
        sheet, key = blind_sheet(self._groups(), per_group=8)
        self.assertIsNot(sheet, key)
        self.assertNotIn("ERAONE", render_sheet(sheet))
        self.assertIn("ERAONE", render_key(key))

    def test_the_sheet_asks_one_question_and_offers_no_scores(self):
        sheet, _key = blind_sheet(self._groups(), per_group=4)
        rendered = render_sheet(sheet)
        self.assertIn("read another page", rendered)
        for banned in ("duplication", "gesture", "recap", "dialogue share"):
            self.assertNotIn(banned, rendered,
                             "showing the rater the panel produces a hundred confirmations "
                             "of what the panel already says")

    def test_every_line_has_a_box_to_fill_in(self):
        sheet, _key = blind_sheet(self._groups(), per_group=6)
        rendered = render_sheet(sheet)
        self.assertEqual(rendered.count("[ ]"), 12)

    def test_is_deterministic_for_a_seed(self):
        a, _ = blind_sheet(self._groups(), per_group=10, seed=4)
        b, _ = blind_sheet(self._groups(), per_group=10, seed=4)
        self.assertEqual(a, b)


class TestParseRatings(unittest.TestCase):
    def test_reads_a_filled_in_sheet(self):
        text = "[3]   1.  A sentence.\n[1]   2.  Another.\n[ ]   3.  Unrated.\n"
        self.assertEqual(parse_ratings(text), {1: 3, 2: 1})

    def test_unrated_lines_are_absent_rather_than_zero(self):
        # A zero would enter the arithmetic as the worst possible rating, which is not what an
        # unfilled box means.
        self.assertEqual(parse_ratings("[ ]   1.  A sentence.\n"), {})

    def test_ignores_the_preamble(self):
        sheet, _key = blind_sheet([("a", [fakes.clean_prose(400)])], per_group=3)
        self.assertEqual(parse_ratings(render_sheet(sheet)), {})

    def test_tolerates_spacing_inside_the_box(self):
        self.assertEqual(parse_ratings("[ 2 ]  7.  A sentence.\n"), {7: 2})


class TestSentenceSignals(unittest.TestCase):
    """The per-sentence half of the panel — the only half a rated sentence can test."""

    def test_reports_every_signal_for_any_sentence(self):
        signals = sentence_signals("The gauge read four inches and she wrote it down.")
        self.assertEqual(set(signals),
                         {"words", "spoken", "gesture", "somatic", "gloss", "slop",
                          "past_perfect"})

    def test_counts_words(self):
        self.assertEqual(sentence_signals("One two three four five.")["words"], 5.0)

    def test_sees_speech(self):
        self.assertEqual(sentence_signals('She said, "Go."')["spoken"], 1.0)
        self.assertEqual(sentence_signals("She told him to go.")["spoken"], 0.0)

    def test_sees_a_somatic_beat(self):
        self.assertEqual(sentence_signals("Her chest tightened.")["somatic"], 1.0)

    def test_sees_past_perfect(self):
        self.assertEqual(sentence_signals("She had counted the pages twice.")["past_perfect"],
                         1.0)
        self.assertEqual(sentence_signals("She counted the pages twice.")["past_perfect"], 0.0)

    def test_an_empty_sentence_does_not_crash(self):
        self.assertEqual(sentence_signals("")["words"], 0.0)


class TestCorrelate(unittest.TestCase):
    def test_a_perfect_line_is_one(self):
        self.assertAlmostEqual(correlate([1., 2., 3., 4.], [2., 4., 6., 8.]), 1.0)

    def test_a_perfect_inverse_is_minus_one(self):
        self.assertAlmostEqual(correlate([1., 2., 3., 4.], [8., 6., 4., 2.]), -1.0)

    def test_a_constant_signal_is_zero_rather_than_a_crash(self):
        # A signal identical on every rated sentence has told you nothing about any of them,
        # which is a different statement from "undefined" and the one worth printing.
        self.assertEqual(correlate([1., 1., 1., 1.], [1., 2., 3., 4.]), 0.0)

    def test_too_few_points_is_zero(self):
        self.assertEqual(correlate([1., 2.], [1., 2.]), 0.0)


class TestBootstrapCI(unittest.TestCase):
    def test_brackets_the_mean(self):
        values = [1.0, 2.0, 3.0] * 20
        lo, hi = bootstrap_ci(values, iterations=500)
        self.assertLess(lo, 2.0)
        self.assertGreater(hi, 2.0)

    def test_a_constant_sample_has_a_zero_width_interval(self):
        self.assertEqual(bootstrap_ci([2.0] * 30, iterations=200), (2.0, 2.0))

    def test_more_data_narrows_it(self):
        few = bootstrap_ci([1.0, 3.0] * 5, iterations=2000, seed=1)
        many = bootstrap_ci([1.0, 3.0] * 50, iterations=2000, seed=1)
        self.assertLess(many[1] - many[0], few[1] - few[0])

    def test_an_empty_sample_is_zero(self):
        self.assertEqual(bootstrap_ci([]), (0.0, 0.0))


class TestParseKey(unittest.TestCase):
    def test_round_trips_a_rendered_key(self):
        _sheet, key = blind_sheet([("ERAONE", [fakes.clean_prose(400)]),
                                   ("ERATWO", [fakes.clean_prose(400, 1)])], per_group=5)
        parsed = parse_key(render_key(key))
        self.assertEqual(len(parsed), 10)
        self.assertEqual({label for label, _kind in parsed.values()}, {"ERAONE", "ERATWO"})

    def test_records_the_speech_control(self):
        key = [(1, "A", 'She said, "Go."'), (2, "B", "She told him to go.")]
        parsed = parse_key(render_key(key))
        self.assertEqual(parsed[1][1], "spoken")
        self.assertEqual(parsed[2][1], "narrated")

    def test_ignores_the_preamble(self):
        self.assertEqual(parse_key("# Key — do not read before rating\n\nsome prose\n"), {})


class TestRestoreQuotes(unittest.TestCase):
    """The splitter eats a quotation mark; this puts it back. Restoration, not editing.

    It matters because the artefact tracks dialogue and the two sides of a sheet can differ in
    dialogue share by threefold — 10.9% of current-era sentences begin inside a quote against
    5.4% of the older ones. Left alone it biases a blind rating against exactly the prose the
    work was meant to improve, for a reason that is not the prose.
    """

    def test_a_sentence_that_begins_mid_speech_gets_its_opener_back(self):
        self.assertEqual(restore_quotes("You have nothing left to lose?” He did not look up."),
                         "“You have nothing left to lose?” He did not look up.")

    def test_a_sentence_that_opens_a_quote_and_never_closes_gets_its_closer(self):
        self.assertEqual(restore_quotes("“You don’t get to decide what happens to them."),
                         "“You don’t get to decide what happens to them.”")

    def test_a_balanced_sentence_is_untouched(self):
        line = "“Go,” she said, and he went."
        self.assertEqual(restore_quotes(line), line)

    def test_prose_with_no_speech_is_untouched(self):
        line = "The gauge read four inches and she wrote it down."
        self.assertEqual(restore_quotes(line), line)

    def test_it_changes_no_words(self):
        line = "You have nothing left to lose?” He did not look up."
        self.assertEqual(restore_quotes(line).replace("“", "").split(),
                         line.split())

    def test_two_complete_quotes_are_untouched(self):
        line = "“Go,” she said. “Now.”"
        self.assertEqual(restore_quotes(line), line)

    def test_it_runs_over_drawn_sentences(self):
        found = sentences_from(["She spoke. You have nothing left to lose?” He did not look up "
                                "at her from the bench."], min_words=3)
        self.assertTrue(any(s.startswith("“") for s in found), found)

    def test_a_straight_quoted_sentence_missing_its_opener(self):
        self.assertEqual(restore_quotes('You have nothing left to lose?"'),
                         '"You have nothing left to lose?"')

    def test_a_dialogue_tag_marks_the_quote_as_a_closer(self):
        # The shape the first pass missed. The mark sits mid-sentence, not at the end, but it is
        # preceded by a comma and followed by a tag — so it closes, and the opener is what went.
        self.assertEqual(
            restore_quotes('I know what you are asking," Vay said.'),
            '"I know what you are asking," Vay said.')

    def test_a_straight_quoted_sentence_missing_its_closer(self):
        self.assertEqual(restore_quotes('"You have nothing left to lose.'),
                         '"You have nothing left to lose."')

    def test_a_balanced_straight_quote_is_untouched(self):
        line = '"Go," she said, and he went.'
        self.assertEqual(restore_quotes(line), line)

    def test_a_quote_followed_by_a_letter_opens(self):
        # The mirror case: an opening mark with nothing closing it.
        self.assertEqual(restore_quotes('She said "go and he went on for a while.'),
                         'She said "go and he went on for a while."')

    def test_an_ambiguous_straight_quote_is_left_alone(self):
        # Neither shape: the mark is preceded by a space and followed by a space, so nothing
        # about it says which job it was doing. Guessing here would edit the prose.
        line = 'The sign read the word " and nothing else at all was printed on it.'
        self.assertEqual(restore_quotes(line), line)

    def test_straight_quotes_change_no_words(self):
        line = 'You have nothing left to lose?"'
        self.assertEqual(restore_quotes(line).replace('"', "").split(),
                         line.replace('"', "").split())


class TestBootstrapDegenerate(unittest.TestCase):
    def test_no_iterations_returns_zero_rather_than_indexing_an_empty_list(self):
        self.assertEqual(bootstrap_ci([1.0, 2.0], iterations=0), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
