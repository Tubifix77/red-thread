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


class TestJudgeConflictsValidatesItsIndex(unittest.TestCase):
    """A number a model returned, used as an index without checking it addresses anything.

    The same class as the re-people bug found an hour earlier, on the one path in this project
    that emits a BLOCKER from a model's answer. `pairs[-1]` raises nothing, so a judgement row
    with no "pair" key was silently attributed to the *last* pair and a negative index wrapped to
    another one — stopping an unattended run on a contradiction between two facts the model was
    not judging, and quoting both of them.
    """

    def _run(self, judgements):
        import json
        from redthread.ledger import Ledger
        from redthread.models import Fact, FactKind
        from redthread.verify import judge_conflicts
        from tests import fakes

        # **Two** pairs, not one. With a single pair `pairs[-1]` is `pairs[0]` and the wrap is
        # invisible — the test would pass against the bug it exists to catch, which is the trap
        # the fixtures elsewhere in this suite fell into.
        older = [Fact(subject="the vial", predicate="is", object="full", scene=1,
                      kind=FactKind.STATE),
                 Fact(subject="the door", predicate="is", object="locked", scene=1,
                      kind=FactKind.STATE)]
        newer = [Fact(subject="the vial", predicate="is", object="empty", scene=2,
                      kind=FactKind.STATE),
                 Fact(subject="the door", predicate="is", object="open", scene=2,
                      kind=FactKind.STATE)]
        ledger = Ledger(older)
        models, _backend = fakes.scripted_models(
            {"conflict": json.dumps({"judgements": judgements})})
        assert len(ledger.conflict_candidates(newer)) == 2, "the fixture must offer two pairs"
        return judge_conflicts(newer, ledger, models)

    def test_a_well_formed_judgement_is_reported(self):
        found = self._run([{"pair": 0, "contradiction": True, "why": "both cannot hold"}])
        self.assertEqual([v.kind for v in found], ["continuity_contradiction"])

    def test_a_row_with_no_pair_key_is_dropped_not_pinned_to_the_last_pair(self):
        self.assertEqual(self._run([{"contradiction": True, "why": "unattributed"}]), [])

    def test_a_negative_index_is_dropped_rather_than_wrapping(self):
        self.assertEqual(self._run([{"pair": -1, "contradiction": True, "why": "x"}]), [])

    def test_an_index_past_the_end_is_dropped(self):
        self.assertEqual(self._run([{"pair": 99, "contradiction": True, "why": "x"}]), [])

    def test_a_non_numeric_index_is_dropped(self):
        self.assertEqual(self._run([{"pair": "first", "contradiction": True, "why": "x"}]), [])


class TestJudgeThreadsValidatesItsIndex(unittest.TestCase):
    """The same defect twice more, found by grepping for the shape rather than by a run.

    `required[-1]` and `forbidden[-1]` raise nothing, so a row with no "n" reported its verdict
    against the *last* obligation. Advisory rather than blocking here, so the cost is a
    misdirected repair rather than a halted book — but it is the same bug, and the search that
    found it took a minute after the second instance made the pattern obvious.
    """

    def _run(self, payload):
        import json
        from redthread.models import Beat, SceneSpec, Scene, StorySpec, Thread, ThreadKind, Transition
        from redthread.verify import check_threads
        from tests import fakes

        story = StorySpec(title="T", premise="p", threads=[
            Thread(id="T1", name="one", kind=ThreadKind.MAIN, states=["a", "b"]),
            Thread(id="T2", name="two", kind=ThreadKind.SUBPLOT, states=["a", "b"])])
        spec = SceneSpec(id="s", index=1, summary="x", beats=[Beat(summary="y")])
        spec.thread_ops["T1"] = Transition(post=["the vial is handed back"],
                                           forbid=["the enclave is named"])
        spec.thread_ops["T2"] = Transition(post=["the licence is refused"],
                                           forbid=["the printer confesses"])
        scene = Scene(spec_id="s", index=1, text=fakes.clean_prose(300))
        models, _b = fakes.scripted_models({"threads": json.dumps(payload)})
        return check_threads(scene, spec, story, models)

    def test_a_well_formed_verdict_is_reported(self):
        found = self._run({"requirements": [{"n": 0, "verdict": "missed", "evidence": "no"}],
                           "prohibitions": []})
        self.assertEqual([v.kind for v in found], ["thread_obligation"])

    def test_a_requirement_row_with_no_n_is_dropped(self):
        self.assertEqual(self._run({"requirements": [{"verdict": "missed"}],
                                    "prohibitions": []}), [])

    def test_a_requirement_index_past_the_end_is_dropped(self):
        self.assertEqual(self._run({"requirements": [{"n": 99, "verdict": "missed"}],
                                    "prohibitions": []}), [])

    def test_a_prohibition_row_with_no_n_is_dropped(self):
        self.assertEqual(self._run({"requirements": [],
                                    "prohibitions": [{"violated": True, "quote": "x"}]}), [])

    def test_a_negative_prohibition_index_is_dropped(self):
        self.assertEqual(self._run({"requirements": [],
                                    "prohibitions": [{"n": -1, "violated": True}]}), [])


