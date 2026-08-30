"""The rule this project has been keeping without stating it.

Phase 6 of docs/PLAN.md, steps 23 and 24.

    The gate may refuse only on evidence code can locate.
    The plan may be shaped by anything, including a model's reading of a story.

The asymmetry is about cost. A bad plan costs one re-ask before a word is written; a bad gate
costs a book that never finishes, because a scene held back by a model's opinion cannot be
repaired — there is nothing to repair against — and an unattended run stops there at three in the
morning.

The first test below is the enforcement. It walks the source tree for `Severity.BLOCKER` and
insists the emitting source is one that has written down what a person could check by hand. That
turns "we have a principle" into "adding a blocker requires saying what makes it checkable",
which is the only form a principle survives in.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from redthread import checks

SOURCE_DIR = Path(__file__).resolve().parent.parent / "redthread"


class TestTheGateRefusesOnlyWhatCodeCanLocate(unittest.TestCase):

    def _blocker_sites(self):
        """(file, line, the source string) for every Violation constructed as a BLOCKER.

        Matches the constructor's own shape — kind, severity, detail, source — across line
        breaks, which is how every one of them is actually written.
        """
        pattern = re.compile(
            r'Violation\(\s*"(?P<kind>[a-z_]+)",\s*Severity\.BLOCKER'
            r'(?:[^()]|\([^()]*\))*?,\s*"(?P<source>[a-z_:]+)"',
            re.S)
        out = []
        for path in sorted(SOURCE_DIR.glob("*.py")):
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                line = text[: match.start()].count("\n") + 1
                out.append((path.name, line, match.group("kind"), match.group("source")))
        return out

    def test_the_scan_finds_the_blockers(self):
        # If this ever returns nothing the test below passes vacuously, which would be the worst
        # possible outcome for an enforcement test.
        self.assertGreaterEqual(len(self._blocker_sites()), 5)

    def test_every_blocker_comes_from_a_source_that_has_said_what_it_can_locate(self):
        for filename, line, kind, source in self._blocker_sites():
            self.assertIn(
                source, checks.BLOCKER_SOURCES,
                f"{filename}:{line} emits a BLOCKER ({kind}) from {source!r}, which is not in "
                f"checks.BLOCKER_SOURCES. A blocker stops an unattended run, so add the source "
                f"there with a note on what a person could check by hand — or make it a MAJOR.")

    def test_the_model_sourced_blockers_are_the_two_that_are_not_judgements(self):
        """Writing this test is what made the rule precise.

        The first draft asserted there was exactly one model-sourced blocker and was wrong:
        `llm:extract_facts` blocks too. That is not a counterexample, it is a sharpening. Neither
        of these refuses a scene for how it reads — one answers a binary question about two
        ledger rows code selected and quotes both, and the other fires because a call returned
        nothing parseable, which is a broken call rather than an opinion.
        """
        model_sourced = sorted(s for s in checks.BLOCKER_SOURCES if s.startswith("llm:"))
        self.assertEqual(model_sourced, ["llm:extract_facts", "llm:judge_conflicts"])

    def test_every_listed_source_says_what_makes_its_evidence_locatable(self):
        for source, reason in checks.BLOCKER_SOURCES.items():
            self.assertGreater(len(reason.split()), 3,
                               f"{source} needs a real reason, not a label")

    def test_no_check_blocks_on_a_judgement_of_quality(self):
        # The probes that read a scene as a story — tells, thematic gloss, forecastability —
        # are all advisory by construction. `probe_tells` has a known false-positive floor
        # recorded in its own docstring, which is exactly why.
        for banned in ("llm:probe_tells", "llm:probe_forecast", "llm:judge_threads"):
            self.assertNotIn(banned, checks.BLOCKER_SOURCES)


class TestQuietChecksAreNamed(unittest.TestCase):
    """Step 24. A check that cannot fire reads as coverage in an audit that lists it."""

    def test_the_scheduler_guaranteed_set_is_the_documented_one(self):
        self.assertEqual(
            set(checks.SCHEDULER_GUARANTEED),
            {"subplot_independence", "state_regression", "state_repeat", "unknown_state",
             "midpoint_stall", "uniform_scene_length"})

    def test_each_names_why_it_cannot_fire(self):
        for kind, reason in checks.quiet_checks().items():
            self.assertGreater(len(reason.split()), 5,
                               f"{kind} is marked quiet without a reason anyone can check")

    def test_instruction_confirming_is_separate_from_scheduler_guaranteed(self):
        # Different guarantees, different failure modes: the scheduler's holds because code
        # makes it hold, and the brief's holds because a model is complying — which could stop
        # being true at any time without anything here changing.
        self.assertEqual(set(checks.INSTRUCTION_CONFIRMING), {"somatic_emotion"})
        self.assertFalse(set(checks.SCHEDULER_GUARANTEED) & set(checks.INSTRUCTION_CONFIRMING))

    def test_quiet_checks_is_the_union(self):
        # One function so a report cannot list a subset and imply the rest are live.
        self.assertEqual(
            set(checks.quiet_checks()),
            set(checks.SCHEDULER_GUARANTEED) | set(checks.INSTRUCTION_CONFIRMING))

    def test_the_named_kinds_are_kinds_the_code_can_emit(self):
        # Guards against a rename leaving this table pointing at nothing, which would silently
        # turn the audit's disclaimer into a list of checks that no longer exist.
        source = "\n".join(p.read_text(encoding="utf-8") for p in SOURCE_DIR.glob("*.py"))
        for kind in checks.quiet_checks():
            self.assertIn(f'"{kind}"', source, f"nothing in the codebase emits {kind!r}")

    def test_the_audit_says_so_out_loud(self):
        import contextlib
        import io
        from redthread.cli import cmd_audit
        from redthread.models import StorySpec, Thread, ThreadKind

        class Args:
            project = "unused"

        story = StorySpec(title="T", premise="p",
                          threads=[Thread(id="t1", name="n", kind=ThreadKind.MAIN,
                                          states=["a", "b"])])

        class FakeProject:
            def __init__(self):
                self.plan, self.story, self.history = [], story, []

        import redthread.cli as cli
        original = cli._load
        cli._load = lambda _path: FakeProject()
        try:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                cmd_audit(Args())
        finally:
            cli._load = original
        printed = buffer.getvalue()
        self.assertIn("cannot fire", printed)
        self.assertIn("midpoint_stall", printed)


if __name__ == "__main__":
    unittest.main()
