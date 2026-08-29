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

from redthread.models import (Beat, Character, Scene, SceneSpec, Severity, StorySpec,
                              StyleContract,
                              Thread, ThreadKind, Transition, Violation)
from redthread import checks
from redthread.pipeline import (Config, _deseam, _expand_passage, _fulfil, _reseam,
                                write_all, write_scene)
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

        # The unusable reply consumes a round and is retried, not spliced and not forfeited.
        self.assertTrue(any("expand attempt 1 unusable; retrying" in n
                            for n in result.notes), result.notes)
        self.assertNotIn("Three words only.", result.scene.text)

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
        repair loops start oscillating. A quoteless major routes to whole-scene repair; the
        reply here trades it for a format BLOCKER, which must be discarded."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(500))          # length major, quoteless path
        backend.queue("draft", fakes.prose_with_heading(900))   # the "expansion": strictly worse

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=1))

        self.assertTrue(any("did not improve; discarded" in n for n in result.notes),
                        result.notes)
        self.assertEqual(result.blockers(), [], "the worse version must not be kept")

    def test_a_bad_attempt_does_not_abandon_the_repair_budget(self):
        """`break` on the first non-improving attempt made max_repairs=2 behave as 1.

        Multi-attempt convergence lives in the deterministic loop (phase A); the judge's
        findings deliberately get one response, not a negotiation.
        """
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(500))          # short: a length major
        backend.queue("draft", fakes.clean_prose(520, 1))       # still short, discarded
        backend.queue("draft", fakes.clean_prose(900, 1))       # resolved, kept

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        expansions = [p for role, p in backend.calls if "so it is short by" in p]
        self.assertEqual(len(expansions), 2, "the second attempt was never made")
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

        # This truncation hits phase C — the single bounded response to the judge — whose
        # failure wording differs from phase A's retry loop.
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
        # A different closing, or scene 2 ends in scene 1's exact words and the seam repair —
        # not the brief — becomes the last prompt the backend saw.
        backend.queue("draft", fakes.clean_prose(variant=1))
        write_scene(self.project, self.project.spec_at(2), models, Config(candidates=1))

        drafts = [prompt for role, prompt in backend.calls if role == "draft"]
        self.assertIn(" ".join(tail_words), drafts[-1])

    def test_second_scene_brief_receives_the_first_scene_facts(self):
        models, backend = fakes.scripted_models({
            "extract": fakes.facts_json([("Siv", "has", "a green notebook", "detail")])})
        backend.queue("draft", fakes.clean_prose())
        write_scene(self.project, self.project.spec_at(1), models, Config(candidates=1))

        backend.queue("draft", fakes.clean_prose(variant=1))
        write_scene(self.project, self.project.spec_at(2), models, Config(candidates=1))

        drafts = [prompt for role, prompt in backend.calls if role == "draft"]
        self.assertIn("a green notebook", drafts[-1])


if __name__ == "__main__":
    unittest.main()


