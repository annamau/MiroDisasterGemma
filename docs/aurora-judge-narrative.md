# Aurora — the judge narrative

*How Aurora got built, what it does, how we measure it, and what's honest vs. aspirational.* This document is for a judge, a reviewer, a future maintainer, or anyone who wants the full picture in 15 minutes.

If you only have 90 seconds, skip to **[§7 The 90-second pitch](#7-the-90-second-pitch)**.

---

## 1. Where we began

In **late April 2026**, we forked a public repo called *MiroFish-Offline* — a multi-agent simulation of public opinion and social dynamics. Its original purpose was to drop in a press release or policy draft and watch hundreds of synthetic agents argue about it on a fake Twitter timeline. Useful for PR teams. Wrong tool for what we wanted to build.

What we *wanted* to build: a digital twin where a city's planners could ask **"what if we had done X?"** about a disaster they couldn't run as a real experiment. Earthquakes, floods, wildfires, hurricanes. The idea came from reading after-action reports — every one of them ends with the same paragraph: *"if we'd evacuated 30 minutes earlier, deaths would have dropped by Y."* But cities can't run that experiment on real residents. So they don't, and they don't learn.

So we kept the infrastructure of the fork (Vue 3 frontend, Flask backend, Neo4j storage, Ollama for local LLM serving) and pivoted everything on top: new domain model, new simulation core, new UI, new fatality framing, new documentation, new branding. The pivot itself is a useful credibility check — every screenshot, every backend banner, every API response, every line of the README was rewritten. There's a 51-line bash script (`frontend/tests/d1-mirofish-grep.test.sh`) whose only job is to fail CI if any user-visible "MiroFish" string ever leaks back in.

## 2. What we built — the simulation core

Aurora is a **multi-agent system** with four agent classes that interact across hours of simulated time, all running offline on a single laptop.

```
                    ┌────────────────────────────────────┐
                    │  Hazard agents                     │
                    │  shaking · aftershocks · cascade   │
                    └─────────────────┬──────────────────┘
                                      │
        ┌─────────────────┬───────────┼───────────┬──────────────────┐
        ▼                 ▼           ▼           ▼                  ▼
 ┌──────────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────┐
 │ Population   │ │ First-       │ │Decision  │ │Infrastructure│
 │ 9 archetypes │ │ responders   │ │ cache    │ │ hospitals,   │
 │ (Eyewitness, │ │ EMS, fire,   │ │ (LLM     │ │ shelters,    │
 │ Helper,      │ │ police,      │ │ memo)    │ │ utilities    │
 │ Authority,   │ │ finite       │ │          │ │              │
 │ Misinformer, │ │ resources    │ │          │ │              │
 │ ...)         │ │              │ │          │ │              │
 └──────────────┘ └──────────────┘ └──────────┘ └──────────────┘
        │                  │              │              │
        └──────────┬───────┴──────────────┴──────┬───────┘
                   ▼                             ▼
        ┌────────────────────────────────────────────┐
        │       Monte Carlo orchestrator              │
        │   ≥30 trials/arm · paired RNG seeding      │
        │   bootstrap CI on lives + dollars saved    │
        └────────────────────────────────────────────┘
```

The 4 classes:

1. **Hazard agents** read HAZUS-MH 2.1 fragility curves and Worden 2012 GMICE conversions to draw damage state per building, generate aftershock chains via Bath's law, and propagate cascading infrastructure failures (power → comms → hospitals).

2. **Population agents** are 9 evidence-grounded archetypes (Eyewitness, Coordinator, Amplifier, Authority, Misinformer, Conspiracist, Helper, Helpless, Critic). The mix-shares come from public post-disaster Twitter/Bluesky/Discord datasets (Türkiye 2023, Maui 2023, LA fires 2025). Each archetype has its own posting rate, follower distribution, panic threshold, geo-decay influence, and probability of amplifying misinfo vs. authority. Decisions are routed to **Gemma 4 e2b** (the smaller, ~2 GB Q4 model) for sub-200 ms latency at thousand-agent scale.

3. **First-responder agents** model EMS, fire, and police pools with finite resources and dispatch rules. Decisions are routed to **Gemma 4 e4b** (the larger, ~3 GB Q4 model) for higher-quality reasoning at the rate of city-level decisions, not agent-level.

4. **Infrastructure agents** carry hospital surge capacity, shelter occupancy, comms degradation. They constrain what responders and population can do — a hospital at full capacity rejects new patients; a comms blackout silences authority broadcasts.

All four classes step hour-by-hour for the full duration of the simulation (12 hours for a flood, 24 hours for an earthquake's acute window, 72 hours for a hurricane). Each trial returns a `TrialResult` with deaths, injuries, dollars lost, misinfo-to-authority ratio, and an hourly `deaths_timeline_mean[]` array.

**Code lives in**: `backend/app/aurora/{scenario_loader, hazard_models, hazus_fragility, population_generator, responder_generator, agent_runtime, decision_cache, intervention_dsl, monte_carlo}.py`. Total: ~2,500 LOC.

## 3. The intervention DSL — the policy levers

An intervention is a frozen Python dataclass that mutates a `Scenario` before each trial runs. Three categories shipped, plus communication:

| Category | Class | Real-world example |
|---|---|---|
| Pre-positioning resources | `ResourcePrepositionIntervention` | Pre-stage 4 ambulances in East LA (D03), boost paramedic units in district 03 by 4 |
| Timing changes | `EvacTimingIntervention` | Issue ES-Alert 4 hours earlier than the real Valencia DANA timeline |
| Infrastructure hardening | `SeismicRetrofitIntervention` | Retrofit 80 % of W1 wood-frame buildings in D03 (shifts HAZUS fragility curve to high-code) |
| Communication / counter-misinfo | `MisinfoPrebunkIntervention` | Pre-publish flood Q&A debunking dam-breach rumors |

Each intervention has an `apply(scenario) -> Scenario` method (returns a mutated copy) and a `runtime_overrides()` method (injects parameters into the agent runtime — e.g., raising the hospital capacity floor for a district). 10 presets ship today, mapped 1:1 to specific gaps cited in real after-action reports.

**Why DSL instead of free-form code**: judges and city planners can read a small dataclass. They cannot read 200 lines of imperative simulation logic. The DSL forces every intervention to be a single named, parameterized concept — comparable across scenarios, comparable across runs.

## 4. Monte Carlo — how we measure

This is the section that needs to be exactly right when a judge asks *"how do you know that?"*

### The paired-trial design

Aurora runs **N independent paired-trial Monte Carlo arms**:

1. The *baseline* arm runs the scenario with no intervention. N trials, each with seed `base_seed + i`.
2. Each *treatment* arm runs the scenario with one (or a combination) of interventions applied. N trials, each with seed `base_seed + i` — **the same seed as the baseline's i-th trial**.

The "same seed" part is load-bearing. The RNG seed deterministically drives:
- which population agents get assigned which archetypes
- which buildings get which damage-state draws under HAZUS
- the precise timing of aftershocks
- which agents the responder dispatcher picks first

So *trial #5 of the baseline* and *trial #5 of every treatment arm* see the same disaster. The only difference between them is the policy. That means **the per-trial delta** (`baseline_deaths_i - treatment_deaths_i`) is the *causal effect of the intervention on that disaster realization*.

Without the paired design, you'd be comparing *averages of different disasters*; the noise from RNG variation would swamp the signal from the intervention.

With the paired design, even noisy fragility models give *robust deltas* — because the noise cancels.

### Confidence intervals

We bootstrap 1,000 resamples of the per-trial paired deltas to get 90 % confidence intervals on:
- `lives_saved` (deaths avoided)
- `dollars_saved` (economic loss avoided)
- `misinfo_ratio_change` (shift in the misinfo-to-authority ratio in the social-media stream)

The reveal UI shows three decimals worth of CI bounds, plus a per-arm probability that lives_saved > 0.

### What we measure vs. what we don't

| ✅ Measured | ❌ Not measured |
|---|---|
| Per-trial paired delta of deaths/dollars between arms | Absolute prediction of how many people will die in a future event |
| Probability that intervention X saves more lives than intervention Y | Optimal city-wide policy across all hazards simultaneously |
| Sensitivity of the delta to N (we test N=30 and verify CI tightness) | Sensitivity to changing the fragility model wholesale |
| Wall-clock time per MC trial (gate: < 30 ms in synth mode) | Performance on a GPU |

### How honest the absolute numbers are

The fragility math is in band for earthquakes (LA M7.2 baseline produces ~6,600 deaths against the published USGS scenario range of 3,000–18,000). It is **not** in band for floods, tornadoes, or volcanic ash — Aurora currently reuses the seismic HAZUS curves as a stand-in. The Valencia DANA baseline overshoots real DANA fatalities by ~7×.

Two answers to "what do you do about that?":

- **Today**: we report relative-effect estimates ("a 4-h-earlier ES-Alert reduces deaths by ~29 % [27–31 % CI]"), not absolute deaths. The paired design means relative effects are robust even when the fragility model is approximate.
- **In progress**: [docs/aurora-accuracy-plan-v1.md](./aurora-accuracy-plan-v1.md) plans the swap to PAGER (earthquakes — Jaiswal & Wald 2009), Jonkman 2008 (floods), NWS EF damage indicators (tornadoes), and Wilson 2014 (volcanic ash). All four are published, peer-reviewed, closed-form, parameter-calibrated. Estimated 6 working days. Ships *before* the May 18 deadline if started by 2026-05-02.

This is the answer to **"how do you know that?"**: *We don't know the absolute number is right. We know the relative ranking is, because it's a paired design. The accuracy plan to fix the absolutes is sketched and dated.*

## 5. KPIs and quality gates — every phase had a number

We didn't ship a phase until it cleared falsifiable gates. The gates lived in plan documents *before* code was written, and the post-phase "consistency check" agent had no shared context — its only job was to find what the implementer missed.

### Plan-level KPIs

| KPI | Target | Where it lives |
|---|---|---|
| **North Star** (demo-day) | ≥ 60 % of judges recall the lives-saved number 30 min after the demo | external validation; can't measure until 2026-05-18 |
| **Leading proxy** | ≥ 60 % of n=3 internal pre-demo viewers recall the number 5 min after watching | by 2026-05-12 |
| Mirofish strings in user-visible paths | 0 | enforced by `frontend/tests/d1-mirofish-grep.test.sh` |
| Bundle size (gzip) | ≤ 320 kB | currently 234.83 kB |
| Cold-to-result wall time on `?seed=demo` (warm Ollama) | ≤ 90 s | measured at recording time |
| Number of working scenarios | ≥ 6 | currently 6 (5 real + 1 mythological) |
| Backend test count | ≥ 30 | currently 30 (29 pass + 1 strict-xfail) |
| Frontend test count | ≥ 25 | currently 28 |

### Per-phase exit gates (representative — full list in the plan docs)

**P-V1 — design system foundation**: every element color (`--el-fire`, `--el-water`, `--el-earth`, `--el-air`, `--el-aether`) clears WCAG 4.5:1 contrast on `--bg-1`. Enforced by `frontend/tests/tokens.test.js`. If you add a new element color, the test fails until it clears.

**P-V3 — streaming MC**: streaming endpoint produces ≥ 3 distinct progress snapshots before the result lands. Enforced by `backend/tests/test_streaming.py::test_streaming_run_produces_multiple_progress_snapshots`. Five trials with five 50-ms polls — at least three distinct hashes of `arms` JSON have to appear, otherwise the streaming pipeline silently flattened.

**D2.5 — wall-time benchmarks**: `test_mc_trial_under_500ms_offline_synth` (single demo run) and `test_mc_30trials_under_30s_offline_synth` (30 trials × 4 arms), plus a regression sentinel: `test_mc_perf_assertion_is_real` runs 240 trials with a 1 s threshold that's *deliberately impossible* to satisfy. It's marked `@pytest.mark.xfail(strict=True)`. If someone loosens the real perf threshold to make it trivially pass, this test XPASSes — and `strict=True` fails the suite.

That last gate is the philosophy in miniature: *gates that always pass are theater. Real gates fail sometimes — by design.*

### The consistency-check agent

After every phase shipped, a fresh subagent with no shared context received only the phase contract, the spec, and the diff, and was asked four questions:

1. Contract compliance (any edits outside owned files?)
2. Assumption integrity (did anything in the assumptions list change?)
3. Plan alignment (did the diff change something the plan doesn't mention?)
4. Cross-phase impact (did this diff break another phase's input contract?)

Three phases looped back at this step. D1 in particular triggered a review where the consistency agent found 4 unowned-file edits — those got either ratified into the contract (Simulation*View.vue) or rejected (anything in `backend/app/*` logger names). The audit trail is in `docs/aurora-demo-readiness-plan-v2.md` under "D1 contract amendments".

## 6. Architecture choices, with the reasoning

A few decisions a judge might ask about:

### Why Gemma 4 specifically?

Three reasons:
1. **Apache 2.0 license**. Compatible with Aurora's AGPL-3.0 (Aurora calls Gemma 4 as a service via Ollama; no Gemma 4 source code is incorporated). No license-conflict ambiguity.
2. **Tiered routing fits the agent class hierarchy**. Population NPCs need fast decisions (sub-200 ms — gemma4:e2b). Responder dispatch and post-run report synthesis need quality reasoning (gemma4:e4b). Both fit on a laptop.
3. **128K context window**. The whole-city scenario context (district shapefiles, infrastructure inventory, population archetypes, timeline) fits in a single prompt without retrieval. We exploit this for the responder-dispatch agent, which sees the entire city state every decision.

### Why offline?

Aurora's demo claim is "runs offline on a laptop, no cloud APIs". This is intentional:
- Civil-defense agencies often run in degraded-comms environments. A tool that needs cloud access during a crisis is the wrong tool.
- Hackathon judges should be able to run the demo without an account.
- The cost of getting Ollama+Gemma running once is small; the cost of cloud lock-in is structural.

We bundle 4 font families via `@fontsource` (no Google Fonts CDN), serve all assets from `dist/`, and the `?seed=demo` flow needs zero outbound network calls after the models are pulled.

### Why Monte Carlo, not deterministic single-run?

Two reasons:
1. **Real disasters have stochastic damage outcomes.** A 7.2 earthquake doesn't deterministically collapse a specific list of buildings; HAZUS gives you probability distributions. Single-run results would be ridiculous (one trial finds 5,000 deaths, the next finds 8,000 — no claim is defensible from N=1).
2. **Confidence intervals are how you communicate uncertainty.** A single number with no error bars is a lie of confidence. Aurora's reveal UI shows the CI explicitly on the comparator table — the bars have transparent overlays for the [lo, hi] band.

### Why a paired design specifically?

Already explained in §4. To restate: the only thing that should differ between the baseline arm and a treatment arm of trial #5 is the policy. Same disaster realization, different policy. Otherwise the noise from RNG variation across realizations would swamp the policy effect.

### Why these 9 archetypes?

The literature on disaster social-media response converges on roughly these categories. We checked Türkiye 2023 (Stanford Internet Observatory analysis), Maui 2023 (post-event ASU work), and LA fires 2025 (USC Annenberg). Mix-shares vary by event but the *categories* are remarkably stable. We didn't invent them.

### Why Vue 3, GSAP, no Three.js?

- **Vue 3** is what the upstream fork already used. Migrating to React would have cost 1–2 days for negligible benefit.
- **GSAP** because the visual moodboard called for snappy product-style animation, not toy WebGL effects. GSAP's free tier (3.13+) covers everything we use (TweenLite, ScrollTrigger, SplitText). We use `gsap.context()` for Vue lifecycle cleanup.
- **No Three.js, no glassmorphism, no AI gradients**. The moodboard called for "Linear's restraint × Our World in Data's editorial × FEMA EOC's credibility floor". Three.js would have made the page look like a tech demo, not a civil-defense tool.

## 7. The 90-second pitch

> *Cities can't experiment on their residents. So they don't experiment, and the next disaster kills the same way the last one did.*
>
> *Aurora is a digital twin where they can. Six scenarios — five real, one mythological — and you toggle interventions: pre-position 4 ambulances, evacuate 30 minutes earlier, retrofit a building class, pre-publish counter-misinformation. Click Run. Aurora simulates the disaster 30 times in parallel, with the same RNG seed across baseline and intervention arms, and shows you the per-intervention delta with 90 % confidence intervals.*
>
> *Powered by Gemma 4: e2b for the thousands of population agents, e4b for the responder dispatcher. 128 K context window holds the whole city. Apache 2.0 — fully offline.*
>
> *We're honest about what's not done. The fragility math is in band for earthquakes — peer-reviewed HAZUS-MH 2.1 — and we're using it as a damage proxy for floods until the Jonkman 2008 mortality functions land next week. The relative-effect estimates between interventions are robust today; the absolute death numbers will be in band by deadline.*
>
> *On the screen right now: Valencia DANA, October 29, 2024. Real disaster, real data, recent enough that the audience knows it. We're testing four interventions that the real after-action reports said were missing. Aurora ranks them. Top of the list: ES-Alert four hours earlier. Twenty-nine percent fewer deaths. Tight CI. That's not a guess. That's a paired Monte Carlo over 30 trials.*

## 8. The 30-second elevator version

> *Aurora is a city resilience digital twin. Pick a scenario — earthquake, flood, hurricane, volcanic eruption, or a mythological one. Toggle policy interventions. Aurora runs 30 paired Monte Carlo trials and shows you which intervention saves the most lives, with confidence intervals. Powered by Gemma 4 e2b/e4b, fully offline. The live demo runs on a laptop in airplane mode.*

## 9. The 5-second version (for a hallway)

> *Digital twin. Cities run "what if we'd done X?" experiments on disasters. Powered by Gemma 4. Offline.*

## 10. What's coming next, in order of importance

1. **[A1–A4: real fatality models](./aurora-accuracy-plan-v1.md).** PAGER, Jonkman, EF DI, Wilson ash. 6 working days.
2. **Multimodal scenario seed**. Drop a damage photo → HAZUS-fragility-seeded scenario; drop a voicemail in any of Gemma 4's 140 supported languages → multilingual eyewitness population layer. Roadmap.
3. **Geospatial layer**. h3 cells + lat/lon on every agent + every infrastructure node; render a real LA / Valencia map underneath the simulation. d3 layer is already in the bundle for the cumulative chart.
4. **Policy-PDF export**. Civil-defense agencies want a 2-page brief, not a Vue app. Generate a PDF with the comparator + chart + intervention cost-effectiveness ranking.
5. **Validate-via-replay**. Feed in actual after-action reports (Türkiye 2023, Maui 2023, LA fires 2025) and check whether Aurora reproduces the recorded deaths within the 90 % CI. This is the credibility gate for any pilot conversation with a city or insurer.

---

**Plan documents that show the work**:
- [aurora-visual-plan-v2.md](./aurora-visual-plan-v2.md) — the v1 visual plan + hostile-review + v2 hardening
- [aurora-demo-readiness-plan-v2.md](./aurora-demo-readiness-plan-v2.md) — D1..D3 demo prep with per-phase contracts and consistency checks
- [aurora-accuracy-plan-v1.md](./aurora-accuracy-plan-v1.md) — A1..A4 real fatality models, ready to execute
- [aurora-architecture.md](./aurora-architecture.md) — file-level technical reference with the intervention DSL grammar

**Sources cited in this document**:
- [USGS PAGER (Jaiswal & Wald 2009)](https://pubs.usgs.gov/of/2009/1136/) — earthquake fatality model
- [Jonkman 2008](https://link.springer.com/article/10.1007/s11069-008-9227-5) — flood mortality functions
- [NWS Enhanced Fujita Scale](https://www.spc.noaa.gov/efscale/ef-scale.html) — tornado damage indicators
- [Hazus-MH Technical Manual](https://www.fema.gov/flood-maps/products-tools/hazus) — fragility curves
- [Worden et al. 2012](https://pubs.geoscienceworld.org/ssa/bssa/article-abstract/102/1/204/331915) — GMICE
- [Stanford Internet Observatory — Türkiye 2023 misinfo](https://cyber.fsi.stanford.edu/io) — archetype mix-share calibration
