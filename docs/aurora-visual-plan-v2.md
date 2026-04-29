# Aurora Visual Plan v2 — APPROVED for execution

**Date**: 2026-04-29
**Status**: Locked. Executes via `phases-execution`. Companion: [aurora-moodboard.md](aurora-moodboard.md).
**Goal**: Turn `/aurora` from a functional spreadsheet into a 45-second wow demo for Gemma 4 hackathon judges (deadline May 18 2026), without crossing into mystic/gamified territory that hurts B2G validator credibility.

---

## Design north stars (locked from moodboard)

- **Aesthetic anchor**: Linear (restraint) × Our World in Data (editorial dataviz) × FEMA EOC dashboards (credibility). NOT Awwwards portfolio sites.
- **Single font family**: Inter Display (headings) + Inter (body) — `@fontsource-variable/inter` only.
- **Phosphor `bold` weight**, no duotone (lighter, more Linear-coded).
- **Type scale, 4px grid**: 12 / 14 / 16 / 20 / 24 / 32 / 48 / 64.
- **Page retints by hazard scenario** (single accent at a time, not 5 simultaneously).
- **5-element CSS tokens**, but user-facing labels say `Population` (not "Aether"), `Hazard`, `Infrastructure`, etc.
- **Motion earns its place**: 5 moments only. SplitText hero, hover, run-button states, MC streaming progress, post-MC reveal. NO ScrollTrigger pinning, NO Flip, NO Three.js, NO custom cursor, NO glassmorphism.

---

## Element palette (verified WCAG AA on `--bg-1: #10131F`)

| Token | Hex | Contrast | Used for |
|---|---|---|---|
| `--el-fire` | `#F25C1F` | 5.0:1 ✓ | Fire / wildfire scenario, hazard active |
| `--el-water` | `#33C0FF` | 8.5:1 ✓ | Flood scenario, evac-timing intervention |
| `--el-earth` | `#B68A5F` | 4.7:1 ✓ | Earthquake scenario, retrofit (icons + ≥24px only) |
| `--el-air` | `#9FE0CF` | 9.6:1 ✓ | Hurricane scenario, comms cascade |
| `--el-aether` | `#C580F0` | 6.0:1 ✓ | Population / social agents (label = "Population") |

Surface neutrals:
```
--bg-0: #080A12   (page)
--bg-1: #10131F   (card)
--bg-2: #1A1E2E   (input/hover)
--ink-0: #F5F7FB  (17.4:1 — primary text)
--ink-1: #9CA3B5  (6.5:1 — secondary)
--ink-2: #5A6075  (muted)
--line: #252A3D   (1px borders, ~6% white)
--line-glow: rgba(197, 128, 240, 0.18)  (active borders)
```

Hover/active states use the **glow** variants (Fire `#FF7A47`, Water `#33C0FF` already glow, etc.).

---

## Bundle budget (gz, prod build, after per-icon tree-shake + latin-only subset)

| Asset | gz |
|---|---|
| gsap core | 24 kB |
| ScrollTrigger | 12 kB |
| SplitText | 5 kB |
| Phosphor — barrel import (verified P-V0: no subpath exports in v2.2.1) | 25 kB est. with tree-shaking on Vite prod build |
| Inter Variable (latin only, both Display + regular axes) | 35 kB |
| **Uplift total** | **~101 kB** |
| Existing baseline | ~140 kB |
| **Projected total** | **≤ 295 kB ✓** (budget cap 320 kB) |

**P-V0 finding (2026-04-29)**: `@phosphor-icons/vue@2.2.1` has no per-icon subpath exports — only `.` and `./compact`. Use `import { PhFlame } from '@phosphor-icons/vue'` (Ph-prefixed). Tree-shaking still works because Vite analyzes named imports, but bundle is ~15 kB heavier than v1's optimistic estimate. Still within total budget.

---

## Component plan

