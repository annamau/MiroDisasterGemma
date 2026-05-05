# Aurora Experience v3 — HARDENED

**Status:** v2 of the plan. v1 (the DRAFT) had 13 red-team findings; this absorbs all of them.
**Source:** `aurora-experience-v3-DRAFT.md` + red-team review of 2026-05-05.
**Working tree:** branch `phase/aurora-sim-experience-v3`. M0 (per-district timeline), M1 (intervention costs), M2 (schematic map), M2.1 (Neo4j decoupling) shipped. Everything from N0 onward is new.
**Ask:** user greenlight before any phase starts.

---

## What v1 (DRAFT) got wrong (13 red-team findings, addressed)

### BLOCKERS (3)

**1. The decision-cache stream was technically wrong.**
v1 claimed we could stream "real cached Gemma decisions" by reading `decision_cache.py`. Cache schema is `sha256(model|system|user) → {content, model, gen_tps, eval_count, ts}` — there is **no archetype, district, hour, or phase key**. Streaming from cache would give us LLM outputs without any way to label them.
**Fix in v2 plan:** instrument `agent_runtime.py:_sample_decision_for_cell` (line ~169) with a `DecisionEvent` emitter that pushes `(archetype, district_id, hour, phase, content)` tuples into an asyncio.Queue at the moment Gemma returns. Frontend SSE reads that queue. Cache stays untouched. Reframe in plan: *"stream Gemma decisions as the runtime samples them, cache-warm or cold."*

**2. M5' was 1.25d, real cost is 2.5–3d.**
M5' bundled SSE endpoint + `useMCStreaming` composable + USGS-MMI choropleth + INFORM chip strip + JBM monospace memory rail + Bloomberg ticker + time scrub control. Each is 0.5–0.75d.
**Fix in v2 plan:** split into **M5'-A (1.5d): backend SSE + `useMCStreaming` composable + JBM memory rail + Bloomberg ticker** and **M5'-B (1.25d): MMI choropleth + INFORM strip + time scrub**. New honest total = 8.6d. Mitigation in cuts section below.

**3. "Gemma simulates real people" is an overclaim.**
`agent_runtime.py:30` is explicit: ~360 LLM calls per trial = 9 archetypes × 8 districts × 5 phase buckets. Per-cell, not per-agent. A judge reading code catches the gap in 60s.
**Fix in v2 plan:** Drop the phrase verbatim. New tagline: **"Gemma reasons over disaster-response archetypes — eyewitness, coordinator, misinformer, authority — sampled per district per phase. ~360 calls per trial, cached."** Place this in Act 0 hero copy, Act 5 methodology footer, README, and the recording voiceover script. Memory stream panel header reads "ARCHETYPE DECISION FEED" not "AGENT FEED."

### MAJOR (8)

**4. Topo PNG generation in 0.25d is a trap.** Cartopy on Apple Silicon, Atlantis bbox is in mid-Atlantic with no NaturalEarth topo, alignment with d3-geoEquirectangular non-trivial.
**Fix:** drop topo PNGs. Ship dark canvas + subtle hex-grid overlay + USGS-MMI choropleth on districts. Saves 0.5d, kills a high-risk dependency.

**5. Card → map GSAP morph in 0.75d is 1.5d realistic.** Morph between CSS-grid and SVG layouts wants GSAP Flip (premium) or custom FLIP.
**Fix:** drop the morph. Clean cross-fade (180ms). Saves 0.75d.

**6. USGS-MMI palette on floods/tornado/volcanic = misuse.** A judge trained in emergency management spots it instantly.
**Fix:** MMI only for the 3 earthquake scenarios (LA, Türkiye, Atlantis-as-quake-proxy). For Valencia: blue→navy depth ramp (NOAA SLOSH idiom). Joplin: Fujita yellow→red wind ramp. Pompeii: black→red pyroclastic-distance ramp. Each map labeled with the scale it uses. Methodology footer in Act 5 says "We use hazard-appropriate scales: USGS MMI for ground shaking, NOAA SLOSH-style depth bins for floods, Fujita-derived for tornado, pyroclastic-distance for volcanic. We do not interchangeably apply MMI to non-seismic hazards." This earns more credibility than a uniform palette.

