# Aurora demo-readiness plan v1

**Status:** DRAFT — pending red-team review.

## Goal
Aurora is hackathon-recordable by **2026-05-11 (T-7 days before May 18 deadline)**: a fresh `git clone` → `?seed=demo` → recorded run → screenshot deliverables, with **zero "MiroFish" string visible to a judge** and a README that describes Aurora (not the legacy product).

## Current state (concrete)
- Branch: `phase/aurora-v2-atomics` — P-V0…P-V5 shipped. Bundle 231.69 kB gz. 46/46 tests (27 backend + 19 frontend).
- **38 tracked files contain "mirofish"** (from `git grep -li mirofish`). Six are binary image assets (`MiroFish_logo.jpeg`, `MiroFish_logo_compressed.jpeg`, `MiroFish_logo_left.jpeg`, `mirofish-offline-banner.png`, `mirofish-offline-screenshot.jpg`, plus a duplicate under `frontend/src/assets/logo/`).
- **Page chrome leaks legacy strings**: `frontend/index.html:10–11` sets `<meta name="description" content="MiroFish Offline...">` and `<title>MiroFish Offline - Predict Everything</title>`. The `/aurora` page renders inside this shell — the browser tab name during the demo recording would say "MiroFish Offline".
- **Offline claim is technically broken**: `frontend/index.html:5` loads `https://fonts.googleapis.com/...`. Aurora's "runs offline" pitch fails an airplane-mode test (Inter Variable IS bundled via npm but the index.html still has the legacy Google Fonts `<link>`).
- README.md (205 lines) describes the OLD MiroFish-Offline product (PR/policy public-opinion sim, qwen2.5/llama3, Zep→Neo4j migration story). Zero mention of Aurora, Gemma 4, the disaster-prevention pivot, or any of the 4 agent classes.
- `.env.example` line 2: `NEO4J_PASSWORD=mirofish` (in-band string, used as a default password — changing it breaks docker-compose.yml's NEO4J_AUTH).
- `backend/pyproject.toml`: project name = `mirofish-offline-backend`, description = "MiroFish-Offline - Offline-first fork...". Internal package imports use `app.*` (not `mirofish.*`), so renaming the project name is safe; description is text-only.
- Chrome MCP tools verified available via ToolSearch: `mcp__Claude_in_Chrome__navigate`, `find`, `read_page`, `browser_batch`. Native screenshot is via `computer-use__screenshot` (the chrome MCP itself does not expose a screenshot tool — that is a real constraint).
- Chrome is "read"-tier under computer-use rules: clicks blocked while Chrome is the frontmost app from that path. **Chrome MCP is the driver**, computer-use is the screenshot path. The two share allowlist state.

## Phases

### Phase D1 — Mirofish purge (low risk, must precede screenshots)
**Why this slot first**: any screenshot taken before the purge captures legacy strings, contaminates the screenshot deliverable, and forces a re-run.

**Files changed (~15)**:
- `frontend/index.html` — `<title>`, `<meta name="description">`, drop the Google Fonts `<link>` (Inter Variable already bundled in P-V1; preserves offline claim)
- `frontend/package.json` — `name: "frontend"` (already not "mirofish") — no change needed; verify
- `frontend/src/views/Home.vue` — github link, "MiroFish Offline" body copy, alt text on logo image
- `frontend/src/views/MainView.vue` — search and replace
- `frontend/src/components/Step5Interaction.vue:158` — string in tooltip
- `frontend/src/components/Step2EnvSetup.vue:443` — string in copy
- `frontend/src/views/InteractionView.vue`, `Process.vue`, `ReportView.vue` — sweep
- Replace `frontend/src/assets/logo/MiroFish_logo_left.jpeg` reference in Home.vue with placeholder text or new Aurora wordmark (don't delete the file yet — `Home.vue` uses it; either swap to a text-only header or generate a simple SVG wordmark in-repo)
- `backend/pyproject.toml` — `name = "aurora-backend"`, `description = "Aurora — City Resilience Digital Twin"`. Keep Python module paths as-is (`app.*`).
- `.env.example` — `NEO4J_PASSWORD=aurora` (and matching `docker-compose.yml` NEO4J_AUTH); requires verifying both files stay consistent
- `docs/license-decision.md`, `docs/progress.md` — leave (historical record, not user-facing)
- `frontend/CHINESE_TEXT_INVENTORY.md` — leave (legacy artifact, no demo visibility)
- `ROADMAP.md` — touch only the title/intro paragraph; body is project history

**OUT of scope (intentionally not changed)**:
- Git history, branch names, repo directory name on disk
- Backend Python module imports (`app.aurora.*` already exists; there's no `mirofish` package to rename)
- The 6 `MiroFish_*.jpeg` / `mirofish-offline-*.png` files in `static/image/` — leave them on disk but make sure no template references them. Deletion is risky (build cache, docker-compose volumes).
- `backend/uv.lock` (auto-regenerated) — `pyproject.toml` rename triggers a relock
- Comments inside Python files referencing "mirofish" as a project name (not user-visible)

**Test scaffold (write FIRST)**:
- *Unit*: `tests/test_no_mirofish_in_frontend.sh` — bash script that runs `git grep -i "mirofish" frontend/src frontend/index.html | grep -v 'CHINESE_TEXT_INVENTORY\|//.*legacy'` and exits non-zero if any matches in user-visible files.
- *Unit*: `tests/test_offline_index.sh` — `grep -c "fonts.googleapis.com\|fonts.gstatic.com" frontend/index.html` must return 0.
- *Integration*: `npm run build && grep -ri "MiroFish\|mirofish-offline" frontend/dist` returns zero matches in `dist/index.html` and `dist/assets/index*.css|js`.
- *Misuse*: re-run `?seed=demo` after purge — backend and frontend boot, all routes return 200, no 404 on logo asset (someone might delete the JPEG without removing the `<img>` tag).

**Risk**: medium. Removing the Google Fonts link without re-checking that Inter Variable's npm load actually serves the page on first paint could leave the page using a system fallback for ~50ms (FOUT). The bundled `@fontsource-variable/inter/opsz.css` is the authoritative source, but verifying via DevTools Network panel during prod build is non-negotiable.

### Phase D2 — README rewrite (parallel-safe with D1 if no merge collision; safer to serialize after D1)
**Why this slot**: README references logos and screenshots; the screenshots come from D3, but the README's content does not depend on the screenshots existing yet — placeholders work, and D3 fills them in. The README *content* depends on the **product framing being accurate**, which is independent of D1's string purge.

**Files changed**:
- `README.md` — full rewrite, 250–450 lines
- `docs/aurora-architecture.md` — NEW, ~80 lines, technical reference linked from README (4-agent-class diagram in ASCII, intervention DSL grammar, monte_carlo orchestration)

**Required README sections (verbatim from user spec)**:
1. Title + tagline
2. Problem (why disaster prevention needs simulation)
3. What Aurora does (4 agent classes + intervention DSL + MC reveal)
4. Gemma 4 angle (Apache 2.0, e2b/e4b roles, 128K, multimodal, PLE, function calling)
5. Quickstart (3 commands: prewarm + backend + frontend)
6. Screenshots (placeholders during D2, filled by D3)
7. Benchmarks (n_trials × n_population × wall time on M-series — must be reproducible)
8. What's next
9. License (AGPL-3.0 + Gemma 4's Apache 2.0 — no conflict)

**OUT of scope**:
- Marketing claims that aren't load-bearing (no "10,000 agents per second" — only what the wall-clock data supports)
- Architectural diagrams that require new tooling (ASCII only — no mermaid, no diagrams.net)

**Test scaffold (write FIRST)**:
- *Unit*: `wc -l README.md` returns 250–450.
- *Unit*: `grep -c "Aurora" README.md` ≥ 10 (the product name must be invoked frequently); `grep -c "MiroFish\|MiroFish-Offline" README.md` = 0.
- *Unit*: required-section grep — every one of the 9 required headings must appear (`grep -c "^## " README.md` ≥ 9).
- *Integration*: every link in README that points to a local file resolves (`grep -oE '\]\(\.?\.?\/[^)]+\)' README.md | xargs -I{} test -e {}`).
- *Misuse*: a benchmark line that cites a wall-time number must be reproducible by `pytest backend/tests/test_aurora.py::test_monte_carlo_runs_offline_and_produces_paired_deltas` — if the README claims "MC trial in 123ms offline", pytest must show that number ±20%.

**Risk**: low. Pure content. Worst case is overclaiming, which the misuse test catches.

### Phase D3 — Chrome E2E + screenshot pack (highest risk, depends on D1)
**Why this slot last**: D3 captures pixels that prove the demo works. Capturing before D1 means re-shooting after string purge.

**Files added**:
- `docs/screenshots/` — 12 PNG files (defined below)
- `docs/aurora-e2e-walkthrough.md` — narrative tying screenshots to phase boundaries (auditable by judges)
- `frontend/scripts/e2e-driver.md` — written-down (not code) Chrome MCP recipe so a future dev can reproduce. (Not a Vitest e2e — Chrome MCP requires the connector to be live, can't run unattended in CI.)

**Files NOT changed**: zero production code. Pure validation.

**The screenshot pack (12 frames)**:
| # | When | What | Validates |
|---|---|---|---|
| 1 | Cold load `/` (root) | Aurora landing or redirect | No "MiroFish" tab title |
| 2 | `/aurora?seed=demo` t=0s | Skeleton cards rendering | D1 purge complete |
| 3 | `/aurora?seed=demo` t=2s | Scenario cards loaded, demo seed pre-selected | Demo seed wired |
| 4 | t=3s | Intervention chips selected, RunButton "running" | Auto-run fired |
| 5 | t=10s | MCProgressPanel mid-run, ≥1 bar partial, AgentLogTicker has ≥1 entry | Streaming works |
| 6 | t=20s | Progress further along | Bars tween smoothly (verify by DevTools FPS) |
| 7 | done | Result reveal, HeroNumber CountUp mid-tween | Reveal animation exists |
| 8 | done+2s | Result fully revealed, DeltaCards staggered in | All 4 components composed |
| 9 | scroll down | ComparatorTable bars at final width | Comparator works |
| 10 | scroll down | CumulativeChart paths drawn, end labels visible | Chart works |
| 11 | reduce-motion ON, fresh load | Result reveal lands instantly | a11y guard works |
| 12 | Ollama killed, useLLM=true, run | "Try without Gemma 4" button visible | Error path works |

**Driving recipe (Chrome MCP family)**:
1. `tabs_context_mcp` → get tabId for an open Aurora tab
2. `navigate(tabId, "http://localhost:3000/aurora?seed=demo")`
3. Wait via Bash `sleep 1.5`
4. `read_page(tabId, filter="all", depth=8)` → assert demo seed copy is in the DOM
5. `find(tabId, "running run button")` → assert RunButton state-running visible
6. `computer-use__screenshot({save_to_disk: true})` → save into `docs/screenshots/02-demo-cold.png`
7. Repeat for each of the 12 frames

**Test scaffold (write FIRST)**:
- *Unit*: `ls docs/screenshots/*.png | wc -l` ≥ 12 (count check).
- *Unit*: each PNG file size > 30 kB (placeholder/blank-page guard) and < 2 MB (un-cropped retina).
- *Unit*: `file docs/screenshots/*.png` reports `PNG image data` for all (catch corrupted captures).
- *Integration*: prod build smoke test — `npm run build && (cd dist && python -m http.server 4173) &` — `curl /aurora` returns 200 and the served HTML contains zero `MiroFish` substrings.
- *Misuse*: kill Ollama with `pkill -f "ollama serve"`, run the demo seed flow, screenshot 12 must contain the "Try without Gemma 4" string.

**Risk**: HIGH. Chrome MCP one-shot reliability is unproven for a 60s flow with timed screenshots. Concrete failure modes:
- The connector drops the tabId mid-batch (browser navigation can re-issue tabIds)
- `find()` natural-language query returns the wrong element ("running button" matches both RunButton and a transient log entry)
- Animation timing in CI/headed Chrome differs from the spec (60Hz cap on macOS, but the timing of `done` event vs result reveal CountUp is millisecond-sensitive)
- `computer-use__screenshot` captures the WRONG monitor if the user has multi-display

Mitigations: take 2× the screenshots (24 frames), visually triage. Wrap each screenshot in a **manual checkpoint** — pause, ask the user to confirm before advancing. Don't try to do this in `browser_batch` — sequential is fine; debugability beats round-trip cost.

## Math sanity check
- Time budget today (2026-04-30) → demo recording (2026-05-11): **11 days**. Estimated effort: D1 = 0.5d, D2 = 0.5d, D3 = 1–2d (Chrome MCP probing dominates). Total ≈ 2–3 days. Buffer = 8–9 days. **Realistic**.
- README length: 250–450 lines. Required sections × avg 30 lines = 270 lines. Math closes if every section is concise. Going over 450 means too much marketing.
- Bundle ceiling 320 kB gz; current 231.69 kB. Removing the Google Fonts link saves 0 kB (it's a remote CSS, not bundled), but improves first paint. README does not affect bundle.
- Screenshot count: 12 base + 12 buffer = 24. At ~200 kB per PNG = 4.8 MB. Well under any GitHub size cap.

## Test-first scaffold (consolidated, written before any change)
| Phase | Unit (3+) | Integration (1+) | Misuse (1) |
|---|---|---|---|
| D1 | mirofish-grep, fonts-grep, env-consistency | prod build no-mirofish | logo missing → page renders or fails loud |
| D2 | line count, section count, link resolution | benchmark numbers reproducible by pytest | overclaim → README cites a number not in any test |
| D3 | screenshot count, file size band, PNG validity | prod build serves /aurora 200 | kill Ollama → "Try without Gemma 4" surfaces |

## Open questions
1. **Logo replacement**: Home.vue uses `MiroFish_logo_left.jpeg`. Do we want a new Aurora wordmark image (effort: half-day for an SVG), or a CSS-only text wordmark? **Recommend CSS-only** to avoid binary asset commits.
2. **`.env.example` Neo4j password**: changing `NEO4J_PASSWORD=mirofish` to `aurora` means anyone with an existing Neo4j volume will hit auth failure. Document the override in README quickstart.
3. **`/` (root) route**: currently goes to `Home.vue` which is the legacy MiroFish landing. Demo URL is `/aurora?seed=demo` — but a judge typing the bare domain hits Home.vue. Should `/` redirect to `/aurora`? **Recommend yes**, simple `router.beforeEach` guard.
4. **Screenshot placement in README**: which 4 of the 12 frames go in the README itself? Default: #2 (cold demo), #6 (mid-streaming), #8 (result reveal), #10 (comparator + chart).
5. **CI gate on the mirofish-grep test?** Adding it to the existing test runner means CI fails on legacy file changes. Accept the bus factor or scope the grep to user-visible paths only.

---

# Measurable KPIs & quality gates

## North Star
**% of judges who recall the lives-saved number 30 min after demo ≥ 60%**.
- Definition: in the live judging round / booth interview, ask "what was the lives-saved number Aurora showed?". Externally validated.
- Cadence: post-demo (one-shot for the hackathon).
- Today: N/A (not yet recorded).
- Target by 2026-05-18: ≥ 60% of judges polled.

## Input metrics (5)
| # | Metric | Definition | Today | Target | Phase |
|---|---|---|---|---|---|
| 1 | Mirofish strings in user-visible files | `git grep -i mirofish frontend/src frontend/index.html \| wc -l` | ~12 | 0 | D1 |
| 2 | Bundle gz total | `cd frontend && npm run build` JS+CSS gz | 231.69 kB | ≤ 240 kB | D1 |
| 3 | README accuracy | grep-count of (Aurora ≥ 10) AND (mirofish == 0) | (Aurora=0, mirofish=12) | (Aurora≥10, mirofish=0) | D2 |
| 4 | Screenshots delivered | `ls docs/screenshots/*.png \| wc -l` | 0 | ≥ 12 | D3 |
| 5 | E2E demo seed cold-to-result wall time | Stopwatch `?seed=demo` page load → result reveal complete | unknown | ≤ 90s with warm Ollama | D3 |

## HEART (red-flag thresholds)
| Dimension | Metric | Red flag |
|---|---|---|
| Happiness | Demo viewer says "this is impressive" / "credible" verbatim | "Looks broken", "where's Aurora", "I see MiroFish" |
| Engagement | Time on `/aurora?seed=demo` from cold load to user click | < 30s = page didn't engage |
| Adoption | % of cold visitors who reach the result reveal | < 80% |
| Retention | Recall after 30 min (= North Star) | < 60% |
| Task Success | % of `?seed=demo` runs that complete without error | < 95% |

## Phase exit criteria (numeric, falsifiable)

### D1 exit
- `git grep -li mirofish frontend/src frontend/index.html` returns **0 matches**.
- `grep -c "fonts.googleapis.com\|fonts.gstatic.com" frontend/index.html` = **0**.
- Bundle: `npm run build` + `wc -c dist/assets/index-*.js | awk '{print $1}'` reports **JS gz ≤ 215 kB** (current 203.96 kB; ≤ +5%).
- Browser tab title on `/aurora` = exact string **"Aurora — City Resilience Digital Twin"**.
- 46/46 tests still pass.

### D2 exit
- `wc -l README.md` ∈ **[250, 450]**.
- All 9 required sections present (grep `^## `).
- Zero `MiroFish` / `mirofish-offline` strings in README.
- Every benchmark cited has a corresponding pytest assertion within ±20% of stated value.

### D3 exit
- 12 screenshots in `docs/screenshots/`, each 30 kB ≤ size ≤ 2 MB, valid PNG (`file` reports PNG image data).
- Cold-to-result wall time on `?seed=demo` with warm Ollama ≤ **90s** (P-V5 demo doc gate).
- Reduce-motion screenshot 11 captured AFTER toggling macOS Accessibility → Display → Reduce motion ON; assert `<title>` reads Aurora.
- Failure-path screenshot 12 captures the visible "Try without Gemma 4" button.

## Universal exit criteria (all phases)
- Reviewer subagent on the PR returns zero unresolved correctness findings.
- 46 tests still green; bundle still ≤ 320 kB gz.
- No new files reference legacy paths (mirofish-offline-*, MiroFish_logo*).

## Stop conditions
- D3 fails to produce 12 valid screenshots after **3 attempts** → halt, switch to manual screen recording with QuickTime, accept loss of judge-auditable narrative.
- D1 grep test still finds matches after **2 fix iterations** → halt, deliver a checklist of remaining strings to the user instead of trying to ship a clean grep.
- README rewrite balloons over 600 lines → halt, ask user for explicit cuts.

---

# Stop conditions (project-level)
- If by **2026-05-08 (T-10 days)** no full E2E run lands cleanly, halt and reassess scope (drop screenshots #11 and #12, ship just the happy-path 10).
- If Chrome MCP connector becomes unavailable mid-D3, halt and switch to `puppeteer` headed via Node script (small new dep, but local).

# Ready-to-start step
**Decision needed from user**: pick one of (a) ship D1 → D2 → D3 strictly serial (safest, ~3d), (b) D1 + D2 in parallel (D2 doesn't actually need D1 to start since README content is independent of which Vue strings are clean), then D3 (~2d).

After greenlight: dispatch the phases-execution skill with this plan as the input and the 3-phase split.
