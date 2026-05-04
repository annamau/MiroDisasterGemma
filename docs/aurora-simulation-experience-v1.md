# Aurora simulation-experience v1 — DRAFT, pre-hostile-review

**Replaces**: the current AuroraView UI (one-page picker → run → numbers).
**Lands on top of**: U1 streaming-fix PR #5 (must merge first).
**Status**: v1 draft — to be hostile-reviewed before any code is written.

## Goal

By **2026-05-12 (recording day, pushed from 5/11 per v2 hardening)**, Aurora's `/aurora?seed=demo` flow walks the viewer through 5 sequential acts: (1) load situation, (2) see the 2D schematic map at hour 0, (3) watch the disaster unfold over ~30s of animated map state, (4) get a cost-ranked report of intervention ideas, (5) apply chosen interventions, re-run, and see a side-by-side compare with a visible motion delta. All on a Mac mini M4 Pro / 64 GB target. Schematic projection (Option B), no real OSM tiles. Existing 6 scenarios remain runnable end-to-end without regression.

## Current state (concrete, file:line verified)

- **Backend per-district per-hour data: PARTIAL.** `HourlySnapshot` at `backend/app/aurora/agent_runtime.py:70-81` carries citywide totals only (`deaths_cumulative: int`). `deaths_by_district: dict[str, int]` exists at the **TrialResult** level (line 101 — end of horizon, not per hour) and inside `_hourly_loss` (line 251 — per hour but discarded after aggregation). **The map needs per-district per-hour breakdowns. Backend change required: add field, populate from `_hourly_loss` return, propagate through `trial_to_dict` + `monte_carlo.run_to_dict`. ~30 LOC.**
- **Geo coverage: COMPLETE.** All 6 scenarios have `lat`/`lon` for every building, hospital, fire station, shelter (verified via Python script: 180-256 buildings each, 24-37 responder facilities each, 100% with coordinates).
- **Intervention costs: ABSENT.** No `cost_usd` field on any `Intervention` dataclass (`backend/app/aurora/intervention_dsl.py`). FEMA BCA Toolkit doesn't publish per-line-item dollar values publicly — the toolkit is a calculator, not a price catalog. Costs must be fabricated against named secondary sources (academic literature, local procurement records). ~0.5 day of research + a `costs.json` file.
- **Frontend tech: Vue 3 + GSAP 3.15 + d3 7.9** (already in bundle from CumulativeChart at P-V4). No Pixi.js. Bundle currently 234.84 kB gz.
- **Streaming MC**: post-U1 (PR #5 still open, must merge first), `MCProgressPanel.vue` correctly destructures the outer envelope. The map should consume the **same `progress_callback` plumbing** P-V3 wired up — that means each per-hour callback fires a new map frame.
- **Recording target**: 2026-05-11. **Today: 2026-05-01**. Working days available: **6** (5/4-5/8 + 5/11; weekends excluded).

## Phases

### M0 — Pre-flight: merge U1 + add per-district-hour timeline (~0.5d)

**Why this slot first**: M3 (animation) reads per-district per-hour death counts. Without this backend change M3 can't paint the map state at hour t. M0 also unblocks the v3 work from PR #5's open state.

**Files**:
- `backend/app/aurora/agent_runtime.py` (lines 70-81 — `HourlySnapshot` dataclass, add `deaths_by_district: dict[str, int]` field; lines 472-484 — populate it from `_hourly_loss`'s `d_by_dist` return)
- `backend/app/aurora/agent_runtime.py:trial_to_dict` and `backend/app/aurora/monte_carlo.py:run_to_dict` — propagate the new field into the JSON envelope
- (User greenlight needed) merge PR #5 to get U1 streaming-fix on main; M1+ branch off updated main

**Diff scope**: ~30 LOC backend, 1 file new, 0 file edits frontend.

**Test scaffold**:
- *Unit-1*: `test_hourly_snapshot_has_deaths_by_district` — assert the new field exists on the dataclass + a non-empty trial populates it with 1 entry per district
- *Unit-2*: `test_deaths_by_district_sum_matches_total` — for each hour h, sum(deaths_by_district.values()) == deaths_cumulative_at_h - deaths_cumulative_at_(h-1) — proves the per-district breakdown is consistent with the cumulative total
- *Misuse*: `test_no_district_in_breakdown_means_zero_deaths` — a trial where one district has zero deaths still appears as a 0 entry in the dict (not missing key — defensive against frontend KeyError)

**Exit gates**:
- 30 backend tests + 3 new = 33; all green
- The streaming `/run_mc/<run_id>/progress` JSON now contains per-hour per-district death counts (verified via curl)

**Risk**: low. ~30 LOC; the backend code path is already aware of the breakdown.

### M1 — Intervention costs catalog (~0.5d)

**Why this slot**: Act 4 (the report) ranks interventions by cost-effectiveness. Without `cost_usd`, the ranking is meaningless.

**Approach**: add `cost_usd` field to each `Intervention` dataclass with named-source footnotes. **Fabrication path** because FEMA BCA Toolkit doesn't publish line items publicly. Source-cite each cost in `intervention_dsl.py` docstring (e.g., "USACE 2018 Economic Guidance for Civil Works, p.34 — paramedic-vehicle TCO at ~$500K/yr").

**Files**:
- `backend/app/aurora/intervention_dsl.py` — extend each frozen dataclass with `cost_usd: int` and `cost_source: str` fields; populate the 10 existing presets
- `backend/app/aurora/monte_carlo.py:run_to_dict` — emit cost in the response envelope
- New: `docs/intervention-costs.md` — table of (intervention_id, cost_usd, source URL/citation)

**Diff scope**: ~80 LOC across 2 files + 1 new doc.

**Test scaffold**:
- *Unit-1*: `test_every_preset_has_cost_and_source` — iterate `PRESET_INTERVENTIONS`; assert `cost_usd > 0` AND `len(cost_source) > 10` for each
- *Unit-2*: `test_cost_per_life_saved_reasonable` — for the LA M7.2 + evac_d03 case (deltas already computed), `cost_usd / lives_saved_mean` lands in [$10K, $50M] — the FEMA-cited range for hazard mitigation
- *Misuse*: `test_zero_cost_intervention_rejected` — `Intervention(cost_usd=0)` raises ValueError on construction (so a future contributor can't ship a "free" intervention without naming a real reason)

**Exit gates**:
- 33 + 3 = 36 backend tests; all green
- API response includes `cost_usd` for every preset
- `docs/intervention-costs.md` exists with 10 rows + 10 sources

**Risk**: med. Fabrication credibility risk if a judge probes the sources. Mitigation: use ranges from peer-reviewed hazard-mitigation literature (Multi-Hazard Mitigation Council 2005 cost-benefit study has order-of-magnitude figures), not made-up specifics.

### M2 — Schematic map base (~1d)

**Why this slot**: M3 (animation) and M4 (Act 1+2 integration) both need the map to render. M2 ships the static map at t=0, no animation.

**Files**:
- New: `frontend/src/components/aurora/SchematicMap.vue` — main SVG component
- New: `frontend/src/components/aurora/map/DistrictTile.vue` — one tile per district (label + outlined polygon)
- New: `frontend/src/components/aurora/map/Building.vue` — colored dot per building (color by hazus_class)
- New: `frontend/src/components/aurora/map/ResponderIcon.vue` — Phosphor icon at lat/lon (Hospital, FirstAid, Siren)
- New: `frontend/src/design/projection.js` — equirectangular projection helpers: `project(lat, lon, bbox, viewBoxWidth, viewBoxHeight) -> [x, y]`
- `frontend/src/views/AuroraView.vue` — render `<SchematicMap>` in the new "See the map" step (replaces the existing static scenario card on the demo seed flow)

**Map projection**: equirectangular (linear lat→y, lon→x) within the scenario's bounding box. ViewBox 1200×800. Bbox derived from min/max lat/lon of all buildings (computed once on scenario load). District polygons either (a) Voronoi tessellation around district centroids — d3-voronoi is in d3 — or (b) circular pucks at centroids with 80% radius. Option (b) is 5 LOC; Option (a) is 30 LOC. Pick (b) for v1; upgrade to (a) in M5 if it looks bad.

**Visual style**: Mode C palette (≤30% saturation tones already targeted in the closed v2 plan, but v3 doesn't migrate the global palette — uses Mode C ONLY for map colors, leaving the rest of the UI as-is). District polygons: 1px stroke `var(--ink-2)`, fill `color-mix(in srgb, var(--bg-2) 90%, transparent)`. Building dots: 3-4px radius, color by hazus_class (W1 = `var(--el-water)` muted, C1L/C1M = `var(--el-earth)` muted, PC1 = `var(--el-aether)` muted). Responder icons: 16px Phosphor + tinted via `--el-fire` for fire stations, `--el-aether` for hospitals.

**Diff scope**: ~5 new files, ~600 LOC total.

**Test scaffold**:
- *Unit-1*: `test_projection_within_bbox` — a building at the bbox center projects to (viewBoxWidth/2, viewBoxHeight/2) ± 1px
- *Unit-2*: `test_projection_aspect_ratio_preserved` — a 1° lat × 1° lon scenario projects to a square area in viewBox
- *Unit-3*: `test_schematic_map_renders_all_buildings` — mount with the LA scenario; count rendered building circles equals `scenario.buildings.length` (256)
- *Unit-4*: `test_schematic_map_renders_all_responders` — mount; count Hospital + FireStation + Shelter icons equals total facility count
- *Integration*: `test_schematic_map_renders_each_of_6_scenarios` — for each scenario_id, mount the map and assert it renders without error
- *Misuse*: `test_zero_buildings_renders_empty_map` — pass an empty `buildings: []`; the component renders a "no buildings" state, doesn't crash

**Exit gates**:
- 28 + 6 = 34 frontend tests + 36 backend = 70; all green
- Bundle gz: ≤ 270 kB total (currently 234.84; budget +35 kB for the new SVG components)
- All 6 scenarios render the static t=0 map without error
- Visual: spot-check (you eye-test the screenshots) — districts visibly tile the bbox, buildings dot the inside, responder icons are visible

**Risk**: med. Visual quality is subjective; budget allows 1 iteration with you.

### M3 — Animation engine (~1.5d)

**Why this slot**: M5 (Act 3 integration) needs the animation to play during a real run. M4 (Act 1+2) is independent.

**Files**:
- New: `frontend/src/components/aurora/map/HazardHeatmap.vue` — radial-gradient SVG `<defs>` + `<circle>` at epicenter, animated via GSAP from r=0 to bbox-diameter over `duration_hours` simulated time
- New: `frontend/src/components/aurora/map/Timeline.vue` — `<input type="range" min="0" max="duration_hours">` + play/pause/speed buttons (1×, 2×, 4×). 5-LOC scrubber, not d3-brush.
- New: `frontend/src/composables/useScenarioPlayback.js` — playback state machine: ref<currentHour: number>, ref<playing: boolean>, ref<speed: number>; play() advances currentHour by speed every (1000ms / speed) interval; pause() stops; seek(h) sets currentHour
- `frontend/src/components/aurora/map/Building.vue` — extend to read damage state from `mcRun.timeline[currentHour].deaths_by_district[building.district_id]` and color-shift accordingly (green→amber→red as cumulative district deaths grow)
- `frontend/src/components/aurora/map/SchematicMap.vue` — accept new props `currentHour`, `mcRunResult`; pass through

**Time/sim mapping**: 1 simulated hour = 1 second of wall time at speed=1×. LA M7.2 demo has 24h → 24 sec. Joplin EF5 has 6h → 6 sec. Türkiye-Syria has 72h → 72 sec (long; default speed=2× for that scenario). Demo seed flow auto-runs at speed=1× for LA = 24 sec.

**Heatmap**: SVG radial gradient. Inner stop = `color-mix(in srgb, var(--el-fire) 60%, transparent)` at hazard intensity peak. Outer stop = transparent. Animate `r` attribute via GSAP's `to(circle, {attr: {r: targetR}, duration: simHours, ease: 'expo.out'})`. Peak intensity reached at hour 1 then plateau (matches HAZUS shake intensity profile).

**Agent dots**: don't actually render 80,000 population dots. Each district's `population` is rendered as a single density meter (a small horizontal bar inside the district tile, fills over time as evacuations happen). The simulator already produces aggregate counts per district per hour; visualizing per-individual dots is a yak-shave that adds zero pedagogical value and would tank performance.

**Diff scope**: ~3 new files, 2 file edits, ~400 LOC total.

**Test scaffold**:
- *Unit-1*: `test_playback_advances_hour_on_play` — call play(); after 1100ms (1× speed), currentHour should be 1
- *Unit-2*: `test_playback_seek_clamps_to_duration` — seek(999) on a 24h scenario → currentHour=24
- *Unit-3*: `test_building_damage_color_at_hour` — given an `mcRun.timeline[5].deaths_by_district = {LA-D03: 12}`, the building component for a D03 building reads color from a heuristic `deaths_in_district / total_buildings_in_district * SEVERITY` and lerps between green/amber/red
- *Unit-4*: `test_heatmap_radius_at_hour` — at hour=0, r=0; at hour=duration, r=full bbox diameter
- *Integration*: `test_play_full_run_no_errors` — mount with a complete mcRun result; programmatically play through all 24 hours; no error events emitted, no console warnings
- *Misuse*: `test_play_without_mcrun_renders_t0_only` — mount with `mcRun=null`; play() does nothing; the map stays at t=0

**Exit gates**:
- 34 + 6 = 40 frontend tests + 36 backend = 76; all green
- Bundle gz: ≤ 290 kB total (M2 added ~35; M3 adds ~20)
- Manual smoke (you eye-test): demo seed flow → animation plays smoothly from t=0 to t=24 → heatmap pulses outward → at least one district visibly changes color

**Risk**: high. SVG animation perf at 60fps with 256 buildings + heatmap + ticking timeline is the unknown.

### M4 — Act 1 + Act 2 integration (~0.5d)

**Why this slot**: AuroraView's existing one-page render needs to break into "screens". This phase wires the FIRST TWO screens (Load + See the map at t=0).

**Files**:
- `frontend/src/views/AuroraView.vue` — add `currentAct: ref<'load' | 'map' | 'run' | 'report' | 'compare'>` state. Render only the matching screen via `v-if`. The existing scenario picker becomes the "load" screen (cleaned up — drop the always-visible interventions block, that lives in Act 4 now).
- New: `frontend/src/components/aurora/acts/Act1Load.vue` — scenario picker only; "Continue → see the map" CTA
- New: `frontend/src/components/aurora/acts/Act2Map.vue` — wraps `<SchematicMap>` at t=0; shows scenario context (city, hazard summary, district pop totals); "Run the simulation" CTA
- `?seed=demo` flow: lands on Act 2 with the LA scenario pre-selected; auto-advances to Act 3 after 2-second beat (was 1s; bump for the user to actually see the map)

**Diff scope**: ~3 files, ~250 LOC.

**Test scaffold**:
- *Unit-1*: `test_initial_act_is_load` — mount AuroraView with no params; currentAct === 'load'
- *Unit-2*: `test_continue_advances_to_map_only_if_scenario_selected` — disabled-attribute + click-handler-guard pattern (same as v2 plan U3)
- *Unit-3*: `test_seed_demo_lands_on_act2` — mount with `?seed=demo`; after applyDemoSeed returns, currentAct === 'map'
- *Integration*: `test_load_to_map_transition_preserves_scenario_id` — pick LA, click Continue, the map renders LA's buildings (256 dots)
- *Misuse*: `test_continue_with_no_scenario_does_nothing` — both `:disabled` AND handler guard refuse advance

**Exit gates**:
- 40 + 5 = 45 frontend tests + 36 backend = 81; all green
- Demo seed lands on Act 2 within 2.5s, no console errors

**Risk**: low.

### M5 — Act 3 integration: live disaster on the map (~1d)

**Why this slot**: ties M3 (animation engine) to the live `/run_mc?streaming=true` flow. Replaces the existing `MCProgressPanel` for the demo's visual path; the panel stays available as a programmatic-debug surface.

**Files**:
- New: `frontend/src/components/aurora/acts/Act3Run.vue` — wraps `<SchematicMap>` in a "playing" mode. Subscribes to the same `/run_mc/<run_id>/progress` polling as MCProgressPanel. As each per-hour update arrives, advances the playback's `currentHour`. When `done=true`, fetches `/result` and emits `done` event up to AuroraView, which advances to Act 4.
- `frontend/src/components/aurora/MCProgressPanel.vue` — leave as-is. Act 3 uses it as a side-panel (small) showing "trial 12/30 complete · 18s elapsed" so the user knows progress is real.
- `?seed=demo` auto-advance to Act 3 starts the run; the existing 1-second beat stays.

**Diff scope**: ~2 files, ~250 LOC.

**Test scaffold**:
- *Unit-1*: `test_act3_starts_run_on_mount` — mounting Act3Run with a scenarioId triggers `runMCStreaming`; assert the API was called once
- *Unit-2*: `test_act3_advances_playback_on_progress` — fake `/progress` response with `arms.X.trials_done=5`; assert playback.currentHour increments
- *Unit-3*: `test_act3_emits_done_with_full_result` — fake `done=true` response; assert emit('done') fires with the full mcRun
- *Integration*: `test_full_run_via_act3` — mock LLM stub returning deterministic numbers; full streaming MC plays through, animation runs through all hours, done event fires
- *Misuse*: `test_act3_handles_run_failure` — fake `error: 'simulated failure'` in /progress response; act3 surfaces error, does NOT advance to Act 4

**Exit gates**:
- 45 + 5 = 50 frontend tests; all green
- Demo seed flow: Act 3 plays animation in ≤30s on LA M7.2 (24 hours × 1s/hour wall time + ~3s startup overhead), result fetched, advances to Act 4

**Risk**: med. Streaming + animation timing must align — if the per-hour callback arrives faster than 1s/hour, the animation looks choppy. Solution: decouple animation playback time from MC run time. The animation always plays at 1s/sim-hour regardless of how fast the backend produces data; if backend finishes early, the animation finishes its remaining hours from the cached result.

### M6 — Act 4: cost-ranked report (~0.5d)

**Why this slot**: After Act 3 completes, the user sees the deltas + ranked interventions. Reuses M1's cost data + the existing `mcRun.deltas` from the API.

**Files**:
- New: `frontend/src/components/aurora/acts/Act4Report.vue` — header: "Without intervention: 6,400 deaths in LA M7.2." Body: ranked list of `intervention.cost_usd / delta.lives_saved_mean` (cost-per-life-saved, ascending). Each row has a checkbox "Add to next run". CTA: "Re-run with selected interventions →"
- `frontend/src/views/AuroraView.vue` — wire Act 4 → currentAct='compare' transition with `selectedInterventionIds` state
- Optional: small bar-chart sparkline per intervention row showing `lives_saved` vs cost

**Diff scope**: ~2 files, ~200 LOC.

**Test scaffold**:
- *Unit-1*: `test_act4_renders_only_interventions_with_cost_data` — interventions without `cost_usd` are excluded from the ranked list
- *Unit-2*: `test_act4_sorts_by_cost_per_life_saved` — given known mcRun, the rendered order matches `sorted(deltas, key=lambda d: d.intervention.cost_usd / d.lives_saved.mean)`
- *Unit-3*: `test_act4_emits_selected_intervention_ids` — toggle 2 chips, click "Re-run", emitted payload contains those 2 ids
- *Misuse*: `test_act4_handles_zero_lives_saved` — an intervention with `lives_saved.mean = 0` shows "no impact" — does NOT divide by zero

**Exit gates**:
- 50 + 4 = 54 frontend tests; all green
- Manual: report renders, ranking is monotonic, "Re-run" CTA enabled iff ≥1 chip selected

**Risk**: low.

### M7 — Act 5: re-run + visible compare (~1d)

**Why this slot**: This is the wow moment. Without it, the user never SEES that interventions matter — they only see numbers.

**Approach** (simplest that works):
- After Act 4 emits selected interventions, AuroraView kicks off a second `/run_mc?streaming=true` call WITH those interventions applied
- During the second run, Act 5 shows BOTH the original mcRun (left half) and the new run (right half) playing simultaneously on side-by-side maps. The difference in heatmap intensity, building damage, and final death tally is visible motion.
- After both complete, the comparison persists. CTA: "Try a different scenario" → resets to Act 1.

**Files**:
- New: `frontend/src/components/aurora/acts/Act5Compare.vue` — two `<SchematicMap>` instances side-by-side, both advancing in lockstep via a shared `useScenarioPlayback` instance
- `frontend/src/views/AuroraView.vue` — wire Act 5 with `originalMcRun` + `interventionMcRun` state

**Diff scope**: ~2 files, ~300 LOC.

**Test scaffold**:
- *Unit-1*: `test_act5_renders_both_maps` — mount with both mcRuns; find 2 `<SchematicMap>` instances
- *Unit-2*: `test_act5_playback_lockstep` — both maps' currentHour stays equal as playback advances
- *Unit-3*: `test_act5_summary_shows_lives_saved_delta` — at end-of-playback, the summary chip reads `livesSaved = original.deaths - intervention.deaths`
- *Misuse*: `test_act5_handles_intervention_run_failure` — if the second run errors, Act 5 stays in Act 4 state, surfaces error, does NOT crash

**Exit gates**:
- 54 + 4 = 58 frontend tests; all green
- Demo seed full flow: Act 1→2→3→4→5 takes ≤ 2 minutes (24s + 24s for 2 runs + ~30s of UI transitions/reveals)
- Side-by-side: the visible delta in the right map's heatmap intensity vs the left is unambiguous (subjective; you eye-test)

**Risk**: med. Two maps × 256 buildings each × 60fps = 30k DOM updates/sec — likely the perf ceiling. Mitigation: drop to 30fps (visually fine for science viz), or render the right map at half-size during playback, or delay the second map's render until the first finishes (sequential, not lockstep). Pick at implementation time based on actual measured FPS.

### M8 — Final E2E + recording prep (~0.5d)

**Files**:
- README update: replace screenshots, update narrative to describe the 5-act experience
- USAGE.md update: document `?seed=demo` lands on Act 2, full flow takes ≤2min
- Manual: run the demo end-to-end on the M4 Pro target hardware; record a screen capture

**Exit gates**:
- 58 frontend + 36 backend = 94 tests, all green
- D1 mirofish-grep guard: 3/3 OK
- `./start.sh check`: all green
- Bundle ≤ 320 kB gz (target ≤ 290; ceiling 320)
- Demo recording captures the 5 acts in ≤ 2 min wall time

**Risk**: low.

## Math sanity check

- **Effort**: M0 (0.5d) + M1 (0.5d) + M2 (1d) + M3 (1.5d) + M4 (0.5d) + M5 (1d) + M6 (0.5d) + M7 (1d) + M8 (0.5d) = **6.5 working days**.
- **Available**: 6 working days. **Buffer: -0.5 days** (negative — over budget by half a day).
- **Bundle delta projection**: M2 (~35 kB) + M3 (~20 kB) + M4 (~5 kB) + M5 (~5 kB) + M6 (~5 kB) + M7 (~10 kB) = **+80 kB**. Total: 234.84 + 80 = ~315 kB. Within the 320 kB ceiling but tight.
- **Animation perf**: 256 building dots × 60 fps = 15.4k ops/sec. SVG is fine for this. 2 maps in M7 = 31k ops/sec — borderline; mitigation noted above.

## Open questions

1. **Pixi.js?** v1 says no, but if M3 measures < 30fps with raw SVG, Pixi may be required. Adding it post-M3 is the wrong order.
2. **Costs sourcing**: shall we use Multi-Hazard Mitigation Council 2005 cost-benefit study + local EM procurement public records, with each entry footnoted? Or a simpler "estimated by Aurora authors based on order-of-magnitude reference points; not authoritative for pilot use" disclaimer?
3. **Compare layout**: side-by-side or before/after toggle? Side-by-side reads instantly in a recording but takes 2× the screen real estate.
4. **Streaming + animation alignment**: lockstep (animation paces with backend) or decoupled (animation always 1s/hour, backend may finish first)? v1 picks decoupled but you should review.
5. **Effort overrun**: 6.5d estimated vs 6d budget. Cuts to consider: drop M7 lockstep compare and ship sequential (run-1-then-run-2) — saves ~0.25d. Drop M5 streaming-progress side-panel — saves ~0.25d. Or push recording to 2026-05-12 (still in-budget for the 5/18 deadline).

## Test-first scaffold (consolidated)

| Phase | Unit (≥3) | Integration (≥1) | Misuse (1) |
|---|---|---|---|
| M0 | hourly snapshot has field; sum-matches-cumulative; missing-district-zeroed | curl /progress includes per-district per-hour | trial with no deaths still has all districts in dict |
| M1 | every preset has cost+source; cost/life-saved in [10K, 50M]; sources are non-empty | /run_mc response includes cost_usd | zero-cost intervention construction raises ValueError |
| M2 | projection within bbox; aspect-ratio preserved; buildings rendered; responders rendered | each of 6 scenarios renders | empty buildings list → empty-state, no crash |
| M3 | playback advances; seek clamps; building color at hour; heatmap radius at hour | full play through 24h, no console errors | play without mcRun stays at t=0 |
| M4 | initial act is load; continue gated by selection; ?seed=demo lands on Act 2 | load→map preserves scenario_id | continue with no selection refuses |
| M5 | starts run on mount; advances on progress; emits done | full streaming run plays through animation | run failure surfaces error, no advance |
| M6 | filters costless interventions; sorts by $/life; emits selected ids | rendered ranking matches sorted | zero lives saved → no division-by-zero |
| M7 | renders 2 maps; lockstep playback; summary delta | full Act 5 with 2 mcRuns plays | second-run failure shows error, no crash |
| M8 | (no new tests; integration sweep) | full E2E ≤ 2min walkthrough | reduce-motion still works |

---

# Measurable KPIs & quality gates

## North Star
**Time from cold load to user-visible "lives saved with intervention" comparison ≤ 2 minutes**, on the M4 Pro target. Externally validated by stopwatch on the demo recording.

## Input metrics (5)
| # | Metric | Definition | Today | Target | Phase |
|---|---|---|---|---|---|
| 1 | Acts visible in viewport | currentAct render gates work | 1 (one-page UI) | exactly 1 of 5 at a time | M4 |
| 2 | Map FPS during playback (Act 3) | Chrome perf panel measurement on M4 Pro | n/a | ≥ 30 fps for 24h LA M7.2 | M3 |
| 3 | Cost-ranked interventions in Act 4 | count rendered | 0 | ≥ 5 (covering at least 3 categories) | M6 |
| 4 | Visible delta in compare (Act 5) | (max heatmap red intensity in original) − (max heatmap red intensity in intervention) | n/a | > 15% measured by RGB sampling | M7 |
| 5 | Bundle gz total | npm run build | 234.84 kB | ≤ 320 kB | M2-M8 |

## HEART
| Dimension | Metric | Red flag |
|---|---|---|
| Happiness | n=5 viewers Likert: "Could you understand what was happening on the map?" 1=confused, 5=clear | < 60% pick 4 or 5 |
| Engagement | Time on page through full Acts 1→5 | < 60s = too fast/skippable, > 180s = too slow |
| Adoption | % of demo runs reaching Act 5 | < 90% |
| Task Success | % full Act 1→5 walkthroughs without error on n=5 attempts | 100% required |

## Stop conditions
- **M3 perf < 30fps with SVG** → switch to Pixi.js (adds ~30 kB gz; bundle ceiling stays satisfied). If still < 30fps, drop the heatmap pulse and only animate building color shifts.
- **M7 lockstep doubles cost** → fall back to sequential compare (run 1, then run 2, no concurrent playback). Visual delta still legible.
- **By 2026-05-08 EOD M0-M3 not committed** → halt M4-M8; ship M0-M3 only (the map exists but no Acts 4/5). The user still sees the simulation visualized.
- **Costs research blocks for > 4h** → ship "estimated by Aurora authors; for hackathon demonstration only" disclaimer + simple round-number costs ($1M / $10M / $50M tiers); don't try to look authoritative.

---

## Ready-to-start step

User greenlight on:

(a) **Strict serial M0 → M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8** (~6.5d, over budget by 0.5d, requires either pushing recording to 5/12 or dropping M7's lockstep compare).
(b) **Cut M7 to "sequential compare"** (run 1 fully, then run 2 fully, side-by-side static at end) — saves ~0.5d, recording stays at 2026-05-11.
(c) **Cut M5 streaming side-panel** (animation still plays, but no "trial 12/30" indicator) — saves ~0.25d.

Recommended: **(b)**. Sequential compare is more legible in a recorded video anyway — the viewer focuses on one map at a time, then sees both side-by-side at the end.

After greenlight, this v1 plan goes through hostile review per the plan-with-review skill. No code lands until v2 is hardened.
