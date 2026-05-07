# Aurora pipeline v3 — Gemma-as-co-driver + 3 cities × 6 hazards (HARDENED)

**Status:** GREENLIT 2026-05-06 — user picked 3 cities / 3 demo-runnable hazards / drop validation slide. Other 3 hazards ship as YAML manifest stubs. Code freeze 2026-05-15 EOD; 1.5d recording over weekend. Implementation via sonnet subagents starting now with J0a.
**Source DRAFT:** `aurora-pipeline-v3-DRAFT.md`.
**Date:** 2026-05-06.
**Branch:** `phase/aurora-sim-experience-v3` at `4758df0` (after H6 overlay fix).
**Supersedes:** `aurora-city-data-pipeline-v1.md` (v2 plan, city × hazard split only).

## What v1 (DRAFT) got wrong vs reality

The red-team raised 5 worst pitfalls. Two collapsed on contact with hardware reality (Mac mini check 2026-05-06):

### P1 (claimed BLOCKER) — "demo math is mathematically infeasible." **REFUTED.**

Reviewer's projection: 12s/call × 500 calls × 8 trials × 4 arms = 100+ minutes per MC.

Actual measurement on Mac mini M4 Pro / 64 GB / Ollama 0.21.2 (LAN access from dev box, not localhost):

| Mode | Wall per call | Eval tps | Schema-valid JSON |
|---|---|---|---|
| `gemma4:e4b` warm, schema-constrained, num_predict=100 | **0.87s median** | 60 | 6/6 |
| `gemma4:e2b` (existing fast_model in `agent_runtime.py:321`) | **~0.57s/call** | 96.9 median | 245/245 (cold cache evidence) |
| **Warm-cache MC** (LA M7.2, 4 trials × 2 arms, useLLM=true) | **0.16s server wall** | n/a | full cycle works |

The reviewer was working from theory; reality is mixed:

- **Warm path (the demo path) is ~0 cost.** Pre-existing 5,263-entry decision cache means the demo runs in 0.16-0.32s server wall.
- **Cold path is more expensive than the bare benchmark suggests.** Measured 2026-05-06 against a real Aurora MC: ~5.5s per cold call on Aurora's actual prompt template (vs 0.87s on the bare bench), driven by longer system prompt + larger num_predict. **150 cold calls fired in 820s = 0.18 calls/s.** Extrapolated cold trial cost: ~33 min for 360 calls. Confirms reviewer's instinct that pre-baked cache is mandatory; refutes the absolute number.

**Operational answer: the cache IS the architecture.** Pre-bake one canonical run per (city, hazard) at fixed seed, ship `decision_cache.jsonl` in the repo. The existing 5,263 entries cover all 6 current scenarios. We just extend with new entries for new hazards as they're added. Demo always plays from cache; cold paths only happen when contributors add a new case.

### P2 (claimed BLOCKER) — "Gemma 4 doesn't exist publicly." **REFUTED.**

Reviewer had no web access. Reality on Mac mini (verified 2026-05-06):

```
NAME                       ID              SIZE      MODIFIED
gemma4:e2b                 7fbdbf8f5e45    7.2 GB    10 days ago
gemma4:e4b                 c6eb396dbd59    9.6 GB    10 days ago
gemma4:26b                 5571076f3d70    17 GB     4 weeks ago
gemma4:31b                 6316f0629137    19 GB     4 weeks ago
```

`ollama show gemma4:e4b`:
- architecture: gemma4
- parameters: 8.0B
- context: 131,072
- quantization: Q4_K_M
- capabilities: completion · vision · audio · tools · thinking
- license: Apache 2.0

The hackathon submission story is fine. We use Gemma 4. We can ship the e4b binary identifier honestly.

## What v1 (DRAFT) got right (red-team's other 3 worst pitfalls)

### P3 — Schedule has zero buffer + recording prep unbudgeted. **STILL TRUE.**

13 calendar days, ~9 working days, 9.9d planned (Option α). Recording prep (voiceover, screen capture, README screenshots, edge-case bug-fix buffer) = 3.0d unscheduled. Honest deadline math:

- Last code commit: **2026-05-15 EOD (Friday)** — 9 working days from 2026-05-05.
- Recording: **May 16-17 weekend.**
- Submit Sunday evening 2026-05-17, 24h before the 2026-05-18 deadline as buffer.
- Working backwards: **6 working days for code.**

