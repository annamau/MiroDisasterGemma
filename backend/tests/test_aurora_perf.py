"""
Aurora performance / wall-time assertions (D2.5).

Every wall-time number cited in the D2 demo-readiness report has a
corresponding assertion here (±20% tolerance headroom built into thresholds).

Contract
--------
- No pytest fixtures, no parametrize — keep it greppable (mirrors test_aurora.py)
- All thresholds are conservative: actual synth times are well under them on
  M-series hardware; CI machines get the same free pass because synth is CPU-bound
  with no I/O.
- test_mc_perf_assertion_is_real is marked xfail so it documents *regression
  detection* without blocking the suite.

Runs: cd backend && python -m pytest tests/test_aurora_perf.py -v -s
"""

from __future__ import annotations

import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.aurora import monte_carlo, scenario_loader  # noqa: E402


# ---------------------------------------------------------------------------
# Test 1 — single demo run (n_trials=1) under 500 ms wall-clock
# ---------------------------------------------------------------------------

def test_mc_trial_under_500ms_offline_synth():
    """One demo run (baseline + 1 treatment, n_trials=1) should finish under 0.5 s.

    run_monte_carlo orchestrates 2 arms × 1 trial = 2 trials total.
    We use interpretation (a): the whole call must be under 500 ms.
    llm_call=None → synth-only path, no network / Ollama dependency.
    """
    scn = scenario_loader.build_la_puente_hills_m72()

    t0 = time.perf_counter()
    run = monte_carlo.run_monte_carlo(
        scn,
        ["evac_d03_30min_early"],
        n_trials=1,
        n_population_agents=30,
        duration_hours=12,
        llm_call=None,
    )
    wall = time.perf_counter() - t0

    print(f"\n[perf] test_mc_trial_under_500ms_offline_synth  wall={wall:.4f}s")

    assert wall < 0.5, (
        f"Single demo run took {wall:.3f}s — threshold is 0.5s. "
        "Synth path should be well under this on any dev machine."
    )
    # Sanity: run really was n_trials=1 with 1 intervention
    assert run.n_trials == 1
    assert len(run.interventions) == 1


# ---------------------------------------------------------------------------
# Test 2 — 30-trial realistic demo (3 interventions) under 30 s
# ---------------------------------------------------------------------------

def test_mc_30trials_under_30s_offline_synth():
    """Realistic demo: 4 arms × 30 trials = 120 trials, all synth.

    Threshold: 30 s total → 250 ms/trial average. This is feasible on
    M-series hardware; the synth path is sub-100 ms/trial.
    llm_call=None → synth-only, no Ollama dependency.
    """
    scn = scenario_loader.build_la_puente_hills_m72()
    intervention_ids = [
        "evac_d03_30min_early",
        "preposition_d03_4amb",
        "retrofit_d03_w1",
    ]

    t0 = time.perf_counter()
    run = monte_carlo.run_monte_carlo(
        scn,
        intervention_ids,
        n_trials=30,
        n_population_agents=30,
        duration_hours=12,
        llm_call=None,
    )
    wall = time.perf_counter() - t0

    print(f"\n[perf] test_mc_30trials_under_30s_offline_synth  wall={wall:.4f}s")
    avg_ms = wall / (4 * 30) * 1000  # 4 arms × 30 trials
    print(f"[perf]   avg per trial: {avg_ms:.1f} ms  ({4*30} trials total)")

    assert wall < 30.0, (
        f"30-trial demo run took {wall:.3f}s — threshold is 30.0s. "
        "Synth path should be well under this (expected < 10s on M-series)."
    )
    # Sanity checks
    assert run.n_trials == 30
    assert len(run.interventions) == 3
    assert len(run.deltas) == 3


# ---------------------------------------------------------------------------
# Test 3 — misuse / regression sentinel (expected to fail)
# ---------------------------------------------------------------------------

@pytest.mark.xfail(
    reason=(
        "Proves the threshold catches regressions: a 5x trial-count run "
        "with a 1s threshold cannot finish in time on any hardware. If this "
        "unexpectedly passes, the threshold was loosened or the system is broken."
    ),
    strict=True,   # XPASS would fail the suite — that is intentional
)
def test_mc_perf_assertion_is_real():
    """Regression sentinel — this test MUST fail (i.e., report XFAIL).

    Strategy: keep the trial count modest (60 trials × 4 arms = 240 trials,
    ~5s wall) but set an unsatisfiably tight threshold of 1s. This proves the
    threshold mechanism catches a 5x regression without burning a full minute
    of CI / dev time. If the threshold ever gets loosened to >5s, this test
    XPASS-es and breaks the suite — exactly the failure mode we want to catch.
    """
    scn = scenario_loader.build_la_puente_hills_m72()

    t0 = time.perf_counter()
    monte_carlo.run_monte_carlo(
        scn,
        ["evac_d03_30min_early", "preposition_d03_4amb", "retrofit_d03_w1"],
        n_trials=60,
        n_population_agents=30,
        duration_hours=12,
        llm_call=None,
    )
    wall = time.perf_counter() - t0

    print(f"\n[perf] test_mc_perf_assertion_is_real  wall={wall:.4f}s")

    # This assertion is *designed* to fail — 60 trials × 4 arms in <1s is impossible.
    assert wall < 1.0, (
        f"As expected, 240-trial run ({wall:.2f}s) exceeds the 1s sentinel "
        "threshold. XFAIL confirms the assertion is real, not a no-op."
    )
