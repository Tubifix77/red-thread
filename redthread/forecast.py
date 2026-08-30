"""Tension as forecastability — the experiment, kept where it can be repeated.

Phase 2 of docs/PLAN.md. The idea is sourced (RESEARCH.md section 9): narrative tension is
downstream of hidden information, so a scene a model can call from the story so far has none.
The lexical implementation of it failed its control — the real scene beat a random other scene
from the same book **41% of the time**, worse than chance — and `probe_forecast` is shipped off
with that result in its docstring.

The plan said the 35 predictions were on disk and a semantic re-score would be free. **They were
not.** `probe_forecast` only ever records a Violation when the overlap clears its threshold, and
across the whole corpus none did, so the calibration ran in a throwaway script and left nothing
behind. That is the more useful finding of the two: an experiment whose output is a pass/fail
verdict cannot be re-analysed, and this project's most expensive negative result had to be paid
for twice.

So predictions are persisted here, as data, with the context that produced them. Three questions
can then be asked of one generation run:

    step 10   does *meaning* overlap separate a right guess from a wrong one, where word
              overlap could not?
    step 11   the control, run before anything is believed: predicted scene against a random
              other scene from the same book. Below about 65% and embeddings have failed the
              same way words did.
    step 12   with k predictions per scene, how much do they disagree *with each other*? That
              never touches the actual scene, so the book's shared vocabulary cannot confound
              it — which is the failure mode that killed both earlier attempts.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .embed import Embedder, cosine
from .llm import LLMError, Models
from .verify import FORECAST_PROMPT, JSON_ONLY, STRUCTURED_BUDGET, _clip, forecast_overlap
from .llm import parse_json


@dataclass
class Prediction:
    """One blind guess at one scene, with everything needed to score it later."""
    index: int
    """The scene being predicted."""
    context: str
    """The story-so-far the model was shown. Kept so a re-score cannot silently change it."""
    predictions: list[str] = field(default_factory=list)
    """k blind guesses. More than one only for step 12."""


def story_so_far(texts: list[str], scenes: int = 3, tail: int = 800) -> str:
    """The same window `write_scene` gives the probe, so a stored run matches a live one."""
    return "\n\n".join(t[-tail:] for t in texts[-scenes:])


def predict(context: str, models: Models, k: int = 1,
            temperature: float = 0.0) -> list[str]:
    """k blind predictions from one context.

    Blind is the whole point and was the original bug: the first version of this prompt contained
    the actual scene and then asked the model to "predict it before reading what happens next",
    so what came back was a rationalisation. The model sees the story so far and nothing else.

    For k > 1 the temperature must not be zero, or the k samples are one sample repeated and the
    spread measured in step 12 is identically zero. The caller is trusted to know this; the
    default is the single-sample case at 0.0, which is what the shipped probe uses.
    """
    prompt = FORECAST_PROMPT.format(context=_clip(context, 1200), json_only=JSON_ONLY)
    out: list[str] = []
    for _ in range(max(1, k)):
        try:
            reply = models.critic.complete(prompt, max_tokens=STRUCTURED_BUDGET,
                                           temperature=temperature, json_mode=True)
            data = parse_json(reply.text)
        except LLMError:
            continue
        if isinstance(data, dict):
            guess = str(data.get("prediction", "")).strip()
            if guess:
                out.append(guess)
    return out


def sample_scenes(count: int, wanted: int, first: int = 4) -> list[int]:
    """Evenly spaced scene indices to predict, as 0-based positions in the committed list.

    Skips the opening scenes: a prediction from a context of nothing is a prediction about a
    premise, and scoring it measures how well the premise describes its own first chapter.
    """
    usable = list(range(first, count))
    if not usable:
        return []
    if wanted >= len(usable):
        return usable
    step = len(usable) / wanted
    return [usable[int(i * step)] for i in range(wanted)]


def generate(texts: list[str], models: Models, wanted: int = 35, k: int = 1,
             temperature: float = 0.0, on_scene=None, store: Path | None = None
             ) -> list[Prediction]:
    """Blind predictions for evenly spaced scenes of a finished book.

    Saves after every scene when given a `store`. With k = 5 this is 175 model calls sharing a
    GPU with a book being written, which is the better part of an hour — and a job that writes
    nothing until it finishes is one interruption away from having produced nothing at all. That
    is the failure this module exists because of, and it would have been rebuilt here.
    """
    out: list[Prediction] = []
    for position in sample_scenes(len(texts), wanted):
        context = story_so_far(texts[:position])
        guesses = predict(context, models, k=k, temperature=temperature)
        if guesses:
            out.append(Prediction(index=position, context=context, predictions=guesses))
            if store is not None:
                save(out, store)
        if on_scene is not None:
            on_scene(position, guesses)
    return out


def save(predictions: list[Prediction], path: Path) -> None:
    Path(path).write_text(
        json.dumps([asdict(p) for p in predictions], indent=2, ensure_ascii=False),
        encoding="utf-8")


def load(path: Path) -> list[Prediction]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Prediction(**row) for row in raw]


# --------------------------------------------------------------------------------------
# scoring, always against a control
# --------------------------------------------------------------------------------------

@dataclass
class ScoreResult:
    """A scorer's verdict, and the control that says whether to believe it."""
    name: str
    on_target: float
    """Mean score of a prediction against the scene it was predicting."""
    on_control: float
    """Mean score of the same prediction against a random other scene from the same book."""
    win_rate: float
    """How often the real scene beat the random one. This is the number that matters."""
    n: int

    def verdict(self, floor: float = 0.65) -> str:
        if self.n < 10:
            return "too few predictions to say anything"
        if self.win_rate < 0.55:
            return "CHANCE — this scorer cannot tell a right guess from a wrong one"
        if self.win_rate < floor:
            return f"below the {floor:.0%} bar — not usable"
        return "clears the bar"


