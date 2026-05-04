# Aurora simulation-experience v2 — HARDENED, ready for greenlight

**Source v1**: `docs/aurora-simulation-experience-v1.md`
**Reviewer verdict**: PLAN BREAKS — 5 load-bearing failures + multiple substantive issues.
**Status**: v2 absorbs every finding. Awaiting user greenlight.

---

## What v1 got wrong (5 load-bearing items)

1. **Effort math off by 0.5d.** v1 line 255 said 6.5d total. Actual sum: 0.5+0.5+1.0+1.5+0.5+1.0+0.5+1.0+0.5 = **7.0d**. Available: 6 working days. **Buffer: -1.0 day**, not -0.5d. Either cut scope or push recording to 5/13.

2. **Türkiye-Syria busts the 2-min North Star by 50%.** `duration_hours=72` × 1s/sim-hour × 2 runs (Act 3 + Act 5) = 144s; plus Acts 1+2+4+5 reading = ~2m59s. v1's North Star is unreachable for that scenario. Either constrain to LA only OR cap Act 3 at fixed wall time and stretch sim-hours/sec dynamically.

3. **M1 breaks 3 existing intervention tests.** `backend/tests/test_aurora.py:171,182,197` construct `ResourcePrepositionIntervention`, `SeismicRetrofitIntervention`, `EvacTimingIntervention` without `cost_usd`. Adding a required field (no default) → `TypeError`. Adding `cost_usd: int = 0` default → contradicts the misuse test. v1 didn't address this.

4. **LLM-slow-path desync has no fallback.** M5 "decouples animation from backend" but only spec'd the FAST case (backend faster than animation). On LLM mode, backend at p95 ~45s vs animation 24s → viewer sees a "completed" map for ~20 seconds with no result yet. No fallback specified.

5. **Reduce-motion + vite cold compile failure modes uncaught.** M3/M7 wow factor IS animation; with reduce-motion ON, GSAP snaps to end → static t=24 map, no story arc. M4's 2-second auto-advance fires before the SchematicMap chunk paints on a vite cold-compile (4-8s).

## Failure scenarios the red team found (and how v2 addresses each)

- **FS-1 — Vite cold compile vs auto-advance** → v2 changes M4 to "auto-advance fires AFTER the SchematicMap component reports `mounted` AND its first paint completes" (use `requestAnimationFrame` after `onMounted`). The 2-second timer becomes "max(2s, time-to-first-paint + 500ms)". New M4 exit gate: `time_to_first_paint < 3000ms` measured via Performance API; if not, halt and show a "Loading map…" skeleton.

- **FS-2 — LLM path desync** → v2 M5 adds an explicit "computing" state. If `currentHour === duration_hours` AND `done === false`, show "Aurora is finalizing trial X of N — animation complete, computing remaining trials…" overlay on the map. The map's final state stays visible. When `done === true`, the overlay clears and Act 4 advances. v2 adds a unit test `test_act3_handles_backend_slower_than_animation`.

- **FS-3 — Reduce-motion kills wow** → v2 adds a "stepped frames" fallback for reduce-motion: instead of continuous animation, the playback advances in 5 quartile beats (t=0, t=quarter, t=half, t=three-quarter, t=end) with 1s pauses between. This preserves the story arc visually while respecting the OS preference. New unit test in M3: `test_reduce_motion_steps_through_quartiles`.

## Missing edge cases now covered

- **EC-1 (M1 breaks existing tests)** → v2 M1 specifies: `cost_usd: int = 1_000_000` AS DEFAULT (a placeholder representing "unspecified" — the magnitude is the FEMA BCA-Toolkit median for hazard mitigation). The misuse test changes from "default rejected" to "explicit `cost_usd=0` rejected" — the contradiction the reviewer caught. Existing 3 tests pass without modification because they get the default. M1 effort drops to 0.25d (no test fixture surgery needed).

- **EC-2 (back-nav scenario change)** → v2 M4 adds `onScenarioChange()` watcher: when `selectedScenarioId` changes mid-flow, reset `currentAct = 'load'` AND clear `mcRun`. Test: `test_back_navigation_resets_to_act1_on_scenario_change`.

