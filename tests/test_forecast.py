"""Embeddings, and the forecast experiment kept where it can be repeated.

Phase 2 of docs/PLAN.md. The through-line of these tests is the control: this project has twice
built a measure on shared vocabulary, twice produced a distribution that looked entirely
reasonable on its own, and twice found it was measuring the book's furniture. So `score` computes
the control in the same pass as the result, and there is a test here asserting that a scorer
which ignores its input reports chance rather than a number.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from redthread.embed import Embedder, cosine
from redthread.forecast import (Prediction, generate, lexical_scorer, load, prediction_spread,
                                sample_scenes, save, score, semantic_scorer, story_so_far)

from . import fakes


class FakeEmbedder(Embedder):
    """Deterministic vectors from the words in a text, with no network.

    A bag-of-words vector is a poor embedding and a perfectly good test double: it is stable,
    it puts similar texts near each other, and it makes the arithmetic checkable by hand.
    """

    def __init__(self):
        super().__init__(model="fake", cache_dir=None)
        self.fetched: list[str] = []

    def _fetch(self, texts):
        self.fetched.extend(texts)
        out = []
        for text in texts:
            vector = [0.0] * 26
            for char in text.lower():
                if "a" <= char <= "z":
                    vector[ord(char) - 97] += 1.0
            out.append(vector)
        return out


class TestCosine(unittest.TestCase):
    def test_identical_vectors_are_one(self):
        self.assertAlmostEqual(cosine([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)

    def test_orthogonal_vectors_are_zero(self):
        self.assertAlmostEqual(cosine([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_scale_does_not_matter(self):
        self.assertAlmostEqual(cosine([1.0, 2.0], [3.0, 6.0]), 1.0)

    def test_a_zero_vector_is_zero_rather_than_a_crash(self):
        self.assertEqual(cosine([0.0, 0.0], [1.0, 1.0]), 0.0)

    def test_mismatched_lengths_are_zero(self):
        self.assertEqual(cosine([1.0], [1.0, 2.0]), 0.0)


class TestEmbedderCache(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_a_repeat_is_served_from_memory(self):
        embedder = FakeEmbedder()
        embedder.embed(["the harbour"])
        embedder.embed(["the harbour"])
        self.assertEqual(len(embedder.fetched), 1)
        self.assertEqual(embedder.cached, 1)

    def test_only_the_misses_are_fetched(self):
        embedder = FakeEmbedder()
        embedder.embed(["one", "two"])
        embedder.embed(["two", "three"])
        self.assertEqual(embedder.fetched, ["one", "two", "three"])

    def test_the_disk_cache_survives_a_new_embedder(self):
        cache = Path(self._tmp.name)
        first = FakeEmbedder()
        first.cache_dir = cache
        first.embed(["the harbour"])
        second = FakeEmbedder()
        second.cache_dir = cache
        second.embed(["the harbour"])
        self.assertEqual(second.fetched, [], "the second embedder should have hit the cache")

    def test_the_cache_key_includes_the_model(self):
        # Otherwise switching embedding model silently reads another model's vectors, and every
        # cosine after that is between two different vector spaces — a number that looks exactly
        # like a measurement.
        cache = Path(self._tmp.name)
        first = FakeEmbedder()
        first.cache_dir = cache
        first.embed(["the harbour"])
        second = FakeEmbedder()
        second.model = "a-different-model"
        second.cache_dir = cache
        second.embed(["the harbour"])
        self.assertEqual(second.fetched, ["the harbour"])

    def test_order_is_preserved_across_a_mixed_batch(self):
        embedder = FakeEmbedder()
        embedder.embed(["aaa"])
        vectors = embedder.embed(["bbb", "aaa", "ccc"])
        self.assertAlmostEqual(cosine(vectors[1], embedder.one("aaa")), 1.0)
        self.assertLess(cosine(vectors[0], vectors[2]), 0.5)

    def test_similarity_reads_both_sides(self):
        embedder = FakeEmbedder()
        self.assertAlmostEqual(embedder.similarity("abc", "abc"), 1.0)


class TestSampleScenes(unittest.TestCase):
    def test_skips_the_opening(self):
        # A prediction from a context of nothing is a prediction about the premise, and scoring
        # it measures how well the premise describes its own first chapter.
        self.assertNotIn(0, sample_scenes(40, 10))
        self.assertGreaterEqual(min(sample_scenes(40, 10)), 4)

    def test_returns_the_requested_number(self):
        self.assertEqual(len(sample_scenes(71, 35)), 35)

    def test_asking_for_more_than_exist_returns_what_exists(self):
        self.assertEqual(sample_scenes(10, 50), list(range(4, 10)))

    def test_a_short_book_returns_nothing_rather_than_a_crash(self):
        self.assertEqual(sample_scenes(3, 10), [])

    def test_spreads_across_the_book(self):
        drawn = sample_scenes(71, 10)
        self.assertLess(drawn[0], 15)
        self.assertGreater(drawn[-1], 55)


class TestStorySoFar(unittest.TestCase):
    def test_uses_the_last_few_scenes_only(self):
        texts = [f"scene {i} " + "x" * 100 for i in range(10)]
        context = story_so_far(texts, scenes=3)
        self.assertIn("scene 9", context)
        self.assertNotIn("scene 5", context)

    def test_an_empty_book_gives_an_empty_context(self):
        self.assertEqual(story_so_far([]), "")


class TestScoreAndControl(unittest.TestCase):
    """Every scorer is measured against something it has no business matching."""

    def _predictions(self, n=12):
        return [Prediction(index=i, context="c", predictions=[f"prediction about scene {i}"])
                for i in range(n)]

    def _texts(self, n=12):
        return [f"prediction about scene {i} " + fakes.clean_prose(120, i % 4)
                for i in range(n)]

    def test_a_scorer_that_works_wins(self):
        result = score(self._predictions(), self._texts(), lexical_scorer, "lexical")
        self.assertGreater(result.win_rate, 0.8)
        self.assertGreater(result.on_target, result.on_control)

    def test_a_scorer_that_ignores_its_input_reports_chance(self):
        # The shape of the failure this whole module is built around: a constant scorer has a
        # perfectly reasonable-looking mean and a win rate of zero.
        result = score(self._predictions(), self._texts(), lambda g, s: 0.5, "constant")
        self.assertEqual(result.win_rate, 0.0)
        self.assertEqual(result.on_target, result.on_control)
        self.assertIn("CHANCE", result.verdict())

    def test_the_control_uses_a_different_scene(self):
        seen = []

        def spy(guess, scene):
            seen.append(scene)
            return 0.5
        score(self._predictions(3), self._texts(3), spy, "spy")
        self.assertEqual(len(seen), 6, "one real and one control score per prediction")

    def test_a_semantic_scorer_runs_through_the_embedder(self):
        embedder = FakeEmbedder()
        result = score(self._predictions(), self._texts(), semantic_scorer(embedder), "semantic")
        self.assertGreater(embedder.calls, 0)
        self.assertEqual(result.n, 12)

    def test_predictions_with_no_guess_are_skipped(self):
        predictions = [Prediction(index=0, context="c", predictions=[]),
                       Prediction(index=1, context="c", predictions=["a guess"])]
        self.assertEqual(score(predictions, self._texts(4), lexical_scorer, "l").n, 1)

    def test_a_prediction_past_the_end_of_the_book_is_skipped(self):
        predictions = [Prediction(index=99, context="c", predictions=["a guess"])]
        self.assertEqual(score(predictions, self._texts(4), lexical_scorer, "l").n, 0)

    def test_too_few_predictions_says_so_rather_than_reporting_a_rate(self):
        result = score(self._predictions(3), self._texts(4), lexical_scorer, "l")
        self.assertIn("too few", result.verdict())

    def test_the_verdict_bar_is_the_one_the_plan_names(self):
        result = score(self._predictions(), self._texts(), lexical_scorer, "l")
        result.win_rate = 0.60
        self.assertIn("below", result.verdict(0.65))
        result.win_rate = 0.70
        self.assertEqual(result.verdict(0.65), "clears the bar")

    def test_the_control_is_deterministic_for_a_seed(self):
        a = score(self._predictions(), self._texts(), lexical_scorer, "l", seed=3)
        b = score(self._predictions(), self._texts(), lexical_scorer, "l", seed=3)
        self.assertEqual(a.on_control, b.on_control)


class TestPredictionSpread(unittest.TestCase):
    """Step 12 — the one measure here that never looks at the actual scene."""

    def test_identical_guesses_have_no_spread(self):
        prediction = Prediction(index=1, context="c", predictions=["same words", "same words"])
        self.assertAlmostEqual(prediction_spread(prediction, FakeEmbedder()), 0.0)

    def test_different_guesses_spread(self):
        prediction = Prediction(index=1, context="c",
                                predictions=["aaaa bbbb", "wwww xxxx yyyy"])
        self.assertGreater(prediction_spread(prediction, FakeEmbedder()), 0.3)

    def test_one_guess_has_no_spread_to_measure(self):
        prediction = Prediction(index=1, context="c", predictions=["only one"])
        self.assertEqual(prediction_spread(prediction, FakeEmbedder()), 0.0)

    def test_it_never_reads_the_scene(self):
        # The property that makes step 12 worth trying after two failures: a measure that never
        # sees the scene cannot be confounded by the book's shared vocabulary.
        import inspect
        source = inspect.getsource(prediction_spread)
        self.assertNotIn("texts", source)
        self.assertNotIn("scene_text", source)


class TestPersistence(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_round_trips(self):
        path = Path(self._tmp.name) / "forecast.json"
        original = [Prediction(index=4, context="the story so far", predictions=["a", "b"])]
        save(original, path)
        self.assertEqual(load(path), original)

    def test_the_context_is_stored_with_the_prediction(self):
        # So a re-score cannot silently change what the model was shown. The first calibration
        # of this idea kept nothing, which is why the plan's "free re-score" was not free.
        path = Path(self._tmp.name) / "forecast.json"
        save([Prediction(index=4, context="the story so far", predictions=["a"])], path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(raw[0]["context"], "the story so far")


class TestGenerate(unittest.TestCase):
    def test_asks_the_critic_once_per_scene(self):
        models, backend = fakes.scripted_models(
            {"forecast": json.dumps({"prediction": "She returns the ledger."})})
        texts = [fakes.clean_prose(150, i % 4) for i in range(12)]
        predictions = generate(texts, models, wanted=5)
        self.assertEqual(len(predictions), 5)
        self.assertEqual(backend.count("forecast"), 5)

    def test_k_asks_k_times(self):
        models, backend = fakes.scripted_models(
            {"forecast": json.dumps({"prediction": "She returns the ledger."})})
        texts = [fakes.clean_prose(150, i % 4) for i in range(12)]
        generate(texts, models, wanted=3, k=4, temperature=0.9)
        self.assertEqual(backend.count("forecast"), 12)

    def test_a_scene_with_no_usable_reply_is_dropped_rather_than_stored_empty(self):
        models, backend = fakes.scripted_models({"forecast": "not json at all"})
        texts = [fakes.clean_prose(150, i % 4) for i in range(12)]
        self.assertEqual(generate(texts, models, wanted=5), [])

    def test_the_context_shown_is_the_story_before_that_scene(self):
        models, backend = fakes.scripted_models(
            {"forecast": json.dumps({"prediction": "x"})})
        texts = [f"SCENE{i} " + fakes.clean_prose(150, i % 4) for i in range(12)]
        predictions = generate(texts, models, wanted=1)
        target = predictions[0].index
        self.assertNotIn(f"SCENE{target}", predictions[0].context,
                         "the prediction must be blind to the scene it is predicting")


if __name__ == "__main__":
    unittest.main()
