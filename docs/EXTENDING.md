# Aurora — Extending guide

How to add new scenarios, new interventions, new agent classes, and new
hazard physics. Every section ends with a "what to test" checklist so you
know when the change is done.

If you're trying to *use* Aurora, read [USAGE.md](./USAGE.md) instead. For
*architecture* (file map + data flow), read
[aurora-architecture.md](./aurora-architecture.md).

## Quick links

| If you want to… | Jump to |
|---|---|
| Add a new disaster scenario (city / hazard / districts) | [§1 Adding a scenario](#1-adding-a-scenario) |
| Add a new policy intervention (resource, timing, retrofit, comms) | [§2 Adding an intervention](#2-adding-an-intervention) |
| Add a new agent archetype (population behavior) | [§3 Adding a population archetype](#3-adding-a-population-archetype) |
| Wire a new hazard kind (real flood physics, real volcano, etc.) | [§4 Adding hazard physics](#4-adding-real-hazard-physics) |
| Run a different LLM (vLLM, lmstudio, hosted) | [§5 Swapping the LLM](#5-swapping-the-llm) |
| Add a new visual component to the result reveal | [§6 Adding a UI component](#6-adding-a-ui-component) |
| Cite Aurora in academic work | [§7 Citing](#7-citing) |

---

## 1. Adding a scenario

A scenario answers: *"What hazard, in what city, with what people, infrastructure, and responders?"* Each one ships as a Python builder function returning a `Scenario` dataclass. There are 6 of them right now; the helpers make adding a 7th a ~80-line file edit.

### Recipe (90 minutes for a real scenario; ~30 minutes for a stylized one)

#### Step 1 — Pick your anchor data

You need:

- **Epicenter** lat/lon (where the worst damage starts)
- **6–8 districts** with: name, centroid lat/lon, population, median income, SVI (Social Vulnerability Index 0–1), primary language
- **Origin time** (ISO format with timezone)
- **Duration hours** (how long the simulation runs)
- A magnitude / intensity value (Mw for earthquakes, mm/h for floods, EF-rating for tornadoes, VEI for volcanoes)

Sources:
- Earthquakes → USGS event page + ShakeMap
- Floods → AEMET, Spain; NOAA, US; Copernicus EMS, EU
- Wildfires → CalFire, NIFC, EU EFFIS
- Tornadoes → NWS post-event surveys
- Volcanoes → Smithsonian Global Volcanism Program

Population + income + SVI:
- US → CDC SVI tract data, ACS 5-year
- ES → INE income deciles + dependency-ratio
- Anywhere else → Wikipedia first; tag the scenario `simulation_only=True` if you can't find primary sources

#### Step 2 — Write the builder in `backend/app/aurora/scenario_loader.py`

Pattern (copy from `build_valencia_dana_2024` or `build_pompeii_79`):

```python
# 1. Anchor data
MYCITY_LABEL = "MyCity Hazard YYYY-MM-DD — Reconstruction"
MYCITY_EPICENTER = (lat, lon)
MYCITY_ORIGIN_ISO = "YYYY-MM-DDTHH:MM:SS+TZ:00"

MYCITY_DISTRICTS: list[dict[str, Any]] = [
    {"id": "MYC-D01", "name": "...",  "lat": ..., "lon": ...,
     "pop": ..., "income": ..., "svi": ..., "lang": ".."},
    # ... 6 to 8 entries ...
]

# 2. Builder
def build_mycity_hazard_year(
    *, seed: int = 20250101, buildings_per_district: int = 30,
) -> Scenario:
    """One-line description."""
    return _build_generic_scenario(
        scenario_id="mycity-hazard-year",
        label=MYCITY_LABEL,
        city="MyCity, CC",
        hazard_kind="earthquake",   # or "flood" / "wildfire" / "hurricane"
        epicenter=MYCITY_EPICENTER,
        origin_iso=MYCITY_ORIGIN_ISO,
        duration_hours=24,
        magnitude=6.5,              # Mw / mm / EF / VEI as appropriate
        districts_anchor=MYCITY_DISTRICTS,
        intensity_at=lambda lat, lon: _generic_intensity_at(
            MYCITY_EPICENTER, lat, lon, peak=9.0, far=5.5,
            anchors=[(2.0, 9.0), (10.0, 8.0), (30.0, 7.0), (60.0, 6.0)],
        ),
        bbox=(lat_min, lat_max, lon_min, lon_max),
        seed=seed, buildings_per_district=buildings_per_district,
    )
```

The `_generic_intensity_at` waypoints are piecewise-linear-in-log10(distance). Pick 3–5 anchor points that match the published damage gradient.

#### Step 3 — Register it

`backend/app/api/scenario.py`:

```python
from ..aurora.scenario_loader import (
    build_la_puente_hills_m72,
    # ... existing ...
    build_mycity_hazard_year,    # ADD THIS
)

REFERENCE_BUILDERS = {
    "la-puente-hills-m72-ref":  build_la_puente_hills_m72,
    # ...
    "mycity-hazard-year":       build_mycity_hazard_year,    # ADD THIS
}
```

#### Step 4 — Add visuals

`frontend/src/views/AuroraView.vue`:

```javascript
const SCENARIO_VISUAL = {
  // ...
  'mycity-hazard-year': { element: 'fire',  icon: 'Flame' },  // ADD THIS
}
```

Element + icon mapping:

| Hazard kind | Element | Icon |
|---|---|---|
| earthquake | `earth` | `Mountains` |
| flood | `water` | `WaveTriangle` |
| wildfire | `fire` | `Flame` |
| hurricane / tornado | `air` | `Wind` |
| pop displacement / cyber / mythological | `aether` | `Users` or `WaveTriangle` |

#### Step 5 — Smoke test

```bash
cd backend && python -c "
from app.aurora import scenario_loader, monte_carlo
import time
scn = scenario_loader.build_mycity_hazard_year()
print(f'built: {scn.scenario_id}, {len(scn.districts)} districts, {len(scn.buildings)} buildings')
t0 = time.perf_counter()
run = monte_carlo.run_monte_carlo(
    scn, intervention_ids=[], n_trials=1, n_population_agents=20,
    duration_hours=6, llm_call=None,
)
print(f'1-trial MC: {(time.perf_counter()-t0)*1000:.1f}ms')
"
```

Expected: `built` line + `1-trial MC: ~10-30ms`. If it hangs, see the
"flood pitfall" below.

#### Step 6 — Add a pytest

`backend/tests/test_aurora.py`:

```python
def test_mycity_scenario_builds_deterministic():
    a = scenario_loader.build_mycity_hazard_year()
    b = scenario_loader.build_mycity_hazard_year()
    assert a.scenario_id == b.scenario_id == "mycity-hazard-year"
    assert len(a.buildings) == len(b.buildings)
    assert len(a.districts) >= 6
```

Run `python -m pytest tests/test_aurora.py -k mycity`.

### What to test

- [ ] Scenario builds in < 1 s
- [ ] 1-trial MC runs in < 100 ms (synth-only, n_pop=20)
- [ ] Card appears in `/aurora` UI with the correct element color and icon
- [ ] Clicking the card + clicking Run produces a valid result reveal (HeroNumber lands a real number, not NaN)
- [ ] `./start.sh check` still passes

### Pitfall — non-earthquake hazards and the aftershock loop

Aurora's `agent_runtime.run_trial` calls `aftershock_chain(magnitude, ...)` to seed aftershocks. **This is gated on `hazard.kind == "earthquake"`** because Bath's law diverges if you feed it a non-seismic magnitude (e.g., Valencia DANA's `magnitude=491.1` is rainfall in mm). If you set `kind="flood"` or `"wildfire"` or `"hurricane"`, the gate skips aftershocks — you're good. **If you set `kind="earthquake"` but pass a wild `magnitude` (e.g., the EF-rating of a tornado) the runtime will hang.** Stick to actual Mw values for `kind="earthquake"`.

### Pitfall — fragility curves

Every non-earthquake scenario currently reuses Aurora's seismic HAZUS curves as a damage proxy. The intervention RANKING is plausible; the absolute death count is not. Document this in your scenario's docstring. Fixing this is §4 below.

---

## 2. Adding an intervention

An intervention is a frozen `@dataclass` that mutates a `Scenario` before each trial. There are 5 categories and 10 presets right now.

### Recipe (15–30 minutes per intervention)

#### Step 1 — Pick a category

| Category | Class in `intervention_dsl.py` | Real-world examples |
|---|---|---|
| Resource pre-positioning | `ResourcePrepositionIntervention` | Add ambulances to a district, pre-stage fire engines, raise hospital surge capacity |
| Timing change | `EvacTimingIntervention` | Earlier evacuation order, mandatory vs. advisory shift, school dismissal time |
| Infrastructure hardening | `SeismicRetrofitIntervention` | Retrofit a building class, raise a levee, harden the power grid |
| Communication | `MisinfoPrebunkIntervention` | Pre-published Q&A, authority follower-boost, fact-check rapid response |
| (You can add a new category — see §2.5 below) | | |

#### Step 2 — Add the preset

`backend/app/aurora/intervention_dsl.py`, in the `PRESET_INTERVENTIONS` dict:

```python
"mycity_evac_2h_early": EvacTimingIntervention(
    intervention_id="mycity_evac_2h_early",
    label="MyCity: evacuate 2h earlier (60% compliance)",
    target_district_id="MYC-D03",
    advance_hours=2,
    expected_compliance=0.60,
),
```

Naming convention: `<scenario-prefix>_<short-name>`. The prefix prevents collisions when scenarios share intervention types (e.g., `evac_d03_30min_early` is LA's; `vlc_evac_es_alert_4h_early` is Valencia's).

#### Step 3 — Add visual mapping

`frontend/src/views/AuroraView.vue`:

```javascript
const INTERVENTION_VISUAL = {
  // ...
  mycity_evac_2h_early: { element: 'water', icon: 'ClockClockwise' },
}
```

Common icons: `ClockClockwise` (timing), `FirstAidKit` (medical), `Buildings` (retrofit), `ChatCircleDots` (comms), `Siren` (baseline / general), `Flame` (fire-break).

#### Step 4 — Test it

The intervention will appear automatically in the `/api/scenario/interventions` endpoint and the UI chip list. Click the chip + run the MC. Expected: a valid `lives_saved` number with a CI.

### What to test

- [ ] Intervention appears in `/api/scenario/interventions`
- [ ] Chip is clickable in the UI
- [ ] MC run with this intervention selected produces a non-NaN delta
- [ ] CI bounds make sense (lo ≤ point ≤ hi)
- [ ] If `lives_saved` is negative, ask: did I get the sign convention wrong? `target_district_id` mismatch? `advance_hours` accidentally negative?

### §2.5 Adding a brand-new intervention category

Adding a new category (e.g., `LandUseChangeIntervention` for zoning) is a deeper edit — you have to define how it mutates the `Scenario`:

1. Add a new frozen `@dataclass` in `intervention_dsl.py` inheriting from `Intervention`
2. Implement `apply(scenario) -> Scenario` (return a mutated copy — never mutate the input)
3. Implement `runtime_overrides() -> dict` if your intervention needs runtime parameters
4. Add at least 1 preset entry
5. Add a unit test in `backend/tests/test_aurora.py`

Read the existing 4 categories (lines 70–200 of `intervention_dsl.py`) for the pattern.

---

## 3. Adding a population archetype

Population agents are one of 9 archetypes (Eyewitness, Coordinator, Amplifier, Authority, Misinformer, Conspiracist, Helper, Helpless, Critic). Each has its own posting rate, follower distribution, panic threshold, and probability of amplifying misinformation vs. authority.

### Recipe (1–2 hours)

#### Step 1 — Define the archetype

`backend/app/aurora/archetypes.py`:

```python
ARCHETYPES["mediator"] = ArchetypeSpec(
    name="mediator",
    description="Calms others, translates between authority and panic",
    base_post_rate_per_hour=2.5,
    follower_distribution=("lognormal", mu=4.5, sigma=1.2),
    panic_threshold=0.7,            # higher = harder to panic
    misinfo_amplify_prob=0.05,      # very low — by design
    authority_amplify_prob=0.85,    # very high
    geo_decay_km=8.0,               # local first
    # ... see existing archetypes for full field list ...
)
```

#### Step 2 — Add a mix-share

`backend/app/aurora/population_generator.py` — find `ARCHETYPE_MIX` and add an entry that sums to 1.0:

```python
ARCHETYPE_MIX = {
    "eyewitness": 0.18,
    # ...
    "mediator": 0.05,    # ADD; reduce others proportionally
}
assert abs(sum(ARCHETYPE_MIX.values()) - 1.0) < 1e-6
```

#### Step 3 — Update the README narrative

Open the README, find the "9 archetypes" list, change to "10 archetypes", add the new one to the bullets.

#### Step 4 — Test

```bash
cd backend && python -m pytest tests/test_aurora.py -k archetype -v
```

If you wired it correctly, the population generator will spawn ~5% `mediator` agents and the simulation will run unchanged.

### What to test

- [ ] `ARCHETYPE_MIX` sums to 1.0 ± 1e-6
- [ ] Population generator produces ~expected share when running 1000 agents
- [ ] MC runs don't error when the new archetype is in the mix
- [ ] Misinfo / authority ratio shifts in the expected direction (mediators should pull the ratio toward authority)

---

## 4. Adding real hazard physics

Right now every non-earthquake scenario reuses the seismic HAZUS fragility curves as a damage proxy. To fix this:

### Real flood inundation-depth fragility

Pattern: replicate `backend/app/aurora/hazus_fragility.py` for HAZUS-FL.

1. Read FEMA Hazus FL Methodology Technical Manual (Chapter 5 — building damage)
2. Write `backend/app/aurora/hazus_flood_fragility.py` exposing
   `flood_damage_state(class, inundation_depth_ft, basement: bool) -> P[damage_state]`
3. In `agent_runtime.run_trial`, switch on `scenario.hazard.kind`:
   - `"earthquake"` → existing path
   - `"flood"` → call `hazus_flood_fragility` instead
4. Re-define what `IntensityPoint.mmi` means for floods — re-purpose it as
   inundation depth in feet, OR add a new `IntensityPoint.depth` field
5. Update Valencia's `_valencia_proxy_mmi_at` to return real inundation depths

Effort: 2-3 days for a defensible implementation. Worth doing before any
real civil-defense pilot conversation.

### Real volcanic ash-fall

Pattern: similar — replicate the fragility module for ash-load (kg/m²).
Reference: Spence et al. 2005, Wilson et al. 2014.

### Real tornado wind damage

Pattern: replace HAZUS with the EF-scale damage indicators. NWS publishes
DI tables (Damage Indicators by structure class).

### What to test

- [ ] New fragility module has unit tests against published anchor points
- [ ] Existing earthquake scenarios still pass `pytest tests/test_aurora.py`
- [ ] At least one non-earthquake scenario runs end-to-end and produces deaths
      that are within an order of magnitude of the historical record

---

## 5. Swapping the LLM

Aurora calls Ollama by default. Swap by editing `backend/app/services/llm_client.py`:

### vLLM (better function calling)

vLLM speaks the OpenAI-compatible API:

```bash
vllm serve google/gemma-4-2b-it --port 8000
```

Then in `.env`:

```
LLM_BASE_URL=http://localhost:8000/v1
LLM_API_KEY=EMPTY
```

vLLM has more reliable tool-call support than Ollama 0.x. Aurora's
`agent_runtime.py` falls back to JSON-mode prompting when tool-calls
fail; you can flip that off in `agent_runtime.AGENT_USE_TOOL_CALLS = True`
once you're on vLLM.

### Hosted Gemma 4 (e.g., Vertex AI)

```
LLM_BASE_URL=https://us-central1-aiplatform.googleapis.com/v1/projects/.../locations/us-central1/openai
LLM_API_KEY=<your token>
```

Note: this breaks the "fully offline" claim. Don't use it for the demo.

### LM Studio / llama.cpp / mlx-lm

All speak the OpenAI API at `http://localhost:1234/v1` or similar — same
pattern as vLLM.

### What to test

- [ ] `python -c "from app.services.llm_client import get_default_client; c = get_default_client(); print(c.chat([{'role':'user','content':'reply with single word ready'}]))"` returns "ready"
- [ ] `./start.sh check` still passes
- [ ] An LLM-backed MC produces deaths within 10% of the synth-backed MC for the same scenario + interventions + seed (sanity check that the LLM isn't introducing wild bias)

---

## 6. Adding a UI component

The Aurora visual system is built on 11 atomic components in
`frontend/src/components/aurora/`. Adding a 12th follows the P-V2 pattern.

### Recipe

1. Create `frontend/src/components/aurora/MyComponent.vue`
2. Use the design tokens — never hardcode colors. `var(--el-fire)`, `var(--bg-1)`, `var(--ink-0)`, etc.
3. Wrap any animation in `useGsap` (from `@/design/useGsap`) so cleanup is automatic
4. Guard every animation with `@media (prefers-reduced-motion: reduce)` for CSS, and `prefersReducedMotion()` for JS
5. Add a vitest mount test in `frontend/tests/components/my-component.test.js`
6. If the component appears in the demo path, screenshot it for the next D3 pack

### Reference component

`HeroNumber.vue` is the smallest end-to-end example: imports tokens, uses
GSAP for the CountUp tween, has a reduce-motion fallback. Read it before
writing your own.

### What to test

- [ ] Vitest mount test passes
- [ ] Reduce-motion fallback renders the final state instantly
- [ ] Bundle size doesn't grow > 10 kB gz (run `npm run build` and compare)
- [ ] Component renders inside `/aurora?seed=demo` without console errors

---

## 7. Citing

If Aurora helps your research or pilot work, please cite:

```bibtex
@software{aurora-2026,
  title  = {Aurora: City Resilience Digital Twin powered by Gemma 4},
  author = {Naves Maur{\'i}, Andr{\'e}s},
  year   = {2026},
  url    = {https://github.com/annamau/MiroDisasterGemma},
  note   = {Built for the Gemma 4 Good Hackathon, May 2026.}
}
```

The HAZUS-MH 2.1 fragility curves and the Worden 2012 GMICE conversions
implemented in `backend/app/aurora/hazus_fragility.py` are derived from
publicly available FEMA / USGS publications — cite those directly if you
use the fragility math:

- FEMA P-58 / HAZUS-MH 2.1 Technical Manual
- Worden, C.B., Gerstenberger, M.C., Rhoades, D.A., Wald, D.J., 2012.
  *Probabilistic relationships between ground-motion parameters and modified
  Mercalli intensity in California.* Bulletin of the Seismological Society
  of America, 102(1), pp.204–221.

---

## When to ask for help

| Situation | Where to look first |
|---|---|
| `./start.sh` errors | `/tmp/aurora-*.log` |
| Backend test failure | `backend/tests/test_aurora.py` for the scenario; `test_streaming.py` for the API; `test_aurora_perf.py` for wall-time |
| Frontend test failure | Vue + Vitest output; `frontend/tests/components/` |
| Bundle blew past 320 kB | `npm run build` reports per-asset gz; usually a font import without subset filtering |
| Demo went off the rails on stage | Read [aurora-demo-script.md](./aurora-demo-script.md) for the recovery playbook |

If Aurora becomes a thing you maintain seriously, the next docs to write
are: `CONTRIBUTING.md` (PR conventions), `SECURITY.md` (threat model for
city-data), `OPERATIONS.md` (production deployment beyond the laptop demo).
