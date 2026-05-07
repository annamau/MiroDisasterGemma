# SPDX-License-Identifier: Apache-2.0
"""
Golden-file regression test for all 6 reference scenarios.

Strategy
--------
Run each scenario through run_monte_carlo with a fixed, minimal config
(n_trials=3, duration_hours=24, n_population_agents=80, use_llm=False,
intervention_ids=[] i.e. baseline only).  Capture the tuple:

    (scenario_id,
     baseline.deaths.point,
     baseline.injuries.point,
     baseline.economic_loss.point,
     sorted list of (district_id, deaths_sum) from raw trials)

Save to backend/tests/golden/scenario_outputs.json on first run (or when
UPDATE_GOLDEN=1 env var is set).  On subsequent runs assert the captured
tuple matches verbatim.

The golden file MUST be generated against an unmodified scenario_loader
(before any J0a migration changes) so that the file encodes the
ground-truth output.  After the migration the test must still pass —
that is the load-bearing gate.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.api.scenario import REFERENCE_BUILDERS  # noqa: E402
from app.aurora.monte_carlo import run_monte_carlo  # noqa: E402
from app.aurora.decision_cache import DecisionCache  # noqa: E402

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_FILE = GOLDEN_DIR / "scenario_outputs.json"

# Fixed parameters — small enough to run in <30s total on a laptop.
_N_TRIALS = 3
_DURATION_HOURS = 24
_N_AGENTS = 80
_BASE_SEED = 1000


def _capture_scenario(scenario_id: str) -> dict[str, Any]:
    """Build scenario, run baseline MC, return a JSON-safe snapshot dict."""
    builder = REFERENCE_BUILDERS[scenario_id]
    scn = builder()

    # Fresh cache per scenario so cache state doesn't bleed across runs
    cache = DecisionCache()

    run = run_monte_carlo(
        scn,
        intervention_ids=[],          # baseline only
        n_trials=_N_TRIALS,
        base_seed=_BASE_SEED,
        duration_hours=_DURATION_HOURS,
        n_population_agents=_N_AGENTS,
        llm_call=None,                 # no LLM — fully deterministic
        cache=cache,
    )
    baseline = run.baseline

    # Aggregate deaths_by_district across all raw trials (summed, then
    # converted to a sorted list of [did, deaths] pairs).  JSON has no
    # tuple type, so we serialize as list-of-lists; using `sorted(...)`
    # alone returns tuples and would fail the strict `==` after JSON
    # round-trip against a list-of-lists golden file.
    agg_dbd: dict[str, int] = {}
    for trial in baseline.trials:
        for did, deaths in trial.deaths_by_district.items():
            agg_dbd[did] = agg_dbd.get(did, 0) + deaths
    sorted_dbd = [list(item) for item in sorted(agg_dbd.items())]

    return {
        "scenario_id": scenario_id,
        "deaths_point": baseline.deaths.point,
        "injuries_point": baseline.injuries.point,
        "economic_loss_point": baseline.economic_loss_usd.point,
        "deaths_by_district_sorted": sorted_dbd,
    }


def _load_golden() -> dict[str, Any]:
    return json.loads(GOLDEN_FILE.read_text())


def _write_golden(data: dict[str, Any]) -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    GOLDEN_FILE.write_text(json.dumps(data, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# The actual test
# ---------------------------------------------------------------------------

def test_all_scenarios_match_golden():
    """Assert every scenario's MC output matches the captured golden values.

    Set env var UPDATE_GOLDEN=1 to regenerate the golden file (do this
    BEFORE any schema migration to capture the ground truth).
    """
    update_mode = os.environ.get("UPDATE_GOLDEN", "0").strip() not in ("", "0", "false", "False")

    captured: dict[str, Any] = {}
    for scenario_id in REFERENCE_BUILDERS:
        captured[scenario_id] = _capture_scenario(scenario_id)

    if update_mode or not GOLDEN_FILE.exists():
        _write_golden(captured)
        # On first generation we skip the assertion — the file IS the truth.
        pytest.skip(
            f"Golden file written to {GOLDEN_FILE} — re-run without "
            "UPDATE_GOLDEN=1 to validate."
        )

    golden = _load_golden()

    for scenario_id, current in captured.items():
        assert scenario_id in golden, (
            f"Scenario {scenario_id!r} missing from golden file. "
            "Run with UPDATE_GOLDEN=1 to regenerate."
        )
        expected = golden[scenario_id]
        assert current["deaths_point"] == expected["deaths_point"], (
            f"{scenario_id}: deaths_point {current['deaths_point']} != "
            f"golden {expected['deaths_point']}"
        )
        assert current["injuries_point"] == expected["injuries_point"], (
            f"{scenario_id}: injuries_point {current['injuries_point']} != "
            f"golden {expected['injuries_point']}"
        )
        assert current["economic_loss_point"] == expected["economic_loss_point"], (
            f"{scenario_id}: economic_loss_point {current['economic_loss_point']} != "
            f"golden {expected['economic_loss_point']}"
        )
        assert current["deaths_by_district_sorted"] == expected["deaths_by_district_sorted"], (
            f"{scenario_id}: deaths_by_district_sorted mismatch\n"
            f"  current:  {current['deaths_by_district_sorted']}\n"
            f"  expected: {expected['deaths_by_district_sorted']}"
        )