Option α (8.6d) is mathematically late. **Option γ (3 cities × 3 hazards = 7.4d) is the only honest fit with a 1d buffer.** v3 hardened plan goes with γ.

### P4 — "Gemma as co-driver" diagram is contradictory. **STILL TRUE; FIXED.**

Reviewer caught it: the DRAFT said Gemma drives `severity_bin → MMI → fragility curve → deaths` AND that Gemma can't override loss math. Both can't be true. The user picked **Reading 1.5 = co-driver** (per the architectural-fork question I asked them on 2026-05-05). v3 implements the reviewer's recommendation:

**Gemma is a CLAMPED MODULATOR.** HAZUS curves compute the central estimate; Gemma proposes a per-district per-hour multiplier in `[0.5, 1.5]` that widens the loss curve into a **90% confidence envelope**. Toggle "Gemma OFF" produces a single deterministic line; "Gemma ON" produces an envelope that varies with the LLM's per-district reasoning. Visible difference on screen: envelope width. Honest framing: "Gemma narrates the uncertainty, HAZUS computes the math."

### P5 — Tornado/wildfire/hurricane reuse seismic building classes. **STILL TRUE; FIXED.**

Aurora's `BuildingClass` is W1/C1L/C1M/PC1 — HAZUS-EQ. Hurricane needs 39 wind types; tornado needs NIST EF-scale Damage Indicators 1-28; wildfire needs roof + ember-vent component fragility. Running Holland 1980 wind through HAZUS-EQ fragility produces nonsense.

Fix: **add J0.6 (0.5d) wind-taxonomy bridge** that adds a `wind_class` field to `Building` with a 6-class abbreviation. For tornado/wildfire, accept that these are "stub fragility" cases and label them with a `Gemma-estimated` provenance badge (separate from `HAZUS-fragility`).

## The user's architectural choices (recorded 2026-05-05)

1. **Tokyo replaces Türkiye-Syria.** "One per continent: LA, Valencia, Tokyo." More recognizable, better Gemma training coverage.
2. **Gemma as co-driver, Reading 1.5.** "Co-driver will fully highlight Gemma 4's reasoning capabilities and driven to really simulate it, not just an algorithm." Implementation: clamped modulator that produces a CI envelope, not a loss override.
3. **More than just hurricane.** "Aurora should adapt to every disaster since the disasters will be driven by Gemma models." **6 hazards demoed, more shippable via YAML manifest.**

## Pipeline architecture (v3 hardened)

### Three layers, separable

```
exposure (city)  ×  hazard footprint  ×  vulnerability (fragility curves)  →  loss
                                ↑
                  Gemma 4 e4b co-driver clamped multiplier
```

Files:

```
data/cities/
  los_angeles_ca.json          # 8 districts, real OSM POIs, ACS demographics
  los_angeles_ca.boundary.geojson
  valencia_es.json             # 7 districts, Eurostat demographics
  valencia_es.boundary.geojson
  tokyo_jp.json                # 23 wards (full granularity per red-team #11)
  tokyo_jp.boundary.geojson    # NLI 国土数値情報

data/hazards/
  m72_puente_hills.json        # earthquake (LA — already in code)
  m69_san_andreas.json         # earthquake (LA alternate)
  cat3_landfall_la.json        # hurricane (LA, Holland 1980 wind field)
  ef3_socal.json               # tornado (LA, Gemma-driven)
  m9_cascadia.json             # tsunami (LA, synth depth grid)
  palisades_2025.json          # wildfire (LA, Gemma-driven)

  m55_iberia.json              # earthquake (Valencia low-seismicity)
  medicane_2030.json           # hurricane (Valencia)
  dana_2024.json               # flash flood (Valencia, already in code)
  ef2_iberia.json              # tornado (Valencia, rare)
  m8_n_africa.json             # tsunami (Valencia, synth)
  med_summer_2030.json         # wildfire (Valencia)

  tokyo_inland_m73.json        # earthquake (Tokyo, TMG 2022 official)
  hagibis_2019_typhoon.json    # hurricane (Tokyo, real event)
  hagibis_2019_flood.json      # flash flood (Tokyo, Tama River)
  ef2_saitama.json             # tornado (Tokyo, rare)
  tohoku_2011_tsunami.json     # tsunami (Tokyo, real event for validation)
  fuji_ashfall.json            # wildfire/ashfall (Tokyo, Cabinet Office 2020)

data/cases/
  la_m72_puente_hills.yaml
  la_cat3_hurricane.yaml
  la_dana_flood.yaml
  ... (6 hazards × 3 cities = 18 cases, with case_id pointing at city + hazard)

data/fragility/
  hazus_eq_v2.1.json           # earthquake (HAZUS-MH 2.1 lifted from manual)
  hazus_hurricane_v6.json      # hurricane (6-class abbreviated taxonomy)
  hazus_flood_v7.json          # flood (depth-damage)
  hazus_tsunami_v6.1.json      # tsunami
  ef_scale_tornado_v1.json     # tornado (NIST/NWS empirical, stub badge)
  arup_wildfire_v1.json        # wildfire (Arup/First Street 2023, stub badge)
```

