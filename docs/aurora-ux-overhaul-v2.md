# Aurora UX overhaul v2 — HARDENED, ready for greenlight

**Source v1**: `docs/aurora-ux-overhaul-v1.md`
**Reviewer verdict**: PLAN BREAKS — 2 load-bearing failures, 7 substantive issues.
**Status**: v2 absorbs every finding. Awaiting user greenlight.

---

## What v1 got wrong (5 load-bearing items)

1. **U1 fix-shape was misdiagnosed.** v1 line 13 said the interceptor "returns `{success, data: {arms, done...}}` and the destructure pulls the inner data dict". Half right. The interceptor at `frontend/src/api/index.js:26-34` already returns `res = response.data` directly and **rejects** the promise when `res.success === false` (lines 29-31). So `auroraApi.getMCProgress` returns the OUTER envelope `{success, data: {...}}`. The current `const { data } = await ...` extracts the INNER payload (`{arms, done, recent_decisions, error}`) — which has no `success` key. The fix is **NOT 2 lines** — it's a 4-line rewrite of MCProgressPanel.vue:117-124 to destructure `success` and `data` separately. v2 specifies the exact patch.

2. **`-glow` token deletion silently breaks `tokens.test.js:26-31`.** The existing test asserts `--el-X-glow` siblings exist for each element. v1's U2 says "drop the glow siblings entirely" but doesn't update or remove the assertion. v2 lists the test edit as part of U2's owned files.

3. **Working-day math off by 1.** v1 claimed 7 working days → 4 effort + 3 buffer. Real count from 2026-05-01 (Fri) to 2026-05-11 (Mon) excluding weekends = 6 working days → 4 effort + 2 buffer. No rehearsal day before 5/11 recording.

4. **U1 misuse test was dead code.** v1 mocked `getMCProgress` to return `{success:false, error:"..."}` — but the interceptor (index.js:29) rejects rather than returns that payload. The mocked test never exercises the real-backend failure path.

5. **U1 effort estimate was 30 min.** With the corrected diagnosis + fixing the wrong test scaffold + verifying the rejection path: **2.5 hours honest**.

## Failure scenarios the red team found (and how v2 addresses each)

- **F1 — Wrong fix lands**: v1's diagnosis was wrong. v2's U1 specifies the exact 4-line patch and a unit test that mocks the AXIOS boundary (not just the auroraApi function), so the test exercises the real interceptor → MCProgressPanel data flow. **New gate**: stub the underlying `service.get` (axios), not `auroraApi.getMCProgress`. **Test name**: `test_streaming_panel_handles_real_axios_response_shape`.

- **F2 — Interceptor rejection path untested**: v2 adds a SECOND U1 test that wires a rejected promise through `auroraApi.getMCProgress` (simulating a real 500) and asserts MCProgressPanel.vue:157's catch fires + emits `e.message`. **Test name**: `test_streaming_panel_handles_rejected_promise`.

- **F3 — `?seed=demo` race**: v2's U3 sets `currentStep = 3` SYNCHRONOUSLY at the top of `applyDemoSeed()`, before the `await loadIndex()` and before the 1-second timer. The RunButton is therefore mounted before the timer fires. **Test name**: `test_seed_demo_runbutton_mounted_before_autorun`.

## Missing edge cases now covered

- **Continue button "disabled"**: v2 specifies BOTH `:disabled` attribute AND a click-handler guard (`function handleContinue() { if (!canAdvance) return; currentStep++ }`). Test: `test_continue_disabled_screenreader_path`.
- **Browser back/forward to `/`**: v2 keeps the `/` → `/aurora` redirect but adds `currentStep` persistence to `sessionStorage` (sub-200-byte cost, no router needed). Test: `test_wizard_resumes_after_back_button`.
- **Reduce-motion + `v-if` GSAP teardown**: v2's U3 wraps each step in a `<KeepAlive>`-aware `useGsap` ctx that calls `ctx.revert()` in the section's `onUnmount` even though the parent stays mounted. Test: `test_reduce_motion_preserves_inline_styles_across_step_transitions`.
- **Double-click Continue**: v2 adds `:disabled` toggling on `transitioning.value = true` for the 200ms tween window. Test: `test_double_click_continue_only_advances_once`.
- **Scenario with 50 districts**: out of scope — Aurora ships with 7 districts max per scenario. Acknowledged ceiling, documented.

