# Aurora Experience v3 — DRAFT (pre-red-team)

**Status:** draft. Do NOT execute. Spawn red-team first.
**Date:** 2026-05-05.
**Working tree state:** branch `phase/aurora-sim-experience-v3`. M0 (per-district timeline), M1 (intervention costs), M2 (schematic map), M2.1 (Neo4j decoupling) shipped. M3-M8 not started. User feedback today: "Looks horrible. Lets make a plan to win this hackathon."

## What the user wants (verbatim, distilled)

1. **Intro screen** — strong opening, Aurora as a brand, not a one-page form.
2. **City pick** — cards morph into chosen city.
3. **2D topology** — the schematic map we already have.
4. **Disaster pick on the map** — running scenarios visible, click to load.
5. **Setup screen** — see the agents that exist (responders, populations, infrastructure, hazard), feels like a "game setup screen" but reads as a briefing.
6. **Start button**, lives + dollars trackers ticking, agent comms + social-media chatter visible.
7. **The 2D map IS the wow moment** — events develop in real time, communications visualize how Gemma agents reason like real people.
8. **Outcome report** — how people reacted, how responders performed, how prepared the city was, then the prevention pitch (interventions ranked by $ / life saved).

User constraints carved into stone:
- "Informational, we don't want to be seen as fake because of our game feel."
- "Showcase that Gemma can perfectly simulate real people."
- "Win this hackathon."

## Honest audit — what we ACTUALLY simulate today

(verified file:line)

- **Hazard physics** is real: HAZUS-MH 2.1 fragility curves (W1, C1L, C1M, PC1), Omori-Utsu aftershocks, infrastructure cascade (power → comms → hospital), 6 reference scenarios with real geocoded districts.
- **Population reasoning** is real: 9 archetypes (eyewitness, coordinator, amplifier, authority, misinformer, conspiracist, helper, helpless, critic), each with a Gemma 4 e2b system prompt ≤60 words, phase-dependent posting (0-6h / 6-24h / 24-72h), language tags (en/es/ko/zh), follower-count log-normal distribution.
- **Hourly timeline data** we can plot: cumulative deaths, deaths-by-district per hour, injuries, collapsed buildings, posts (total / misinfo / authority), hospital-load %.
- **Interventions** with named-source costs: 4 families (preposition, evac timing, retrofit, prebunk-misinfo), 10 presets, $1M-$5M per anchored to FEMA BCA / Roozenbeek 2022 / etc.
- **Monte Carlo** with paired-bootstrap 90% CI on lives_saved, dollars_saved, cost_per_life_saved.

**What is NOT simulated today** (critical for honesty):
- ❌ Inter-agent reply graphs / one population agent answering another.
- ❌ Live responder dispatch (responders generated but TODO at agent_runtime.py:485).
- ❌ Per-message LLM streaming to the frontend — `recent_decisions` is currently SYNTHETIC templates from scenario.py:87-147, not real Gemma outputs.
- ❌ Per-district infrastructure status in the timeline (computed but discarded).

This gap matters. The user said "showcase that Gemma can perfectly simulate real people" — today we sample LLM decisions per (archetype × district × phase) cell, not per agent. We must either (a) honestly frame it as "archetype-level sampling, ~360 Gemma calls/trial" or (b) close some of the gap. v3 picks (b) for the demo's hot path: **stream the cached Gemma decisions to the agent log live, and add a synthesized per-message timeline on the map that uses real cached samples.**

## The winning bet (one paragraph, will be tested by reviewer)

Aurora is a USGS ShakeMap that came alive. The page opens to a dark topographic schematic of LA with the official USGS MMI palette painted across districts, a Bloomberg-style amber-on-black ticker pinned to the bottom narrating Gemma agent decisions in UTC-Zulu monospace, a right rail showing the active archetype's last 6 Gemma decisions as a typed memory stream with timestamp + reasoning excerpt, and an INFORM-style chip strip above the map showing the live comparative delta against the no-intervention baseline. No cartoon icons, no speech bubbles, no celebratory hero KPI. The aesthetic is **FEMA + USGS + Bloomberg desk + air traffic control**. Judges should feel they are watching a decision-support console real cities could deploy on Monday — and Gemma is the analyst on shift.

