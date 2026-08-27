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

    def test_truncated_json_is_salvaged(self):
        """Not an edge case with local models: a real extraction spent its whole 8000-token
        budget enumerating 258 facts and was cut off mid-object. Discarding it threw away every
        complete fact along with the broken tail."""
        truncated = ('{"facts": [{"subject": "Siv", "predicate": "has", "object": "a notebook", '
                     '"kind": "detail"}, {"subject": "Otto", "predicate": "is", "object": '
                     '"maintenance chief", "kind": "state"}, {"subject": "the door", "predi')
        data = parse_json(truncated)
        self.assertEqual(len(data["facts"]), 2)
        self.assertEqual(data["facts"][0]["subject"], "Siv")

    def test_truncated_top_level_array_is_salvaged(self):
        data = parse_json('[{"a": 1}, {"b": 2}, {"c": ')
        self.assertEqual(data, [{"a": 1}, {"b": 2}])

    def test_salvage_ignores_brackets_inside_strings(self):
        """A closing brace inside a fact's text must not be mistaken for structure."""
        data = parse_json('{"facts": [{"object": "a note reading }] end"}, {"object": "cut')
        self.assertEqual(data["facts"], [{"object": "a note reading }] end"}])

    def test_a_prefix_ending_inside_a_string_is_not_guessed_at(self):
        with self.assertRaises(LLMError):
            parse_json('{"facts": [{"subject": "an unterminated stri')

    def test_complete_json_is_not_touched_by_salvage(self):
        self.assertEqual(parse_json('{"facts": [{"a": 1}]}'), {"facts": [{"a": 1}]})


class TestOllamaBackend(unittest.TestCase):
    """Request construction against the documented `/api/chat` shape, with no network call.

    This backend exists because the OpenAI-compatible shim cost real debugging time: `think` is
    not documented as supported there, and reasoning arrives inline in the content where it
    silently destroyed fact extraction.
    """

    def setUp(self):
        from redthread import llm
        self.sent = []

        def fake_send(request, timeout, retries):
            self.sent.append(json.loads(request.data.decode("utf-8")))
            return {"model": "m", "message": {"role": "assistant",
                                             "thinking": "reasoning that must not leak",
                                             "content": "the answer"},
                    "prompt_eval_count": 11, "eval_count": 22}

        self._original = llm._send
        llm._send = fake_send
        self.llm = llm

    def tearDown(self):
        self.llm._send = self._original

    def backend(self, **kwargs):
        return self.llm.OllamaBackend("qwen3:8b", **kwargs)

    def test_posts_to_the_native_chat_endpoint(self):
        self.backend().complete("hello")
        self.assertEqual(self.sent[0]["model"], "qwen3:8b")
        self.assertFalse(self.sent[0]["stream"])

    def test_thinking_is_off_by_default(self):
        self.backend().complete("hello")
        self.assertIs(self.sent[0]["think"], False)

    def test_thinking_can_be_enabled_or_set_to_an_effort(self):
        self.backend(think=True).complete("hello")
        self.backend(think="high").complete("hello")
        self.assertIs(self.sent[0]["think"], True)
        self.assertEqual(self.sent[1]["think"], "high")

    def test_think_none_omits_the_field_entirely(self):
        self.backend(think=None).complete("hello")
        self.assertNotIn("think", self.sent[0])

    def test_temperature_and_token_limit_go_in_options(self):
        self.backend().complete("hello", max_tokens=1234, temperature=0.25)
        options = self.sent[0]["options"]
        self.assertEqual(options["num_predict"], 1234)
        self.assertEqual(options["temperature"], 0.25)

    def test_json_mode_sets_the_format_field(self):
        self.backend().complete("hello", json_mode=True)
        self.backend().complete("hello")
        self.assertEqual(self.sent[0]["format"], "json")
        self.assertNotIn("format", self.sent[1])

    def test_system_prompt_becomes_a_system_message(self):
        self.backend().complete("hello", system="be terse")
        roles = [m["role"] for m in self.sent[0]["messages"]]
        self.assertEqual(roles, ["system", "user"])

    def test_the_thinking_field_is_discarded(self):
        """The whole point: reasoning must not reach the caller."""
        reply = self.backend().complete("hello")
        self.assertEqual(reply.text, "the answer")
        self.assertNotIn("reasoning that must not leak", reply.text)

    def test_token_counts_are_read_from_the_native_field_names(self):
        reply = self.backend().complete("hello")
        self.assertEqual((reply.input_tokens, reply.output_tokens), (11, 22))

    def test_an_openai_style_base_url_is_accepted(self):
        """Every other part of the CLI passes the /v1 URL around."""
        backend = self.llm.OllamaBackend("m", base_url="http://localhost:11434/v1")
        self.assertEqual(backend.base_url, "http://localhost:11434")

    def test_all_local_uses_the_native_backend_with_thinking_off(self):
        models = self.llm.Models.all_local("qwen3:8b")
        for role in (models.writer, models.critic, models.extractor):
            self.assertIsInstance(role, self.llm.OllamaBackend)
            self.assertIs(role.think, False)

    def test_all_local_can_fall_back_to_openai_compat(self):
        models = self.llm.Models.all_local("qwen3:8b", native=False)
        self.assertIsInstance(models.writer, self.llm.OpenAICompatBackend)

    def test_structured_roles_keep_thinking_off_even_when_the_writer_has_it_on(self):
        models = self.llm.Models.all_local("qwen3:8b", think_writer="high")
        self.assertEqual(models.writer.think, "high")
        self.assertIs(models.critic.think, False)
        self.assertIs(models.extractor.think, False)


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