## Scalability risk → mitigation

**Risk**: 5 simultaneous demo runners on the Mac mini hit Flask's `_MC_PROGRESS` LRU; if size < 5, the oldest in-flight evicts and returns 404.

**Mitigation**: out of scope for this overhaul (the underlying P-V3 streaming infra is what handles concurrency). v2 documents the **single-user demo ceiling** in the README as a known constraint. The hackathon recording is single-user; pilots are single-user. If multi-user becomes real, that's a separate phase against P-V3, not v1 of this overhaul.

## Other gaps the reviewer caught

- **N=3 cohort statistically meaningless**: v2 bumps to **n=5 internal viewers** for the North Star pre-demo recall test. Same effort to recruit.
- **Input metric #3 (CTAs visible) gameable**: v2 redefines: `count of <button> elements + role="button" with text content >0, in the initial viewport, excluding step-dot navigation and tooltip triggers`.
- **Input metric #4 (Monte Carlo string count) tooltip exception unenforceable**: v2 puts the tooltip text in a single constant `METHODOLOGY_TOOLTIP` in a new `frontend/src/design/copy.js`; grep excludes that file.
- **HEART Happiness leading question**: v2 reworded to "Rate the visual style: 1=very flashy/loud, 5=very calm/restrained" (no value judgment baked in).
- **U2 vibe gate**: dropped "side-by-side screenshot via you" — replaced with the saturation gate already in test scaffold.
- **U3 p95 latency without instrumentation**: dropped the gate. The wizard transitions are sub-frame on any modern machine; not worth measuring.
- **U4 tooltip "explainer" adjective**: v2 specifies `tooltip.textContent.includes("Monte Carlo")` — falsifiable.
- **U5 favicon "visible in Chrome tab" manual**: v2 replaces with file-existence + index.html regex.
- **U6 cold-load gate redundant** with U3 integration test: dropped.

## Corrected sequencing (with realistic effort)

| # | Phase | Why this slot | Effort | Risk | Depends on |
|---|---|---|---|---|---|
| U1 | Streaming bug fix + start.sh check fix | Smallest, highest confidence; lands first as a quick-win commit | **2.5 h** | low | none |
| U2 | Mode C palette + drop -glow + update tokens.test.js | Wizard styling depends on new tokens | **1 d** | med | U1 |
| U3 | Multi-step wizard (with sessionStorage, click guard, GSAP teardown) | Continue CTA replaces Run button copy in U4 | **1.5 d + 4 h buffer** | med | U2 |
| U4 | Rename "Monte Carlo" + add inline tooltip with methodology | Wizard structure determines where tooltip lives | **45 min** | low | U3 |
| U5 | Aurora SVG logo (mark + wordmark + favicon) | Independent | **1 d** | med | none (ships parallel-safe) |
| U6 | Final E2E sweep | After all phases ship | **30 min** | low | U1-U5 |

**Total effort**: U1 (0.3d) + U2 (1d) + U3 (1.5d + 0.5d buffer) + U4 (0.1d) + U5 (1d) + U6 (0.1d) = **4.5 working days**.
**Available**: 6 working days. **Buffer: 1.5 days**. Tight; halt criteria below kick in if it slips.

## Corrected math

- **WCAG `#C77B5C` on `#0F1217`**: 4.78:1 (was claimed 4.91 — small rounding discrepancy, both clear 4.5:1 ✓)
- **Saturation `#A691B8`**: HSL.S = 21.5% (under 30% ✓)
- **Bundle delta**: U2 (-50 bytes gz from glow CSS removal) + U3 (+1.5-2 kB from wizard) + U5 (+1 kB inline SVG) = **+2.5 to +3.5 kB gz**. Original v1 said +5; honest is +3.5. Both within ceiling.
- **Working days**: 6 (was 7). 4.5d effort + 1.5d buffer.

