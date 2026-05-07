# Aurora pipeline v3 — Gemma-as-co-driver + 3 cities × 6 hazards (DRAFT, pre-red-team)

**Status:** DRAFT. Do NOT execute. Spawn red-team first.
**Date:** 2026-05-05.
**Branch:** `phase/aurora-sim-experience-v3` at `4758df0` (after H6 overlay fix).
**Supersedes:** `docs/aurora-city-data-pipeline-v1.md` (v2 plan with 4 questions).

## What the user picked

1. **3 cities, one per continent: Los Angeles · Valencia · Tokyo.** Türkiye-Syria dropped (less recognizable; Tokyo has stronger Gemma training coverage and is more iconic).
2. **Gemma 4 = co-driver of hazard physics**, not just narrator. HAZUS curves do canonical math where they exist; Gemma proposes per-hour per-district intensity bins, narrates evolution, and fills in for novel hazards.
3. **6 hazards × 3 cities = 18 cases.** Earthquake / Hurricane / Flood / Tornado / Tsunami / Wildfire. Aurora "adapts to every disaster" because adding a new hazard = one YAML manifest with a Gemma prompt template.

## Why this is bigger than v2

v2 (city-data-pipeline-v1.md) split city × hazard at the data layer. The runtime stayed canonical-physics with Gemma narrating archetypes only.

v3 promotes Gemma into the **hazard physics loop**:
- Per simulation hour, per district, Gemma proposes `severity_bin (0-5)`, `dominant_effect`, and a 1-sentence narration grounded in the hazard's history so far.
- A deterministic table maps `severity_bin → intensity range`. HAZUS fragility curves consume the intensity. Casualties remain canonical math when curves exist.
- For hazards with no public canonical curve (wildfire, ice storm, industrial accidents), Gemma proposes loss class per building category; a fixed translation table converts class → numeric.

This is the architecture that makes "Aurora adapts to every disaster" defensible: adding a 7th hazard = one YAML manifest with prompt + parameter schema. No new physics code.

## The winning bet (one paragraph)

Aurora is **the first hackathon-grade civic simulator where an LLM co-drives hazard physics, not just agent behavior**. Three cities (LA / Valencia / Tokyo) — one per continent — host six hazards each. A user picks a city + hazard and watches HAZUS-canonical math + Gemma reasoning evolve the disaster minute-by-minute, narrate per-district state, and propose targeted interventions afterwards. Every number on screen is provenance-tagged: HAZUS-fragility / Gemma-proposed / JMA-historical / cached. A baseline-vs-Gemma toggle lets judges see the difference. A validation slide replays a real historical event (Tōhoku 2011, Northridge 1994, DANA 2024) against Gemma's proposals to ground credibility. The pitch is: *real cities, real hazards, real reasoning — not a movie poster.*

## The 6 hazards × 3 cities matrix

| | Earthquake | Hurricane | Flood | Tornado | Tsunami | Wildfire |
|---|---|---|---|---|---|---|
| **Los Angeles** | M7.2 Puente Hills (HAZUS) | Cat-3 landfall (Holland 1980) | LA River 100yr (synth) | EF3 SoCal (Gemma-driven) | M9 Cascadia analog (synth depth grid) | Palisades 2025-style (Gemma-driven) |
| **Valencia** | M5.5 (Iberia low-seismicity, HAZUS) | Medicane (Gemma-driven) | DANA 2024 (synth — already in code) | EF2 (Gemma-driven, rare) | M8 N. Africa (synth depth grid) | Mediterranean summer (Gemma-driven) |
| **Tokyo** | Tokyo Inland M7.3 (TMG 2022) | Typhoon Hagibis 2019 analog (HAZUS Hurricane) | Hagibis flooding (synth) | EF2 Saitama analog (Gemma-driven) | M9 Tōhoku 2011 analog (synth + JMA validation) | Mt Fuji ashfall scenario | 

**Color codes:** 11 cells use canonical HAZUS curves (white) ; 7 cells are Gemma-driven loss model (italic) — those judge-defenders need the validation slide most.

## Architecture — Gemma-as-co-driver

### The loop (per simulation hour)

```
runtime.step(t, scenario_state)
  ↓
hazard_physics.compute_intensity_grid(t, scenario_state)
  ├─ if HAZUS-fragility curve exists for (hazard, building_class):
  │     └─ Gemma proposes severity_bin per district (5 categories)
  │        Deterministic table maps bin → MMI/wind/depth range
  │        Sample intensity within range using cached seed
  │
  └─ if no canonical curve (wildfire, ice storm, etc.):
        └─ Gemma proposes damage_class per (district, building_category)
           Deterministic table maps class → expected loss fraction
  ↓
fragility.estimate_damage(intensity_grid, building_inventory)
  ↓
agent_runtime.run_archetype_decisions(damage_state, t)
  └─ Gemma proposes archetype-cell decisions (existing path, unchanged)
  ↓
casualties.compute(damage_state, occupancy, hospital_capacity)
```

