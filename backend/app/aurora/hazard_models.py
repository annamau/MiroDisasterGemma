"""
Hazard time-evolution models — Omori aftershocks + infrastructure cascade.

These are the deterministic physics layers that mutate the scenario state
hour-by-hour during a Monte Carlo simulation. Kept LLM-free intentionally
(physics is cheap, LLM is the budget item).

Models implemented
------------------
1. Omori aftershock chain (Utsu 1961): aftershock rate decays as
       n(t) = K / (t + c)^p
   where t is hours since mainshock, K calibrated from mainshock magnitude
   via Bath's law (largest aftershock ~ Mw - 1.2), p ~ 1.0 for California,
   c ~ 0.05 days. Aftershock magnitudes drawn from Gutenberg-Richter (b=1).

2. Infrastructure cascade: power -> comms -> hospitals -> shelter capacity.
   Triggers depend on the % of buildings in `complete` damage state in each
   district (proxy for substation, cell-tower, water-main damage).
       - Power outage: triggers when collapse_share > 0.04 in district
       - Comms degraded: triggers when collapse_share > 0.06 OR power down
       - Hospital surge cap drops to 60% of nominal when power degraded;
         drops to 25% when comms also degraded (no triage routing).
       - Shelter capacity drops to 70% if power down (no AC/heat in summer/
         winter pulses).

These cascades are the physics of why "harden the substation in District 4"
or "back-up cell tower in District 2" matters. Without them, every
intervention looks the same.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


# ---- Aftershocks (Omori-Utsu) ----

@dataclass(frozen=True)
class AftershockEvent:
    hour: float
    magnitude: float
    epicenter_lat: float
    epicenter_lon: float


def aftershock_chain(
    mainshock_mag: float,
    epicenter_lat: float,
    epicenter_lon: float,
    *,
    duration_hours: int = 72,
    seed: int = 31,
) -> list[AftershockEvent]:
    """Generate a deterministic aftershock chain over `duration_hours`.

    Modified Omori law (Utsu 1961, JPCG):
        n(t) = K / (t + c)^p,  with t in days
    For California, p=1.07, c=0.04 days, K calibrated from Bath's law
    (Bath 1965): the largest aftershock has magnitude ~ Mw - 1.2.
    Magnitudes drawn from Gutenberg-Richter b=1 truncated [3.0, mag_max].
    Aftershocks cluster spatially around the mainshock; we use a 2D Gaussian
    cloud with sigma = 8 km for M7 mainshocks (Helmstetter & Sornette 2002).
    """
    rng = random.Random(seed)
    # Reasenberg & Jones 1989 SoCal generic: p ~ 1.07, c ~ 0.05 days, b=1.
    p, c = 1.07, 0.05
    mag_max = mainshock_mag - 1.2

    # Calibrate K so total M3+ aftershocks in 72h matches Hauksson 2011 LA
    # review numbers (~150 for M7.0, ~250 for M7.5). Scale linearly across
    # the magnitude range we care about — keep gentle, real Omori has a
    # 10**(b*(Mw - Mc)) productivity term but b=0.7-1.0 in SoCal so a
    # roughly linear-in-Mw approximation lands within 25% of literature.
    target_total = int(50 + 100 * (mainshock_mag - 6.5))   # ~120 for M7.2
    duration_days = duration_hours / 24.0
    # Integral of K/(t+c)^p from 0 to duration_days
    integral = (((duration_days + c) ** (1 - p)) - (c ** (1 - p))) / (1 - p)
    K = target_total / max(abs(integral), 1e-6)

    events: list[AftershockEvent] = []
    for hour in range(duration_hours):
        # Use the *midpoint* of the hour for the rate, and integrate over
        # the hour rather than treating it as instantaneous — kills the
        # singularity-near-t=0 sampling explosion.
        t_start_day = hour / 24.0
        t_end_day = (hour + 1) / 24.0
        # Closed-form integral of K/(t+c)^p over [t_start, t_end]
        expected_n = K * (
            ((t_end_day + c) ** (1 - p)) - ((t_start_day + c) ** (1 - p))
        ) / (1 - p)
        expected_n = abs(expected_n)
        n_this_hr = _poisson(expected_n, rng)
        for _ in range(n_this_hr):
            # Gutenberg-Richter inverse CDF for b=1 truncated [Mc=3.0, mag_max]:
            #   F(M) = 1 - 10^(-(M - Mc))  for Mc <= M <= mag_max
            # Inverse with U ~ Uniform(0, F(mag_max)):
            Mc = 3.0
            F_max = 1.0 - 10 ** (-(mag_max - Mc))
            u = rng.random() * F_max
            mag = Mc - math.log10(1.0 - u)
            mag = min(mag_max, mag)
            # Spatial: 2D Gaussian, sigma ~ 0.07 deg (~8 km at LA latitude)
            dlat = rng.gauss(0, 0.07)
            dlon = rng.gauss(0, 0.07)
            events.append(AftershockEvent(
                hour=hour + rng.random(),
                magnitude=round(mag, 2),
                epicenter_lat=epicenter_lat + dlat,
                epicenter_lon=epicenter_lon + dlon,
            ))
    events.sort(key=lambda e: e.hour)
    return events


def _poisson(rate: float, rng: random.Random) -> int:
    """Knuth Poisson sampler — fine for small rates we use here."""
    if rate <= 0:
        return 0
    L = math.exp(-rate)
    k, p = 0, 1.0
    while True:
        k += 1
        p *= rng.random()
        if p < L:
            return k - 1


# ---- Infrastructure cascade ----

@dataclass
class DistrictInfraState:
    district_id: str
    power_ok: bool = True
    comms_ok: bool = True
    water_ok: bool = True
    # Capacity multipliers; downstream consumers (hospitals, shelters) read these.
    hospital_capacity_mult: float = 1.0
    shelter_capacity_mult: float = 1.0


def update_infra_state(
    states: dict[str, DistrictInfraState],
    collapse_share_by_district: dict[str, float],
    *,
    aftershock_in_district: dict[str, bool] | None = None,
) -> dict[str, DistrictInfraState]:
    """Apply collapse-share thresholds to flip infra flags. Idempotent —
    once a flag flips off, it doesn't flip back without an explicit
    intervention (those are applied separately in the intervention DSL)."""
    aftershock_in_district = aftershock_in_district or {}
    for did, st in states.items():
        col = collapse_share_by_district.get(did, 0.0)
        nudge = 1.5 if aftershock_in_district.get(did) else 1.0
        adj = col * nudge

        if adj > 0.04:
            st.power_ok = False
        if adj > 0.06 or not st.power_ok:
            st.comms_ok = False
        if adj > 0.05:
            st.water_ok = False

        if not st.power_ok and not st.comms_ok:
            st.hospital_capacity_mult = 0.25
        elif not st.power_ok:
            st.hospital_capacity_mult = 0.60
        else:
            st.hospital_capacity_mult = 1.0

        if not st.power_ok:
            st.shelter_capacity_mult = 0.70
        else:
            st.shelter_capacity_mult = 1.0
    return states


def init_infra_state(district_ids: list[str]) -> dict[str, DistrictInfraState]:
    return {did: DistrictInfraState(district_id=did) for did in district_ids}


# ---- Aggregate aftershock impact ----

def aftershock_intensity_bump(
    aftershock: AftershockEvent, lat: float, lon: float,
) -> float:
    """Approximate MMI bump from a single aftershock at (lat, lon).
    Uses the same anchor-decay shape as the mainshock. Aftershocks <M5.0
    are ignorable structurally."""
    if aftershock.magnitude < 4.5:
        return 0.0
    d_lat = lat - aftershock.epicenter_lat
    d_lon = lon - aftershock.epicenter_lon
    d_km = math.sqrt(d_lat ** 2 + d_lon ** 2) * 111.0
    if d_km <= 3.0:
        peak = aftershock.magnitude - 1.5  # rough MMI peak
        return max(0.0, peak)
    decay = max(0.0, (aftershock.magnitude - 1.5) - 1.0 * math.log10(d_km / 3.0))
    return decay