## Corrected KPIs & gates

### North Star (corrected)
**% of n=5 internal pre-demo viewers who can name the wizard step they're on without prompting ≥ 80% (i.e. ≥ 4/5)**.

### Input metrics (corrected)
| # | Metric | Definition | Target |
|---|---|---|---|
| 1 | Streaming MC happy-path success | `?seed=demo` runs progress panel populates → reveal renders | 100% on 3 attempts |
| 2 | Element token saturation | max(HSL.S) across `--el-*` | ≤ 30% |
| 3 | Initial-viewport CTAs (precise) | `count of <button> + role="button" with text content >0 in initial viewport, excluding step-dot nav and tooltip triggers` | 1 per step |
| 4 | "Monte Carlo" in user-visible Vue files | `grep -c "Monte Carlo" frontend/src/views/*.vue frontend/src/components/aurora/*.vue` (excluding `frontend/src/design/copy.js` which holds the tooltip constant) | 0 |
| 5 | Aurora-branded chrome | `<h1>` shows AuroraWordmark; `frontend/public/aurora-mark.svg` exists; `index.html` favicon link is `type="image/svg+xml"` | 100% |

### HEART (corrected)
| Dimension | Metric | Red flag |
|---|---|---|
| Happiness | n=5 viewers Likert: "Rate visual style: 1=flashy/loud, 5=calm/restrained" | < 60% pick 4 or 5 |
| Engagement | Time on page from cold load to user click in step 1 | < 5s = overwhelming, > 60s = lost |
| Adoption | % cold loads reaching Outcome | < 90% |
| Task Success | % full wizard walkthroughs (5 trials × n=5 viewers) completing without error | 100% |

## Phase exit criteria (v2 — every gate is a number)

### U1 exit
- 4-line patch lands on `MCProgressPanel.vue:117-124` AND `:145-149` (both fetch sites)
- `tokens.test.js`'s `-glow` assertion still passes (this phase doesn't touch it)
- 28 + 4 frontend tests = **32**, all green
- Manual smoke: `?seed=demo` → run kicks off → progress panel populates within 2 s → reveal renders → confirmed via single Bash curl + screenshot

### U2 exit
- All 5 element tokens still pass 4.5:1 (existing tokens.test.js)
- New saturation gate: each `--el-*` HSL.S ≤ 30% (new test in `tokens.test.js`)
- Zero `drop-shadow` or `filter: blur` in `frontend/src/components/aurora/*.vue` (new bash grep test)
- Existing `-glow` assertion at `tokens.test.js:26-31` is **REMOVED** as part of U2 (palette intent change documented in commit message)
- 32 + 2 = **34** tests, all green
- Bundle gz: ≤ 240 kB (currently 234.83 + ~3 kB U2/U3 net add)

### U3 exit
- `currentStep` defaults to 1, advances on Continue, decrements on Back, persists across reload via sessionStorage
- `?seed=demo` lands at step 3 with auto-run (existing demo path, no regression)
- Continue is disabled both via `:disabled` attr AND click-handler guard (test for both paths)
- Double-click during transition only advances once (test asserted)
- 34 + 6 = **40** tests, all green

### U4 exit
- 0 user-visible "Monte Carlo" strings in `frontend/src/views/*.vue` and `frontend/src/components/aurora/*.vue` (excluding `frontend/src/design/copy.js`)
- Tooltip element exists; its `textContent` includes the literal string "Monte Carlo" (so curious judges find the methodology)
- 40 + 2 = **42** tests