**7. "Pre-roll silently to t=2h" is dishonest.**
**Fix:** Active hazards in Act 2 are labeled `[REF]` chips and called "Reference scenarios — click to brief and run." No fake real-time-ness.

**8. Bloomberg ticker @ ≥12 events/sim-min = 6–12 events/wall-second = unreadable flicker.**
**Fix:** new KPI is **≥4 events visible at any wall-second, average row dwell ≥600ms**. A "freeze" hover lets a judge actually read one. Memory stream right rail rotates entries on a 1.5s clock for legibility, not on every Gemma return.

**9. Reduce-motion path leaves a static dashboard.** Memory stream + Bloomberg ticker have no reduce-motion contract.
**Fix:** for reduce-motion, ticker becomes a fixed list re-rendering every 2s wall (5 quartile beats × N events). Memory stream auto-rotates entries on a clock, not on transition. KPIs still met.

**10. 6 cities in 7 days is the recording-day fail.** Pompeii/Joplin/Atlantis each demand a separate scale + QA pass. Joplin's corridor heatmap is on M3 critical path.
**Fix:** ship LA + Valencia + Türkiye for the recording. Pompeii/Joplin/Atlantis hidden behind `?show_more=1`, mentioned in voiceover ("Aurora ships with three additional reference scenarios"). Saves 1–1.5d, removes Joplin from M3 critical path.

**11. Apache 2.0 in one paragraph won't pass legal.** AGPL OASIS deps would taint the combined work.
**Fix:** TODAY (2026-05-05) — grep `backend/` for AGPL imports. If OASIS is vendored or imported, replace with MIT/BSD/Apache equivalent (or clean reimplementation) by 2026-05-12. Re-licensing our own commits requires every contributor's consent — `git log` shows only `annamau`, fine. **A 0.5d task added to N0** to do the audit.

**12. Plan over-corrects away from "game feel" the user explicitly asked for.** User said "start button, lives tracker, money tracker." Plan replied "INFORM chip strip."
**Fix:** keep the FEMA-USGS topology canvas (the *map* is air-traffic-control credibility), but give Act 3 a real **START SIMULATION** button (centered, primary color, big), and Act 4 large-number **LIVES SAVED** + **DOLLARS SAVED** tickers (centered top, tabular monospace, physically tick up during playback). The INFORM chip strip stays — but as a SECOND row below the big tickers, holding the deltas + responder utilization. Game-show-tally framing for the headline; air-traffic-control framing for everything else. They coexist.

### MINOR (1)

**13. Speed-running Acts 0+1 in 10s kills the brand opener.**
**Fix:** record a 25s cold open at design pace, jump-cut to Act 3. Reuse cold-open in social cuts. Demo seed mode (`?seed=demo`) is for development, not the recording.

---

## The winning bet (corrected)

**Aurora is a Prevention Lab.** The page opens to a dark schematic of LA painted with the official USGS-MMI palette. The user picks interventions and watches a live multi-agent sim — Gemma reasoning over archetypes per district per phase, narrated in a Bloomberg-style ticker — play out the disaster minute by minute. Then comes the actual product moment: **Act 5 stays open as a lab.** The user toggles a different intervention combo, hits RUN, and the same map replays with a new outcome. Each run becomes a saved column in a comparison strip. Within 60 seconds the user has 4 saved scenarios side by side: baseline, +retrofit, +retrofit +earlier evac, +retrofit +earlier evac +prebunk. Each column shows lives lost, dollars lost, and the delta vs baseline. The ranked catalog at the bottom updates after every run with $/life-saved sorted ascending. **The pitch isn't "we predicted the disaster." The pitch is "you can A/B-test civic decisions before they cost anyone."**

