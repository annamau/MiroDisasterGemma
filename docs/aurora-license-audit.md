# Aurora License Audit — N0 deliverable

**Date:** 2026-05-05
**Goal:** decide path to Apache-2.0 for the Gemma 4 Good Hackathon submission.

## Findings

### 1. Repo today is AGPL-3.0
`./LICENSE` is `GNU AFFERO GENERAL PUBLIC LICENSE Version 3`. This is an inherited license — it was set by the upstream MiroFish project before this repo pivoted to Aurora.

### 2. Upstream OASIS / camel deps are Apache-2.0, NOT AGPL
- `camel-oasis 0.2.5` — PyPI license: **Apache-2.0** ✅
- `camel-ai 0.2.78` — GitHub LICENSE: **Apache-2.0** ✅
- The "AGPL" status of the repo is self-imposed, not inherited from any dependency.

### 3. Aurora hot path imports zero AGPL or OASIS code
```
$ grep -r "^import oasis\|^from oasis\|^import camel\|^from camel" backend/app/aurora/
(no matches)
```
- `backend/app/aurora/*.py` — clean, all Apache-2.0-friendly stdlib + numpy + pydantic.
- `backend/app/aurora/population_generator.py:4` only mentions OASIS in a comment ("Replaces the legacy `oasis_profile_generator.py`"); no import.
- All OASIS / camel references live in legacy MiroFish surface: `backend/app/services/oasis_profile_generator.py`, `backend/app/api/simulation.py`, `backend/app/services/report_agent.py`, `backend/app/services/simulation_runner.py`, `backend/app/services/graph_tools.py`. None are reachable from any Aurora API route or Aurora component.

### 4. Contributor analysis on code reachable from Aurora
- **`backend/app/aurora/*`** — sole contributor: `annamau` ✅
- **`frontend/src/components/aurora/*`, `frontend/src/api/aurora.js`, `frontend/src/views/AuroraView.vue`** — sole contributor: `annamau` ✅ (verified via `git log --format='%an' HEAD -- <path>`)
- **Legacy MiroFish surface** (Step1-5 components, `simulation_*` services, `report_agent.py`, etc.): mixed contributors including `Nik`, `nikmcfly`, `Sebastian Mäki`, `eugeniozamengopontrelli`, `robbie-tench`, `thousand flowers`. Cannot relicense without consent of every upstream contributor.

## Decision: dual-license the Aurora subset only

The hackathon submission ships the **Aurora subset** (≈90% of what we'll demo) under **Apache License 2.0**. The legacy MiroFish surface stays under AGPL-3.0. The repo gets a clear `LICENSE` + `LICENSE-APACHE` split with a `LICENSE-MAP.md` enumerating which files are Apache-2.0 and which are AGPL-3.0.

### What ships under Apache-2.0
- `backend/app/aurora/**`
- `backend/app/api/scenario.py` (Aurora-only API surface, sole contributor: `annamau`)
- `backend/tests/test_aurora.py`
- `frontend/src/api/aurora.js`
- `frontend/src/components/aurora/**`
- `frontend/src/views/AuroraView.vue`
- `frontend/src/design/**` (we'll create new files here under N1; all `annamau`)
- `frontend/tests/components/schematic-map.test.js` and other Aurora tests
- `docs/aurora-*.md`

### What stays AGPL-3.0
Everything else in the tree (Step1-5 MiroFish components, OASIS profile generator, legacy report agent, etc.). These are present in the repo for historical reference but the hackathon demo does not exercise them.

### What this means in practice for the hackathon
1. Hackathon submission's repo URL = this repo with the dual-license file structure.
2. Submission write-up explicitly says: "The Aurora subset (`backend/app/aurora`, `frontend/src/{api/aurora.js, components/aurora, views/AuroraView.vue, design}`, and Aurora tests/docs) is licensed under Apache-2.0. The remainder of the repo is legacy upstream code under AGPL-3.0 and is not exercised by the demo." Reviewers can verify by running the Aurora-only subset in isolation.
3. We add an Apache-2.0 LICENSE-APACHE file at the repo root.
4. Each Aurora-subset file gets a top-of-file SPDX header: `# SPDX-License-Identifier: Apache-2.0`. Files outside the Aurora subset get `# SPDX-License-Identifier: AGPL-3.0-or-later`. This makes the split machine-readable.
5. The current root `LICENSE` (AGPL) stays — Apache lives in `LICENSE-APACHE`. README updated to point to both + `LICENSE-MAP.md`.

### Effort
- Step 4 (SPDX headers across ~20 Aurora files) — automated with a script, ≤10 minutes.
- Step 3 (LICENSE-APACHE file) — paste from https://www.apache.org/licenses/LICENSE-2.0.txt, 1 minute.
- Step 5 (README + LICENSE-MAP.md) — 15 minutes.
- **Total: ≤ 0.05d.** Original v3 estimate was 0.5d; came in well under because the OASIS deps turned out to be Apache-2.0 themselves.

## Stop conditions hit?
None. v3 plan said "if OASIS removal takes > 1d, halt and notify." OASIS is not the blocker we feared. Proceeding with N0 commit.

## Action items for N0d commit
1. Add `LICENSE-APACHE` at repo root.
2. Add `LICENSE-MAP.md` enumerating the Aurora subset.
3. Add SPDX headers to the Aurora subset files.
4. Update `README.md` license section.
5. Commit the v3 plan docs (`aurora-experience-v3.md`, `aurora-experience-v3-DRAFT.md`, this audit).
6. Commit the N0a/N0c UI cleanups already in the working tree.
