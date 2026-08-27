"""Build the reference plan: a hand-authored ten-scene demo.

This is the de-risking fixture. The point of writing a plan by hand is to test the machinery that
matters — the brief, the ledger, the verifier, the commit gate — without also depending on an
automatic planner. If a scene generated from one of these briefs reads as continuous with its
neighbour, and the verifier catches deliberately injected contradictions, the architecture works
and the planner becomes a separate problem.

It doubles as a worked example of a plan that passes both acceptance markers
(docs/TESTING.md):

* T-WELL owns scenes 3, 6, 8 and 10, none of which the main thread touches. It is a subplot
  because it has the page to itself, not because it is labelled one.
* Every thread gains state between scenes 4 and 7, so the midpoint complicates rather than
  restates.

Run:  python examples/build_inherited_glitch.py runs/glitch
Then: python -m redthread audit runs/glitch
      python -m redthread brief runs/glitch --scene 1
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from redthread.models import (Beat, Character, SceneSpec, StorySpec, StyleContract, Thread,
                              ThreadKind, Transition)
from redthread.project import Project


def build_story() -> StorySpec:
    return StorySpec(
        title="The Inherited Glitch",
        premise=(
            "A rural technician discovers that the automated infrastructure her community "
            "depends on is hiding a deliberate, fatal code error programmed by the original "
            "founders. She can expose it and destroy the comfort the town is built on, or "
            "maintain the lie while the system degrades."
        ),
        world_rules=[
            "Hallowmere is a farming settlement of about four thousand people, sixty years old, "
            "dependent on an automated water, power and cold-storage grid called the Provision.",
            "The Provision was built by twelve founders. All twelve are dead. They left "
            "documentation, and the documentation is incomplete on purpose.",
            "Nobody in Hallowmere can write the language the Provision's core is written in. "
            "Siv can read it. That is the whole of her authority and the whole of her isolation.",
            "The grid degrades measurably: three cold-storage failures in the last two years, "
            "each written off as component age.",
            "There is no outside authority to appeal to. The nearest arbitration court is nine "
            "days away and has no jurisdiction over founder covenants.",
        ],
        characters=[
            Character(
                id="siv", name="Siv Alderman",
                description=(
                    "Thirty-four, the Provision's only reader. Grew up in Hallowmere, trained "
                    "off-settlement for six years, came back. Keeps a paper notebook because "
                    "she does not trust the grid to remember things for her."
                ),
                voice=(
                    "Short declaratives. Technical when precise, blunt when not. Does not "
                    "soften bad news and resents being asked to. Never says 'I think' — she "
                    "says what is true or says she does not know."
                )),
            Character(
                id="otto", name="Otto Renner",
                description=(
                    "Sixty-one, maintenance chief for twenty-two years. Cannot read the core "
                    "but knows every physical inch of the grid. Taught Siv to strip a pump at "
                    "eleven. Believes the Provision is a covenant, not a machine."
                ),
                voice=(
                    "Circles a subject before landing on it. Uses the grid's parts as nouns for "
                    "everything else. Deflects with practical questions when cornered."
                )),
            Character(
                id="beata", name="Beata Alderman",
                description=(
                    "Twenty-nine, Siv's sister. Farms the eastern parcel their mother left them "
                    "and wants out — she has a buyer for her half, contingent on the eastern "
                    "well being re-registered as independent of the Provision. It is not, and "
                    "the registry says it never was."
                ),
                voice=(
                    "Fast, funny, and always mid-argument. Uses Siv's own logic against her. "
                    "Says the unkind true thing and then apologises for the phrasing, not the "
                    "content."
                )),
            Character(
                id="lund", name="Ines Lund",
                description=(
                    "Fifty-two, sits on the Hallowmere council and holds the registry. Not "
                    "corrupt; institutionally incapable of an answer that is not already "
                    "written down somewhere."
                ),
                voice=(
                    "Procedural. Answers a question with the process that would answer it. "
                    "Genuinely kind in the gaps between clauses."
                )),
        ],
        threads=[
            Thread(
                id="T-CODE", name="The dead line in the founders' code",
                kind=ThreadKind.MAIN,
                states=["dormant", "planted", "complicated", "escalated", "paid_off"],
                concealment=(
                    "That the error is deliberate, and that the founders wrote it down as an "
                    "accepted loss with a figure attached. The reader must not understand this "
                    "before scene 4."
                ),
                payoff=(
                    "Siv holds proof that is unambiguous to her and unreadable to everyone "
                    "else — which is the trap, not the victory."
                ),
                reveal_scene=4,
                deadline_scene=9),
            Thread(
                id="T-CHOICE", name="Expose it or carry it",
                kind=ThreadKind.THEMATIC,
                states=["dormant", "dilemma_visible", "cost_named", "forced", "chosen"],
                concealment=(
                    "Which way she goes. Both terminal outcomes cost lives; the story must not "
                    "signal a correct answer."
                ),
                reveal_scene=10,
                payoff=(
                    "She chooses, and the cost of the road she did not take stays legible on "
                    "the page. Nobody thanks her."
                )),
            Thread(
                id="T-WELL", name="Beata's eastern well",
                kind=ThreadKind.SUBPLOT,
                states=["dormant", "planted", "complicated", "escalated", "paid_off"],
                concealment=(
                    "That the well's registry entry was altered sixty years ago, for reasons "
                    "that have nothing to do with the code error."
                ),
                reveal_scene=6,
                payoff=(
                    "Beata gets an answer about the well and it does not solve her problem. "
                    "This thread must never become evidence for the main plot."
                )),
            Thread(
                id="T-OTTO", name="Siv and Otto",
                kind=ThreadKind.RELATIONSHIP,
                states=["dormant", "planted", "complicated", "escalated", "paid_off"],
                concealment="That Otto has suspected something for years and chose not to look.",
                reveal_scene=5,
                payoff=(
                    "The person who taught her to be careful turns out to have been careful "
                    "about the wrong thing. He does not die and he is not redeemed."
                )),
        ],
        style=StyleContract(
            pov="third limited",
            tense="past",
            samples=[
                "The pump had been running eleven minutes longer than the log said it had.",
                "Otto did not look up. He turned the coupling a quarter turn, felt it, turned "
                "it back.",
                "Nine days to the court. She had counted it out on the calendar twice, the way "
                "you check a number you already believe.",
            ],
            forbidden_phrases=[
                "the truth", "the system was broken", "everything changed",
                "she had to make a choice", "little did she know",
            ],
            notes=(
                "Industrial rural register. Machinery named specifically — couplings, "
                "impellers, part numbers. No lyricism about the landscape. Emotion arrives as "
                "behaviour and as what a character refuses to say, never as a summary of a "
                "feeling and not through the body."
            )),
    )


def build_plan() -> list[SceneSpec]:
    """Ten scenes. Word targets vary deliberately — uniform scene length is a pacing tell."""
    return [
        SceneSpec(
            id="s01", index=1, chapter=1, word_target=900,
            pov="siv", characters=["siv"],
            setting="Provision substation four, the reader terminal in the pump house",
            time="late evening, end of the dry season",
            summary=(
                "Siv reconciles the cold-storage failure logs against the core and finds a "
                "branch that cannot be reached."
            ),
            beats=[
                Beat("She is doing routine reconciliation, resentfully, on her own time. "
                     "Establish the grid as physical and specific, and establish that she is "
                     "the only person who can read the core.", 0.9),
                Beat("The third failure's log entry does not match what the core would have "
                     "done. She assumes she has misread it. She checks twice more.", 0.9),
                Beat("She finds an unreachable branch — code the founders wrote and then made "
                     "impossible to execute. She writes the line number in her paper notebook "
                     "and goes home. No conclusion, no realisation stated.", 0.9),
            ],
            thread_ops={
                "T-CODE": Transition(
                    post=["Siv has found a specific unreachable branch in the core and recorded "
                          "its line number",
                          "the reader understands the grid degrades and the failures were "
                          "written off"],
                    forbid=["revealing or hinting that the branch is deliberate",
                            "Siv voicing a theory about why it exists",
                            "any founder appearing as a character, in memory or otherwise"],
                    to_state="planted"),
            },
            notes=("This is scene one of a novel: no context-setting summary paragraph. Open "
                   "inside the work."),
        ),
        SceneSpec(
            id="s02", index=2, chapter=1, word_target=1200,
            pov="siv", characters=["siv", "otto"],
            setting="The maintenance yard, under the number-two intake housing",
            time="the following morning",
            summary=("Siv asks Otto about the three failures without telling him what she "
                     "found. He answers the question she did not ask."),
            beats=[
                Beat("Otto is doing physical work and keeps doing it through the conversation. "
                     "Establish their history through how they hand each other tools, not "
                     "through reminiscence.", 0.9),
                Beat("Siv fishes. Otto gives her component age, part numbers, the story he has "
                     "told himself. He is not lying and he is not curious.", 0.9),
                Beat("He says something that reveals he has noticed a pattern and decided not "
                     "to pursue it. Siv registers this and does not push. She does not tell him "
                     "about the branch.", 0.85),
            ],
            thread_ops={
                "T-OTTO": Transition(
                    post=["the reader sees that Otto has noticed something and chose not to look",
                          "Siv withholds what she found, and the withholding is visible as "
                          "behaviour rather than stated"],
                    forbid=["Otto explaining his own motives",
                            "either character naming what the relationship means to them"],
                    to_state="planted"),
                "T-CODE": Transition(
                    pre=["Siv has recorded the unreachable branch's line number"],
                    post=["a second, independent detail about the failures is established that "
                          "the reader can later connect to the branch"],
                    forbid=["Siv sharing the line number with anyone"]),
            },
        ),
        SceneSpec(
            id="s03", index=3, chapter=1, word_target=750,
            pov="beata", characters=["beata", "siv"],
            setting="The eastern parcel, at the well head",
            time="that afternoon",
            summary=("Beata has a buyer and a problem: the registry says the eastern well was "
                     "never independent of the Provision. She wants Siv's help and Siv is "
                     "elsewhere."),
            beats=[
                Beat("Beata's POV, her voice, her competence. The farm is specific and the sale "
                     "is real and imminent.", 0.9),
                Beat("She lays out the registry problem. Siv is physically present and mentally "
                     "on the branch, which Beata notices and names unkindly.", 0.9),
                Beat("Beata asks for a concrete favour with a date attached. Siv agrees "
                     "carelessly, which is worse than refusing.", 0.9),
            ],
            thread_ops={
                "T-WELL": Transition(
                    post=["the well's registry problem is established concretely, with a "
                          "deadline",
                          "the reader understands this has nothing to do with the Provision's "
                          "code"],
                    forbid=["connecting the well to the code error in any way",
                            "Beata learning anything about the branch"],
                    to_state="planted"),
            },
            notes=("This scene belongs to the subplot. The main thread must not appear except "
                   "as Siv's distraction. Resist making the well evidence for anything."),
        ),
        SceneSpec(
            id="s04", index=4, chapter=2, word_target=1400,
            pov="siv", characters=["siv"],
            setting="The founders' documentation archive, a converted grain store",
            time="three days later, overnight",
            summary=("Siv finds the founders' own note about the branch. It is deliberate, it "
                     "is documented, and it has a number attached."),
            beats=[
                Beat("The archive as a physical research problem: incomplete indexes, water "
                     "damage, sixty-year-old handwriting. She is methodical and tired.", 0.9),
                Beat("She finds the reference. Give the reader the founders' actual words, "
                     "short, bureaucratic, and worse for being bureaucratic.", 0.95),
                Beat("An accepted-loss figure. She checks it against current population and "
                     "does the arithmetic. She does not react in summary — she reacts by doing "
                     "something small and practical and wrong.", 0.9),
            ],
            thread_ops={
                "T-CODE": Transition(
                    pre=["Siv has recorded the unreachable branch's line number",
                         "a second detail about the failures is established"],
                    post=["the reader now knows the error is deliberate and was documented as "
                          "an accepted loss with a figure",
                          "Siv holds a physical document she could show someone"],
                    forbid=["the narration explaining what this means for the town",
                            "Siv deciding anything about what to do",
                            "a founder appearing as a character"],
                    to_state="complicated"),
            },
        ),
        SceneSpec(
            id="s05", index=5, chapter=2, word_target=1100,
            pov="siv", characters=["siv", "otto"],
            setting="Otto's kitchen",
            time="the next night",
            summary=("Siv tells Otto. He understands immediately and his first instinct is "
                     "containment, not outrage — which is when the real problem becomes "
                     "visible."),
            beats=[
                Beat("She tells him badly. He is quiet for too long. Establish that he grasps "
                     "the technical point faster than she expected.", 0.9),
                Beat("His response is about what will happen to Hallowmere if people know, not "
                     "about whether it is true. Siv had not thought that far and it lands.",
                     0.9),
                Beat("They do not agree and do not fight. The scene ends with a practical "
                     "arrangement that is really a decision neither of them named.", 0.9),
            ],
            thread_ops={
                "T-CHOICE": Transition(
                    post=["the dilemma is on the page as two costed roads, with neither "
                          "presented as correct",
                          "the cost of exposure is voiced by a character who loves the town"],
                    forbid=["either character stating the theme of the story",
                            "the narration adjudicating between the two roads",
                            "a resolution or a plan of action"],
                    to_state="dilemma_visible"),
                "T-OTTO": Transition(
                    pre=["Otto has noticed something and chose not to look"],
                    post=["Otto's earlier incuriosity is retroactively legible as a choice he "
                          "made repeatedly"],
                    forbid=["Otto apologising", "Otto being cast as complicit or as a villain"],
                    to_state="complicated"),
            },
        ),
        SceneSpec(
            id="s06", index=6, chapter=2, word_target=850,
            pov="beata", characters=["beata", "lund"],
            setting="The council registry office",
            time="the same week, a working morning",
            summary=("Beata takes the well problem to Lund alone. The registry entry was "
                     "altered sixty years ago and the reason is mundane and unhelpful."),
            beats=[
                Beat("Lund is procedural and genuinely trying. The bureaucracy is not a "
                     "metaphor; it is just how the office works.", 0.9),
                Beat("The alteration is found. Its reason is trivial — a surveying convenience, "
                     "a clerk's shortcut — and it is irreversible in practice.", 0.9),
                Beat("Beata's sale is now in jeopardy for a stupid reason. She leaves with a "
                     "form and no remedy, and takes it out on the wrong person.", 0.9),
            ],
            thread_ops={
                "T-WELL": Transition(
                    pre=["the well's registry problem is established with a deadline"],
                    post=["the reason for the alteration is revealed and is mundane",
                          "the sale is materially threatened"],
                    forbid=["the alteration turning out to be connected to the founders' error",
                          "Siv appearing in this scene"],
                    to_state="complicated"),
            },
            notes=("The main plot does not appear in this scene at all. If it does, the subplot "
                   "has been converted into set dressing and the plan has failed marker 1."),
        ),
        SceneSpec(
            id="s07", index=7, chapter=3, word_target=1500,
            pov="siv", characters=["siv", "otto", "lund"],
            setting="A council hearing room, informal session",
            time="ten days later",
            summary=("Siv brings the document to Lund. Nobody can read it, and the "
                     "unreadability becomes the whole problem."),
            beats=[
                Beat("Siv presents. Lund needs a process, and there is no process for this. "
                     "Otto's position in the room is ambiguous and he does not clarify it.",
                     0.9),
                Beat("The document is passed around and means nothing to anyone. Siv's "
                     "authority is also her isolation: she is the only witness and the only "
                     "possible liar.", 0.95),
                Beat("The stakes change shape — it is no longer whether to tell, it is that "
                     "telling does not work. End on a concrete consequence, not a reflection.",
                     0.9),
            ],
            thread_ops={
                "T-CODE": Transition(
                    pre=["Siv holds a physical document she could show someone"],
                    post=["the proof is delivered and fails to function as proof",
                          "an institutional consequence follows that Siv did not anticipate"],
                    forbid=["anyone in the room being convinced by the document alone",
                            "the founders' motives being explained"],
                    to_state="escalated"),
                "T-CHOICE": Transition(
                    pre=["the dilemma is on the page as two costed roads"],
                    post=["the cost of the exposure road is now specific and attached to named "
                          "people"],
                    forbid=["Siv making her choice in this scene",
                            "the narration naming what the story is about"],
                    to_state="cost_named"),
            },
        ),
        SceneSpec(
            id="s08", index=8, chapter=3, word_target=1000,
            pov="beata", characters=["beata", "siv", "otto"],
            setting="The eastern parcel, the sisters' kitchen",
            time="two days later",
            summary=("The sisters collide. Beata's sale is collapsing and Siv's problem has "
                     "made her useless as family, and Otto arrives with news that removes "
                     "Siv's remaining options."),
            beats=[
                Beat("The domestic argument, specific and unfair, about the favour Siv agreed "
                     "to in scene 3 and did not do.", 0.9),
                Beat("Otto arrives. What he brings is procedural and closes a door — an "
                     "institutional response to scene 7 that nobody chose and everyone "
                     "permitted.", 0.9),
                Beat("Beata learns roughly what is happening and her reaction is about the "
                     "farm, not about the town. She is not wrong to feel that way.", 0.9),
            ],
            thread_ops={
                "T-CHOICE": Transition(
                    pre=["the cost of the exposure road is specific and attached to named "
                         "people"],
                    post=["Siv's options are reduced to two by circumstance rather than by her "
                          "own decision"],
                    forbid=["Siv choosing", "anyone giving Siv permission or absolution"],
                    to_state="forced"),
                "T-OTTO": Transition(
                    post=["Otto acts, and the action is neither betrayal nor rescue"],
                    forbid=["Otto dying, leaving, or being injured",
                            "Otto delivering a speech about the covenant"],
                    to_state="escalated"),
                "T-WELL": Transition(
                    pre=["the sale is materially threatened"],
                    post=["Beata commits to a course of action about the farm that does not "
                          "depend on Siv"],
                    forbid=["the well problem being solved by anything in the main plot"],
                    to_state="escalated"),
            },
        ),
        SceneSpec(
            id="s09", index=9, chapter=4, word_target=1300,
            pov="siv", characters=["siv", "otto"],
            setting="Substation four, the pump house, at the reader terminal",
            time="the following night",
            summary=("Siv can execute the branch or leave it unreachable. The scene is the "
                     "physical act, and Otto is there for it."),
            beats=[
                Beat("Return to the room from scene 1, and make the return structural rather "
                     "than sentimental — the same equipment, a different problem.", 0.9),
                Beat("The technical act, concretely: what she would have to do, what it does, "
                     "what it cannot be undone from.", 0.95),
                Beat("Otto's presence is not permission. He does something small and useful, "
                     "the way he has for twenty-two years, and that is the whole of the "
                     "resolution between them.", 0.9),
            ],
            thread_ops={
                "T-CODE": Transition(
                    pre=["the proof is delivered and fails to function as proof"],
                    post=["the branch's status is settled, irreversibly, on the page",
                          "the reader understands exactly what was done and what it costs"],
                    forbid=["the narration summarising the meaning of the act",
                            "a last-minute revelation that removes the cost"],
                    to_state="paid_off"),
                "T-OTTO": Transition(
                    pre=["Otto acts, and the action is neither betrayal nor rescue"],
                    post=["the relationship reaches its end state through action, not "
                          "conversation"],
                    forbid=["reconciliation dialogue", "Otto being forgiven or condemned"],
                    to_state="paid_off"),
            },
        ),
        SceneSpec(
            id="s10", index=10, chapter=4, word_target=1150,
            pov="beata", characters=["beata", "siv"],
            setting="The eastern parcel, the well head",
            time="six weeks later",
            summary=("The aftermath from outside Siv's head. Beata's well is still wrong, her "
                     "sale went how it went, and Hallowmere is living with what Siv did."),
            beats=[
                Beat("Beata's POV so the consequence is measured by someone who did not choose "
                     "it. Concrete state of the farm and the sale.", 0.9),
                Beat("What the town knows and how it has metabolised it — specific, ordinary, "
                     "unheroic. Nobody thanks Siv.", 0.9),
                Beat("The sisters, at the well, not resolving. End on something physical that "
                     "the reader can finish for themselves.", 0.9),
            ],
            thread_ops={
                "T-CHOICE": Transition(
                    pre=["Siv's options are reduced to two by circumstance"],
                    post=["the cost of the road not taken is legible on the page",
                          "no character and no narration adjudicates whether she was right"],
                    forbid=["a closing line that states the theme",
                            "the town rallying, or condemning her as a group"],
                    to_state="chosen"),
                "T-WELL": Transition(
                    pre=["Beata commits to a course of action about the farm"],
                    post=["the well thread ends with an answer that does not solve Beata's "
                          "problem"],
                    forbid=["the well being fixed", "the well turning out to have mattered to "
                            "the main plot all along"],
                    to_state="paid_off"),
            },
        ),
    ]


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "runs/glitch")
    project = Project(root, build_story(), build_plan())
    project.save()
    print(f"built {root}")
    print(f"  {len(project.plan)} scenes, "
          f"{sum(s.word_target for s in project.plan)} target words")
    print(f"  {len(project.story.threads)} threads, "
          f"{len(project.story.characters)} characters")
    print(f"\nnext:  python -m redthread audit {root}")


if __name__ == "__main__":
    main()