def score(predictions: list[Prediction], texts: list[str], scorer, name: str,
          seed: int = 0) -> ScoreResult:
    """Score every prediction against its scene and against a random other scene.

    The control is not optional and is not a second step. Lexical overlap produced a distribution
    that looked entirely reasonable on its own — mean .538, range .26 to .73 — and was noise; the
    only thing that revealed it was scoring the same guesses against scenes they were not about.
    So the two are computed together and the win rate is what gets reported, because an absolute
    similarity is a property of the book's vocabulary and not of the prediction.
    """
    rng = random.Random(seed)
    on_target: list[float] = []
    on_control: list[float] = []
    wins = 0
    for prediction in predictions:
        guess = prediction.predictions[0] if prediction.predictions else ""
        if not guess or prediction.index >= len(texts):
            continue
        others = [i for i in range(len(texts)) if i != prediction.index]
        if not others:
            continue
        real = scorer(guess, texts[prediction.index])
        decoy = scorer(guess, texts[rng.choice(others)])
        on_target.append(real)
        on_control.append(decoy)
        wins += real > decoy
    n = len(on_target)
    return ScoreResult(
        name=name,
        on_target=sum(on_target) / n if n else 0.0,
        on_control=sum(on_control) / n if n else 0.0,
        win_rate=wins / n if n else 0.0,
        n=n)


def lexical_scorer(guess: str, scene: str) -> float:
    """The shipped implementation, kept as the thing to beat."""
    return forecast_overlap(guess, scene)


def semantic_scorer(embedder: Embedder):
    """Cosine between the prediction and the scene, in meaning space.

    A raw cosine here is not comparable to a raw lexical overlap and must never be printed beside
    one as though it were — unrelated sentences score around .43 with this model. Only the win
    rate is comparable between the two, which is the reason `score` returns it.
    """
    def run(guess: str, scene: str) -> float:
        return cosine(embedder.one(guess), embedder.one(scene))
    return run


def prediction_spread(prediction: Prediction, embedder: Embedder) -> float:
    """How much k blind guesses at one scene disagree with each other, 0 to 1.

    Step 12, and the reason it is worth trying after two failures: this never looks at the actual
    scene. Both earlier attempts foundered on a prediction and a scene sharing the book's
    furniture rather than its events, and a measure that never sees the scene cannot be
    confounded that way. A scene the model can call has low spread; a scene it cannot has high.

    Returns 1 - the mean pairwise cosine, so larger means less predictable — the same direction
    as tension.
    """
    guesses = prediction.predictions
    if len(guesses) < 2:
        return 0.0
    vectors = embedder.embed(guesses)
    pairs = [cosine(vectors[i], vectors[j])
             for i in range(len(vectors)) for j in range(i + 1, len(vectors))]
    return 1.0 - (sum(pairs) / len(pairs)) if pairs else 0.0


# --------------------------------------------------------------------------------------
# step 16: does a declared dependency leave a trace in the prose?
# --------------------------------------------------------------------------------------

def declared_vs_random(plan, texts: list[str], embedder: Embedder,
                       seed: int = 0) -> ScoreResult:
    """Is a scene closer to its declared ancestors than to a random earlier scene?

    The check that decides whether `depends_on` is worth its place in the schema. If a declared
    dependency leaves no trace in the prose, the field is bookkeeping — the planner writing down
    an intention the writer never acted on — and the graph audit is measuring the planner rather
    than the book.

    Same shape as `score`, and for the same reason: an absolute similarity between two scenes of
    one novel is a property of the novel's vocabulary and setting, so only the comparison against
    a scene that is *not* an ancestor means anything. Two scenes in the same book with the same
    cast in the same town will always look similar; the question is whether the declared ones
    look more similar than that.

    Uses direct edges rather than the transitive closure. A closure over a well-connected graph
    reaches most of the book, and a control drawn from "everything else" would be drawn from
    almost nothing.
    """
    rng = random.Random(seed)
    by_position = {s.index: i for i, s in enumerate(sorted(plan, key=lambda s: s.index))}
    on_target: list[float] = []
    on_control: list[float] = []
    wins = 0

    for spec in sorted(plan, key=lambda s: s.index):
        position = by_position[spec.index]
        if position >= len(texts) or not spec.depends_on:
            continue
        declared = [by_position[e] for e in spec.depends_on
                    if e in by_position and by_position[e] < position]
        declared = [p for p in declared if p < len(texts)]
        others = [p for p in range(position) if p not in declared]
        if not declared or not others:
            continue

        scene = embedder.one(texts[position])
        real = max(cosine(scene, embedder.one(texts[p])) for p in declared)
        decoy = cosine(scene, embedder.one(texts[rng.choice(others)]))
        on_target.append(real)
        on_control.append(decoy)
        wins += real > decoy

    n = len(on_target)
    return ScoreResult(
        name="declared dependency",
        on_target=sum(on_target) / n if n else 0.0,
        on_control=sum(on_control) / n if n else 0.0,
        win_rate=wins / n if n else 0.0,
        n=n)
