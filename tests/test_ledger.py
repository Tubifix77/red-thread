"""The fact ledger: DOME's quadruple store plus its two-stage conflict detection.

The deterministic half of conflict detection is what is tested here. Stage two — asking a model
whether a candidate pair really contradicts — is tested in `test_pipeline.py` against a scripted
backend, because the point of stage one is precisely that it decides *without* a model.
"""

from __future__ import annotations

import unittest

import redthread.ledger as ledger_mod
from redthread.ledger import Ledger, claim_class, jaccard, normalise
from redthread.models import Fact, FactKind


def f(subject, predicate, obj, sceneno, kind=FactKind.STATE) -> Fact:
    return Fact(subject, predicate, obj, sceneno, kind)


class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger([
            f("Siv", "has", "a paper notebook", 1, FactKind.DETAIL),
            f("Otto", "is", "maintenance chief", 1),
            f("Substation four", "houses", "the reader terminal", 1),
            f("Siv", "knows", "the branch is unreachable", 1, FactKind.KNOWLEDGE),
            f("Otto", "knows", "there were three failures", 2, FactKind.KNOWLEDGE),
            f("Beata", "owns", "the eastern parcel", 3),
        ])

    def test_as_of_excludes_later_scenes(self):
        self.assertEqual(len(self.ledger.as_of(1)), 4)
        self.assertEqual(len(self.ledger.as_of(2)), 5)

    def test_knows_is_scoped_to_the_character(self):
        """Character-scoped knowledge is the field that breaks most often, so it gets its own
        accessor and its own test."""
        siv = self.ledger.knows("Siv", scene=5)
        self.assertEqual(len(siv), 1)
        self.assertIn("branch", siv[0].object)

    def test_knows_excludes_the_current_and_later_scenes(self):
        """A character does not know, entering scene 1, what scene 1 teaches them."""
        self.assertEqual(self.ledger.knows("Siv", scene=1), [])

    def test_knows_ignores_non_knowledge_facts(self):
        self.assertTrue(all(fact.kind is FactKind.KNOWLEDGE
                            for fact in self.ledger.knows("Siv", scene=9)))

    def test_about_filters_to_named_subjects(self):
        hits = self.ledger.about(["Beata"], scene=9)
        self.assertTrue(hits)
        self.assertTrue(all("beata" in normalise(h.subject) or "beata" in normalise(h.object)
                            for h in hits))

    def test_about_excludes_the_scene_being_written(self):
        self.assertEqual(self.ledger.about(["Beata"], scene=3), [])

    def test_about_returns_most_recent_first(self):
        ledger = Ledger([f("Siv", "is", "at the yard", 1), f("Siv", "is", "at the archive", 4)])
        hits = ledger.about(["Siv"], scene=9)
        self.assertEqual(hits[0].scene, 4)

    def test_short_fact_name_matches_full_spec_name(self):
        """Regression: specs carry "Siv Alderman", extraction produces "Siv".

        A one-directional substring test matched neither, so the ledger filled up while every
        brief still said "nothing established yet" — continuity failing with no error anywhere.
        """
        ledger = Ledger([f("Siv", "has", "a green notebook", 1, FactKind.DETAIL)])
        self.assertTrue(ledger.about(["Siv Alderman"], scene=2),
                        "short subject name did not match the full spec name")

    def test_full_fact_name_matches_short_spec_name(self):
        ledger = Ledger([f("Siv Alderman", "has", "a green notebook", 1, FactKind.DETAIL)])
        self.assertTrue(ledger.about(["Siv"], scene=2))

    def test_object_mention_is_retrieved(self):
        """A fact about a door in a room is relevant to a scene set in that room."""
        ledger = Ledger([f("the eastern hatch", "is in", "the pump house", 1)])
        self.assertTrue(ledger.about(["the pump house"], scene=2))

    def test_unrelated_subject_is_not_retrieved(self):
        ledger = Ledger([f("Beata", "owns", "the eastern parcel", 1)])
        self.assertEqual(ledger.about(["Otto Renner"], scene=2), [])

    def test_latest_state_wins(self):
        ledger = Ledger([f("door", "is", "open", 2), f("door", "is", "welded shut", 7)])
        self.assertEqual(ledger.latest_state("door", "is").object, "welded shut")