class TestSeamRepair(PipelineCase):
    """A seam is a region problem, so its repair replaces a region.

    Scene 4 of a live 27-scene run ended in two sentences lifted verbatim from scene 3.
    Surgical repair rewrote one of them per round; `check_seam` compares the whole last 25
    words, so it kept firing and the scene burned all five rounds without ever committing.
    """

    def _commit_first(self, backend, models):
        backend.queue("draft", fakes.clean_prose())
        return write_scene(self.project, self.project.spec_at(1), models, Config(candidates=1))

    def test_copied_ending_is_deleted_in_code(self):
        models, backend = fakes.scripted_models()
        self._commit_first(backend, models)

        # Scene 2 ends in scene 1's exact words — the failure the live run hit.
        backend.queue("draft", fakes.clean_prose())
        result = write_scene(self.project, self.project.spec_at(2), models,
                             Config(candidates=1, max_repairs=3))

        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")
        self.assertTrue(any("deseam: deleted" in n for n in result.notes), result.notes)
        self.assertEqual(backend.count("surgical"), 0,
                         "a seam must not be routed to sentence-local repair")
        self.assertEqual(backend.count("reseam"), 0,
                         "deleting a duplicated ending needs no model")

    def test_a_long_copied_opening_is_still_reachable(self):
        """Scene 7 of a live run reproduced the whole of scene 6's closing — eleven sentences,
        172 words — before beginning its own story. A four-sentence cap could not reach it, so
        nothing could. The bound is the fraction of the scene duplicated, not a sentence count."""
        previous = fakes.clean_prose(400, variant=2)
        tail = " ".join(previous.split()[-150:])
        copied = Scene(spec_id="s2", index=2,
                       text=tail + " " + fakes.clean_prose(750, variant=5))
        flagged = checks.check_seam(copied, tail)
        self.assertIn("seam_echo", {v.kind for v in flagged})

        notes: list[str] = []
        cut = _deseam(copied, tail, flagged, notes)

        self.assertIsNotNone(cut, notes)
        self.assertEqual(checks.check_seam(Scene(spec_id="s2", index=2, text=cut), tail), [])
        self.assertTrue(any("deseam: deleted" in n for n in notes), notes)

    def test_a_scene_that_echoes_at_both_ends_is_fixed_one_end_per_round(self):
        """Scene 12 of a live run opened on the previous scene's words and closed on them too.
        Trimming the ending can never clear the opening, so an acceptance test that demanded
        both be gone rejected every deletion that worked."""
        previous = fakes.clean_prose(400, variant=3)
        tail = " ".join(previous.split()[-150:])
        text = tail + " " + fakes.clean_prose(700, variant=6) + " " + tail

        for expected in ("seam_tail_copy", "seam_echo"):
            flagged = checks.check_seam(Scene(spec_id="s2", index=2, text=text), tail)
            self.assertIn(expected, {v.kind for v in flagged})
            notes: list[str] = []
            text = _deseam(Scene(spec_id="s2", index=2, text=text), tail, flagged, notes)
            self.assertIsNotNone(text, f"no cut for {expected}: {notes}")

        self.assertEqual(checks.check_seam(Scene(spec_id="s2", index=2, text=text), tail), [])

    def test_a_cut_that_trades_a_seam_for_a_shortfall_is_kept(self):
        """`_deseam` cut 155 copied words off scene 21 of a live run, cleared the seam, dropped
        the scene under its target, and was discarded as "no improvement" — twice, then
        sidelined, leaving the copy in the manuscript. Clearing the problem an action was chosen
        for is progress even when the violation count ties."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(950))
        first = write_scene(self.project, self.project.spec_at(1), models, Config(candidates=1))
        self.assertTrue(first.committed)

        tail = " ".join(first.scene.text.split()[-150:])
        # Just over target, so cutting the copied opening lands it just under: one MAJOR either
        # way, which is exactly the tie that used to throw the cut away.
        backend.queue("draft", tail + " " + fakes.clean_prose(900, variant=7))
        result = write_scene(self.project, self.project.spec_at(2), models,
                             Config(candidates=1, max_repairs=4))

        self.assertTrue(any("deseam: deleted" in n for n in result.notes), result.notes)
        self.assertFalse(any("deseam attempt" in n and "discarded" in n for n in result.notes),
                         result.notes)
        self.assertNotIn("seam_echo", {v.kind for v in result.violations})

    def test_clearing_one_end_counts_even_when_the_other_remains(self):
        """`_deseam` fixes one end per call by design, so a scene echoing at both ends still has
        `seam_echo` after the tail copy is cut. Requiring every target kind gone judged that cut
        a failure and discarded it — twice, then sidelined — on a live scene."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(950))
        first = write_scene(self.project, self.project.spec_at(1), models, Config(candidates=1))
        self.assertTrue(first.committed)

        tail = " ".join(first.scene.text.split()[-150:])
        both_ends = tail + " " + fakes.clean_prose(700, variant=5) + " " + tail
        backend.queue("draft", both_ends)
        result = write_scene(self.project, self.project.spec_at(2), models,
                             Config(candidates=1, max_repairs=3))

        cuts = [n for n in result.notes if "deseam: deleted" in n]
        self.assertTrue(cuts, result.notes)
        self.assertFalse(any("deseam attempt" in n and "introduced" in n
                             for n in result.notes), result.notes)

    def test_deletion_is_bounded_by_sentence_count_as_well(self):
        """A live run cut 34 sentences — a quarter of the scene — off one opening to clear a
        single echo. The word fraction allowed it; the largest genuine case needed eleven."""
        previous = fakes.clean_prose(900, variant=2)
        tail = " ".join(previous.split()[-150:])
        # The whole scene echoes: no cut within the cap can clear it, so none should be made.
        copied = Scene(spec_id="s2", index=2, text=previous + " " + previous)
        flagged = checks.check_seam(copied, tail)
        notes: list[str] = []

        _deseam(copied, tail, flagged, notes)

        for note in notes:
            if "deseam: deleted" in note:
                dropped = int(note.split("deleted ")[1].split(" ")[0])
                self.assertLessEqual(dropped, 12, note)

    def test_deletion_is_refused_when_it_would_gut_the_scene(self):
        """Past a few sentences the copy is not a seam artefact but an empty scene."""
        first = Scene(spec_id="s1", index=1, text=fakes.clean_prose(120))
        tail = " ".join(first.text.split()[-25:])
        short = Scene(spec_id="s2", index=2, text=" ".join(first.text.split()[-90:]))
        notes: list[str] = []
        flagged = checks.check_seam(short, tail)

        self.assertTrue(any(v.kind == "seam_tail_copy" for v in flagged))
        self.assertIsNone(_deseam(short, tail, flagged, notes))
        self.assertEqual(notes, [])

    def test_a_rewrite_that_still_echoes_is_discarded(self):
        """The model is asked for fresh wording and hands back the copy anyway — as qwen3:8b
        did twice in a row on the live run, in about a second each time."""
        models, backend = fakes.scripted_models()
        first = self._commit_first(backend, models)
        tail = " ".join(first.scene.text.split()[-25:])
        copy = Scene(spec_id="s2", index=2, text=fakes.clean_prose())
        flagged = checks.check_seam(copy, tail)
        backend.queue("reseam", " ".join(first.scene.text.split()[-40:]))

        notes: list[str] = []
        self.assertIsNone(_reseam(copy, tail, flagged, models, notes))
        self.assertTrue(any("still echoes the previous scene" in n for n in notes), notes)

    def test_the_rewrite_prompt_never_shows_the_forbidden_text(self):
        """Handing a small model the words it must not reuse is handing it the words to
        produce. The verification is in code; the prompt only needs the block to replace."""
        models, backend = fakes.scripted_models()
        first = self._commit_first(backend, models)
        tail = " ".join(first.scene.text.split()[-25:])
        copy = Scene(spec_id="s2", index=2, text=fakes.clean_prose())

        _reseam(copy, tail, checks.check_seam(copy, tail), models, [])

        prompts = [p for role, p in backend.calls if role == "reseam"]
        self.assertEqual(len(prompts), 1)
        # The block being replaced is itself the copy, so those words are unavoidably present
        # once. What was removed is the second copy, under a heading announcing it as forbidden.
        self.assertEqual(prompts[0].count(" ".join(tail.split()[:8])), 1)
        self.assertNotIn("FROM THE PREVIOUS SCENE", prompts[0])

    def test_exhausted_actions_stop_the_loop_early(self):
        """Every action tried twice and failed means the remaining budget buys nothing."""
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        # A brief leak: the draft narrates its own beat back, and every surgical rewrite narrates
        # it again. `brief_leak` is a craft violation, not a contract one, so there is no
        # deletion fallback and no round at which this starts working.
        beat = ("She copies the altered column into the spare ledger and initials the bottom "
                "of the page")
        spec.beats = [Beat(beat)]
        backend.queue("draft", fakes.clean_prose(870) + " " + beat + ".")
        backend.queue("surgical", *[beat + "."] * 8)

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=8))

        self.assertFalse(result.committed)
        self.assertLess(result.repairs, 8, "the loop should stop before the budget runs out")
        self.assertTrue(any("tried twice and failed" in n for n in result.notes), result.notes)


