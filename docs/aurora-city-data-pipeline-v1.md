# Aurora City × Hazard pipeline — HARDENED v1

**Status:** v2 of the plan. Absorbs 14 red-team findings (3 BLOCKERS, 7 MAJOR, 4 MINOR). Awaiting user greenlight.
**Source DRAFT:** `docs/aurora-city-data-pipeline-DRAFT.md`.
**Date:** 2026-05-05.
**Branch:** `phase/aurora-sim-experience-v3` at `4758df0`.

---

## What v1 (DRAFT) got wrong (corrected here)

### BLOCKERS (3)

**B1. `agent_runtime.py` is hardcoded to earthquake physics.**
v1 claimed "the runtime sees no change." Reality: `agent_runtime.py:354-364` runs aftershocks only when `hazard.kind == "earthquake"`; `agent_runtime.py:122-136` (`_mainshock_mmi_at`) hardcodes a Puente Hills MMI decay applied to every scenario. Hurricane / tornado / flood cannot share this code path.
**Fix in v2:** **add I0.5 (0.5d): extract a `hazard_physics.py` dispatcher** with two interfaces:
```python
compute_intensity(hazard: HazardSpec, lat: float, lon: float, hour: int) -> float
intensity_to_damage_input(intensity: float, hazard_kind: str) -> dict
```
Earthquake's existing math becomes one of N implementations. Without I0.5, every later phase is impossible.

**B2. Overpass at demo time has no fallback.**
v1 said `/api/cities/import` is SSE-streamed live. Overpass-turbo public endpoints 504/429 spike during business hours; one judge typing a city name during a demo with flaky wifi → 90s of nothing.
**Fix in v2:** **cache-first import.** Pre-bake `data/cities/_overpass_cache/<city>.json` for ~20 judge-likely cities (Madrid, Berlin, Tokyo, NYC, Mexico City, Cairo, Singapore, Mumbai, Istanbul, Lisbon, Paris, Seoul, Bangkok, São Paulo, Lagos, Sydney, Toronto, Cape Town, Athens, Jakarta). Live import falls through cache → 5s-timeout Overpass with two-mirror retry (overpass-api.de, kumi.systems) → graceful-degrade message ("Showing cached data; live import unavailable"). Cache-bake script runs in CI.

**B3. Hazard intensity grids for non-EQ are wishful thinking.**
For a HYPOTHETICAL Cat-3 over LA, no public source returns a wind-speed grid. ASCE 7-22 maps are statistical (return periods); SLOSH MOMs are surge-only; NRI is per-tract aggregate.
**Fix in v2:** ship a parametric wind-field generator using **Holland 1980** (~150 LOC, well-documented). For tornado, use NIST/NWS EF-scale damage-indicator grid sampling. For flood, use a synthetic depth-attenuation around an epicenter (matches what `scenario_loader.py` already does for floods). Each generator becomes part of `hazard_physics.py`. Add as I3a (0.5d).

### MAJOR (7)

**M1. I0 effort 0.6d → realistic 1.5-2d.**
Splitting `Scenario` requires (a) splitting dataclass, (b) extracting per-district anchors to JSON, (c) re-encoding 6 bespoke `intensity_at` lambdas, (d) round-tripping the random-stable `_synth_buildings_for_district` (rng-dependent), (e) wrapper, (f) loaders, (g) golden-file harness. **v2 budgets I0 = 1.5d.**

**M2. HAZUS curve redistribution needs per-source license audit.**
`hazus_fragility.py` already redistributes Worden 2012 GMICE coefficients (BSSA journal — not gov work). Numerical coefficients as fact-not-expression are likely safe under fair use, but blanket "lift verbatim" is overconfident. **v2 adds I1.0 step "license-audit each curve source"** — list every coefficient with its source (FEMA tech manual / journal article / NIST / NIBS) before re-encoding to JSON. ~1h work, not a budget hit.

