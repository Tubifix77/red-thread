"""`write` must refuse a plan the audit has already rejected.

`audit` sits between planning and writing precisely so a structural failure is found before the
hours are spent, and nothing was enforcing that. A live plan came back with one thread and no
subplot — the audit said so, `plan` exited non-zero, and `write` started anyway and spent three
scenes on it.
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread.cli import cmd_write
from redthread.models import (Beat, Character, SceneSpec, StorySpec, StyleContract, Thread,
                              ThreadKind, Transition)
from redthread.project import Project


class _Args:
    def __init__(self, project, force=False):
        self.project = project
        self.scene = None
        self.start, self.stop = 1, None
        self.candidates, self.repairs = 1, 0
        self.forecast = False
        self.force = force
        self.quiet = True
        self.writer = self.critic = None
        self.local = self.all_local = self.local_critic = None
        self.base_url = None
        self.openai_compat = False


def _project(root: Path, subplot: bool) -> Project:
    threads = [Thread(id="T-A", name="Main", kind=ThreadKind.MAIN,
                      states=["dormant", "planted", "paid_off"],
                      concealment="a secret", payoff="a payoff")]
    if subplot:
        threads.append(Thread(id="T-B", name="Side", kind=ThreadKind.SUBPLOT,
                              states=["dormant", "planted", "paid_off"],
                              concealment="another secret", payoff="another payoff"))
    story = StorySpec(title="Fixture", premise="A premise.",
                      characters=[Character("siv", "Siv"), Character("otto", "Otto"),
                                  Character("beata", "Beata")],
                      threads=threads, style=StyleContract(samples=["A sentence."]))
    ops = {"T-A": Transition(post=["something"], to_state="planted")}
    plan = [SceneSpec(id="s01", index=1, word_target=900, pov="siv", characters=["siv"],
                      summary="Something happens.", beats=[Beat("a beat")], thread_ops=ops)]
    project = Project(root, story, plan)
    project.save()
    return project


class TestWriteRefusesARejectedPlan(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "run"

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_plan_with_no_subplot_is_refused_before_any_model_is_touched(self):
        _project(self.root, subplot=False)
        out = io.StringIO()
        with redirect_stdout(out):
            code = cmd_write(_Args(str(self.root)))
        self.assertEqual(code, 2)
        self.assertIn("no_subplots", out.getvalue())
        self.assertIn("--force", out.getvalue())

    def test_force_writes_anyway(self):
        """The refusal is a guard, not a veto — it must stay overridable."""
        _project(self.root, subplot=False)
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            # No model is configured, so it gets past the audit and stops at model resolution,
            # which is exactly far enough to prove the guard was not what stopped it.
            cmd_write(_Args(str(self.root), force=True))
        self.assertNotIn("unresolved structural findings", out.getvalue())


if __name__ == "__main__":
    unittest.main()