## The 6-act story (v3)

Each act is an explicit `?act=N` URL state. Back button restores the prior act.

### Act 0 — Brief (15s, Aurora intro)
- **Full-bleed dark scene.** Wordmark "Aurora" + tagline ("City resilience, simulated"). Topographic line-art world map decoration in the background, USGS-palette MMI scale stripe along the bottom edge.
- One sentence: "Pick a city. Pick a hazard. See lives and dollars saved if we act differently."
- One CTA: "Begin briefing →".
- **No marketing copy. No metrics. No marketing-style graphs.**

### Act 1 — City selection (15s)
- Six city cards in a 3×2 grid. Each card shows: city name, country flag (data:URI emoji-flag fallback), population, and a single hazard tag chip in the city's element color (earth/water/fire/air/aether). Background: a low-contrast PNG topographic snippet (assets list below).
- Hover: card lifts 1px, glow in element color.
- Click: card morphs into the topology map (GSAP layout animation: card scales up, other cards fade, map fades in beneath). Wall ≤ 600ms.

### Act 2 — Topology + active hazards (15s)
- The 2D schematic map fills the canvas. USGS topographic basemap underneath (static PNG asset per city).
- Active hazards visible AS PINS on the map at their epicenters with the element color. Click a hazard pin → enters Act 3.
- Right rail: "Active hazards" list with title, magnitude, hours-since-onset, button "Brief →".
- Bottom: a thin amber ticker primed but empty — "AURORA BRIEFING ROOM ONLINE · STANDING BY".

### Act 3 — Briefing (the "game setup" screen, 30s)
- Map dims to 30% opacity (still showing the city). Foreground: a 4-column briefing panel.
  - **HAZARD** — kind, magnitude, depth, predicted MMI, expected duration. Pulled from `scenario.hazard`.
  - **POPULATION** — 9 archetype tiles, each with count, posting rate, language mix. Pulled from `archetypes.py` totals.
  - **RESPONDERS** — engines + paramedics from `responder_generator.py`, hospital beds, shelter capacity.
  - **INTERVENTIONS AVAILABLE** — toggle chips with $/life-saved estimates from `intervention_dsl.py`. Default selection: top-3 most-impactful for the chosen scenario.
- Two buttons: "Run baseline" (no interventions, the toll the city would take) and "Run with prevention" (with selected interventions). Default is "Run with prevention" — but a small toggle "compare both" is the headline path.
- Optional: "Use Gemma 4 (slow, real LLM calls)" toggle. Off by default. When ON, the briefing shows "Estimated wall time: 45-90s" honestly.

### Act 4 — Live simulation (60-90s, THE WOW MOMENT)
- Map full-bleed. USGS MMI choropleth painted on districts at the current simulated minute. Building dots fade their color from W1/C1L/PC1 native to USGS-red as damage accumulates (we already have this data per hour).
- **Top INFORM strip:** chips showing live tally — "DEATHS · 412 · vs baseline 1,108 (-63%)" "DOLLARS LOST · $1.4B · vs baseline $3.9B" "RESPONDERS DEPLOYED · 18/24" "POSTS · 1.2k authority · 4.8k civilian · 380 misinfo".
- **Right rail (Gemma memory stream):** the active archetype's last 6 Gemma decisions, monospace, timestamp + 1-line reasoning excerpt + 1-line post text. This is the Smallville move and our headline credibility device.
- **Bottom ticker (Bloomberg-style):** amber-on-black, ALL CAPS, monospace, scrolling event codes — `[14:02:18Z] M2 AFTERSHOCK 4.1 · D03 PUENTE HILLS` · `[14:02:21Z] FIRE-STN-3 → DISTRICT-7 ETA 6m` · `[14:02:25Z] ARCHETYPE-MISINFORMER → 240 RT · "boil water order is fake"` · `[14:02:31Z] AUTHORITY-COUNTER → 1.1k RT · "boil water order is REAL — source LADWP"`.
- Time control: a single horizontal time slider showing hour 0 → duration_hours, with play/pause/scrub. Pacing rule: `wall_seconds_per_sim_hour = max(0.4, min(2.0, 24/duration_hours))` (already in v2 plan, reused).
- **No speech bubbles. No emoji. No glow effects on agents.** The dot colors and the ticker carry the story.