### U5 exit
- `frontend/public/aurora-mark.svg` exists
- `frontend/index.html` favicon link uses `type="image/svg+xml"` and href ending in `.svg` (regex test)
- AuroraView.vue header contains `<svg>` and **no** `<img>` (assertion test, not snapshot)
- 5 element-color stops in the SVG gradient match `--el-*` token values (test asserts)
- `frontend/src/assets/logo/MiroFish_logo*.jpeg` and `frontend/public/icon.png` are **deleted from disk** (file-existence test asserts absence)
- 42 + 4 = **46** tests

### U6 exit (no new tests)
- All 46 tests green
- D1 mirofish-grep guard: 3/3 OK
- `./start.sh check` reports green
- Manual cold + seed walkthroughs both work
- Recording prep: rehearse with `?seed=demo` once, capture screenshots for the README's `docs/screenshots/` slot

## Stop conditions

- **U1 fails after 1 fix iteration** → revert to non-streaming `runMonteCarlo` for the demo. Streaming is a wow factor, not a requirement.
- **U2 saturation gate fails on any token** → halt the migration. Commit the glow-filter removal and the contrast cleanup; ship without the saturation gate.
- **U3 reactivity breaks `?seed=demo`** → revert wizard, ship U2 + U4 + U5 only. The current monolith UI works.
- **U5 SVG aesthetics rejected by user after 2 iterations** → ship the existing CSS-only Aurora wordmark; no logo this round.
- **By 2026-05-06 EOD U1-U3 not committed** → halt U4-U5; ship U1 + U2 + U3 + U6 only.
- **By 2026-05-08 EOD any gate red** → halt; recording happens with whatever's green.

## Updated test-first scaffold

| Phase | Unit (≥3) | Integration (≥1) | Misuse (1) |
|---|---|---|---|
| U1 | success+data destructure roundtrip; rejected-promise emits `e.message`; happy-path emits `done` | full poll cycle through real axios stub | explicit-failure path tested at axios layer (real interceptor in flight) |
| U2 | tokens contrast (existing); saturation ≤ 30% (new); no-glow grep (new); -glow assertion removed | full AuroraView snapshot with new palette, no drop-shadow in DOM | replace `--el-fire` with `#FF0000` → saturation gate fails |
| U3 | starts at step 1; advances on Continue; Back preserves selection; sessionStorage roundtrip; ?seed=demo lands at step 3 with mounted RunButton; double-click only advances once; reduce-motion preserves inline styles across transitions | full wizard walkthrough end-to-end with mocked LLM stub | Continue with no selection: both `:disabled` AND handler guard refuse |
| U4 | RunButton default label is "Run simulation"; AuroraView 0 user-visible MC strings; tooltip contains "Monte Carlo" | full demo walkthrough renders all updated copy | tooltip refactor that drops "Monte Carlo" → test fails |
| U5 | SVG renders 5 element-color gradient stops; favicon link is svg in index.html; legacy MiroFish logo files don't exist on disk | header snapshot has svg, no img | swapping `<svg>` for `<img>` regression caught |
| U6 | (no new tests) | full E2E with stack live: cold load + seed=demo + manual walkthrough | reduce-motion ON across the wizard still works |

---

## Ready-to-start step

User greenlight on:

(a) **Strict serial U1 → U2 → U3 → U4 → U5 → U6** (~4.5 working days, safest). Each phase ships its own commit on `phase/aurora-ux-overhaul` branch; one PR at the end.

(b) **U1 alone first as its own quick PR off main** (the streaming bug fix). Then U2-U6 as a separate, longer PR. Lets you verify the bug is dead before more changes land.

(c) **U1 + U5 in parallel** (independent: bug fix doesn't share files with the SVG logo), then strict serial U2 → U3 → U4 → U6. Saves ~1 day calendar but you have to track two branches at once.

Recommended: **(b)** — the streaming bug is currently blocking your ability to test the demo at all. A 2.5-hour PR ships the fix today; then the bigger U2-U6 PR has the time and care it deserves.

After greenlight: dispatch `phases-execution` skill with this v2 plan + the chosen sequencing.
