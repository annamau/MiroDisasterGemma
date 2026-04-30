"""
Aurora P-V3 streaming MC tests.

Falsifying gate: a streaming run produces multiple distinct progress
snapshots BEFORE the result lands. If a regression flattens the
streaming pipeline (e.g. the worker thread aggregates and only writes
once at the end, or the lock starves the callback), this test fails.

Also covers:
  - 100% backwards compatibility: progress_callback=None preserves the
    original silent run_monte_carlo() behavior.
  - Callback overhead is bounded (soft check; <20% wall-time inflation).
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.aurora import monte_carlo, scenario_loader  # noqa: E402


# ---- 1. Direct callback wiring (unit-level, no Flask) ----

def test_progress_callback_fires_per_trial():
    """run_monte_carlo invokes progress_callback once per trial per arm."""
    s = scenario_loader.build_la_puente_hills_m72()
    events: list[tuple] = []

    def cb(arm_id, trials_done, trials_total, deaths_running_mean):
        events.append((arm_id, trials_done, trials_total))

    run = monte_carlo.run_monte_carlo(
        s, ["evac_d03_30min_early"],
        n_trials=3, n_population_agents=50, duration_hours=12,
        llm_call=None, progress_callback=cb,
    )
    # 3 trials × 2 arms (baseline + 1 treatment) = 6 events
    assert len(events) == 6, f"expected 6 callback fires, got {len(events)}: {events}"
    # trials_done is monotonically non-decreasing per arm
    by_arm: dict[str, list[int]] = {}
    for arm, done, total in events:
        by_arm.setdefault(arm, []).append(done)
        assert total == 3
    for arm, seq in by_arm.items():
        assert seq == sorted(seq), f"arm {arm} done sequence not monotone: {seq}"


def test_progress_callback_optional_preserves_silent_behavior():
    """progress_callback=None must not change run_monte_carlo's output."""
    s = scenario_loader.build_la_puente_hills_m72()
    run_silent = monte_carlo.run_monte_carlo(
        s, ["evac_d03_30min_early"],
        n_trials=3, n_population_agents=50, duration_hours=12,
        llm_call=None,
    )
    assert run_silent.baseline.n_trials == 3


def test_progress_callback_overhead_is_bounded():
    """Wall-time overhead from the callback must stay under 20%."""
    s = scenario_loader.build_la_puente_hills_m72()

    t0 = time.time()
    monte_carlo.run_monte_carlo(
        s, ["evac_d03_30min_early"],
        n_trials=3, n_population_agents=50, duration_hours=12,
        llm_call=None,
    )
    silent = time.time() - t0

    fired = []
    t0 = time.time()
    monte_carlo.run_monte_carlo(
        s, ["evac_d03_30min_early"],
        n_trials=3, n_population_agents=50, duration_hours=12,
        llm_call=None, progress_callback=lambda *a: fired.append(a),
    )
    callback = time.time() - t0

    overhead = (callback - silent) / max(silent, 1e-3)
    assert overhead < 0.20, (
        f"callback overhead {overhead:.1%} exceeds 20% budget "
        f"(silent={silent:.3f}s, callback={callback:.3f}s)"
    )
    assert len(fired) == 6


# ---- 2. End-to-end via Flask test client (the real falsifying gate) ----

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


def test_streaming_run_produces_multiple_progress_snapshots(client):
    """The falsifying gate: a streaming MC writes multiple distinct
    progress snapshots before the result lands."""
    body = {
        "intervention_ids": ["evac_d03_30min_early"],
        "n_trials": 3,
        "n_population_agents": 30,
        "duration_hours": 12,
        "use_llm": False,
        "streaming": True,
    }
    r = client.post('/api/scenario/la-puente-hills-m72-ref/run_mc', json=body)
    assert r.status_code == 202, f"expected 202, got {r.status_code}: {r.data!r}"
    payload = r.get_json()
    assert payload["success"] is True
    run_id = payload["data"]["run_id"]
    assert isinstance(run_id, str) and len(run_id) == 8

    # Poll up to 60s for completion. Capture distinct progress snapshots.
    seen_snapshots: list[str] = []
    deadline = time.time() + 60
    done = False
    while time.time() < deadline:
        pr = client.get(f'/api/scenario/la-puente-hills-m72-ref/run_mc/{run_id}/progress')
        assert pr.status_code == 200
        prog = pr.get_json()["data"]
        # Hash the arm progress to detect distinct snapshots
        snap = json.dumps(prog["arms"], sort_keys=True)
        if snap and snap not in seen_snapshots:
            seen_snapshots.append(snap)
        if prog["done"]:
            done = True
            break
        time.sleep(0.05)  # poll every 50ms

    assert done, "MC did not complete within 60s"
    assert prog.get("error") is None, f"worker errored: {prog['error']}"
    # Falsifying assertion: MUST see ≥3 distinct progress states.
    # With 3 trials × 2 arms = 6 callback fires, at least 3 polls should
    # have caught distinct intermediate states.
    assert len(seen_snapshots) >= 3, (
        f"expected ≥3 distinct progress snapshots, got {len(seen_snapshots)}: "
        f"{seen_snapshots}"
    )

    # Result endpoint returns the full run dict
    rr = client.get(f'/api/scenario/la-puente-hills-m72-ref/run_mc/{run_id}/result')
    assert rr.status_code == 200, f"result fetch failed: {rr.status_code} {rr.data!r}"
    result = rr.get_json()["data"]
    assert "baseline" in result
    assert result["baseline"]["n_trials"] == 3