Visually: FEMA + USGS + Bloomberg desk + air traffic control + game-show tally for the headline counters + scientific-poster discipline for the comparison strip. No cartoon icons, no speech bubbles, no celebratory hero KPI. Judges should feel they are watching a decision-support console real cities could deploy on Monday — and crucially, watch the user *use* it three times in a row and learn something each time.

---

## The 6-act story (v3 final)

Each act is `?act=N`. Back-button restores prior act. **3-city demo path:** LA → Valencia → Türkiye. Pompeii/Joplin/Atlantis behind `?show_more=1`.

### Act 0 — Brief (10s on demo, 25s on cold record)
Full-bleed dark scene. Wordmark "Aurora" + corrected tagline: "City resilience, simulated. Gemma reasons over archetypes per district per phase. Hazard physics from HAZUS-MH 2.1." USGS-MMI scale stripe along the bottom edge for the earthquake palette. One CTA: "Begin briefing →".

### Act 1 — City selection (15s)
Three city cards (LA, Valencia, Türkiye) in a horizontal row. Each card: city name, country flag chip, population, hazard tag chip in hazard-appropriate color (earth/water/earth). Background: dark gradient + subtle hex grid (no topo PNG). Hover: card lifts 1px, glow in element color. Click: cross-fade (180ms) to topology view. `?show_more=1` reveals the other 3 cards in a second row, each with a `[REF]` chip and "physics-proxy" tooltip.

### Act 2 — Topology + reference scenarios (15s)
Schematic map fills the canvas. Hazard pins at epicenters with element color, labeled `[REF]`. Click pin → Act 3. Right rail "Reference scenarios" lists pin name, magnitude, expected duration, "Brief →". Bottom: amber Bloomberg ticker primed but empty — `AURORA BRIEFING ROOM ONLINE · STANDING BY`.

### Act 3 — Briefing (the game-setup screen, 30s)
Map dims to 30%. Foreground: 4-column briefing panel.
- **HAZARD** — kind, magnitude, depth, duration. Reads from `scenario.hazard.{kind,magnitude,duration_hours,depth_km}`. For non-seismic scenarios, swap "depth" → "intensity proxy" with the hazard-appropriate metric.
- **POPULATION** — 9 archetype tiles with count, posting rate, language mix from `archetypes.py` × `scenario.districts`.
- **RESPONDERS** — engines, paramedics, hospital beds, shelter capacity from `responder_generator.py`.
- **INTERVENTIONS** — toggle chips with $/life-saved estimates from `intervention_dsl.PRESET_INTERVENTIONS`. Default selection: top 3 most-impactful.
Two buttons: **"START SIMULATION ▶"** (centered, primary, big — the game-show button) runs **with-prevention vs baseline side-by-side** by default. Above it, optional "Use Gemma 4 (slow, real LLM calls)" toggle, OFF by default.

### Act 4 — Live simulation (60–90s, THE WOW)
- **Map full-bleed.** Hazard-appropriate choropleth painted on districts at the current simulated minute. Building dots fade their color from W1/C1L/PC1 native to severity-red as damage accumulates.
- **Top center, ticker scale**: **LIVES SAVED · 696** big tabular numerals (game-show level), **DOLLARS SAVED · $2.5B** next to it. Subline: "vs no-intervention baseline".
- **Top secondary INFORM strip**: "DEATHS · 412 · -63% vs baseline" "RESPONDERS DEPLOYED · 18/24" "POSTS · 1.2k authority · 4.8k civilian · 380 misinfo" "HOSPITAL LOAD · 78%".
- **Right rail (Archetype Decision Feed)**: monospace, last 6 Gemma decisions, each `[hh:mm UTC] ARCHETYPE-MISINFORMER · LA-D03 · phase=acute · "boil water order is fake" — followers 1.2k`. Header reads "ARCHETYPE DECISION FEED · GEMMA 4 e2b cached". On reduce-motion, rotates entries on 1.5s clock.
- **Bottom Bloomberg ticker**: amber-on-black, ALL CAPS, monospace, ≥4 events visible at all times, average row dwell ≥600ms. Each event tagged `[hzd]`, `[rsp]`, `[gemma]`, `[counter]`. Hover freezes the row.
- **Time control**: horizontal slider hour 0 → duration_hours, play/pause/scrub. Pacing: `wall_seconds_per_sim_hour = max(0.4, min(2.0, 24/duration_hours))`.

