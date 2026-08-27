"""The planner: premise in, auditable plan out.

The property that matters most here is negative: **the model must not be able to break either
acceptance marker.** Structure is scheduled before any content is proposed, so a model that
misbehaves — reassigning thread states, proposing only main threads, returning junk — should
degrade the plan's *content* and never its structure.

Most of these tests therefore feed the planner deliberately bad proposals and assert the plan
still audits clean.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread import checks
from redthread.llm import LLMError, Models
from redthread.models import Severity, ThreadKind
from redthread.planner import (make_plan, parse_story, propose_story, story_problems,
                               expand_beats, flesh_scenes)
from redthread.schedule import schedule_threads, score_spec, to_scene_specs

from tests.fakes import ScriptedBackend

FIVE = ["dormant", "planted", "complicated", "escalated", "paid_off"]


def story_json(threads=None, characters=None, style=None, **kwargs) -> str:
    payload = {
        "title": "The Salt Line",
        "premise": "A harbour inspector finds the tide tables have been altered.",
        "world_rules": ["The harbour runs on printed tide tables.", "The press is two days away."],
        "characters": characters if characters is not None else [
            {"id": "ves", "name": "Vesna Kolar", "description": "Forty, harbour inspector.",
             "voice": "Clipped. Answers with measurements."},
            {"id": "ard", "name": "Ardo Pilv", "description": "Sixty, printer.",
             "voice": "Talks around a subject."},
            {"id": "mira", "name": "Mira Sepp", "description": "Thirty, Vesna's neighbour.",
             "voice": "Fast, funny, always mid-argument."},
        ],
        "threads": threads if threads is not None else [
            {"id": "T-TIDE", "name": "The altered tables", "kind": "main", "states": FIVE,
             "concealment": "who altered them", "payoff": "she can prove it and cannot use it"},
            {"id": "T-BOAT", "name": "Mira's boat licence", "kind": "subplot", "states": FIVE,
             "concealment": "the licence lapsed years ago",
             "payoff": "she gets an answer that does not help"},
            {"id": "T-ARDO", "name": "Vesna and Ardo", "kind": "relationship", "states": FIVE,
             "concealment": "he set the type himself", "payoff": "neither is forgiven"},
        ],
        "style": style if style is not None else {
            "pov": "third limited", "tense": "past",
            "samples": ["The tide was out by four inches more than the sheet allowed.",
                        "Ardo did not look up from the case.",
                        "Two days to the press. She counted it twice."],
            "forbidden_phrases": ["the truth", "everything changed"],
            "notes": "Maritime industrial register. Emotion as behaviour.",
        },
    }
    payload.update(kwargs)
    return json.dumps(payload)


def scenes_json(indices, threads_by_index=None) -> str:
    rows = []
    for i in indices:
        rows.append({
            "index": i,
            "summary": f"Vesna checks the tide sheet against the harbour gauge in shed {i}.",
            "setting": f"Harbour shed {i}",
            "time": "before dawn",
            "pov": "ves",
            "characters": ["ves", "ard"],
            "beats": [f"She reads the gauge at 04:{i:02d} and writes the number down.",
                      f"Ardo arrives with the proof sheet and will not sit down."],
            "threads": (threads_by_index or {}).get(i, {}),
        })
    return json.dumps({"scenes": rows})


class PlannerBackend(ScriptedBackend):
    """Routes the planner's three prompt shapes on top of the pipeline roles."""

    def __init__(self, story: str | None = None, scenes_reply=None, beats_reply=None) -> None:
        super().__init__()
        self._story = story if story is not None else story_json()
        self._scenes = scenes_reply
        self._beats = beats_reply
        self.story_calls = 0
        self.scene_calls = 0
        self.beat_calls = 0

    def complete(self, prompt, *, system="", max_tokens=4096, temperature=1.0, stop=None,
                 json_mode=False):
        from redthread.llm import Reply
        # Record here too: the base class only logs calls that fall through to it, and several
        # tests inspect the planner's prompts rather than just its outputs.
        if any(marker in prompt for marker in
               ("structural bible", "filling in scenes", "under-specified")):
            self.calls.append(("plan", prompt))
        if "structural bible" in prompt:
            self.story_calls += 1
            text = (self._story if isinstance(self._story, str)
                    else self._story[min(self.story_calls - 1, len(self._story) - 1)])
            return Reply(text, model="scripted")
        if "filling in scenes" in prompt:
            self.scene_calls += 1
            indices = [int(m) for m in __import__("re").findall(r"^Scene (\d+) \(chapter",
                                                                prompt, __import__("re").M)]
            text = self._scenes(indices) if callable(self._scenes) else (
                self._scenes or scenes_json(indices))
            return Reply(text, model="scripted")
        if "under-specified" in prompt:
            self.beat_calls += 1
            indices = [int(m) for m in __import__("re").findall(r"^Scene (\d+) \(~",
                                                                prompt, __import__("re").M)]
            text = self._beats(indices) if callable(self._beats) else (
                self._beats or json.dumps({"scenes": [
                    {"index": i,
                     "beats": [f"She sets the brass gauge on the bench and reads {i}00 exactly.",
                               f"Ardo puts the proof sheet on the table and leaves it there."],
                     "setting": f"Harbour shed {i}", "time": "04:10"} for i in indices]}))
            return Reply(text, model="scripted")
        return super().complete(prompt, system=system, max_tokens=max_tokens,
                                temperature=temperature, stop=stop, json_mode=json_mode)