class TestConflictCandidates(unittest.TestCase):
    def test_same_key_different_object_is_a_candidate(self):
        ledger = Ledger([f("Siv", "eye colour", "grey", 1, FactKind.DETAIL)])
        new = f("Siv", "eye colour", "brown", 6, FactKind.DETAIL)
        ledger.add(new)
        self.assertEqual(len(ledger.conflict_candidates([new])), 1)

    def test_same_key_same_object_is_not_a_candidate(self):
        ledger = Ledger([f("Siv", "eye colour", "grey", 1, FactKind.DETAIL)])
        new = f("Siv", "eye colour", "grey", 6, FactKind.DETAIL)
        ledger.add(new)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_events_are_not_compared_by_object(self):
        """Two different events for one subject and verb are normal, not a contradiction:
        walking to the dock twice is a story, not an error."""
        ledger = Ledger([f("Siv", "went to", "the dock", 1, FactKind.EVENT)])
        new = f("Siv", "went to", "the archive", 4, FactKind.EVENT)
        ledger.add(new)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_near_synonymous_predicate_is_a_candidate(self):
        ledger = Ledger([f("the eastern door", "is welded shut", "permanently", 2)])
        new = f("the eastern door", "is welded", "no longer", 8)
        ledger.add(new)
        self.assertTrue(ledger.conflict_candidates([new]))

    def test_the_same_claim_split_differently_is_not_a_candidate(self):
        """From a live run: scene 6 was blocked by `Dain Korr | has | read the records` against
        `Dain Korr | has read | records`. One proposition, extracted twice with the verb on
        opposite sides of the predicate/object boundary. The judge answered "same action given
        twice" — correct, and not a contradiction. The pair should never have reached it."""
        ledger = Ledger([f("Dain Korr", "has", "read the records", 4, FactKind.KNOWLEDGE)])
        new = f("Dain Korr", "has read", "records", 6, FactKind.KNOWLEDGE)
        ledger.add(new)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_narrowing_a_claim_is_not_a_candidate(self):
        ledger = Ledger([f("Siv", "carries", "a notebook", 1, FactKind.STATE)])
        new = f("Siv", "carries", "a green canvas notebook", 5, FactKind.STATE)
        ledger.add(new)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_a_genuinely_different_value_survives_the_filter(self):
        """The filter must not swallow the case it sits next to: two claims that differ in a
        content word are still a candidate, however similar the rest reads."""
        ledger = Ledger([f("Siv", "has", "grey eyes", 1, FactKind.DETAIL)])
        new = f("Siv", "has", "brown eyes", 6, FactKind.DETAIL)
        ledger.add(new)
        self.assertEqual(len(ledger.conflict_candidates([new])), 1)

    def test_a_state_that_moved_is_not_a_candidate(self):
        """A live run blocked scene 8 on `The register | is | open on the table` against
        `the register | is | in the drawer`, three scenes apart. A STATE is defined here as
        something that stays true *until something changes it* — two states placing the same
        subject somewhere are a subject that moved."""
        ledger = Ledger([f("The register", "is", "open on the table", 5, FactKind.STATE)])
        new = f("the register", "is", "in the drawer", 8, FactKind.STATE)
        ledger.add(new)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_claims_about_different_attributes_are_not_compared(self):
        """A live run blocked scene 9 on "the register cannot be both open on the table and a
        book with worn leather" — which of course it can. A bare copula carries no meaning, so
        the `(subject, predicate)` key groups where a thing lies with what it is made of."""
        ledger = Ledger([f("the register", "is", "open on the table", 5, FactKind.STATE)])
        new = f("the register", "is", "a book with worn leather", 9, FactKind.DETAIL)
        ledger.add(new)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_two_identity_claims_still_conflict(self):
        ledger = Ledger([f("the truck", "is", "a green Hilux", 1, FactKind.DETAIL)])
        new = f("the truck", "is", "a red Hilux", 6, FactKind.DETAIL)
        ledger.add(new)
        self.assertEqual(len(ledger.conflict_candidates([new])), 1)

    def test_claim_class_reads_the_object(self):
        cases = {"open on the table": "position", "a book with worn leather": "identity",
                 "grey eyes": "condition", "welded shut": "condition",
                 "the maintenance chief": "identity"}
        for obj, expected in cases.items():
            with self.subTest(obj=obj):
                self.assertEqual(claim_class(f("x", "is", obj, 1)), expected)

    def test_a_mind_changing_is_not_a_contradiction(self):
        """A live run blocked scene 7 on `Marta | has | belief that the register is correct`
        against `Marta | has known | system is broken` — the arc the book exists to trace,
        reported as a detail given two different values."""
        ledger = Ledger([f("Marta", "has", "belief that the register is correct", 5)])
        new = f("Marta", "has known", "system is broken", 7)
        ledger.add(new)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_two_things_never_questioned_do_not_conflict(self):
        """From a live run: `Elin | had | never questioned the temperature` against
        `Elin | had | never questioned the schedule`. Both are true at once."""
        ledger = Ledger([f("Elin", "had", "never questioned the temperature", 3)])
        new = f("Elin", "had", "never questioned the schedule", 7)
        ledger.add(new)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_a_physical_detail_is_not_a_belief(self):
        ledger = Ledger([f("Siv", "has", "grey eyes", 1, FactKind.DETAIL)])
        new = f("Siv", "has", "brown eyes", 6, FactKind.DETAIL)
        ledger.add(new)
        self.assertEqual(len(ledger.conflict_candidates([new])), 1)

    def test_a_fixed_detail_in_two_places_is_still_a_candidate(self):
        """A DETAIL is "a concrete particular the prose has now fixed and cannot change". A scar
        on the left hand against one on the right is the contradiction this system is for."""
        ledger = Ledger([f("the scar", "is", "on his left hand", 1, FactKind.DETAIL)])
        new = f("the scar", "is", "on his right hand", 6, FactKind.DETAIL)
        ledger.add(new)
        self.assertEqual(len(ledger.conflict_candidates([new])), 1)

    def test_a_non_locative_state_change_is_still_a_candidate(self):
        ledger = Ledger([f("the door", "is", "welded shut", 2, FactKind.STATE)])
        new = f("the door", "is", "standing open", 9, FactKind.STATE)
        ledger.add(new)
        self.assertEqual(len(ledger.conflict_candidates([new])), 1)

    def test_different_subjects_are_never_candidates(self):
        ledger = Ledger([f("Siv", "eye colour", "grey", 1, FactKind.DETAIL)])
        new = f("Otto", "eye colour", "brown", 6, FactKind.DETAIL)
        ledger.add(new)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_same_scene_facts_do_not_conflict_with_each_other(self):
        """Within one scene a state may legitimately change: a door opened and closed again."""
        a = f("door", "is", "open", 4)
        b = f("door", "is", "shut", 4)
        ledger = Ledger([a, b])
        self.assertEqual(ledger.conflict_candidates([a, b]), [])

    def test_candidate_pairs_are_deduplicated(self):
        ledger = Ledger([f("Siv", "eye colour", "grey", 1, FactKind.DETAIL)])
        new = f("Siv", "eye colour", "brown", 6, FactKind.DETAIL)
        ledger.add(new)
        pairs = ledger.conflict_candidates([new, new])
        self.assertEqual(len(pairs), 1)