BREAK = "\n\n"


class TestExpansionIsLocal(PipelineCase):
    """Whole-scene expansion asks a small model to reproduce every word it was given and add
    more. A live run watched it come back shorter twice, get sidelined, and lose a scene that
    `_deseam` had just correctly repaired — the seam fixed, the length not."""

    def _scene(self) -> Scene:
        paragraphs = [fakes.clean_prose(220, variant=1), "He set it down and waited.",
                      fakes.clean_prose(220, variant=4)]
        return Scene(spec_id="s1", index=1, text=BREAK.join(paragraphs))

    def test_the_thinnest_interior_passage_is_the_one_rewritten(self):
        models, backend = fakes.scripted_models()
        scene = self._scene()
        spec = self.project.spec_at(1)
        spec.word_target = scene.word_count() + 300

        notes: list[str] = []
        grown = _expand_passage(scene, spec, models, notes)

        self.assertIsNotNone(grown, notes)
        self.assertGreater(len(grown.split()), scene.word_count())
        self.assertTrue(any("staged the thinnest passage" in n for n in notes), notes)
        prompts = [p for role, p in backend.calls if role == "passage"]
        self.assertEqual(len(prompts), 1)
        self.assertIn("He set it down and waited.", prompts[0])

    def test_the_opening_and_closing_paragraphs_are_never_touched(self):
        """The shortfall is usually there *because* `_deseam` just cut a copied seam. An
        expansion that rewrote either end could hand the seam straight back."""
        models, _ = fakes.scripted_models()
        scene = self._scene()
        spec = self.project.spec_at(1)
        spec.word_target = scene.word_count() + 300

        grown = _expand_passage(scene, spec, models, [])

        paragraphs = grown.split(BREAK)
        original = scene.text.split(BREAK)
        self.assertTrue(paragraphs[0].startswith(original[0][:40]))
        self.assertTrue(paragraphs[-1].endswith(original[-1][-40:]))

    def test_a_scene_of_one_paragraph_falls_back(self):
        models, backend = fakes.scripted_models()
        scene = Scene(spec_id="s1", index=1, text=fakes.clean_prose(400))
        spec = self.project.spec_at(1)
        spec.word_target = 900

        self.assertIsNone(_expand_passage(scene, spec, models, []))
        self.assertEqual(backend.count("passage"), 0)


