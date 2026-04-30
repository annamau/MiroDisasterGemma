"""
Aurora LLM client — thin wrapper around Ollama's native /api/chat endpoint.

Why this wrapper exists (verified empirically 2026-04-28; see docs/perf-baseline.md):

1. /v1/chat/completions returns empty `content` for gemma4:e4b on Ollama 0.21.x
   (issue #15288). Native /api/chat works.
2. Tool-call streaming on gemma4 is broken (issue #15315). We use stream:false.
3. format=json + small num_predict can exhaust budget on internal reasoning,
   leaving content empty (issue #15260). We default num_predict to 1500 for
   structured calls.
4. Aurora needs tiered routing: gemma4:e2b for fast NPC / population-agent
   decisions, gemma4:e4b for responder dispatch + report synthesis.

This module is the ONE place all Aurora services should call for LLM inference.
The legacy MiroFish code paths still use openai.ChatCompletions for backwards
compatibility — we don't touch those.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.config import Config

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    wall_seconds: float
    eval_count: int
    prompt_eval_count: int
    raw: dict[str, Any]

    @property
    def gen_tps(self) -> float:
        eval_dur_ns = self.raw.get("eval_duration", 0)
        if eval_dur_ns <= 0:
            return 0.0
        return self.eval_count / (eval_dur_ns / 1e9)


class LLMClient:
    """Native Ollama /api/chat wrapper with Aurora-specific defaults."""

    DEFAULT_TIMEOUT = 180

    def __init__(self, base_url: str | None = None) -> None:
        # base_url like http://localhost:11434/v1 → strip /v1 to hit native API.
        configured = base_url or Config.LLM_BASE_URL
        self.host = configured.rstrip("/").removesuffix("/v1")
        self.chat_url = f"{self.host}/api/chat"

    # ---- public API ----

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        json_mode: bool = False,
        max_tokens: int = 600,
        temperature: float = 0.3,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> LLMResponse:
        """Single non-streaming chat completion.

        Set json_mode=True to constrain output via Ollama's `format: json`.
        Bumps num_predict to >=1500 in that case to avoid empty-content bug.
        """
        chosen_model = model or Config.LLM_MODEL_NAME

        if json_mode:
            # Empty-content bug: with format=json, internal reasoning can eat
            # the entire budget. Always give it room. (#15260)
            max_tokens = max(max_tokens, 1500)

        body: dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "stream": False,  # tool-call streaming broken on gemma4 (#15315)
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }
        if json_mode:
            body["format"] = "json"

        return self._post(self.chat_url, body, chosen_model, timeout)

    def chat_json(
        self,
        system: str,
        user: str,
        *,
        model: str | None = None,
        max_tokens: int = 1500,
        temperature: float = 0.1,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> tuple[dict[str, Any] | list[Any] | None, LLMResponse]:
        """Convenience: one-shot system+user → parsed JSON.

        Returns (parsed_or_none, raw_response). Caller can inspect raw on parse fail.
        """
        # Reinforce "no preamble" — Gemma 4's thinking mode otherwise leaks
        # natural-language reasoning into the content channel even with format=json.
        terse_system = (
            f"{system}\n\nOutput strict JSON only. No preamble, no markdown fences, "
            "no thinking. Emit JSON immediately."
        )
        msgs = [
            {"role": "system", "content": terse_system},
            {"role": "user", "content": user},
        ]
        resp = self.chat(
            msgs, model=model, json_mode=True,
            max_tokens=max_tokens, temperature=temperature, timeout=timeout,
        )
        parsed = _safe_json_parse(resp.content)
        return parsed, resp

    # ---- routed convenience ----

    def fast(self, **kwargs: Any) -> LLMResponse:
        """Route to gemma4:e2b — population/NPC fast path."""
        return self.chat(model=Config.TRIAGE_MODEL_NAME, **kwargs)

    def reason(self, **kwargs: Any) -> LLMResponse:
        """Route to gemma4:e4b — responder dispatch + report synthesis."""
        return self.chat(model=Config.REASONING_MODEL_NAME, **kwargs)

    # ---- internals ----

    def _post(
        self, url: str, body: dict[str, Any], model: str, timeout: int,
    ) -> LLMResponse:
        encoded = json.dumps(body).encode()
        req = urllib.request.Request(
            url, data=encoded, headers={"Content-Type": "application/json"},
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
        except urllib.error.URLError as exc:
            wall = time.perf_counter() - t0
            logger.error("LLM call failed (%s) after %.1fs: %s", model, wall, exc)
            raise
        wall = time.perf_counter() - t0
        msg = data.get("message", {})
        content = msg.get("content", "") or ""

        if not content and data.get("done_reason") == "stop":
            # Reasoning leak — content went to thinking channel. Surface for caller.
            logger.warning(
                "LLM returned empty content (model=%s, eval=%s). "
                "Likely reasoning-leak bug; consider raising num_predict or "
                "softening system prompt.",
                model, data.get("eval_count"),
            )

        return LLMResponse(
            content=content,
            model=model,
            wall_seconds=wall,
            eval_count=data.get("eval_count", 0),
            prompt_eval_count=data.get("prompt_eval_count", 0),
            raw=data,
        )


def _safe_json_parse(text: str) -> dict[str, Any] | list[Any] | None:
    """Tolerant JSON parse — strips fences, falls back to first {...} or [...] block."""
    if not text:
        return None
    cleaned = text.strip()
    # Strip ```json fences (some Gemma 4 variants ignore format=json)
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rstrip("`").strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Fallback: find first complete JSON object/array
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = cleaned.find(opener)
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == opener:
                depth += 1
            elif cleaned[i] == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


# Module-level singleton — safe because client is stateless.
_default_client: LLMClient | None = None


def get_default_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
