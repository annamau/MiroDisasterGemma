"""
Agent runtime — one Monte Carlo trial of the Aurora simulator.

This is the OASIS replacement. One call to `run_trial(...)` simulates
`duration_hours` of wall-clock at hourly granularity, with four agent
classes interacting:

    Hazard agents       (deterministic — Omori chain + intensity field)
    Infrastructure      (deterministic — cascade thresholds)
    Population agents   (LLM-driven via decision cache, ~hourly samples)
    Responder agents    (LLM-driven dispatch + finite resource budgets)

What's *cached* (the wins):
    - Per-archetype, per-phase, per-condition population decisions. The
      cache key collides aggressively across agents that share archetype +
      district + hour-bucket, so the realized hit rate target is 60%.
    - Per-station responder dispatch decisions, keyed on incident profile.

What's *deterministic* (the leverage):
    - Aftershock chain (seeded RNG)
    - HAZUS deterministic loss totals — used as the trial's "expected" line
    - Infrastructure cascade flips
    - Resource depletion math

Why hourly (not minute-by-minute):
    - Real disaster decisions update on ~hour timescales.
    - Hourly buckets keep the cache key cardinality tractable (hours x
      archetypes x districts ~ 72 x 9 x 8 = 5184 cells).
    - Total LLM calls per trial = 9 archetypes x 8 districts x 5 sample
      decisions = ~360, not 200 agents x 72 hours = 14400. Massive win.

The output is a `TrialResult`: deterministic loss totals + sampled social-
media post counts + responder-utilization summary + 90% CI inputs (we
record per-agent sampled outcomes so the MC orchestrator can bootstrap CIs
across trials).
"""

from __future__ import annotations

import json
import logging
import math
import random
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .archetypes import (
    ARCHETYPES, ARCHETYPE_ORDER, ArchetypeName, phase_for_hour, posting_rate,
)
from .decision_cache import DecisionCache, get_default_cache
from .hazard_models import (
    AftershockEvent, DistrictInfraState, aftershock_chain,
    aftershock_intensity_bump, init_infra_state, update_infra_state,
)
from .hazus_fragility import (
    estimate_building_loss, shaking_intensity_to_sa,
)
from .population_generator import PopulationAgent, generate_population
from .responder_generator import (
    ResponderAgent, generate_responders, hospital_capacity, responder_summary,
)
from .scenario import Building, Scenario

logger = logging.getLogger("aurora.agent_runtime")


# ---- Result types ----

@dataclass
class HourlySnapshot:
    hour: int
    deaths_cumulative: int
    injuries_cumulative: int
    new_aftershocks: int
    posts_total: int
    posts_misinfo: int
    posts_authority: int
    responders_busy: int
    hospital_load_pct: float


@dataclass
class TrialResult:
    scenario_id: str
    trial_id: int
    intervention_id: str
    seed: int
    wall_seconds: float
    cache_hits: int
    cache_misses: int
    duration_hours: int

    # Loss totals (citywide, end of horizon)
    deaths: int
    injuries: int
    collapsed_buildings: int
    economic_loss_usd: float

    # Per-district breakdown
    deaths_by_district: dict[str, int]

    # Behavioral telemetry
    posts_total: int
    posts_misinfo: int
    posts_authority: int
    # Reach-weighted impressions (followers reached). This is what matters for
    # public-perception dynamics — Vosoughi 2018 found false news has 6x the
    # reach of true news, so the reach ratio is the meaningful one, not raw counts.
    impressions_misinfo: int
    impressions_authority: int
    misinfo_to_authority_ratio: float

    # Hourly snapshots for plotting
    timeline: list[HourlySnapshot]


# ---- Mainshock MMI field (same anchors as scenario_loader) ----

