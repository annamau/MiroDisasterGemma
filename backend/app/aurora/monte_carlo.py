"""
Monte Carlo orchestrator — N trials per intervention, bootstrap 90% CI on
deltas vs baseline. This is what powers the "wow factor" output:

    "Pre-stage 4 ambulances in D03 saves 312 ± [180, 451] lives (90% CI)
     and $1.4B ± [$0.7B, $2.0B] vs baseline."

Design choices
--------------
1. Outer loop is intervention; inner loop is trial. The intervention's
   `apply()` mutates the scenario once before the trials, then trials
   share the cache so cache-hit rate climbs across trials.

2. Bootstrap CI (not parametric) — the trial outputs are skewed
   (collapse-driven heavy-tail), so percentile bootstrap on the resampled
   means is the honest CI. B=2000 resamples is fine on 50-trial samples.

3. Delta-from-baseline reported as a *paired* signed difference: trial i
   under baseline vs trial i under intervention with the same seed (and
   same population/responder draws). This kills variance from the
   stochastic damage roll-outs and makes the "lives saved" number
   credible at low N.

4. Concurrency: trials within an intervention are LLM-bound and the
   cache is the shared-state bottleneck — running them serially keeps
   the cache hit rate climbing monotonically. We can parallelize across
   *interventions* but they don't share useful cache. So serial it is
   for the laptop demo; an MC backend could fan out per-intervention.

5. Output shape mirrors what the UI Outcome Comparator needs: the dict
   from `summarize_run` has the lives_saved + dollars_saved + CIs and
   the per-intervention timeline mean to render the line chart.

Reference for bootstrap CI:
    Efron 1979, "Bootstrap methods: another look at the jackknife."
    Diciccio & Efron 1996 for percentile-method limits.
"""

from __future__ import annotations

import logging
import math
import random
import statistics
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable

from .agent_runtime import TrialResult, run_trial, trial_to_dict
from .decision_cache import DecisionCache, get_default_cache
from .intervention_dsl import Intervention, get_intervention
from .scenario import Scenario

logger = logging.getLogger("aurora.monte_carlo")


# ---- Result types ----

@dataclass
class CIBound:
    point: float          # mean across trials (or median if specified)
    lo: float             # lower bound of 90% CI
    hi: float             # upper bound of 90% CI
    n: int                # number of trials


@dataclass
class InterventionOutcome:
    intervention_id: str
    label: str
    n_trials: int
    deaths: CIBound
    injuries: CIBound
    economic_loss_usd: CIBound
    misinfo_ratio: CIBound
    # Mean cumulative-deaths timeline at hour t, length = duration_hours
    deaths_timeline_mean: list[float]
    # Per-trial walltime stats
    wall_seconds_mean: float
    cache_hit_rate: float
    # Raw trial dicts (kept compact; UI gets these for box plot)
    trial_summaries: list[dict[str, Any]]


@dataclass
class InterventionDelta:
    """Paired delta vs baseline (positive = lives saved / dollars saved)."""
    intervention_id: str
    label: str
    lives_saved: CIBound
    injuries_avoided: CIBound
    dollars_saved: CIBound
    misinfo_ratio_change: CIBound
    cost_per_life_saved_usd: float | None     # if intervention has a cost field


@dataclass
class MonteCarloRun:
    scenario_id: str
    n_trials: int
    duration_hours: int
    started_at: float
    finished_at: float
    wall_seconds: float
    baseline: InterventionOutcome
    interventions: list[InterventionOutcome]
    deltas: list[InterventionDelta]


# ---- Bootstrap CI ----

def _bootstrap_ci(
    samples: list[float],
    *,
    n_resample: int = 2000,
    alpha: float = 0.10,
    seed: int = 11,
) -> CIBound:
    """Percentile bootstrap CI for the *mean*. Honest for skewed samples."""
    if not samples:
        return CIBound(point=0.0, lo=0.0, hi=0.0, n=0)
    rng = random.Random(seed)
    n = len(samples)
    if n == 1:
        v = float(samples[0])
        return CIBound(point=v, lo=v, hi=v, n=1)
    means: list[float] = []
    for _ in range(n_resample):
        resample = [samples[rng.randrange(n)] for _ in range(n)]
        means.append(sum(resample) / n)
    means.sort()
    lo_idx = int(alpha / 2 * n_resample)
    hi_idx = int((1 - alpha / 2) * n_resample) - 1
    return CIBound(
        point=round(sum(samples) / n, 2),
        lo=round(means[lo_idx], 2),
        hi=round(means[hi_idx], 2),
        n=n,
    )


# ---- Run one intervention's trials ----