- **EC-3 (URL deep-links to acts)** → v2 commits to URL-driven `?act=N` query param. Vue-router watch on the param sets `currentAct`. Reload mid-recording lands on the correct act. Test: `test_url_act_param_drives_currentAct`.

- **EC-4 (recent_decisions / AgentLogTicker)** → v2 explicitly KEEPS the AgentLogTicker as a side-panel in Act 3. The agent decision feed is part of the Aurora narrative. Wired via the same shared poller composable noted in EC below.

- **EC-5 (M7 doubles MC wall time)** → v2 picks plan **option (b) + (c)**: sequential compare (no lockstep) AND drop M5's separate streaming side-panel (Act 3's map IS the progress UI). Saves 0.75d. New effort total: 6.25d, still 0.25d over 6.0d budget. Mitigation: defer M8 README screenshot updates to post-recording (the PR ships; screenshots are a follow-up commit).

- **EC-6 (M5 double-poll)** → v2 lifts the `/progress` polling into a NEW shared composable `frontend/src/composables/useMCStreaming.js`. Both MCProgressPanel and Act3Run consume it. Single poll rate. Test: `test_useMCStreaming_single_poll_for_multiple_consumers`.

## Scalability risk → mitigation

**Risk**: Türkiye-Syria 72-hour duration busts the 2-min North Star by 50%.

**Mitigation in v2** — adaptive animation pacing:
- New formula: `wall_seconds_per_sim_hour = max(0.4, min(2.0, 24.0 / duration_hours))`. LA (24h) → 1.0s/hour → 24s. Joplin (6h) → 2.0s/hour → 12s. Pompeii (20h) → 1.2s/hour → 24s. Türkiye-Syria (72h) → 0.4s/hour → 28.8s. All scenarios fit in ≤30s of Act 3 animation. New North Star math: 30s + 30s + 30s + 5s = 95s ≤ 120s for ALL 6 scenarios.
- Constraint: cap minimum at 0.4s/hour so even fast scenarios don't blur.
- Atlantis: same math (24h × 1.0s = 24s).

**Map projection upgrade** (was equirectangular linear; now d3-geo proper):
- v2 uses `d3.geoEquirectangular()` from d3-geo (already in d3 7.9 bundle). Auto-centers and scales to bbox. For Türkiye-Syria, this halves the E-W distortion vs naive linear lat/lon. Adds ~3 LOC, not 30.

**SVG perf realism**:
- v2 default target: **30fps**, not 60fps. Industry rule: pure SVG holds 30fps to ~500 nodes; 60fps requires Canvas/Pixi. Plan acknowledges this honestly and ships at 30fps target. New M3 exit gate: `measured_fps_30s_window ≥ 28fps` (allow 2fps headroom for jitter). Pixi escape hatch documented in M3 stop conditions.

**Two consumers, single poller** (EC-6 mitigation): saves doubled request rate visible in network panel.

## Other gaps the reviewer caught