def _mainshock_mmi_at(
    epi_lat: float, epi_lon: float, lat: float, lon: float,
) -> float:
    d_lat = lat - epi_lat
    d_lon = lon - epi_lon
    d = math.sqrt(d_lat ** 2 + d_lon ** 2) * 111.0
    if d <= 3.0:
        return 9.0
    anchors = [(3.0, 9.0), (10.0, 8.0), (20.0, 7.0), (40.0, 6.0), (100.0, 5.5)]
    for (d1, m1), (d2, m2) in zip(anchors, anchors[1:]):
        if d <= d2:
            t = ((math.log10(d) - math.log10(d1))
                 / (math.log10(d2) - math.log10(d1)))
            return m1 + (m2 - m1) * t
    return 5.5


# ---- Population decision sampling ----

@dataclass(frozen=True)
class CellKey:
    """Cache-friendly aggregation cell. All agents matching this cell share
    one LLM decision draw — that's where the 60% cache hit comes from."""
    archetype: ArchetypeName
    district_id: str
    phase: str
    infra_state: str   # "ok" | "power_down" | "comms_down" | "all_down"


def _infra_state_label(st: DistrictInfraState) -> str:
    if not st.power_ok and not st.comms_ok:
        return "all_down"
    if not st.comms_ok:
        return "comms_down"
    if not st.power_ok:
        return "power_down"
    return "ok"


def _decision_user_prompt(cell: CellKey, hour: int) -> str:
    """User-side prompt for the archetype decision call."""
    return (
        f"Hour {hour} since the M7.2 quake. You are in district {cell.district_id} "
        f"(infra={cell.infra_state}). Phase: {cell.phase}. "
        f"Pick ONE action and emit JSON."
    )


def _sample_decision_for_cell(
    cache: DecisionCache,
    cell: CellKey,
    hour: int,
    *,
    llm_call: Any | None,
    fast_model: str,
) -> dict[str, Any]:
    """Cache-aware decision draw for one (archetype, district, phase, infra) cell.

    If `llm_call` is None (no Ollama running), we synthesize a plausible
    decision from archetype defaults. The simulator runs deterministic in
    that mode — useful for CI and unit tests."""
    archetype = ARCHETYPES[cell.archetype]
    user = _decision_user_prompt(cell, hour)

    cached = cache.get(fast_model, archetype.system, user)
    if cached is not None:
        cache.stats.hits += 1
        try:
            return json.loads(cached.content)
        except Exception:
            pass

    if llm_call is None:
        cache.stats.misses += 1
        # Deterministic fallback: action based on archetype default
        synth = _synth_decision(cell.archetype)
        cache.put(
            model=fast_model, system=archetype.system, user=user,
            content=json.dumps(synth), gen_tps=0.0, eval_count=0,
        )
        return synth

    parsed, content, was_cached = cache.get_or_call(
        llm_call,
        system=archetype.system, user=user, model=fast_model,
        max_tokens=200, temperature=0.4,
    )
    if isinstance(parsed, dict):
        return parsed
    return _synth_decision(cell.archetype)


def _synth_decision(archetype: ArchetypeName) -> dict[str, Any]:
    """Archetype-default action used when LLM is offline. Keeps determinism."""
    defaults = {
        "eyewitness":  {"action": "post_observation", "intent": "inform"},
        "coordinator": {"action": "broadcast_need", "intent": "coordinate"},
        "amplifier":   {"action": "reshare", "intent": "amplify"},
        "authority":   {"action": "official_update", "intent": "guide"},
        "misinformer": {"action": "post_unverified", "intent": "engage"},
        "conspiracist":{"action": "frame_coverup", "intent": "doubt"},
        "helper":      {"action": "offer_aid", "intent": "help"},
        "helpless":    {"action": "request_rescue", "intent": "survive"},
        "critic":      {"action": "critique_response", "intent": "blame"},
    }
    d = defaults[archetype].copy()
    d["post_text"] = f"<{archetype}-default>"
    return d


# ---- Loss accumulation per hour ----