```
frontend/src/design/
  tokens.css            NEW   palette + neutrals + scale + spacing
  globals.css           NEW   reset + body + scrollbar + focus-visible
  motion.js             NEW   gsap setup, EASES, DUR
  useGsap.js            NEW   gsap.context() composable for cleanup
  fonts.css             NEW   @fontsource-variable/inter latin subset only

frontend/src/components/aurora/
  ElementBadge.vue      NEW   icon + element-tinted halo, props: element, icon, size
  ScenarioCard.vue      NEW   replaces lines 16-29 of AuroraView
  InterventionChip.vue  NEW   replaces lines 47-56
  RunButton.vue         NEW   3 states: idle (breathing), running (notch), done (flash)
  MCProgressPanel.vue   NEW   live per-arm progress bars during MC compute
  AgentLogTicker.vue    NEW   sub-component of MCProgressPanel — 3-line scroll
  HeroNumber.vue        NEW   CountUp 0 → lives_saved, 64px, tabular-nums
  DeltaCard.vue         NEW   per-intervention outcome card
  ComparatorTable.vue   NEW   width-tween bars, replaces existing <table>
  CumulativeChart.vue   NEW   d3 + GSAP path-draw via stroke-dasharray

frontend/src/views/AuroraView.vue   REWRITE   compose all of above, ~150 lines

backend/app/aurora/monte_carlo.py   EDIT    add progress_callback param
backend/app/api/scenario.py         EDIT    add /run_mc/<run_id>/progress GET
```

---

## Phase plan + per-phase quality gates

### Dependency graph

```
P-V0 (install spike, throwaway branch)
  ↓
P-V1 (foundation: tokens, motion.js, useGsap, fonts)
  ↓
P-V2 (atomic components: ElementBadge, ScenarioCard, InterventionChip, RunButton)  [parallel-internal but one PR]
  ↓
P-V3 (backend streaming + MCProgressPanel + AgentLogTicker)
  ↓
P-V4 (result reveal: HeroNumber, DeltaCard, ComparatorTable, CumulativeChart)
  ↓
P-V5 (polish: reduced-motion, mobile, a11y, demo-seed, video-record prep)
```

All phases serialize. P-V2 is the only one with multiple components but they're tightly coupled visually so they ship in one PR.

---

### **P-V0 — Install spike** (1h budget)

**Spec.** On a throwaway branch off `claude/silly-albattani-912537`, run:
```bash
cd frontend
npm i gsap@^3.13.0 @phosphor-icons/vue@^2.2.1 @fontsource-variable/inter@^5.1.0
npm run dev
```
Verify Vite boots. Verify Vue 3.5.24 + Vite 7.2.4 has no peer-dep conflicts. Verify per-icon import works:
```js
import { Flame } from '@phosphor-icons/vue/Flame'
```
Verify SplitText is included in the free GSAP 3.13+ npm package (no Club-only gating). If any of these fail, halt and report — do NOT proceed to P-V1.

**Files touched**: `frontend/package.json`, `frontend/package-lock.json`. Branch is throwaway — DO NOT merge to main.

**Gates** (all must pass):
- ✅ `npm i` exits 0 with no peer-dep warnings about Vue 3.5
- ✅ `npm run dev` boots, http://localhost:3000 returns 200
- ✅ Per-icon import compiles (Vite has no "module not found")
- ✅ `node -e "require('gsap/SplitText')"` resolves OR `import { SplitText } from 'gsap/SplitText'` Vite-compiles without 401/Club gate

**Falsifying test**: Create `frontend/src/spike-test.vue` that imports `Flame` and `SplitText` and renders. If it doesn't render, P-V0 fails.

---

### **P-V1 — Foundation** (2h budget) — depends on P-V0

**Spec.** Create the design system foundation:

1. `frontend/src/design/tokens.css` — full element palette + neutrals + 4px-grid spacing (`--sp-1: 4px` ... `--sp-16: 64px`) + type scale (`--fz-12` ... `--fz-64`). Colors verified above.
2. `frontend/src/design/globals.css` — CSS reset (modern, not Eric Meyer), `html, body` styles, custom scrollbar (`scrollbar-width: thin; scrollbar-color: var(--bg-2) var(--bg-0)`), `:focus-visible { outline: 2px solid var(--el-aether); outline-offset: 2px; }`.
3. `frontend/src/design/fonts.css` — `@import '@fontsource-variable/inter/standard.css';` (latin only, both Display and regular axes via the `wghtOpsz` variant).
4. `frontend/src/design/motion.js` — register GSAP + ScrollTrigger + SplitText, export `EASES = { out: 'power3.out', inOut: 'power2.inOut', snappy: 'expo.out', bounce: 'back.out(1.4)' }` and `DUR = { fast: 0.18, base: 0.42, slow: 0.9, hero: 1.6 }`.
5. `frontend/src/design/useGsap.js` — Vue 3 composable returning `{ ctx, gsap }`. Wraps `gsap.context()` keyed to a ref. On `onUnmounted`, calls `ctx.revert()`. Required reading: https://gsap.com/docs/v3/GSAP/gsap.context()
6. `frontend/src/main.js` — import the four design files in this order: fonts, tokens, globals, motion.