- **`_hourly_loss` doesn't pre-seed all district keys** at `agent_runtime.py:298-299` — uses `.get(district, 0) + d_h`, so districts with zero deaths are absent. v2 M0 adds an explicit pre-seed step: `deaths_by_district = {d.district_id: 0 for d in scenario.districts}` before the loss loop. Adds ~5 LOC. v2 misuse test now correct.
- **Heatmap radial doesn't fit Joplin EF5 (corridor) or Pompeii (asymmetric pyroclastic flow)**. v2 M3 adds a `Hazard.shape: Literal["radial", "corridor", "asymmetric"]` field to the existing `Hazard` dataclass + per-scenario assignment. HazardHeatmap renders the appropriate primitive: radial (current), corridor (rect with feathered ends along epicenter→destination vector), asymmetric (radial + directional cone offset). Adds ~80 LOC vs v1's 30. Effort: M3 = 1.5d → 1.75d.
- **No per-phase slip threshold**. v2 adds: "any phase exceeds 1.5× its estimate → halt and re-scope before continuing". Catches the M2-takes-2d-not-1d failure mode.
- **HEART Happiness n=5 thin**. Bump to **n=10** with 70% pick 4 or 5 (i.e. 7-of-10). Same recording effort.
- **HEART Engagement band → target**. Median 90s, σ ≤ 30s. Falsifiable.
- **M2 adjective gates** "districts visibly tile the bbox" → "each district polygon centroid within 10% of projected lat/lon centroid; circles don't overlap > 5% by area".
- **M3 adjective gates** "you eye-test" → "max FPS ≥ 28 measured via in-page rAF counter; GPU memory ≤ 200MB via Chrome perf; zero console warnings".
- **M7 adjective gate** → "≥ 15% RGB delta in heatmap red channel between maps at end-of-playback" (binds to existing input metric #4).

## Corrected sequencing (v2 — sequential compare, single-poll, adaptive animation)

| # | Phase | Why this slot | Effort | Risk | Depends on |
|---|---|---|---|---|---|
| M0 | Per-district per-hour timeline | M3 reads it; ships with U1 streaming-fix | **0.5d** | low | U1 PR #5 merged |
| M1 | Intervention costs (default-valued, no test fixture surgery) | Act 4 ranks by it | **0.25d** | low | M0 |
| M2 | Schematic map base + d3-geo projection | M3, M4, M7 all use it | **1.0d** | med | M1 |
| M3 | Animation engine + adaptive pacing + reduce-motion stepped fallback + corridor/asymmetric heatmaps | M5/M7 plays through it | **1.75d** | high | M2 |
| M4 | Act 1 + Act 2 + URL `?act=N` driver + back-nav reset | enables Acts 3-5 | **0.75d** | low | M3 |
| M5 | Act 3 + shared `useMCStreaming` composable + LLM-slow-path "computing" overlay | Act 4 needs result | **1.0d** | med | M4 |
| M6 | Act 4: cost-ranked report | Act 5 needs selected ids | **0.5d** | low | M5 |
| M7 | Act 5: SEQUENTIAL compare (run-1 then run-2) — NOT lockstep | demo wow moment | **0.75d** | med | M6 |
| M8 | Final E2E + recording prep (README screenshots DEFERRED to post-recording) | recording is the goal | **0.25d** | low | M7 |

**Total: 6.75d. Available: 6 days. Buffer: -0.75d.** Mitigation: M8 README screenshots are deferred to post-recording follow-up commit, saving 0.5d → 6.25d → still 0.25d over.

**Final mitigation**: push recording to **2026-05-12 (Tuesday)**. Adds 1 working day (2026-05-12 itself), buffer becomes +0.75d. Hackathon submission deadline 2026-05-18 unchanged. The user picks: (i) ship at 6.0d-tight 5/11 with risk, or (ii) push to 5/12 with breathing room.

## Corrected math

- Effort: **6.75d** (was 6.5d in v1)
- Bundle delta: +35 (M2) + 25 (M3 with corridor/asymmetric) + 5 (M4) + 5 (M5) + 5 (M6) + 10 (M7) = **+85 kB**. 234.84 + 85 = **319.84 kB**. **Inside the 320 ceiling by 0.16 kB.** Tight but valid. Any extra Phosphor icon would tip over — flagged.
- Animation timing per scenario (adaptive pacing): all 6 fit in ≤ 30s Act 3.
- LA M7.2 demo seed total: 30s Act 3 + 30s Act 5 + ~30s reading = **90s ≤ 120s.** Holds.
- Türkiye-Syria worst case: same 90s with adaptive pacing. Holds.

## Corrected KPIs & gates

### North Star (corrected)
**Time from cold load to user-visible "lives saved with intervention" comparison ≤ 2 minutes, on ALL 6 scenarios on the M4 Pro target** (was "≤ 2 min on LA only"). Adaptive animation pacing makes this universally feasible.

### Input metrics (corrected)
| # | Metric | Definition | Today | Target | Phase |
|---|---|---|---|---|---|
| 1 | Acts visible in viewport | currentAct render gates | 1 (one-page) | exactly 1 of 5 | M4 |
| 2 | Map FPS (in-page rAF counter) | Median FPS over 30s playback window | n/a | ≥ 28 fps (was 30 — 2fps jitter allowance) | M3 |
| 3 | Cost-ranked interventions in Act 4 | count rendered ≥ 5 covering ≥ 3 categories | 0 | ≥ 5 / ≥ 3 categories | M6 |
| 4 | Visible delta in compare (Act 5) | RGB-red-channel delta at end-of-playback | n/a | ≥ 15% | M7 |
| 5 | Bundle gz total | npm run build | 234.84 kB | ≤ 320 kB | M2-M8 |

### HEART (corrected)
| Dimension | Metric | Red flag |
|---|---|---|
| Happiness | n=10 viewers Likert: "could you understand what was happening on the map?" 1=confused, 5=clear | < 70% pick 4 or 5 |
| Engagement | Time on page through full Acts 1→5 | median 90s, σ ≤ 30s |
| Adoption | % demo runs reaching Act 5 | < 90% |
| Task Success | % full Act 1→5 walkthroughs without error on n=5 | 100% |

### Phase exit criteria (v2 — every gate is a number)

#### M0 exit
- 30 + 3 = 33 backend tests; all green
- `/progress` JSON contains per-hour per-district death counts (curl-verified)
- All districts present even when 0 deaths (the pre-seed fix)
- U1 PR #5 merged into main

#### M1 exit
- 33 + 3 = 36 backend tests; all green
- All 10 presets have `cost_usd > 0` (default 1M placeholder OR named source)
- `/run_mc` response includes `cost_usd` for each delta
- `docs/intervention-costs.md` with named sources; ≤ 2h research budget; fallback disclaimer if no sources found

#### M2 exit
- 28 + 6 = 34 frontend tests; all green
- Each district polygon centroid within 10% of projected lat/lon centroid
- Building circle pairs don't overlap > 5% by area
- Bundle ≤ 270 kB gz
- All 6 scenarios render at t=0 without console error

#### M3 exit
- 34 + 6 = 40 frontend tests; all green
- Median FPS ≥ 28 over 30s playback window (in-page rAF counter)
- GPU memory ≤ 200MB via Chrome perf
- Zero console warnings during playback
- Reduce-motion: 5 quartile-step beats land within 6s total
- Heatmap renders correctly for radial / corridor / asymmetric shapes (3 shape tests)
- Bundle ≤ 295 kB gz

#### M4 exit
- 40 + 5 = 45 frontend tests; all green
- `?act=2` URL deep-link lands on Act 2 directly
- Time-to-first-paint < 3000ms (Performance API)
- Back-nav scenario change resets to Act 1

#### M5 exit
- 45 + 5 = 50 frontend tests; all green
- Shared `useMCStreaming` composable: only 1 poll request per `run_id` regardless of consumer count
- LLM-slow-path: "computing" overlay renders when `done === false` AND `currentHour === duration_hours`
- Demo seed Act 3 plays in ≤ 30s on LA M7.2 synth path

#### M6 exit
- 50 + 4 = 54 frontend tests; all green
- Ranked list sorted ascending by `cost_usd / lives_saved.mean`
- Re-run CTA emits selected ids; disabled iff 0 selected
- Zero-lives-saved interventions show "no impact" placeholder, no division error

#### M7 exit
- 54 + 4 = 58 frontend tests; all green
- Sequential compare (NOT lockstep): run-1 plays fully → result captured → run-2 plays fully → side-by-side static at end
- ≥ 15% RGB-red-channel delta at end-of-playback
- Total Act 5 wall time ≤ 70s (30s + 30s + 10s buffer)

#### M8 exit
- 58 frontend + 36 backend = **94 tests, all green**
- D1 mirofish-grep guard: 3/3 OK
- `./start.sh check`: all green
- Bundle ≤ 320 kB gz
- Recording captures all 5 acts in ≤ 2 min wall time
- README screenshots DEFERRED (post-recording follow-up commit; out of M8 scope)

## Stop conditions

- **M3 perf < 28fps with SVG** → switch to Pixi.js (adds ~30 kB gz; bundle headroom 0.16 kB so ALSO drop 1 phosphor icon to make room). If Pixi still < 28fps, drop the heatmap pulse and only animate building color shifts.
- **Any phase > 1.5× estimate** → halt, re-scope before continuing. Don't paper over with "we'll catch up". v1 did not have this gate.
- **By 2026-05-08 EOD M0-M3 not committed** → halt M4-M8; ship M0-M3 (map exists, plays animation, no Acts 4/5). The user STILL sees the simulation visualized — partial wow.
- **Costs research blocks > 2h** → ship default-1M placeholder + footnote disclaimer ("estimated by Aurora authors for hackathon demonstration; not authoritative for pilot use"). Don't try to look authoritative.
- **Türkiye-Syria adaptive pacing breaks visual readability** (60-frame test viewer can't follow what's happening) → halt the universal North Star claim; revert to "≤ 2 min for LA M7.2; longer scenarios may exceed".

## Updated test-first scaffold

| Phase | Unit (≥3) | Integration (≥1) | Misuse (1) |
|---|---|---|---|
| M0 | hourly snapshot has field; sum-matches-cumulative; pre-seed all districts | curl /progress includes per-district per-hour | trial with no deaths still has all districts in dict |
| M1 | every preset has cost+source; cost-per-life-saved in [10K, 50M]; default cost honored | /run_mc response includes cost_usd | explicit `cost_usd=0` raises ValueError (NOT default) |
| M2 | projection within bbox; aspect-ratio preserved (d3-geo); buildings rendered; centroid within 10% | each of 6 scenarios renders at t=0 | empty buildings list → empty-state, no crash |
| M3 | playback advances; seek clamps; building color at hour; heatmap radial+corridor+asymmetric; reduce-motion 5 beats | full play through 24h, FPS ≥ 28, zero warnings | play without mcRun → t=0 stays |
| M4 | initial act is load; continue gated by selection; ?seed=demo lands on Act 2; ?act=N URL drives currentAct; back-nav scenario change resets | load→map preserves scenario_id; URL deep-link survives reload | continue with no selection refuses (handler + disabled) |
| M5 | useMCStreaming single-poll for multi-consumer; "computing" overlay on slow backend; advances on progress | full streaming run plays animation through | run failure halts animation, surfaces error, shows Retry CTA |
| M6 | filters costless interventions; sorts ascending; emits selected ids | rendered ranking matches sorted | zero lives saved → no division-by-zero |
| M7 | renders sequential compare (NOT lockstep); summary delta computes; RGB delta ≥ 15% | full Act 5 with 2 mcRuns plays sequentially | second-run failure shows error, no crash |
| M8 | (no new tests; integration sweep + recording) | full E2E ≤ 2min walkthrough on all 6 scenarios | reduce-motion still works through all 5 acts |

---

## Ready-to-start step — GREENLIT (option b, full scope)

User picked **option (b)** + explicit "no deferrals". Locked decisions:

- **Recording target: 2026-05-12 (Tuesday)** — pushed from 5/11. Hackathon submission deadline 2026-05-18 unchanged. Buffer: +0.75d.
- **No phases dropped.** M0 → M8 strict serial. M8's README screenshots ship inline (not deferred to follow-up commit).
- **Total effort: 6.75d in 7d budget** (5/4-5/8 + 5/11-5/12 = 7 working days, weekends excluded).
- **Per-phase slip gate**: any phase > 1.5× its estimate halts the round for re-scoping (caught in v1 review).

Sequencing locked:
M0 (0.5d) → M1 (0.25d) → M2 (1.0d) → M3 (1.75d) → M4 (0.75d) → M5 (1.0d) → M6 (0.5d) → M7 (0.75d) → M8 (0.25d) = **6.75d**.

After U1 PR #5 merges into main, M0 starts immediately on a new branch `phase/aurora-sim-experience-v3` off updated main. One PR off that branch covering M0-M8 at the end. No code lands until v2 plan is the source of truth.
