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
from redthread.planner import (drop_unavoidable_bans, make_plan, parse_story,
                               propose_story, story_problems, expand_beats,
                               flesh_scenes)
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
                        "The typesetter did not look up from the case.",
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

    def __init__(self, story: str | None = None, scenes_reply=None, beats_reply=None,
                 scrub_reply=None, deprose_reply=None, restate_reply=None) -> None:
        super().__init__()
        self._story = story if story is not None else story_json()
        self._scenes = scenes_reply
        self._beats = beats_reply
        self._scrub = scrub_reply
        self._deprose = deprose_reply
        self._restate = restate_reply
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
        if "Rewrite this line from a novel outline" in prompt:
            self.calls.append(("restate", prompt))
            from redthread.llm import Reply
            return Reply(self._restate if isinstance(self._restate, str)
                         else "The snow gauge climbs past the mark.", model="scripted")
        if "Rewrite this outline beat" in prompt:
            self.calls.append(("deprose", prompt))
            from redthread.llm import Reply
            return Reply(self._deprose if isinstance(self._deprose, str)
                         else "Varyn demands the years back.", model="scripted")
        if "Rewrite this one outline line" in prompt:
            self.calls.append(("scrub", prompt))
            from redthread.llm import Reply
            if self._scrub is not None and not isinstance(self._scrub, str):
                return Reply(next(self._scrub, "A neutral line."), model="scripted")
            return Reply(self._scrub if isinstance(self._scrub, str)
                         else "Varen must choose between duty and morality as the enclave "
                              "hangs in the balance.", model="scripted")
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


class TestScrub(unittest.TestCase):
    """The plan must obey its own style contract, in the scene content too: a real run banned
    "fate" in its bible and then wrote "the enclave's fate hangs in the balance" into a scene
    summary, injecting the banned word into every brief built from it."""

    def _story_with_ban(self):
        return parse_story(json.loads(story_json(style={
            "pov": "third limited", "tense": "past",
            "samples": ["A.", "B.", "C."],
            "forbidden_phrases": ["fate"], "notes": ""})))

    def test_offending_lines_are_rewritten(self):
        from redthread.planner import scrub_forbidden
        from redthread.models import Beat, SceneSpec
        story = self._story_with_ban()
        specs = [SceneSpec(id="s01", index=1,
                           summary="The enclave's fate hangs in the balance.",
                           beats=[Beat("She reads the ledger at the bench.")])]
        backend = PlannerBackend(
            scrub_reply="The enclave's survival hangs in the balance.")
        fixed = scrub_forbidden(specs, story, models_with(backend))
        self.assertEqual(fixed, 1)
        self.assertNotIn("fate", specs[0].summary.lower())
        self.assertIn("survival", specs[0].summary)

    def test_the_story_bible_is_scrubbed_too(self):
        """A live plan banned "truth" and then wrote "he's too old to confront the truth" into a
        character description. Descriptions go into every brief, so scrubbing only the scene
        content left a permanent MAJOR and the banned word in all fifteen briefs."""
        from redthread.planner import scrub_forbidden
        from redthread.models import Beat, SceneSpec
        story = self._story_with_ban()
        story.characters[0].description = "He is too old to confront the fate of it."
        specs = [SceneSpec(id="s01", index=1, summary="She reads the ledger.",
                           beats=[Beat("A beat.")])]
        backend = PlannerBackend(scrub_reply="He is too old to confront what it means.")

        fixed = scrub_forbidden(specs, story, models_with(backend))

        self.assertEqual(fixed, 1)
        self.assertNotIn("fate", story.characters[0].description.lower())
        self.assertEqual(checks.check_spec_self_consistency(specs, story), [])

    def test_a_failed_rewrite_is_retried_with_the_failure_named(self):
        """Two live plans banned "truth" and kept beats saying "truth", because every silent
        retry reached for the word again. Naming the failure is what breaks the loop."""
        from redthread.planner import scrub_forbidden
        from redthread.models import Beat, SceneSpec
        story = self._story_with_ban()
        specs = [SceneSpec(id="s01", index=1, summary="A summary.",
                           beats=[Beat("The villagers react to the fate of the pass.")])]
        backend = PlannerBackend(scrub_reply=iter([
            "The villagers react to the fate of it.",
            "The villagers react to what the register says."]))

        fixed = scrub_forbidden(specs, story, models_with(backend))

        self.assertEqual(fixed, 1)
        self.assertEqual(specs[0].beats[0].summary,
                         "The villagers react to what the register says.")
        prompts = [p for role, p in backend.calls if role == "scrub"]
        self.assertEqual(len(prompts), 2)
        self.assertIn("still uses", prompts[1], "the retry was not told what went wrong")

    def test_a_rewrite_that_keeps_the_phrase_is_discarded(self):
        from redthread.planner import scrub_forbidden
        from redthread.models import Beat, SceneSpec
        story = self._story_with_ban()
        specs = [SceneSpec(id="s01", index=1,
                           summary="The enclave's fate hangs in the balance.",
                           beats=[Beat("A beat.")])]
        backend = PlannerBackend(scrub_reply="Their fate still hangs there.")
        fixed = scrub_forbidden(specs, story, models_with(backend))
        self.assertEqual(fixed, 0, "an unverified rewrite must not land")
        self.assertIn("fate", specs[0].summary.lower())

    def test_clean_plans_cost_no_calls(self):
        from redthread.planner import scrub_forbidden
        from redthread.models import Beat, SceneSpec
        story = self._story_with_ban()
        specs = [SceneSpec(id="s01", index=1, summary="She reads the ledger.",
                           beats=[Beat("A beat.")])]
        backend = PlannerBackend()
        self.assertEqual(scrub_forbidden(specs, story, models_with(backend)), 0)
        self.assertEqual(backend.count("scrub"), 0)


