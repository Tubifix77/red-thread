"""The pipeline and the commit gate.

The single most important property in this project is asserted here: **a scene that fails its
checks leaves no trace in dynamic memory.** ConWriter updates memory only after a scene passes
(docs/RESEARCH.md section 4), and if that guarantee leaks, every later scene is built on a
manuscript state that never happened — which is the exact failure the whole architecture exists
to prevent.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread.models import (Beat, Character, SceneSpec, Severity, StorySpec, StyleContract,
                              Thread, ThreadKind, Transition)
from redthread.pipeline import Config, write_all, write_scene
from redthread.project import Project

from tests import fakes


def build_project(root: Path, scenes: int = 2) -> Project:
    story = StorySpec(
        title="Fixture",
        premise="A premise.",
        characters=[Character("siv", "Siv Alderman"), Character("otto", "Otto Renner")],
        threads=[
            Thread(id="T-A", name="Main", kind=ThreadKind.MAIN,
                   states=["dormant", "planted", "complicated", "paid_off"],
                   concealment="a secret", payoff="a payoff"),
        ],
        style=StyleContract(samples=["A short sentence."], forbidden_phrases=["the truth"]),
    )
    plan = []
    targets = {1: "planted", 2: "complicated", 3: "paid_off"}
    for i in range(1, scenes + 1):
        plan.append(SceneSpec(
            id=f"s{i:02d}", index=i, word_target=900, pov="siv",
            characters=["siv", "otto"], setting="the pump house",
            summary="Something happens.", beats=[Beat("a beat"), Beat("another beat")],
            thread_ops={"T-A": Transition(post=["something is established"],
                                          forbid=["revealing the secret"],
                                          to_state=targets.get(i, "paid_off"))}))
    return Project(root, story, plan)


class PipelineCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "run"
        self.project = build_project(self.root)

    def tearDown(self):
        self._tmp.cleanup()


class TestHappyPath(PipelineCase):
    def test_clean_scene_commits(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(), fakes.clean_prose(), fakes.clean_prose())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1))

        self.assertTrue(result.committed, f"held back by: {[str(v) for v in result.violations]}")
        self.assertEqual(result.blockers(), [])
        self.assertEqual(result.majors(), [])

    def test_commit_writes_facts_into_the_ledger(self):
        models, backend = fakes.scripted_models({
            "extract": fakes.facts_json([
                ("Siv", "has", "a paper notebook", "detail"),
                ("Siv", "knows", "the log is wrong", "knowledge"),
            ])})
        backend.queue("draft", fakes.clean_prose())

        write_scene(self.project, self.project.spec_at(1), models, Config(candidates=1))

        self.assertEqual(len(self.project.ledger.facts), 2)
        self.assertTrue(self.project.ledger.knows("Siv", scene=2))

    def test_commit_advances_thread_state_and_records_the_move(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose())

        write_scene(self.project, self.project.spec_at(1), models, Config(candidates=1))

        self.assertEqual(self.project.story.thread("T-A").current_state, "planted")
        self.assertEqual(len(self.project.history), 1)
        self.assertEqual(self.project.history[0].to_state, "planted")


class TestCommitGate(PipelineCase):
    """Nothing may enter dynamic memory until the scene passes."""

    def test_blocker_prevents_commit(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.prose_with_heading())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        self.assertFalse(result.committed)
        self.assertTrue(result.blockers())

    def test_blocked_scene_leaves_no_facts_behind(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.prose_with_heading())

        write_scene(self.project, self.project.spec_at(1), models,
                    Config(candidates=1, max_repairs=0))

        self.assertEqual(self.project.ledger.facts, [],
                         "a rejected scene contaminated the ledger")

    def test_blocked_scene_does_not_advance_thread_state(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.prose_with_heading())

        write_scene(self.project, self.project.spec_at(1), models,
                    Config(candidates=1, max_repairs=0))

        self.assertEqual(self.project.story.thread("T-A").current_state, "dormant")
        self.assertEqual(self.project.history, [])

    def test_continuity_contradiction_is_a_blocker(self):
        """Stage two of DOME's detection: the model judges a flagged pair as contradictory."""
        self.project.ledger.add(
            __import__("redthread.models", fromlist=["Fact"]).Fact(
                "Siv", "eye colour", "grey", 0,
                __import__("redthread.models", fromlist=["FactKind"]).FactKind.DETAIL))

        models, backend = fakes.scripted_models({
            "extract": fakes.facts_json([("Siv", "eye colour", "brown", "detail")]),
            "conflict": fakes.conflict_found(0, "eye colour cannot change"),
        })
        backend.queue("draft", fakes.clean_prose())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        self.assertFalse(result.committed)
        self.assertIn("continuity_contradiction", {v.kind for v in result.violations})

    def test_violated_prohibition_is_a_blocker(self):
        """A premature reveal cannot be committed: once the reader knows, no later scene can
        un-know it."""
        models, backend = fakes.scripted_models({
            "threads": fakes.threads_one_prohibition_violated(0)})
        backend.queue("draft", fakes.clean_prose())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        self.assertFalse(result.committed)
        self.assertIn("thread_prohibition", {v.kind for v in result.violations})

    def test_missed_thread_obligation_holds_the_scene_back(self):
        models, backend = fakes.scripted_models({"threads": fakes.threads_one_missed(0)})
        backend.queue("draft", fakes.clean_prose())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        self.assertFalse(result.committed)
        self.assertTrue(result.majors())

    def test_force_commits_despite_majors_but_never_despite_blockers(self):
        models, backend = fakes.scripted_models({"threads": fakes.threads_one_missed(0)})
        backend.queue("draft", fakes.clean_prose())
        forced = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0,
                                    allow_commit_with_majors=True))
        self.assertTrue(forced.committed)

        project2 = build_project(self.root.parent / "run2")
        models2, backend2 = fakes.scripted_models()
        backend2.queue("draft", fakes.prose_with_heading())
        blocked = write_scene(project2, project2.spec_at(1), models2,
                              Config(candidates=1, max_repairs=0,
                                     allow_commit_with_majors=True))
        self.assertFalse(blocked.committed, "a blocker must survive allow_commit_with_majors")

    def test_extraction_failure_blocks_the_commit(self):
        """If facts cannot be extracted, continuity cannot be checked, so the scene is unsafe
        to commit even though the prose may be fine."""
        models, backend = fakes.scripted_models({"extract": "sorry, I can't do that"})
        backend.queue("draft", fakes.clean_prose())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        self.assertFalse(result.committed)
        self.assertIn("extraction_failed", {v.kind for v in result.violations})