class TestCandidateRedundancyIsReduced(unittest.TestCase):
    """`conflict_candidates` used to hand the judge every historical assertion of a key.

    On *The Debt of Years* that produced 9,560 candidate pairs across 70 scenes — median 70 per
    scene, maximum 979 — while `judge_conflicts` truncates at 25. **86% of all candidate pairs
    were discarded by list order, silently**, so the gate was far weaker than its design and no
    run said so. Reducing to the latest assertion per shared attribute brings the same book to
    571 pairs, and one scene over the cap instead of 46.
    """

    def test_only_the_latest_assertion_of_an_attribute_is_offered(self):
        """Two re-assertions of the same claim collapse to the newer one.

        Both of these share exactly `{scar, hand}` with the new fact, so they are the same claim
        restated and only the later one describes the state the new scene must agree with.

        *Note on what is deliberately NOT collapsed:* `a scar on her left palm` against
        `a scar on her right hand` shares only `{scar}`, a different signature, so it would be
        offered as its own pair. That is wanted — hand-versus-palm and hand-versus-hand are two
        different questions, and an earlier draft of this test asserted the wrong thing by
        assuming they were one.
        """
        ledger = Ledger([
            f("Siv", "has", "a scar on her left hand", 2, FactKind.DETAIL),
            f("Siv", "has", "a scar on her left hand, pale now", 5, FactKind.DETAIL),
        ])
        new = f("Siv", "has", "a scar on her right hand", 9, FactKind.DETAIL)
        pairs = ledger.conflict_candidates([new])
        self.assertEqual(len(pairs), 1, [(a.as_line(), b.as_line()) for a, b in pairs])
        self.assertEqual(pairs[0][0].scene, 5, "the newer assertion is the one to judge against")

    def test_a_wandering_attribute_survives_the_reduction(self):
        """The regression the first version of the reduction introduced, pinned.

        Keying on `(subject, predicate)` alone looked right and was wrong: `(siv, has)` covers
        scars, coats and maps alike, so the "latest assertion of that key" was an unrelated fact
        and **both scar facts were discarded** — the reduction deleted exactly the defect it was
        written to expose. Keying on the tokens the two objects share keeps scar against scar.
        """
        ledger = Ledger([
            f("Siv", "has", "a scar on her palm", 3, FactKind.DETAIL),
            f("Siv", "has", "a canvas satchel", 8, FactKind.DETAIL),
            f("Siv", "has", "a folded map", 11, FactKind.DETAIL),
        ])
        new = f("Siv", "has", "a scar on her temple", 20, FactKind.DETAIL)
        pairs = ledger.conflict_candidates([new])
        scar = [(o, n) for o, n in pairs
                if "scar" in o.object and "scar" in n.object]
        self.assertTrue(scar, f"the scar pair must survive; got "
                              f"{[(a.as_line(), b.as_line()) for a, b in pairs]}")

    def test_unrelated_attributes_are_still_offered_separately(self):
        """The reduction must not collapse two genuinely different claims into one."""
        ledger = Ledger([
            f("Siv", "eye colour", "grey", 2, FactKind.DETAIL),
            f("Siv", "hair colour", "black", 3, FactKind.DETAIL),
        ])
        new_eyes = f("Siv", "eye colour", "brown", 9, FactKind.DETAIL)
        new_hair = f("Siv", "hair colour", "red", 9, FactKind.DETAIL)
        pairs = ledger.conflict_candidates([new_eyes, new_hair])
        self.assertEqual(len(pairs), 2, [(a.as_line(), b.as_line()) for a, b in pairs])