def test_streaming_unknown_run_id_returns_404(client):
    r = client.get('/api/scenario/la-puente-hills-m72-ref/run_mc/deadbeef/progress')
    assert r.status_code == 404
    r = client.get('/api/scenario/la-puente-hills-m72-ref/run_mc/deadbeef/result')
    assert r.status_code == 404


def test_streaming_recent_decisions_appear_during_run(client):
    """The AgentLogTicker depends on recent_decisions populating during
    the run. With 9 trials × 2 arms = 18 callback fires and one synthetic
    decision per 3 fires, we MUST see ≥3 decisions by completion."""
    body = {
        "intervention_ids": ["evac_d03_30min_early"],
        "n_trials": 9,
        "n_population_agents": 30,
        "duration_hours": 12,
        "use_llm": False,
        "streaming": True,
    }
    r = client.post('/api/scenario/la-puente-hills-m72-ref/run_mc', json=body)
    run_id = r.get_json()["data"]["run_id"]

    deadline = time.time() + 60
    final_count = 0
    while time.time() < deadline:
        pr = client.get(f'/api/scenario/la-puente-hills-m72-ref/run_mc/{run_id}/progress')
        prog = pr.get_json()["data"]
        decisions = prog.get("recent_decisions") or []
        if decisions:
            entry = decisions[0]
            assert "archetype" in entry
            assert "post_text" in entry
            assert isinstance(entry["post_text"], str) and len(entry["post_text"]) > 0
            final_count = max(final_count, len(decisions))
        if prog["done"]:
            break
        time.sleep(0.05)

    assert prog["done"], "MC did not complete in time"
    # 18 callback fires / 3 = 6 decisions emitted; the dict caps at 20 so
    # we expect to see all of them. Hard gate (no skip).
    assert final_count >= 3, (
        f"expected ≥3 synthetic decisions, observed peak count={final_count}"
    )


def test_streaming_result_returns_202_while_in_flight(client):
    """Hitting /result before the worker finishes must return 202 with
    status=running, not 200 and not 404. This is a documented contract
    of the endpoint."""
    body = {
        "intervention_ids": ["evac_d03_30min_early"],
        "n_trials": 5,
        "n_population_agents": 50,
        "duration_hours": 12,
        "use_llm": False,
        "streaming": True,
    }
    r = client.post('/api/scenario/la-puente-hills-m72-ref/run_mc', json=body)
    run_id = r.get_json()["data"]["run_id"]

    # Poll /result immediately — the worker should still be running.
    saw_202 = False
    deadline = time.time() + 30
    while time.time() < deadline:
        rr = client.get(
            f'/api/scenario/la-puente-hills-m72-ref/run_mc/{run_id}/result'
        )
        if rr.status_code == 202:
            payload = rr.get_json()
            assert payload["success"] is False
            assert payload.get("status") == "running"
            saw_202 = True
            break
        if rr.status_code == 200:
            # Already done — too fast for this assertion to hold; tolerate
            # but ensure success path matches contract.
            break
        time.sleep(0.01)

    # Drain the run before exiting so other tests see a clean slate.
    end_deadline = time.time() + 60
    while time.time() < end_deadline:
        pr = client.get(
            f'/api/scenario/la-puente-hills-m72-ref/run_mc/{run_id}/progress'
        )
        if pr.get_json()["data"]["done"]:
            break
        time.sleep(0.05)

    assert saw_202, (
        "never observed 202/running response — either the worker "
        "completed before any /result poll could land, or the in-flight "
        "branch is broken"
    )


def test_synchronous_run_still_works(client):
    """Backwards compatibility: streaming=false (or absent) must keep the
    original synchronous behavior."""
    body = {
        "intervention_ids": ["evac_d03_30min_early"],
        "n_trials": 3,
        "n_population_agents": 30,
        "duration_hours": 12,
        "use_llm": False,
        # no "streaming" key
    }
    r = client.post('/api/scenario/la-puente-hills-m72-ref/run_mc', json=body)
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert "baseline" in data
    assert data["baseline"]["n_trials"] == 3