class TestUnquotedLeak(PipelineCase):
    """A `thread_prohibition` the judge cannot quote had no repair at all.

    `_surgical` needs a span, `_fulfil` answers obligations, and whole-scene repair is the one
    that does not work on a small model. Scene 6 of a clean-slate run was held by exactly that,
    with both whole-scene attempts failing on the call.
    """

    LEAK = " He said the fissure ran under the sluice."

    def _models(self):
        # The judge reports the violation with no quote, so nothing can be located.
        return fakes.scripted_models({
            "threads": fakes.threads_one_prohibition_violated(0, quote="")})

    def test_the_named_sentence_is_cut(self):
        models, backend = self._models()
        backend.queue("draft", fakes.clean_prose(950) + self.LEAK)
        backend.queue("excise", self.LEAK.strip())
        # Second look at the cut scene: the leak is gone.
        backend.queue("threads", fakes.threads_one_prohibition_violated(0, quote=""),
                      fakes.threads_all_met())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=3))

        self.assertTrue(any("excise: cut the sentence" in n for n in result.notes), result.notes)
        self.assertNotIn("fissure ran under", result.scene.text)

    def test_an_invented_quote_is_refused(self):
        """A quote that does not locate is a quote the judge invented, and is refused the same
        way an unevidenced finding is refused everywhere else here."""
        models, backend = self._models()
        backend.queue("draft", fakes.clean_prose(950) + self.LEAK)
        backend.queue("excise", "A sentence that appears nowhere in this scene at all.")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=3))

        self.assertTrue(any("not in the scene; discarded" in n for n in result.notes),
                        result.notes)
        self.assertIn("fissure ran under", result.scene.text)

    def test_none_is_taken_at_its_word(self):
        models, backend = self._models()
        backend.queue("draft", fakes.clean_prose(950) + self.LEAK)
        backend.queue("excise", "NONE")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=3))

        self.assertTrue(any("could not point at a sentence" in n for n in result.notes),
                        result.notes)


class TestSecondResponsePass(PipelineCase):
    """A leaked concealment is usually carried by more than one sentence.

    `_surgical` can only delete the sentences whose quotes located this round. Scene 4 of a
    clean-slate run had its leaking sentence cut, the judge still read the reveal in what was
    left, and one response pass was all there was.
    """

    FIRST = " He said the fissure ran under the sluice."
    SECOND = " The crack under the sluice was where the water went."

    def test_a_second_pass_runs_while_a_blocker_stands(self):
        models, backend = fakes.scripted_models()
        backend.queue("threads",
                      fakes.threads_one_prohibition_violated(0, quote=self.FIRST.strip()),
                      fakes.threads_one_prohibition_violated(0, quote=self.SECOND.strip()),
                      fakes.threads_all_met())
        backend.queue("draft", fakes.clean_prose(950) + self.FIRST + self.SECOND)

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=4))

        cuts = [n for n in result.notes if "deleted the thread_prohibition" in n]
        self.assertEqual(len(cuts), 2, result.notes)
        self.assertNotIn("fissure ran under", result.scene.text)
        self.assertNotIn("crack under the sluice", result.scene.text)

    def test_no_second_pass_once_the_blocker_is_gone(self):
        models, backend = fakes.scripted_models()
        backend.queue("threads",
                      fakes.threads_one_prohibition_violated(0, quote=self.FIRST.strip()),
                      fakes.threads_all_met())
        backend.queue("draft", fakes.clean_prose(950) + self.FIRST)

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=4))

        cuts = [n for n in result.notes if "deleted the thread_prohibition" in n]
        self.assertEqual(len(cuts), 1, result.notes)
        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")