class TestPlanRulesAreStoredAsWritten(unittest.TestCase):
    """The plan is not edited so a checker can cope with it.

    Earlier versions rewrote scene rules at parse time — absences moved to the forbid list,
    negations inverted, bans on common words dropped — and the cost was paid by the writer,
    because the brief is built from this text. A live plan lost "Nils ignores the thermometer's
    reading", a perfectly writable beat, because a judge could not confirm it afterwards.

    The audit reports rules that look unwritable. The author decides. `verify` narrows what it
    asks the judge, which is its own business and does not touch the plan.
    """

    def _op(self, post=None, forbid=None):
        from redthread.planner import _apply_scene_content
        from redthread.models import SceneSpec, StorySpec, Transition
        spec = SceneSpec(id="s01", index=1, thread_ops={"T-A": Transition()})
        _apply_scene_content(spec, {"index": 1, "threads": {"T-A": {
            "post": post or [], "forbid": forbid or []}}},
            StorySpec(title="t", premise="p"))
        return spec.thread_ops["T-A"]

    def test_a_negated_forbid_survives_verbatim(self):
        op = self._op(forbid=["The enclave is not revealed"])
        self.assertEqual(op.forbid, ["The enclave is not revealed"])

    def test_an_obligation_to_ignore_something_survives_verbatim(self):
        """The beat a live plan lost."""
        op = self._op(post=["Nils ignores the thermometer's reading"])
        self.assertEqual(op.post, ["Nils ignores the thermometer's reading"])

    def test_an_absence_post_stays_where_the_author_put_it(self):
        op = self._op(post=["Mira remains uncertain about the logs' authenticity",
                            "Mira photographs both entries"])
        self.assertEqual(op.post, ["Mira remains uncertain about the logs' authenticity",
                                   "Mira photographs both entries"])
        self.assertEqual(op.forbid, [])

    def test_the_audit_is_what_reports_them(self):
        from redthread.models import SceneSpec, StorySpec, Thread, Transition
        spec = SceneSpec(id="s01", index=1, summary="x",
                         thread_ops={"T": Transition(post=["The Allegiance reaches 'settled'"])})
        story = StorySpec(title="t", premise="p",
                          threads=[Thread(id="T", name="The Allegiance",
                                          states=["dormant", "settled"])])
        self.assertIn("post_names_a_state",
                      {v.kind for v in checks.check_post_is_an_event([spec], story)})


class TestBansAreReportedNotDropped(unittest.TestCase):
    """A ban on a word the prose is made of is the author's to reconsider, not ours to delete."""

    def _story(self, *phrases):
        return parse_story(json.loads(story_json(style={
            "pov": "third limited", "tense": "past", "samples": ["A.", "B.", "C."],
            "forbidden_phrases": list(phrases), "notes": ""})))

    def test_the_ban_survives_parsing(self):
        story = self._story("truth", "conspiracy")
        self.assertEqual(story.style.forbidden_phrases, ["truth", "conspiracy"])

    def test_the_audit_reports_it(self):
        found = checks.check_ban_is_avoidable([], self._story("truth", "conspiracy"))
        self.assertEqual([v.quote for v in found], ["truth"])


