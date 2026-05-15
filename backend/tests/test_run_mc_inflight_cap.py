# SPDX-License-Identifier: Apache-2.0
"""
Phase 2a — Per-scenario in-flight cap on /run_mc?streaming=true.

Falsifying gate: when a streaming MC run is already active for a
scenario, a second POST must return the SAME run_id with
status="already_running" instead of spawning a second worker thread
(which would OOM the macmini Ollama on Re-run-spam).

Flask's default test_client is single-threaded, so the threads below
serialise. The cap must still be correct in that ordering: the first
request creates the run, every subsequent request while
no _result/_error has landed must return the existing run_id.
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app  # noqa: E402
from app.api import scenario as _scenario_mod  # noqa: E402


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _clear_mc_progress():
    """Each test starts with an empty progress store."""
    with _scenario_mod._MC_PROGRESS_LOCK:
        _scenario_mod._MC_PROGRESS.clear()
    yield
    with _scenario_mod._MC_PROGRESS_LOCK:
        _scenario_mod._MC_PROGRESS.clear()


def test_inflight_cap_returns_same_run_id(client):
    """M-3 (misuse) — 5 serial POSTs to the same scenario, with a
    fake "in-flight" entry seeded in _MC_PROGRESS, must all collapse
    onto a single run_id.

    We seed an in-flight entry by hand because Flask's test_client
    doesn't safely support overlapping concurrent calls — the cap
    logic is what we're testing, not Flask's threading. Production
    callers hit the same lock under Waitress/gunicorn just fine."""
    # Seed an "active" run for LA: it exists in _MC_PROGRESS, no
    # _result / _error yet → second POST must return THIS run_id.
    seeded_run_id = "seedabcd"
    with _scenario_mod._MC_PROGRESS_LOCK:
        _scenario_mod._MC_PROGRESS[seeded_run_id] = {
            "recent_decisions": [],
            "_scenario_id": "la-puente-hills-m72-ref",
        }

    payload = {
        "intervention_ids": [],
        "n_trials": 1,
        "n_population_agents": 20,
        "duration_hours": 4,
        "use_llm": False,
        "streaming": True,
    }
    results: list[dict] = []
    for _ in range(5):
        r = client.post(
            "/api/scenario/la-puente-hills-m72-ref/run_mc",
            json=payload,
        )
        assert r.status_code == 202
        results.append(r.get_json())

    run_ids = {r["data"]["run_id"] for r in results}
    # All 5 must collapse onto the seeded run_id.
    assert run_ids == {seeded_run_id}, (
        f"Expected all 5 requests to return seeded run_id "
        f"{seeded_run_id!r}; got {run_ids}"
    )
    statuses = [r["data"].get("status") for r in results]
    assert all(s == "already_running" for s in statuses), (
        f"Expected every response to be 'already_running'; got {statuses!r}"
    )


def test_inflight_cap_is_per_scenario(client):
    """Different scenarios must get different run_ids — the cap is
    keyed on scenario_id, not global."""
    payload = {
        "intervention_ids": [],
        "n_trials": 1,
        "n_population_agents": 20,
        "duration_hours": 4,
        "use_llm": False,
        "streaming": True,
    }
    r1 = client.post(
        "/api/scenario/la-puente-hills-m72-ref/run_mc", json=payload,
    )
    r2 = client.post(
        "/api/scenario/valencia-dana-2024/run_mc", json=payload,
    )
    assert r1.status_code == 202
    assert r2.status_code == 202
    id1 = r1.get_json()["data"]["run_id"]
    id2 = r2.get_json()["data"]["run_id"]
    assert id1 != id2, (
        "In-flight cap must be per-scenario; LA and Valencia should "
        f"both get fresh run_ids (got both = {id1!r})"
    )
    # The status of the second call must NOT be already_running — it
    # is a different scenario.
    assert r2.get_json()["data"].get("status") != "already_running"


def test_inflight_cap_progress_endpoint_hides_scenario_id(client):
    """The _scenario_id field on a progress entry must NOT leak into
    the public /progress arms snapshot — it's an underscore-prefix
    private field per the existing filter at line ~851."""
    payload = {
        "intervention_ids": [],
        "n_trials": 1,
        "n_population_agents": 20,
        "duration_hours": 4,
        "use_llm": False,
        "streaming": True,
    }
    r = client.post(
        "/api/scenario/la-puente-hills-m72-ref/run_mc", json=payload,
    )
    assert r.status_code == 202
    run_id = r.get_json()["data"]["run_id"]
    p = client.get(
        f"/api/scenario/la-puente-hills-m72-ref/run_mc/{run_id}/progress",
    )
    assert p.status_code == 200
    arms = p.get_json()["data"]["arms"]
    assert "_scenario_id" not in arms, (
        "_scenario_id is a private progress field and must NOT appear "
        f"in the public arms snapshot. Got arms={arms!r}"
    )