class TestNoModelIndexIsUsedUnchecked(unittest.TestCase):
    """The generalisation of three bugs found in one hour, made mechanical.

    Every one was the same shape: a number a model returned, used to address a list, with no
    check that it addresses anything. `xs[-1]` raises nothing in Python, so a missing field
    defaulting to -1 silently selects the last element instead of being dropped.

        planner.repeople_solo_scenes   90% of the pass discarded, and a rewrite could have
                                       landed on the wrong scene
        verify.judge_conflicts         a BLOCKER on facts the model was not judging
        verify.check_threads           twice — a verdict reported against the wrong obligation

    A scan is worth more than three fixes, because the fourth instance is the one nobody is
    looking for.
    """

    # Written as a subscript scan plus two content tests rather than as one regex, because the
    # one regex was wrong: `[^)]*?` cannot cross the inner `)` of `row.get(...)`, so it matched
    # none of the three real instances and the test passed by finding nothing.
    #
    # A scan that cannot fail is worse than no scan — which is the lesson this whole file is
    # about, committed here, in the test written to enforce it, an hour after being written down.
    # The two tests below exist so that cannot happen again silently.
    _SUBSCRIPT = re.compile(r"\[([^\[\]]+)\]")
    _NEGATIVE_DEFAULT = re.compile(r",\s*-\d+\s*\)")

    def _unchecked_subscripts(self, text: str) -> list[str]:
        return [m.group(0) for m in self._SUBSCRIPT.finditer(text)
                if "int(" in m.group(1) and self._NEGATIVE_DEFAULT.search(m.group(1))]

    def test_the_scan_catches_the_shapes_it_is_for(self):
        # The three real instances, verbatim, plus a variant.
        for probe in ('tid, text = required[int(row.get("n", -1))]',
                      'old, new = pairs[ int(row.get("pair", -1)) ]',
                      'spec = window[int(row.get("index", -1))]',
                      'x = xs[int(row.get("k", -2))]'):
            self.assertTrue(self._unchecked_subscripts(probe), probe)

    def test_the_scan_leaves_the_safe_shapes_alone(self):
        for safe in ('spec = by_index.get(int(row.get("index", -1)))',
                     'x = xs[index]',
                     'lo = means[int(alpha / 2 * iterations)]',
                     'tail = text[-1]'):
            self.assertEqual(self._unchecked_subscripts(safe), [], safe)

    def test_no_negative_default_reaches_a_subscript(self):
        offenders = []
        for path in sorted(SOURCE_DIR.glob("*.py")):
            for found in self._unchecked_subscripts(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.name}  {found}")
        self.assertEqual(
            offenders, [],
            "a model's number is being used as a subscript with a negative default. `xs[-1]` "
            "raises nothing, so a missing field selects the last element rather than being "
            "dropped. Validate the range instead of catching IndexError:\n  "
            + "\n  ".join(offenders))

    def test_the_dict_lookup_form_is_fine_and_still_used(self):
        # `by_index.get(n)` returns None for anything unknown, so it needs no range check — and
        # the planner uses it in two places that were audited and left alone. This test exists so
        # the scan above is not read as banning every model-returned number.
        source = (SOURCE_DIR / "planner.py").read_text(encoding="utf-8")
        self.assertIn("by_index.get(int(row.get(\"index\", -1)))", source)


class TestTruncationIsNeverSilent(unittest.TestCase):
    """`judge_conflicts` caps its candidate list, and the cap must announce itself.

    It used to bite in 46 of 70 scenes of one book and discard 86% of all candidate pairs by list
    order, in silence — so the gate was far weaker than its design and no run could say so.
    `Ledger._latest_only` removed most of that redundancy (9,560 candidates to 571 on the same
    book), but one scene of 70 still reaches 33 against a cap of 25, so this MINOR is not a
    vacuous check: it fires on real material. That check on a new check is rule VIII, applied to
    the thing rule VIII was written about.
    """

    def _judge(self, older, newer, max_pairs):
        import json
        from redthread.ledger import Ledger
        from redthread.verify import judge_conflicts
        from tests import fakes
        models, _b = fakes.scripted_models({"conflict": json.dumps({"judgements": []})})
        return judge_conflicts(newer, Ledger(older), models, max_pairs=max_pairs)

    def _pair(self, i):
        from redthread.models import Fact, FactKind
        return (Fact(subject=f"thing {i}", predicate="is", object="intact", scene=1,
                     kind=FactKind.DETAIL),
                Fact(subject=f"thing {i}", predicate="is", object="broken", scene=2,
                     kind=FactKind.DETAIL))

    def test_the_cap_biting_emits_a_minor_naming_the_count(self):
        from redthread.models import Severity
        pairs = [self._pair(i) for i in range(6)]
        older = [o for o, _n in pairs]
        newer = [n for _o, n in pairs]
        found = self._judge(older, newer, max_pairs=2)
        truncated = [v for v in found if v.kind == "conflict_check_truncated"]
        self.assertEqual(len(truncated), 1, [v.kind for v in found])
        self.assertIs(truncated[0].severity, Severity.MINOR,
                      "it must not hold a scene; it must only be impossible to miss")
        self.assertIn("6 candidate pairs", truncated[0].detail)
        self.assertIn("4 were not", truncated[0].detail)

    def test_nothing_is_said_when_the_cap_does_not_bite(self):
        pairs = [self._pair(i) for i in range(2)]
        found = self._judge([o for o, _n in pairs], [n for _o, n in pairs], max_pairs=25)
        self.assertEqual([v for v in found if v.kind == "conflict_check_truncated"], [])