def _run_intervention_trials(
    scenario: Scenario,
    intervention: Intervention,
    *,
    n_trials: int,
    base_seed: int,
    duration_hours: int,
    n_population_agents: int,
    llm_call: Any | None,
    fast_model: str,
    cache: DecisionCache,
) -> InterventionOutcome:
    """Run N trials with this intervention applied. Trials share cache."""
    mutated = intervention.apply(scenario)
    overrides = intervention.runtime_overrides()
    trials: list[TrialResult] = []
    cache_hits_start = cache.stats.hits
    cache_misses_start = cache.stats.misses

    for i in range(n_trials):
        t = run_trial(
            mutated,
            trial_id=i,
            intervention_id=intervention.intervention_id,
            seed=base_seed + i,
            duration_hours=duration_hours,
            n_population_agents=n_population_agents,
            llm_call=llm_call,
            fast_model=fast_model,
            cache=cache,
            runtime_overrides=overrides,
        )
        trials.append(t)
        logger.info(
            "intervention=%s trial=%d/%d deaths=%d wall=%.2fs",
            intervention.intervention_id, i + 1, n_trials,
            t.deaths, t.wall_seconds,
        )

    deaths = [t.deaths for t in trials]
    injuries = [t.injuries for t in trials]
    economic = [t.economic_loss_usd for t in trials]
    misinfo = [
        t.misinfo_to_authority_ratio if math.isfinite(t.misinfo_to_authority_ratio)
        else 99.0
        for t in trials
    ]

    duration = trials[0].duration_hours if trials else duration_hours
    deaths_tl_sum = [0.0] * duration
    for t in trials:
        for h, snap in enumerate(t.timeline):
            if h < duration:
                deaths_tl_sum[h] += snap.deaths_cumulative
    deaths_tl_mean = [round(s / max(1, len(trials)), 1) for s in deaths_tl_sum]

    wall_mean = (
        sum(t.wall_seconds for t in trials) / len(trials) if trials else 0.0
    )
    hits = cache.stats.hits - cache_hits_start
    misses = cache.stats.misses - cache_misses_start
    hit_rate = hits / max(1, hits + misses)

    return InterventionOutcome(
        intervention_id=intervention.intervention_id,
        label=intervention.label,
        n_trials=len(trials),
        deaths=_bootstrap_ci(deaths),
        injuries=_bootstrap_ci(injuries),
        economic_loss_usd=_bootstrap_ci(economic),
        misinfo_ratio=_bootstrap_ci(misinfo),
        deaths_timeline_mean=deaths_tl_mean,
        wall_seconds_mean=round(wall_mean, 3),
        cache_hit_rate=round(hit_rate, 3),
        trial_summaries=[
            {
                "trial_id": t.trial_id,
                "deaths": t.deaths,
                "injuries": t.injuries,
                "economic_loss_usd": t.economic_loss_usd,
                "wall_seconds": t.wall_seconds,
            }
            for t in trials
        ],
    )


# ---- Paired delta CI (the "lives saved" number) ----

def _paired_delta(
    baseline_samples: list[float],
    treatment_samples: list[float],
    *,
    seed: int = 23,
) -> CIBound:
    """Paired signed difference, bootstrap CI on the mean delta.

    Trials are paired by index — both ran with seeds (base_seed + i),
    so their stochastic-damage rolls match. Differencing kills the
    inter-trial variance and makes "lives saved" credible at low N.
    Positive number = baseline > treatment = improvement (lives saved).
    """
    n = min(len(baseline_samples), len(treatment_samples))
    if n == 0:
        return CIBound(point=0.0, lo=0.0, hi=0.0, n=0)
    diffs = [
        baseline_samples[i] - treatment_samples[i] for i in range(n)
    ]
    return _bootstrap_ci(diffs, seed=seed)


