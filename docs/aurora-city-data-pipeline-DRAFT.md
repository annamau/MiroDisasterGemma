# Aurora City × Hazard pipeline — DRAFT (pre-red-team)

**Status:** draft. Do NOT execute. Spawn red-team first.
**Date:** 2026-05-05.
**Working tree:** branch `phase/aurora-sim-experience-v3` at `4758df0` (after H6 overlay fix).
**User asks (verbatim, distilled):**
1. *"Lets not only load where the issues where but the real data from the agencies to check what they do have for protection right now."*
2. *"We are presetting flood, but we could add tornado, hurricane, tsunami or others to the cities. And test the city against the different factors."*
3. *"We should have the real data on import about population, doctors, policemen, etc for this."*
4. *"Lets learn the format used by cities and make an easy way to add new cases."*
5. *"Search the internet on how this is done and create a plan for this."*

## Headline finding (from research)

Real cities and emergency-management agencies don't model *city-and-hazard* as one thing. They keep three things separable:

```
exposure (city)  ×  hazard footprint  ×  vulnerability (fragility curves)  →  loss
```

This is the FEMA HAZUS architecture, the OpenQuake architecture, and the GFDRR Risk Data Library Standard (RDLS) architecture. Aurora today violates this — our 6 reference scenarios bake city + hazard together. The user is asking us to break them apart.

## What v1 of Aurora gets wrong

1. **`Scenario` mixes city facts (districts, buildings, population) with hazard facts (kind, magnitude, epicenter)**. To run "what if Valencia got an EF5 instead of a flood?" we'd duplicate the entire city dataclass. There are 6 hazards × 6 cities = 36 cells; we don't want 36 dataclasses.
2. **Building stock is generated synthetically, district-by-district**. There's no concept of "import the real building inventory FEMA HAZUS publishes for LA County."
3. **Essential facilities (hospitals, fire stations, shelters) are anchored to a few hand-picked points**. There's no script that says "give me all `amenity=hospital` POIs inside the LA city boundary from OSM."
4. **There is no hazard catalog**. Each scenario hardcodes its hazard params. There's no "Madrid + Cat-3 hurricane + the hurricane fragility pack" path.
5. **Fragility curves only exist for earthquake**. Hurricane / tornado / tsunami / flood / wildfire don't have curve packs in the codebase.

## What real systems do (concretely)

