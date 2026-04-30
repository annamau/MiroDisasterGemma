# Aurora performance baseline — Gemma 4 on this laptop

**Date**: 2026-04-28
**Hardware**: Darwin 24.6.0 (macOS), Apple Silicon (M-series), Ollama 0.21.2 native
**Models**: pulled and live in Ollama at `http://localhost:11434`

## Empirical tok/s (Ollama `/api/chat`, JSON-output, 120-token cap)

| Model | Mean wall (s) | Mean gen tok/s | P0 gate | Pass? |
|---|---:|---:|---:|---:|
| `gemma4:e2b` | 3.15 | **87.1** | ≥60 | ✅ |
| `gemma4:e4b` | 8.27 | **52.3** | ≥35 | ✅ |

Run-by-run (3 runs each, 102-tok prompt + 120-tok generation):

```
gemma4:e2b: 83.7 / 88.0 / 89.6 tok/s   wall: 6.34 / 1.58 / 1.52 s
gemma4:e4b: 50.3 / 53.3 / 53.3 tok/s   wall: 19.86 / 2.47 / 2.48 s
```

Run 1 includes cold-load wall-time. Steady-state is run 2-3.

## Implication for Monte Carlo math

v2 plan assumed E2B at 95 tok/s. **Empirical: 87 tok/s** (8% lower, still well above plan's 50-tok/s pessimistic case). E4B empirical 52 tok/s confirms reviewer's number.

Recompute v2 MC budget with empirical numbers:

```
100 agents × 10 decision points × 50 trials × 3 interventions = 150,000 calls
60% cache hit (honest target)                                 →  60,000 cold calls
80-token avg response @ 87 tok/s                              =   0.92 s/call
60,000 × 0.92 s                                              =   55,200 s = 15.3 hours single-thread
2× parallel Ollama (RAM-realistic on 32GB)                   =   7.7 hours pre-compute
```

**Verdict: feasible**. Pre-compute cache overnight on a desktop, ship cache file with repo, demo plays back from cache (airplane-mode demo target).

## Workarounds adopted (validated empirically 2026-04-28)

- **`/v1/chat/completions` returns empty `content` on `gemma4:e4b`** — verified locally. Reviewer's flag of Ollama issue [#15288](https://github.com/ollama/ollama/issues/15288) is real today.
- **Native `/api/chat` + `format: "json"` works cleanly** — validated with NER on a disaster scenario, parsed 7 entities cleanly in 11.9s.
- **`num_predict` must be generous** (≥1500) when `format: "json"` is set, otherwise Gemma 4 may exhaust budget on internal reasoning and return empty content.
- **System prompt should be terse and emit-immediately** (e.g. "You are a strict JSON extractor. No thinking, no preamble. Emit JSON immediately.") — reduces leakage to the thinking channel.
- **All Aurora LLM calls must route through a thin wrapper** (`backend/app/services/llm_client.py`, to be added in P1) that:
  - Calls `/api/chat` not `/v1/chat/completions`
  - Sets `stream: false` until [#15315](https://github.com/ollama/ollama/issues/15315) is fixed
  - Sets `format: "json"` for structured calls
  - Uses adequate `num_predict`
- **Skip Ollama multimodal in default path** — text-focused integration as of Apr 2026. Vision/audio reserved as bonus if Ollama ships clean support before May 18.

## Reproduce

```bash
ollama serve &
python3 /tmp/bench_gemma4.py
```

Script: see git history for `/tmp/bench_gemma4.py` snapshot or run inline from this commit.