class TestUnavoidableBansAreDroppedFromAProposal(unittest.TestCase):
    """The other half of `TestBansAreReportedNotDropped`, and the distinction between them.

    A ban in a `story.json` a person wrote is theirs; the audit reports it and `write` refuses.
    A ban in a model's *proposal*, still inside the planner's retry loop, is not a decision
    anyone made — and every fresh premise tried has produced at least one, which makes it the
    single largest obstacle to a run nobody is watching.

    The prompt already tells the planner that "truth", "right", "memory" and "silence" are words
    a novel needs. A live plan for a lighthouse story listed all four, alongside three good bans
    it got right. Which is the whole argument for checking rather than asking.
    """

    def _story(self, *phrases):
        return parse_story(json.loads(story_json(style={
            "pov": "third limited", "tense": "past", "samples": ["A.", "B.", "C."],
            "forbidden_phrases": list(phrases), "notes": ""})))

    def test_the_avoidable_bans_survive(self):
        story = drop_unavoidable_bans(self._story("conspiracy", "hacker", "sentient"))
        self.assertEqual(story.style.forbidden_phrases, ["conspiracy", "hacker", "sentient"])

    def test_the_unavoidable_ones_are_dropped(self):
        story = drop_unavoidable_bans(
            self._story("conspiracy", "truth", "hacker", "right", "memory", "silence"))
        self.assertEqual(story.style.forbidden_phrases, ["conspiracy", "hacker"])

    def test_what_survives_passes_the_audit_that_would_have_blocked_it(self):
        """The filter and the gate have to agree, or one of them is wrong."""
        story = drop_unavoidable_bans(self._story("truth", "right", "conspiracy", "silence"))
        self.assertEqual(checks.check_ban_is_avoidable([], story), [])

    def test_a_plan_that_needs_nothing_dropped_is_returned_untouched(self):
        story = self._story("conspiracy")
        self.assertIs(drop_unavoidable_bans(story), story)


class TestBeatsSurviveSharpening(unittest.TestCase):
    """`scrub_prose_beats` has to run AFTER `expand_beats`, not before.

    Sharpening is the step that pushes beats toward specificity, so it is also the step that turns
    them into prose — and when the scrub ran first, the very next call undid it. Scene 26 of a live
    book carried ten beats like "Dain steps forward, his boots crunching over dry leaves, his voice
    steady and low", the writer wrote what it was given, `check_brief_leak` found seven copied
    runs, and the scene never committed at any repair budget.
    """

    PROSE = ("Dain steps forward, his boots crunching over dry leaves, and says, "
             "'You will not take these years.'")

    def _sharpener_returns_prose(self, indices):
        return json.dumps({"scenes": [
            {"index": i, "beats": [self.PROSE, self.PROSE],
             "setting": "the enclave", "time": "midnight"} for i in indices]})

    def _vague_scenes(self, indices):
        """Beats too vague to write from, so the sharpener actually has a frontier to work on."""
        return json.dumps({"scenes": [
            {"index": i, "summary": "Something happens.", "setting": "", "time": "",
             "pov": "siv", "characters": ["siv"], "beats": ["it develops", "it deepens"],
             "threads": {}} for i in indices]})

    def test_prose_beats_from_sharpening_are_rewritten_before_the_plan_is_returned(self):
        backend = PlannerBackend(scenes_reply=self._vague_scenes,
                                 beats_reply=self._sharpener_returns_prose)
        result = make_plan("A premise.", models_with(backend), total_words=4000,
                           sharpen_rounds=1)

        self.assertTrue(backend.beat_calls, "the sharpener never ran; the test proves nothing")

        self.assertTrue(backend.count("deprose"),
                        "the scrub never saw the sharpened beats")
        offenders = [b.summary for spec in result.plan for b in spec.beats
                     if checks._BEAT_PROSE.search(b.summary)]
        self.assertEqual(offenders, [], "prose beats survived into the finished plan")

    def test_the_audit_reports_any_that_survive(self):
        """The scrub is best-effort — a rewrite that still carries dialogue is discarded — so the
        check behind it has to stay the honest backstop."""
        backend = PlannerBackend(scenes_reply=self._vague_scenes,
                                 beats_reply=self._sharpener_returns_prose,
                                 deprose_reply=self.PROSE)
        result = make_plan("A premise.", models_with(backend), total_words=4000,
                           sharpen_rounds=1)

        self.assertIn("beat_is_prose", {v.kind for v in result.violations})


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