class TestRollback(unittest.TestCase):
    def test_drop_scene_removes_only_that_scene(self):
        ledger = Ledger([f("a", "b", "c", 1), f("d", "e", "g", 2), f("h", "i", "j", 2)])
        ledger.drop_scene(2)
        self.assertEqual([fact.scene for fact in ledger.facts], [1])


class TestRendering(unittest.TestCase):
    def test_render_groups_by_kind_and_omits_empty_groups(self):
        out = Ledger([f("Siv", "has", "a notebook", 1, FactKind.DETAIL)]).render(
            [f("Siv", "has", "a notebook", 1, FactKind.DETAIL)])
        self.assertIn("DETAIL:", out)
        self.assertNotIn("EVENT:", out)

    def test_render_of_nothing_is_explicit(self):
        self.assertIn("nothing established", Ledger().render([]))


class TestNormalisation(unittest.TestCase):
    def test_normalise_strips_punctuation_and_case(self):
        self.assertEqual(normalise("The Door's Lock!"), "the door s lock")

    def test_jaccard_of_disjoint_sets_is_zero(self):
        self.assertEqual(jaccard({"a"}, {"b"}), 0.0)

    def test_jaccard_of_identical_sets_is_one(self):
        self.assertEqual(jaccard({"a", "b"}, {"a", "b"}), 1.0)

    def test_jaccard_with_an_empty_set_is_zero(self):
        self.assertEqual(jaccard(set(), {"a"}), 0.0)


