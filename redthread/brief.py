"""The scene brief: everything one generation session is allowed to know.

This is the single most important file in the project. Coherence in a chunked manuscript is
not a property of the model — it is a property of what the brief carries in and what the
verifier refuses to let out.

Two structural decisions, both sourced (docs/RESEARCH.md):

*Section ordering.* Liu et al. (TACL 2024) found a U-shaped attention curve: models use
information at the beginning and end of a context far better than information in the middle.
So hard constraints — the voice contract, the thread operations this scene must effect, the
prohibitions — sit at the two ends. The bulky reference material (the ledger slice) sits in
the middle, on purpose: the brief only has to make continuity *likely*, because the verifier
makes it *checked*. Never rely on the middle of a prompt for a guarantee you can test for.

*Cohesion is separate from coherence.* STORYTELLER draws this distinction explicitly and
gives cohesion its own enforcement module. Here it gets its own brief section: the verbatim
tail of the previous scene, the character overlap, and the hand-off.
"""

from __future__ import annotations

from .ledger import Ledger
from .models import Fact, SceneSpec, StorySpec, Thread

TAIL_WORDS = 150

# Negative constraints derived from StoryScope's measured AI-vs-human gaps
# (RESEARCH.md section 6). These are the tells that survive style scrubbing, so they belong in
# the brief as prohibitions rather than being left to a cleanup pass.
ANTI_TELLS = [
    "Do not have the narration explain what the scene means. AI fiction states its theme "
    "explicitly in 77% of stories against 52% for human fiction — the narrator naming the "
    "point is the single loudest tell. Dramatise; never gloss.",
    "Do not route emotion through the body as a reflex. AI fiction conveys feeling through "
    "physical sensation and bodily metaphor in 81% of stories against 38% for humans. No "
    "tightening chests, dropping stomachs, or breath the character did not know they were "
    "holding. At most one somatic beat in this scene, and only if it earns its place.",
    "Do not write dialogue as philosophical debate. Characters want things from each other; "
    "they are not exchanging positions on the theme.",
    "Write what happens, not what had happened. Past perfect — \"she had run the system, it "
    "had settled, she had not expected\" — is the grammar of recap, and a page made of it is a "
    "summary wearing a scene's clothes. The cleanest drafts measured use it in about one "
    "sentence in ten; scenes written for this project sit at four in ten, and one ran to "
    "forty-six such sentences in a row. Never write more than two of them consecutively. "
    "Backstory in one clause is fine; the scene itself happens in simple past.",
    "Name things specifically. Prefer the actual brand, book, song, street, or make of car to "
    "a vague allusion. AI fiction uses named references at 24% against 47% for humans.",
    "Do not resolve tension through the protagonist's decisive agency by default. Human "
    "fiction lets circumstance, other people, and accident carry outcomes far more often.",
]


def _fmt_list(items: list[str], bullet: str = "- ") -> str:
    return "\n".join(f"{bullet}{i}" for i in items) if items else "(none)"