### Act 5 — The Prevention Lab (45-90s, the *real* pitch)

Act 5 is **not a final report**. It's an interactive lab where the user A/B-tests civic decisions and watches the yield. The page does not navigate forward — it stays here, and re-runs play **in place**. Each run becomes a saved column. This is the moment that proves the product: "Aurora lets you test prevention before it costs anyone."

**Layout (3 horizontal regions):**

1. **Top: Comparison strip** — one column per saved run, ordered left → right by run order. Each column has:
   - Run label (auto-generated, editable: "Baseline", "Run 2 · +retrofit D03", "Run 3 · +retrofit +earlier evac", ...)
   - **LIVES LOST** big number, with a `Δ vs baseline` chip below in green (saved) or red (worse)
   - **DOLLARS LOST** big number, same Δ treatment
   - Mini-map thumb (200×120px) showing end-of-playback severity choropleth
   - Active intervention chips (the ones toggled ON for this run)
   - "Replay this run" link → re-plays Act 4 against the cached trial data, no re-compute

2. **Middle: Re-run console** — a compact horizontal bar persisting at all times:
   - The intervention toggle chips from Act 3, **live-editable here**. Each toggle is colored by family (preposition / evac timing / retrofit / prebunk).
   - **N trials slider** (default 8, max 32) — visible because honesty: more trials = tighter CI.
   - **"RUN THIS COMBO ▶"** primary button — when clicked, the map below transitions back to Act 4 playback (in-place, no nav) and the Bloomberg ticker comes alive again. When done, a new column lands at the right of the comparison strip.
   - Diff hint: when the user changes a toggle, a small "would yield ≈ ±X lives" estimate appears next to RUN, computed from the linear sum of selected interventions' baseline deltas (acknowledged-non-additive in tooltip — "estimate only; run to confirm").

3. **Bottom: Ranked-by-yield list (the intervention catalog)** — every intervention available, ranked ascending by `cost_per_life_saved_usd` from the *most recent* run. Each row:
   - Intervention name + family + element color
   - $/life-saved as the primary number
   - 90% CI on lives_saved as a horizontal bar
   - Citation chip (FEMA BCA, Roozenbeek 2022, MMC 2005, etc.) — click to expand methodology
   - "Add to next run" toggle that mirrors the re-run console above

**Behavior contract:**
- The first time the user lands on Act 5, two columns are already populated: **Baseline** and **With prevention** (the side-by-side from the initial Act 4 run). User sees them auto-compared.
- Up to **6 saved columns** in the comparison strip. Older runs are scrollable horizontally if more are saved. A "🗑" on each column removes it.
- The map area below the comparison strip plays Act 4 for whatever run is "selected" (clicked column header glows).
- "Pick another city" exits to Act 1 (loses runs). "Reset lab" clears all but baseline. Both are buried in a meta menu — the headline path is **stay in the lab and keep iterating**.
- URL state encodes the saved run combos so a recording can deep-link `?act=5&runs=baseline,prep_d03+evac_30,retrofit_d03_w1` for reproducibility.

**Methodology footer** (sticky bottom, always visible in Act 5): one paragraph naming HAZUS-MH 2.1, Omori-Utsu, archetype-level Gemma sampling (~360 calls/trial), FEMA BCA + Roozenbeek 2022 + MMC 2005 + FEMA P-58/ATC-33 cost sources. Plus a one-line caveat: "Aurora estimates are illustrative for hackathon demonstration; not authoritative for pilot use."

