# SPDX-License-Identifier: Apache-2.0
"""
Phase 2a — math.isfinite() coercion of cost_per_life_saved_usd.

Falsifying gate: when an intervention saves zero (or negative) lives,
cost_per_life_saved_usd must be JSON-null (Python None) in the
serialised output — never the literal Infinity (which the Flask JSON
encoder may emit and the JS-side parser handles inconsistently).

We exercise the unit-test seam directly via _delta_for_intervention.
"""

from __future__ import annotations

import math
import os
import sys
from dataclasses import asdict

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.aurora import monte_carlo  # noqa: E402
from app.aurora.intervention_dsl import PRESET_INTERVENTIONS  # noqa: E402


def _make_outcome(intervention_id: str, label: str, deaths_seq: list[float],
                  inj_seq: list[float], eco_seq: list[float]):
    """Hand-build an InterventionOutcome with controlled trial summaries
    so we can drive the delta math straight to the zero-lives-saved edge."""
    n = len(deaths_seq)
    deaths_ci = monte_carlo.CIBound(
        point=sum(deaths_seq) / n, lo=min(deaths_seq), hi=max(deaths_seq), n=n,
    )
    inj_ci = monte_carlo.CIBound(
        point=sum(inj_seq) / n, lo=min(inj_seq), hi=max(inj_seq), n=n,
    )
    eco_ci = monte_carlo.CIBound(
        point=sum(eco_seq) / n, lo=min(eco_seq), hi=max(eco_seq), n=n,
    )
    misinfo_ci = monte_carlo.CIBound(point=0.0, lo=0.0, hi=0.0, n=n)
    return monte_carlo.InterventionOutcome(
        intervention_id=intervention_id,
        label=label,
        n_trials=n,
        deaths=deaths_ci,
        injuries=inj_ci,
        economic_loss_usd=eco_ci,
        misinfo_ratio=misinfo_ci,
        deaths_timeline_mean=[],
        wall_seconds_mean=0.0,
        cache_hit_rate=0.0,
        trial_summaries=[
            {"deaths": d, "injuries": i, "economic_loss_usd": e}
            for d, i, e in zip(deaths_seq, inj_seq, eco_seq)
        ],
    )


def test_zero_lives_saved_yields_none_not_infinity():
    """U_inf — _delta_for_intervention with identical baseline+treated
    trial summaries must emit cost_per_life_saved_usd=None (not Inf).

    Also asserts the value is JSON-serialisable cleanly (no Infinity in
    the str output) — that's the actual demo-killer."""
    import json

    baseline = _make_outcome(
        "baseline", "Baseline",
        deaths_seq=[100.0, 100.0, 100.0],
        inj_seq=[200.0, 200.0, 200.0],
        eco_seq=[1.0e9, 1.0e9, 1.0e9],
    )
    treated = _make_outcome(
        "evac_d03_30min_early", "Evac 30min early",
        deaths_seq=[100.0, 100.0, 100.0],  # identical → lives_saved = 0
        inj_seq=[200.0, 200.0, 200.0],
        eco_seq=[1.0e9, 1.0e9, 1.0e9],
    )
    iv = PRESET_INTERVENTIONS["evac_d03_30min_early"]
    delta = monte_carlo._delta_for_intervention(baseline, treated, iv)

    assert delta.cost_per_life_saved_usd is None, (
        f"Expected None for zero lives saved, got "
        f"{delta.cost_per_life_saved_usd!r}"
    )
    # Must round-trip through JSON without an "Infinity" literal.
    payload = asdict(delta)
    text = json.dumps(payload)
    assert "Infinity" not in text, (
        f"JSON output leaked Infinity literal: {text}"
    )
    assert math.isfinite(delta.cost_per_life_saved_usd or 0.0)


def test_negative_lives_saved_yields_none():
    """An intervention that *increases* deaths (negative lives_saved)
    must also emit None for cost_per_life_saved_usd — a negative CPL
    has no meaningful interpretation in the UI."""
    baseline = _make_outcome(
        "baseline", "Baseline",
        deaths_seq=[100.0, 100.0, 100.0],
        inj_seq=[200.0, 200.0, 200.0],
        eco_seq=[1.0e9, 1.0e9, 1.0e9],
    )
    treated = _make_outcome(
        "evac_d03_30min_early", "Evac 30min early",
        deaths_seq=[120.0, 120.0, 120.0],  # worse than baseline
        inj_seq=[220.0, 220.0, 220.0],
        eco_seq=[1.1e9, 1.1e9, 1.1e9],
    )
    iv = PRESET_INTERVENTIONS["evac_d03_30min_early"]
    delta = monte_carlo._delta_for_intervention(baseline, treated, iv)
    assert delta.cost_per_life_saved_usd is None


def test_positive_lives_saved_yields_finite_float():
    """Sanity: the safety net must NOT clobber legitimate finite CPL."""
    baseline = _make_outcome(
        "baseline", "Baseline",
        deaths_seq=[100.0, 100.0, 100.0],
        inj_seq=[200.0, 200.0, 200.0],
        eco_seq=[1.0e9, 1.0e9, 1.0e9],
    )
    treated = _make_outcome(
        "evac_d03_30min_early", "Evac 30min early",
        deaths_seq=[50.0, 50.0, 50.0],  # saved 50 lives per trial
        inj_seq=[100.0, 100.0, 100.0],
        eco_seq=[5.0e8, 5.0e8, 5.0e8],
    )
    iv = PRESET_INTERVENTIONS["evac_d03_30min_early"]
    delta = monte_carlo._delta_for_intervention(baseline, treated, iv)
    assert delta.cost_per_life_saved_usd is not None
    assert math.isfinite(delta.cost_per_life_saved_usd)
    assert delta.cost_per_life_saved_usd > 0.0