if __name__ == "__main__":
    unittest.main()


class TestPossessionChangesAreNotContradictions(unittest.TestCase):
    """What somebody is carrying is a thing that changes. That is what a STATE is.

    The 71-scene run halted at scene 37 on `Vael | is carrying | a blade` from scene 27 against
    `Vael | is carrying | a bundle`. Ten scenes apart, a character who put one thing down and
    picked another up is not a contradiction; it is the story. The judge was asked and said
    contradiction, which is what a judge will always say to two different objects — it has no
    notion of elapsed time. The fix is not a better judge, it is not asking.

    The failure only appears at length: across every ledger in the project there are 35
    possession facts and three subject-and-predicate keys carrying more than one object, so no
    nine-scene book ever met it.
    """

    def _fact(self, predicate, obj, scene, kind=FactKind.STATE):
        return Fact("Vael", predicate, obj, scene, kind)

    def test_the_pair_that_halted_the_book_is_not_a_candidate(self):
        ledger = Ledger([self._fact("is carrying", "a blade", 27)])
        new = self._fact("is carrying", "a bundle", 37)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_other_possession_verbs_too(self):
        for verb in ("holds", "is holding", "wears", "is wearing", "grips", "clutches"):
            with self.subTest(verb=verb):
                ledger = Ledger([self._fact(verb, "a lantern", 3)])
                new = self._fact(verb, "a coil of rope", 14)
                self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_the_verb_may_sit_on_either_side_of_the_boundary(self):
        """Where the predicate ends and the object begins is an artefact of extraction.

        The first version of this guard read only the predicate. It caught `Vael | is carrying |
        a blade` at scene 37 and then missed `Vael | is | holding a dagger` at scene 49 — same
        claim, same book, same run halted twice on one bug. `same_claim` makes exactly this
        argument about the predicate/object boundary; this guard now respects it too.
        """
        ledger = Ledger([Fact("Vael", "is", "holding a dagger", 22, FactKind.STATE)])
        new = Fact("Vael", "is", "gripping the rope", 49, FactKind.STATE)
        self.assertEqual(ledger.conflict_candidates([new]), [])

    def test_a_fixed_detail_is_still_checked(self):
        """The load-bearing restriction. A scar is a DETAIL — a particular the prose has fixed
        and cannot change — so a scar that moves wrists is exactly what this system is for."""
        ledger = Ledger([self._fact("has a", "scar on his left wrist", 27, FactKind.DETAIL)])
        new = self._fact("has a", "scar on his right wrist", 37, FactKind.DETAIL)
        self.assertTrue(ledger.conflict_candidates([new]),
                        "a fixed physical detail changing is a real contradiction")

    def test_it_does_not_swallow_an_unrelated_state_conflict(self):
        ledger = Ledger([self._fact("is", "dead", 27)])
        new = self._fact("is", "alive", 37)
        self.assertTrue(ledger.conflict_candidates([new]))