def _delta_for_intervention(
    baseline: InterventionOutcome,
    treated: InterventionOutcome,
) -> InterventionDelta:
    base_deaths = [s["deaths"] for s in baseline.trial_summaries]
    base_inj = [s["injuries"] for s in baseline.trial_summaries]
    base_eco = [s["economic_loss_usd"] for s in baseline.trial_summaries]

    treat_deaths = [s["deaths"] for s in treated.trial_summaries]
    treat_inj = [s["injuries"] for s in treated.trial_summaries]
    treat_eco = [s["economic_loss_usd"] for s in treated.trial_summaries]

    lives = _paired_delta(base_deaths, treat_deaths)
    inj = _paired_delta(base_inj, treat_inj)
    dollars = _paired_delta(base_eco, treat_eco)

    # Misinfo ratio change is *not* a saving — it's a signed difference
    # where positive means baseline ratio > treated ratio (improvement).
    misinfo_change = CIBound(
        point=round(baseline.misinfo_ratio.point - treated.misinfo_ratio.point, 2),
        lo=round(baseline.misinfo_ratio.lo - treated.misinfo_ratio.hi, 2),
        hi=round(baseline.misinfo_ratio.hi - treated.misinfo_ratio.lo, 2),
        n=min(baseline.misinfo_ratio.n, treated.misinfo_ratio.n),
    )

    return InterventionDelta(
        intervention_id=treated.intervention_id,
        label=treated.label,
        lives_saved=lives,
        injuries_avoided=inj,
        dollars_saved=dollars,
        misinfo_ratio_change=misinfo_change,
        cost_per_life_saved_usd=None,    # set when interventions carry $$ cost
    )


# ---- Top-level orchestrator ----

def run_monte_carlo(
    scenario: Scenario,
    intervention_ids: list[str],
    *,
    n_trials: int = 50,
    base_seed: int = 1000,
    duration_hours: int | None = None,
    n_population_agents: int = 200,
    llm_call: Any | None = None,
    fast_model: str = "gemma4:e2b",
    cache: DecisionCache | None = None,
) -> MonteCarloRun:
    """Run baseline + each requested intervention, return paired deltas.

    `intervention_ids` does NOT need to include "baseline" — it's added
    automatically as the reference point for delta computation.
    """
    cache = cache or get_default_cache()
    duration = duration_hours or scenario.hazard.duration_hours
    started = time.time()
    t0 = time.perf_counter()

    # 1) Baseline first — its cache state primes the run for treated arms
    baseline = _run_intervention_trials(
        scenario, get_intervention("baseline"),
        n_trials=n_trials, base_seed=base_seed,
        duration_hours=duration,
        n_population_agents=n_population_agents,
        llm_call=llm_call, fast_model=fast_model, cache=cache,
    )

    # 2) Each treatment — same base_seed so trials are paired
    treated: list[InterventionOutcome] = []
    for iv_id in intervention_ids:
        if iv_id == "baseline":
            continue
        iv = get_intervention(iv_id)
        out = _run_intervention_trials(
            scenario, iv,
            n_trials=n_trials, base_seed=base_seed,
            duration_hours=duration,
            n_population_agents=n_population_agents,
            llm_call=llm_call, fast_model=fast_model, cache=cache,
        )
        treated.append(out)

    # 3) Compute deltas vs baseline (paired)
    deltas = [_delta_for_intervention(baseline, t) for t in treated]

    finished = time.time()
    wall = time.perf_counter() - t0

    return MonteCarloRun(
        scenario_id=scenario.scenario_id,
        n_trials=n_trials,
        duration_hours=duration,
        started_at=started,
        finished_at=finished,
        wall_seconds=round(wall, 2),
        baseline=baseline,
        interventions=treated,
        deltas=deltas,
    )


# ---- Serialization ----

def run_to_dict(run: MonteCarloRun) -> dict[str, Any]:
    """Compact JSON shape for /api/simulation/run response + UI consumption."""
    def outcome(o: InterventionOutcome) -> dict[str, Any]:
        return {
            "intervention_id": o.intervention_id,
            "label": o.label,
            "n_trials": o.n_trials,
            "deaths": asdict(o.deaths),
            "injuries": asdict(o.injuries),
            "economic_loss_usd": asdict(o.economic_loss_usd),
            "misinfo_ratio": asdict(o.misinfo_ratio),
            "deaths_timeline_mean": o.deaths_timeline_mean,
            "wall_seconds_mean": o.wall_seconds_mean,
            "cache_hit_rate": o.cache_hit_rate,
            "trial_summaries": o.trial_summaries,
        }

    def delta(d: InterventionDelta) -> dict[str, Any]:
        return {
            "intervention_id": d.intervention_id,
            "label": d.label,
            "lives_saved": asdict(d.lives_saved),
            "injuries_avoided": asdict(d.injuries_avoided),
            "dollars_saved": asdict(d.dollars_saved),
            "misinfo_ratio_change": asdict(d.misinfo_ratio_change),
            "cost_per_life_saved_usd": d.cost_per_life_saved_usd,
        }

    return {
        "scenario_id": run.scenario_id,
        "n_trials": run.n_trials,
        "duration_hours": run.duration_hours,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "wall_seconds": run.wall_seconds,
        "baseline": outcome(run.baseline),
        "interventions": [outcome(o) for o in run.interventions],
        "deltas": [delta(d) for d in run.deltas],
    }