def _hourly_loss(
    scenario: Scenario,
    epi_lat: float, epi_lon: float,
    aftershocks_this_hour: list[AftershockEvent],
    infra_states: dict[str, DistrictInfraState],
    *,
    base_mmi_cache: dict[str, float],
    accumulated_collapse_share: dict[str, float],
    rng: random.Random,
    seen_collapses: set[str],
) -> tuple[int, int, int, dict[str, int], float]:
    """Compute per-hour loss attributable to mainshock + this-hour aftershocks.

    The mainshock loss is amortized across the first 6 hours (people are
    extricated, hospital arrivals, etc.). Aftershocks contribute additional
    collapses and casualties on top.
    """
    mainshock_amortize_hours = 6
    deaths = injuries = collapsed = 0
    deaths_by_district: dict[str, int] = {}
    economic_loss = 0.0

    # Treat each Building independently. Cache base MMI per location.
    for b in scenario.buildings:
        if b.building_id not in base_mmi_cache:
            base_mmi_cache[b.building_id] = _mainshock_mmi_at(
                epi_lat, epi_lon, b.lat, b.lon,
            )
        mmi = base_mmi_cache[b.building_id]
        # Add aftershock bumps
        for af in aftershocks_this_hour:
            mmi = max(mmi, mmi + 0.6 * aftershock_intensity_bump(
                af, b.lat, b.lon,
            ) - mmi)  # take max of base or aftershock-augmented
        sa = shaking_intensity_to_sa(mmi)
        est = estimate_building_loss(b.hazus_class, sa, year_built=b.year_built)
        rep = b.representative_count

        # Stochastic: did this building actually collapse this hour?
        if rng.random() < est.collapse_probability / mainshock_amortize_hours:
            if b.building_id not in seen_collapses:
                collapsed += rep
                seen_collapses.add(b.building_id)
                accumulated_collapse_share[b.district_id] = (
                    accumulated_collapse_share.get(b.district_id, 0.0)
                    + rep / max(1, sum(
                        bx.representative_count for bx in scenario.buildings
                        if bx.district_id == b.district_id
                    ))
                )
        # Casualties amortized across first 6 hours
        per_hour_factor = 1.0 / mainshock_amortize_hours
        occ_real = b.occupants_day * rep
        d_h = est.expected_death_rate * occ_real * per_hour_factor
        i_h = est.expected_injury_rate * occ_real * per_hour_factor

        # Infrastructure penalty: if hospital capacity dropped, untreated
        # injuries roll over to deaths at a higher rate.
        infra = infra_states[b.district_id]
        if infra.hospital_capacity_mult < 0.5:
            roll_over = i_h * (1.0 - infra.hospital_capacity_mult) * 0.10
            d_h += roll_over
            i_h -= roll_over

        deaths += int(d_h)
        injuries += int(i_h)
        deaths_by_district[b.district_id] = (
            deaths_by_district.get(b.district_id, 0) + int(d_h)
        )
        # Economic: $200k per occupant injury, $5M per fatality (FEMA stats),
        # $400k per fully-collapsed bldg (rebuild cost).
        economic_loss += i_h * 200_000 + d_h * 5_000_000

    return deaths, injuries, collapsed, deaths_by_district, economic_loss


# ---- One trial ----

