"""Ollama discovery: list what is actually installed, so nothing has to be guessed.

Verified 2026-08-27:
  GET  http://localhost:11434/api/tags   -> {"models": [{name, model, size, details{...}}]}
  POST http://localhost:11434/api/show   -> {details{...}, capabilities[...]}
  OpenAI-compatible base: http://localhost:11434/v1  (/v1/chat/completions, /v1/models);
  api_key is required by the OpenAI SDK shape but ignored by Ollama.

Sources: ollama/ollama docs/api.md; docs.ollama.com/api/openai-compatibility.

Note the two base URLs are different: this module talks to the *native* API at `/api/...` for
discovery, while `llm.OpenAICompatBackend` talks to `/v1/...` for generation. Passing one where
the other is expected is the obvious mistake, so `native_base` converts.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_OPENAI_BASE = "http://localhost:11434/v1"


class OllamaUnavailable(RuntimeError):
    pass


@dataclass
class InstalledModel:
    name: str
    size_bytes: int = 0
    parameter_size: str = ""
    quantization: str = ""
    family: str = ""

    @property
    def size_gb(self) -> float:
        return self.size_bytes / (1024 ** 3)

    def fits_in(self, vram_gb: float, headroom_gb: float = 1.5) -> bool:
        """Whether the weights plus a rough allowance leave room on a card of this size.

        This is a crude filter, not a promise. The KV cache grows with context length and is not
        counted here, so a model that "fits" by this test can still fail to load at a long
        context. Treat it as a shortlist, and confirm by loading it.
        """
        return self.size_gb + headroom_gb <= vram_gb

    @property
    def is_embedding(self) -> bool:
        """Embedding models cannot write prose, and offering one as a writer is a wasted run.

        Heuristic on the name rather than a /api/show call per model: the authoritative answer is
        in that endpoint's `capabilities` list, but it costs a round trip each and the naming
        convention is near-universal.
        """
        lowered = self.name.lower()
        return any(marker in lowered for marker in
                   ("embed", "bge-", "gte-", "all-minilm", "e5-", "reranker"))

    def describe(self) -> str:
        bits = [f"{self.size_gb:.1f} GB"]
        if self.parameter_size:
            bits.append(self.parameter_size)
        if self.quantization:
            bits.append(self.quantization)
        return f"{self.name:34} {' · '.join(bits)}"


def native_base(base_url: str = DEFAULT_OPENAI_BASE) -> str:
    """Turn an OpenAI-compatible base URL into the native API root."""
    trimmed = base_url.rstrip("/")
    return trimmed[: -len("/v1")] if trimmed.endswith("/v1") else trimmed


def list_installed(base_url: str = DEFAULT_OPENAI_BASE,
                   timeout: int = 10) -> list[InstalledModel]:
    """Everything `ollama pull`ed on this machine, largest last."""
    url = f"{native_base(base_url)}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise OllamaUnavailable(
            f"could not reach Ollama at {url} ({type(exc).__name__}: {exc}). "
            f"Is it running? Try: ollama serve") from exc

    return parse_tags(payload)


def parse_tags(payload: dict) -> list[InstalledModel]:
    """Turn an `/api/tags` response into models, largest last.

    Split out from the fetch so it can be tested against a canned payload — the parsing is where
    the field-name assumptions live (`model` vs `name`, `details.parameter_size`), and those are
    exactly what a future Ollama release could change under us.
    """
    out: list[InstalledModel] = []
    for row in payload.get("models") or []:
        if not isinstance(row, dict):
            continue
        details = row.get("details") or {}
        out.append(InstalledModel(
            name=row.get("model") or row.get("name") or "",
            size_bytes=int(row.get("size") or 0),
            parameter_size=details.get("parameter_size") or "",
            quantization=details.get("quantization_level") or "",
            family=details.get("family") or "",
        ))
    out = [m for m in out if m.name]
    out.sort(key=lambda m: m.size_bytes)
    return out


def resolve(name: str, base_url: str = DEFAULT_OPENAI_BASE) -> str:
    """Match a user-typed model name against what is installed.

    Ollama names carry tags (`qwen3:14b`), and typing the bare name is the obvious slip. Rather
    than letting generation fail hundreds of tokens later with an opaque 404, resolve up front
    and fail with the actual list of candidates.
    """
    installed = list_installed(base_url)
    names = [m.name for m in installed]
    if name in names:
        return name

    prefix = [n for n in names if n.split(":")[0] == name.split(":")[0]]
    if len(prefix) == 1:
        return prefix[0]

    partial = [n for n in names if name.lower() in n.lower()]
    if len(partial) == 1:
        return partial[0]

    candidates = prefix or partial or names
    raise OllamaUnavailable(
        f"'{name}' is not installed. " +
        (f"Did you mean one of: {', '.join(candidates)}?" if candidates
         else "No models are installed — try: ollama pull qwen3:8b"))