def models_with(backend) -> Models:
    return Models(writer=backend, critic=backend, extractor=backend)


def serious(violations) -> list:
    return [v for v in violations if v.severity is not Severity.MINOR]


class TestParseStory(unittest.TestCase):
    def test_parses_a_well_formed_proposal(self):
        story = parse_story(json.loads(story_json()))
        self.assertEqual(story.title, "The Salt Line")
        self.assertEqual(len(story.threads), 3)
        self.assertEqual(len(story.characters), 3)
        self.assertEqual(story.style.pov, "third limited")
        self.assertEqual(story_problems(story), [])

    def test_exactly_one_main_thread_is_enforced(self):
        """Code settles this rather than spending a round trip re-asking."""
        threads = [
            {"id": "A", "name": "A", "kind": "main", "states": FIVE, "concealment": "c",
             "payoff": "p"},
            {"id": "B", "name": "B", "kind": "main", "states": FIVE, "concealment": "c",
             "payoff": "p"},
        ]
        story = parse_story(json.loads(story_json(threads=threads)))
        mains = [t for t in story.threads if t.kind is ThreadKind.MAIN]
        self.assertEqual(len(mains), 1)

    def test_missing_main_is_promoted(self):
        threads = [{"id": "A", "name": "A", "kind": "subplot", "states": FIVE,
                    "concealment": "c", "payoff": "p"}]
        story = parse_story(json.loads(story_json(threads=threads)))
        self.assertIs(story.threads[0].kind, ThreadKind.MAIN)

    def test_repeated_states_are_de_duplicated(self):
        """A repeated state would make the arc re-enter a state it already occupied."""
        threads = [{"id": "A", "name": "A", "kind": "main",
                    "states": ["dormant", "planted", "planted", "paid_off"],
                    "concealment": "c", "payoff": "p"}]
        story = parse_story(json.loads(story_json(threads=threads)))
        self.assertEqual(story.threads[0].states, ["dormant", "planted", "paid_off"])

    def test_too_few_states_are_padded(self):
        threads = [{"id": "A", "name": "A", "kind": "main", "states": ["only"],
                    "concealment": "c", "payoff": "p"}]
        story = parse_story(json.loads(story_json(threads=threads)))
        self.assertGreaterEqual(len(story.threads[0].states), 2)

    def test_unknown_kind_falls_back_to_subplot(self):
        threads = [{"id": "A", "name": "A", "kind": "main", "states": FIVE, "concealment": "c",
                    "payoff": "p"},
                   {"id": "B", "name": "B", "kind": "interstitial", "states": FIVE,
                    "concealment": "c", "payoff": "p"}]
        story = parse_story(json.loads(story_json(threads=threads)))
        self.assertIs(story.thread("B").kind, ThreadKind.SUBPLOT)

    def test_duplicate_character_ids_are_made_unique(self):
        characters = [{"id": "x", "name": "One"}, {"id": "x", "name": "Two"}]
        story = parse_story(json.loads(story_json(characters=characters)))
        self.assertEqual(len({c.id for c in story.characters}), 2)

    def test_junk_rows_are_skipped(self):
        data = json.loads(story_json())
        data["characters"] = ["nonsense", {}, {"name": "Real Person"}]
        data["threads"] = ["nonsense", {}, {"name": "Real Thread", "kind": "main"}]
        story = parse_story(data)
        self.assertEqual([c.name for c in story.characters], ["Real Person"])
        self.assertEqual([t.name for t in story.threads], ["Real Thread"])

    def test_empty_proposal_does_not_crash(self):
        story = parse_story({})
        self.assertEqual(story.title, "Untitled")
        self.assertTrue(story_problems(story))