---

## Asset list (concrete)

### Palette
**Severity choropleths (NEW, per-hazard):**
- **Earthquake (USGS MMI):** `#ffffff`, `#bfccff`, `#80ffff`, `#7af0c8`, `#ffff00`, `#ffc800`, `#ff9100`, `#ff0000`, `#c80000`, `#640000` (I → X+).
- **Flood (NOAA SLOSH-derived):** depth ramp `#dbeeff` → `#3387c8` → `#0d3d6e` → `#06203d` (1ft → 21ft).
- **Tornado (Fujita-derived):** `#fff5cc` → `#f7c84a` → `#ee7a2c` → `#c43a16` → `#7d1a05` (EF1 → EF5).
- **Volcanic (pyroclastic distance):** `#1a1a1a` → `#5a1f0c` → `#a23919` → `#e85f1f` → `#ffb061` (near → far).

**UI chrome:** unchanged from v1 (Bloomberg-flavored dark).
**Element accents:** kept for hazard tag chips only.
**Bloomberg amber:** `#f7a200` for ticker text.

### Typography
Inter (already in repo). **JetBrains Mono** woff2 added (1 weight, ~50KB).

### Iconography
Phosphor for chrome/setup. Map: NO icons. Buildings = colored dots. Responders = small triangles (engines), crosses (paramedics). Hospitals/shelters = simple stroked glyphs at 60% opacity, label only on hover.

### Static assets shipped
- `frontend/src/assets/fonts/JetBrainsMono-subset.woff2` (~50KB)
- `frontend/public/aurora/twemoji/{us,es,tr}.svg` (3 country flags, ~3KB each)
- `frontend/public/aurora/{ref}/{us,es,tr,it,my,xa}.svg` for `?show_more=1` cards (3 more flags)

NO topo PNGs. NO sounds.

---

## Phase plan v3 final

| # | Phase | Effort | Risk | Depends |
|---|---|---|---|---|
| **N0** | UX cleanup (kill "Refresh DB", "not loaded", rename map header) **+ AGPL audit + Apache 2.0 path decided** | **0.6d** | low | — |
| N1 | Asset pass: JBM woff2, 3 + 3 flag SVGs, 4 hazard palettes wired to design tokens | **0.4d** | low | N0 |
| N2 | Act 0 (brand) + Act 1 (city pick, cross-fade not morph) | **0.6d** | low | N1 |
| N3 | Act 2 (topology + `[REF]` hazard pins + ticker stub) | **0.4d** | low | N2 |
| N4 | Act 3 (briefing, 4-col, START SIMULATION button, default-prevention) | **0.7d** | med | N3 |
| **M3** | Animation engine + adaptive pacing + reduce-motion stepped fallback + radial heatmap (drop corridor/asymmetric — Joplin is `?show_more`) | **1.25d** | high | N4 |
| **M5'-A** | Backend `DecisionEvent` emitter in `_sample_decision_for_cell`, SSE endpoint, `useMCStreaming` composable, JBM memory rail, Bloomberg ticker (with hover-freeze + reduce-motion path) | **1.5d** | high | M3 |
| **M5'-B** | MMI/SLOSH/Fujita/pyroclastic choropleth, INFORM strip, BIG LIVES + DOLLARS counters, time scrub | **1.25d** | high | M5'-A |
| **M6'** | Act 5 **Prevention Lab**: comparison strip (≤6 columns), persistent re-run console, ranked-by-yield catalog, in-place Act-4-replay on column click, URL `?runs=` state | **1.1d** | med | M5'-B |
| **M7'** | E2E + URL `?act=N` driver + back-nav reset + reduce-motion path + bundle audit | **0.5d** | low | M6' |
| M8 | Recording prep (3-city demo: LA → Valencia → Türkiye) | **0.25d** | low | M7' |

**Total: 8.55d. Available 2026-05-05 → 2026-05-12 (8 days) + recording day = 8-9 days.** (Recording shifted to 2026-05-12 to absorb the Act 5 lab uplift; hackathon submission 2026-05-18 unchanged.)

