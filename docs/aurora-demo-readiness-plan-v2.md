# Aurora demo-readiness plan v2 — hardened

**Status:** v2, deltas on v1, ready for user greenlight.
**Source v1:** `docs/aurora-demo-readiness-plan-v1.md`
**Red-team review:** captured below.

---

## What v1 got wrong (5 items)

1. **Mirofish file count off by 13.** v1 line 9 claimed 38 files; actual `git grep -li mirofish | wc -l` = **51**, including `package-lock.json`, `backend/uv.lock`, 8 backend service files, 4 storage files, `.github/workflows/docker-image.yml`. v1 D1 exit grep scope (`frontend/src` + `frontend/index.html`) was too narrow — backend strings would have leaked into served JSON / log lines.
2. **Google Fonts strip ignored 3 of 4 font families.** v1 line 25 said "Inter Variable already bundled". Actual `frontend/index.html:6` loads Inter, **JetBrains Mono, Noto Sans SC, Space Grotesk**. Removing the link without replacing the latter three causes FOUT in screenshots 2, 5, 7.
3. **Neo4j volume-persistence trap.** v1 changed `NEO4J_PASSWORD=mirofish` → `aurora` but `docker-compose.yml:28` reads it via `NEO4J_AUTH`, and Neo4j sets the password on first boot of the volume — never re-reads. Judge cloning a fresh repo against a stale `neo4j_data` volume gets login refused.
4. **D2 wall-time benchmark gate unsatisfiable.** `backend/tests/test_aurora.py` has zero wall-time assertions (only correctness). v1 D2 exit (line 197) "every benchmark within ±20% of pytest" cannot be satisfied because no such pytest exists. Either drop wall-time README claims or add `pytest-benchmark` assertions.
5. **D3 missing pre-flight Chrome MCP liveness check.** `mcp__Claude_in_Chrome__list_connected_browsers` exists; v1 never called it. If the connector is offline on day-of, D3 dies after the first navigate. v1 also did not flag that `computer-use__screenshot` requires Chrome to be frontmost — a stray Bash command surfacing a terminal silently captures the wrong window.

## Failure scenarios the red team found (and how v2 addresses each)

- **F1: Mirofish-grep undercount → D1 declared done while strings remain.**
  → v2 D1 exit gate widens grep scope to `frontend/src frontend/index.html backend/app docker-compose.yml .env.example package-lock.json backend/uv.lock backend/pyproject.toml README.md docs/aurora-demo-script.md`. Adds explicit allowlist for permitted matches (test fixtures, license-decision.md historical record).
- **F2: Google Fonts strip → FOUT.**
  → v2 D1 adds @fontsource-variable for **all four families** *before* removing the `<link>` — `@fontsource-variable/inter` (already in P-V1), `@fontsource-variable/jetbrains-mono`, `@fontsource/noto-sans-sc`, `@fontsource/space-grotesk`. Bundle delta budget raised from +5% to +35 kB gz. New D1 exit assertion: `npm run build` reports JS gz ≤ **240 kB** AND `dist/index.html` contains zero `googleapis.com` hits.
- **F3: docker-compose Neo4j auth break.**
  → v2 D1 adds a README quickstart section "If you have an existing Neo4j volume" with the explicit `docker volume rm neo4j_data` step. v2 D2 README structure includes this in section 5 (Quickstart). v2 D2 misuse test: `docker compose down -v && docker compose up -d` from clean state, backend boots, `/aurora` returns 200.

## Missing edge cases now covered