class TestSilentFailureGuards(PipelineCase):
    """Both of these came from the first real write run, on a local 8B."""

    def test_an_empty_extraction_blocks_the_commit(self):
        """The dangerous case: JSON parses, so nothing errors, but no facts come back.

        A real run returned zero facts for a 591-word scene. The ledger stayed empty, every later
        brief would have said "nothing established yet", and continuity would have failed with no
        error anywhere.
        """
        models, backend = fakes.scripted_models({"extract": fakes.facts_json([])})
        backend.queue("draft", fakes.clean_prose())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        self.assertFalse(result.committed)
        self.assertIn("extraction_empty", {v.kind for v in result.violations})
        self.assertEqual(self.project.ledger.facts, [])

    def test_an_empty_extraction_is_tolerated_on_a_tiny_scene(self):
        """A fragment may genuinely establish nothing; the guard is for real scenes."""
        models, backend = fakes.scripted_models({"extract": fakes.facts_json([])})
        backend.queue("draft", "She waited. Nothing came.")
        spec = self.project.spec_at(1)
        spec.word_target = 5

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=0))

        self.assertNotIn("extraction_empty", {v.kind for v in result.violations})

    def test_a_short_scene_is_expanded_not_repaired(self):
        """The repair prompt forbids changing length, so a short scene sent there can never be
        salvaged — a real run 'repaired' 564 words to 591 and was held back anyway."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(500))
        backend.queue("draft", fakes.clean_prose(900))  # the expansion reply

        spec = self.project.spec_at(1)
        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=1))

        expansions = [p for role, p in backend.calls if "so it is short by" in p]
        self.assertEqual(len(expansions), 1, "the expansion prompt should have been used")
        self.assertNotIn("Fix ONLY the problems listed", expansions[0])
        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")

    def test_the_expansion_prompt_carries_the_beats(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(500))
        backend.queue("draft", fakes.clean_prose(900))
        write_scene(self.project, self.project.spec_at(1), models,
                    Config(candidates=1, max_repairs=1))

        expansion = [p for role, p in backend.calls if "so it is short by" in p][0]
        self.assertIn("a beat", expansion)
        self.assertIn("another beat", expansion)

    def test_an_expansion_that_came_back_shorter_is_rejected(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(500))
        backend.queue("draft", "Three words only.")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=1))

        self.assertEqual(result.repairs, 0)
        self.assertTrue(any("expand call failed" in n for n in result.notes), result.notes)

    def test_an_over_long_scene_still_goes_to_repair(self):
        """Over-length is MINOR and is not an expansion problem."""
        models, backend = fakes.scripted_models({"threads": fakes.threads_one_missed(0)})
        backend.queue("draft", fakes.clean_prose(1400))
        backend.queue("repair", fakes.clean_prose(900))

        write_scene(self.project, self.project.spec_at(1), models,
                    Config(candidates=1, max_repairs=1))

        self.assertTrue(any("Fix ONLY the problems listed" in p for _, p in backend.calls))
        self.assertFalse(any("so it is short by" in p for _, p in backend.calls))


class TestCandidateSelection(PipelineCase):
    def test_cleanest_candidate_is_chosen(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft",
                      fakes.prose_with_heading(),        # blocker
                      fakes.prose_with_somatic_tics(),   # major
                      fakes.clean_prose())               # clean

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=3, max_repairs=0))

        self.assertEqual(result.candidates_drafted, 3)
        self.assertTrue(result.committed, f"picked badly: {[str(v) for v in result.violations]}")
        self.assertNotIn("## Chapter One", result.scene.text)

    def test_all_candidates_failing_still_returns_the_best(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.prose_with_heading(), fakes.prose_with_somatic_tics())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=2, max_repairs=0))

        self.assertFalse(result.committed)
        # the somatic draft is MAJOR, the heading draft is BLOCKER — the former must win
        self.assertEqual(result.blockers(), [])


class TestRepair(PipelineCase):
    def test_repair_fixes_a_major_and_commits(self):
        """Quoteless majors (a missed thread obligation has no offending span) still go through
        whole-scene repair; quote-bearing ones now route to the surgical path instead."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose())
        # First verify: the obligation is missed. After the repair: met. Queued in call order —
        # the queue is consumed before the role's default.
        backend.queue("threads", fakes.threads_one_missed(0), fakes.threads_all_met())
        backend.queue("repair", fakes.clean_prose(905))

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertEqual(result.repairs, 1)
        self.assertTrue(result.committed, f"held back by: {[str(v) for v in result.violations]}")

    def test_repair_that_does_not_improve_is_discarded(self):
        """A repair trading one problem for another is not progress, and accepting it is how
        repair loops start oscillating."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.prose_with_somatic_tics())
        backend.queue("repair", fakes.prose_with_heading())  # strictly worse

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertTrue(any("did not improve; discarded" in n for n in result.notes),
                        result.notes)
        self.assertEqual(result.blockers(), [], "the worse version must not be kept")

    def test_a_bad_attempt_does_not_abandon_the_repair_budget(self):
        """`break` on the first non-improving attempt made max_repairs=2 behave as 1."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose())
        backend.queue("threads", fakes.threads_one_missed(0),   # initial verify: missed
                      fakes.threads_one_missed(0),              # after the bad attempt: still
                      fakes.threads_all_met())                  # after the good one: met
        backend.queue("repair", fakes.prose_with_heading(900))  # worse, discarded
        backend.queue("repair", fakes.clean_prose(905))         # good, should be reached

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertEqual(backend.count("repair"), 2, "the second attempt was never made")
        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")

    def test_an_expansion_that_fixes_length_is_kept_even_without_a_better_score(self):
        """The deadlock this rule exists to break.

        An expansion that reaches the target while introducing a different major scores no better
        on the tuple. Reverting it leaves a permanently short scene, because the repair prompt is
        forbidden from changing length — so no later attempt can rescue it.
        """
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(500))
        # Right length now, but carries a fresh major of its own.
        backend.queue("draft", fakes.prose_with_somatic_tics(900))
        backend.queue("repair", fakes.clean_prose(900))

        spec = self.project.spec_at(1)
        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=2))

        self.assertNotIn("length", {v.kind for v in result.violations},
                         "the expansion should have been kept and length resolved")
        self.assertGreater(result.scene.word_count(), 700)

    def test_truncated_repair_is_rejected(self):
        """A 'repair' that returns a third of the scene has rewritten, not repaired."""
        models, backend = fakes.scripted_models({"threads": fakes.threads_one_missed(0)})
        backend.queue("draft", fakes.clean_prose())
        backend.queue("repair", "She wrote it down.")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=1))

        self.assertEqual(result.repairs, 0)
        self.assertIn("repair call failed; keeping previous draft", result.notes)

    def test_repair_budget_is_bounded(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.prose_with_somatic_tics())
        for _ in range(6):
            backend.queue("repair", fakes.prose_with_somatic_tics() + " Another sentence here.")

        write_scene(self.project, self.project.spec_at(1), models,
                    Config(candidates=1, max_repairs=2))

        self.assertLessEqual(backend.count("repair"), 2)