**Mitigation if any phase exceeds 1.5×:**
- M5'-B drops time scrub control (saves 0.25d) — playback only auto-plays.
- M3 drops radial-heatmap pulse, only animates building color shifts (saves 0.25d).
- N3 drops the right-rail "Reference scenarios" list, hazard pins suffice (saves 0.15d).
- M6' drops mini-map thumbs in the comparison strip, replaces with a 1-line sparkline of cumulative deaths (saves 0.3d). Acceptable: thumbs are nice-to-have, sparklines still tell the story.

**Stop conditions:**
- Any phase > 1.5× → halt, re-scope.
- AGPL audit reveals OASIS taint that takes > 1d to remove → halt the Apache 2.0 commit, ship under AGPL, accept hackathon may reject; user notified immediately on 2026-05-05.
- M3 < 28fps → drop heatmap pulse, only color-shift dots.
- DecisionEvent SSE not delivering by 2026-05-08 EOD → fall back to "Bloomberg ticker only" (skip memory rail), with honest copy in Act 5 footer.

---

## KPIs and quality gates v3 final

### North Star
**Time from cold load to user-visible LIVES-SAVED + DOLLARS-SAVED reveal in Act 4 ≤ 90s** on LA M7.2, 24h sim, 8 trials, Gemma 4 OFF (deterministic). With Gemma 4 ON, ≤ 180s.

### Input metrics
| # | Metric | Target | Phase |
|---|---|---|---|
| 1 | Acts visible per render | exactly 1 of {0..5} | N2-M7' |
| 2 | Map FPS during Act 4 | ≥ 28 fps median over 30s | M3 |
| 3 | Bloomberg ticker readability | ≥ 4 events visible at any wall-second; row dwell ≥ 600ms | M5'-A |
| 4 | Archetype Decision Feed entries | ≥ 6, monospace, UTC-timestamped, archetype + district labeled | M5'-A |
| 5 | Bundle gz total | ≤ 320 KB | all |

### HEART
| Dimension | Metric | Red flag |
|---|---|---|
| Happiness | Likert "could you understand?" n=10 | < 70% pick 4-5 |
| Engagement | Time on page through Acts 0→5 | < 90s median, σ ≤ 30s |
| Adoption | % demo runs reaching Act 5 | < 90% |
| Task Success | 3-city walkthrough w/o error | 100% |
| Credibility | "Real tool a city could deploy?" yes/no | < 80% yes |

### Per-phase exits (each is a number)
- **N0**: 0 "Refresh DB" / "not loaded" strings in Aurora components. AGPL audit complete: written assessment "OASIS tainted" or "OASIS clean / Apache 2.0 dual-license OK". Bundle ≤ 220 KB.
- **N1**: 4 hazard palette token sets present in `frontend/src/design/tokens.css`. JBM woff2 ≤ 60 KB. Test asserts each palette has ≥ 5 calibrated stops.
- **N2**: `?act=0` and `?act=1` render correctly. Cross-fade ≤ 200ms. 4 unit tests on intro/city-card.
- **N3**: hazard pin centroid within 10% of bbox-projected lat/lon. Click pin → `?act=3`. 3 unit tests.
- **N4**: 4-column briefing reads from real scenario data. START SIMULATION button visible, primary color, ≥ 64px tall. 5 unit tests.
- **M3**: median FPS ≥ 28, GPU mem ≤ 200 MB, zero console warnings. Radial heatmap renders.
- **M5'-A**: SSE endpoint pushes ≥ 1 DecisionEvent per archetype-cell. Frontend ticker shows ≥ 4 events visible, dwell ≥ 600ms. Memory rail shows ≥ 6 entries. Reduce-motion: rail rotates on 1.5s clock, ticker becomes fixed list every 2s.
- **M5'-B**: hazard-appropriate choropleth renders for earthquake (MMI), flood (SLOSH-style), tornado (Fujita) — 3 of 4. LIVES + DOLLARS counters tick during playback (verified by Performance API mark every 200ms). 4 unit tests.
- **M6'**: comparison strip seeded with 2 columns (Baseline, With-prevention) at first land. User can run a 3rd combo from the persistent re-run console; new column appears at the right ≤ 1s after MC completes. Up to 6 columns. ≥ 15% RGB-red delta on at least one column pair at end-of-playback. Methodology footer cites HAZUS-MH 2.1 + Omori-Utsu + 3 cost sources + archetype-level Gemma framing verbatim. URL `?runs=` round-trips: paste a `?runs=` URL and the lab restores those columns. 5 unit tests on the lab.
- **M7'**: `?act=N` deep-links work for N ∈ {0..5}. Back button restores prior act. `?reduce_motion=1` forces stepped fallback.
- **M8**: 3-city walkthrough recorded in ≤ 2:30 wall. Voiceover script names "archetype-level Gemma sampling" verbatim.

