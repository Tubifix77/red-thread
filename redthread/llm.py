"""Model adapter. Standard library only — no SDK, no dependency to pin.

Two backends, because the two kinds of call in this system have opposite requirements:

* **Prose generation** tolerates a weaker model. It is forgiving, it is the bulk of the token
  spend, and it is the natural place for a local model.
* **The structured stages** — fact extraction, contradiction judgement, the anti-tell probes —
  need reliable JSON and careful reading. These are where a small local model is most likely to
  fail, and where failure is silent: a malformed extraction does not error, it just quietly
  stops protecting continuity.

So the roles are configured separately and default to different models. Whether local models can
carry the structured roles is listed as untested in docs/RESEARCH.md.

API facts verified 2026-08-27 against platform.claude.com:
  POST https://api.anthropic.com/v1/messages
  headers: x-api-key, anthropic-version: 2023-06-01, content-type: application/json
  body:    model, max_tokens, messages[{role, content}]
  text at: response["content"][0]["text"]
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class LLMError(RuntimeError):
    pass


@dataclass
class Reply:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""


class Backend:
    name = "base"

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 4096,
                 temperature: float = 1.0, stop: list[str] | None = None) -> Reply:
        raise NotImplementedError


# --------------------------------------------------------------------------------------
# Anthropic
# --------------------------------------------------------------------------------------

class AnthropicBackend(Backend):
    name = "anthropic"

    def __init__(self, model: str, api_key: str | None = None, timeout: int = 300,
                 retries: int = 3) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.timeout = timeout
        self.retries = retries
        if not self.api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 4096,
                 temperature: float = 1.0, stop: list[str] | None = None) -> Reply:
        body: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        if stop:
            body["stop_sequences"] = stop

        request = urllib.request.Request(
            ANTHROPIC_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            method="POST",
        )
        payload = _send(request, self.timeout, self.retries)
        blocks = payload.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        usage = payload.get("usage") or {}
        return Reply(text, usage.get("input_tokens", 0), usage.get("output_tokens", 0),
                     payload.get("model", self.model))


# --------------------------------------------------------------------------------------
# OpenAI-compatible (Ollama, llama.cpp, vLLM, LM Studio)
# --------------------------------------------------------------------------------------

class OpenAICompatBackend(Backend):
    name = "openai-compat"

    def __init__(self, model: str, base_url: str = "http://localhost:11434/v1",
                 api_key: str | None = None, timeout: int = 600, retries: int = 2) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        # Local servers ignore the key but usually require the header to be present.
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "local")
        self.timeout = timeout
        self.retries = retries

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 4096,
                 temperature: float = 1.0, stop: list[str] | None = None) -> Reply:
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        body: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stop:
            body["stop"] = stop

        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            method="POST",
        )
        payload = _send(request, self.timeout, self.retries)
        choices = payload.get("choices") or []
        if not choices:
            raise LLMError(f"no choices in response: {str(payload)[:300]}")
        text = (choices[0].get("message") or {}).get("content", "") or ""
        usage = payload.get("usage") or {}
        return Reply(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
                     payload.get("model", self.model))


def _send(request: urllib.request.Request, timeout: int, retries: int) -> dict:
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            # 429 and 5xx are worth retrying; 4xx otherwise is a bug in our request.
            if exc.code not in (408, 409, 429) and exc.code < 500:
                raise LLMError(f"HTTP {exc.code}: {detail}") from exc
            last = LLMError(f"HTTP {exc.code}: {detail}")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = LLMError(f"{type(exc).__name__}: {exc}")
        if attempt < retries:
            time.sleep(2 ** attempt)
    raise last or LLMError("request failed with no recorded error")


# --------------------------------------------------------------------------------------
# roles
# --------------------------------------------------------------------------------------

@dataclass
class Models:
    """Which backend serves which role.

    `writer` is called once per candidate per scene and dominates cost. `critic` and `extractor`
    are called on every scene too but with much smaller outputs, and they are the roles where a
    weak model degrades continuity silently — so they default to the stronger model even when
    the writer is local.
    """
    writer: Backend
    critic: Backend
    extractor: Backend

    @classmethod
    def anthropic(cls, writer: str = "claude-opus-5",
                  critic: str = "claude-sonnet-5") -> "Models":
        return cls(AnthropicBackend(writer), AnthropicBackend(critic),
                   AnthropicBackend(critic))

    @classmethod
    def local_writer(cls, writer_model: str, base_url: str = "http://localhost:11434/v1",
                     critic_model: str = "claude-sonnet-5") -> "Models":
        """Local prose, hosted structure. The hybrid this project expects to be the sweet spot
        — though that is reasoning, not a measured result."""
        return cls(OpenAICompatBackend(writer_model, base_url),
                   AnthropicBackend(critic_model), AnthropicBackend(critic_model))

    @classmethod
    def all_local(cls, model: str, base_url: str = "http://localhost:11434/v1") -> "Models":
        backend = OpenAICompatBackend(model, base_url)
        return cls(backend, backend, backend)


# --------------------------------------------------------------------------------------
# JSON coaxing
# --------------------------------------------------------------------------------------

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json(text: str) -> dict | list:
    """Extract JSON from a model reply that may be wrapped in prose, fences, or reasoning.

    Models — local ones especially — add commentary around JSON no matter how the prompt is
    worded. Failing hard here would make the pipeline brittle for the exact backends it is meant
    to support, so this tries progressively looser strategies before giving up.

    Reasoning blocks are stripped first, and that is not a nicety. A thinking model emits
    `<think>…</think>` on *structured* calls as readily as on prose ones, and a real run silently
    lost an entire scene's fact extraction to it: the reasoning derailed the brace matching, the
    parse failed, and the only visible symptom was a scene reporting zero facts. Stripping here
    covers every probe at once rather than at each call site.
    """
    text = strip_reasoning(text)
    candidates: list[str] = [text.strip()]
    fenced = _FENCE.search(text)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())

    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if 0 <= start < end:
            candidates.append(text[start:end + 1])

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise LLMError(f"no parseable JSON in reply: {text[:300]}")


# --------------------------------------------------------------------------------------
# reasoning-block stripping
# --------------------------------------------------------------------------------------

_TAGS = r"think|thinking|reason|reasoning|scratchpad|analysis"

_REASONING = re.compile(rf"<({_TAGS})\b[^>]*>.*?</\1\s*>", re.S | re.I)
_UNCLOSED = re.compile(rf"^\s*<({_TAGS})\b[^>]*>.*?(?:\n\s*\n|\Z)", re.S | re.I)
_STRAY_TAG = re.compile(rf"</?({_TAGS})\b[^>]*>", re.I)


def strip_reasoning(text: str) -> str:
    """Remove reasoning blocks from a completion.

    Local thinking models — qwen3, deepseek-r1 and their kin — emit reasoning inline in the
    completion rather than in a separate field. Left in place it wrecks the word count, trips the
    format check, and gets committed into the manuscript. This is not optional tidying: it is the
    difference between a thinking model being usable as a writer here and not.

    Three cases, in order:

    1. A properly closed block. The backreference matters — `</\\1>` rather than any closing tag —
       so a scene that legitimately contains an angle-bracketed word is not eaten.
    2. An *unclosed* opening tag at the very start, which is what a token limit cut mid-thought
       looks like. Dropped to the first blank line, or to the end if there is none.
    3. A stray closing tag with no opener, which happens when a server strips the opening tag but
       not the close.
    """
    cleaned = _REASONING.sub("", text)
    # Only treat a leading tag as an unclosed block: a tag deep in the text is far more likely to
    # be prose than a truncated reasoning dump.
    if _UNCLOSED.match(cleaned):
        cleaned = _UNCLOSED.sub("", cleaned, count=1)
    cleaned = _STRAY_TAG.sub("", cleaned)
    return cleaned.strip()
