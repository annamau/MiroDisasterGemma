# Aurora Architecture

Aurora is a multi-agent disaster simulation engine. This document covers the agent class interactions, the intervention DSL grammar, and the file-level layout of the backend.

## Agent Class Interactions

```
  ┌──────────────────────────────────────────────────────────────┐
  │                    run_monte_carlo()                          │
  │               backend/app/aurora/monte_carlo.py              │
  │                                                              │
  │  for arm in [baseline, *interventions]:                      │
  │    mutated_scenario = arm.apply(scenario)                    │
  │    for trial_i in range(n_trials):                           │
  │      result = run_trial(mutated_scenario, seed=base+i)       │
  │    compute paired delta vs baseline (bootstrap 90% CI)       │
  └───────────────────┬──────────────────────────────────────────┘
                      │ run_trial()
                      │ backend/app/aurora/agent_runtime.py
                      │
          ┌───────────┼──────────────────────┐
          │           │                      │
          ▼           ▼                      ▼
  ┌──────────────┐ ┌───────────────────┐ ┌──────────────────────┐
  │ Hazard Agent │ │ Population Agents  │ │ First-Responder Agents│
  │              │ │                   │ │                       │
  │ Reads HAZUS  │ │ 9 archetypes:     │ │ Dispatch, triage,     │
  │ fragility    │ │  Eyewitness       │ │ route to hospital /   │
  │ curves for   │ │  Coordinator      │ │ shelter.              │
  │ each bldg    │ │  Amplifier        │ │                       │
  │ class; draws │ │  Authority        │ │ LLM: gemma4:e4b       │
  │ damage state │ │  Misinformer      │ │ (responder_generator) │
  │ per building │ │  Conspiracist     │ └──────────────────────┘
  │              │ │  Helper           │
  │ (hazard_     │ │  Helpless         │           │
  │  models.py,  │ │  Critic           │           │ capacity /
  │  hazus_      │ │                   │           │ routing feedback
  │  fragility.  │ │ LLM: gemma4:e2b   │           │
  │  py)         │ │ (population_      │           │
  └──────────────┘ │  generator.py)    │           ▼
          │        └───────────────────┘  ┌─────────────────────┐
          │                │              │ Infrastructure Agent  │
          │ deaths /       │ misinfo /    │                      │
          │ injuries /     │ authority    │ Road network load,   │
          │ econ loss      │ ratio        │ hospital capacity,   │
          └────────────────┴──────────────│ shelter fill rate,   │
                                          │ comms degradation    │
                                          └─────────────────────┘
                                                    │
                                                    ▼
                                          TrialResult (deaths,
                                          injuries, economic_loss_usd,
                                          misinfo_ratio, timeline[])
```

The `DecisionCache` (`decision_cache.py`) sits across all agents. Identical (archetype, situation-hash) pairs return cached LLM responses — cache-hit rate climbs across trials within an arm, keeping demo-mode wall time under 100 ms/trial.

## Intervention DSL Grammar

An intervention is a frozen dataclass. Its `apply(scenario) -> Scenario` method mutates a copy of the scenario before the trial runs. Its `runtime_overrides() -> dict` injects parameters into the agent runtime (e.g., raising the hospital capacity floor for a district).

Three categories are implemented:

**A. Resource pre-positioning**

```python
ResourcePrepositionIntervention(
    intervention_id="preposition_d03_4amb",
    label="Pre-stage 4 ambulances in East LA (D03)",
    target_district_id="LA-D03",
    added_paramedic_units=4,
    added_engine_units=0,
    added_shelter_capacity=0,
)
```

`apply()` inserts a new `FireStation` at the district centroid. `runtime_overrides()` raises `hospital_capacity_floor_by_district` by 5% per added paramedic unit (capped at +30%).

**B. Timing change**

```python
EvacTimingIntervention(
    intervention_id="evac_d03_30min_early",
    label="Evacuate D03 30 min earlier (55% compliance)",
    target_district_id="LA-D03",
    advance_hours=1,
    expected_compliance=0.55,
)
```

`apply()` reduces `occupants_day` for each building in the target district by `compliance × (1 - 0.10^(advance_hours/6))`, floored at 1 occupant.

**C. Infrastructure hardening**

```python
SeismicRetrofitIntervention(
    intervention_id="retrofit_d03_w1",
    label="Retrofit 80% of W1 wood-frame in D03",
    target_district_id="LA-D03",
    target_class="W1",       # HAZUS building class
    coverage_share=0.80,
)
```

`apply()` sets `year_built=2020` on the first 80% of matching buildings, causing the downstream HAZUS lookup to select the high-code fragility curve instead of pre-code.

## File-Level Layout

| File | Role |
|---|---|
| `app/aurora/scenario_loader.py` | Builds the LA Puente Hills M7.2 scenario (`build_la_puente_hills_m72`). Eight districts, 32 buildings each (256 total), hospitals, fire stations, shelters. Deterministic given seed. |
| `app/aurora/agent_runtime.py` | `run_trial()` — drives one 12-hour trial across all four agent classes, returns `TrialResult`. |
| `app/aurora/monte_carlo.py` | `run_monte_carlo()` — outer loop: baseline + each intervention arm. Computes paired delta CIs. `run_to_dict()` serializes for the API response. |
| `app/aurora/intervention_dsl.py` | Typed intervention dataclasses + `PRESET_INTERVENTIONS` registry. `get_intervention(id)` for lookup. |
| `app/aurora/hazard_models.py` | Shake intensity model, per-building damage state draw, economic loss calculation. |
| `app/aurora/hazus_fragility.py` | HAZUS-MH 2.1 fragility curves by building class and code level. Open-source, peer-reviewed. |
| `app/aurora/responder_generator.py` | Generates first-responder agents (dispatch, triage, routing). Uses `gemma4:e4b`. |
| `app/aurora/population_generator.py` | Generates population agents with archetype assignments. Uses `gemma4:e2b`. |
| `app/aurora/decision_cache.py` | LRU cache keyed on (archetype, situation-hash). Shared across trials within an arm. |