### Act 5 — Outcome report (30s, the prevention pitch)
- Two-column layout. Left: baseline result (no interventions). Right: with-intervention result. Same map projection, same time window, side by side. End-of-playback static images.
- Top: comparative delta strip. Same chips as Act 4 but final values: "DEATHS · 412 (you saved 696 lives)" "DOLLARS · $1.4B (you saved $2.5B)".
- Below: a ranked list of interventions by `cost_per_life_saved_usd` ascending, with the source citation (FEMA BCA / Roozenbeek 2022 / etc.) inline as a footnote.
- Bottom CTA: "Try a different intervention mix" (returns to Act 3 with map state preserved) or "Pick another city" (Act 1).
- Subhead text: "Aurora simulates 9 population archetypes via Gemma 4 (e2b · ~360 calls/trial · cached). Hazard physics: HAZUS-MH 2.1 fragility curves and Omori-Utsu aftershock chains. Cost data: FEMA BCA Toolkit, Roozenbeek et al 2022, MMC 2005, FEMA P-58/ATC-33." — INFORM-style methodology footer that earns credibility with one line.

## Asset list (concrete, named)

### Palette — the USGS-MMI core (NEW — overrides current element palette in Acts 4/5)

**Severity choropleth (USGS ShakeMap MMI v4):**
- I    `#ffffff` (Not felt)
- II   `#bfccff` (Weak)
- III  `#80ffff` (Light)
- IV   `#7af0c8` (Light-moderate)
- V    `#ffff00` (Moderate)
- VI   `#ffc800` (Strong)
- VII  `#ff9100` (Very strong)
- VIII `#ff0000` (Severe)
- IX   `#c80000` (Violent)
- X+   `#640000` (Extreme)

**UI chrome (kept dark, Bloomberg-flavored):**
- `--bg-0` #0a0c10 (full bleed)
- `--bg-1` #11141a (panels)
- `--bg-2` #181c24 (raised)
- `--ink-0` #e7eaf2 (titles)
- `--ink-1` #b1b7c4 (body)
- `--ink-2` #6b7383 (meta)
- `--line` #232834
- Bloomberg accent `#f7a200` (ticker text only)

**Element accents (kept for hazard kind chips, INFORM-style indicators only — no longer used for severity):**
- `--el-earth` #c89758
- `--el-water` #33c0ff
- `--el-fire` #ff6a3d
- `--el-air` #9adcff
- `--el-aether` #b794f4

### Typography
- UI sans: **Inter** (already in repo). Tabular numerals everywhere.
- Monospace (ticker + memory stream): **JetBrains Mono** (free, OFL, ~50KB woff2 subset). NEW asset, 1 weight.

### Iconography — keep Phosphor only for setup briefing
- Acts 0-3: Phosphor icons OK (already in bundle).
- Act 4 ON THE MAP: **NO icons**. Buildings = colored dots. Responders = small triangles (engines) and crosses (paramedics). Hospitals/shelters/fire stations = simple stroked glyphs in white at 60% opacity, label only when zoomed.