### Determinism guards (the credibility checklist absorbed verbatim from research)

1. **Constrained JSON schema** — Pydantic-validated server-side; out-of-range outputs rejected and Gemma re-prompted with the violation. Anthropic tool-use docs pattern.
2. **Categorical not continuous** — Gemma picks bin 0-5; a deterministic table maps bin → numeric range. Hallucinations get *clamped*, not propagated.
3. **HAZUS-as-floor** — when curves exist, HAZUS computes losses; Gemma only modulates timing and narration. Gemma never overrides loss math for canonical hazards.
4. **Self-consistency** — sample N=3 proposals (cheap on a 4B model), take median; flag outliers >1.5 IQR.
5. **Cache by content hash** — Gemma calls keyed on `(hazard_id, hour, district_id, history_hash)` so a re-run replays from cache deterministically. Cache hit rate visible in UI.
6. **Provenance per number** — every UI number tagged: `HAZUS-fragility` / `Gemma-proposed` / `JMA-historical` / `cached`. Always visible in tooltip.
7. **Tripwire counter** — out-of-bound proposals counted and shown ("12 proposals corrected this run"). Counter-intuitively, this *increases* judge trust.
8. **Validation slide** — one historical event per city (Tōhoku 2011, Northridge 1994, DANA 2024) replayed: Gemma's per-hour proposals vs actual ShakeMap/SLOSH/JMA. Even one matching curve is sufficient credibility.
9. **Baseline-vs-Gemma toggle** — every run can flip "Gemma co-driver OFF" → pure deterministic HAZUS. Compare deaths-by-hour curves side by side.

### Hazard manifest schema (the contributor experience)

Adding a 7th hazard = one YAML file under `hazards/<id>/manifest.yaml`. No code change for the common case.

```yaml
# hazards/ice_storm/manifest.yaml
id: ice_storm
version: 1
display:
  label: "Ice storm"
  icon: "snowflake"
  severity_palette: ["#dbeafe","#93c5fd","#3b82f6","#1d4ed8","#1e3a8a"]
  unit: "ice_accretion_mm"
  unit_label: "Ice accretion (mm)"

parameters:
  - { id: peak_accretion_mm, type: float, min: 0, max: 80, default: 25 }
  - { id: duration_hours, type: int, min: 1, max: 96, default: 18 }
  - { id: temperature_c, type: float, min: -20, max: 2, default: -3 }

evolution:
  timestep_minutes: 60
  max_hours: 96
  gemma_co_driver: true
  cache_key_fields: [district_id, hour, peak_accretion_mm]

loss_model:
  primary: gemma_fallback   # OR "fragility:hazus_eq_v2.1" if curve exists
  damage_classes: [none, light, moderate, severe, complete]
  exposure_classes: [residential, commercial, lifeline_power, lifeline_road]

prompts:
  system: |
    You are a hazard co-driver for an ice storm in {city}. Propose plausible
    per-hour evolution given history. Output JSON only, schema:
    {hour:int, district_id:str, severity_bin:int 0-5,
     dominant_effect:str enum[accretion,wind,power_outage,thaw],
     narration:str <=120 chars}
    Prior hours: {history}. Current params: {params}.
  user: |
    Hour {hour}. Districts: {districts}. Propose state for each.

interventions:
  - { id: pre_salt, label: "Pre-salt evac routes", cost_usd: 500_000 }
  - { id: bury_feeders, label: "Bury power feeders", cost_usd: 12_000_000 }

validation:
  reference_event:
    name: "1998 NA Ice Storm (Quebec)"
    url: "https://en.wikipedia.org/wiki/January_1998_North_American_ice_storm"
```

A contributor drops `hazards/ice_storm/manifest.yaml` + (optional) `hazards/ice_storm/physics.py` if custom evolution needed. Aurora discovers it via directory walk on app boot.

## Phase plan v3