class TestTheSliceReachesBackIntoTheBook(unittest.TestCase):
    """Recency alone empties a book out from under its own ending.

    Sorting by scene and truncating is fine while the ledger is small and catastrophic once it
    is not. Measured on a finished 71-scene novel: at scene 71, 888 facts matched the scene's
    subjects, 40 survived the cap, and the oldest kept was from scene 68. The final scene of the
    book could see scenes 68, 69 and 70 and nothing else — every revelation, promise and
    relationship from the first 67 scenes was invisible to it.

    That is a structural reason a middle cannot earn an ending, and it was found while trying to
    measure whether one does: the first two attempts at that measurement both turned out to be
    measuring this cap instead of the book.
    """

    def _ledger(self, scenes=70, per_scene=15):
        return Ledger([
            Fact("Siv", "did", f"thing {s}-{i}", s, FactKind.STATE)
            for s in range(1, scenes + 1) for i in range(per_scene)])

    def test_the_slice_spans_the_book_rather_than_its_last_three_scenes(self):
        got = self._ledger().about(["Siv"], 71)
        scenes = {f.scene for f in got}
        self.assertLessEqual(min(scenes), 10,
                             "the ending must be able to see the beginning of its own book")
        self.assertGreater(len(scenes), 8,
                           "the slice must span the book, not cluster at one end")

    def test_it_is_still_mostly_recent(self):
        """Current state is what a scene mostly needs; the reach-back is the remainder."""
        got = self._ledger().about(["Siv"], 71)
        recent = sum(1 for f in got if f.scene >= 66)
        self.assertGreaterEqual(recent, len(got) // 2)

    def test_the_limit_is_still_the_limit(self):
        """The cap exists because the brief has a token budget, and that has not changed."""
        self.assertEqual(len(self._ledger().about(["Siv"], 71)), 40)

    def test_a_small_ledger_is_returned_whole(self):
        led = self._ledger(scenes=2, per_scene=3)
        self.assertEqual(len(led.about(["Siv"], 3)), 6)

    def test_no_fact_is_returned_twice(self):
        got = self._ledger().about(["Siv"], 71)
        self.assertEqual(len(got), len({id(f) for f in got}))

    def test_character_knowledge_was_never_capped_and_still_is_not(self):
        led = Ledger([Fact("Siv", "knows", f"secret {s}", s, FactKind.KNOWLEDGE)
                      for s in range(1, 71)])
        self.assertEqual(len(led.knows("Siv", 71)), 70)


class TestSupersededPlacementsAreRetired(unittest.TestCase):
    """A STATE is "true until changed", and nothing ever changed it.

    Every placement a character has ever had accumulated and was handed to the brief under the
    heading "Already established (do not contradict)". At scene 71 of a live novel, 12 of the 18
    states in the slice were superseded by a newer state in the same slice — the model was told
    Kai was in a room, on a bench, and in a room with a jagged ceiling, and told to contradict
    none of them.

    Recency-capping hid most of this by accident. Stratifying the slice so an ending can see the
    beginning of its own book removed that accident, which makes this a precondition of that
    change rather than an improvement on it.
    """

    def _led(self, *facts):
        return Ledger(list(facts))

    def test_the_older_placement_is_dropped(self):
        led = self._led(Fact("Kai", "is", "in a room", 22, FactKind.STATE),
                        Fact("Kai", "is", "in a room with a jagged ceiling", 39, FactKind.STATE))
        got = led.about(["Kai"], 40)
        self.assertEqual([f.scene for f in got], [39])

    def test_a_different_subject_keeps_its_own_placement(self):
        led = self._led(Fact("Kai", "is", "in a room", 22, FactKind.STATE),
                        Fact("Mir", "is", "inside the hall", 37, FactKind.STATE))
        self.assertEqual(len({f.subject for f in led.about(["Kai", "Mir"], 40)}), 2)

    def test_two_conditions_may_both_hold(self):
        """Nobody is in two rooms; plenty of people have a leg injury and a bad temper."""
        led = self._led(Fact("Kai", "has", "a leg injury", 22, FactKind.STATE),
                        Fact("Kai", "is", "out of breath", 39, FactKind.STATE))
        self.assertEqual(len(led.about(["Kai"], 40)), 2)

    def test_a_prepositional_phrase_that_is_not_a_placement_survives(self):
        """`claim_class` reads any object containing a preposition as a position, which makes
        "pain in his leg" a placement. Superseding on that reading would retire real facts."""
        led = self._led(Fact("Kai", "feels", "pain in his leg", 22, FactKind.STATE),
                        Fact("Kai", "is", "near the desk", 39, FactKind.STATE))
        got = led.about(["Kai"], 40)
        self.assertEqual(len(got), 2)
        self.assertTrue(any("pain" in f.object for f in got))

    def test_a_detail_is_never_retired(self):
        """A DETAIL is a particular the prose has fixed. It does not go stale."""
        led = self._led(Fact("Kai", "has", "a scar on his wrist", 4, FactKind.DETAIL),
                        Fact("Kai", "is", "in the yard", 39, FactKind.STATE))
        self.assertEqual(len(led.about(["Kai"], 40)), 2)


class TestSliceKeepsFixedParticulars(unittest.TestCase):
    """What an old fact band contributes to a brief, and why the kind matters.

    Scene 15 of a live novel established BOTH `[detail] Kai has a scar along his palm` and
    `[state] Kai feels the scar still burns faintly`. The stratified spread picked whichever fact
    landed on its step boundary, the state won, and by scene 40 the brief told the writer Kai had
    a scar without saying where — so it put one on his temple, and "temple" then propagated to
    the end of the book. Measured across the corpus, 15 of 19 books at 60+ scenes carry a
    permanent mark in two or more body regions against 1 of 19 shorter ones.
    """

    def test_a_detail_beats_a_state_for_the_same_slot(self):
        older = [f("Kai", "feels", "the scar still burns faintly", 15, FactKind.STATE),
                 f("Kai", "has", "a scar along his palm", 15, FactKind.DETAIL)]
        best = min(older, key=ledger_mod._slice_rank)
        self.assertEqual(best.object, "a scar along his palm")

    def test_the_more_specific_assertion_wins_within_a_kind(self):
        """`Kai has scar` and `Kai has a scar along his palm` are both details.

        Preferring details alone was not enough: the bare one still won slots, and a brief that
        says a character has a scar without saying where is exactly what invited the temple.
        """
        older = [f("Kai", "has", "scar", 23, FactKind.DETAIL),
                 f("Kai", "has", "a scar along his palm", 15, FactKind.DETAIL)]
        best = min(older, key=ledger_mod._slice_rank)
        self.assertEqual(best.object, "a scar along his palm",
                         "specificity must outrank recency inside a kind")

    def test_recency_still_decides_when_kind_and_specificity_tie(self):
        older = [f("Kai", "has", "a folded paper map", 8, FactKind.DETAIL),
                 f("Kai", "has", "a folded linen cloth", 30, FactKind.DETAIL)]
        best = min(older, key=ledger_mod._slice_rank)
        self.assertEqual(best.scene, 30)

    def test_the_slice_carries_more_details_than_recency_alone_would(self):
        """The measured effect: 5.0 details per slice became 15.9 on a 71-scene book."""
        facts = []
        for i in range(1, 60):
            facts.append(f("Kai", "is", f"standing in room {i}", i, FactKind.STATE))
            facts.append(f("Kai", "did", f"thing {i}", i, FactKind.EVENT))
            facts.append(f("Kai", "has", f"a marked token number {i}", i, FactKind.DETAIL))
        sl = Ledger(facts).about(["Kai"], scene=60, limit=40)
        details = sum(1 for x in sl if x.kind is FactKind.DETAIL)
        self.assertEqual(len(sl), 40)
        self.assertGreater(details, 15, f"only {details} details in a 40-fact slice")