### Topographic basemap PNGs (NEW assets)
For the wow factor without OSM (per user constraint "option B, NOT real OSM tiles"), we generate 6 stylized topographic PNGs once and ship them as static assets:
- `frontend/public/aurora/topo-la.png`
- `frontend/public/aurora/topo-valencia.png`
- `frontend/public/aurora/topo-pompeii.png`
- `frontend/public/aurora/topo-joplin.png`
- `frontend/public/aurora/topo-turkiye.png`
- `frontend/public/aurora/topo-atlantis.png`

Each ≤ 80 KB. Source: NaturalEarth or USGS National Map → grayscale topo, then duotone-tinted to `--bg-0` / `--ink-2`. Export at 2400×1440. **Generation method**: a one-shot Python script `tools/gen_topo_basemaps.py` calling `cartopy` with NaturalEarth at 1:10m, saved as PNG. Alternative if cartopy is fragile: hand-pick 6 from USGS National Map's free topo tiles, run through ImageMagick `-colorspace Gray -level 30%,80% -tint`. Budget: 0.25d. Fallback: generic dark gradient with subtle hex-grid overlay if cartopy fails on the M4 Pro.

### City flag chips (Act 1)
Use Twemoji SVG country flag glyphs inline as `data:image/svg+xml;base64,…` strings in the scenario JSON. Six countries: US (LA, Joplin), ES (Valencia), IT (Pompeii), TR (Türkiye), and a custom blue triangle for Atlantis. Twemoji is CC-BY 4.0 — attribute in methodology footer.

### Sounds — explicitly NONE
The user said "informational, not gamey." Sounds make it gamey. Default OFF, no toggle.

## Phase plan (v3 — supersedes v2 from M3 onward)

| # | Phase | Why this slot | Effort | Risk | Depends on |
|---|---|---|---|---|---|
| **N0** | **UX-cleanup-now** — strip "Refresh DB" button, "not loaded" badge, and rename map header. Already 80% done in this session; finish + commit. | unblocks user trust today | **0.1d** | low | — |
| N1 | **Asset pass** — JetBrains Mono woff2, 6 topographic PNGs, Twemoji flag SVGs, USGS-MMI palette wired to design tokens | Acts 0/1/2/4 all need the visual lexicon | **0.5d** | med (cartopy fragility) | N0 |
| N2 | **Act 0 + Act 1 (intro + city pick)** — full-bleed brand scene, 6 city cards with topo bg + flags, GSAP morph from card → map | story arc starts | **0.75d** | low | N1 |
| N3 | **Act 2 (topology + active hazards)** — schematic map with USGS-MMI tinted basemap + hazard pins + right-rail hazard list + primed empty ticker | sets up Act 3 entry | **0.5d** | low | N2 |
| N4 | **Act 3 (briefing room)** — 4-column setup panel (HAZARD / POPULATION / RESPONDERS / INTERVENTIONS), default-selected interventions, "Run baseline + with prevention" CTA | the "game setup" the user asked for, but framed as ops briefing | **0.75d** | med | N3 |
| **M3** | **Animation engine + adaptive pacing + reduce-motion stepped fallback + corridor/asymmetric heatmaps** (UNCHANGED from v2) | drives Act 4 | **1.75d** | high | N4 |
| **M5'** | **Act 4 (live sim) with USGS-MMI choropleth, INFORM strip, Gemma memory stream right rail, Bloomberg ticker bottom, time scrub control** + shared `useMCStreaming` composable | THE WOW | **1.25d** | high | M3 |
| **M6'** | **Act 5 (outcome) with side-by-side baseline vs intervention, ranked-by-cost-per-life list, methodology footer** | the prevention pitch | **0.75d** | low | M5' |
| **M7'** | **End-to-end + URL `?act=N` driver + back-nav reset + reduce-motion path + bundle audit** | recording-ready | **0.5d** | low | M6' |
| M8 | **Final E2E + recording prep** | recording is the goal | **0.25d** | low | M7' |

**Total: 7.1d. Available before recording 2026-05-12: 7 days (May 5-11) + recording day buffer = 7-8 days.** Tight but feasible.