| # | Phase | Effort | Risk | Depends |
|---|---|---|---|---|
| **J0** | **Schema + manifest loader.** `City` + `HazardSpec` + `HazardManifest` + `Case` dataclasses. YAML manifest parser. Migrate 6 existing scenarios into 6 hazards × 3 cities. Golden-file regression test (existing 6 scenarios produce identical MC output). Replace Türkiye→Tokyo data. | **2.0d** | high | nothing |
| **J0.5** | `hazard_physics.py` dispatcher with `compute_intensity_grid(hazard, t, state)` interface. EarthquakePhysics impl moves out of agent_runtime. | **0.5d** | high | J0 |
| **J1** | **Gemma co-driver wiring.** New `gemma_co_driver.py` that takes hazard manifest + history + districts, calls Gemma 4 with constrained JSON schema, validates output, samples N=3 with median, caches by content hash. Tripwire counter. Provenance tagging in API responses. | **1.5d** | high | J0.5 |
| **J2** | **Earthquake refit.** Move EQ physics to use co-driver pattern. Validation: Northridge 1994 replay matches USGS ShakeMap within ±1 MMI. | **0.5d** | med | J1 |
| **J3** | **Holland 1980 wind generator** (parametric hurricane). HAZUS Hurricane v6 fragility pack (6 building types). 3 hurricane interventions (`roof_strap`, `shutters`, `safe_room`). Validation: Hagibis 2019 + Cat-3 LA. | **1.2d** | med | J2 |
| **J4** | **Flood physics**. Synthetic depth-attenuation around inundation centroid (matches existing scenario_loader pattern). HAZUS Flood v7 depth-damage curves. Validation: DANA 2024 Valencia. | **0.5d** | low | J2 |
| **J5** | **Tornado physics** (Gemma-driven loss + EF-scale category mapping). Joplin EF5 already in our data. | **0.5d** | med | J2 |
| **J6** | **Tsunami physics** (synthetic depth grid + HAZUS Tsunami v6.1). Validation: Tōhoku 2011 replay. | **0.6d** | med | J2 |
| **J7** | **Wildfire physics** (fully Gemma-driven loss). Single generic structure-ignition curve. WIP badge. | **0.4d** | low | J5 |
| **J8** | **Tokyo data import** (replaces Türkiye). NLI国土数値情報 ward boundaries + e-Stat demographics + JMA hazard catalog. Hand-keyed Tōhoku, Hagibis, Tokyo Inland EQ scenarios. | **0.7d** | low | J0 |
| **J9** | **City picker + hazard sub-picker UI.** Act 1 shows 3 cities; clicking a city expands to show 6 hazard chips. Act 2 topbar shows `City / Hazard / Severity Palette`. | **0.6d** | low | J0 |
| **J10** | **Validation slide** (the credibility move). One historical event per city. Side-by-side: Gemma proposals vs real data. Showable in Act 5. | **0.5d** | med | J6 |
| **J11** | **UI provenance + tripwire + baseline-vs-Gemma toggle.** Every number tagged. Tripwire counter visible. Toggle re-runs the same case with `gemma_co_driver: false`. | **0.5d** | low | J9 |
| **J12** | **Pre-bake Overpass cache** for ~10 judge-likely cities (LA, Valencia, Tokyo, NYC, Mexico City, London, Singapore, Mumbai, São Paulo, Sydney). Live import is cache-first. | **0.4d** | low | J0 |

**Total: 9.9d.** Hackathon submission 2026-05-18, today 2026-05-05 = 13 calendar days, ~9 working days. **This is over budget by 0.9d.**

## Honest scope cuts (must pick before greenlighting)

The pivot is much bigger than v2's 7.3d. Three options:

