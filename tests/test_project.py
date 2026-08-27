"""Project state on disk: round-trip fidelity and the commit gate's two directions.

State that does not survive a save/load cycle is state the architecture does not really have.
Every generation session reads its brief out of these files, so a field that silently fails to
round-trip is a constraint that silently stops being enforced.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread.ledger import Ledger
from redthread.models import (Beat, Character, Fact, FactKind, Scene, SceneSpec, Severity,
                              StorySpec, StyleContract, Thread, ThreadKind, Transition,
                              Violation)
from redthread.project import Project


def sample_story() -> StorySpec:
    return StorySpec(
        title="Round Trip",
        premise="A premise with a — dash and “quotes”.",
        world_rules=["rule one", "rule two"],
        characters=[Character("siv", "Siv Alderman", "a description", "a voice")],
        threads=[Thread(id="T-A", name="Main", kind=ThreadKind.MYSTERY,
                        states=["dormant", "planted", "paid_off"],
                        current_state="planted", concealment="a secret",
                        payoff="a payoff", deadline_scene=7)],
        style=StyleContract(pov="first", tense="present", samples=["A sample."],
                            forbidden_phrases=["nope"], notes="some notes"),
    )


def sample_plan() -> list[SceneSpec]:
    return [SceneSpec(
        id="s01", index=1, chapter=2, summary="a summary", setting="a place", time="a time",
        pov="siv", characters=["siv"], beats=[Beat("a beat", 0.75)],
        thread_ops={"T-A": Transition(pre=["p"], post=["q"], forbid=["r"],
                                      to_state="paid_off")},
        word_target=1234, concreteness=0.5, notes="a note")]


class TestRoundTrip(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "run"

    def tearDown(self):
        self._tmp.cleanup()

    def test_story_survives_save_and_load(self):
        Project(self.root, sample_story(), sample_plan()).save()
        story = Project.load(self.root).story

        self.assertEqual(story.title, "Round Trip")
        self.assertIn("—", story.premise)
        self.assertEqual(story.world_rules, ["rule one", "rule two"])
        self.assertEqual(story.character("siv").voice, "a voice")
        self.assertEqual(story.style.pov, "first")
        self.assertEqual(story.style.forbidden_phrases, ["nope"])

    def test_thread_state_machine_survives(self):
        Project(self.root, sample_story(), sample_plan()).save()
        thread = Project.load(self.root).story.thread("T-A")

        self.assertIsInstance(thread.kind, ThreadKind)
        self.assertEqual(thread.kind, ThreadKind.MYSTERY)
        self.assertEqual(thread.states, ["dormant", "planted", "paid_off"])
        self.assertEqual(thread.current_state, "planted")
        self.assertEqual(thread.concealment, "a secret")
        self.assertEqual(thread.deadline_scene, 7)

    def test_transitions_survive(self):
        """The (Pre, Post, Forbid) operators are the guardrail. If they do not round-trip, the
        verifier checks nothing on the next run."""
        Project(self.root, sample_story(), sample_plan()).save()
        op = Project.load(self.root).spec_at(1).thread_ops["T-A"]

        self.assertEqual(op.pre, ["p"])
        self.assertEqual(op.post, ["q"])
        self.assertEqual(op.forbid, ["r"])
        self.assertEqual(op.to_state, "paid_off")

    def test_beats_and_scene_fields_survive(self):
        Project(self.root, sample_story(), sample_plan()).save()
        spec = Project.load(self.root).spec_at(1)

        self.assertEqual(spec.chapter, 2)
        self.assertEqual(spec.word_target, 1234)
        self.assertEqual(spec.beats[0].summary, "a beat")
        self.assertEqual(spec.beats[0].concreteness, 0.75)
        self.assertEqual(spec.notes, "a note")

    def test_facts_and_history_survive(self):
        project = Project(self.root, sample_story(), sample_plan())
        scene = Scene(spec_id="s01", index=1, text="Some prose here.")
        scene.facts = [Fact("Siv", "knows", "a thing", 1, FactKind.KNOWLEDGE)]
        project.commit(scene)
        project.save()

        loaded = Project.load(self.root)
        self.assertEqual(len(loaded.ledger.facts), 1)
        self.assertIs(loaded.ledger.facts[0].kind, FactKind.KNOWLEDGE)
        self.assertEqual(len(loaded.history), 1)
        self.assertEqual(loaded.history[0].to_state, "paid_off")

    def test_violations_survive_on_a_rejected_scene(self):
        project = Project(self.root, sample_story(), sample_plan())
        scene = Scene(spec_id="s01", index=1, text="Some prose.")
        scene.violations = [Violation("a_kind", Severity.MAJOR, "a detail", "a source", "a quote")]
        project.put_scene(scene)
        project.save()

        loaded = Project.load(self.root)
        violation = loaded.scene("s01").violations[0]
        self.assertIs(violation.severity, Severity.MAJOR)
        self.assertEqual(violation.quote, "a quote")

    def test_prose_is_stored_one_file_per_scene(self):
        project = Project(self.root, sample_story(), sample_plan())
        project.commit(Scene(spec_id="s01", index=1, text="Prose."))
        project.save()

        self.assertTrue((self.root / "scenes" / "0001.txt").exists())
        self.assertEqual((self.root / "scenes" / "0001.txt").read_text(encoding="utf-8"),
                         "Prose.")


class TestCommitGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Project(Path(self._tmp.name) / "run", sample_story(), sample_plan())

    def tearDown(self):
        self._tmp.cleanup()

    def test_commit_is_the_only_path_into_the_ledger(self):
        scene = Scene(spec_id="s01", index=1, text="Prose.")
        scene.facts = [Fact("Siv", "has", "a notebook", 1, FactKind.DETAIL)]

        self.project.put_scene(scene)
        self.assertEqual(self.project.ledger.facts, [],
                         "put_scene must not write dynamic memory")

        self.project.commit(scene)
        self.assertEqual(len(self.project.ledger.facts), 1)

    def test_rollback_removes_the_scene_facts(self):
        scene = Scene(spec_id="s01", index=1, text="Prose.")
        scene.facts = [Fact("Siv", "has", "a notebook", 1, FactKind.DETAIL)]
        self.project.commit(scene)

        self.project.rollback(scene)
        self.assertEqual(self.project.ledger.facts, [])
        self.assertFalse(scene.committed)

    def test_recommit_replaces_rather_than_duplicates_facts(self):
        """A repaired scene is committed again. Its facts must supersede, not accumulate."""
        scene = Scene(spec_id="s01", index=1, text="Prose.")
        scene.facts = [Fact("Siv", "has", "a notebook", 1, FactKind.DETAIL)]
        self.project.commit(scene)

        scene.facts = [Fact("Siv", "has", "a green notebook", 1, FactKind.DETAIL)]
        self.project.commit(scene)

        self.assertEqual(len(self.project.ledger.facts), 1)
        self.assertEqual(self.project.ledger.facts[0].object, "a green notebook")

    def test_commit_is_idempotent_for_thread_state(self):
        scene = Scene(spec_id="s01", index=1, text="Prose.")
        self.project.commit(scene)
        self.project.commit(scene)

        self.assertEqual(len(self.project.history), 1,
                         "re-committing the same scene must not record the move twice")

    def test_commit_of_an_unknown_spec_raises(self):
        with self.assertRaises(KeyError):
            self.project.commit(Scene(spec_id="nope", index=9, text="Prose."))


class TestManuscript(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "run"

    def tearDown(self):
        self._tmp.cleanup()

    def test_only_committed_scenes_appear(self):
        plan = sample_plan() + [SceneSpec(id="s02", index=2, pov="siv", characters=["siv"])]
        project = Project(self.root, sample_story(), plan)
        project.commit(Scene(spec_id="s01", index=1, text="First scene."))
        project.put_scene(Scene(spec_id="s02", index=2, text="Uncommitted scene."))

        manuscript = project.manuscript()
        self.assertIn("First scene.", manuscript)
        self.assertNotIn("Uncommitted scene.", manuscript)

    def test_scenes_appear_in_index_order(self):
        plan = sample_plan() + [SceneSpec(id="s02", index=2, pov="siv", characters=["siv"])]
        project = Project(self.root, sample_story(), plan)
        project.commit(Scene(spec_id="s02", index=2, text="SECOND"))
        project.commit(Scene(spec_id="s01", index=1, text="FIRST"))

        manuscript = project.manuscript()
        self.assertLess(manuscript.index("FIRST"), manuscript.index("SECOND"))

    def test_status_counts_committed_work_only(self):
        project = Project(self.root, sample_story(), sample_plan())
        project.put_scene(Scene(spec_id="s01", index=1, text="one two three"))
        self.assertEqual(project.status()["words"], 0)

        project.commit(project.scene("s01"))
        self.assertEqual(project.status()["words"], 3)
        self.assertEqual(project.status()["scenes_committed"], 1)


if __name__ == "__main__":
    unittest.main()