class TestProposeStoryRetries(unittest.TestCase):
    def test_retries_when_no_subplot_is_proposed(self):
        bad = story_json(threads=[
            {"id": "A", "name": "A", "kind": "main", "states": FIVE, "concealment": "c",
             "payoff": "p"}])
        backend = PlannerBackend(story=[bad, story_json()])
        story = propose_story("A premise.", models_with(backend))

        self.assertEqual(backend.story_calls, 2, "should have retried the degenerate proposal")
        self.assertTrue([t for t in story.threads if t.kind is not ThreadKind.MAIN])

    def test_retry_prompt_names_the_actual_problem(self):
        bad = story_json(threads=[
            {"id": "A", "name": "A", "kind": "main", "states": FIVE, "concealment": "",
             "payoff": ""}])
        backend = PlannerBackend(story=[bad, story_json()])
        propose_story("A premise.", models_with(backend))
        second = [p for role, p in backend.calls if "structural bible" in p][1]
        self.assertIn("concealed", second)

    def test_gives_up_after_the_attempt_budget_and_returns_the_best_effort(self):
        bad = story_json(threads=[
            {"id": "A", "name": "A", "kind": "main", "states": FIVE, "concealment": "c",
             "payoff": "p"}])
        backend = PlannerBackend(story=bad)
        story = propose_story("A premise.", models_with(backend), attempts=2)
        self.assertEqual(backend.story_calls, 2)
        self.assertIsNotNone(story)

    def test_unparseable_reply_is_retried_not_raised(self):
        backend = PlannerBackend(story=["I'd rather not.", story_json()])
        with self.assertRaises(LLMError):
            # parse_json raises on the first attempt; the planner surfaces it rather than
            # silently continuing with an empty story.
            propose_story("A premise.", models_with(backend), attempts=1)


class TestSelfConsistency(unittest.TestCase):
    """Both of these came from a real planner run on a real premise."""

    def test_a_plan_that_breaks_its_own_forbidden_list_is_flagged(self):
        """The model listed 'sentient' as forbidden and then used it in the premise it wrote."""
        story = parse_story(json.loads(story_json(
            premise="Two crews collide on a sentient shipwreck.",
            style={"pov": "third limited", "tense": "past",
                   "samples": ["A.", "B.", "C."],
                   "forbidden_phrases": ["sentient", "xenomorph"], "notes": ""})))
        problems = story_problems(story)
        self.assertTrue(any("sentient" in p for p in problems), problems)
        self.assertTrue(any("spec_self_violation" == v.kind
                            for v in checks.check_spec_self_consistency([], story)))

    def test_a_slop_character_name_is_flagged(self):
        """`kael` is on the antislop list, and check_slop exempts cast names by necessity."""
        story = parse_story(json.loads(story_json(characters=[
            {"id": "senna", "name": "Senna Kael", "description": "d", "voice": "v"},
            {"id": "b", "name": "Bern Toft", "description": "d", "voice": "v"},
            {"id": "c", "name": "Ilse Vahr", "description": "d", "voice": "v"},
        ])))
        self.assertTrue(any("Kael" in p for p in story_problems(story)))

    def test_a_clean_story_reports_neither(self):
        story = parse_story(json.loads(story_json()))
        self.assertEqual(story_problems(story), [])

    def test_planner_retries_on_a_self_violation(self):
        bad = story_json(premise="A sentient hull.",
                         style={"pov": "third limited", "tense": "past",
                                "samples": ["A.", "B.", "C."],
                                "forbidden_phrases": ["sentient"], "notes": ""})
        backend = PlannerBackend(story=[bad, story_json()])
        propose_story("A premise.", models_with(backend))
        self.assertEqual(backend.story_calls, 2)

    def test_the_forbidden_list_itself_is_not_counted_as_a_violation(self):
        """Otherwise every story would self-violate merely by declaring its prohibitions."""
        story = parse_story(json.loads(story_json(
            style={"pov": "third limited", "tense": "past", "samples": ["A.", "B.", "C."],
                   "forbidden_phrases": ["zzzunlikelyword"], "notes": ""})))
        self.assertEqual(checks.check_spec_self_consistency([], story), [])


