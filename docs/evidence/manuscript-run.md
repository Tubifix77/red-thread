# First complete manuscript — run record

The Inherited Glitch, 10 scenes, 12,169 words, generated 2026-08-28 entirely on
qwen3:8b (every role) via Ollama on an RTX 3080 10GB. Zero API calls.

## Seams (closing words -> opening words)

**s1 → s2**
> …the Provision had done what it had. She only needed to remember.
> Siv Alderman stood in the maintenance yard, the morning air sharp with…

**s2 → s3**
> …the Provision had done what it had. She only needed to remember.
> Beata stood at the well head, the sun glinting off the rusted…

**s3 → s4**
> …And Beata had hers, the one that ended when the sale closed.
> Siv stood in the maintenance yard, the notebook in her hand. She…

**s4 → s5**
> …founders had left behind, and she would not let them stop her.
> Siv walked into Otto’s kitchen, the notebook tucked under her arm, the…

**s5 → s6**
> …due to age. He had known. He had not said a word.
> Beata stood at the edge of the registry office’s desk, the pressure…

**s6 → s7**
> …end of anything. That it was just the beginning of something else.
> Siv Alderman stood in the council chamber, her notebook tucked under her…

**s7 → s8**
> …voice was quiet. “And now you know what you have to do.”
> Beata was standing at the well, the pressure gauge in her hand,…

**s8 → s9**
> …a kind of language, a kind of code, a kind of failure.
> Siv Alderman stepped into the pump house, the same place she had…

**s9 → s10**
> …had changed the town. She had done what she needed to do.
> Beata stood at the well, the pressure gauge in her hand, its…

## Cross-scene 5-grams in 3+ scenes (the honest prose verdict)

27 distinct phrases, worst offenders:

- x5: “she didn t need to”
- x4: “tucked under her arm the”
- x4: “the notebook in her hand”
- x4: “the cold storage failures had”
- x4: “notebook tucked under her arm”
- x4: “didn t say anything she”
- x4: “didn t need to she”
- x3: “the pressure gauge in her”
- x3: “the numbers didn t add”
- x3: “the notebook tucked under her”

These are an 8B writer's tics, surfaced by the system's own cross-corpus checks and
committed as MINOR by policy. Two of them — a closing line copied verbatim into the
next scene's ending, and eight of ten scenes opening on name-plus-stance — became
deterministic checks (`seam_tail_copy`, the stance opener) the same night.