Adding a 7th hazard: drop `hazards/<id>.json` + `cases/<city>_<id>.yaml`. **No code changes** for the common case. Optional `hazards/<id>/physics.py` override for hazards that need bespoke evolution.

### The Gemma co-driver loop (clamped modulator, not upstream override)

Per simulation hour:

1. Deterministic physics computes **central intensity** at each district from hazard parameters (Holland wind for hurricane, MMI decay for EQ, depth-attenuation for flood).
2. HAZUS fragility curve maps central intensity → damage state distribution → expected deaths/injuries/loss. **This is the central estimate.**
3. **Gemma proposes a multiplier `m ∈ [0.5, 1.5]` per district per hour**, given the hazard's history so far (constrained JSON: `{district_id, hour, multiplier (0.5-1.5), rationale (≤120 chars)}`).
4. The clamped multiplier widens the central estimate into a 90% CI: `[deaths × m_low, deaths × m_high]`.
5. Per-trial, sample within the envelope using the trial seed. Aggregate across trials = the visible CI.

**Toggle "Gemma OFF":** multiplier locked to 1.0; envelope collapses to the central line. Toggle "Gemma ON": envelope widens with Gemma's reasoning. Side-by-side comparison is visible in the demo. The pitch is honest: "HAZUS computes the math, Gemma narrates the uncertainty."

For hazards without canonical curves (tornado, wildfire), Gemma proposes the central damage class per (district, building category); a fixed translation table converts class → numeric. Provenance badge `Gemma-estimated (no canonical curve)` in **amber**, distinct from the HAZUS provenance in **green**. Honesty closes the credibility gap.

### Determinism guards (red-team's checklist + measured constraints)

