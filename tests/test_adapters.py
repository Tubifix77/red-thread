"""Model adapter, Ollama discovery, and progress rendering.

None of these touch the network. The Ollama tests run against a canned `/api/tags` payload
matching the documented shape, because the field-name assumptions are the fragile part and a
future Ollama release is the thing that would break them.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import ollama
from redthread.llm import LLMError, parse_json, strip_reasoning
from redthread.models import Thread, ThreadKind
from redthread.progress import Progress, _Glyphs

# Shape per ollama/ollama docs/api.md, verified 2026-08-27.
TAGS_PAYLOAD = {
    "models": [
        {"model": "qwen3:8b", "name": "qwen3:8b", "size": 5_200_000_000,
         "details": {"parameter_size": "8.2B", "quantization_level": "Q4_K_M",
                     "family": "qwen3"}},
        {"model": "nomic-embed-text:latest", "size": 300_000_000,
         "details": {"parameter_size": "137M", "quantization_level": "F16",
                     "family": "nomic-bert"}},
        {"model": "phi4:14b", "size": 9_000_000_000,
         "details": {"parameter_size": "14.7B", "quantization_level": "Q4_K_M",
                     "family": "phi3"}},
    ]
}


class TestStripReasoning(unittest.TestCase):
    """Thinking models emit reasoning inline. Left in, it wrecks the word count, trips the
    format check, and lands in the manuscript."""

    def test_closed_block_removed(self):
        self.assertEqual(
            strip_reasoning("<think>plan the scene</think>\n\nOtto had the housing open."),
            "Otto had the housing open.")

    def test_thinking_variant_removed(self):
        self.assertEqual(strip_reasoning("<thinking>a</thinking>Prose."), "Prose.")

    def test_unclosed_leading_block_removed(self):
        """What a token limit cut mid-thought looks like."""
        self.assertEqual(
            strip_reasoning("<think>cut off and never closed\n\nOtto had the housing open."),
            "Otto had the housing open.")

    def test_stray_closing_tag_removed(self):
        self.assertEqual(strip_reasoning("Some prose.</think> More prose."),
                         "Some prose. More prose.")

    def test_plain_prose_untouched(self):
        text = "Otto had the intake housing open and both hands inside it."
        self.assertEqual(strip_reasoning(text), text)

    def test_angle_bracket_in_prose_survives(self):
        """A scene may legitimately contain angle brackets — a gauge reading, a part spec."""
        text = "She wrote <5 on the sheet and moved on."
        self.assertEqual(strip_reasoning(text), text)

    def test_mismatched_tags_are_not_greedily_eaten(self):
        """The backreference matters: `</\\1>`, not any closing tag."""
        text = "<think>reasoning</think>The valve read <2 bar</reason> after the reset."
        out = strip_reasoning(text)
        self.assertNotIn("reasoning", out)
        self.assertIn("<2 bar", out)


class TestParseJson(unittest.TestCase):
    """Local models wrap JSON in prose no matter how the prompt is worded."""

    def test_bare_json(self):
        self.assertEqual(parse_json('{"a": 1}'), {"a": 1})

    def test_fenced_json(self):
        self.assertEqual(parse_json('Sure!\n```json\n{"a": 1}\n```\nHope that helps.'),
                         {"a": 1})
        self.assertEqual(parse_json('```\n{"a": 1}\n```'), {"a": 1})

    def test_json_with_surrounding_prose(self):
        self.assertEqual(parse_json('Here you go: {"a": 1} — let me know.'), {"a": 1})

    def test_top_level_array(self):
        self.assertEqual(parse_json('Result:\n[1, 2, 3]'), [1, 2, 3])

    def test_unparseable_raises(self):
        with self.assertRaises(LLMError):
            parse_json("I'm sorry, I can't help with that.")


class TestOllamaDiscovery(unittest.TestCase):
    def test_parses_documented_payload(self):
        models = ollama.parse_tags(TAGS_PAYLOAD)
        self.assertEqual([m.name for m in models],
                         ["nomic-embed-text:latest", "qwen3:8b", "phi4:14b"])
        qwen = next(m for m in models if m.name == "qwen3:8b")
        self.assertEqual(qwen.parameter_size, "8.2B")
        self.assertEqual(qwen.quantization, "Q4_K_M")

    def test_sorted_smallest_first(self):
        sizes = [m.size_bytes for m in ollama.parse_tags(TAGS_PAYLOAD)]
        self.assertEqual(sizes, sorted(sizes))

    def test_missing_fields_tolerated(self):
        models = ollama.parse_tags({"models": [{"name": "bare:latest"}, "junk", {}]})
        self.assertEqual([m.name for m in models], ["bare:latest"])

    def test_empty_payload(self):
        self.assertEqual(ollama.parse_tags({}), [])

    def test_embedding_models_identified(self):
        models = {m.name: m for m in ollama.parse_tags(TAGS_PAYLOAD)}
        self.assertTrue(models["nomic-embed-text:latest"].is_embedding)
        self.assertFalse(models["qwen3:8b"].is_embedding)
        self.assertFalse(models["phi4:14b"].is_embedding)

    def test_fits_in_accounts_for_headroom(self):
        model = ollama.InstalledModel("m", size_bytes=int(8.9 * 1024 ** 3))
        self.assertFalse(model.fits_in(10.0))
        self.assertTrue(model.fits_in(10.0, headroom_gb=1.0))

    def test_native_base_strips_the_v1_suffix(self):
        self.assertEqual(ollama.native_base("http://localhost:11434/v1"),
                         "http://localhost:11434")
        self.assertEqual(ollama.native_base("http://localhost:11434/v1/"),
                         "http://localhost:11434")
        self.assertEqual(ollama.native_base("http://box:8080"), "http://box:8080")


class TestProgress(unittest.TestCase):
    def test_quiet_writes_nothing(self):
        stream = io.StringIO()
        p = Progress(total_scenes=3, quiet=True, stream=stream)
        p.run_header(_story(), "w", "c")
        self.assertEqual(stream.getvalue(), "")

    def test_bar_reflects_fraction(self):
        p = Progress(total_scenes=4, stream=io.StringIO())
        self.assertNotIn(p.g.full, p.bar(0.0))
        self.assertNotIn(p.g.empty, p.bar(1.0))

    def test_overall_reports_counts(self):
        p = Progress(total_scenes=10, scenes_done=3, words_done=3500, stream=io.StringIO())
        text = p.overall()
        self.assertIn("3/10 scenes", text)
        self.assertIn("3,500 words", text)
        self.assertIn("30.0%", text)

    def test_thread_bar_fills_to_current_state(self):
        p = Progress(stream=io.StringIO())
        thread = Thread(id="T", name="T", kind=ThreadKind.MAIN,
                        states=["a", "b", "c", "d"], current_state="b")
        rendered = p.thread_bar(thread)
        self.assertEqual(rendered.count(p.g.full), 2)
        self.assertEqual(rendered.count(p.g.empty), 2)

    def test_ascii_fallback_when_stream_cannot_encode(self):
        """Regression: UnicodeEncodeError subclasses ValueError, so a broad catch silently
        dropped every line with a block or tick glyph on a cp1252 console."""
        class Cp1252Stream(io.StringIO):
            encoding = "cp1252"

            def reconfigure(self, **kwargs):
                raise ValueError("cannot reconfigure")

        p = Progress(total_scenes=2, stream=Cp1252Stream())
        self.assertEqual(p.g, _Glyphs.for_stream(Cp1252Stream()))
        self.assertNotIn("█", p.bar(0.5))
        p.run_header(_story(), "w", "c")
        self.assertIn("Test Story", p.stream.getvalue())

    def test_unicode_glyphs_used_when_the_stream_can_encode(self):
        class Utf8Stream(io.StringIO):
            encoding = "utf-8"

        self.assertEqual(_Glyphs.for_stream(Utf8Stream()).full, "█")

    def test_summary_lists_every_thread(self):
        class Utf8Stream(io.StringIO):
            encoding = "utf-8"

        p = Progress(total_scenes=1, stream=Utf8Stream())
        p.summary(_story())
        out = p.stream.getvalue()
        self.assertIn("T-A", out)
        self.assertIn("T-B", out)


def _story():
    from redthread.models import StorySpec
    return StorySpec(title="Test Story", premise="p", threads=[
        Thread(id="T-A", name="Alpha", kind=ThreadKind.MAIN,
               states=["a", "b"], current_state="a"),
        Thread(id="T-B", name="Beta", kind=ThreadKind.SUBPLOT,
               states=["a", "b"], current_state="b"),
    ])


if __name__ == "__main__":
    unittest.main()