class TestForbiddenPhraseRepair(PipelineCase):
    """The fixture story forbids "the truth"."""

    OFFENDER = " She finally saw the truth of the whole arrangement laid out plain."

    def test_a_rewrite_that_keeps_the_phrase_is_refused(self):
        """`check_forbidden` quotes the containing sentence — it has to, or the span cannot be
        located — and the verification here was still asking whether that whole sentence came
        back, which it never does. Every rewrite passed, and scene 6 of a live run spliced in two
        replacements that both still said the banned word."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(1100) + self.OFFENDER)
        backend.queue("surgical", "She saw the truth of it laid out on the bench.")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=1))

        self.assertTrue(any("forbidden_phrase rewrite failed verification" in n
                            for n in result.notes), result.notes)

    def test_an_unfixable_sentence_is_deleted_even_under_target(self):
        """Scene 12 of a live run had the same banned word survive three rewrites and be skipped
        every time, because the scene was under target and deletion was refused. Skipping makes
        no progress at all; the shortfall a deletion creates has `_expand` waiting for it."""
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        # Just under target: no length violation to route elsewhere, but `can_delete` is false,
        # which is the state scene 12 was in.
        spec.word_target = 780
        backend.queue("draft", fakes.clean_prose(700) + self.OFFENDER)
        backend.queue("surgical", *["She saw the truth of it on the bench."] * 4)

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=2))

        self.assertTrue(any("forbidden_phrase rewrite failed verification; deleted" in n
                            for n in result.notes), result.notes)
        self.assertNotIn("the truth", result.scene.text.lower())

    def test_a_clean_rewrite_is_accepted(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(880) + self.OFFENDER)
        backend.queue("surgical", "She saw the shape of the arrangement laid out plain.")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertNotIn("the truth", result.scene.text.lower())
        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")


class TestLeakedProhibition(PipelineCase):
    """A premature reveal is deleted, not rewritten.

    `REMEDIES` has always said "Remove what was revealed", and surgical repair was rewriting the
    sentence instead — which on an 8B tends to reveal it again in different words. Scene 4 of a
    live book leaked a concealment, was under its word target so the length guard forbade
    deletion, had the leaking sentence rewritten, leaked it again, and was blocked.
    """

    # Plain reportage, so nothing else flags it: the only thing wrong is that the reader is not
    # meant to know it yet.
    LEAK = " He said the second hand in the book was her mother's."

    def _models(self):
        return fakes.scripted_models({
            "threads": fakes.threads_one_prohibition_violated(0, quote=self.LEAK.strip())})

    def test_the_leaking_sentence_is_cut_without_a_model_call(self):
        models, backend = self._models()
        backend.queue("draft", fakes.clean_prose(950) + self.LEAK)

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertTrue(any("deleted the thread_prohibition sentence" in n
                            for n in result.notes), result.notes)
        self.assertEqual(backend.count("surgical"), 0, "deletion needs no model")

    def test_a_blocker_outranks_the_length_guard(self):
        """Deleting gloss can shrink a scene under its floor, which is why the guard exists. A
        reveal cannot be un-read by any later scene; a short scene has `_expand` waiting."""
        models, backend = self._models()
        # Under target, so `can_delete` is False and the old code rewrote instead.
        backend.queue("draft", fakes.clean_prose(600) + self.LEAK)

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertTrue(any("deleted the thread_prohibition sentence" in n
                            for n in result.notes), result.notes)
        self.assertNotIn("second hand in the book", result.scene.text)


class TestRedraftWhenEveryRepairFails(PipelineCase):
    """Some violations are properties of the draft rather than of a span inside it.

    Scene 7 of a clean-slate run opened on a long stretch resembling the previous scene:
    deletion could not reach it inside its bounds, rewriting came back echoing twice, and the
    remaining budget could buy nothing more of the same. The scene had only ever been attacked
    from the candidates drawn at the start.
    """

    def _leaky_beat(self, spec):
        beat = ("She copies the altered column into the spare ledger and initials the bottom "
                "of the page")
        spec.beats = [Beat(beat)]
        return beat

    def test_a_better_fresh_draft_replaces_the_scene(self):
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        beat = self._leaky_beat(spec)
        backend.queue("draft", fakes.clean_prose(870) + " " + beat + ".")
        backend.queue("surgical", *[beat + "."] * 4)
        # The redraft is clean.
        backend.queue("draft", fakes.clean_prose(900, variant=3))

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=8))

        self.assertTrue(any("drafted again" in n for n in result.notes), result.notes)
        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")

    def test_a_worse_fresh_draft_is_discarded(self):
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        beat = self._leaky_beat(spec)
        backend.queue("draft", fakes.clean_prose(870) + " " + beat + ".")
        backend.queue("surgical", *[beat + "."] * 4)
        backend.queue("draft", fakes.prose_with_heading())

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=8))

        self.assertTrue(any("no better and was discarded" in n for n in result.notes),
                        result.notes)
        self.assertNotIn("format", {v.kind for v in result.violations})

    def test_a_stuck_scene_is_always_redrafted_before_the_budget_ends(self):
        """Two triggers, and the scene must reach one of them. Exhaustion fires when every
        action has been sidelined; the budget reservation fires when it has not, because a live
        scene ran out one round before sidelining completed and so never redrafted at all."""
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        beat = self._leaky_beat(spec)
        backend.queue("draft", fakes.clean_prose(870) + " " + beat + ".")
        backend.queue("surgical", *[beat + "."] * 8)
        backend.queue("draft", fakes.clean_prose(900, variant=3))

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=5))

        self.assertTrue(any("drafted again" in n for n in result.notes), result.notes)
        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")

    def test_the_budget_reservation_fires_when_sidelining_does_not(self):
        """A repair that keeps succeeding-and-not-helping never sidelines, so exhaustion is
        never declared and the reservation is the only route to a redraft."""
        from redthread.pipeline import Config as _C
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        beat = self._leaky_beat(spec)
        backend.queue("draft", fakes.clean_prose(870) + " " + beat + ".")
        # Each rewrite differs, so the check keeps firing but nothing is ever sidelined twice in
        # a row on identical text.
        backend.queue("surgical", *[beat + "." for _ in range(8)])
        backend.queue("draft", fakes.clean_prose(900, variant=3))

        result = write_scene(self.project, spec, models, _C(candidates=1, max_repairs=4))

        self.assertTrue(any("drafted again" in n for n in result.notes), result.notes)

    def test_a_small_budget_still_spends_its_rounds_on_repairs(self):
        """The reservation must not pre-empt the repairs a short budget exists to try."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(900) + " She finally saw the truth of it.")
        backend.queue("surgical", "She saw the shape of it laid out on the bench.")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertFalse(any("drafted again" in n for n in result.notes), result.notes)
        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")

    def test_it_happens_at_most_once(self):
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        beat = self._leaky_beat(spec)
        backend.queue("draft", fakes.clean_prose(870) + " " + beat + ".")
        backend.queue("surgical", *[beat + "."] * 8)
        backend.queue("draft", *[fakes.clean_prose(870, variant=2) + " " + beat + "."] * 4)

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=8))

        self.assertEqual(sum(1 for n in result.notes if "redrafted once" in n
                             or "drafted again" in n), 1, result.notes)