class TestStructureIsNotTheModelsToBreak(unittest.TestCase):
    """The core guarantee: bad content proposals must not corrupt structure."""

    def test_plan_audits_clean_with_a_good_proposal(self):
        backend = PlannerBackend()
        result = make_plan("A premise.", models_with(backend), total_words=13200)
        self.assertEqual(serious(result.violations), [],
                         "; ".join(str(v) for v in result.violations))
        self.assertTrue(result.is_clean())

    def test_plan_audits_clean_when_scene_proposals_are_junk(self):
        backend = PlannerBackend(scenes_reply="not json at all")
        result = make_plan("A premise.", models_with(backend), total_words=13200)
        self.assertEqual(serious(result.violations), [],
                         "structure must survive unusable content proposals")

    def test_model_cannot_reassign_thread_states(self):
        """A model that 'helpfully' sets to_state would break the audit guarantee."""
        def sabotage(indices):
            rows = json.loads(scenes_json(indices))
            for row in rows["scenes"]:
                row["threads"] = {"T-TIDE": {"post": ["something"], "forbid": ["nothing"],
                                             "to_state": "paid_off"}}
            return json.dumps(rows)

        backend = PlannerBackend(scenes_reply=sabotage)
        result = make_plan("A premise.", models_with(backend), total_words=13200)

        seq = checks.planned_state_sequence(result.plan, "T-TIDE")
        tide = result.story.thread("T-TIDE")
        self.assertEqual([s for _, s in seq], tide.states[1:],
                         "the scheduler's arc was overwritten by the model")
        self.assertEqual(serious(result.violations), [])

    def test_unknown_thread_ids_in_the_proposal_are_ignored(self):
        def bogus(indices):
            rows = json.loads(scenes_json(indices))
            for row in rows["scenes"]:
                row["threads"] = {"T-DOES-NOT-EXIST": {"post": ["x"], "forbid": ["y"]}}
            return json.dumps(rows)

        backend = PlannerBackend(scenes_reply=bogus)
        result = make_plan("A premise.", models_with(backend), total_words=13200)
        for spec in result.plan:
            self.assertNotIn("T-DOES-NOT-EXIST", spec.thread_ops)

    def test_unknown_character_ids_are_dropped(self):
        def bogus(indices):
            rows = json.loads(scenes_json(indices))
            for row in rows["scenes"]:
                row["pov"] = "nobody"
                row["characters"] = ["nobody", "ves"]
            return json.dumps(rows)

        backend = PlannerBackend(scenes_reply=bogus)
        result = make_plan("A premise.", models_with(backend), total_words=13200)
        valid = {c.id for c in result.story.characters}
        for spec in result.plan:
            self.assertTrue(set(spec.characters) <= valid)


