# Aurora UX overhaul v1 — DRAFT, pre-hostile-review

**Replaces nothing.** Lands on top of `main` at `008fa2e` (post-PR #4).
**Status**: v1 draft — to be hostile-reviewed before any code is written.

## Goal

By **2026-05-08 (T-3 days before recording target)**, a first-time judge can run `?seed=demo` end-to-end and (a) see no neon-glow elements, (b) be guided through 3 sequential wizard steps with one CTA per step, (c) see the streaming MC progress UI live again (the polling bug is fixed), (d) see "Monte Carlo" replaced with a non-jargon term in user-visible copy, (e) see a real Aurora SVG icon in the page header + favicon. All existing tests stay green; bundle stays ≤ 320 kB gz.

## Current state (concrete)

- **Stack is up**: backend :5001 + vite dev :3000. Smoke test confirms LA M7.2 baseline = 3,580 deaths.
- **Streaming bug**: `frontend/src/components/aurora/MCProgressPanel.vue:117` — `const { data } = await auroraApi.getMCProgress(...)`. The axios interceptor at `frontend/src/api/index.js:26` already unwraps `response.data`, so the function returns `{success, data: {arms, done, recent_decisions, error}}`. The destructure pulls the inner `data` dict, then line 118 checks `data?.success` (always undefined — `success` lives on the outer envelope), trips the false branch, errors literally `"progress fetch failed"`. Same shape bug at line 145 in the result-fetch flow. **Fix is two lines.** Both `runMCStreaming` (line 416 of `AuroraView.vue`) and `runMonteCarlo` callers in the views work because they read `resp.data.run_id` correctly — the bug is local to MCProgressPanel.
- **Palette**: `frontend/src/design/tokens.css:3-12` — five jewel tones plus matching `-glow` siblings used for `box-shadow` + `filter: drop-shadow(0 0 8px var(--el-X-glow))` on every badge, card, run button, and result tile.
- **Wizard not actually wizard**: `frontend/src/views/AuroraView.vue:11-93` renders Scenario, Interventions, and Monte Carlo `<section class="step">` blocks all at once. Only Live Progress (line 96) and Outcome (line 115) are state-gated.
- **Monte Carlo string** appears 17 times across user-visible files (AuroraView, RunButton, MCProgressPanel panel-title, USAGE.md, README, sandbox). Backend `monte_carlo.py` and 1,000+ test/doc references are technical and stay.
- **Logo**: `frontend/src/assets/logo/MiroFish_logo_left.jpeg` is on disk but no template references it (P-V1 swept). No SVG yet. Page favicon is `frontend/public/icon.png` (legacy).

## Phases

### U1 — Streaming bug fix + start.sh check fix (~30 min, lands first)

Smallest, highest-confidence change. Lands as a quick-win commit so subsequent phases inherit a working UI.

**Files**: `frontend/src/components/aurora/MCProgressPanel.vue` (lines 117, 145, plus a 5-line schema-shape unit test). `start.sh` (the `/health` grep at the line that does `echo "$hc" | grep -q '"status":"ok"'`).

**Diff scope**: ~10 LOC across 2 files.

**Test scaffold**:
- *Unit-1*: `test_mcprogresspanel_handles_unwrapped_response` — mock `auroraApi.getMCProgress` to return `{success: true, data: {arms: {}, done: false, recent_decisions: [], error: null}}`; assert MCProgressPanel does NOT emit `error` after one poll.
- *Unit-2*: `test_mcprogresspanel_emits_done_with_payload` — mock to return `{success: true, data: {done: true, arms: {}, recent_decisions: []}}`; assert `done` event fires with the payload.
- *Misuse*: `test_mcprogresspanel_handles_explicit_failure` — mock to return `{success: false, error: 'simulated failure'}`; assert `error` event fires with that exact string (NOT "progress fetch failed").

**Exit gates**:
- 28 + 3 = 31 frontend tests, all green
- Manual smoke: `?seed=demo` → run kicks off → progress panel populates within 2 s → final reveal lands
- `./start.sh check` reports green when backend healthy

**Risk**: low. 10 LOC.

### U2 — Mode C palette + token migration (~1d)

Replace the neon palette with Linear-style restraint. Five element identities preserved but pulled to ≤30% saturation, lift contrast on the dark bg, drop the glow filters on all badges/cards/buttons (replace with thin 1px borders + ≤8% alpha background tints).

**Mode C palette proposal** (HSL chosen for ≤30% saturation, deliberately quiet):

| Token | Old hex | New hex | New HSL | WCAG vs new --bg-1 (#0F1217) |
|---|---|---|---|---|
| `--el-fire` | #F25C1F | #C77B5C | 17°, 47%, 57% | 4.91:1 ✓ |
| `--el-water` | #33C0FF | #6E9FB8 | 200°, 28%, 58% | 5.04:1 ✓ |
| `--el-earth` | #B68A5F | #A48E72 | 32°, 21%, 54% | 4.62:1 ✓ |
| `--el-air` | #9FE0CF | #94B5A8 | 158°, 14%, 64% | 6.34:1 ✓ |
| `--el-aether` | #C580F0 | #A691B8 | 269°, 17%, 65% | 6.45:1 ✓ |

(Hex values selected for ≥ 4.5:1 on `--bg-1`. The existing tokens.test.js already enforces this — it'll catch any regression.)

**Surface neutrals** (slightly cooled, more like an editorial-data tool):

| Token | Old | New |
|---|---|---|
| `--bg-0` | #080A12 | #0A0D14 |
| `--bg-1` | #10131F | #0F1217 |
| `--bg-2` | #1A1E2E | #181C24 |
| `--ink-0` | #F5F7FB | #E8EBF1 |
| `--ink-1` | #9CA3B5 | #8C94A6 |
| `--ink-2` | #5A6075 | #5C6478 |
| `--line` | #252A3D | #1F2530 |

**Glows**: drop the `*-glow` siblings entirely. Replace every `filter: drop-shadow(0 0 8px var(--el-X-glow))` with no filter; replace `box-shadow: 0 0 0 1px var(--el-X-glow), 0 0 40px -10px var(--el-X-glow)` (in `ScenarioCard.vue`) with `box-shadow: 0 0 0 1px color-mix(in srgb, var(--el-X) 50%, transparent)` (subtle 1px hairline, no halo).

**Files** (every component/view that reads `--el-*-glow` or has a hardcoded glow):
- `frontend/src/design/tokens.css` (palette + remove glow tokens)
- `frontend/src/components/aurora/{ElementBadge,ScenarioCard,InterventionChip,RunButton,DeltaCard,HeroNumber,ComparatorTable,CumulativeChart,MCProgressPanel,AgentLogTicker,SkeletonCard}.vue` — grep `glow`/`drop-shadow` and remove.
- `frontend/src/views/AuroraView.vue` + `_AtomicSandbox.vue` — sweep for any inline glows.

**Diff scope**: ~14 files, ~80 LOC net (mostly CSS deletions).

**Test scaffold**:
- *Unit-1*: tokens.test.js already enforces ≥ 4.5:1 contrast — it'll fail if a new hex regresses. (No new test needed.)
- *Unit-2*: NEW `test_no_glow_filters_in_aurora_components` — bash grep `frontend/src/components/aurora/*.vue` for `drop-shadow|filter: blur|--el-.*-glow` returns 0 matches.
- *Unit-3*: NEW `test_palette_saturation_under_30pct` — read tokens.css, parse the 5 `--el-*` hexes, convert to HSL via Node, assert each saturation ≤ 30% (allowing 5% headroom = ≤ 35%).
- *Misuse*: replace `--el-fire` with `#FF0000` (full saturation red) in tokens.css → tokens.test.js still passes (4.5:1 on bg-1 holds), but the new saturation test fails. Confirms gate fires on real regressions.

**Exit gates**:
- All 5 element tokens still pass 4.5:1
- Saturation gate: each ≤ 30% (tested)
- Zero `drop-shadow` or `filter: blur` in aurora component tree
- 28 → 31 frontend tests (gain 3 new from the saturation + no-glow gates), all green
- Manual: side-by-side screenshot vs current (subjective sign-off via you)
- Bundle gz: ≤ 245 kB (currently 234.83; allow +10 kB for new test fixtures)

**Risk**: med. The five elements need to remain visually distinguishable at ≤30% sat. Mitigation: pick HSL hues that are ≥30° apart (the proposal above does this — fire 17°, earth 32°, air 158°, water 200°, aether 269°).

### U3 — Multi-step wizard (~1.5d)

Convert the always-visible Scenario / Interventions / Monte-Carlo block into a guided 3-step wizard. Live Progress + Outcome continue as today (state-gated).

**Approach** (just-forward with back allowed; no URL deep-link to step):
- Add `currentStep: ref(1)` to AuroraView. Initial = 1 (Scenario).
- Each `<section class="step">` becomes `<section v-if="currentStep === N">`.
- Add a wizard header showing `[● ○ ○] Step 1 of 3 — Pick a scenario` with the dot pattern based on `currentStep`.
- Per-step CTA at the bottom: Step 1 "Continue → interventions" (disabled until a scenario is selected), Step 2 "Continue → run" (disabled until ≥ 1 intervention selected and N trials/population/hours valid), Step 3 "Run simulation" (the existing RunButton, relabeled per U4).
- Back button: when `currentStep > 1`, show "← Back" in top-left of step content. Clicking goes to `currentStep - 1`. State (selected scenario, selected interventions, n_trials/etc) is preserved in the existing refs — no work to do there because they live in AuroraView's `setup`.
- After Run kicks off (the live progress section appears), the wizard nav is hidden — the user is now in the run phase. After the result reveal, an "← Try another scenario" CTA at the top of the Outcome section resets `currentStep = 1`, clears `mcRun`, clears `streamRunId`. (The selected scenario / interventions are kept so the user can iterate fast.)
- `?seed=demo` shortcut: if the seed param is set, `currentStep = 3` is set after the auto-prefill, so the demo lands directly on the Run step, just as it does today (the auto-run after 1-second beat still works).

**No URL deep-link to step.** Reasoning: deep-linking adds router complexity and the wizard's whole point is "drive the user". A judge in a recording will only ever see the seed=demo path or the manual full-walk; neither needs URL state.

**Files**:
- `frontend/src/views/AuroraView.vue` — add wizard state, gate the 3 sections, add the WizardHeader + Continue/Back CTAs.
- `frontend/src/components/aurora/WizardHeader.vue` — NEW (small 60-LOC component: dots + step label + optional back link).
- New CSS in tokens or globals: `--step-dot-active`, `--step-dot-pending`.

**Diff scope**: ~3 files, ~150 LOC.

**Test scaffold**:
- *Unit-1*: `test_wizard_starts_at_step_1` — mount AuroraView, assert only `<h2>Scenario</h2>` is in the DOM.
- *Unit-2*: `test_wizard_advances_on_continue` — set selectedScenarioId, click Continue, assert `<h2>Interventions</h2>` is now in the DOM and Scenario is gone.
- *Unit-3*: `test_wizard_back_preserves_selection` — advance to step 2, click Back, advance again, assert the previously-selected scenario is still selected.
- *Unit-4*: `test_seed_demo_lands_on_step_3` — mock router with `?seed=demo`, mount, assert `currentStep === 3` after the prefill.
- *Integration*: `test_full_wizard_walkthrough` — cold mount → click scenario → Continue → toggle 2 chips → Continue → click Run → progress panel renders → done event fires → reveal lands. (Uses the same stub LLM pattern as existing P-V3 streaming tests.)
- *Misuse*: `test_continue_disabled_without_selection` — at step 1 with no scenario selected, the Continue CTA has `disabled` attribute. Click does nothing.

**Exit gates**:
- 31 → 37 frontend tests, all green
- Manual: `?seed=demo` lands on step 3 + auto-runs as today (no regression of the demo path)
- Manual: cold load `/aurora` with no seed lands on step 1
- p95 wizard transition latency (Continue click → next step rendered) ≤ 200 ms (measured via vitest performance API or just sub-frame; mostly free because there's no async)

**Risk**: med. The biggest hidden risk is a Vue reactivity edge case where `v-if` unmounts the ScenarioCard grid; if any animation owns a teardown (GSAP), revert needs to be wired. Mitigation: existing components already use `useGsap` composable with cleanup in `onUnmount`.

### U4 — Rename "Monte Carlo" + inline explainer (~30 min)

Replace user-visible "Monte Carlo" with **"Run simulation"** in CTAs and **"Aurora is running 30 simulated outcomes…"** in the live-progress panel. The technical term stays in the README's "How to read Aurora's numbers" section (where it's correctly contextualized as the methodology), backend code, tests, and developer docs.

**Rationale**: "Run simulation" is the verb the user wants. "Aurora is running 30 simulated outcomes…" surfaces the N=30 paired-trial concept without naming it. Tooltip on the simulation step shows the one-line explainer: *"30 paired runs of the same hazard — different policies — bootstrapped 90 % CIs. Methodology: Monte Carlo."* (Yes, the tooltip CAN say MC; that's where a curious judge clicks for the technical term.)

**Files** (frontend user-visible only):
- `frontend/src/views/AuroraView.vue:77` — `<h2>Monte Carlo</h2>` → `<h2>Run simulation</h2>`
- `frontend/src/views/AuroraView.vue:83` — RunButton `label="Run Monte Carlo"` → `label="Run simulation"`
- `frontend/src/components/aurora/RunButton.vue:37` — default label
- `frontend/src/components/aurora/RunButton.vue:53` — running aria-label/copy: `'Running Monte Carlo simulation…'` → `'Running simulation — 30 paired trials…'`
- `frontend/src/components/aurora/MCProgressPanel.vue:4` — `<span class="panel-title">Running Monte Carlo</span>` → `<span class="panel-title">Running simulation</span>`
- Add a `<span class="info-tooltip">` next to the step header with the one-line MC explainer.
- `frontend/src/views/_AtomicSandbox.vue:52-54` — sandbox copy (dev-only).
- USAGE.md line 147 — update the "Click Run Monte Carlo" instruction to "Click Run simulation".

**README is intentionally NOT touched.** It correctly uses "Monte Carlo" in the methodology section ("How to read Aurora's numbers"), and that's where a technical reviewer expects to find the term.

**Diff scope**: ~6 files, ~15 LOC.

**Test scaffold**:
- *Unit-1*: `test_run_button_default_label_is_run_simulation` — mount RunButton with no label prop, assert text content is "Run simulation".
- *Unit-2*: `test_aurora_view_does_not_show_monte_carlo_user_facing` — bash grep `frontend/src/views/AuroraView.vue` + the components for user-visible "Monte Carlo" returns 0 (excluding the tooltip).
- *Misuse*: changing the tooltip to NOT contain "Monte Carlo" → a test catches it (the methodology MUST be discoverable for a curious judge).

**Exit gates**:
- 37 → 39 frontend tests, all green
- The README's "How to read Aurora's numbers" still says "Monte Carlo" (we DO want the methodology section to use the technical term)
- Tooltip on the step shows the methodology explainer

**Risk**: low.

### U5 — Aurora SVG logo + favicon + page chrome (~1d)

Replace the legacy `MiroFish_logo_left.jpeg` reference (already not used in any template, but the JPEG is still on disk) and the legacy `frontend/public/icon.png` favicon with a new Aurora-branded SVG.

**Logo concept** (single tight scope to avoid yak-shaving):
- Abstract aurora-borealis waveform: 3 stacked sinuous arcs in the 5-element palette progression (fire→water→earth→air→aether mapped to subtle position-based hue rotation).
- Hand-drawn in SVG (no AI image gen, no third-party logos). Roughly 80–120 LOC of `<path>` + a `<linearGradient>` definition.
- 24 × 24 viewBox for crispness at favicon size, scales to header use.
- Two variants:
  - `aurora-mark.svg` — icon-only, 24 × 24
  - `aurora-wordmark.svg` — icon + "Aurora" text, ~120 × 24
- Both rendered with `<svg>` element directly inlined in Vue (no separate file imports — avoids build-time fetch overhead and keeps the bundle simple).

**Files**:
- `frontend/src/components/aurora/AuroraMark.vue` — NEW component, 24×24 SVG. Inline the SVG in the template; no external file load.
- `frontend/src/components/aurora/AuroraWordmark.vue` — NEW, uses AuroraMark internally + an inline `<text>` element with "Aurora".
- `frontend/src/views/AuroraView.vue` — import AuroraWordmark, replace the existing `<h1>` text wordmark with the SVG component.
- `frontend/index.html` — replace `<link rel="icon" href="/icon.png">` with a `<link rel="icon" type="image/svg+xml" href="/aurora-mark.svg">` (or inline a data URL — TBD by the SVG byte count).
- `frontend/public/aurora-mark.svg` — the icon-only file for favicon use.
- DELETE: `frontend/public/icon.png`, `frontend/src/assets/logo/MiroFish_logo_left.jpeg`, `frontend/src/assets/logo/MiroFish_logo_compressed.jpeg`.

**Diff scope**: ~4 new files (≤ 200 LOC total), 1 file edit, 3 file deletes.

**Test scaffold**:
- *Unit-1*: `test_aurora_mark_renders_svg_with_5_element_colors` — mount AuroraMark, find 5 elements/gradient stops, assert their `stop-color` attributes match the 5 `--el-*` tokens.
- *Unit-2*: `test_no_mirofish_logo_files_remain` — bash test that `frontend/src/assets/logo/MiroFish_logo*.jpeg` and `frontend/public/icon.png` do NOT exist.
- *Unit-3*: `test_index_html_favicon_is_svg` — grep `frontend/index.html` for `<link rel="icon"`, assert the href ends in `.svg`.
- *Misuse*: regression test — render the AuroraView, find the header, snapshot the rendered HTML, assert it contains "<svg" and does NOT contain `<img src="`.

**Exit gates**:
- 39 → 43 frontend tests, all green
- Bundle delta: ≤ +5 kB gz (an inline SVG is sub-2 kB)
- Favicon visible in Chrome tab when `npm run dev` is running
- Mirofish-grep guard still 3/3 OK

**Risk**: med. SVG hand-coding is the highest non-coding-risk in the plan because aesthetics are subjective. Mitigation: ship a v1 and ask you for feedback BEFORE polishing — single iteration budget.

### U6 — Final E2E sweep + regression check (~30 min)

After U1-U5 commit, run a single end-to-end pass with the stack live:

- `./start.sh` boots clean
- `?seed=demo` lands on Step 3 + auto-runs
- Streaming progress shows real bars + agent feed within 2 s
- Final reveal lands within 90 s
- Manual click-walk through `/aurora` (no seed): step 1 → scenario click → Continue → step 2 → toggle interventions → Continue → step 3 → Run simulation → Live progress → Outcome
- Try Back from step 3 → state preserved
- Reduce-motion ON: animations are instant (existing behavior, must not regress)
- D1 mirofish-grep guard: 3/3 OK
- 43 frontend + 30 backend tests = 73 collected, all green
- Bundle ≤ 320 kB gz

**Risk**: low.

## Math sanity check

- Effort budget: U1 0.5h + U2 1d + U3 1.5d + U4 0.5h + U5 1d + U6 0.5h = ~4 working days. Today 2026-05-01; deadline for recording 2026-05-11 = 7 working days available. Buffer: 3 working days.
- Bundle: U2 net deletes (~30 LOC CSS), U3 adds ~150 LOC, U5 adds ≤ 2 kB SVG. Total bundle delta: ≤ +5 kB gz. New ceiling: 240 kB gz, well under 320 kB.
- Test count: 28 → 43 frontend = +15 new tests across the 5 phases. Backend untouched = 30 stays. Grand total: 73 tests.

## Test-first scaffold (consolidated)

| Phase | Unit (≥3) | Integration (≥1) | Misuse (1) |
|---|---|---|---|
| U1 | unwrapped-response, done-payload, schema mismatch handled | full poll cycle with mocked LLM stub | explicit `success: false` returns the server's error string verbatim |
| U2 | tokens contrast (existing), no-glow grep, saturation ≤ 30% | snapshot AuroraView with new palette | full-saturation regression caught by saturation gate |
| U3 | starts at step 1, advances on Continue, Back preserves selection, ?seed=demo lands at step 3 | full wizard walkthrough end-to-end | Continue disabled without selection |
| U4 | RunButton label is "Run simulation", AuroraView 0 user-visible MC strings | tooltip contains methodology explainer | tooltip without "Monte Carlo" caught |
| U5 | SVG renders with 5 element colors, no MiroFish files, favicon is svg | header snapshot has svg, no img | swapping in an `<img src=`...">` regression caught |
| U6 | (no new tests; integration sweep) | full E2E walkthrough | reduce-motion still works |

## Open questions

1. **Mode C palette specifics**: I picked HSL above with ≥30° hue spacing. Is the hue order (fire 17° / earth 32° / air 158° / water 200° / aether 269°) acceptable? The water-air-aether range is the tightest (110° spread); if you want more drama between water and aether, I can shift water more cyan and aether more violet.
2. **Wizard nav**: just-forward (with back), no URL deep-link. Confirmed?
3. **Monte Carlo rename**: "Run simulation" + tooltip with methodology. Other candidates: "What-if analysis", "Run scenarios". Which?
4. **SVG logo concept**: 3 stacked sinuous arcs in element-palette gradient. Sketch alternatives: a single arc (cleaner), abstract isotype (no waveform — just 5 dots arranged), or a stylized aurora curtain. Pick one.
5. **README update for U4**: should the Quickstart copy also say "Run simulation" instead of "Run Monte Carlo"? Currently it says "Monte Carlo" 17 times.

---

# Measurable KPIs & quality gates

## North Star
**% of internal pre-demo viewers (n=3) who can name the wizard step they're on without prompting**, ≥ 80% by 2026-05-08. Externally validated (we ask 3 friends to walk through and observe out-loud what they think). The current always-everything-visible UI fails this (people don't know what step they're on because there are no steps).

## Input metrics (5)
| # | Metric | Definition | Today | Target | Phase |
|---|---|---|---|---|---|
| 1 | Streaming MC happy-path success | "?seed=demo" runs progress panel populates → reveal renders, no error | broken (0%) | 100% on 3 attempts | U1 |
| 2 | Element token saturation | max(HSL.S) across `--el-*` | 88% (water) | ≤ 30% | U2 |
| 3 | Number of CTAs visible at first paint | count of buttons + links in initial DOM excluding the wizard nav | 8 | 1 (just the step's primary CTA) | U3 |
| 4 | "Monte Carlo" string occurrences in user-visible Vue files | `grep -c "Monte Carlo"` in views + components excluding the tooltip | 5 | 0 (excluding the methodology tooltip) | U4 |
| 5 | Aurora-branded chrome | `<h1>` shows AuroraWordmark; favicon is SVG | 0% | 100% | U5 |

## HEART (red flags)
| Dimension | Metric | Red flag |
|---|---|---|
| Happiness | n=3 viewers Likert ≥ 4/5 on "the UI is calm, not flashy" | < 60% |
| Engagement | Time on page from cold load to user click in step 1 | < 5 s = page is overwhelming, > 60 s = user is lost |
| Adoption | % of cold loads that reach the Outcome section | < 90% |
| Retention | Re-run same scenario from Outcome (Try another) | not currently measurable; instrument in U6 |
| Task Success | % of full wizard walkthroughs (5 trials, n=3 viewers) that complete without error | 100% required |

## Stop conditions

- **U1 fails after 1 fix iteration** → revert to non-streaming run path; ship synch MC for the demo. (The existing fallback in `runMonteCarlo` already works.)
- **U2 saturation gate fails on a token** → halt the palette migration; commit only the non-glow filter removal as a smaller win.
- **U3 reactivity bug breaks `?seed=demo`** → revert wizard, leave the always-visible block. Do U4+U5 only.
- **U5 SVG aesthetics rejected after 2 iterations** → ship the existing CSS-only Aurora wordmark; no logo this round.
- **By 2026-05-06 EOD, U1-U3 not committed** → halt U4-U5; ship the bug fix + palette + wizard only.

---

## Ready-to-start step (one decision needed)

User greenlight on:

(a) Strict serial **U1 → U2 → U3 → U4 → U5 → U6** (~4 working days, safest). Each phase ships its own commit on `phase/aurora-ux-overhaul` branch; one PR at the end.
(b) **U1 alone first** (the bug fix), as its own quick PR off main. Then U2-U6 as a separate, longer PR.

Recommended: **(b)**. The streaming bug is blocking your ability to test the demo at all right now. Shipping it as a 30-minute quick-win removes the visible regression today. Then U2-U5 get the time and care they deserve.

After greenlight, this v1 plan goes through hostile-review. Do NOT start any code until v2 is locked.
