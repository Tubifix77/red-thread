"""Embeddings, for the two places lexical overlap has already failed.

Phase 2 of docs/PLAN.md. `nomic-embed-text` has been installed on this machine the whole time
and never used, while two separate measures were built on shared vocabulary and both of them
turned out to be measuring the book's furniture:

    probe_forecast          a two-sentence prediction against an 800-word scene. The real scene
                            beat a random other scene from the same book 41% of the time —
                            worse than chance. Rarity weighting moved it to 51%.
    check_post_reveals…     flagged plan posts sharing words with an active concealment. The
                            reference plan's best writing reuses .67 of its concealment's words
                            and the genuine contradiction reuses .60, because echoing the
                            concealment's language while withholding the disclosure *is* the
                            technique.

Neither is a bug in the arithmetic. Word overlap cannot tell "hints at the secret" from "states
the secret", and it never will. Whether meaning overlap can is an open question this module makes
askable — and step 11 of the plan exists to answer it with a control before anything is believed.

Verified 2026-08-31:
  POST http://localhost:11434/api/embed  {"model": ..., "input": str | list[str]}
    -> {"embeddings": [[float, ...], ...], "model": ..., ...}

Source: ollama/ollama docs/api.md. The older `/api/embeddings` (singular, `prompt`, returns
`embedding`) is deprecated and takes one text per call; this uses the batching endpoint.
"""

from __future__ import annotations

import hashlib
import json
import math
import urllib.error
import urllib.request
from pathlib import Path

from .llm import LLMError
from .ollama import DEFAULT_OPENAI_BASE, native_base

DEFAULT_EMBED_MODEL = "nomic-embed-text"


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity, or 0.0 for a zero vector.

    Not clamped to [0, 1]. Embeddings of unrelated text routinely score .3 to .5 with this
    family of models, so a raw cosine is not a probability and must never be printed as one —
    the number that matters is always a *difference* between two cosines, which is why every
    caller here runs a control.
    """
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class Embedder:
    """Ollama's `/api/embed`, cached by text hash on disk.

    The cache is the reason this is a class rather than a function. Step 10 of the plan re-scores
    a failed experiment with one variable changed, step 11 runs its control, and step 12 may
    generate several predictions per scene — the same scene text is embedded over and over across
    those, and an 800-word embedding takes long enough that recomputing it turns a two-minute
    analysis into a twenty-minute one.

    Keyed by model *and* text, so switching embedding models cannot silently read another
    model's vectors out of the cache. That would produce cosines between two different vector
    spaces, which is a number that looks exactly like a measurement.
    """

    def __init__(self, model: str = DEFAULT_EMBED_MODEL,
                 base_url: str = DEFAULT_OPENAI_BASE,
                 cache_dir: Path | str | None = None, timeout: int = 120) -> None:
        self.model = model
        self.url = f"{native_base(base_url)}/api/embed"
        self.timeout = timeout
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory: dict[str, list[float]] = {}
        self.calls = 0
        self.cached = 0

    def _key(self, text: str) -> str:
        digest = hashlib.sha256(f"{self.model}\x00{text}".encode("utf-8")).hexdigest()
        return digest[:32]

    def _read_cache(self, key: str) -> list[float] | None:
        if key in self._memory:
            return self._memory[key]
        if not self.cache_dir:
            return None
        path = self.cache_dir / f"{key}.json"
        if not path.exists():
            return None
        try:
            vector = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        self._memory[key] = vector
        return vector

    def _write_cache(self, key: str, vector: list[float]) -> None:
        self._memory[key] = vector
        if self.cache_dir:
            (self.cache_dir / f"{key}.json").write_text(json.dumps(vector), encoding="utf-8")

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Vectors for a batch, in order, hitting the network only for cache misses."""
        out: list[list[float] | None] = []
        wanted: list[tuple[int, str, str]] = []
        for i, text in enumerate(texts):
            key = self._key(text)
            hit = self._read_cache(key)
            if hit is None:
                out.append(None)
                wanted.append((i, key, text))
            else:
                self.cached += 1
                out.append(hit)

        if wanted:
            # Counted here rather than inside `_fetch` so the count survives a subclass that
            # replaces the transport — a test double that does not increment it would make
            # "how many network calls did this analysis cost" silently untestable.
            self.calls += 1
            vectors = self._fetch([text for _i, _key, text in wanted])
            if len(vectors) != len(wanted):
                raise LLMError(f"asked {self.model} for {len(wanted)} embeddings and got "
                               f"{len(vectors)}")
            for (i, key, _text), vector in zip(wanted, vectors):
                self._write_cache(key, vector)
                out[i] = vector
        return [v or [] for v in out]

    def one(self, text: str) -> list[float]:
        return self.embed([text])[0]

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.embed([a, b])
        return cosine(va, vb)

    def _fetch(self, texts: list[str]) -> list[list[float]]:
        request = urllib.request.Request(
            self.url,
            data=json.dumps({"model": self.model, "input": texts}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code == 404:
                raise LLMError(
                    f"{self.model} is not installed. `ollama pull {self.model}`") from exc
            raise LLMError(f"HTTP {exc.code} from /api/embed: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise LLMError(f"could not reach {self.url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise LLMError(f"/api/embed returned something that is not JSON: {exc}") from exc

        vectors = payload.get("embeddings")
        if not isinstance(vectors, list):
            raise LLMError(f"/api/embed returned no embeddings: {str(payload)[:200]}")
        return vectors
