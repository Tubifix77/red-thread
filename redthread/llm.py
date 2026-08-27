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
import socket
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

    reasoning_overhead = 4000
    """Tokens to add to a whole-scene output budget to leave room for inline reasoning.

    A whole-scene call must return the entire scene or the truncation guard rejects it, so the
    budget has to cover any reasoning the model emits *before* the prose. Where reasoning is
    switched off or returned in its own field this is zero and the budget can be tight — which
    matters, because a loose budget also lets a rambling draft run six times past its target, and
    that costs a minute of generation before any check gets to reject it.
    """

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 4096,
                 temperature: float = 1.0, stop: list[str] | None = None,
                 json_mode: bool = False) -> Reply:
        """`json_mode` asks the backend to constrain output to valid JSON where it can.

        Advisory, not a contract: backends that cannot do it ignore the flag, and callers
        must still parse defensively. Where it *is* honoured it removes the parse-failure
        class outright, which is worth the extra parameter.
        """
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
                 temperature: float = 1.0, stop: list[str] | None = None,
                 json_mode: bool = False) -> Reply:
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
                 temperature: float = 1.0, stop: list[str] | None = None,
                 json_mode: bool = False) -> Reply:
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


# --------------------------------------------------------------------------------------
# Ollama, native API
# --------------------------------------------------------------------------------------

class OllamaBackend(Backend):
    """Ollama's own `/api/chat`, not its OpenAI-compatible shim.

    Worth a second backend for two reasons, both of which cost this project real debugging time
    before the API docs were read properly:

    * **`think` is a first-class parameter here**, and reasoning comes back in its own
      `message.thinking` field rather than inline in the content. That removes the failure mode
      that silently destroyed fact extraction — `<think>` blocks derailing the JSON — at the
      source rather than by stripping them afterwards. Setting `think=False` for structured calls
      also removes the reasoning tokens entirely, which is most of the latency.
    * **`format="json"` constrains output to valid JSON.** For the structured probes this turns
      "parse defensively and hope" into a guarantee.

    Ollama's thinking docs describe `think` on `/api/chat` and `/api/generate` and say nothing
    about the `/v1` endpoint supporting it, which is the practical reason to prefer this one.

    Verified 2026-08-27 (docs.ollama.com/capabilities/thinking, ollama/ollama docs/api.md):
      POST http://localhost:11434/api/chat
      body:     model, messages, stream:false, think, format, options{temperature, num_predict}
      text at:  response["message"]["content"]
      thinking: response["message"]["thinking"]
    """

    name = "ollama"

    def __init__(self, model: str, base_url: str = "http://localhost:11434",
                 think: bool | str | None = False, timeout: int = 240,
                 retries: int = 2, keep_alive: str | None = "10m") -> None:
        self.model = model
        # Tolerate being handed the OpenAI-compatible URL, since that is what every other part
        # of the CLI passes around.
        trimmed = base_url.rstrip("/")
        self.base_url = trimmed[:-3] if trimmed.endswith("/v1") else trimmed
        self.think = think
        self.timeout = timeout
        self.retries = retries
        self.keep_alive = keep_alive

    @property
    def reasoning_overhead(self) -> int:
        # Reasoning arrives in `message.thinking`, never inline, so the prose budget needs no
        # allowance for it whether thinking is on or off.
        return 0

    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 4096,
                 temperature: float = 1.0, stop: list[str] | None = None,
                 json_mode: bool = False) -> Reply:
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        options: dict = {"temperature": temperature, "num_predict": max_tokens}
        if stop:
            options["stop"] = stop

        body: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if self.think is not None:
            body["think"] = self.think
        if json_mode:
            body["format"] = "json"
        if self.keep_alive:
            body["keep_alive"] = self.keep_alive

        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        payload = _send(request, self.timeout, self.retries)
        message = payload.get("message") or {}
        text = message.get("content") or ""
        # `thinking` is deliberately discarded: it is the model's scratchpad, and mixing it into
        # the text is exactly the bug this backend exists to avoid.
        return Reply(text, payload.get("prompt_eval_count", 0), payload.get("eval_count", 0),
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
        except (TimeoutError, socket.timeout) as exc:
            # Do not retry a timeout. If a request did not finish inside the budget it will not
            # finish inside the same budget again, and retrying turns one slow call into three:
            # a real run spent 28 minutes on a single repair — 600s x 3 attempts — before failing
            # anyway. A clean failure after one timeout is strictly better than a stall.
            raise LLMError(
                f"timed out after {timeout}s (not retried — a repeat would take as long). "
                f"Lower the token budget, use a smaller model, or raise the timeout."
            ) from exc
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            # A URLError wrapping a timeout is the same situation wearing a different exception.
            if isinstance(getattr(exc, "reason", None), (TimeoutError, socket.timeout)):
                raise LLMError(f"timed out after {timeout}s (not retried)") from exc
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
                     critic_model: str = "claude-sonnet-5", native: bool = True) -> "Models":
        """Local prose, hosted structure. The hybrid this project expects to be the sweet spot
        — though that is reasoning, not a measured result."""
        writer = (OllamaBackend(writer_model, base_url, think=False) if native
                  else OpenAICompatBackend(writer_model, base_url))
        return cls(writer, AnthropicBackend(critic_model), AnthropicBackend(critic_model))

    @classmethod
    def all_local(cls, model: str, base_url: str = "http://localhost:11434/v1",
                  native: bool = True, think_writer: bool | str = False) -> "Models":
        """Every role on one local model.

        Uses Ollama's native API by default, with thinking off. Both matter: `think=False`
        removes the reasoning that silently broke fact extraction and most of the latency with
        it, and the native endpoint returns any reasoning in its own field rather than inline.
        Pass `native=False` for a non-Ollama OpenAI-compatible server (vLLM, LM Studio,
        llama.cpp), which loses those two properties.

        Thinking stays off for the structured roles unconditionally: their output is a fixed
        schema, and reasoning there buys nothing while costing the whole latency budget.
        """
        if not native:
            backend = OpenAICompatBackend(model, base_url)
            return cls(backend, backend, backend)
        structured = OllamaBackend(model, base_url, think=False)
        writer = (structured if think_writer is False
                  else OllamaBackend(model, base_url, think=think_writer))
        return cls(writer, structured, structured)


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

    # Last resort: the reply may be well-formed JSON that simply ran out of tokens. This is not
    # an edge case with local models — a real extraction spent its entire 8000-token budget
    # enumerating facts and was cut off mid-object, and discarding it threw away 250 perfectly
    # good facts along with the broken tail.
    salvaged = _salvage_truncated(text)
    if salvaged is not None:
        try:
            return json.loads(salvaged)
        except json.JSONDecodeError:
            pass

    raise LLMError(f"no parseable JSON in reply: {text[:300]}")


def _salvage_truncated(text: str) -> str | None:
    """Close off JSON that was cut off mid-value, keeping every complete element.

    Trims back to the last structurally complete element and appends the closing brackets the
    prefix is missing. Bracket counting skips anything inside a string literal, so a `}` in a
    fact's text does not confuse it; a prefix ending *inside* a string is unsalvageable and
    returns None rather than guessing.
    """
    end = max(text.rfind("}"), text.rfind("]"))
    if end < 0:
        return None
    prefix = text[:end + 1]

    stack: list[str] = []
    in_string = escaped = False
    for char in prefix:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            stack.append(char)
        elif char in "]}" and stack:
            stack.pop()

    if in_string or not stack:
        return None
    return prefix + "".join("]" if opener == "[" else "}" for opener in reversed(stack))


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