- **FEMA HAZUS-MH** keeps `Inventory` (buildings + essential facilities + lifelines) separate from `Hazard` (EQ / Hurricane / Flood / Tsunami modules), then runs them through `Fragility` (per-occupancy curves). `Inventory` is published per-county as SQL Server tables; the technical manuals carry the curve coefficients. ([HAZUS 7.0 Inventory Technical Manual June 2025](https://www.fema.gov/sites/default/files/documents/fema_rsl_hazus-7-invtm_06272025_1.pdf))
- **GFDRR Risk Data Library Standard (RDLS)** is an open JSON-Schema (riskdatalibrary.org/docs) with three top-level objects: `hazard`, `exposure`, `vulnerability`. World Bank publishes data packages keyed against it. This is the format we should adopt.
- **OpenQuake Engine** (Global Earthquake Model) uses fragility/vulnerability XML; it accepts a `JobINI` that names *which* exposure file + *which* hazard file + *which* vulnerability file. Same pattern.
- **OpenStreetMap + Overpass API** is the de-facto source for `amenity=hospital | fire_station | police | school | clinic` POIs (ODbL license; attribution required).
- **US Census ACS API** is the standard for tract-level demographics (population, age, vehicle access, English proficiency).
- **FEMA National Risk Index (NRI)** publishes per-county and per-tract risk + community resilience scores for all 18 hazards. Use it to suggest "plausible hazards for this city."
- **USGS Q-Fault** + **NOAA SLOSH** + **NCEI Storm Events** provide hazard catalogs (faults, surge MOMs, historical tornadoes/floods).
- The OSM tile-usage policy explicitly bans bulk + commercial tile fetching from `tile.openstreetmap.org` — we already ship CartoDB Positron tiles which are fine. Don't change that.

## The winning bet (one paragraph)

**Aurora becomes a "civic resilience harness."** A city is a *city* — population, hospitals, fire stations, police, schools, building stock, geography — imported once from OSM + Census + FEMA NRI. A hazard is a *hazard* — EQ M7.2, Cat-3 hurricane, EF5 tornado, M9 tsunami, 100-yr flash flood, wildfire — parameterized once and runnable against any city. The user picks {city, hazard, intervention combo}; Gemma 4 reasons over the archetypes; we get loss + comparison. Adding a new city is *one Python script run* (`scripts/import_city.py "Madrid, ES"`); adding a new hazard is *one JSON file* in `data/hazards/`; adding a new "case" (city × hazard combo) is *one YAML file* in `data/cases/`. The pitch is no longer "we built 6 demos." It's "we built a harness and the demos are 6 instances of it."

## Proposed data model (concrete, file paths)

### Cities (one JSON per city)

```
data/cities/
  los_angeles_ca.json
  los_angeles_ca.boundary.geojson
  los_angeles_ca.districts.geojson
  los_angeles_ca.facilities.geojson
  valencia_es.json
  valencia_es.boundary.geojson
  ...
```

```jsonc
// data/cities/los_angeles_ca.json
{
  "city_id": "los_angeles_ca",
  "label": "Los Angeles, CA",
  "country": "US",
  "iso2": "US",
  "centroid": { "lat": 34.052, "lon": -118.244 },
  "boundary_geojson": "los_angeles_ca.boundary.geojson",
  "districts_geojson": "los_angeles_ca.districts.geojson",
  "facilities_geojson": "los_angeles_ca.facilities.geojson",
  "demographics": {
    "population": 3849000,
    "median_age": 36.5,
    "households_no_vehicle_pct": 8.7,
    "limited_english_pct": 23.4,
    "source": "ACS 5-year 2024, tract aggregated"
  },
  "essential_facilities_summary": {
    "hospitals": 81,
    "hospital_beds_total": 16800,
    "fire_stations": 106,
    "police_stations": 21,
    "schools": 1320,
    "shelters": 47
  },
  "building_stock": {
    "method": "hazus_aggregate",
    "counts_by_occupancy": { "RES1": 612000, "RES3": 84000, "COM1": 31000, "EDU1": 1800, "GOV1": 410, "IND1": 9200 },
    "counts_by_structure":  { "W1": 480000, "W2": 120000, "RM1": 28000, "URM": 14500, "S1": 9000, "C1": 7000 }
  },
  "import_provenance": {
    "imported_at": "2026-05-05T15:00:00Z",
    "sources": [
      { "what": "POIs", "from": "OSM Overpass API", "license": "ODbL" },
      { "what": "demographics", "from": "Census ACS 5-year 2024", "license": "Public-domain" },
      { "what": "building stock", "from": "HAZUS 7.0 Inventory Technical Manual + NSI 2.0", "license": "Public-domain" },
      { "what": "boundary", "from": "OSM admin_level=8" }
    ]
  }
}
```

### Hazards (one JSON per hazard)

```
data/hazards/
  m72_puente_hills.json          # earthquake
  cat3_landfall_la.json          # hurricane (LA cat 3 hypothetical)
  ef5_joplin_2011.json           # tornado (real history)
  dana_2024_valencia.json        # flash flood
  m9_cascadia.json               # tsunami
  vesuvius_79ad.json             # volcanic / showcase
  ...
```

```jsonc
// data/hazards/cat3_landfall_la.json
{
  "hazard_id": "cat3_landfall_la",
  "kind": "hurricane",
  "label": "Cat-3 hurricane landfall, San Pedro Bay",
  "parameters": {
    "saffir_simpson": 3,
    "max_sustained_wind_mph": 125,
    "rmax_km": 32,
    "track_geojson": "tracks/cat3_landfall_la.geojson",
    "forward_speed_kmh": 18,
    "duration_hours": 36
  },
  "footprint": {
    "format": "wind_field_grid",
    "intensity_metric": "3-second gust mph",
    "grid_geotiff": null
  },
  "fragility_pack": "fragility/hazus_hurricane_v6.json",
  "ui_label_short": "Cat-3 hurricane",
  "severity_palette": "wind"
}
```

### Cases (one YAML per "demo" — combines a city and a hazard)

```yaml
# data/cases/la_m72_puente_hills.yaml
case_id: la_m72_puente_hills
city: los_angeles_ca
hazard: m72_puente_hills
ui:
  label: "Los Angeles · M7.2 Puente Hills"
  hero_blurb: "Largest blind-thrust scenario in southern California"
gemma:
  enable_post_sim_intervention: true
  persona_pack: persona_packs/california_urban.json
```

```yaml
# data/cases/la_cat3_hurricane.yaml — SAME city, DIFFERENT hazard
case_id: la_cat3_hurricane
city: los_angeles_ca
hazard: cat3_landfall_la
ui:
  label: "Los Angeles · Cat-3 hurricane"
  hero_blurb: "Hypothetical landfall in San Pedro Bay; ASCE 7-22 wind loads"
gemma:
  enable_post_sim_intervention: true
  persona_pack: persona_packs/california_urban.json
```

The user can now toggle between "LA quake" and "LA hurricane" by changing one dropdown; the city stays the same.

### Fragility packs (per hazard kind)

```
data/fragility/
  hazus_eq_v2.1.json          # earthquake (already implemented in code)
  hazus_hurricane_v6.json     # hurricane wind
  ef_scale_tornado_v1.json    # tornado (NIST/NOAA empirical)
  hazus_tsunami_v6.1.json     # tsunami inundation
  hazus_flood_v7.0.json       # flood depth-damage
  arup_wildfire_v1.json       # wildfire (no FEMA canonical, transparent caveat)
```

Each is a JSON encoding of the curve coefficients lifted from the public technical manuals. We DO NOT redistribute the FEMA SQL Server `.bak` baseline — we re-encode the published curves.

## The import pipeline (Python script + Flask route)

```
backend/scripts/import_city.py "Madrid, ES"
```

Steps the script runs:

1. **Geocode + boundary** — `geopy` Nominatim → admin-boundary polygon → write `data/cities/madrid_es.boundary.geojson`.
2. **POIs (Overpass API)** — bbox query for `amenity~"hospital|fire_station|police|school|clinic"`; respect rate limits, cache locally. Write `madrid_es.facilities.geojson`.
3. **Demographics** — for US: Census ACS 5-year `B01003,B01002,B25044,B16001` per tract; for non-US: try Eurostat NUTS for Europe, fall back to UN World Population Prospects.
4. **Building stock** — for US: pull HAZUS 7.0 baseline tables per county and roll up; for non-US: pull GFDRR exposure data packages keyed by RDLS schema, fall back to OSM `building=*` count × climate-zone defaults (with disclosure in `import_provenance`).
5. **NRI hazard suggestions** — query NRI per-tract risk; return a ranked list of plausible hazards for this city. The UI uses this to populate the "available hazards" picker for that city.
6. **Persist** — write all the files. UI auto-discovers the new city via `data/cities/*.json` glob.

The same script is callable from `/api/cities/import` (Flask, SSE-streamed because Overpass + ACS take 30-90s).

## Adding a new case end-to-end

To add "Tokyo + M9 Cascadia tsunami":

1. `python backend/scripts/import_city.py "Tokyo, JP"` (one command)
2. Create `data/hazards/m9_cascadia.json` with the hazard parameters
3. Create `data/cases/tokyo_m9_cascadia.yaml`
4. Reload UI — the case appears in Act 1 city picker

No code changes. The runtime resolves both halves and dispatches to `data/fragility/hazus_tsunami_v6.1.json`.

## How this maps to current Aurora code

- `backend/app/aurora/scenario.py` — split into `City` (the dataclass minus `hazard`) and `HazardSpec` (the dataclass minus city assets). `Scenario` becomes a thin wrapper: `Scenario = City × HazardSpec × FragilityPack`.
- `backend/app/aurora/scenario_loader.py` — REFERENCE_BUILDERS becomes a registry that reads `data/cases/*.yaml` and resolves the `city` + `hazard` references. Existing scenario_ids stay — they just point to YAML cases instead of Python builders.
- `backend/app/aurora/hazus_fragility.py` — generalized to load any fragility pack from JSON. The current Python-coded curves migrate into `data/fragility/hazus_eq_v2.1.json` (verbatim, with a unit test that the math doesn't change).
- `backend/app/aurora/agent_runtime.py` — sees no change. It already takes a `Scenario`; the wrapper just sources from the new schema.
- Frontend `Act1CityPick` — reads `/api/cases/list` (new endpoint) which groups cases by city. UI adds a "hazard picker" within each city card.

## Phase plan

| # | Phase | Effort | Risk | Depends |
|---|---|---|---|---|
| **I0** | Schema split: `City` + `HazardSpec` + `Scenario` wrapper. Migrate the 6 existing scenarios into `data/cities/*.json` + `data/hazards/*.json` + `data/cases/*.yaml` (no behavior change yet). | 0.6d | low | nothing |
| **I1** | Fragility pack loader: pull HAZUS EQ curves from Python into `data/fragility/hazus_eq_v2.1.json`; runtime reads pack from JSON. Test: same trial output as before. | 0.4d | low | I0 |
| **I2** | Import script `scripts/import_city.py`: Geocode + Overpass POIs + Census ACS + NRI suggestions. Write a city JSON. | 0.8d | med | I0 |
| **I3** | One new fragility pack: hurricane (HAZUS Hurricane v6 wind curves, lifted from public manual). One new case: `la_cat3_hurricane.yaml`. End-to-end: same LA city + Cat-3 hurricane returns plausible loss numbers. | 0.6d | med | I1 |
| **I4** | UI: Act 1 city picker shows hazards as nested chips per city. Act 2 topbar shows `City / Hazard` so the user knows which is which. | 0.4d | low | I3 |
| **I5** | Two more fragility packs: tornado (EF-scale empirical) + flood (HAZUS Flood v7 depth-damage). Two more cases: any city × tornado or × flood. | 0.6d | med | I3 |
| **I6** | One more fragility pack: tsunami (HAZUS Tsunami v6.1). The remaining (wildfire) ships as a stub with a "WIP" badge — explicitly transparent. | 0.4d | med | I5 |
| **I7** | `/api/cities/import` Flask route + SSE wiring. Runs the import script under the hood. UI lets the user paste a city name and watch the import. | 0.5d | med | I2 |

**Total: 4.3d.** Currently we're 4 commits past the H-bundle (light theme + map + pan/zoom). 4.3d is a real chunk; need to weigh against M3/M5'/M6' work.

## Recommended order with the rest of the v3 plan

The user's most recent feedback is more important than the recording polish. So:

- **Pause M3 / M5' / M6' / M7' / M8** until I-bundle ships — those phases are about live-sim animations and the Prevention Lab. They depend on `Scenario` shape; if we refactor that under them, we redo work.
- **Ship I0 + I1 first (1 day)** — that's the schema split with no behavior change. After that the runtime is decoupled and we can resume M3/M5'/M6' on the new shape.
- **Ship I2 + I3 next (1.4 days)** — import script + first new hazard pack. This is what the user actually asked for: real data + one extra hazard kind running against an existing city.
- **I4 (0.4d)** — minimal UI change so the new pattern is visible.
- **I5 + I6 + I7 (1.5d)** — additional hazards + the Flask import route. Could slot AFTER M3 if needed.

## KPIs and quality gates

### North Star
**A user can add a new city + hazard combo (`scripts/import_city.py "Madrid, ES"` + 1 hazard JSON + 1 case YAML) and see it appear in the UI with no Python code change.**

### Input metrics
| # | Metric | Today | Target | Phase |
|---|---|---|---|---|
| 1 | Cities defined as data, not Python | 0 | 6+ | I0 |
| 2 | Hazards defined as data | 0 | 6+ | I0 |
| 3 | Fragility packs as JSON | 0 | 4 (EQ, hurricane, tornado, flood) | I1+I3+I5 |
| 4 | Hazard kinds runnable against any city | 1 (eq only) | 4 | I3+I5+I6 |
| 5 | New-case onboarding time | "edit Python" | "1 YAML + 1 JSON" | I0-I7 |

### Per-phase exits

- **I0**: existing 6 scenarios still produce identical MC results vs `main` (golden-file regression test). New file layout in `data/`. 28 backend tests still green.
- **I1**: HAZUS EQ curves return bit-identical fragility probabilities as the Python implementation for ≥10 sample (MMI, building-class) pairs. New unit test asserts JSON loader matches the old code.
- **I2**: `scripts/import_city.py "Valencia, ES"` produces a `data/cities/valencia_es.json` with ≥3 hospitals, ≥10 schools, demographics block populated. Smoke test: run the script in CI against a fixture (mock Overpass).
- **I3**: `data/cases/la_cat3_hurricane.yaml` runs and produces lives_lost > 0. Hurricane fragility curves live in `data/fragility/hazus_hurricane_v6.json` with ≥6 building types covered (per HAZUS Hurricane Model technical manual sample).
- **I4**: Act 1 picker shows hazards-per-city; clicking a hazard updates `selectedScenarioId` to that case_id.
- **I5**: 2 more fragility packs + 2 more cases live. Both produce non-zero loss when run.
- **I6**: 4 of 5 hazard kinds covered (EQ + hurricane + tornado + flood). Tsunami curves loaded; wildfire shipped with WIP badge.
- **I7**: User can paste "Madrid, ES" into the UI and watch the import progress; on completion the new city is selectable.

## Risks

1. **Overpass API rate limits.** ~10k queries/day, ~1 GB/day. For 6 cities × 4 amenity classes = 24 queries — well within. For a live demo where a judge types a city name, ALSO fine. Cache to disk on first import.
2. **Census ACS keyless rate limit (~500 calls/IP/day).** Pre-bake city data; don't query at user demo time. We already ship 6 cities with import done.
3. **HAZUS hurricane wind curves coverage.** 39 specific building types in HAZUS Hurricane v6; we only encode ~6 mapped to W1/W2/RM/URM/S/C for parity with the EQ pack. Be transparent.
4. **Wildfire is the weakest leg.** No public canonical curve set. Ship a single "structure ignition probability vs flame length" curve from the Arup/First Street v1.0 (2023) methodology with an explicit WIP badge.
5. **OSM `building=*` count is noisy in non-US cities.** Where HAZUS / NSI 2.0 doesn't apply (non-US), we fall back to OSM building counts × climate-zone occupancy/structure defaults. Disclosed in `import_provenance.json`.
6. **Schema migration breaking existing live demo.** Mitigate by golden-file regression test in I0: identical MC output across the migration boundary.
7. **Deadline.** 4.3d is a real chunk. Ship I0+I1+I2+I3 (2.4d) for the demo; I4+I5+I6+I7 (1.9d) can ship to the repo after recording.

## Open questions for the user (must answer before I0 starts)

1. **Schema split first, then resume animations? Or interleave?** Recommend: schema split first (1d) then resume.
2. **Apache 2.0 + ODbL.** Aurora subset stays Apache 2.0 (already done in N0). OSM data is ODbL; redistributing OSM data files needs ODbL attribution + share-alike. We need to add an `ODBL-NOTICE.md` for the data files. ☐ Approve / ☐ Different.
3. **HAZUS curves re-encoded into JSON.** We re-encode the published technical-manual coefficients (public-domain US gov work). Don't redistribute the SQL Server `.bak`. ☐ Approve.
4. **Wildfire as WIP badge** vs cutting it. ☐ WIP / ☐ Cut.
5. **First non-EQ hazard to ship.** Plan recommends hurricane (HAZUS Hurricane v6 well-documented). Alternatives: flood (HAZUS Flood v7, also well-documented) or tornado (less canonical, but Joplin EF5 is in our existing data). ☐ Hurricane / ☐ Flood / ☐ Tornado.

## Ready-to-start step

I0 — half a day:

1. Create `backend/app/aurora/city.py` with `City` dataclass (population, demographics, essential_facilities_summary, building_stock, district list).
2. Create `backend/app/aurora/hazard.py` with `HazardSpec` dataclass (kind, parameters, footprint, fragility_pack ref).
3. Refactor `Scenario` → wrapper holding `(city, hazard, fragility_pack)`.
4. Migrate 6 existing scenario builders into `data/cities/*.json` + `data/hazards/*.json` + `data/cases/*.yaml`.
5. Golden-file regression test: identical MC trial output before/after.

That's the first commit. Pending user greenlight.