class TestPartialLengthProgress(PipelineCase):
    """`_expand_passage` caps how far one passage may grow, so closing a large shortfall is meant
    to take two rounds. Scene 12 of a live run added 101 of the 121 words it needed, scored
    identically to having done nothing, was discarded twice and then sidelined — and when a later
    `deseam` cut the scene shorter still, the only repair for it was switched off."""

    def test_an_expansion_that_gets_closer_is_kept(self):
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        spec.word_target = 1200
        short = BREAK.join([fakes.clean_prose(300, variant=1), "He set it down and waited.",
                            fakes.clean_prose(300, variant=4)])
        backend.queue("draft", short)
        # Grows the thinnest passage, but not far enough to clear the length major.
        backend.queue("passage", fakes.clean_prose(200, variant=6))

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=1))

        self.assertGreater(result.scene.word_count(), len(short.split()))
        self.assertFalse(any("expand attempt" in n and "discarded" in n for n in result.notes),
                         result.notes)

    def test_an_expansion_that_shrinks_the_scene_is_still_discarded(self):
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        spec.word_target = 1200
        backend.queue("draft", BREAK.join([fakes.clean_prose(300, variant=1),
                                           "He set it down and waited.",
                                           fakes.clean_prose(300, variant=4)]))
        backend.queue("passage", "Three words only")

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=1))

        self.assertIn("length", {v.kind for v in result.violations})


class TestARepairMustNotBreakSomethingElse(PipelineCase):
    """Whole-scene `_repair` regenerates the prose, so it can undo work a dedicated action has
    already done. On a live run it cleared a style leak and handed back an ending copied from the
    previous scene — two rounds after `deseam` had cut exactly that. Scoring alone accepted it,
    because the totals improved."""

    SOMATIC = (" Her chest tightened. His stomach dropped. Something twisted in her throat.")

    def test_a_repair_that_introduces_a_new_major_is_discarded(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(950))
        first = write_scene(self.project, self.project.spec_at(1), models, Config(candidates=1))
        self.assertTrue(first.committed)
        tail = " ".join(first.scene.text.split()[-40:])

        # Scene 2 is short and full of somatic beats: two major kinds, and `length` has no quote
        # so the loop routes to whole-scene repair once `expand` has been sidelined.
        backend.queue("draft", fakes.clean_prose(500, variant=1) + self.SOMATIC)
        backend.queue("expand", "too short", "too short")
        # The "repair" fixes both and hands back scene 1's ending in their place.
        backend.queue("repair", fakes.clean_prose(880, variant=1) + " " + tail)

        result = write_scene(self.project, self.project.spec_at(2), models,
                             Config(candidates=1, max_repairs=5))

        self.assertTrue(any("introduced seam_tail_copy" in n for n in result.notes),
                        result.notes)
        self.assertNotIn("seam_tail_copy", {v.kind for v in result.violations})

    def test_a_repair_may_still_trade_several_majors_for_one(self):
        """The guard is about reintroduction, not novelty. An earlier version rejected any new
        MAJOR kind, which stopped `_surgical` deleting anything: cutting four flagged sentences
        drops the scene under target and creates a `length` that was never there. Scene 6 of a
        clean-slate run had every surgical attempt thrown away for exactly that."""
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        spec.word_target = 850
        gloss = (" She realised then that the founders had known. In that moment, she "
                 "understood the cost. That was what it meant to keep a village fed.")
        backend.queue("draft", fakes.clean_prose(880) + gloss)

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=3))

        self.assertTrue(any("deleted the thematic_gloss" in n for n in result.notes),
                        result.notes)
        self.assertNotIn("thematic_gloss", {v.kind for v in result.violations})