---

## Open questions for the user (must answer before N0 starts)

1. **3-city recording cut OK?** Plan ships LA + Valencia + Türkiye for the 2:30 recording. Pompeii / Joplin / Atlantis behind `?show_more=1`, mentioned in voiceover. ☐ Approve / ☐ Cut to LA only / ☐ Insist on all 6.

2. **AGPL → Apache 2.0 path.** N0 includes a 0.5d AGPL audit. If OASIS code is in the tree as AGPL-3.0 imports/vendoring and removal takes > 1d, plan halts the Apache 2.0 commitment and notifies you. ☐ Approve halt-and-notify / ☐ Insist on Apache 2.0 even if it costs 2d.

3. **Tagline correction.** v3 drops "Gemma simulates real people" verbatim and replaces with "Gemma reasons over archetypes per district per phase." ☐ Approve / ☐ Push back.

4. **Per-hazard palettes (4 of them).** Plan ships USGS-MMI for earthquakes only, NOAA-SLOSH-style for flood, Fujita for tornado, pyroclastic for volcanic. ☐ Approve / ☐ Pick uniform palette and accept credibility hit.

5. **No topo PNG basemaps.** v3 ships dark canvas + hex grid. ☐ Approve / ☐ Insist on PNGs (adds 0.5–1d).

6. **No card→map morph.** v3 ships cross-fade. ☐ Approve / ☐ Insist on morph (adds 0.75d).

7. **Game-show tally + air-traffic-control hybrid.** Big LIVES + DOLLARS counters above the map (game-show), INFORM chip strip below (air-traffic), monospace ticker at bottom (Bloomberg). ☐ Approve hybrid / ☐ Pick one register only.

8. **Prevention Lab is the headline.** Act 5 stays open as a comparison lab — re-run combos in place, up to 6 columns, ranked catalog updates per run. Recording script: 2 baseline + with-prevention reveal at 0:30, then user re-runs 2 alternative combos live in front of the camera before final voiceover. Adds ~25s to the recording (2:55 total — was 2:30; hackathon limit is 3:00, still OK). ☐ Approve / ☐ Cap at 2 columns and skip live re-runs / ☐ Different shape.

9. **Recording day shift.** v2 was 2026-05-12; v3 keeps that day for the lab uplift, with hackathon submission 2026-05-18 unchanged. ☐ Approve.

---

## Ready-to-start step (after greenlight)

**N0** — half a day:
1. Strip `loaded_in_db` references in `ScenarioCard.vue` ✅ (already done in this session, not committed)
2. Strip "Refresh DB" button ✅ (already done in this session, not committed)
3. Commit those.
4. AGPL audit: `grep -r "AGPL\|GNU Affero" backend/` and check vendored deps. Write a 1-page assessment doc.
5. Decide Apache 2.0 path or escalate to user.

That's the first commit. If user greenlights, I proceed to N1 immediately after.

End of v3 hardened plan.