**M3. "1 YAML to add a city" is half-true.**
`_synth_buildings_for_district` runs RNG every load. JSON encoding the OUTPUTS abandons seed determinism; encoding the INPUTS keeps the synth code (just relocated). **v2 chooses INPUTS:** the `cities/<id>.json` file persists per-district anchors (`pop`, `income_decile`, `svi`, `lang`, `n_buildings`); `_synth_buildings_for_district` stays as the loader, gets called against the JSON. Adding a new city means writing the anchors into JSON; the synth runs. Honest framing in plan.

**M4. Hurricane in 0.6d is 1.7d realistic.**
HAZUS Hurricane v6 has 39 building types (terrain × roof × deck × secondary). MVP needs 6 types + casualty model + duration mapping (hurricanes don't amortize like EQ). **v2 splits I3 into I3a (0.5d Holland wind generator), I3b (0.5d 6-type fragility pack), I3c (0.4d hurricane interventions: `roof_strap`, `shutters`, `safe_room`), I3d (0.3d runtime dispatch).** Total I3 = **1.7d**, not 0.6d.

**M5. Climate-zone defaults nowhere defined.**
v1 said "OSM `building=*` × climate-zone defaults." The defaults don't exist.
**Fix in v2:** for non-US cities use **EFFIS / GFDRR Global Exposure Database** as the source. If unavailable for a given country, use a single fallback table (Köppen-keyed, ~5 climate zones × 4 occupancy classes = 20 numbers) committed to `data/fragility/climate_zone_defaults.json`. Document in `import_provenance` so judges see when we're using the fallback.

**M6. Türkiye demographics — TÜİK API or nothing.**
ACS = US-only. Eurostat NUTS = EU-only.
**Fix in v2:** for Türkiye specifically, hand-key the existing scenario_loader population values into `cities/turkey_syria_eq.json`. The auto-import script fetches Eurostat for EU, ACS for US, and falls through to a `manual_demographics: true` flag for everything else. Judges see the flag in `import_provenance`. No automation lie.

**M7. Interventions tied to hazard kinds.**
Adding a new hazard means new intervention dataclasses (e.g. `roof_strap` for hurricane, `safe_room` for tornado).
**Fix in v2:** add **I3c (0.4d)**, **I5b (0.3d for tornado interventions)**, **I6b (0.3d for tsunami interventions)** as explicit phases. Plan now names this work instead of hiding it.

### MINOR (4)

**m1. ODbL share-alike + Apache-2.0 mixing.**
Aurora repo is Apache-2.0 (N0). OSM data files derived from ODbL must stay ODbL.
**Fix in v2:** OSM-derived files live in `data/cities/_osm_cache/` and `data/cities/_overpass_cache/` — those subdirectories carry their own `LICENSE-ODBL.md` and an `SPDX-License-Identifier: ODbL-1.0` header. Aurora codebase stays Apache-2.0. `LICENSE-MAP.md` updated.

**m2. Golden-file determinism is fragile.**
Stochastic ordering matters. Mitigate by sorting building IDs deterministically AT JSON LOAD time, not at synth time. ~3 lines of code, 1 line of test.

**m3. Live demo Overpass timeout.**
Already covered by B2 fix.

**m4. Wildfire WIP badge — keep that pattern, apply it to hurricane stub if I3 slips.**

---

## The winning bet (one paragraph, unchanged from DRAFT)

Aurora becomes a *civic resilience harness*. A city is data; a hazard is data; a fragility pack is data; a case is one YAML. Adding a new city is a script run; adding a new hazard is a JSON file; adding a new "what if Madrid got an EF5?" is a YAML file. The pitch shifts from "we built 6 demos" to "we built a harness, the demos are 6 instances of it, here's how to add the 7th in 5 minutes."

## Phase plan (v2 final, with all fixes)

| # | Phase | Effort | Risk | Depends |
|---|---|---|---|---|
| **I0** | Schema split: `City` + `HazardSpec` + `FragilityPack` + `Case` wrapper. JSON anchors per district. JSON loader. Golden-file regression test. | **1.5d** | high | nothing |
| **I0.5** | `hazard_physics.py` dispatcher. Earthquake math moves into `EarthquakePhysics` impl. `agent_runtime.py` calls dispatcher only. | **0.5d** | high | I0 |
| **I1** | Re-encode HAZUS EQ curves into `data/fragility/hazus_eq_v2.1.json` after license audit. Loader matches Python output bit-for-bit. | **0.5d** | low | I0.5 |
| **I2** | Import script `scripts/import_city.py` (cache-first, 2-mirror Overpass, ACS for US, Eurostat for EU, manual fallback for others). Pre-bake 20-city `_overpass_cache/`. | **1.0d** | med | I0 |
| **I3a** | Holland 1980 parametric wind-field generator. Test against historical Andrew/Katrina anchors. | **0.5d** | med | I0.5 |
| **I3b** | Hurricane fragility pack (6 building types, HAZUS Hurricane v6 manual values). | **0.5d** | low | I3a |
| **I3c** | Hurricane interventions: `roof_strap`, `shutters`, `safe_room`. Plus Stripe-able cost sources. | **0.4d** | low | I3b |
| **I3d** | `HurricanePhysics` impl + runtime dispatch. End-to-end: LA + Cat-3 hurricane returns plausible loss. | **0.3d** | med | I3c |
| **I4** | UI: Act 1 city picker shows hazards as nested chips per city. Act 2 topbar shows `City / Hazard`. Act 3 briefing shows current hazard's fragility-pack name + citation. | **0.4d** | low | I3d |
| **I5** | Tornado fragility pack (NIST/NWS EF-scale empirical) + tornado physics + tornado interventions (`safe_room`, `tie_downs`). | **0.7d** | med | I3d |
| **I6** | Flood fragility pack (HAZUS Flood v7 depth-damage) + flood physics (synthetic depth-attenuation, matches existing scenario_loader pattern) + flood interventions (`wet_floodproofing` already partial). | **0.5d** | low | I3d |
| **I7** | Tsunami fragility (HAZUS Tsunami v6.1) + tsunami interventions; wildfire ships as STUB with explicit WIP badge. | **0.5d** | med | I6 |
| **I8** | `/api/cities/import` Flask SSE route. UI lets user paste a city name; import progress streams. Cache-first; live import falls through 2 mirrors with graceful-degrade. | **0.5d** | med | I2 |

**Total: 7.3d.** v1 claimed 4.3d; the gap is the 3 blockers + 4 majors. Honest budget.

## Recommended order with rest of v3 plan

The user has now expressed two strong preferences:
- "real data from agencies" + "test the city against different factors" + "easy way to add new cases" — this whole I-bundle.
- The earlier ask: live-sim wow factor (M3, M5'-A, M5'-B), Prevention Lab (M6'), URL driver (M7'), 3-city E2E (M8) ≈ 5d.

**Total work in front of us: ~12.3d.** Hackathon submission 2026-05-18, today 2026-05-05 = 13 calendar days; ~9 working days.

So we cut. The honest options for the user to choose between:

**Option A — All-in on the harness (recommended):**
Ship I0 + I0.5 + I1 + I2 + I3a-d + I4 (5d). Skip I5/I6/I7/I8. Run M3 + M5'-A + M5'-B + M6' on top of the harness shape (4d). Demo path: LA + EQ vs LA + Cat-3 hurricane (2 hazards on the same city — directly answers user's "test the city against different factors"). 9d total.