**Cuts if we slip > 1.5×:**
- Drop topographic PNG basemaps, ship pure dark canvas with subtle hex grid (saves 0.25d).
- Drop side-by-side compare in Act 5, ship sequential with "rewind to baseline" toggle (saves 0.5d).
- Drop the Smallville memory stream right rail, leave only the Bloomberg ticker (saves 0.5d) — would hurt the credibility bet, accept only if forced.

## KPIs and quality gates (v3)

### North Star (corrected for the new shape)
**Time from cold load to user-visible "with-intervention vs baseline" delta on Act 4 ≤ 90 seconds**, on LA M7.2, 24h sim, 8 trials, Gemma 4 OFF (deterministic fallback). Hard gate. With Gemma 4 ON, target ≤ 180s.

### Input metrics (5)
| # | Metric | Today | Target | Phase |
|---|---|---|---|---|
| 1 | Acts visible per render | always 1 | 1 of 6 (0..5) | N2-M7' |
| 2 | Map FPS during Act 4 playback | n/a | ≥ 28 fps median over 30s | M3 |
| 3 | Bloomberg ticker events per Act 4 minute | 0 | ≥ 12 (mix of hazard / responder / archetype-post / counter) | M5' |
| 4 | Right-rail Gemma memory stream entries during Act 4 | 0 | ≥ 6 simultaneous, monospace, timestamped | M5' |
| 5 | Bundle gz total | 234 KB | ≤ 340 KB (added: JBM 50KB + topo PNGs are public, not bundled) | all |

### HEART (5 internal viewers, n=10 external if time)
| Dimension | Metric | Red flag |
|---|---|---|
| Happiness | Likert "could you understand what was happening?" | < 70% pick 4-5 |
| Engagement | Time spent through full Acts 0→5 | < 90s median |
| Adoption | % of demo-mode runs reaching Act 5 | < 90% |
| Task Success | Run all 6 cities back-to-back without error | < 100% |
| **Credibility (NEW)** | "Does this look like a real tool a city could deploy?" yes/no | < 80% yes |

### Per-phase exit criteria (every gate is a number)

- **N0**: zero "Refresh DB" / "not loaded" strings in `frontend/src/views/AuroraView.vue` and `ScenarioCard.vue`. All 44 frontend tests still green. Bundle ≤ 220 KB gz.
- **N1**: 6 topo PNGs ≤ 80 KB each present at `frontend/public/aurora/topo-*.png`. JetBrains Mono woff2 in `frontend/src/assets/fonts/` ≤ 60 KB. USGS-MMI palette tokens added to `frontend/src/design/tokens.css` (or wherever palette lives). New design test `tests/design/usgs-mmi-palette.test.js` asserts all 10 MMI tokens present.
- **N2**: Act 0 + Act 1 render at `?act=0` and `?act=1`. City card click triggers GSAP morph in ≤ 600ms (Performance API mark). 4 unit tests on intro/city-card.
- **N3**: Act 2 renders hazard pin at correct projected lat/lon (within 10% of bbox-projected centroid). Click pin → state changes to act=3.
- **N4**: Act 3 briefing panel renders all 4 columns from real scenario data (HAZARD reads `scenario.hazard.{kind,magnitude,duration_hours,depth_km}`; POPULATION reads `archetypes.py` distribution × scenario.districts populations; RESPONDERS reads `responder_generator.spawn_engines/spawn_paramedics` totals; INTERVENTIONS reads `intervention_dsl.PRESET_INTERVENTIONS`). 5 unit tests.
- **M3**: median FPS ≥ 28, GPU mem ≤ 200 MB, zero console warnings. Heatmap renders for radial / corridor / asymmetric.
- **M5'**: Bloomberg ticker pushes ≥ 12 events/sim-minute. Memory stream side rail shows ≥ 6 entries timestamped UTC-Zulu. Gemma decisions when LLM ON come from `decision_cache.py`, NOT from synth templates (this closes the honesty gap).
- **M6'**: side-by-side compare renders both panels, ≥ 15% RGB-red delta at end-of-playback, methodology footer cites HAZUS-MH 2.1 + Omori-Utsu + 3 named cost sources verbatim.
- **M7'**: `?act=N` deep-links work for N ∈ {0..5}. Back button restores prior act. `?reduce_motion=1` forces stepped fallback (5 quartile beats).

