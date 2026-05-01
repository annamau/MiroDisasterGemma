# Aurora — Usage guide

How to run, demo, and troubleshoot Aurora. For the *what* and *why*, read the
[README](../README.md). For *how to add new scenarios or interventions*, read
[EXTENDING.md](./EXTENDING.md).

## TL;DR

```bash
./start.sh           # full stack: Neo4j + backend + frontend (dev)
./start.sh prod      # full stack with prod build (recording-quality)
./start.sh check     # health-check every endpoint
./start.sh stop      # kill everything we started
./start.sh help      # all flags
```

Open <http://localhost:3000/aurora?seed=demo> (dev) or <http://localhost:4173/aurora?seed=demo> (prod).

---

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python 3.13+ | required | backend runtime (older may work; tested on 3.13) |
| Node 20+ | required | vite + vue-tsc require modern node |
| npm 10+ | required | ships with node 20+ |
| Docker | recommended | runs Neo4j 5.18 (graph storage) |
| Ollama 0.4+ | recommended | serves Gemma 4 e2b/e4b for the LLM-backed demo |
| Bash 3.2+ | required | start.sh — macOS default bash works |

`start.sh` will tell you what's missing on first run. Set `AURORA_NO_DOCKER=1`
or `AURORA_NO_OLLAMA=1` to silence warnings if you knowingly skip those.

## First-time setup (~5 min if Ollama already installed)

```bash
# 1. Clone
git clone https://github.com/annamau/MiroDisasterGemma.git aurora
cd aurora

# 2. Pull Gemma 4 models (~5 GB total, one-time)
ollama pull gemma4:e2b
ollama pull gemma4:e4b

# 3. Boot
./start.sh
```

The first boot installs Python deps, npm deps, and pulls the Neo4j image.
Subsequent boots are ~5 seconds.

## Daily commands

| Command | What it does |
|---|---|
| `./start.sh` | dev mode — backend on :5001, vite dev on :3000, hot reload |
| `./start.sh prod` | prod mode — backend on :5001, vite preview on :4173 (use this for the recorded demo) |
| `./start.sh backend` | backend only — useful when iterating on Python |
| `./start.sh frontend` | frontend only — useful when iterating on Vue |
| `./start.sh prewarm` | one-shot: chat each Gemma 4 model + run a small MC trial to warm KV cache (run T-30min before recording) |
| `./start.sh check` | health-check; greps `/health`, `/api/scenario/list`, runs a 1-trial MC, reports green/red |
| `./start.sh stop` | kills any process we started; leaves Neo4j up (use `docker compose down` for that) |
| `./start.sh clean` | nuke `__pycache__`, `dist/`, `.vite`, `/tmp/aurora-*.log` |

## URLs

| URL | What's there |
|---|---|
| <http://localhost:3000/aurora?seed=demo> | dev mode demo (auto-runs after 1s beat) |
| <http://localhost:3000/aurora> | dev mode, manual scenario + intervention selection |
| <http://localhost:4173/aurora?seed=demo> | prod build preview |
| <http://localhost:5001/health> | `{"service":"Aurora Backend","status":"ok"}` |
| <http://localhost:5001/api/scenario/list> | JSON list of all 6 scenarios |
| <http://localhost:5001/api/scenario/interventions> | JSON list of all available interventions |
| <http://localhost:7474> | Neo4j browser (user: `neo4j`, password: `aurora`) |

## The 6 scenarios

| ID | Hazard | Notes |
|---|---|---|
| `la-puente-hills-m72-ref` | earthquake | LA M7.2 reference, USGS PHBT scenario, 8 districts |
| `valencia-dana-2024` | flood | DANA 29-Oct-2024, AEMET 491mm Chiva, 230+ deaths |
| `pompeii-79` | wildfire | Vesuvius AD 79, Sigurdsson et al. ash maps |
| `joplin-ef5-2011` | hurricane | EF5 22 May 2011, NWS Springfield post-event survey |
| `turkey-syria-m78-2023` | earthquake | M7.8 doublet 6 Feb 2023, includes Aleppo + Idlib |
| `atlantis` | earthquake | Plato's Atlantis — openly mythological, "fun closer" |

Honest framing: every non-earthquake scenario reuses Aurora's seismic HAZUS
fragility curves as a damage proxy. Numbers are useful for **intervention
ranking** but not absolute death prediction. Real flood inundation-depth
fragility is on the README's "What's next".

## API quick reference

```bash
# List scenarios
curl http://localhost:5001/api/scenario/list

# List all preset interventions
curl http://localhost:5001/api/scenario/interventions

# Run synchronous Monte Carlo (≤30s wait for response)
curl -X POST -H 'Content-Type: application/json' \
  -d '{
    "intervention_ids": ["vlc_evac_es_alert_4h_early"],
    "n_trials": 30,
    "n_population_agents": 80,
    "duration_hours": 24,
    "use_llm": false
  }' \
  http://localhost:5001/api/scenario/valencia-dana-2024/run_mc

# Run streaming Monte Carlo (returns run_id immediately)
curl -X POST -H 'Content-Type: application/json' \
  -d '{"intervention_ids":["..."], "streaming": true, ...}' \
  http://localhost:5001/api/scenario/<id>/run_mc
# Then poll:
curl http://localhost:5001/api/scenario/<id>/run_mc/<run_id>/progress
curl http://localhost:5001/api/scenario/<id>/run_mc/<run_id>/result
```