class TestMissedObligation(PipelineCase):
    """A missed obligation is the one violation with nothing to point at: the judge says the
    scene never delivered X, so there is no quote and sentence-local surgery has no purchase.
    That left whole-scene repair, which on an 8B returns a shortened rewrite that drops
    something else — three times running, on the finale of a live 27-scene book."""

    def _scene(self) -> Scene:
        return Scene(spec_id="s1", index=1,
                     text=BREAK.join([fakes.clean_prose(300, variant=1),
                                      fakes.clean_prose(300, variant=4),
                                      fakes.clean_prose(300, variant=8)]))

    def _missed(self) -> list[Violation]:
        return [Violation("thread_obligation", Severity.MAJOR,
                          "missed: [The Allegiance] the enclave sacrifices its people",
                          "llm:check_threads")]

    def test_the_missing_beat_is_written_and_spliced_in(self):
        models, backend = fakes.scripted_models()
        scene = self._scene()
        notes: list[str] = []

        grown = _fulfil(scene, self._missed(), models, notes)

        self.assertIsNotNone(grown, notes)
        self.assertGreater(len(grown.split()), scene.word_count())
        self.assertIn("slid it across to him", grown)
        self.assertTrue(any("fulfil: wrote" in n for n in notes), notes)
        self.assertEqual(backend.count("fulfil"), 1)

    def test_the_final_passage_stays_last(self):
        """A missing beat belongs before the ending, not after it: the seam checks have already
        cleared that ending, and appending past it would hand the scene a new one."""
        models, _ = fakes.scripted_models()
        scene = self._scene()

        grown = _fulfil(scene, self._missed(), models, [])

        self.assertTrue(grown.endswith(scene.text.split(BREAK)[-1]))

    def test_the_judge_wording_reaches_the_prompt_without_its_prefix(self):
        models, backend = fakes.scripted_models()
        _fulfil(self._scene(), self._missed(), models, [])

        prompt = [p for role, p in backend.calls if role == "fulfil"][0]
        self.assertIn("the enclave sacrifices its people", prompt)
        self.assertNotIn("missed:", prompt)

    def test_nothing_to_do_without_a_missed_obligation(self):
        models, backend = fakes.scripted_models()
        other = [Violation("thread_prohibition", Severity.MAJOR, "violated: x", "llm")]

        self.assertIsNone(_fulfil(self._scene(), other, models, []))
        self.assertEqual(backend.count("fulfil"), 0)


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


    def test_deterministic_and_judge_findings_are_handled_in_their_own_phases(self):
        """The phase contract. Deterministic violations are repaired in a loop that never
        consults the judge (a judge that re-runs each round flips verdicts on near-identical
        text and poisons the comparison — a real run discarded four good fixes that way). The
        judge then verifies once, and its quoteless findings — things that must be ADDED —
        get one whole-scene repair and one re-verify."""
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(880)
                      + " She finally saw the truth of the whole arrangement laid out plain.")
        backend.queue("surgical", "She saw the shape of the arrangement on the bench.")
        backend.queue("threads", fakes.threads_one_missed(0), fakes.threads_all_met())
        backend.queue("repair", fakes.clean_prose(905))

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        roles = [r for r, _ in backend.calls]
        self.assertIn("surgical", roles, "the deterministic phase should have run surgically")
        self.assertIn("repair", roles, "the additive whole-scene phase never ran")
        self.assertLess(roles.index("surgical"), roles.index("threads"),
                        "deterministic repair happens before the judge is consulted at all")
        self.assertGreater(roles.index("repair"), roles.index("threads"),
                           "the additive repair responds to the judge, not the other way round")
        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")

    def test_a_failed_rewrite_below_target_still_deletes_down_to_the_floor(self):
        """Preferring a rewrite is right until the rewrite has failed. A live scene at 1087
        words against a 1300 target — 82 words clear of a floor it was never going to breach —
        skipped three somatic rewrites in a row, made no progress, and had the action sidelined
        for it."""
        models, backend = fakes.scripted_models()
        spec = self.project.spec_at(1)
        spec.word_target = 1000
        somatic = (" Her chest tightened at the door. His stomach dropped when he read it. "
                   "Something twisted in her throat.")
        backend.queue("draft", fakes.clean_prose(900) + somatic)
        # Every rewrite reaches for the body again, so verification refuses all of them.
        backend.queue("surgical", *["Her chest tightened again."] * 6)

        result = write_scene(self.project, spec, models, Config(candidates=1, max_repairs=3))

        self.assertTrue(any("failed verification; deleted" in n for n in result.notes),
                        result.notes)
        self.assertGreaterEqual(result.scene.word_count(), int(1000 * 0.85),
                                "deleted past the length floor")

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


