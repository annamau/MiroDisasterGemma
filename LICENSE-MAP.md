# License map

This repository is dual-licensed. Different files are released under different licenses based on contributor history.

## Apache License 2.0 (Aurora subset)

The following paths are licensed under the [Apache License 2.0](LICENSE-APACHE). Sole contributor: `annamau`.

### Backend
- `backend/app/aurora/**`
- `backend/app/api/scenario.py`
- `backend/tests/test_aurora.py`

### Frontend
- `frontend/src/api/aurora.js`
- `frontend/src/components/aurora/**`
- `frontend/src/views/AuroraView.vue`
- `frontend/src/design/**`
- `frontend/src/composables/useMCStreaming.js` (when added in M5'-A)
- `frontend/src/assets/fonts/**` (third-party fonts shipped under their own OFL/Apache terms)
- `frontend/public/aurora/**`
- `frontend/tests/components/schematic-map.test.js`
- `frontend/tests/components/aurora/**` (when added)
- `frontend/tests/composables/**` (when added)

### Documentation
- `docs/aurora-*.md`

Each file in this subset carries an `SPDX-License-Identifier: Apache-2.0` header.

## GNU AGPL v3.0-or-later (legacy MiroFish surface)

Everything else in the repository remains under the [GNU Affero General Public License v3.0-or-later](LICENSE), inherited from the upstream MiroFish project. Multiple contributors hold copyright on these files; they cannot be relicensed without each contributor's consent.

The legacy surface includes (non-exhaustive):
- `backend/app/services/oasis_profile_generator.py`, `simulation_runner.py`, `report_agent.py`, `graph_tools.py`, `simulation_*.py`
- `backend/app/api/{simulation,report,graph}.py`
- `frontend/src/views/{Home,MainView,Process,SimulationRunView,SimulationView,ReportView,InteractionView}.vue`
- `frontend/src/components/{GraphPanel,HistoryDatabase,Step1GraphBuild,Step2EnvSetup,Step3Simulation,Step4Report,Step5Interaction}.vue`
- `frontend/src/views/Home.css`, `frontend/public/home-styles.css`
- `frontend/src/api/{graph,report,simulation}.js`

Files in this surface either carry no SPDX header (default to AGPL per the root `LICENSE` and this map) or an explicit `SPDX-License-Identifier: AGPL-3.0-or-later` header.

## Why two licenses?

The Aurora City Resilience Prevention Lab is a clean-slate codebase under `backend/app/aurora/` and `frontend/src/{api/aurora.js, components/aurora/, views/AuroraView.vue, design/}`. It does not import any AGPL-licensed code. All `camel-ai` and `camel-oasis` Python dependencies it transitively touches are themselves Apache-2.0. The Aurora subset can therefore safely be released under Apache-2.0, which is the license required by the Gemma 4 Good Hackathon submission.

The legacy MiroFish surface was contributed under AGPL by upstream authors and remains under AGPL. The Aurora demo does not exercise these files.

## How to verify

```sh
# Verify no AGPL imports inside the Aurora subset
grep -rE "^from oasis|^import oasis|^from camel|^import camel" backend/app/aurora/ || echo "clean"

# Verify SPDX headers on Aurora files
grep -L "SPDX-License-Identifier: Apache-2.0" backend/app/aurora/*.py
```

## Questions

If you are an upstream contributor and believe a file is misclassified in this map, please open an issue.