### Stop conditions
- Any phase exceeds 1.5× → halt + re-scope. (kept from v2)
- M3 < 28fps with SVG → switch to Pixi.js (already drafted as v2 escape hatch).
- Cartopy fails on M4 Pro by 2026-05-06 EOD → drop topo PNGs, ship dark gradient + subtle hex grid.
- Real Gemma decisions don't reach the memory stream by 2026-05-09 EOD → ship synth templates BUT label panel "Sample of Gemma archetype decisions" honestly. Don't fake this.

## The honesty problem (must address now)

Today, the AgentLogTicker shows synthetic templates, not real Gemma outputs. If we ship that under "see how Gemma simulates real people," judges who read the code will catch it. v3 fix:

1. Stream cached Gemma decisions from `decision_cache.py` to the frontend during MC runs. Add a `/api/scenario/{id}/run_mc/{run_id}/decisions` SSE or chunked endpoint. Each tick, emit the most recent cached decision keyed by archetype/district/phase.
2. Memory stream right rail shows the LIVE cached decision verbatim — `archetype`, `district_id`, `hour`, full Gemma response (post_text + reasoning if model returns it).
3. Bloomberg ticker mixes hazard events (deterministic, generated by hazard models) + responder events (deterministic until we wire dispatch) + archetype-post events (real Gemma). Each event tagged with its source so judges see what's deterministic and what's LLM.
4. Methodology footer in Act 5 names exactly which subsystems use Gemma. No fake "all agents are Gemma" framing.

## Open questions for the user (must answer before starting)

1. **City picker vs scenario picker.** Today scenarios are `la-puente-hills-m72-ref`, `valencia-dana-2024`, etc. Are we keeping 1:1 (each card = one fixed hazard) OR should one city support multiple hazards (LA could be earthquake OR fire)? Recommend KEEP 1:1 for hackathon scope.
2. **"Active hazards" framing.** v3 plan implies hazards are "running" on the topology map (Act 2). For a deterministic sim that hasn't been kicked off yet, this is theatrical — they're not running, they're scheduled. Should we frame as "scheduled scenarios" honestly OR pre-roll each scenario silently to t=2h so they appear "active" when the user lands? Recommend pre-roll t=2h.
3. **2:30 video script implications.** Current 5-act takes ~3min minimum. Do we cut Act 0 (brief intro) for the recording and start at Act 1? Or speed-run Acts 0+1 in 10s with `?seed=demo`? Recommend speed-run.
4. **Apache 2.0 vs AGPL.** Hackathon requires Apache 2.0; Aurora is AGPL-3.0 today. v2 plan deferred this. v3 deadline 2026-05-18 — must be resolved by 2026-05-15 latest. Path: dual-license our own contributions (Apache 2.0 OR AGPL at user's choice) + leave OASIS deps unchanged.
5. **Apache 2.0 + Phosphor.** Phosphor is MIT — fine. JetBrains Mono is OFL — fine. Twemoji is CC-BY 4.0 — fine with attribution in footer. NaturalEarth is public domain — fine.

## What I commit to delivering after this plan is greenlit

- Plan v3 hardened by red-team (next step after this draft).
- Asset pipeline + design tokens (N1).
- Acts 0-5 wired with URL state (N2..M7').
- Real Gemma cached-decision stream (M5' honesty fix).
- Recording-ready end-to-end at 2026-05-11 EOD.

End of v3 DRAFT.