def render_thread_ops(spec: SceneSpec, story: StorySpec) -> str:
    """The red threads this scene is responsible for, as explicit operators.

    ConWriter's (Pre, Post, Forbid) formulation. This is what turns "keep the story coherent"
    into a set of statements a checker can evaluate one by one.
    """
    if not spec.thread_ops:
        return "(this scene advances no tracked thread — unusual, check the spec)"

    blocks = []
    for tid, op in spec.thread_ops.items():
        thread: Thread | None = story.thread(tid)
        name = thread.name if thread else tid
        kind = thread.kind.value if thread else "unknown"
        state = thread.current_state if thread else "unknown"

        lines = [f"### {tid} — {name}  ({kind}, currently: {state})"]
        if op.pre:
            lines.append("Already true entering this scene:")
            lines.append(_fmt_list(op.pre, "  - "))
        lines.append("This scene MUST bring about:")
        lines.append(_fmt_list(op.post, "  - "))
        if op.to_state:
            lines.append(f"  - thread state must end at: {op.to_state}")
        if op.forbid:
            lines.append("This scene must avoid all of the following:")
            lines.append(_fmt_list(op.forbid, "  - "))
        if thread and thread.concealment:
            # Tension is downstream of hidden information (RESEARCH.md section 9). Telling the
            # writing session what to withhold is as important as telling it what to reveal —
            # and telling it a reveal-scene to keep concealing is a contradiction it cannot
            # satisfy, so from reveal_scene on the line flips.
            if thread.reveal_scene is None or spec.index < thread.reveal_scene:
                lines.append(f"Still concealed from the reader: {thread.concealment}")
            elif spec.index == thread.reveal_scene:
                lines.append(f"THIS is the scene that discloses what was concealed: "
                             f"{thread.concealment}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def render_cohesion(spec: SceneSpec, story: StorySpec, previous_tail: str,
                    previous_characters: list[str]) -> str:
    """The seam section. Kept separate from coherence, per STORYTELLER."""
    if not previous_tail:
        if spec.index <= 1:
            return "This is the opening scene. There is no previous text to carry forward."
        # Writing out of order defeats the point: every brief is built from committed state, so
        # a gap means this scene is being written against a ledger missing a scene of facts.
        return (f"WARNING: scene {spec.index - 1} has not been committed, so there is no "
                f"previous text to carry forward and no facts from it in the ledger above. "
                f"Scenes should be written in order.")

    overlap = [c for c in spec.characters if c in previous_characters]
    names = [story.character(c).name if story.character(c) else c for c in overlap]

    lines = [
        "The previous scene ended with exactly this text. Read it as the reader just did — "
        "your first sentence lands immediately after it:",
        "",
        f"    …{previous_tail}",
        "",
        "Open so that a reader feels one continuous narrative, not a new beginning:",
        "  - Do not re-establish anything the passage above already established.",
        "  - Do not restate or paraphrase its closing image. Move.",
        "  - Do not open with the weather, waking up, or a name and a verb of arrival.",
        "  - The passage above is also off limits at the END of your scene. A scene that closes "
        "on the previous scene's closing words reads as a loop, and one real run produced "
        "exactly that: two sentences repeated verbatim, one scene later.",
    ]
    if names:
        lines.append(
            f"  - Carried over from the previous scene: {', '.join(names)}. Their state at the "
            "end of that passage is their state at the start of this one."
        )
    else:
        lines.append(
            "  - No character carries over, so this is a hard cut. Earn it: the first line "
            "must orient the reader in the new place and time without a summary of travel."
        )
    return "\n".join(lines)