- **`<title>` ownership conflict** → v2 D1 adds inspection of `App.vue` and `router/index.js` for any `document.title` mutations. New D1 exit: `grep -rn "document.title" frontend/src` returns 0 OR every match writes "Aurora — …".
- **`package-lock.json` and `uv.lock` mirofish strings** → v2 D1 includes these in the explicit grep scope; for `uv.lock` the fix is `uv lock --upgrade-package mirofish-offline-backend` after pyproject rename (or simply delete + regenerate).
- **`prewarm_ollama.py` does NOT guarantee 90s wall time** → v2 modifies `backend/scripts/prewarm_ollama.py` to additionally run **one full demo-seed Monte Carlo trial** (n_trials=1, n_population=30, useLLM=true) before declaring "warm". This loads KV cache for the actual demo prompts.
- **Synth fallback hides the Ollama-error path** → v2 D3 misuse test adds a frontend env override `VITE_E2E_FORCE_LLM_ERROR=1` (read in `AuroraView.vue` only when `import.meta.env.DEV` or explicitly opted in via query param `?force_llm_error=1`) so the button is verifiable in the screenshot pack regardless of synth fallback timing.
- **`/` routes to legacy Home.vue** → v2 D1 adds a router redirect: `{ path: '/', redirect: '/aurora' }`. Screenshot 1 captures the redirected `/aurora` page, no longer the legacy MiroFish landing.
- **`<img src="MiroFish_logo_left.jpeg">`** → v2 D1 replaces the JPEG with a CSS-only Aurora wordmark in Home.vue (text + 5-element underline accent). Removes the binary asset reference; file stays on disk to avoid breaking any unforeseen reference, but no template loads it.

## Scalability risk → mitigation

**Risk**: 24-screenshot Chrome MCP run is multiplicatively flaky. Each frame requires (a) chrome-MCP navigate/click, (b) Bash sleep, (c) computer-use screenshot. If either connector drops mid-run (chrome extension auto-update, mac sleep, computer-use grant expiry), restart cost is the entire batch.

