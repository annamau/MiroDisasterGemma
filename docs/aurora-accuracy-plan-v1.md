# Aurora accuracy plan v1 — moving past the synth-fragility patch

**Status**: planning. Not yet executed. Pairs with [EXTENDING.md §4](./EXTENDING.md#4-adding-real-hazard-physics).

## What this plan replaces

Today, every non-earthquake Aurora scenario reuses the seismic HAZUS-MH 2.1 fragility curves as a damage proxy. The intervention RANKING is plausible (paired Monte Carlo, same RNG seed across arms — so deltas are robust) but the absolute death counts are wrong by ~7× on Valencia DANA. That's a "patch", not a model.

This plan moves Aurora to **per-hazard published fatality models**: PAGER for earthquakes (already partially used via HAZUS), Jonkman 2008 for floods, NWS EF damage indicators for tornadoes, and a Wilson 2014–style ash-load model for volcanic ash-fall. None of these require new ML — they're closed-form formulas with empirically calibrated parameters that we can implement and test in days, not weeks.

## Goal (one sentence, falsifiable)

> By 2026-05-15, Aurora's baseline synth-mode fatality estimate for each of the 5 real scenarios is within **2× of the historical recorded death count**, and the 90 % CI overlaps the recorded value, on a held-out validation set of 5 scenarios.

"Within 2×" is not "perfect"; PAGER itself reports an average factor of 5–10 across all earthquakes worldwide. The point is to bring Aurora from "off by 7× and growing" to "in the published-model band".

## Current state — what's broken vs. what's right

### What's right (don't touch)

- **Earthquake path** (LA M7.2, Türkiye-Syria) uses HAZUS-MH 2.1 fragility curves directly. These are peer-reviewed. The LA Puente Hills baseline produces ~6,600 deaths in synth mode — order-of-magnitude in line with the USGS scenario's 3,000–18,000 band.
- **Paired-trial Monte Carlo design** in `monte_carlo.run_monte_carlo`. Same `base_seed + i` across all arms means deltas are robust regardless of fragility-model accuracy.
- **The streaming + reveal UI**. Independent of the math.

### What's broken

| Scenario | Hazard kind | Current synth baseline | Real recorded | Off by |
|---|---|---|---|---|
| LA Puente Hills M7.2 | earthquake | ~6,600 | 3k–18k (USGS) | within band |
| Valencia DANA 2024 | flood | ~1,750 | ~230 | ~7.6× high |
| Pompeii AD 79 | wildfire | ~94 | 2k–16k (Sigurdsson) | very low |
| Joplin EF5 2011 | hurricane | ~1,500 | 158 | ~9.5× high |
| Türkiye-Syria 2023 | earthquake | ~22k | 59k | ~2.7× low |
| Atlantis | mythological | ~3,150 | N/A | n/a |

The earthquake path is in band. The 3 non-earthquake scenarios are all order-of-magnitude wrong because Aurora is using *seismic* HAZUS curves to predict damage from water, fire, and wind.

## Recommended approach — published models, no new ML

The literature converged 15+ years ago on closed-form, empirically calibrated fatality formulas per hazard kind. None require deep learning, regression on private data, or proprietary software.

### Earthquake — PAGER lognormal model (Jaiswal & Wald 2009)

**Model**:

```
ν(S) = Φ[ (1/β) · ln(S/θ) ]
```

- `S` = MMI shaking intensity at a given grid cell (5.0 to 10.0 in 0.5 increments)
- `Φ` = standard normal CDF
- `θ`, `β` = country-specific parameters fit by least-squares on 1973–2007 fatality records
- `ν(S)` = fatality rate per person exposed at that MMI

**Total fatalities** = Σ over MMI levels of `population_exposed(S) · ν(S)`.

**Country parameters** (from USGS Open-File Report 2009-1136, Jaiswal et al.):

| Country / Region | θ | β | Note |
|---|---|---|---|
| Italy | 13.23 | 0.18 | (used as proxy for Spain — PAGER groups Mediterranean countries) |
| Greece | 21.48 | 0.28 | |
| Romania | 17.50 | 0.24 | |
| Türkiye | (deferred — see Jaiswal 2009 fig. 17) | | listed in PAGER global regionalization |
| Indonesia / Philippines / Iran / Peru / Pakistan | listed in OF09-1136 | | |
| USA without California (incl. Mexico, Canada, Australia group) | "1 death per 23,400 at MMI IX" | | (curve-fit from grouped data) |

For Spain: PAGER groups Spain with Italy and France ("Western Mediterranean"). Use **θ = 13.23, β = 0.18** until we fit Spain-specific data.

**What we need to add to Aurora**:
- A new module `backend/app/aurora/pager_fatality.py` exposing `pager_fatality_rate(mmi: float, country: str) -> float`
- A new module `backend/app/aurora/population_grid.py` exposing `population_exposed_by_mmi(scenario, intensity_field) -> dict[float, int]`
- In `agent_runtime.run_trial`: when `hazard.kind == "earthquake"`, call PAGER to compute total fatalities; let the per-building HAZUS damage path drive *injuries* and *economic loss* but not deaths-as-headcount

Estimated effort: **1.5 days** (formula + 5 country-region table + integration + 6 unit tests).

### Flood — Jonkman 2008 mortality functions

**Model** (Jonkman, Vrijling, Vrouwenvelder 2008, *Natural Hazards*):

The flooded area is divided into 3 zones:

1. **Breaking-wave zone** — within ~1 km of a dike breach, water depth + velocity rise extremely fast. Mortality = 1.0 (everyone exposed dies).
2. **Rapidly rising-water zone** — depth × rise-rate exceeds a threshold. Mortality follows a lognormal CDF in depth `h`:
    ```
    F_D(h) = Φ[ (ln(h) - μ_D) / σ_D ]
    ```
    with calibrated `μ_D = 7.60`, `σ_D = 2.75` from the 1953 Netherlands flood.
3. **Remaining zone** — slowly rising flood. Mortality is much lower (~0.0001), driven by drowning of people who refuse to evacuate.

**Total fatalities** = Σ over cells of `population(cell) · mortality_zone(cell) · (1 - p_evacuated(cell))`.

**Per-cell variables** Aurora needs:
- `inundation_depth_m` (currently we don't compute this — we use a seismic MMI proxy)
- `velocity_m_per_s` (currently absent)
- `rise_rate_m_per_h` (currently absent)
- `warning_lead_time_h` (currently absent — would drive evacuation)

**What we need to add**:
- A new module `backend/app/aurora/jonkman_fatality.py` with the 3-zone mortality functions
- Replace the proxy MMI in `IntensityPoint` for floods with `(depth_m, velocity_m_per_s, rise_rate_m_per_h)` — or add 3 sibling fields, gated by `hazard.kind`
- Update Valencia's `_valencia_proxy_mmi_at` → `_valencia_inundation_at`, returning real DANA-anchored depth/velocity/rise-rate per district. Source: AEMET hydrological reports + the post-event Generalitat hydraulic model
- Evacuation lead time per intervention: `vlc_evac_es_alert_4h_early` should set `warning_lead_time_h = 4` for VLC-D01–D07

Estimated effort: **2 days** (3 lognormal functions + per-district hydrology lookup + integration + 8 unit tests).

### Tornado — NWS EF damage-indicator empirical

The tornado problem is structurally different: tornadoes carve a corridor (~100 m × 35 km for an EF5), not a radial field. Aurora's intensity field needs to become path-aligned.

**Model**: each EF rating has a published per-DI (Damage Indicator) lognormal "wind-speed-given-DoD" distribution (NWS / Texas Tech). Fatality rate per DI/DoD is empirical from NWS post-event surveys:

| EF Rating | Wind speed (3-s gust, mph) | Empirical fatality rate per affected resident |
|---|---|---|
| EF0 | 65–85 | ~0.0001 |
| EF1 | 86–110 | ~0.001 |
| EF2 | 111–135 | ~0.005 |
| EF3 | 136–165 | ~0.025 |
| EF4 | 166–200 | ~0.05 |
| EF5 | > 200 | ~0.10 |

(Calibration from Joplin 2011, Moore 2013, Mayfield 2021 NWS surveys.)

**What we need to add**:
- A `backend/app/aurora/ef_fatality.py` with the 6-row table + a per-cell EF-rating computation from a path corridor
- A path-corridor representation of the tornado track in `Hazard.intensity_field` (start, end, width)
- Joplin's `JOPLIN_DISTRICTS` should overlap the actual NWS-mapped track; our anchor data already does this approximately

Estimated effort: **1 day** (table + corridor geometry + integration + 4 unit tests).

### Volcanic ash-fall — Wilson et al. 2014

For Pompeii and any future volcano:

**Model** (Wilson, Cole, Stewart 2014, *Volcanic Hazards*):

| Ash load (kg/m²) | Building damage state | Per-resident fatality rate |
|---|---|---|
| < 100 | None | 0 |
| 100–300 | Light (roof partial) | ~0.001 |
| 300–700 | Moderate (roof collapse on weak structures) | ~0.05 |
| 700–1500 | Heavy (most roofs collapse) | ~0.30 |
| > 1500 | Pyroclastic-flow regime | 1.0 |

**What we need to add**:
- `backend/app/aurora/ash_fatality.py` with the 5-row table
- Pompeii's intensity field should carry `ash_load_kg_m2` (per Sigurdsson et al. 1985 isopach maps)

Estimated effort: **1 day** (table + isopach lookup + integration + 4 unit tests).

### Population grid — open-data, no proprietary integration

Right now, Aurora's "population per district" is a single integer per district (`d['pop']`). PAGER and Jonkman both need population disaggregated to a sub-district grid (the unit of MMI/depth variation).

**Recommended approach**: WorldPop 100 m gridded population (open Creative Commons license). Cache the relevant tile with each scenario JSON.

**What we need to add**:
- A `backend/app/aurora/population_grid.py` that loads a WorldPop GeoTIFF for the scenario bbox and exposes `population_at(lat, lon, h3_cell) -> int`
- For each scenario, bake a small (~100 KB) population grid JSON into `data/reference_scenarios/`
- Fallback: when WorldPop is unavailable, generate a uniform-density grid from `d['pop']` so the demo never regresses

Estimated effort: **1.5 days** (WorldPop fetcher, GeoTIFF reader using rasterio, baked-grid loader, fallback path, integration tests).

## Phasing

The work splits into 4 atomic phases that can ship independently. Each one is small enough to fit in one focused day; together they cover the four hazard kinds. Think of them as independent PRs, not a monolithic refactor.

| Phase | Goal | Effort | Validates against |
|---|---|---|---|
| **A1 — Population grid + PAGER for earthquakes** | Replace the per-district scalar pop with a WorldPop-fed grid; wire PAGER country params; verify LA M7.2 and Türkiye-Syria stay in band | 2 d | LA: 3k–18k; Türkiye-Syria: ~59k recorded |
| **A2 — Jonkman flood mortality** | Replace proxy MMI for `kind=flood` with depth/velocity/rise-rate; integrate Jonkman 3-zone formula; Valencia within 2× of 230 deaths | 2 d | Valencia: ~230 recorded |
| **A3 — EF damage indicator + path corridor** | Add corridor intensity field for `kind=hurricane`; wire EF table; Joplin within 2× of 158 deaths | 1 d | Joplin: 158 recorded |
| **A4 — Wilson ash-load** | Add `ash_load_kg_m2` field for `kind=wildfire` (used as ash-fall proxy); wire Wilson table; Pompeii in band of Sigurdsson 2k–16k | 1 d | Pompeii: 2k–16k bracketed |

**Total**: ~6 working days. Done by **2026-05-09** if started 2026-05-02. That gives 9 days slack to the May 18 deadline.

Run them strictly serial — A1 blocks A2/A3/A4 because the population grid is shared infrastructure.

## Quality gates per phase (numeric, falsifiable)

### A1 exit
- `pager_fatality_rate(mmi=8.0, country='IT')` returns ~0.001 (1 death per 1,000 — consistent with Italy data on page 29 of Jaiswal 2009).
- LA M7.2 baseline (n_trials=30, n_pop=80, no LLM) lands in **[3000, 18000]** deaths. CI overlaps **6500** (the cited HAZUS scenario midpoint).
- Türkiye-Syria 2023 baseline (n_trials=30) within **[20000, 90000]** deaths. CI overlaps **59000** (recorded).
- 30 backend tests + 5 new PAGER tests = 35 total, all green.
- No regression on the existing test_aurora.py earthquake suite.

### A2 exit
- `jonkman_zone(depth=3.0, velocity=2.0, rise_rate=1.5)` returns "rapidly rising"; mortality ≈ 0.18.
- Valencia DANA 2024 baseline (n_trials=30) within **[100, 500]** deaths. CI overlaps **230** (recorded).
- The intervention `vlc_evac_es_alert_4h_early` reduces mean deaths by 20–40 %. CI does not include zero.
- LA M7.2 still in band (no regression to A1).

### A3 exit
- `ef_fatality_rate(ef_rating=5)` returns ~0.10.
- Joplin EF5 2011 baseline (n_trials=30) within **[80, 320]** deaths. CI overlaps **158** (recorded).
- Path-corridor intensity field correctly assigns EF5 cells along the 22-mi track and EF0/no-damage cells off-axis.

### A4 exit
- `wilson_ash_fatality(load=400)` returns ~0.05.
- Pompeii AD 79 baseline (n_trials=30) within **[1500, 18000]** deaths. CI overlaps **8000** (Sigurdsson midpoint).
- Misuse test: `wilson_ash_fatality(load=2000)` returns 1.0 (pyroclastic-flow regime). 

### Universal gates (all phases)
- D1 mirofish-grep guard: still 3/3 OK.
- README + USAGE.md + EXTENDING.md cross-references updated to new modules.
- `./start.sh check` still passes (no new dependency makes the backend fail to boot).
- Bundle stays ≤ 320 kB gz (these are backend-only changes; should be 0 kB delta).
- The `prefers-reduced-motion` path still works (no UI changes in this plan).

### Stop conditions
- If A1's PAGER integration produces LA M7.2 deaths > 50k or < 1k, halt — something is wrong with population_exposed_by_mmi.
- If A2 reduces Valencia below 50 deaths, the Jonkman implementation is wrong (real DANA killed 230). Halt.
- If by **2026-05-08** A1 hasn't shipped, drop A4 (Wilson ash) and ship a "Pompeii is approximate" note in the README.

## What this plan deliberately does not do

- **No ML, no neural fragility models.** The literature has closed-form formulas. They're calibrated on real disasters. We use them.
- **No real-time hydraulic simulation.** The flood depths come from baked AEMET reconstructions, not a TUFLOW-style HEC-RAS solver. That's a roadmap item, not a hackathon item.
- **No proprietary data.** WorldPop is open. PAGER tables are open. Jonkman's parameters are published. Wilson's table is published.
- **No re-architecting `agent_runtime.run_trial`.** Each new fatality module plugs in via a `if hazard.kind == "X"` branch. The agent simulation, intervention DSL, MC orchestrator, streaming, and UI all stay the same.
- **No retroactive change to the demo numbers.** Until A1–A4 ship, the README's honest framing ("Aurora ranks interventions, doesn't predict deaths") stays. After A1–A4 ship, we can update to "deaths within 2× of recorded; intervention rankings still robust".

## What to do RIGHT NOW (T-17 days to deadline)

1. **Greenlight this plan.** If anything's off (scope, sequencing, gates), say so.
2. **Run [`plan-with-review`](./aurora-demo-readiness-plan-v2.md) skill on this doc**. Spawn a hostile reviewer to break it BEFORE we start the 6 days of work.
3. **Pick the start date.** I recommend 2026-05-02 (i.e., tomorrow). Strict serial A1 → A2 → A3 → A4. Each phase ends with a PR off `phase/aurora-accuracy-A{n}` against `main`.

If we ship A1+A2 only and skip A3+A4, the demo gets the LA + Valencia scenarios accuracy-correct. That's the **minimum viable upgrade** — and Valencia is the personal-angle scenario that lands hardest in the recording. Worth aiming for at minimum.

## Appendix — open data sources cited

| Data | Source | License | What we use |
|---|---|---|---|
| PAGER fatality params | USGS OF09-1136 (Jaiswal & Wald 2009) | Public domain (US gov) | θ, β per country |
| HAZUS-MH 2.1 fragility | FEMA Hazus Earthquake Technical Manual | Public domain | building-class damage curves |
| Jonkman flood mortality | Jonkman et al. 2008, *Natural Hazards* / *J. Flood Risk Mgmt* | Published; equations are public | 3-zone mortality formulas |
| Wilson ash-load fatality | Wilson, Cole, Stewart 2014, *Volcanic Hazards Risk Disasters* | Published; tables are public | 5-row mortality table |
| NWS EF Scale | NOAA / SPC | Public domain (US gov) | EF→wind, DI/DoD mapping |
| WorldPop 100m gridded population | WorldPop, Univ. of Southampton | CC-BY 4.0 | per-cell population |
| OpenStreetMap building footprints | OSM contributors | ODbL 1.0 | building density (optional A1 enhancement) |
| ShakeMap intensity grids | USGS | Public domain | MMI raster per scenario |
| AEMET DANA hydrology | AEMET (Spain) | CC-BY-NC 4.0 — fine for hackathon, may need re-licensing for commercial pilot | depth/velocity/rise-rate for Valencia |

Sources:
- [USGS PAGER FAQ](https://earthquake.usgs.gov/data/pager/faq.php)
- [USGS Open-File Report 2009-1136 (PAGER)](https://pubs.usgs.gov/of/2009/1136/)
- [Hazus Flood Model Technical Manual 7.0](https://www.fema.gov/sites/default/files/documents/fema_rsl_hazus-7-fltm_06272025_0.pdf)
- [Jonkman et al. 2008 — flood mortality](https://link.springer.com/article/10.1007/s11069-008-9227-5)
- [Jonkman 2008 — human instability](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1752-1688.2008.00217.x)
- [NWS Enhanced Fujita Scale + Damage Indicators](https://www.spc.noaa.gov/efscale/ef-scale.html)
- [WorldPop](https://www.worldpop.org/)
- [OpenStreetMap](https://www.openstreetmap.org/)