**Option α (recommended) — Ship the harness across all 3 cities × 4 hazards. 18-cell promise becomes ship-ready post-recording.**
- Phases: J0, J0.5, J1, J2, J3, J4, J8, J9, J11, J12 = **8.6d**.
- Demo path: 3 cities × 4 hazards (EQ + Hurricane + Flood + Tornado) = 12 cases. Drop tsunami + wildfire from the demo (ship as YAML stubs that judges can read but aren't integrated end-to-end).
- Validation slide: J10 deferred to "post-demo polish" — risky if judges ask, but "we have the manifest pattern, here's the ice-storm test case we added in 5 minutes" demonstrates the architecture without the slide.

**Option β — Drop a hazard, add validation. 3 cities × 5 hazards. 9.5d.**
- Phases: J0..J6, J8, J9, J10, J11 = **9.5d**, no buffer.
- Demo path: 3 × 5 (drop wildfire) = 15 cases.
- Risk: 0.5d buffer is zero buffer.

**Option γ — Smaller demo, max polish. 3 cities × 3 hazards (EQ + Hurricane + Flood). 7.4d.**
- Phases: J0, J0.5, J1, J2, J3, J4, J8, J9, J10, J11, J12 = **7.4d**, with 1.6d buffer.
- Demo path: 3 × 3 = 9 cases. Wow factor: validation slide + Gemma co-driver fully wired.
- Risk: feels less ambitious; user explicitly asked for breadth.

**My recommendation: Option α**, because the user said "more hazards than just hurricane" and "Aurora should adapt to every disaster." 4 hazards demonstrates the breadth claim. Validation slide can ship as a doc + screenshot if J10 slips.

## KPIs and quality gates

### North Star
**A user can pick `Tokyo + EF2 Tornado` and watch Gemma propose per-hour severity bins per ward, with HAZUS fragility curves NOT existing for tornado, and the system produces plausible loss numbers within 90 seconds — entirely from a YAML manifest, no Python physics code.**

This is the test that proves Aurora "adapts to every disaster."

### Per-phase exits

- **J0**: 6 existing scenarios produce identical MC output (golden-file regression). 18 cases discoverable from `data/cases/*.yaml`.
- **J0.5**: `hazard_physics.py` dispatcher exists. EarthquakePhysics impl produces bit-identical output to old code.
- **J1**: Gemma co-driver returns valid JSON for ≥99% of calls (1% retry). Out-of-bound rejections logged. Tripwire counter visible. Cache hit rate ≥60% across 100-trial Monte Carlo.
- **J2**: Northridge 1994 replay: Gemma-proposed MMI per district within ±1 of USGS ShakeMap historical.
- **J3**: Cat-3 LA case runs end-to-end; deaths > 0; Holland wind field at 50/100/200km from track matches NHC published Andrew anchors within 15%.
- **J8**: Tokyo case loaded; 23 wards rendered; Tōhoku 2011 hazard parameters present.
- **J9**: Act 1 picker shows 3 cities × N hazards as nested chips.
- **J10**: Validation slide: 3 historical events render side-by-side (Gemma vs real data) with ≥1 plausible match per city.
- **J11**: Every number on screen has a provenance badge. Baseline-vs-Gemma toggle re-runs same case with co-driver off.

## Risks (top 5)

1. **Gemma 4 e4b doesn't exist publicly** (research flagged this). If `gemma4:e4b` isn't on Ollama, fall back to `gemma3:4b`. Numerical claims become Gemma-3 baselines; reframe as "Gemma 3 4B" everywhere.
2. **Latency.** N=3 self-consistency × 24-hour sim × 5 districts × 4-hour cache = ~500 Gemma calls/run. At 40 tps on M4 Pro ≈ 12s/call short proposals → 6-8 min wall time per trial. Mitigation: aggressive caching, shorter histories, fewer self-consistency samples (N=1 for non-edge cases).
3. **Determinism vs randomness.** Gemma is non-deterministic even with cache (temperature). Mitigation: temperature=0, top_k=1, seed in prompt context, cache hit rate target 80%+.
4. **HAZUS curves licensing.** Same as v2: re-encode public coefficients to JSON; do NOT redistribute SQL Server `.bak`.
5. **Tokyo data complexity.** 23 wards is more granular than 8-district LA model. Mitigation: aggregate to 12 zones for sim parity with LA/Valencia.

## Stop conditions

- J0 + J0.5 not committed by 2026-05-08 EOD → halt entire pivot, fall back to v2 plan (city × hazard data split, no co-driver).
- J1 Gemma co-driver returns >5% invalid JSON after first day → halt J1, ship hazards as fully-deterministic with Gemma narrating only (revert to v2 archetype-only Gemma role).
- Any J-phase exceeds 1.5× estimate → halt, re-scope before continuing.

## Open questions (must answer before J0)

1. **Option α / β / γ** above. Recommend α. ☐
2. **Gemma 4 vs Gemma 3 4B fallback.** OK to verify model availability and reframe naming if needed. ☐
3. **Tokyo zone aggregation:** 12 zones to match LA/Valencia parity, or keep 23 wards for authenticity? Recommend 12. ☐
4. **Wildfire stub-only in α** — kept as YAML manifest only (not demo-runnable end-to-end). ☐
5. **Validation slide deferral** if J10 slips. ☐

## Ready-to-start step

After greenlight on Option α:

1. **Verify Gemma 4 availability:** `ollama list | grep gemma`. If `gemma4:e4b` exists, use it; else use `gemma3:4b`.
2. **Write golden-file regression harness:** capture (deaths, injuries, economic_loss, deaths_by_district) tuples for all 6 existing scenarios at fixed seeds.
3. **J0 starts:** schema split, manifest loader, migrate 6 scenarios + Türkiye→Tokyo. Run golden file. Must match.

End of v3 DRAFT.