class TestOrdering(PipelineCase):
    def test_writing_out_of_order_is_refused(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose())

        result = write_scene(self.project, self.project.spec_at(2), models, Config(candidates=1))

        self.assertFalse(result.committed)
        self.assertIn("out_of_order", {v.kind for v in result.violations})
        self.assertEqual(backend.count("draft"), 0, "should refuse before spending a draft call")

    def test_out_of_order_can_be_overridden(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose())

        result = write_scene(self.project, self.project.spec_at(2), models,
                             Config(candidates=1, allow_out_of_order=True))

        self.assertTrue(result.committed)

    def test_write_all_halts_at_the_first_rejection(self):
        """Continuing past a rejected scene means writing later briefs against a ledger that is
        missing a scene of facts."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(), fakes.prose_with_heading())

        results = write_all(self.project, models, Config(candidates=1, max_repairs=0))

        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].committed)
        self.assertFalse(results[1].committed)

    def test_write_all_skips_already_committed_scenes(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose())
        write_scene(self.project, self.project.spec_at(1), models, Config(candidates=1))

        backend.queue("draft", fakes.clean_prose())
        results = write_all(self.project, models, Config(candidates=1))

        self.assertEqual([r.scene.index for r in results], [2])


class TestSeamIsFedForward(PipelineCase):
    def test_second_scene_brief_receives_the_first_scene_tail(self):
        """The chunk-buffer prefix: scene 2's brief must contain the verbatim end of scene 1."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose())
        write_scene(self.project, self.project.spec_at(1), models, Config(candidates=1))

        tail_words = self.project.committed_scenes()[0].text.split()[-12:]
        backend.queue("draft", fakes.clean_prose())
        write_scene(self.project, self.project.spec_at(2), models, Config(candidates=1))

        drafts = [prompt for role, prompt in backend.calls if role == "draft"]
        self.assertIn(" ".join(tail_words), drafts[-1])

    def test_second_scene_brief_receives_the_first_scene_facts(self):
        models, backend = fakes.scripted_models({
            "extract": fakes.facts_json([("Siv", "has", "a green notebook", "detail")])})
        backend.queue("draft", fakes.clean_prose())
        write_scene(self.project, self.project.spec_at(1), models, Config(candidates=1))

        backend.queue("draft", fakes.clean_prose())
        write_scene(self.project, self.project.spec_at(2), models, Config(candidates=1))

        drafts = [prompt for role, prompt in backend.calls if role == "draft"]
        self.assertIn("a green notebook", drafts[-1])


