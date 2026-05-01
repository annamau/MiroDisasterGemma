<div align="center">

# Aurora — City Resilience Digital Twin

**An offline-first multi-agent disaster-prevention simulator powered by Gemma 4.**

*Cities can't experiment on real residents. Aurora lets them experiment on simulated ones.*

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square)](./LICENSE)
[![Gemma 4](https://img.shields.io/badge/Gemma-4-4285F4?style=flat-square&logo=google&logoColor=white)](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Vue 3](https://img.shields.io/badge/Vue-3.5-4FC08D?style=flat-square&logo=vue.js&logoColor=white)](https://vuejs.org/)
[![Tests](https://img.shields.io/badge/tests-58%20passing-brightgreen?style=flat-square)](#benchmarks)

Built for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon).

</div>

---

## At a glance

- **One question Aurora answers**: *"For this hazard, which prevention investment saves the most lives per dollar — and how confident are we?"*
- **How**: a multi-agent simulation (4 agent classes, 9 population archetypes) under a paired-trial Monte Carlo, with Gemma 4 driving NPC and responder decisions.
- **Where it runs**: a single laptop. Offline. No cloud APIs. No Google Fonts CDN. Models served via Ollama.
- **What you see**: an animated streaming-progress UI during the 20–60 s compute window, then a CountUp reveal of lives saved, dollar impact, and per-intervention deltas with 90 % CIs.

## Problem

Earthquakes, hurricanes, and wildfires don't kill randomly. They kill where the city's response broke a specific way: an ambulance that wasn't pre-staged in the right district, an evacuation order that went out 30 minutes too late, a retrofit that didn't happen on a specific block of wood-frame buildings. Every after-action report of every major urban disaster contains the same paragraph: *"if we'd done X, deaths would have dropped by Y."*

But cities can't run those experiments. You can't actually issue a fake evacuation order to a real LA neighborhood to see what happens. You can't pre-position ambulances in East LA on a Tuesday and then trigger a magnitude 7.2 earthquake. So the experiments don't run, and the cities don't learn.

The 2023 Türkiye earthquake spawned a misinformation cascade on social media that arrived 6× faster than verified reports — a pattern that was visible in real time but unmodeled. The 2023 Maui wildfire had a 2-hour window where authoritative communication channels went silent and rumor filled the gap. The Puente Hills thrust fault under downtown LA could trigger an M7.2 today; the most-cited HAZUS estimate is **3,000–18,000 deaths**, but the bands depend entirely on assumptions about evacuation timing, hospital surge capacity, and public-information channels — none of which any city has rehearsed end-to-end.

Aurora is a hackathon-scale answer to that gap. It is not a production tool, and it is not a peer-reviewed model. It is an interactive, offline-runnable digital twin where the user toggles interventions and watches lives saved and dollars saved emerge from a Monte Carlo over a multi-agent simulation.

## What Aurora does

Aurora simulates a hazard scenario — the demo ships with **six**, mixing real historical events with one openly mythological closer — through a **multi-agent system** with four agent classes that interact across hours of simulated time:

| Scenario | Hazard | Anchor | Notes |
|---|---|---|---|
| 🏔️ LA Puente Hills M7.2 | earthquake | USGS PHBT scenario | reference, 8 districts, 256 buildings |
| 🌊 Valencia DANA 29-Oct-2024 | flood | AEMET 491 mm Chiva, 230+ deaths | local relevance — what if ES-Alert went 4h earlier? |
| 🔥 Pompeii AD 79 | wildfire | Sigurdsson et al. ash maps | real geography, seismic-fragility proxy for pyroclastic damage |
| 💨 Joplin EF5 22-May-2011 | hurricane | NWS Springfield post-event survey | 158 deaths, $2.8 B — deadliest US tornado since 1947 |
| ✨ Türkiye-Syria M7.8 6-Feb-2023 | earthquake | USGS + Stanford IO misinfo analysis | cross-border (Aleppo, Idlib), modeled with the misinfo-cascade angle |
| 🌀 Atlantis | earthquake/flood | Plato Timaeus / Critias (mythological) | "fun closer" — flagged simulation_only; not predictive |

Each scenario runs under 30 ms per Monte Carlo trial through the same orchestrator. Total: 1,236 buildings, 41 districts, all four `HazardKind` values exercised.

```
                    ┌───────────────────────────────┐
                    │   Hazard agents (HAZUS/Worden)│
                    │   shaking · aftershocks       │
                    │   cascade: power → comms      │
                    └──────────────┬────────────────┘
                                   │
                ┌──────────────────┼──────────────────┐
                │                  │                  │
                ▼                  ▼                  ▼
   ┌───────────────────┐  ┌──────────────────┐  ┌──────────────────┐
   │ Population        │  │ First-responder  │  │ Infrastructure   │
   │ 9 archetypes      │  │ EMS · fire ·     │  │ hospitals ·      │
   │ panic, evac,      │  │ police           │  │ shelters · power │
   │ social-media post │  │ finite resources │  │ capacity, fail   │
   └───────────────────┘  └──────────────────┘  └──────────────────┘
                │                  │                  │
                └──────────┬───────┴──────────┬───────┘
                           │                  │
                           ▼                  ▼
                ┌──────────────────────────────────────┐
                │     Monte Carlo orchestrator         │
                │  ≥30 trials per arm · paired design  │
                │  90% CI on lives + dollars saved     │
                └──────────────────────────────────────┘
```

See [docs/aurora-architecture.md](./docs/aurora-architecture.md) for file-level pointers and the intervention-DSL grammar.

**Population archetypes (9, evidence-grounded).** Each population agent is one of: Eyewitness, Coordinator, Amplifier, Authority, Misinformer, Conspiracist, Helper, Helpless, Critic. Mix-shares come from public post-disaster Twitter / Bluesky / Discord datasets (Türkiye 2023, Maui 2023, LA fires 2025). Every archetype has its own posting rate, follower distribution, geo-decay influence, and probability of amplifying misinformation vs. authority.

**Intervention DSL.** Three categories of policy lever, written as small dataclasses in `backend/app/aurora/intervention_dsl.py`:

| Category | Example | What it changes |
|---|---|---|
| Pre-positioning resources | `preposition_d03_4amb` — pre-stage 4 ambulances in East LA (district D03) | adds 4 paramedic units to the responder pool, halves first-arrival time in D03 |
| Timing changes | `evac_d03_30min_early` — issue evac orders 30 minutes earlier with 55% compliance | shifts population evac decisions on a per-archetype compliance distribution |
| Infrastructure hardening | `retrofit_d03_w1` — retrofit 80% of W1 wood-frame buildings in D03 | shifts the HAZUS fragility curve; reduces collapse probability per damage state |

The user picks any combination from the UI; Aurora runs **N independent paired-trial Monte Carlo arms**, then computes 90% confidence intervals on lives saved, dollars saved, and the misinfo-to-authority ratio change against the no-intervention baseline.

**Result reveal.** When the run completes, the UI shows an animated CountUp of the best-arm lives saved, a stagger-in grid of per-intervention delta cards, a comparator-table with horizontal mean-bars and CI overlays, and a cumulative-deaths line chart with stroke-dashoffset reveal. All animations respect `prefers-reduced-motion`. Every number on screen comes from the Monte Carlo run — no static fixtures.

## How to read Aurora's numbers (and what they don't mean)

**Aurora ranks interventions. It does not predict absolute deaths.**

This distinction is load-bearing for the demo and for any pilot conversation. Two reasons:

1. **The Monte Carlo design is paired, not predictive.** Trial #5 of the baseline arm shares its RNG seed with trial #5 of every treatment arm. The only thing that changes between paired trials is the policy lever. So even if Aurora's absolute death counts are off, the **delta between arms** — which intervention saved more lives in the same trial — is robust. We bootstrap 1,000 resamples to get 90 % CIs on those deltas.

2. **Our fragility model is approximate.** Aurora's HAZUS-MH 2.1 seismic fragility curves are real and peer-reviewed *for earthquakes*. For floods (Valencia), wildfires (Pompeii), and tornadoes (Joplin), we currently reuse those curves as a damage proxy, because writing real Hazus-FL inundation-depth fragility, ash-load fragility, and EF-scale wind-DI tables is in the [What's next](#whats-next) list, not in this prototype. The **ranking** of interventions is plausible across all hazard kinds; the **absolute death count** for non-earthquake scenarios is a simulator artifact.

**How to phrase Aurora's results** when showing the demo:

| ✅ Good ("relative effect") | ❌ Misleading ("absolute prediction") |
|---|---|
| "A 4-h-earlier ES-Alert reduces deaths by ~29 % [27 %–31 % CI]" | "Aurora says 503 more people would be alive" |
| "Of the three Valencia interventions tested, ground-floor flood-proofing has the tightest CI on lives saved" | "Aurora predicts 1,234 deaths in the next DANA" |
| "Pre-positioning ambulances in D03 ranks above retrofitting in D02 across 30 paired trials" | "Aurora forecasts 156 deaths if we don't retrofit" |

When a judge asks *"how do you know that's right?"*, the honest answer is: *"We don't know the absolute number is right. We know the relative ranking is, because it's a paired design. Validating the absolute numbers needs real Hazus-FL fragility — that's day 1 of any pilot conversation."*

## Gemma 4 angle

Aurora is built around Gemma 4's **Apache 2.0** license (independent of and compatible with Aurora's own AGPL-3.0; see [docs/license-decision.md](./docs/license-decision.md)).

**Tiered model routing** ([backend/app/config.py:38-39](./backend/app/config.py)):

| Model | Use case | Why |
|---|---|---|
| `gemma4:e2b` (~2 GB Q4) | Population / NPC decisions | Fast, runs alongside thousands of agents; latency budget is sub-200 ms per decision |
| `gemma4:e4b` (~3 GB Q4) | First-responder dispatch + post-run report synthesis | Higher reasoning quality; runs at the rate of city-level decisions, not agent-level |

**128K context window.** The whole-city scenario context (district shapefiles, infrastructure inventory, population archetypes, timeline) fits in a single prompt without retrieval. Aurora exploits this for the responder-dispatch agent, which sees the entire city state every decision.

**Native multimodal (planned).** Gemma 4 ships native vision and audio paths. Aurora's roadmap includes:
- *Vision*: judge-supplied damage photo → fragility-curve seed (auto-classify HAZUS damage state from a single image)
- *Audio*: 140-language eyewitness simulation (drop a voicemail in any language; population archetype layers it into the social-media stream)

These are scaffolded but not in v1. The current demo runs entirely on text.

**PLE (Per-Layer Embeddings).** Gemma 4's PLE architecture is what makes the e2b model fast enough to drive thousands of NPC decisions on a laptop. We name-drop PLE in the model card.

**Function calling.** Aurora's `agent_runtime.py` uses tool-use prompts to let agents query the simulation state (current shake intensity in their district, nearest open hospital, etc.). Note: Ollama's tool-call surface is incomplete in some 0.x versions — Aurora falls back to JSON-mode prompting when tool-call mode is unreliable.

## Quickstart

Aurora is **fully offline** — no cloud APIs, no Google Fonts CDN, no external dependencies once the models and containers are up. You can disconnect from Wi-Fi after Step 2 and the demo still works.

> **TL;DR**: `ollama pull gemma4:e2b && ollama pull gemma4:e4b && ./start.sh`
> See [docs/USAGE.md](./docs/USAGE.md) for the full command reference and troubleshooting, and [docs/EXTENDING.md](./docs/EXTENDING.md) for adding scenarios / interventions / agent classes.

**Step 1 — Pull the Gemma 4 models** (~5 GB total):

```bash
ollama pull gemma4:e2b
ollama pull gemma4:e4b
```

**Step 2 — Spin up infrastructure**:

<!-- D1: neo4j-volume-reset -->
> **Existing Neo4j volume?** If you ran an older version of this project, drop the Neo4j data volume before first boot. The database password changed (the legacy default no longer works), and Neo4j only reads the password on the first boot of a volume — a stale volume will refuse the new credentials:
> ```bash
> docker volume rm neo4j_data  # only if you have a stale volume from a prior run
> ```
<!-- /D1 -->

```bash
docker compose up -d        # Neo4j 5.18 + the backend container
```

**Step 3 — Run backend + frontend** (one command):

```bash
./start.sh           # boots Neo4j + Flask backend + vite dev (hot reload)
./start.sh prod      # for the recording-quality demo (vite preview)
./start.sh check     # health-check every endpoint
./start.sh stop      # kills everything we started
./start.sh help      # full reference
```

Open **http://localhost:3000/aurora?seed=demo** — the page pre-selects the LA M7.2 scenario, three high-impact interventions, and auto-runs the Monte Carlo after a 1-second beat.

If you prefer two terminals:

```bash
# Terminal 1
cd backend && python run.py             # Aurora Backend on :5001

# Terminal 2
cd frontend && npm install && npm run dev   # vite on :3000
```

> **First run slow?** Run [`python backend/scripts/prewarm_ollama.py`](./backend/scripts/prewarm_ollama.py) at T-30 min to load model weights and KV-cache before recording the demo. Cold-start adds 8–15 seconds to the first response.

See [docs/aurora-demo-script.md](./docs/aurora-demo-script.md) for the full recording recipe.

## Screenshots

<!-- TODO D3: replace with actual captured frames -->

<div align="center">

| **Demo seed lands** | **Live MC streaming** |
|:---:|:---:|
| ![After demo seed lands](./docs/screenshots/02-demo-cold.png) | ![Streaming progress with agent decision feed](./docs/screenshots/05-mid-streaming.png) |
| **Result reveal** | **Comparator + chart** |
| ![Lives saved + delta cards](./docs/screenshots/08-result-reveal.png) | ![Per-intervention bars + cumulative timeline](./docs/screenshots/10-comparator-chart.png) |

</div>

## Benchmarks

All numbers below are measured by the test suite — there is no marketing inflation. Reproduce with `cd backend && python -m pytest tests/test_aurora_perf.py -v -s`.

| Workload | Wall time | Test |
|---|---|---|
| 1 demo run, n_trials=1, n_pop=30, no LLM | **~45 ms** | `test_mc_trial_under_500ms_offline_synth` |
| 30 trials × 4 arms = 120 trials, n_pop=30, no LLM | **~2.5 s** | `test_mc_30trials_under_30s_offline_synth` |
| Average per-trial wall (synth) | **~21 ms/trial** | (derived from the 30-trial run) |
| Regression sentinel — 240 trials with 1 s threshold | **~5 s (XFAIL)** | `test_mc_perf_assertion_is_real` |

**Hardware**: M-series Mac, 16 GB RAM, no GPU acceleration. Synth path means no LLM call in the trial inner loop (the responder-dispatch decisions are deterministic). Real Gemma-4-backed runs are slower per trial (e2b adds ~150–250 ms per population decision) and are validated in the demo recording rather than CI.

**Bundle**: 234.72 kB gzip total (JS 204.12 + CSS 30.60 + HTML 0.66), well under the 320 kB ceiling. All four font families (Inter, JetBrains Mono, Noto Sans SC Latin subset, Space Grotesk) are bundled via `@fontsource` — zero CDN calls.

**Test count**:

| Suite | Tests |
|---|---|
| Backend (pytest) | 30 collected, 29 passing + 1 strict-xfail regression sentinel |
| Frontend tokens (node:test) | 6 |
| Frontend components (vitest) | 19 |
| Frontend legacy-string guard | 3 |
| **Total** | **58** |

The hostile-reviewer red-team for the demo-readiness plan, the v2 hardening, and the per-phase consistency checks are documented in `docs/aurora-demo-readiness-plan-v2.md`.

## How a run feels

A demo seed run has six visible phases, each of which is captured by a screenshot above:

1. **Cold load** (0–1 s). The page lands on `/aurora?seed=demo`. Skeleton cards shimmer where scenario tiles will appear.
2. **Scenario + interventions populate** (1–2 s). The LA M7.2 reference scenario is pre-selected. Three intervention chips light up — pre-position 4 ambulances, retrofit W1 wood-frame, evacuate 30 minutes earlier.
3. **Run kicks off** (2–3 s). The Run button transitions `idle → running` after a 1-second beat (long enough to give a recorded video a clean cut point). The streaming progress panel mounts.
4. **Streaming progress** (10–60 s, depends on Gemma 4 vs synth). One bar per arm, GSAP-tweened toward 100 % completion. The agent decision feed below scrolls a new entry every ~3 trials — synthetic but plausible: *"[Eyewitness · LA-D03 · t=14:32] lights flickering, no comms"*.
5. **Result reveal** (1.6 s animation). The streaming panel unmounts. A CountUp tween lands the lives-saved hero number. Three delta cards stagger in (8 % delay each), each tinted with the responsible element. The comparator-table bars sweep from 0 → mean width with a snappy ease.
6. **Cumulative chart** (lazy-drawn). The line chart for cumulative mean deaths over the 24-hour window draws via stroke-dashoffset reveal, baseline first, then each treatment arm staggered in. The end-point label dot fades in last, pinned to each arm.

Every animation respects `prefers-reduced-motion`: when the OS setting is on, the GSAP global timeline runs at 100× speed, which is visually equivalent to "instant". The CSS `@keyframes` are guarded the same way.

## What's next

- **Multimodal scenario seed** — drop a damage photo, get back a HAZUS-fragility-seeded scenario; drop a voicemail in any of Gemma 4's 140 supported languages, get a multilingual eyewitness population layer.
- **Geospatial layer** — h3 cells + lat/lon on every agent + every infrastructure node; render a real LA map underneath the simulation. The d3 layer is already in the bundle for the cumulative chart.
- **Policy-PDF export** — civil-defense agencies want a 2-page brief, not a Vue app. Generate a PDF with the comparator + chart + intervention cost-effectiveness ranking. The serialized `MonteCarloRun` already has every number this needs.
- **Real-time interventions during a live drill** — let the user toggle interventions mid-run and watch the trajectory diverge. Currently arms are independent; this would require a partial re-run path.
- **Validate-via-replay** — feed in actual after-action reports (Türkiye 2023, Maui 2023, LA fires 2025) and check whether Aurora reproduces the reported deaths / dollars-lost within the 90 % CI. This is the credibility gate for any pilot conversation with a city or insurer.
- **Power calculation before scaling N** — the current `n_trials=30` was chosen by intuition, not by a power calc. A small `pytest` test that bootstraps the CI width vs N and picks the smallest N that gets the lives-saved CI tight enough to be actionable would replace the magic number.
- **Function calling on Ollama, properly** — Aurora's `agent_runtime.py` falls back to JSON-mode prompting when Ollama's tool-call surface is unreliable. Once `vllm` or a newer Ollama nails this, switching back gets us cleaner traces.

## Project status

| Date | Milestone |
|---|---|
| 2026-04-27 | Aurora project bootstrapped; license decision (stay on AGPL-3.0, see [docs/license-decision.md](./docs/license-decision.md)) |
| 2026-04-28 | P0–P3: HAZUS scenario layer, multi-agent runtime, intervention DSL, Monte Carlo |
| 2026-04-29 | P-V0–P-V5: visual overhaul (tokens, motion, atomics, streaming, reveal, polish) |
| 2026-04-30 | D1: legacy-string purge + offline-fonts fix + `/` → `/aurora` redirect |
| 2026-04-30 | D2.5: pytest wall-time assertions backing every benchmark in this README |
| 2026-04-30 | D2: this document |
| ~2026-05-11 | D3: Chrome E2E + 12 screenshot pack + demo recording (target T-7 days) |
| 2026-05-18 | Hackathon submission deadline |

The full hostile-review trail (v1 plan → 6 red-team findings → v2 hardened plan → per-phase consistency checks) is in [`docs/aurora-demo-readiness-plan-v2.md`](./docs/aurora-demo-readiness-plan-v2.md). Every D-phase shipped through `IMPLEMENT → REVIEW → CONSISTENCY-CHECK → COMMIT`; loop-back fixes are recorded in the v2 plan's amendments section.

## Repository layout

```
.
├── backend/
│   ├── app/
│   │   ├── api/                 # Flask routes (scenario, simulation, graph, report)
│   │   └── aurora/              # The simulation core — read this first
│   │       ├── scenario_loader.py     # builds the LA M7.2 reference scenario
│   │       ├── intervention_dsl.py    # 3 intervention categories + PRESET_INTERVENTIONS
│   │       ├── monte_carlo.py         # paired-trial orchestrator + bootstrap CI
│   │       ├── agent_runtime.py       # per-hour trial stepper across all 4 agent classes
│   │       ├── hazus_fragility.py     # HAZUS-MH 2.1 fragility curves
│   │       ├── hazard_models.py       # shake intensity, aftershocks, cascade rules
│   │       ├── population_generator.py # 9 archetypes
│   │       ├── responder_generator.py  # EMS / fire / police pool
│   │       └── decision_cache.py       # LRU LLM-decision memoization
│   ├── tests/                   # 30 collected (29 pass + 1 strict-xfail sentinel)
│   └── scripts/prewarm_ollama.py
├── frontend/
│   ├── src/
│   │   ├── views/AuroraView.vue        # the single-page Aurora composer
│   │   ├── components/aurora/          # 11 atomic components (P-V2..P-V4)
│   │   └── design/                     # tokens.css, motion.js, fonts.css
│   └── tests/                   # vitest + node:test, 28 collected
├── docs/
│   ├── aurora-architecture.md          # file-level technical reference
│   ├── aurora-demo-readiness-plan-v2.md # hostile-reviewed plan
│   └── license-decision.md             # why AGPL-3.0 stays
└── docker-compose.yml           # Neo4j 5.18 + backend container
```

## License

This project is licensed under [AGPL-3.0](./LICENSE). See [docs/license-decision.md](./docs/license-decision.md) for the reasoning behind staying on AGPL.

**Gemma 4** is licensed under [Apache 2.0](https://blog.google/innovation-and-ai/technology/developers-tools/gemma-4/). Aurora calls Gemma 4 as a service via Ollama — no Gemma 4 source code is incorporated into this codebase. The two licenses are independent and compatible.

The HAZUS-MH 2.1 fragility curves and the Worden 2012 GMICE conversions are open-source / peer-reviewed; their inclusion in `backend/app/aurora/hazus_fragility.py` is a re-implementation, not a redistribution.

---

<div align="center">

*Aurora is a hackathon prototype, not a production tool. It is not a substitute for FEMA's official tooling, your city's emergency management plan, or peer-reviewed disaster modeling. It is a sandbox — a place where a city's planners can argue about which intervention is cheapest, before the disaster forces the argument.*

</div>
