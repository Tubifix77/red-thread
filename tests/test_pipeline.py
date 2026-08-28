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
                              Thread, ThreadKind, Transition)
from redthread import checks
from redthread.pipeline import (Config, _deseam, _expand_passage, _reseam,
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
        backend.queue("draft", fakes.clean_prose(880)
                      + " She finally saw the truth of the whole arrangement laid out plain.")
        # Every surgical rewrite puts the forbidden phrase straight back, and whole-scene repair
        # returns nothing usable. There is no round at which this starts working.
        backend.queue("surgical", *["She saw the truth of it plain on the bench."] * 6)
        result = write_scene(self.project, self.project.spec_at(1), models,
                             Config(candidates=1, max_repairs=8))

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