**Files touched**: 5 new files, 1 edit (main.js). ~200 LOC total.

**Gates**:
- ✅ Page loads with new fonts (Inter Display visible at body)
- ✅ Element CSS vars accessible from any component (`getComputedStyle(document.body).getPropertyValue('--el-fire')` returns `#F25C1F`)
- ✅ All 5 element colors hit AA on `--bg-1` — verify with `wcag-contrast` lib in a unit test
- ✅ No FOUC visible (font-display: swap configured)
- ✅ Bundle delta from baseline ≤ 50 kB gz (fonts + setup only, no GSAP usage yet — but GSAP is installed so it's in node_modules)

**Falsifying test**: `frontend/tests/tokens.test.js` (new): assert each CSS var resolves to the expected hex AND the fire/water/earth/air/aether contrast ratios on `#10131F` clear 4.5:1.

---

### **P-V2 — Atomic components** (4h budget) — depends on P-V1

**Spec.** Build 4 atomic Vue 3 SFC components in `frontend/src/components/aurora/`:

#### 2.1 `ElementBadge.vue`
- Props: `element: 'fire'|'water'|'earth'|'air'|'aether'`, `icon: string` (Phosphor name), `size: 16|20|24|32|48`
- Renders the named Phosphor icon as `Ph{Name}` (e.g. `PhFlame`) imported from `@phosphor-icons/vue` (barrel — no subpath exports). Tinted via `color: var(--el-${element})` plus a soft halo via `filter: drop-shadow(0 0 8px var(--el-${element}))`
- Used by: ScenarioCard, InterventionChip, DeltaCard

#### 2.2 `ScenarioCard.vue`
- Props: `scenario: { scenario_id, label, sub, hazard_params, element, icon, loaded_in_db }`, `selected: boolean`
- Emits `select`
- Layout: ElementBadge left (size 48), title + sub right, hazard params row at bottom (small caps, `tabular-nums`)
- Hover: CSS-only `box-shadow: 0 0 0 1px var(--el-{element}-glow), 0 0 40px -10px var(--el-{element}-glow)`, `transform: translateY(-1px)`
- Active state: `border: 1px solid var(--el-{element}-glow)`, glow halo permanent
- Replaces lines 16–29 of [frontend/src/views/AuroraView.vue:16](frontend/src/views/AuroraView.vue:16)

#### 2.3 `InterventionChip.vue`
- Props: `intervention: { intervention_id, label, kind, element }`, `selected: boolean`, `disabled: boolean`
- Emits `toggle`
- Compact pill: ElementBadge left (size 16), label, optional info-icon right (tooltip = `kind`)
- Replaces lines 47–56 of [frontend/src/views/AuroraView.vue:47](frontend/src/views/AuroraView.vue:47)

#### 2.4 `RunButton.vue`
- Props: `state: 'idle'|'running'|'done'`, `disabled: boolean`, `label: string`
- Emits `click`
- States:
  - `idle`: subtle 4s breathing scale 1→1.012→1 (CSS `@keyframes`, no GSAP)
  - `running`: rotating `CircleNotch` icon left of label, label = "Running…", width auto-adapts
  - `done`: 800ms color flash via `gsap.fromTo(this.$el, { backgroundColor: 'var(--el-aether)' }, { backgroundColor: 'var(--bg-2)', duration: 0.8 })`
- Hover: scale 1.01, glow shadow

**Files touched**: 4 new SFC files. ~600 LOC total. NO modifications to AuroraView yet — that comes in P-V4.

**Gates**:
- ✅ Each component renders standalone in dev with all element variants (visual check via Chrome MCP screenshots)
- ✅ Hover states do not cause layout shift (verify with DevTools "show layout shift regions")
- ✅ Keyboard tab order works on ScenarioCard + InterventionChip (each is `role="button"` or wraps an `<input>`)
- ✅ Reduced-motion: when `(prefers-reduced-motion: reduce)`, RunButton breathing stops, hover scale = 1.0 (no transform)
- ✅ Bundle delta ≤ 30 kB gz (Phosphor 12 icons used = ~10 kB, GSAP unused yet but webpack tree-shakes only what's imported)

**Falsifying test**: `frontend/tests/components/element-badge.test.js`: render `<ElementBadge element="fire" icon="Flame" size="48" />`, assert the rendered SVG has `color: rgb(242, 92, 31)` (= #F25C1F).

---

### **P-V3 — MC streaming progress** (4h budget) — depends on P-V2

**Spec.** Add a live progress UI that fills the 20–60s MC compute window so judges don't think the demo crashed.

#### 3.1 Backend streaming — [backend/app/aurora/monte_carlo.py](backend/app/aurora/monte_carlo.py)
- Add `progress_callback: Callable[[str, int, int, float], None] | None = None` to `_run_intervention_trials()` and `run_monte_carlo()`
- After each trial completes: `progress_callback(arm_id, trials_done, trials_total, lives_saved_running_mean)` if callback provided
- No callback = current behavior (silent). 100% backwards compatible.

#### 3.2 Backend route — [backend/app/api/scenario.py](backend/app/api/scenario.py)
- Add module-level dict `_MC_PROGRESS: dict[str, dict[str, dict]] = {}` (in-memory, fine for hackathon)
- `POST /scenario/<id>/run_mc` already exists. Modify to: generate a `run_id = uuid.uuid4().hex[:8]`, return it immediately as `{run_id, status: 'started'}`, kick off MC in a background thread (use `threading.Thread(target=…, daemon=True)`), with the thread's progress_callback writing into `_MC_PROGRESS[run_id][arm_id] = {trials_done, trials_total, running_mean}`. When done, write `_MC_PROGRESS[run_id]['_result'] = full_result_dict`.
- Add `GET /scenario/run_mc/<run_id>/progress` returning current `_MC_PROGRESS[run_id]` or 404 if not found
- Add `GET /scenario/run_mc/<run_id>/result` returning `_MC_PROGRESS[run_id]['_result']` if present, or 202 if still running

⚠️ **Threading caveat**: Flask dev server is single-threaded by default. Add `app.run(threaded=True)` if not already set. Verify in [backend/run.py](backend/run.py).

#### 3.3 Frontend `MCProgressPanel.vue`
- Props: `runId: string|null`, `arms: Array<{intervention_id, element, label}>`
- On mount + every 500ms: poll `GET /scenario/run_mc/<runId>/progress`
- Renders one row per arm: ElementBadge, label, horizontal bar (width tween via GSAP `to` with `width: ${(done/total)*100}%`), trial counter `12/30`, running-mean live number
- When all arms hit `trials_done === trials_total`: fetch `/result`, emit `done` with the full result payload
- Bar color = `var(--el-{element})`

#### 3.4 Frontend `AgentLogTicker.vue` (sub-component)
- Props: `runId: string|null`
- Same polling endpoint adds a `recent_decisions: [{archetype, hour, post_text, timestamp}]` array (cap at last 5)
- Backend modification: in [backend/app/aurora/decision_cache.py](backend/app/aurora/decision_cache.py), expose a `recent_decisions` accessor; thread it through to `_MC_PROGRESS[run_id]`
- Renders 3 visible lines, scroll-up animation when new entry arrives. Format: `[Eyewitness · LA-D-DOWNTOWN · t=14:32] "lights flickering, no comms"`

#### 3.5 Frontend `frontend/src/api/aurora.js` updates
- Add `runMC` to NOT block: returns `{run_id}` immediately
- Add `getMCProgress(run_id)` and `getMCResult(run_id)`

**Files touched**: 2 backend edits, 2 new components, 1 API client edit. Backend: ~120 LOC. Frontend: ~400 LOC.

**Gates**:
- ✅ Streaming endpoint returns valid JSON for a 30-trial MC; trials_done is monotonically non-decreasing
- ✅ MCProgressPanel updates ≥ once per second (visible movement)
- ✅ Backend MC runtime overhead from progress_callback ≤ 5% (measure: same N trials with vs without callback)
- ✅ Frame rate during streaming ≥ 30 fps (Chrome perf panel during a 30-trial MC)
- ✅ AgentLogTicker shows ≥ 3 distinct decisions during a 30-trial run
- ✅ When MC completes, `done` event fires with the full result payload (compatible with current AuroraView result-rendering)

**Falsifying test**: `backend/tests/test_streaming.py` — spawn an MC with 5 trials, poll progress every 100ms, assert at least 3 distinct progress snapshots are observed before `_result` appears.

---

### **P-V4 — Result reveal animations** (4h budget) — depends on P-V3

**Spec.** Build the post-MC reveal — the wow moment that lands on top of the streaming progress.

#### 4.1 `HeroNumber.vue`
- Props: `value: number`, `label: string`, `ci: { lo, hi }`, `unit: string`
- Renders the hero number at `--fz-64` with `font-feature-settings: "tnum" 1, "ss01" 1`
- Below: small label + `90% CI [lo, hi]` in `--ink-1`
- On mount: GSAP `CountUp`-style tween (animate a JS number, format with `Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })` per frame)
- Duration: `DUR.hero` (1.6s), ease `EASES.out`

#### 4.2 `DeltaCard.vue`
- Props: `delta: { intervention_id, label, element, icon, lives_saved_mean, lives_saved_ci, dollars_saved_mean, dollars_per_life, misinfo_change }`
- Layout: ElementBadge top-left (size 32), label, three small KPIs (lives, $, $/life), small `90% CI` text
- Stagger-in via parent timeline: `gsap.from('.delta-card', { y: 24, opacity: 0, stagger: 0.08, duration: DUR.base })`
- Element-tinted left border: `border-left: 3px solid var(--el-{element})`

#### 4.3 `ComparatorTable.vue`
- Props: `arms: Array<{intervention_id, label, element, lives_saved_mean, lives_saved_ci, ...}>`
- Replaces the existing `<table>` in AuroraView (lines ~88–120 of current file)
- Each row: label, then a horizontal bar showing `lives_saved_mean / max(arms.lives_saved_mean) * 100%`, plus error-bar overlay for CI
- Bars width-tween from 0 → target with `gsap.to({ width: '0%' }, { width: '${pct}%', duration: DUR.slow, ease: EASES.snappy })`, stagger 0.08s

#### 4.4 `CumulativeChart.vue`
- Props: `arms: Array<{intervention_id, label, element, cumulative_deaths_p50: number[], hours: number[]}>`
- Uses d3 to compute the SVG path strings. Renders one `<path>` per arm
- On mount: each path's `stroke-dasharray = pathLength`, `stroke-dashoffset = pathLength`. Tween offset → 0 with `DUR.slow`, stagger 0.15s (baseline first)
- Stroke color = `var(--el-{element})`, width = 2px
- Y-axis grid lines fade in last (after all paths drawn)
- Last data point of each arm gets a label dot + arm name (Our World in Data style — adjacent to the line, not a corner legend)
- Footer: `Source: HAZUS-MH 2.1, Worden 2012 GMICE, n=N trials`

#### 4.5 `views/AuroraView.vue` rewrite
- Compose: scenario row → intervention chips → sliders → RunButton → (during run) MCProgressPanel + AgentLogTicker → (after) HeroNumber + DeltaCard grid + ComparatorTable + CumulativeChart
- Replaces the entire current file. Target ~150 LOC (vs current 370).
- Page accent retints based on selected scenario's element via `<style scoped>` with `:root[data-active-element="fire"] { --accent: var(--el-fire); ... }`

**Files touched**: 4 new components, 1 full rewrite of AuroraView. ~800 LOC total.

**Gates**:
- ✅ Result reveal completes within 2.5s of MC done event
- ✅ Reveal frame rate ≥ 50 fps median (Chrome perf panel)
- ✅ HeroNumber CountUp lands exactly on `value` (verify with snapshot at frame `value/16ms = duration*60` ≈ 96 frames)
- ✅ ComparatorTable bars tween smoothly (no layout-shift jank — measure with DevTools "show layout shift regions")
- ✅ CumulativeChart paths draw without dropped frames
- ✅ Footer attribution present and reads `HAZUS-MH 2.1` and `Worden 2012` (string match)
- ✅ Bundle delta ≤ 80 kB gz (GSAP core + ScrollTrigger + SplitText + d3 already there)

**Falsifying test**: Manual — run a 10-trial MC, verify HeroNumber arrives at the expected lives-saved value within 2s. Plus: `frontend/tests/components/cumulative-chart.test.js` checks that `<path>` count == `arms.length` and stroke colors match `var(--el-{element})`.

---

### **P-V5 — Polish + demo prep** (2h budget) — depends on P-V4

**Spec.**

#### 5.1 Reduced-motion handling
- In `motion.js`, add a global guard: if `window.matchMedia('(prefers-reduced-motion: reduce)').matches`, set `gsap.globalTimeline.timeScale(100)` (effectively instant)
- Also disable the RunButton breathing animation
- Verify with macOS System Settings → Accessibility → Display → Reduce motion ON

#### 5.2 Mobile responsive
- AuroraView: scenario row 4-col → 1-col below 768px
- Intervention chips: wrap freely
- ComparatorTable + CumulativeChart: stack vertically below 1024px
- Hero number: scale to `--fz-48` below 768px

#### 5.3 Loading skeletons
- ScenarioCard: shimmer placeholder when `scenarios` array is empty (currently shows "Loading…" text)
- DeltaCard grid: 4 placeholder cards while waiting for first MC result

#### 5.4 Error states
- "Ollama not running" detection: if `useLLM: true` and the run_mc 500s with that error, show a clear message in MCProgressPanel + a "Try without Gemma 4" link that re-runs with `useLLM: false`
- Generic API error: red banner at top of AuroraView, dismissible

#### 5.5 Demo seed
- Add `?seed=demo` query param. When present, AuroraView pre-selects the LA M7.2 scenario and 3 default interventions (preposition + retrofit + evac), sets `n_trials=20`, `useLLM=true`, and auto-clicks Run after 1s
- Document this in [docs/aurora-demo-script.md](docs/aurora-demo-script.md) (new file)

#### 5.6 Pre-warm script
- `backend/scripts/prewarm_ollama.py` — runs a single Gemma 4 e2b chat to bring the model into RAM. Document running it before the demo recording

**Files touched**: edits to motion.js + AuroraView + RunButton, new docs, new script. ~300 LOC.

**Gates**:
- ✅ Lighthouse a11y ≥ 95 on prod build (`vite build && vite preview`)
- ✅ Lighthouse perf ≥ 90 on prod build
- ✅ FCP ≤ 1.2s on prod build (Lighthouse)
- ✅ Bundle gz ≤ 280 kB
- ✅ Reduced-motion OS setting → reveal completes in < 200ms (or instantly visible)
- ✅ DevTools Network → offline → still loads (fonts npm-bundled)
- ✅ Cold demo: `npm run dev` to result reveal in ≤ 90s

**Falsifying test**: Manual demo run from a fresh terminal: stop Ollama, start it, `npm run dev`, navigate to `/aurora?seed=demo`, time from page load to result reveal — must be ≤ 90s.

---

## North Star (KPI tracking)

**% judges retain the lives-saved number 30 min after demo** ≥ 60%.
- Measure: at live judging round / demo booth interview.
- Today: N/A.

## HEART (don't break the fundamentals)

| Dim | Metric | Red flag |
|---|---|---|
| Happiness | Validator says "credible" / "we'd use this" | "Too flashy", "looks gamified" |
| Engagement | Time on page in `?spectate=1` mode | < 30s |
| Adoption | % of cold visitors who click Run | < 50% |
| Task Success | % of MC runs that complete | < 95% |

## Stop conditions

- P-V0 fails (peer-dep) → halt, debug deps before P-V1
- Any phase exit gate fails → halt that phase, do not advance
- Backend progress callback adds > 5% MC runtime overhead → strip running_mean computation, just emit trials_done
- Validator says "too gamey" in pre-record interview → roll back element-glow halos, keep palette only on bars + KPI numbers
- Streaming progress fps < 25 → drop AgentLogTicker, keep bars only
- Bundle > 320 kB gz → drop SplitText (use CSS-only h1 reveal)
- Reveal fps < 40 on M-series → drop CumulativeChart path-draw animation (render statically)

---

## Execution rhythm (phases-execution skill)

Each phase ships through 6 steps:
1. **IMPLEMENT** — sonnet subagent, prompt = phase spec verbatim
2. **REVIEW** — fresh sonnet subagent, no shared context
3. **GATES** — verify each gate listed above
4. **UNIT TESTS** — phase's falsifying test must pass
5. **E2E** — Chrome MCP visual check + manual demo run
6. **COMMIT** — atomic per phase, push to phase-named branch, await user merge greenlight

Sonnet (claude-sonnet-4-6) on every subagent for cost. Main thread (Opus 4.7) reviews each phase's diff before commit.