class TestGradedVerdicts(PipelineCase):
    """Binary judgments from the local judge hold up; graded ones do not. A 'partial' on a
    fuzzy obligation deadlocked a real run for four repair rounds, exactly like the tell
    false-positives."""

    def test_partial_verdict_is_advisory(self):
        partial = json.dumps({
            "requirements": [{"n": 0, "verdict": "partial", "evidence": "gestured"}]
            + [{"n": i, "verdict": "met"} for i in range(1, 12)],
            "prohibitions": [{"n": i, "violated": False} for i in range(12)]})
        models, backend = fakes.scripted_models({"threads": partial})
        backend.queue("draft", fakes.clean_prose())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        self.assertTrue(result.committed,
                        f"a graded verdict blocked the commit: "
                        f"{[str(v) for v in result.violations]}")
        self.assertIn(("thread_obligation", "minor"),
                      {(v.kind, v.severity.value) for v in result.violations})

    def test_missed_verdict_still_blocks(self):
        models, backend = fakes.scripted_models({"threads": fakes.threads_one_missed(0)})
        backend.queue("draft", fakes.clean_prose())

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=0))

        self.assertFalse(result.committed)


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


class TestTrim(PipelineCase):
    """The counterpart of expansion. The whole-scene repair prompt forbids changing length, so
    a runaway scene sent there is unfixable by construction — a real run burned four 52-second
    repairs on a 2.4x overrun none of them were allowed to fix."""

    def test_a_runaway_scene_is_trimmed(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(2100))
        backend.queue("draft", fakes.clean_prose(900, 1))  # the trim reply

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        trims = [p for role, p in backend.calls if "Cut it to roughly" in p]
        self.assertEqual(len(trims), 1, "the trim path should have run")
        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")
        self.assertLess(result.scene.word_count(), 1200)

    def test_a_trim_that_grew_is_rejected(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(2100))
        backend.queue("draft", fakes.clean_prose(2300, 1))

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=1))

        self.assertFalse(result.committed)
        self.assertTrue(any("unusable; retrying" in n for n in result.notes), result.notes)

    def test_length_ties_break_toward_the_target(self):
        """A real run kept a 2.4x runaway over an on-length draft because the violation tuples
        tied and the sort was stable."""
        models, backend = fakes.scripted_models({"threads": fakes.threads_one_missed(0)})
        backend.queue("draft", fakes.clean_prose(2100))     # runaway: 1 major
        backend.queue("draft", fakes.clean_prose(900, 1))   # on target: also 1 major (threads)

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=2, max_repairs=0))

        self.assertLess(result.scene.word_count(), 1200,
                        "the on-length candidate should win the tie")


class TestSomaticRepair(PipelineCase):
    """From the first Debt of Years run: three body-beats in scene 1, seven attempts, held."""

    def test_all_excess_beats_are_fixed_in_one_surgical_pass(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(860)
                      + " His skin prickled at the ledger's weight."
                      + " His gut twisted when the entry surfaced."
                      + " His scalp crawled as the seal broke.")
        backend.queue("surgical",
                      "He set the ledger down harder than the desk deserved.",
                      "He read the entry twice and said nothing.")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=2))

        self.assertTrue(result.committed,
                        f"held back by: {[str(v) for v in result.violations]}")
        self.assertEqual(backend.count("surgical"), 2,
                         "two excess beats, two rewrites, one pass")

    def test_a_rewrite_that_reaches_for_the_body_again_is_rejected(self):
        models, backend = fakes.scripted_models()
        backend.queue("draft", fakes.clean_prose(880)
                      + " His skin prickled at the ledger's weight."
                      + " His gut twisted when the entry surfaced.")
        backend.queue("surgical", "His stomach knotted as he set the ledger down.")

        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=1))

        self.assertNotIn("stomach knotted", result.scene.text,
                         "the somatic rewrite must not be spliced")