class TestRevealState(unittest.TestCase):
    """Concealment timing is derived from the schedule, never guessed: the planner names the
    state that discloses each concealment, the scheduler knows which scene that state lands in.
    Without this, a planner-made thread whose second state was 'discovered' carried a
    concealment forbidding the very disclosure its own schedule ordered two scenes in."""

    def test_reveal_state_is_parsed_and_validated(self):
        threads = [
            {"id": "A", "name": "A", "kind": "main", "states": FIVE,
             "concealment": "c", "concealment_ends_at_state": "escalated", "payoff": "p"},
            {"id": "B", "name": "B", "kind": "subplot", "states": FIVE,
             "concealment": "c", "concealment_ends_at_state": "not_a_state", "payoff": "p"},
        ]
        story = parse_story(json.loads(story_json(threads=threads)))
        self.assertEqual(story.thread("A").reveal_state, "escalated")
        self.assertIsNone(story.thread("B").reveal_state,
                          "a state not in the machine must not survive parsing")

    def test_reveal_scene_is_derived_from_the_schedule(self):
        backend = PlannerBackend(story=story_json(threads=[
            {"id": "T-TIDE", "name": "Tables", "kind": "main", "states": FIVE,
             "concealment": "who altered them", "concealment_ends_at_state": "escalated",
             "payoff": "p"},
            {"id": "T-BOAT", "name": "Licence", "kind": "subplot", "states": FIVE,
             "concealment": "it lapsed", "payoff": "p"},
        ]))
        result = make_plan("A premise.", models_with(backend), total_words=13200)

        tide = result.story.thread("T-TIDE")
        landing = [i for i, s in checks.planned_state_sequence(result.plan, "T-TIDE")
                   if s == "escalated"]
        self.assertEqual(tide.reveal_scene, landing[0],
                         "reveal must land exactly where the schedule put the state")

        boat = result.story.thread("T-BOAT")
        terminal = [i for i, s in checks.planned_state_sequence(result.plan, "T-BOAT")
                    if s == boat.states[-1]]
        self.assertEqual(boat.reveal_scene, terminal[0],
                         "no declared reveal state defaults to the terminal — payoffs disclose")


class TestACatchphraseIsRefusedInTheRetryLoop(unittest.TestCase):
    """A line written into a character's voice is repeated by the whole book.

    A 71-scene run gave Vaylen Korr the voice "he speaks in clipped, precise sentences,
    deflecting with dry humor, often using the phrase 'this is not a matter of morality.'" That
    description goes into every brief the character appears in, and the phrase landed in 23 of
    71 scenes — while those same briefs were listing it as a refrain to avoid, because
    `manuscript_refrains` had correctly spotted it. Characterisation beat prohibition, which it
    will: one is what the character *is* and the other is a rule about wording.

    The distinction is habitual repetition, not quotation. Another plan gave a character the
    voice "The light is on. The tide is out. The snow is falling." to illustrate clipped rhythm
    and none of it reached the prose — 0 of 9 scenes. It is "often using the phrase" that does
    the damage, so that is what is matched.
    """

    def _story(self, voice):
        return parse_story(json.loads(story_json(characters=[
            {"id": "vaylen", "name": "Vaylen Korr", "description": "a bailiff", "voice": voice},
            {"id": "sorin", "name": "Sorin Vey", "description": "a fugitive", "voice": "evades"},
            {"id": "mirra", "name": "Mirra Thal", "description": "an official", "voice": "flat"},
        ])))

    def test_the_catchphrase_from_the_live_run_is_caught(self):
        story = self._story("He speaks in clipped, precise sentences, deflecting with dry "
                            "humor, often using the phrase 'this is not a matter of morality.'")
        problems = story_problems(story)
        self.assertTrue(any("phrase they repeat" in p for p in problems), problems)
        self.assertTrue(any("Vaylen Korr" in p for p in problems), problems)

    def test_other_habitual_wordings_too(self):
        for lead in ("always says", "has a habit of saying", "is fond of saying",
                     "repeatedly falls back on", "keeps saying"):
            with self.subTest(lead=lead):
                story = self._story(f"Blunt and short. He {lead} 'the ledger does not lie.'")
                self.assertTrue(any("phrase they repeat" in p for p in story_problems(story)))

    def test_a_quoted_rhythm_example_is_not_a_catchphrase(self):
        """The one that did no harm, and must keep doing none. Three clipped sentences shown as
        an illustration of cadence appeared in 0 of 9 scenes of the book that used them."""
        story = self._story("Clipped and declarative: 'The light is on. The tide is out. "
                            "The snow is falling.'")
        self.assertFalse(any("phrase they repeat" in p for p in story_problems(story)))

    def test_an_ordinary_voice_is_left_alone(self):
        story = self._story("Speaks in short sentences and changes the subject to the weather "
                            "whenever the sale is mentioned.")
        self.assertFalse(any("phrase they repeat" in p for p in story_problems(story)))