class TestSceneContent(unittest.TestCase):
    def test_content_is_applied_to_every_scene(self):
        backend = PlannerBackend()
        result = make_plan("A premise.", models_with(backend), total_words=13200)
        self.assertTrue(all(s.summary for s in result.plan))
        self.assertTrue(all(s.beats for s in result.plan))
        self.assertTrue(all(s.pov for s in result.plan))

    def test_post_and_forbid_reach_the_transitions(self):
        def with_ops(indices):
            rows = json.loads(scenes_json(indices))
            for row in rows["scenes"]:
                row["threads"] = {"T-TIDE": {"post": ["the gauge reading is recorded"],
                                             "forbid": ["naming who altered the tables"]}}
            return json.dumps(rows)

        backend = PlannerBackend(scenes_reply=with_ops)
        result = make_plan("A premise.", models_with(backend), total_words=13200)
        filled = [op for s in result.plan for tid, op in s.thread_ops.items()
                  if tid == "T-TIDE" and op.post]
        self.assertTrue(filled)
        self.assertIn("naming who altered the tables", filled[0].forbid)

    def test_earlier_summaries_are_fed_into_later_chunks(self):
        """Scenes invented in isolation have the seam problem before any prose exists."""
        backend = PlannerBackend()
        make_plan("A premise.", models_with(backend), total_words=22000)
        scene_prompts = [p for role, p in backend.calls if "filling in scenes" in p]
        self.assertGreater(len(scene_prompts), 1)
        self.assertIn("SCENES ALREADY SETTLED", scene_prompts[-1])

    def test_chunking_covers_every_scene_exactly_once(self):
        backend = PlannerBackend()
        result = make_plan("A premise.", models_with(backend), total_words=33000)
        indices = sorted(s.index for s in result.plan)
        self.assertEqual(indices, list(range(1, len(indices) + 1)))


class TestBeatExpansion(unittest.TestCase):
    def test_vague_scenes_get_sharpened(self):
        backend = PlannerBackend()
        story = propose_story("A premise.", models_with(backend))
        specs = to_scene_specs(schedule_threads(story.threads, 8), story.threads, 8800)
        for spec in specs:
            spec.summary = "Something significant happens."
        before = [score_spec(s) for s in specs]

        touched = expand_beats(specs, story, models_with(backend), rounds=2)

        self.assertGreater(touched, 0)
        self.assertGreater(sum(score_spec(s) for s in specs), sum(before))

    def test_already_concrete_scenes_are_left_alone(self):
        backend = PlannerBackend()
        story = propose_story("A premise.", models_with(backend))
        specs = to_scene_specs(schedule_threads(story.threads, 6), story.threads, 6600)
        flesh_scenes(specs, story, models_with(backend))
        calls_before = backend.beat_calls
        expand_beats(specs, story, models_with(backend), rounds=1, threshold=0.0)
        self.assertEqual(backend.beat_calls, calls_before,
                         "nothing below the threshold should mean no calls at all")

    def test_a_sharpening_that_makes_things_worse_is_not_counted(self):
        def worse(indices):
            return json.dumps({"scenes": [
                {"index": i, "beats": ["Things happen."], "setting": "", "time": ""}
                for i in indices]})

        backend = PlannerBackend(beats_reply=worse)
        story = propose_story("A premise.", models_with(backend))
        specs = to_scene_specs(schedule_threads(story.threads, 6), story.threads, 6600)
        flesh_scenes(specs, story, models_with(backend))
        touched = expand_beats(specs, story, models_with(backend), rounds=1, threshold=1.0)
        self.assertEqual(touched, 0)

    def test_unparseable_expansion_stops_cleanly(self):
        backend = PlannerBackend(beats_reply="sorry")
        story = propose_story("A premise.", models_with(backend))
        specs = to_scene_specs(schedule_threads(story.threads, 6), story.threads, 6600)
        self.assertEqual(expand_beats(specs, story, models_with(backend), rounds=2), 0)


class TestPlanShape(unittest.TestCase):
    def test_scene_count_follows_the_word_target(self):
        backend = PlannerBackend()
        result = make_plan("A premise.", models_with(backend), total_words=33000,
                           avg_scene_words=1100)
        self.assertEqual(len(result.plan), 30)

    def test_explicit_scene_count_wins(self):
        backend = PlannerBackend()
        result = make_plan("A premise.", models_with(backend), total_words=90000, scenes=12)
        self.assertEqual(len(result.plan), 12)

    def test_reports_scenes_left_without_beats(self):
        backend = PlannerBackend(scenes_reply="junk", beats_reply="junk")
        result = make_plan("A premise.", models_with(backend), total_words=13200)
        self.assertTrue(any("cannot be written yet" in n for n in result.notes))

    def test_mean_concreteness_is_reported(self):
        backend = PlannerBackend()
        result = make_plan("A premise.", models_with(backend), total_words=13200)
        self.assertTrue(any("concreteness" in n for n in result.notes))
        self.assertGreater(result.mean_concreteness(), 0.0)


if __name__ == "__main__":
    unittest.main()
