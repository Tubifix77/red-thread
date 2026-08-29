"""End-to-end: the full ten-scene reference plan, driven by a scripted backend.

This is the closest thing to a real run that costs nothing. It proves the machinery composes —
plan audit, brief assembly, ten commit gates in sequence, thread state advancing to resolution,
the ledger accumulating across scenes, and a manuscript falling out the other end.

It does not and cannot say anything about prose quality. Only a real model can, and that is the
next step (see README, "What is still unproven").
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

import build_inherited_glitch as builder

from redthread import checks
from redthread.pipeline import Config, write_all
from redthread.project import Project

from tests import fakes


class TestFullRun(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "glitch"
        self.project = Project(self.root, builder.build_story(), builder.build_plan())
        self.project.save()

    def tearDown(self):
        self._tmp.cleanup()

    def test_plan_audit_passes_before_generation(self):
        found = checks.audit_plan(self.project.plan, self.project.story)
        self.assertEqual(found, [], "; ".join(str(v) for v in found))

    def test_all_ten_scenes_commit(self):
        models, backend = fakes.scripted_models({
            # Each scene extracts one fact scoped to that scene, so the ledger grows without
            # the fixture manufacturing contradictions.
            "extract": fakes.facts_json([("Siv Alderman", "is at", "the pump house", "state")]),
        })
        for spec in self.project.plan:
            backend.queue("draft", fakes.clean_prose(spec.word_target, spec.index - 1))

        results = write_all(self.project, models, Config(candidates=1))

        held = [r for r in results if not r.committed]
        self.assertEqual(len(results), 10)
        self.assertEqual(held, [], "; ".join(
            f"scene {r.scene.index}: " + "; ".join(str(v) for v in r.violations) for r in held))

    def test_every_thread_reaches_its_final_state(self):
        models, backend = fakes.scripted_models()
        for spec in self.project.plan:
            backend.queue("draft", fakes.clean_prose(spec.word_target, spec.index - 1))
        write_all(self.project, models, Config(candidates=1))

        unresolved = [t.id for t in self.project.story.threads if not t.is_resolved()]
        self.assertEqual(unresolved, [], f"unpaid threads after a full run: {unresolved}")

    def test_thread_history_records_every_move(self):
        models, backend = fakes.scripted_models()
        for spec in self.project.plan:
            backend.queue("draft", fakes.clean_prose(spec.word_target, spec.index - 1))
        write_all(self.project, models, Config(candidates=1))

        planned_moves = sum(
            1 for spec in self.project.plan for op in spec.thread_ops.values() if op.to_state)
        self.assertEqual(len(self.project.history), planned_moves)

    def test_ledger_accumulates_and_survives_a_reload(self):
        models, backend = fakes.scripted_models({
            "extract": fakes.facts_json([
                ("Siv Alderman", "has", "a paper notebook", "detail"),
                ("Siv Alderman", "knows", "the log is wrong", "knowledge"),
            ])})
        for spec in self.project.plan:
            backend.queue("draft", fakes.clean_prose(spec.word_target, spec.index - 1))
        write_all(self.project, models, Config(candidates=1))
        self.project.save()

        reloaded = Project.load(self.root)
        self.assertEqual(len(reloaded.ledger.facts), 20)
        self.assertTrue(reloaded.ledger.knows("Siv Alderman", scene=11))
        self.assertEqual(reloaded.status()["scenes_committed"], 10)

    def test_manuscript_is_written_with_chapter_breaks(self):
        models, backend = fakes.scripted_models()
        for spec in self.project.plan:
            backend.queue("draft", fakes.clean_prose(spec.word_target, spec.index - 1))
        write_all(self.project, models, Config(candidates=1))

        path = self.root / "manuscript.md"
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("# The Inherited Glitch", text)
        for chapter in sorted({s.chapter for s in self.project.plan}):
            self.assertIn(f"## {chapter}", text)

    def test_a_rejection_midway_halts_the_run_and_leaves_state_clean(self):
        """Scene 5 fails. Scenes 1-4 must be committed; nothing from 5 may be in the ledger."""
        models, backend = fakes.scripted_models({
            "extract": fakes.facts_json([("Siv Alderman", "is at", "a place", "state")])})
        for spec in self.project.plan:
            text = (fakes.prose_with_heading(spec.word_target, spec.index - 1) if spec.index == 5
                    else fakes.clean_prose(spec.word_target, spec.index - 1))
            backend.queue("draft", text)

        results = write_all(self.project, models, Config(candidates=1, max_repairs=0))

        self.assertEqual([r.scene.index for r in results], [1, 2, 3, 4, 5])
        self.assertEqual(self.project.status()["scenes_committed"], 4)
        self.assertEqual([f.scene for f in self.project.ledger.facts], [1, 2, 3, 4])
        self.assertTrue(all(m.scene <= 4 for m in self.project.history))

    def test_resuming_after_a_fix_continues_from_the_gap(self):
        models, backend = fakes.scripted_models()
        for spec in self.project.plan:
            text = (fakes.prose_with_heading(spec.word_target, spec.index - 1) if spec.index == 5
                    else fakes.clean_prose(spec.word_target, spec.index - 1))
            backend.queue("draft", text)
        write_all(self.project, models, Config(candidates=1, max_repairs=0))

        # The operator fixes whatever was wrong and re-runs. Drain the queue first: drafts left
        # over from the halted run would be handed to the wrong scenes, at the wrong lengths.
        backend.queues.clear()
        for spec in self.project.plan:
            if spec.index >= 5:
                backend.queue("draft", fakes.clean_prose(spec.word_target, spec.index - 1))
        results = write_all(self.project, models, Config(candidates=1))

        self.assertEqual([r.scene.index for r in results], [5, 6, 7, 8, 9, 10])
        self.assertEqual(self.project.status()["scenes_committed"], 10)

    def test_briefs_carry_forward_the_seam_for_every_scene_after_the_first(self):
        models, backend = fakes.scripted_models()
        for spec in self.project.plan:
            backend.queue("draft", fakes.clean_prose(spec.word_target, spec.index - 1))
        write_all(self.project, models, Config(candidates=1))

        drafts = [prompt for role, prompt in backend.calls if role == "draft"]
        self.assertEqual(len(drafts), 10)
        self.assertIn("This is the opening scene", drafts[0])
        for i, prompt in enumerate(drafts[1:], start=2):
            self.assertIn("The previous scene ended with exactly this text", prompt,
                          f"scene {i}'s brief lost its seam")
            self.assertNotIn("WARNING: scene", prompt,
                             f"scene {i} was written against an incomplete ledger")

    def test_every_brief_tells_the_writer_the_beats_are_not_sentences(self):
        """Scene 9 of a live run copied thirteen six-word runs out of its own beats. The beats
        were fine; nothing had told the writer they were instructions rather than prose."""
        models, backend = fakes.scripted_models()
        for spec in self.project.plan:
            backend.queue("draft", fakes.clean_prose(spec.word_target, spec.index - 1))
        write_all(self.project, models, Config(candidates=1))

        for i, prompt in enumerate([p for role, p in backend.calls if role == "draft"], start=1):
            self.assertIn("They are instructions, not sentences", prompt,
                          f"scene {i}'s brief did not warn against copying its beats")


if __name__ == "__main__":
    unittest.main()