if __name__ == "__main__":
    unittest.main()


class TestSurgicalRepair(PipelineCase):
    """Sentence-local repair: what ConWriter's 'revise only the conflict-bearing sentences'
    actually means. Whole-scene repair on a small local model changed nothing across five
    attempts on a real run; splicing one sentence is a task the same model can do — and for
    delete-remedy kinds, code does it with no model at all."""

    GLOSSY = (" And in that moment, she understood everything the founders had hidden from "
              "the town for sixty years.")

    def test_deterministic_gloss_is_deleted_without_a_model_call(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(900) + self.GLOSSY)

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")
        self.assertNotIn("in that moment", result.scene.text)
        self.assertEqual(backend.count("repair"), 0, "no whole-scene repair should have run")
        self.assertEqual(backend.count("surgical"), 0, "deletion needs no model call")
        self.assertTrue(any("deleted the thematic_gloss sentence" in n for n in result.notes),
                        result.notes)

    def test_quote_bearing_violation_takes_the_surgical_path(self):
        """A forbidden phrase carries its own quote and locates exactly."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(880)
                      + " She finally saw the truth of the whole arrangement laid out plain.")
        backend.queue("surgical",
                      "She saw the shape of the arrangement laid out plain on the bench.")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertEqual(backend.count("surgical"), 1)
        self.assertEqual(backend.count("repair"), 0)
        self.assertNotIn("the truth", result.scene.text.lower())
        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")

    def test_unusable_surgical_reply_is_skipped_not_spliced(self):
        """A replacement three times the original has ignored the instruction."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(880)
                      + " She finally saw the truth of the whole arrangement laid out plain.")
        backend.queue("surgical", "word " * 200)
        backend.queue("repair", fakes.clean_prose(900))

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertNotIn("word word word", result.scene.text)

    def test_quoteless_violations_fall_back_to_whole_scene_repair(self):
        models, backend = fakes.scripted_models({"threads": fakes.threads_one_missed(0)})
        backend.queue("draft", fakes.clean_prose(900))
        backend.queue("repair", fakes.clean_prose(905))

        write_scene(self.project, self.project.spec_at(1), models,
                    Config(candidates=1, max_repairs=1))

        self.assertEqual(backend.count("surgical"), 0)
        self.assertEqual(backend.count("repair"), 1)


    def test_mixed_quoteless_and_quoted_majors_route_to_whole_scene_first(self):
        """A quoteless major means something must be ADDED; surgical can only remove or
        replace. On a real run the quoted tells won the routing every round and the missed
        obligation was never repaired."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(880)
                      + " She finally saw the truth of the whole arrangement laid out plain.")
        backend.queue("threads", fakes.threads_one_missed(0), fakes.threads_all_met())
        backend.queue("repair", fakes.clean_prose(905))

        write_scene(self.project, self.project.spec_at(1), models,
                    Config(candidates=1, max_repairs=2))

        roles = [r for r, _ in backend.calls]
        self.assertIn("repair", roles, "the additive whole-scene path never ran")
        self.assertLess(roles.index("repair"),
                        roles.index("surgical") if "surgical" in roles else len(roles),
                        "whole-scene must run before surgical when a quoteless major exists")

    def test_gloss_below_target_is_rewritten_not_deleted(self):
        """Deleting is free but costs words: a real run deleted its way from 918 to 772 words.
        At or below target, gloss is rewritten into something concrete instead."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(810)
                      + " And in that moment, she understood everything the founders had hidden.")
        backend.queue("surgical", "She photographed the page and clipped the print to the log.")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertEqual(backend.count("surgical"), 1,
                         "below target the gloss should be rewritten, which needs a model call")
        self.assertNotIn("in that moment", result.scene.text)
        self.assertIn("photographed the page", result.scene.text)