The streaming endpoint is what `MCProgressPanel.vue` uses to render the live
bars + agent decision feed during the demo.

## Demo recipe (the WOW path)

```bash
# T-30 min: warm Ollama
./start.sh prewarm

# T-5 min: launch
./start.sh prod

# Open http://localhost:4173/aurora?seed=demo
# Recording starts when the page loads.
```

The page auto-fires a 20-trial MC with 3 high-impact LA interventions after
a 1-second idle beat. The full reveal lands in ~45-90s with Gemma 4 enabled.

To switch to **the Valencia local-angle demo**:

1. Open <http://localhost:4173/aurora> (no `?seed=demo`)
2. Click 🌊 **Valencia DANA 29-Oct-2024**
3. Toggle on all 4 Valencia interventions
4. Click **Run Monte Carlo**

The ES-Alert intervention alone reduces deaths by **~29% [27%–31% CI]** vs.
baseline — verified end-to-end at n_trials=2 in synth mode.

> **Honest framing.** Aurora is a hackathon prototype that **ranks
> interventions**, not one that predicts absolute deaths. Our synth-mode
> Valencia baseline overshoots the real ~230 DANA fatalities by roughly
> 7× because we're reusing seismic HAZUS fragility curves as a proxy for
> flood damage (real Hazus-FL inundation-depth fragility is on the
> roadmap). The 29% relative-effect estimate is what the paired Monte
> Carlo design supports; the absolute numbers are simulator artifacts
> until §4 of [EXTENDING.md](./EXTENDING.md) lands.

## Troubleshooting

**Backend won't start** — check `/tmp/aurora-backend.log`. Common causes:
- Port 5001 already in use → `lsof -i :5001` to find the offender, kill it, or set `FLASK_PORT=5002 ./start.sh backend`.
- Neo4j refusing auth → drop the volume: `docker volume rm neo4j_data && docker compose up -d`.

**Frontend stuck on "Loading scenarios"** — backend isn't responding. Run `./start.sh check` to confirm the API is up.

**MC takes 60+ seconds with `use_llm=true`** — Ollama is cold. Run `./start.sh prewarm` and wait for it to finish before triggering the demo.

**Reduce-motion ON but animations still play** — the page caches `matchMedia` on first mount. Hard-reload (cmd+shift+R) after toggling.

**Bundle size complaint in `npm run build`** — chunks > 500 kB raw is normal; gzipped is what matters (target ≤ 320 kB total). The CSS chunk includes 4 npm-bundled font families.

**`./start.sh check` reports `LA M7.2 MC smoke: failed`** — the backend booted but `run_monte_carlo` is timing out. Check `/tmp/aurora-backend.log` for an exception trace. Most often: a stale `__pycache__` from a previous version. Run `./start.sh clean && ./start.sh dev`.

**Port 7474 / 7687 already in use** — you have another Neo4j running. Either `docker stop` it or set `AURORA_NO_DOCKER=1` and point `NEO4J_URI` at the existing instance via `.env`.

**`mirofish` strings in screenshots** — should not happen post-D1. If they do, run `bash frontend/tests/d1-mirofish-grep.test.sh` to find leaks.

## Logs and PIDs

`start.sh` writes everything to `$AURORA_LOG_DIR` (default `/tmp`):

| File | What |
|---|---|
| `/tmp/aurora-backend.log` | Flask stdout/stderr |
| `/tmp/aurora-frontend.log` | vite stdout/stderr |
| `/tmp/aurora-prewarm.log` | last prewarm run output |
| `/tmp/aurora-backend.pid` | backend PID (used by `./start.sh stop`) |
| `/tmp/aurora-frontend.pid` | frontend PID |

Override with `AURORA_LOG_DIR=/path/to/logs ./start.sh dev`.

## Tests

```bash
# Backend
cd backend && python -m pytest tests/ -v

# Frontend
cd frontend && npm test
# Includes: tokens (WCAG contrast), components (vitest), mirofish-grep guard

# Performance benchmarks
cd backend && python -m pytest tests/test_aurora_perf.py -v -s
# Prints actual wall times; tests assert thresholds
```

Total: 30 backend + 28 frontend = 58 tests.

## Configuration

`.env.example` is the template. Copy to `.env` for overrides:

```bash
cp .env.example .env
```

Key variables:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=aurora        # default in docker-compose.yml
LLM_BASE_URL=http://localhost:11434/v1   # Ollama
LLM_MODEL_NAME=gemma4:e4b    # primary model (responder + report)
TRIAGE_MODEL_NAME=gemma4:e2b # fast NPC model
EMBEDDING_MODEL=nomic-embed-text
FLASK_PORT=5001
FLASK_HOST=0.0.0.0
```

If you change `NEO4J_PASSWORD`, also drop the volume: `docker volume rm
neo4j_data` (Neo4j only reads the env on first boot of a fresh volume).
