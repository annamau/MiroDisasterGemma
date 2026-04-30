"""Prime Ollama by issuing one small chat to each Aurora model.

Run this BEFORE recording the demo so the model weights are already in RAM
when the user clicks "Run Monte Carlo". Cold-start on a 4 GB Q4 model can
add 8–15 s to the first response, which makes a recorded demo look frozen.

Usage:
    python backend/scripts/prewarm_ollama.py
    OLLAMA_HOST=http://localhost:11434 python backend/scripts/prewarm_ollama.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
MODELS = [
    os.environ.get("AURORA_FAST_MODEL", "gemma4:e2b"),
    os.environ.get("AURORA_PRIMARY_MODEL", "gemma4:e4b"),
]
PROMPT = "Reply with a single word: ready"
TIMEOUT_S = 60


def _post(path: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_HOST}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        body = resp.read().decode("utf-8")
    # Ollama streams ndjson by default; non-stream mode returns one JSON.
    return json.loads(body.split("\n")[-1] or body)


def prewarm(model: str) -> tuple[bool, float, str]:
    t0 = time.time()
    try:
        out = _post(
            "/api/chat",
            {
                "model": model,
                "stream": False,
                "messages": [{"role": "user", "content": PROMPT}],
            },
        )
        wall = time.time() - t0
        msg = out.get("message", {}).get("content", "").strip()
        return True, wall, msg or "(empty)"
    except urllib.error.HTTPError as e:
        return False, time.time() - t0, f"HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, time.time() - t0, f"URL error: {e.reason}"
    except Exception as e:  # noqa: BLE001
        return False, time.time() - t0, f"{type(e).__name__}: {e}"


def main() -> int:
    print(f"Prewarming Ollama at {OLLAMA_HOST} …")
    failures = 0
    for model in MODELS:
        if not model:
            continue
        ok, wall, msg = prewarm(model)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {model:24s}  {wall:5.2f}s  {msg[:60]}")
        if not ok:
            failures += 1
    if failures:
        print(f"\n{failures} model(s) failed. Is Ollama running? `ollama serve`")
        return 1
    print("\nAll models warm. You can record the demo now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