1. **Constrained JSON schema** — Pydantic-validated server-side (already proven on Mac mini: 6/6 schema-valid in benchmark).
2. **Categorical/clamped not continuous** — multiplier ∈ [0.5, 1.5]; bin 0-5 for damage class.
3. **HAZUS-as-floor** — central estimate is canonical; Gemma only widens envelope.
4. **Cache by structured fields only** — drop narration from cache key (red-team #8 fix). Hash: `(hazard_id, hour, district_id, severity_bin_history_tuple, params_hash)`.
5. **Pre-bake canonical-run cache** — ship `decision_cache.jsonl` with one warm run per (city, hazard) at fixed seed. **Already exists** with 5,263 entries from prior work — just extend.
6. **Provenance per number** — every UI number badged: `HAZUS-fragility` / `Gemma-modulated` / `Gemma-estimated` / `cached`.
7. **Tripwire counter** — out-of-bound multipliers logged + counter visible.
8. **Validation slide** (J10) — Northridge 1994 only (red-team #9 fix: drop 3-event ambition; do one well).
9. **Baseline-vs-Gemma toggle** — every run can flip `gemma_co_driver: false`; CI envelope collapses to a line.

## Phase plan v3 hardened — Option γ (recommended)

3 cities × 3 hazards (EQ + Hurricane + Flood) = 9 demo cells. 6 hazards demonstrable via YAML manifests (tornado/tsunami/wildfire ship as **manifest-only stubs** that judges can read; the demo doesn't run them end-to-end).

| # | Phase | Effort | Risk | Depends |
|---|---|---|---|---|
| **J0a** | Schema + manifest loader. `City` + `HazardSpec` + `HazardManifest` + `Case` dataclasses. Migrate 6 existing scenarios into `data/cities/*.json` + `data/hazards/*.json` + `data/cases/*.yaml`. Golden-file regression test. | **2.0d** | high | nothing |
| **J0b** | Tokyo data import (replaces Türkiye). 23 wards from NLI 国土数値情報. Hand-keyed Tōhoku, Hagibis, Tokyo Inland EQ scenarios. Gemma e4b prompt-pack tuned for Japanese-context reasoning (model has training coverage). | **1.5d** | low | J0a |
| **J0.5** | `hazard_physics.py` dispatcher — `EarthquakePhysics` impl moves out of `agent_runtime.py`. **No new behavior; pure refactor.** Combined with J1 per red-team #7. | **0.5d** | high | J0a |
| **J0.6** | Wind-taxonomy bridge: `Building.wind_class` field, 6-class abbreviation, mapping table. | **0.5d** | low | J0.5 |
| **J1** | Gemma co-driver wiring: `gemma_co_driver.py` accepts hazard manifest + history + districts, calls Gemma 4 e4b with constrained JSON schema, validates, clamps multiplier to [0.5, 1.5], caches by structured fields only (red-team #8). | **1.0d** | high | J0.5 |
| **J2** | Earthquake refit: move EQ to use co-driver pattern. Northridge 1994 validation: Gemma multipliers within ±25% of real per-district damage data. | **0.5d** | med | J1 |
| **J3** | Hurricane: Holland 1980 wind generator + 6-class HAZUS Hurricane v6 fragility + 3 interventions (`roof_strap`, `shutters`, `safe_room`). Cat-3 LA + Hagibis Tokyo end-to-end. | **1.0d** | med | J0.6 |
| **J4** | Flood: synthetic depth-attenuation + HAZUS Flood v7 depth-damage. DANA 2024 Valencia + Hagibis Tokyo end-to-end. | **0.5d** | low | J3 |
| **J9** | UI: Act 1 city picker shows hazards as nested chips per city. Act 2 topbar shows `City / Hazard / Severity Palette`. | **0.4d** | low | J4 |
| **J11** | UI provenance badges + tripwire counter + baseline-vs-Gemma toggle. CI envelope visualization. | **0.5d** | low | J9 |
| **J-stubs** | Tornado/tsunami/wildfire manifest YAML stubs (NOT demo-runnable end-to-end). Showable in repo, README mentions "Aurora ships 6 hazards via the manifest pattern; 3 are demo-runnable." | **0.2d** | low | J0a |
| **J-record** | Recording prep: voiceover script, screen capture takes, edit, README screenshots, final pass. | **3.0d** | low | J11 |

**Total: 11.6d code + recording.**

Hmm — that's still over. Let me re-check.

**Code total (J0a..J11): 8.6d.** Recording 3.0d. Total 11.6d. Available 9 working days.

Even Option γ is 1-2d over the realistic ship-or-die deadline once recording is honestly accounted for. I have to cut more or accept a tighter recording weekend (1.5d not 3.0d).

### Honest scope cuts within Option γ

Cuts to reach **8.5d code + 0.5d buffer + 1.5d recording = 9d**:

- **Drop J0b Tokyo full import; ship Tokyo with 8 districts not 23 wards.** Saves 0.5d. Loses some "iconic recognizability" (red-team #11) but keeps the 3-city promise.
- **Drop J11 baseline-vs-Gemma toggle.** Saves 0.5d. Keeps provenance badges + tripwire counter. The CI envelope itself is the visible Gemma signal.
- **Tighten J-record to 1.5d.** Voiceover + 1 screen-capture take + minimal edit. README screenshots ship as a follow-up commit.

Revised total: **8.1d code + 1.5d recording + 0.4d buffer = 10.0d.** Still over by 1d.

### The honest ask back to the user

The original v3 ambition (3 cities × 6 hazards × Gemma co-driver) doesn't fit 9 working days even with red-team cuts. Three calls only the user can make:

**Call 1 — Cities.** Ship 3 cities (LA + Valencia + Tokyo at 8 districts) or 2 cities (LA + Valencia at full quality)? **Recommend 3** since user explicitly asked for "one per continent."

**Call 2 — Hazards demo-runnable.** 3 (EQ + Hurricane + Flood), 4 (+ Tsunami), or 5 (+ Tornado)? **Recommend 3** with the other 3 as YAML manifest stubs.

**Call 3 — Recording slack.** Hard 1.5d (voiceover + 1 take + minimal edit), 2.5d (multiple takes + B-roll + music), or push submission to 2026-05-18 itself with no buffer? **Recommend 1.5d.**

If the user accepts all three "recommend" choices: 3 cities × 3 hazards demo-runnable + 3 hazards manifest-only, 8.1d code + 1.5d recording + 0.4d buffer = **10.0d, 1d over.** Still needs one more cut. Likely candidates:
- Drop validation slide entirely (J2's Northridge validation): saves 0.3d.
- Skip wind-taxonomy bridge; ship hurricane + tornado on the same building stock with provenance badge "stub fragility": saves 0.5d.

## KPIs and quality gates

### North Star
**A user picks `Tokyo + Hagibis 2019` and watches Gemma 4 e4b widen the loss curve into a 90% CI envelope; the same case re-runs with Gemma OFF and the envelope collapses to a deterministic line. Both runs complete in <60s on the Mac mini. Provenance badges are visible on every number.**

### Per-phase exits

- **J0a**: 6 existing scenarios produce identical MC output (golden-file regression). 6 hazards × 3 cities discoverable from `data/cases/*.yaml`.
- **J0.5**: `hazard_physics.py` dispatcher exists; `EarthquakePhysics` produces bit-identical output to old code.
- **J1**: Gemma co-driver returns valid JSON for ≥95% of calls (proven 6/6 in benchmark). Cache hit rate ≥80% across 100-trial Monte Carlo on the same scenario (warm path). Cold-cache trial cost ≤90s (will measure when current cold MC completes).
- **J2**: Northridge 1994 replay: Gemma multipliers per LA district within ±25% of historical damage data.
- **J3**: Cat-3 LA case runs end-to-end; Hagibis Tokyo case runs end-to-end; Holland wind-field at 50/100/200km from track within 15% of NHC published Andrew anchors.
- **J9**: Act 1 city picker shows 3 cities × 3 hazards (9 chips) + 9 manifest-stub chips with "manifest-only" disabled state.
- **J11**: Every UI number has provenance badge. CI envelope visible in Act 5 charts. (Toggle dropped if cut.)

## Risks (top 3 after hardening)

1. **Cold-cache trial cost.** Will know in next 5 min from in-flight measurement. If >90s/trial, demo path requires aggressive cache pre-bake before recording. Mitigation: ship pre-baked cache for all 9 demo cells (already have 5,263 entries from prior work as starting point).
2. **Tokyo at 8 districts loses recognizability.** Mitigation: name the 8 districts as actual ward groupings ("Shibuya–Shinjuku core", "Bay area Minato–Chuo", etc.) so judges still see Tokyo names.
3. **Hurricane + flood validation against real events.** Hagibis 2019 has published damage estimates; Cat-3 LA is hypothetical. Validation slide can only honestly cover Northridge + Hagibis; Cat-3 LA gets a "speculative scenario" badge.

## Stop conditions

- Cold-cache trial cost >120s by 2026-05-07 EOD → halt Gemma co-driver path; ship deterministic-only with Gemma narrating archetype decisions only (current behavior).
- J0a not committed by 2026-05-08 EOD → halt entire pivot; ship existing 6-scenario demo with H-bundle UI polish only.
- Any J-phase exceeds 1.5× estimate → halt, re-scope before continuing.

## Open questions for greenlight

1. **Calls 1, 2, 3 above** — confirm "3 / 3 / 1.5d recording" choice or specify alternatives. ☐
2. **Drop validation slide vs drop wind-taxonomy bridge** as the final cut to fit budget? Recommend drop validation slide; the architecture diagram is the credibility move. ☐

## Ready-to-start step (after greenlight)

1. **Wait for cold-Türkiye MC to land** (in flight; expected within 5 min) — confirms cold-trial cost number.
2. **Write golden-file regression harness:** capture (deaths, injuries, economic_loss, deaths_by_district) tuples for all 6 existing scenarios at fixed seeds.
3. **J0a starts:** schema split, manifest loader, migrate 6 scenarios, replace Türkiye file with placeholder Tokyo. Run golden file. Must match.
4. **Subagents (sonnet):** J0.5+J1 (combined queue work) + J3 hurricane + J0b Tokyo can parallelize after J0a lands. User asked for sonnet specifically.