class TestJudgeEvidence(PipelineCase):
    """A local judge sometimes 'quotes' a paraphrase of its own reasoning rather than the
    scene. Evidence that does not locate in the text is not actionable."""

    def test_probe_finding_with_fabricated_quote_is_dropped(self):
        finding = json.dumps({"findings": [{
            "tell": "thematic_gloss", "present": True, "severity": "major",
            "quote": "The narration explicitly states the theme of institutional decay",
            "why": "states the theme"}]})
        models, backend = fakes.scripted_models({"tells": finding})
        backend.queue("draft", fakes.clean_prose(900))

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        self.assertTrue(result.committed,
                        f"a hallucinated judgement held the scene back: "
                        f"{[str(v) for v in result.violations]}")

    def test_probe_finding_with_real_quote_is_kept_as_advisory(self):
        """Calibrated on the target judge: it flags pure physical description as gloss 3/3,
        so probe findings are MINOR — logged for the human, never blocking. The deterministic
        gloss check carries the blocking power (and here it also fires, so the scene is still
        held back — by the check that earns it)."""
        text = fakes.clean_prose(900) + " That was what it meant to keep a town alive."
        finding = json.dumps({"findings": [{
            "tell": "thematic_gloss", "present": True, "severity": "major",
            "quote": "what it meant to keep a town alive",
            "why": "states the theme"}]})
        models, backend = fakes.scripted_models({"tells": finding})
        backend.queue("draft", text)

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        tells = [v for v in result.violations if v.kind == "tell_thematic_gloss"]
        self.assertTrue(tells, "the evidenced finding should be kept")
        self.assertTrue(all(v.severity is Severity.MINOR for v in tells),
                        "probe findings are advisory at this judge size")
        self.assertIn("thematic_gloss", {v.kind for v in result.violations},
                      "the deterministic check still carries the block")

    def test_prohibition_without_locatable_quote_is_major_not_blocker(self):
        models, backend = fakes.scripted_models({
            "threads": fakes.threads_one_prohibition_violated(0)})
        backend.queue("draft", fakes.clean_prose(900))

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        kinds = {(v.kind, v.severity.value) for v in result.violations}
        self.assertIn(("thread_prohibition", "major"), kinds)
        self.assertNotIn(("thread_prohibition", "blocker"), kinds)

    def test_prohibition_with_locatable_quote_stays_a_blocker(self):
        text = fakes.clean_prose(880) + " She told him everything about the founders' figure."
        prohibition = json.dumps({
            "requirements": [{"n": i, "verdict": "met"} for i in range(12)],
            "prohibitions": [{"n": 0, "violated": True,
                              "quote": "She told him everything about the founders' figure"}]
            + [{"n": i, "violated": False} for i in range(1, 12)]})
        models, backend = fakes.scripted_models({"threads": prohibition})
        backend.queue("draft", text)

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        self.assertIn(("thread_prohibition", "blocker"),
                      {(v.kind, v.severity.value) for v in result.violations})