**Mitigation in v2**:
- **Pre-flight gate** (new D3 entry criterion): call `mcp__Claude_in_Chrome__list_connected_browsers` AND `mcp__computer-use__list_granted_applications`. Both must report Chrome connected/granted. If either fails, halt before frame 1 — don't waste effort.
- **Checkpoint commits**: after every 4 screenshots, `git add docs/screenshots/0[1-4]*.png && git commit`. Worst-case restart loses ≤ 4 frames.
- **Manual fallback**: if Chrome MCP fails twice (e.g. tabId regenerates after extension reload), drop to QuickTime screen recording for the dynamic frames (#5–#10) and use the Chrome MCP only for static state captures (#2, #8). Ships 12 frames either way.
- **Ceiling stated**: design holds for ≤ 30 sequential screenshots; beyond that, Chrome MCP `find()` ambiguity dominates, switch to puppeteer.

## Other gaps the reviewer caught

- v1 said "11 days" — calendar, not working. v2 corrects: **7 working days** with **4–5 working day buffer** after 2–3 day execution.
- v1 didn't address `static/image/` indirect references — v2 D1 adds `grep -rn "MiroFish_logo\|mirofish-offline" .` (excluding `static/image/` itself) to confirm no remaining references.
- v1's HEART "Happiness" row was a quote ("looks impressive") — v2 replaces with **≥ 60% of internal pre-demo viewers (n=3) rate demo ≥ 4/5 on credibility Likert**.
- v1 had no leading proxy for the demo-day-only North Star — v2 adds: **internal pre-demo viewer recall test by 2026-05-12** as the leading indicator.
- v1's "logo missing → fails loud" was undefined — v2 specifies: Home.vue gains an `@error` handler on the `<img>` that mounts a fallback text wordmark; misuse test verifies the fallback by giving a bad `src` and asserting the wordmark renders.

## Corrected sequencing

| # | Phase | Why this slot | Risk | Depends on |
|---|---|---|---|---|
| D1 | Mirofish purge + offline-fonts fix + router redirect | Must precede screenshots; touches build inputs | Med | none |
| D2.5 | `pytest-benchmark` wall-time assertions added | Must precede D2 because D2 exit gate cites these tests | Low | D1 |
| D2 | README rewrite + benchmark numbers from D2.5 | Numbers must be backed by tests already shipped | Low | D2.5 |
| D3 | Chrome E2E + 12 screenshot pack | Captures pixels; depends on D1 for clean strings AND D2 for README placeholders | High | D2 |

Strict serial: D1 → D2.5 → D2 → D3.

## D1 contract amendments (loop-back, recorded for audit)

During D1's review/consistency-check loop the following amendments were ratified:
1. **README deferred from D1 grep gate**: D1 grep scope is `frontend/src frontend/index.html backend/pyproject.toml docker-compose.yml .env.example` (allowlist as before). README is rewritten in D2.
2. **`backend/app/config.py` companion fix**: D1 may edit ONLY 2 lines — `SECRET_KEY` and `NEO4J_PASSWORD` defaults — so the password change is functionally consistent end-to-end. All other `backend/app/*` mirofish references (logger channel names, docstrings, JSON-doc comments) remain out of scope.
3. **`SimulationView.vue` and `SimulationRunView.vue` added to D1 owned files**: brand string sweep (one line each, `MIROFISH OFFLINE` → `AURORA`).
4. **`docs/aurora-demo-readiness-plan-v[12].md` and `docs/aurora-demo-script.md`**: planning artifacts owned by the planning skill, not D1; they are allowlisted in the grep guard.

## Corrected math

- 7 working days from 2026-04-30 to 2026-05-11 (excluding 5/2, 5/3, 5/9, 5/10).
- D1 = 0.5–0.75d (was 0.5d). Wider scope (backend + lockfiles + 4 fonts).
- D2 = 0.5d. Unchanged.
- D2.5 = 0.25d (new). Add 1 wall-time pytest, capture baseline.
- D3 = 1.5–2d (was 1–2d). Realistic Chrome MCP probe cost.
- Total ≈ 2.75–3.5 days. **Buffer = 3.5–4.25 working days**. Still passes; tighter than v1 claimed.

## Corrected KPIs & gates

### North Star (unchanged, but with leading proxy)
**Demo-day**: % judges recall lives-saved 30 min after demo ≥ 60%.
**Leading (NEW, v2)**: by **2026-05-12**, % of n=3 internal pre-demo viewers who can name the lives-saved number 5 min after watching ≥ 60%.

### Input metrics (revised)
| # | Metric | Definition | Today | Target | Phase |
|---|---|---|---|---|---|
| 1 | Mirofish strings (widened scope) | `git grep -i mirofish frontend/src frontend/index.html backend/app docker-compose.yml .env.example package-lock.json backend/uv.lock README.md \| wc -l` minus allowlist count | ~50 | 0 | D1 |
| 2 | Bundle gz total | `npm run build` JS+CSS gz | 231.69 kB | ≤ **270 kB** (loosened to absorb 4 npm font families) | D1 |
| 3 | README accuracy | (Aurora ≥ 10) AND (mirofish == 0) AND (every cited wall-time has pytest backing within ±20%) | 0/3 | 3/3 | D2 + D2.5 |
| 4 | Screenshots | `ls docs/screenshots/*.png \| wc -l` | 0 | ≥ 12 | D3 |
| 5 | E2E demo seed cold-to-result wall time | Stopwatch `?seed=demo` page load → result reveal complete, after **enhanced prewarm** (1 model load + 1 full demo-seed MC trial) | unknown | ≤ 90s | D3 |

### HEART thresholds (numbers, not quotes)
| Dimension | Metric | Red flag |
|---|---|---|
| Happiness | ≥ 60% internal viewers rate demo ≥ 4/5 credibility (Likert, n=3) | < 60% |
| Engagement | Time from `/aurora?seed=demo` cold load → user click ≥ 30s spent watching | < 30s = page didn't engage |
| Adoption | % of cold visitors reaching result reveal | < 80% |
| Retention | 30-min recall (= North Star) | < 60% |
| Task Success | % of `?seed=demo` runs that complete without error on n=5 attempts | < 100% (5/5 — no demo-day flakiness allowed) |

### Phase exit criteria (v2 — every gate has a number, all gaps closed)

#### D1 exit
- `git grep -li mirofish frontend/src frontend/index.html backend/pyproject.toml docker-compose.yml .env.example` returns **0 matches** (allowlisting `docs/license-decision.md`, `frontend/CHINESE_TEXT_INVENTORY.md`, `docs/progress.md`, `ROADMAP.md`, the demo-readiness plan files themselves, and the test guard's self-references).
- README is **deferred to D2** (D2 full-rewrites it; D1 only adds an 8-line volume-reset block with `<!-- D1: neo4j-volume-reset -->` markers).
- `backend/app/*` mirofish references (logger channel names, docstrings, JSON-doc comments) are **explicitly out of D1 scope** to avoid silently changing log filters. The 2 functional defaults that DO matter (`SECRET_KEY` and `NEO4J_PASSWORD` in `backend/app/config.py`) are companion fixes folded into D1 because they pair with the env/compose password change.
- Lockfiles (`package-lock.json`, `backend/uv.lock`) auto-regenerate; not grep-gated.
- `grep -c "fonts.googleapis.com\|fonts.gstatic.com" frontend/index.html` = **0**.
- `npm run build` reports **JS gz ≤ 230 kB AND CSS gz ≤ 40 kB**, total ≤ 270 kB. (Loosened to absorb 4 npm font families: ~18 kB gz expected.)
- Browser tab title on `/aurora` = exact string **"Aurora — City Resilience Digital Twin"** (verified by `grep -A0 "<title>" dist/index.html`).
- `grep -rn "document.title" frontend/src` returns 0 OR every match writes "Aurora".
- `cat docker-compose.yml | grep NEO4J_PASSWORD` shows the new password value, AND README quickstart documents `docker volume rm neo4j_data` for users with a stale volume.
- 46/46 backend + frontend tests still pass.

#### D2 exit
- `wc -l README.md` ∈ **[250, 450]**.
- All 9 required sections present (`grep -c "^## "` ≥ 9).
- `grep -i "MiroFish\|mirofish-offline" README.md` = **0**.
- Every wall-time number cited in README has a corresponding **`pytest-benchmark` or assertion-with-timing** test that lands within ±20% of the stated value (D2.5 ships these tests; D2 cites them).
- Every link in README to a local file resolves: `grep -oE '\]\(\.?\.?\/[^)]+\)' README.md | xargs -I{} test -e {}`.

#### D2.5 exit (new)
- `backend/tests/test_aurora_perf.py` exists with **at least 2** wall-time assertions:
  - `test_mc_trial_under_500ms_offline_synth` — single trial, n_population=30, no LLM, asserts wall_seconds < 0.5s
  - `test_mc_30trials_under_30s_offline_synth` — 30 trials × n_population=30, no LLM, asserts total wall < 30s
- README only cites numbers covered by these tests.

#### D3 entry (new)
- **Pre-flight**: `mcp__Claude_in_Chrome__list_connected_browsers` reports ≥ 1 connected browser.
- **Pre-flight**: `mcp__computer-use__list_granted_applications` reports Chrome granted at "read" tier.
- **Pre-flight**: prod build + preview running (`npm run build && npm run preview` on port 4173) — backend on 5001, frontend prod preview on 4173, all serving 200 on a smoke `curl /aurora`.
- If any pre-flight fails, halt — do not consume Chrome MCP retry budget.

#### D3 exit
- 12 screenshots in `docs/screenshots/`, each 30 kB ≤ size ≤ 2 MB, valid PNG (`file` reports PNG image data).
- `docs/screenshots/00-reduce-motion-toggle.png` exists, capturing macOS Accessibility panel with Reduce motion ON (audit trail).
- 5 consecutive `?seed=demo` runs all complete (`task success = 5/5` — no flake budget).
- Cold-to-result wall time on `?seed=demo` with **enhanced prewarm** ≤ **90s** measured by Bash time on the curl-to-curl boundary, NOT eyeballed.
- Failure-path screenshot 12 captures the visible "Try without Gemma 4" button — triggered via `?force_llm_error=1` query param (deterministic) if `pkill ollama` timing window is fragile.
- Chrome and computer-use connectors stayed live throughout (no mid-batch reconnects).

### Universal exit criteria
Same as v1: tests green, bundle ≤ 320 kB, no new mirofish references, reviewer signs off.

### Stop conditions (project-level)
- By **2026-05-08 (T-10 days)** no full E2E lands cleanly → halt, drop screenshots #11–#12, ship 10 happy-path frames.
- Chrome MCP fails 3 successive runs → switch to QuickTime screen recording, lose audit trail, accept.
- D1 grep test still finds matches after **2 fix iterations** → halt, deliver checklist to user.
- README balloons over 600 lines → halt, ask for cuts.
- Internal viewer recall (leading proxy) by 2026-05-12 < 40% → halt, the demo doesn't communicate; redesign the reveal.

## Updated test-first scaffold (per phase, with edge cases folded in)

### D1
- *Unit-1*: widened-scope grep returns 0 (mirofish across all listed paths).
- *Unit-2*: fonts.googleapis.com count = 0 in `frontend/index.html`.
- *Unit-3*: bundle JS gz ≤ 230 kB after build.
- *Unit-4*: every `document.title` write in `frontend/src` writes "Aurora …".
- *Integration*: prod build, `dist/index.html` has Aurora title and zero mirofish/googleapis strings.
- *Integration*: clean docker-compose volume up — backend reaches Neo4j, `/aurora?seed=demo` returns 200.
- *Misuse*: bad logo `src` in Home.vue → `@error` handler renders fallback wordmark, no broken-image icon.

### D2
- *Unit-1*: `wc -l README.md` ∈ [250, 450].
- *Unit-2*: section count ≥ 9.
- *Unit-3*: zero mirofish, ≥ 10 Aurora hits.
- *Unit-4*: every `\d+(\.\d+)?\s*(ms|s|kB|MB)` extracted from README has a matching pytest assertion (regex extractor + grep over D2.5 tests).
- *Integration*: every relative link resolves on disk.
- *Misuse*: insert a fake "MC trial in 1ms" claim → unit-4 fails (proves the cross-check works).

### D2.5
- *Unit*: 2 perf tests run in pytest (`pytest backend/tests/test_aurora_perf.py -v`) and both pass.
- *Integration*: README's quoted timings come from the perf-test output (cite test names in README footnotes).
- *Misuse*: bump n_trials to 1000 in the perf test → it fails (proves the assertion is real, not vacuous).

### D3
- *Unit*: 12 PNGs, valid file headers, in size band.
- *Unit*: pre-flight checks pass (chrome connector + computer-use grant).
- *Integration*: `?seed=demo` cold-to-result ≤ 90s on warm Ollama, 5-of-5 successful runs.
- *Misuse*: Chrome moved to background mid-batch → next computer-use screenshot returns error (proves we'd notice, not silently capture wrong app).

## Ready-to-start step

**One decision needed from user**: pick one of:
- **(a) ship D1 → D2 → D2.5 → D3 strictly serial** (~3.5 days, safest, narrowest blast radius). Recommended.
- **(b) D1 + D2 + D2.5 in parallel, then D3** (~3 days, files don't collide; D3 cannot start until all 3 land). One-day savings, slight merge-conflict risk if D1's fontsource changes touch the same `frontend/package.json` chunk D2's pytest-benchmark dep also touches.

After greenlight: invoke `phases-execution` skill with this v2 plan as the input and the chosen sequencing.