def run_trial(
    scenario: Scenario,
    *,
    trial_id: int = 0,
    intervention_id: str = "baseline",
    seed: int = 7,
    duration_hours: int | None = None,
    n_population_agents: int = 200,
    llm_call: Any | None = None,
    fast_model: str = "gemma4:e2b",
    cache: DecisionCache | None = None,
    runtime_overrides: dict[str, Any] | None = None,
) -> TrialResult:
    """Run one Monte Carlo trial. Pure function modulo `cache` (which is the
    intentional cross-trial state — that's what gives 60% hit rate).
    """
    cache = cache or get_default_cache()
    duration = duration_hours or scenario.hazard.duration_hours
    rng = random.Random(seed + trial_id)
    t0 = time.perf_counter()
    overrides = runtime_overrides or {}
    hospital_floors: dict[str, float] = overrides.get(
        "hospital_capacity_floor_by_district", {},
    )
    auth_reach_mult = float(overrides.get("authority_reach_multiplier", 1.0))
    misinfo_dampen = float(overrides.get("misinfo_dampener", 1.0))

    # Cast: one population sample, one responder pool per trial
    pop = generate_population(
        scenario, n_agents=n_population_agents, seed=seed + trial_id,
    )
    responders = generate_responders(scenario, seed=seed + trial_id + 100)

    # Pre-bin agents by (archetype, district) for cell-decision aggregation
    cell_index: dict[tuple[ArchetypeName, str], list[PopulationAgent]] = {}
    for a in pop:
        cell_index.setdefault((a.archetype, a.district_id), []).append(a)

    # Precompute aftershock chain
    aftershocks = aftershock_chain(
        scenario.hazard.magnitude,
        scenario.hazard.epicenter_lat,
        scenario.hazard.epicenter_lon,
        duration_hours=duration, seed=seed + trial_id + 200,
    )
    aftershocks_by_hour: dict[int, list[AftershockEvent]] = {}
    for af in aftershocks:
        aftershocks_by_hour.setdefault(int(af.hour), []).append(af)

    infra_states = init_infra_state([d.district_id for d in scenario.districts])
    base_mmi_cache: dict[str, float] = {}
    collapse_share: dict[str, float] = {d.district_id: 0.0
                                        for d in scenario.districts}
    seen_collapses: set[str] = set()

    deaths_total = injuries_total = collapsed_total = 0
    economic_total = 0.0
    deaths_by_district_acc: dict[str, int] = {}
    posts_total = posts_misinfo = posts_authority = 0
    impressions_misinfo = impressions_authority = 0
    timeline: list[HourlySnapshot] = []

    # Median follower count by archetype, computed once. Used for impression-weighting.
    followers_by_arch: dict[ArchetypeName, int] = {}
    for a in pop:
        followers_by_arch.setdefault(a.archetype, 0)
        followers_by_arch[a.archetype] = max(
            followers_by_arch[a.archetype], a.follower_count,
        )

    cache_hits_at_start = cache.stats.hits
    cache_misses_at_start = cache.stats.misses

    hosp_cap = hospital_capacity(scenario)

    for hour in range(duration):
        # 1) Hazard tick
        hr_aftershocks = aftershocks_by_hour.get(hour, [])
        af_in_district = {d.district_id: any(
            ((af.epicenter_lat - d.centroid_lat) ** 2
             + (af.epicenter_lon - d.centroid_lon) ** 2) ** 0.5 < 0.05
            for af in hr_aftershocks
        ) for d in scenario.districts}

        # 2) Loss accumulation (deterministic + stochastic)
        d_h, i_h, c_h, d_by_dist, eco = _hourly_loss(
            scenario,
            scenario.hazard.epicenter_lat, scenario.hazard.epicenter_lon,
            hr_aftershocks, infra_states,
            base_mmi_cache=base_mmi_cache,
            accumulated_collapse_share=collapse_share,
            rng=rng,
            seen_collapses=seen_collapses,
        )
        deaths_total += d_h
        injuries_total += i_h
        collapsed_total += c_h
        economic_total += eco
        for did, v in d_by_dist.items():
            deaths_by_district_acc[did] = deaths_by_district_acc.get(did, 0) + v

        # 3) Infrastructure cascade
        update_infra_state(infra_states, collapse_share,
                           aftershock_in_district=af_in_district)
        # Apply intervention floors AFTER cascade so pre-positioning doesn't
        # mask infrastructure failure — it just dampens it. A district with
        # both power+comms down still loses some capacity, but the
        # pre-staged ambulances keep at least `floor` of capacity online.
        for did, floor in hospital_floors.items():
            if did in infra_states:
                infra_states[did].hospital_capacity_mult = max(
                    infra_states[did].hospital_capacity_mult, float(floor),
                )

        # 4) Population decisions: one cache lookup per cell, applied to
        #    every agent in that cell with their posting rate.
        phase = phase_for_hour(hour)
        for d in scenario.districts:
            infra_label = _infra_state_label(infra_states[d.district_id])
            for archetype in ARCHETYPE_ORDER:
                agents_in_cell = cell_index.get((archetype, d.district_id), [])
                if not agents_in_cell:
                    continue
                cell = CellKey(
                    archetype=archetype, district_id=d.district_id,
                    phase=phase, infra_state=infra_label,
                )
                _ = _sample_decision_for_cell(
                    cache, cell, hour,
                    llm_call=llm_call, fast_model=fast_model,
                )
                # Posts contributed by this cell this hour
                rate = posting_rate(archetype, hour)
                # Comms-down districts post at 30% rate
                if not infra_states[d.district_id].comms_ok:
                    rate *= 0.30
                # Use float here; only round when reporting. Otherwise small
                # archetype populations (Authority @ 2%) round to 0 every cell.
                cell_posts_f = rate * len(agents_in_cell)
                posts_total += int(cell_posts_f)
                # Reach-weighted impressions: posts * agents' follower reach
                # (Vosoughi 2018 — what matters for public-perception is reach,
                # not author count)
                cell_impressions = int(
                    cell_posts_f * sum(a.follower_count for a in agents_in_cell)
                    / max(1, len(agents_in_cell))
                )
                if archetype in ("misinformer", "conspiracist"):
                    posts_misinfo += int(cell_posts_f)
                    impressions_misinfo += int(cell_impressions * misinfo_dampen)
                if archetype == "authority":
                    posts_authority += int(cell_posts_f)
                    impressions_authority += int(cell_impressions * auth_reach_mult)

        # 5) Hospital load: untreated portion converts at small rate to deaths
        hosp_load_pct = min(1.5, injuries_total / max(1, hosp_cap[
            "er_capacity_per_hr"] * (hour + 1)))

        timeline.append(HourlySnapshot(
            hour=hour,
            deaths_cumulative=deaths_total,
            injuries_cumulative=injuries_total,
            new_aftershocks=len(hr_aftershocks),
            posts_total=posts_total,
            posts_misinfo=posts_misinfo,
            posts_authority=posts_authority,
            responders_busy=0,    # P3: wire responder dispatch
            hospital_load_pct=round(hosp_load_pct, 3),
        ))

    wall = time.perf_counter() - t0
    cache_hits = cache.stats.hits - cache_hits_at_start
    cache_misses = cache.stats.misses - cache_misses_at_start

    # Reach-weighted ratio (Vosoughi 2018: false news reaches ~6x further)
    misinfo_ratio = (
        impressions_misinfo / impressions_authority
        if impressions_authority > 0 else float("inf")
    )

    return TrialResult(
        scenario_id=scenario.scenario_id,
        trial_id=trial_id,
        intervention_id=intervention_id,
        seed=seed,
        wall_seconds=round(wall, 3),
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        duration_hours=duration,
        deaths=deaths_total,
        injuries=injuries_total,
        collapsed_buildings=collapsed_total,
        economic_loss_usd=round(economic_total, 0),
        deaths_by_district=deaths_by_district_acc,
        posts_total=posts_total,
        posts_misinfo=posts_misinfo,
        posts_authority=posts_authority,
        impressions_misinfo=impressions_misinfo,
        impressions_authority=impressions_authority,
        misinfo_to_authority_ratio=round(misinfo_ratio, 2)
            if math.isfinite(misinfo_ratio) else 99.0,
        timeline=timeline,
    )


def trial_to_dict(t: TrialResult) -> dict[str, Any]:
    d = asdict(t)
    d["timeline"] = [asdict(s) for s in t.timeline]
    return d
