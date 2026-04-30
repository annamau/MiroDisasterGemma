"""
Decision cache — make Monte Carlo on a laptop feasible.

Why this exists
---------------
Empirical perf: Gemma 4 e2b 87 tok/s, e4b 52 tok/s. A naive Aurora MC run is:
    100 agents x 10 decision points x 50 trials x 3 interventions = 150K calls
    @ 80 tok avg @ 87 tok/s        =>  ~38 hours single-thread.
Unacceptable for a hackathon demo. But: most agent decisions in disaster sims
are *highly redundant* — same archetype, same local conditions, same hour →
same decision distribution. A 60% cache hit rate brings 38h down to ~15h
single-thread, which precomputes overnight on the dev laptop. Demo plays
back from cache in real time.

Design
------
- Key  = sha256(model | system | user) hex digest. Deterministic. Identical
  prompts collide, which is the whole point.
- Value = {content, model, gen_tps, eval_count, ts}. We store the full
  content so playback returns the exact original LLM output.
- Storage = single JSONL file (append-only), loaded into memory on init.
  Append + fsync per write so a crash doesn't lose the precompute pack.
  No DB dep, no extra service.
- The cache is content-addressed, so two scenarios that produce the same
  agent decision share the entry. Pre-baked pack ships with the repo for
  the demo path.

Wrapping pattern
----------------
    cache = get_default_cache()
    response = cache.get_or_call(
        client.chat_json,
        system=...,
        user=...,
        model=...,
    )

The cache decorates `LLMClient.chat_json` — call site looks identical.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("aurora.decision_cache")


def _key(model: str, system: str, user: str) -> str:
    h = hashlib.sha256()
    h.update(model.encode("utf-8"))
    h.update(b"\x00")
    h.update(system.encode("utf-8"))
    h.update(b"\x00")
    h.update(user.encode("utf-8"))
    return h.hexdigest()


@dataclass
class CacheEntry:
    key: str
    content: str
    model: str
    gen_tps: float
    eval_count: int
    ts: float


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    writes: int = 0
    saved_seconds: float = 0.0
    spent_seconds: float = 0.0


class DecisionCache:
    """File-backed JSONL cache for Aurora LLM decisions."""

    def __init__(self, path: Path | str | None = None) -> None:
        default = Path(__file__).resolve().parents[3] / "data" / "decision_cache.jsonl"
        self.path = Path(path) if path else default
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._mem: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self.stats = CacheStats()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            logger.info("Decision cache initialized (empty) at %s", self.path)
            return
        n = 0
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    e = CacheEntry(**rec)
                    self._mem[e.key] = e   # last-write-wins
                    n += 1
                except Exception:
                    logger.warning("Skipping malformed cache line")
        logger.info("Decision cache loaded: %d entries from %s", n, self.path)

    def _append(self, entry: CacheEntry) -> None:
        line = json.dumps(entry.__dict__, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
                os.fsync(f.fileno())
            self._mem[entry.key] = entry
            self.stats.writes += 1

    def get(self, model: str, system: str, user: str) -> CacheEntry | None:
        return self._mem.get(_key(model, system, user))

    def put(
        self, *, model: str, system: str, user: str,
        content: str, gen_tps: float, eval_count: int,
    ) -> CacheEntry:
        entry = CacheEntry(
            key=_key(model, system, user),
            content=content, model=model,
            gen_tps=gen_tps, eval_count=eval_count, ts=time.time(),
        )
        self._append(entry)
        return entry

    def get_or_call(
        self,
        chat_json: Callable[..., tuple[Any, Any]],
        *,
        system: str,
        user: str,
        model: str,
        **kwargs: Any,
    ) -> tuple[Any, str, bool]:
        """Cache wrapper around an LLMClient.chat_json-style callable.

        Returns (parsed_or_none, raw_content, was_cached). The wrapped
        callable is expected to return (parsed, response_with_.content_attr).
        """
        cached = self.get(model, system, user)
        if cached is not None:
            self.stats.hits += 1
            self.stats.saved_seconds += (
                cached.eval_count / max(cached.gen_tps, 1.0)
            )
            try:
                parsed = json.loads(cached.content)
            except Exception:
                parsed = None
            return parsed, cached.content, True

        self.stats.misses += 1
        t0 = time.perf_counter()
        parsed, resp = chat_json(system=system, user=user, model=model, **kwargs)
        wall = time.perf_counter() - t0
        self.stats.spent_seconds += wall

        content = getattr(resp, "content", "") or ""
        gen_tps = getattr(resp, "gen_tps", 0.0)
        eval_count = getattr(resp, "eval_count", 0)
        self.put(
            model=model, system=system, user=user,
            content=content, gen_tps=gen_tps, eval_count=eval_count,
        )
        return parsed, content, False

    def report(self) -> dict[str, Any]:
        total = self.stats.hits + self.stats.misses
        hit_rate = (self.stats.hits / total) if total else 0.0
        return {
            "entries": len(self._mem),
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "hit_rate": round(hit_rate, 3),
            "writes": self.stats.writes,
            "spent_seconds": round(self.stats.spent_seconds, 1),
            "saved_seconds": round(self.stats.saved_seconds, 1),
            "path": str(self.path),
        }


_default_cache: DecisionCache | None = None
_cache_lock = threading.Lock()


def get_default_cache() -> DecisionCache:
    global _default_cache
    if _default_cache is None:
        with _cache_lock:
            if _default_cache is None:
                _default_cache = DecisionCache()
    return _default_cache