def render_brief(
    spec: SceneSpec,
    story: StorySpec,
    ledger: Ledger,
    previous_tail: str = "",
    previous_characters: list[str] | None = None,
    slop_sample: list[str] | None = None,
) -> str:
    """Assemble the complete brief for one scene-writing session."""
    previous_characters = previous_characters or []
    pov = story.character(spec.pov)
    pov_name = pov.name if pov else spec.pov

    present = [story.character(c) for c in spec.characters]
    present = [c for c in present if c]

    # --- ledger slice: only what touches this scene -------------------------------------
    subjects = [c.name for c in present] + [spec.setting]
    slice_facts: list[Fact] = ledger.about(subjects, spec.index)
    pov_knows = ledger.knows(pov_name, spec.index) if pov else []

    parts: list[str] = []

    # ============================ HEAD: the task and the voice ==========================
    parts.append(
        f"# Write scene {spec.index} of \"{story.title}\"\n\n"
        f"Target length: {spec.word_target} words (±15%). Prose only — no headings, no "
        f"scene numbers, no commentary, no summary of what you wrote."
    )

    style = story.style
    voice = [
        "## Voice contract",
        f"Point of view: {style.pov}, in {spec.pov and pov_name or 'the POV character'}'s head.",
        f"Tense: {style.tense}.",
    ]
    if style.notes:
        voice.append(style.notes)
    if style.samples:
        # The wording here is load-bearing. An earlier version said only "match this prose", and
        # a local model opened scene one with the first sample verbatim — twice over, across two
        # samples. The samples demonstrate rhythm and diction; they are not text to continue from,
        # and saying so explicitly is cheaper than repairing it afterwards.
        voice.append(
            "\nThese sentences show the RHYTHM AND DICTION to match. They are from elsewhere in "
            "the book. Do not reuse them, quote them, or open with one — write new sentences "
            "that sound like these:")
        voice.extend(f"    {s}" for s in style.samples)
    parts.append("\n".join(voice))

    # ============================ MIDDLE: bulk reference ================================
    static = [
        "## The story",
        f"Premise: {story.premise}",
    ]
    if story.world_rules:
        static.append("\nWorld rules that cannot be broken:")
        static.append(_fmt_list(story.world_rules))
    parts.append("\n".join(static))

    if present:
        cast = ["## Who is in this scene"]
        for c in present:
            marker = " (POV)" if c.id == spec.pov else ""
            cast.append(f"**{c.name}**{marker} — {c.description}")
            if c.voice:
                cast.append(f"    Speech: {c.voice}")
        parts.append("\n".join(cast))

    established = ["## Already established (do not contradict)"]
    established.append(ledger.render(slice_facts))
    if pov_knows:
        established.append(
            f"\n{pov_name} knows the following, and nothing else the story has hidden. "
            f"Do not let them act on information they do not have:"
        )
        established.append(ledger.render(pov_knows))
    parts.append("\n".join(established))

    # ============================ TAIL: constraints and the ask =========================
    parts.append("## Continuity with the previous scene\n" +
                 render_cohesion(spec, story, previous_tail, previous_characters))

    parts.append("## Threads this scene is responsible for\n" +
                 render_thread_ops(spec, story))

    prohibitions = ["## Prohibitions"] + [f"{i+1}. {t}" for i, t in enumerate(ANTI_TELLS)]
    if style.forbidden_phrases:
        prohibitions.append(
            f"{len(ANTI_TELLS)+1}. Never use these phrases: "
            + "; ".join(f'"{p}"' for p in style.forbidden_phrases)
        )
    if slop_sample:
        prohibitions.append(
            f"{len(ANTI_TELLS)+2}. These phrasings are statistically over-represented in "
            f"machine-written prose. Avoid all of them and anything in the same register: "
            + "; ".join(f'"{p}"' for p in slop_sample)
        )
    parts.append("\n".join(prohibitions))

    task = [
        "## What happens",
        f"Setting: {spec.setting}" + (f" — {spec.time}" if spec.time else ""),
        f"Summary: {spec.summary}" if spec.summary else "",
        "",
        "Beats, in order. Each is roughly half a page of story; hit all of them.",
        "They are instructions, not sentences: dramatise each one in your own words. A beat "
        "copied into the prose reads as an outline read aloud, and is rejected as one.",
    ]
    task = [t for t in task if t != ""]
    for i, beat in enumerate(spec.beats, 1):
        task.append(f"  {i}. {beat.summary}")
    if spec.notes:
        task.append(f"\nAlso: {spec.notes}")
    # The target is stated at the top of the brief and again here, in the last line. Those are the
    # two positions a model actually attends to (Liu et al.), and real runs came back consistently
    # short — around two thirds of target — with the figure given only once, at the far end of a
    # 1,000-word brief. Restating it costs nine words.
    task.append(
        f"\nWrite the scene now, in full. Begin with the first sentence of prose, cover every "
        f"beat above, and write about {spec.word_target} words — a scene much shorter than that "
        f"has skipped a beat or summarised one."
    )
    parts.append("\n".join(task))

    return "\n\n".join(parts)


def tail_of(text: str, words: int = TAIL_WORDS) -> str:
    parts = text.split()
    return " ".join(parts[-words:]) if parts else ""