**Option B — Keep more hazards, cut more polish:**
Ship I0 + I0.5 + I1 + I2 + I3a-d + I5 + I6 + I4 (7d). Skip I7/I8. Run M3 + M5'-B + M6' (3d, cut M5'-A streaming agent comms — the most expensive). Demo path: 4 hazards × 1 city. 10d. Tighter. Risks the live-sim wow factor.

**Option C — Cut the harness mostly, ship recording:**
Ship only I0 + I0.5 + I1 + I3a-d (3.2d). Single bonus hazard, no import script. M3 + M5'-A + M5'-B + M6' + M7' (5d). 8.2d. Demo looks more polished but the user's "easy way to add new cases" ask is unmet — they'd see two hazards but no way to add a new city.

**My recommendation: Option A.** It directly executes the user's most recent and most insistent ask. The recording can show LA EQ → switch to LA hurricane in real time. That's the wow factor without the streaming-agent-comms risk.

## KPIs and quality gates (v2 final)

### North Star
**A new contributor can add `data/cities/sf_ca.json` + `data/hazards/m69_sanandreas.json` + `data/cases/sf_m69.yaml` and see the new case in the UI city picker WITHOUT touching Python.** Validated by a CI test that synthesizes a fixture city + hazard and asserts the case appears.

### Per-phase exits

- **I0**: 6 existing scenarios produce identical MC output (golden-file). 28 backend tests still green. New `data/cities/*.json` × 6, `data/hazards/*.json` × 6, `data/cases/*.yaml` × 6.
- **I0.5**: `hazard_physics.py` exists with `EarthquakePhysics` impl. Old `_mainshock_mmi_at` and aftershock branch deleted from runtime. Earthquake scenarios still produce identical output.
- **I1**: HAZUS EQ JSON loader matches Python implementation for ≥10 sample (MMI, building-class) pairs.
- **I2**: `scripts/import_city.py "Madrid, ES"` produces a valid `cities/madrid_es.json` from cache fixtures (CI runs against the cache, never live Overpass).
- **I3a**: Holland 1980 wind generator returns plausible wind speeds at 50/100/200 km from track for historical Andrew test point (compare to NHC published).
- **I3b**: Hurricane fragility curves loaded; sample (W2, 120 mph 3-sec gust) → ≥0.4 prob of moderate damage.
- **I3c**: 3 new intervention presets in `intervention_dsl.py` with named cost sources.
- **I3d**: `data/cases/la_cat3_hurricane.yaml` runs end-to-end and produces deaths > 0, dollars > 0.
- **I4**: Act 1 picker shows hazards-per-city. Act 2 topbar shows both city and hazard.

### HEART (ships unchanged from v3 plan)

## Risks (top 3)

1. **I0 deterministic round-trip.** Synth code stays Python-side; JSON only carries inputs. If we accidentally change input ordering during the migration, golden file breaks. Mitigation: write the test FIRST, then the migration.
2. **`hazard_physics.py` dispatcher abstracted too early.** If we make the interface too generic, we'll fight it every time we add a new hazard. Mitigation: write the EarthquakePhysics impl from existing code; THEN write the second impl (HurricanePhysics) and let the abstraction emerge from the diff.
3. **Holland 1980 wind-field for arbitrary track.** Fine for symmetric idealized hurricanes; less good for asymmetric weakening near landfall. For a hackathon stub, plenty.

## Stop conditions

- I0 + I0.5 not committed by 2026-05-08 EOD → halt I-bundle, fall back to Option C (the harness ships only the schema split + EQ; no extra hazards).
- I3d hurricane case produces nonsense numbers (e.g. 0 deaths or 1M deaths) at 24h LA Cat-3 → halt I3, ship hurricane as WIP stub.
- Overpass cache build > 4h → ship 5 cities only (LA, NYC, Madrid, Tokyo, Lagos), document the rest as "not bundled, importable live."

## Open questions for the user

1. **Option A / B / C above.** Recommend A. ☐ Approve A / ☐ Pick B / ☐ Pick C / ☐ Different.
2. **First non-EQ hazard to ship: hurricane** (HAZUS Hurricane v6 well-documented, Holland wind generator clean) vs flood (HAZUS Flood v7 depth-damage simpler) vs tornado (Joplin already in our data). ☐ Hurricane / ☐ Flood / ☐ Tornado.
3. **Wildfire stub vs cut.** v2 keeps the WIP-badge pattern. ☐ WIP / ☐ Cut.
4. **20-city Overpass cache pre-bake.** Add `scripts/build_overpass_cache.py` that runs once and ships fixtures into `data/cities/_overpass_cache/`. CI runs against this. ☐ Approve / ☐ Smaller list (5 cities) / ☐ Different.

## Ready-to-start step

Once user greenlights Option A:

1. Write golden-file regression harness: load all 6 scenarios, run 3 trials each at fixed seeds, capture `(deaths, injuries, economic_loss, deaths_by_district)` tuples.
2. I0 starts: split `Scenario` → `City + HazardSpec + Case`, migrate 6 builders to JSON. Golden file must match.
3. Commit. I0.5 follows.
