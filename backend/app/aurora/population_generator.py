"""
Population generator — sample archetype-tagged residents for an Aurora scenario.

Replaces the legacy `oasis_profile_generator.py` (Twitter/Reddit social-sim
profiles) with disaster-realistic agent profiles:
- 9 archetypes (see archetypes.py) sampled per the empirical mix
- Geo-located: assigned to a (lat, lon) inside their district, near a building
- Multilingual: language drawn from district demographics (en/es/ko/zh/...)
- Vulnerability-aware: injury / mobility / dependents drawn per CDC-SVI bands
- LLM-ready: system prompt resolved from archetype, prompt-cache-friendly user
  prompt schema attached

Why this exists separately from scenario_loader: the scenario layer is the
*deck* (deterministic, ships in JSON). The population layer is the *cast*
(stochastic, regenerated per Monte Carlo trial). Splitting lets us reuse one
deck across many trials with different population samples.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, asdict, field
from typing import Any

from .archetypes import ARCHETYPE_ORDER, ARCHETYPES, ArchetypeName
from .scenario import District, Scenario


# Language sub-mix per district primary_language. Reflects LA Census tract
# multi-language households — primary language doesn't mean monolingual.
LANG_SUBMIX: dict[str, dict[str, float]] = {
    "en":  {"en": 0.85, "es": 0.10, "zh": 0.02, "ko": 0.02, "tl": 0.01},
    "es":  {"es": 0.78, "en": 0.20, "zh": 0.01, "ko": 0.01},
    "ko":  {"ko": 0.55, "en": 0.40, "es": 0.04, "zh": 0.01},
    "zh":  {"zh": 0.55, "en": 0.38, "es": 0.05, "ko": 0.02},
    "tl":  {"tl": 0.45, "en": 0.50, "es": 0.05},
}


@dataclass(frozen=True)
class PopulationAgent:
    """One stochastic resident in a Monte Carlo population sample."""
    agent_id: str
    archetype: ArchetypeName
    district_id: str
    home_lat: float
    home_lon: float
    primary_language: str
    age: int
    has_dependents: bool
    mobility_limited: bool
    injured_pre_event: bool
    follower_count: int                    # log-normal-distributed proxy for reach
    cred_weight: float                     # archetype prior, carried for fast filter

    # Per-agent attributes used during sim, but immutable at generation time:
    base_posts_per_hour: float
    risk_aversion: float                   # 0-1, drawn per archetype tendency

    def to_neo4j_props(self) -> dict[str, Any]:
        return asdict(self)


def _pick_archetype(rng: random.Random, district: District) -> ArchetypeName:
    """Sample archetype with mild SVI-tilt: high-SVI districts skew toward
    helpless / helper, low-SVI districts skew toward critic / coordinator.
    """
    weights = {a: ARCHETYPES[a].share for a in ARCHETYPE_ORDER}
    if district.svi > 0.8:
        weights["helpless"] *= 1.4
        weights["helper"] *= 1.2
        weights["critic"] *= 0.8
    elif district.svi < 0.65:
        weights["coordinator"] *= 1.4
        weights["critic"] *= 1.3
        weights["helpless"] *= 0.8
    total = sum(weights.values())
    r = rng.random() * total
    cum = 0.0
    for a in ARCHETYPE_ORDER:
        cum += weights[a]
        if r <= cum:
            return a
    return ARCHETYPE_ORDER[-1]


def _pick_language(rng: random.Random, district: District) -> str:
    sub = LANG_SUBMIX.get(district.primary_language) or {"en": 1.0}
    r = rng.random()
    cum = 0.0
    for lang, p in sub.items():
        cum += p
        if r <= cum:
            return lang
    return district.primary_language


def _follower_count(rng: random.Random, archetype: ArchetypeName) -> int:
    """Log-normal followers; archetype shifts the median."""
    median_by_arch: dict[ArchetypeName, int] = {
        "authority": 25_000, "amplifier": 1_200, "critic": 800,
        "coordinator": 600, "misinformer": 1_500, "conspiracist": 900,
        "eyewitness": 200, "helper": 150, "helpless": 90,
    }
    median = median_by_arch[archetype]
    # Heavy tail
    return max(5, int(rng.lognormvariate(mu=0.0, sigma=1.4) * median))


def _risk_aversion(rng: random.Random, archetype: ArchetypeName) -> float:
    base = {
        "authority": 0.85, "helper": 0.55, "coordinator": 0.50,
        "eyewitness": 0.45, "amplifier": 0.30, "critic": 0.50,
        "helpless": 0.65, "misinformer": 0.25, "conspiracist": 0.20,
    }[archetype]
    return max(0.05, min(0.98, base + rng.gauss(0, 0.10)))


def generate_population(
    scenario: Scenario,
    *,
    n_agents: int = 200,
    seed: int = 42,
) -> list[PopulationAgent]:
    """Sample `n_agents` residents distributed across districts proportional
    to district population. Deterministic given `seed`."""
    rng = random.Random(seed)

    # Allocate agents across districts proportional to population
    pops = [d.population for d in scenario.districts]
    total = sum(pops)
    quotas = [max(1, round(n_agents * p / total)) for p in pops]
    # Clamp any rounding drift
    diff = n_agents - sum(quotas)
    if diff != 0:
        quotas[0] = max(1, quotas[0] + diff)

    out: list[PopulationAgent] = []
    aid = 0
    for district, quota in zip(scenario.districts, quotas):
        for _ in range(quota):
            archetype = _pick_archetype(rng, district)
            arch = ARCHETYPES[archetype]
            lat = district.centroid_lat + rng.uniform(-0.012, 0.012)
            lon = district.centroid_lon + rng.uniform(-0.014, 0.014)
            age = max(0, min(95, int(rng.gauss(36, 18))))
            mobility_limited = rng.random() < (
                0.04 + 0.18 * (age / 95.0) + 0.10 * district.svi
            )
            has_deps = rng.random() < (0.32 + 0.20 * district.svi)
            injured = rng.random() < (0.015 + 0.025 * district.svi)
            out.append(PopulationAgent(
                agent_id=f"P-{district.district_id}-{aid:05d}",
                archetype=archetype,
                district_id=district.district_id,
                home_lat=lat,
                home_lon=lon,
                primary_language=_pick_language(rng, district),
                age=age,
                has_dependents=has_deps,
                mobility_limited=mobility_limited,
                injured_pre_event=injured,
                follower_count=_follower_count(rng, archetype),
                cred_weight=arch.cred_weight,
                base_posts_per_hour=arch.posting_rate_per_hr,
                risk_aversion=_risk_aversion(rng, archetype),
            ))
            aid += 1
    return out


def population_summary(agents: list[PopulationAgent]) -> dict[str, Any]:
    """Quick stats for telemetry / KPI dashboards."""
    by_arch: dict[str, int] = {}
    by_lang: dict[str, int] = {}
    by_district: dict[str, int] = {}
    n_mobility = n_deps = n_injured = 0
    follower_total = 0
    for a in agents:
        by_arch[a.archetype] = by_arch.get(a.archetype, 0) + 1
        by_lang[a.primary_language] = by_lang.get(a.primary_language, 0) + 1
        by_district[a.district_id] = by_district.get(a.district_id, 0) + 1
        n_mobility += int(a.mobility_limited)
        n_deps += int(a.has_dependents)
        n_injured += int(a.injured_pre_event)
        follower_total += a.follower_count
    return {
        "n_agents": len(agents),
        "by_archetype": dict(sorted(by_arch.items(),
                                    key=lambda kv: -kv[1])),
        "by_language": dict(sorted(by_lang.items(),
                                   key=lambda kv: -kv[1])),
        "by_district": by_district,
        "mobility_limited_share": round(n_mobility / max(1, len(agents)), 3),
        "has_dependents_share": round(n_deps / max(1, len(agents)), 3),
        "injured_pre_event_share": round(n_injured / max(1, len(agents)), 3),
        "follower_total": follower_total,
    }
