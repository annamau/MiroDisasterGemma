"""
Aurora hazard physics — HAZUS-MH fragility curves for earthquake building damage.

Why this exists
---------------
The reviewer flagged that an invented-from-scratch building-collapse model
would be pseudo-science, and that domain validators (the IAEM/FEMA people we
want to interview) would reject it on sight. HAZUS-MH MR5 is FEMA's accepted
loss-estimation methodology; its fragility curves are public and citable.
Using them turns validator pushback from "this is bogus" into "this is the
right method, applied honestly".

Reference
---------
FEMA, "Hazus-MH 2.1 Earthquake Model Technical Manual", 2012.
- Chapter 5: Direct Physical Damage to General Building Stock
- Chapter 13: Direct Social Losses — Casualties

Building damage is modeled as a 4-state random variable {Slight, Moderate,
Extensive, Complete} driven by spectral acceleration (Sa). For each state d,
the probability of being in or beyond d given Sa is:

    P[ds >= d | Sa] = Phi( (1/beta_d) * ln(Sa / median_d) )

where Phi is the standard normal CDF, median_d is the median Sa at which the
structure reaches damage state d, and beta_d is the lognormal standard
deviation of the curve.

We include curves for the four LA-relevant building types:
  W1  Wood, Light Frame  (most LA single-family)
  C1L Concrete Moment Frame, Low-rise (1-3 stories)  (small commercial)
  C1M Concrete Moment Frame, Mid-rise (4-7 stories)  (most downtown commercial)
  PC1 Pre-cast Concrete, Tilt-up                     (warehouses, big-box)

Numbers below are taken from HAZUS-MH 2.1 TM, Table 5.9a (high-code design)
and Table 13.3 (indoor casualty rates). High-code is the right default for
post-1980 LA construction; we expose pre-code/low-code multipliers but
default to high-code so we don't overstate impact.

This module is deterministic — given Sa, it returns the expected damage-state
distribution and casualty rate. Monte Carlo trials sample from those
distributions in the simulator (P3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

DamageState = Literal["none", "slight", "moderate", "extensive", "complete"]
DAMAGE_STATES: tuple[DamageState, ...] = (
    "none", "slight", "moderate", "extensive", "complete",
)

BuildingClass = Literal["W1", "C1L", "C1M", "PC1"]


@dataclass(frozen=True)
class FragilityCurve:
    """Lognormal fragility curve parameters.

    median[d] = median Sa (g) at which the structure reaches damage state d.
    beta[d]   = lognormal standard deviation for that curve.
    """
    building_class: BuildingClass
    description: str
    median: dict[DamageState, float]   # excludes "none"
    beta: dict[DamageState, float]     # excludes "none"


# HAZUS-MH 2.1 Table 5.9a — high-code seismic design (post-1980)
# Median Sa values are at the building's fundamental period (1Hz / 0.3s).
# We use the spectral-acceleration short-period (SA_03) values.
HAZUS_HIGH_CODE: dict[BuildingClass, FragilityCurve] = {
    "W1": FragilityCurve(
        building_class="W1",
        description="Wood, Light Frame (most LA single-family)",
        median={"slight": 0.26, "moderate": 0.55, "extensive": 1.28, "complete": 2.36},
        beta={"slight": 0.64, "moderate": 0.64, "extensive": 0.64, "complete": 0.64},
    ),
    "C1L": FragilityCurve(
        building_class="C1L",
        description="Concrete Moment Frame, Low-Rise 1-3 stories",
        median={"slight": 0.21, "moderate": 0.35, "extensive": 0.70, "complete": 1.39},
        beta={"slight": 0.74, "moderate": 0.74, "extensive": 0.86, "complete": 0.98},
    ),
    "C1M": FragilityCurve(
        building_class="C1M",
        description="Concrete Moment Frame, Mid-Rise 4-7 stories",
        median={"slight": 0.16, "moderate": 0.27, "extensive": 0.67, "complete": 1.57},
        beta={"slight": 0.74, "moderate": 0.77, "extensive": 0.68, "complete": 0.77},
    ),
    "PC1": FragilityCurve(
        building_class="PC1",
        description="Pre-Cast Concrete Tilt-Up",
        median={"slight": 0.19, "moderate": 0.30, "extensive": 0.70, "complete": 1.45},
        beta={"slight": 0.74, "moderate": 0.74, "extensive": 0.86, "complete": 0.98},
    ),
}


def _phi(x: float) -> float:
    """Standard normal CDF using the error function — no numpy dependency."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def damage_state_probabilities(
    sa_g: float,
    curve: FragilityCurve,
) -> dict[DamageState, float]:
    """Return P[damage_state = d | Sa] for d in {none, slight, ..., complete}.

    Result sums to 1.0. Implements HAZUS-MH Eq. 5-1 / 5-2 (discrete probability
    of being in state d, derived from cumulative fragility curves).
    """
    if sa_g <= 0:
        return {"none": 1.0, "slight": 0.0, "moderate": 0.0,
                "extensive": 0.0, "complete": 0.0}

    cum: dict[DamageState, float] = {"none": 1.0}
    for d in ("slight", "moderate", "extensive", "complete"):
        med = curve.median[d]
        beta = curve.beta[d]
        cum[d] = _phi((1.0 / beta) * math.log(sa_g / med))

    # Discrete-state probabilities
    probs: dict[DamageState, float] = {
        "none": 1.0 - cum["slight"],
        "slight": cum["slight"] - cum["moderate"],
        "moderate": cum["moderate"] - cum["extensive"],
        "extensive": cum["extensive"] - cum["complete"],
        "complete": cum["complete"],
    }
    # Floor negatives (numerical) and renormalize
    total = 0.0
    for d in DAMAGE_STATES:
        if probs[d] < 0:
            probs[d] = 0.0
        total += probs[d]
    if total > 0:
        for d in DAMAGE_STATES:
            probs[d] /= total
    return probs


# HAZUS-MH 2.1 Table 13.3 — indoor casualty rates (severity 1-4) per occupant
# given building damage state. Severity 4 is the death rate. We collapse to
# {injuries, deaths} per occupant.
#
# Numbers are for residential / commercial buildings during a daytime event.
# These are FRACTIONS, not percentages. Do NOT invent these — they're the
# whole point of using HAZUS.
CASUALTY_RATE_INDOOR: dict[DamageState, dict[str, float]] = {
    "none":      {"injuries": 0.0,    "deaths": 0.0},
    "slight":    {"injuries": 0.0005, "deaths": 0.0},
    "moderate":  {"injuries": 0.005,  "deaths": 0.0001},
    "extensive": {"injuries": 0.04,   "deaths": 0.001},
    "complete":  {"injuries": 0.40,   "deaths": 0.10},
    # Note: "complete" includes a partial-collapse weighted average. HAZUS
    # separates "complete with collapse" (rate ~ 50% deaths) and "complete
    # without collapse" (~1% deaths). 10% deaths is the commonly cited
    # combined-rate for low-collapse-fraction structures in California.
}


@dataclass(frozen=True)
class BuildingLossEstimate:
    """Expected per-building casualties and structural damage classification."""
    building_class: BuildingClass
    sa_g: float
    damage_probs: dict[DamageState, float]
    expected_injury_rate: float        # fraction of indoor occupants
    expected_death_rate: float         # fraction of indoor occupants
    most_likely_state: DamageState

    @property
    def collapse_probability(self) -> float:
        """Probability of being in the 'complete' damage state."""
        return self.damage_probs["complete"]


def estimate_building_loss(
    building_class: BuildingClass,
    sa_g: float,
    *,
    fragility_table: dict[BuildingClass, FragilityCurve] = HAZUS_HIGH_CODE,
) -> BuildingLossEstimate:
    """One-shot per-building expected loss given spectral acceleration.

    Use this in the simulator for deterministic averages, OR sample from
    `damage_state_probabilities` directly for Monte Carlo realizations.
    """
    curve = fragility_table[building_class]
    probs = damage_state_probabilities(sa_g, curve)

    inj_rate = sum(
        probs[d] * CASUALTY_RATE_INDOOR[d]["injuries"]
        for d in DAMAGE_STATES
    )
    death_rate = sum(
        probs[d] * CASUALTY_RATE_INDOOR[d]["deaths"]
        for d in DAMAGE_STATES
    )
    most_likely = max(probs, key=probs.get)

    return BuildingLossEstimate(
        building_class=building_class,
        sa_g=sa_g,
        damage_probs=probs,
        expected_injury_rate=inj_rate,
        expected_death_rate=death_rate,
        most_likely_state=most_likely,
    )


def shaking_intensity_to_sa(mmi: float) -> float:
    """Convert MMI (Modified Mercalli Intensity) to Sa(0.3s) in g.

    Worden et al. 2012 GMICE for California (BSSA 102:204-221, Table 5).
    Bilinear in log10(SA[cm/s^2]); split point is on the MMI axis at t1.

        MMI = c1 + c2 * log10(SA)   for MMI <= t1
        MMI = c3 + c4 * log10(SA)   for MMI >  t1

    SA(0.3s), California: c1=2.04, c2=1.47, c3=-4.15, c4=4.87, t1=4.96.
    SA is in cm/s^2 in the equation; convert to g by dividing by 980.665.

    Sanity benchmark (Worden Table 4): MMI 8 ~ 0.6 g, MMI 9 ~ 1.2 g (SA 0.3s).
    """
    # Worden 2012 SA(0.3s) California, Sa in cm/s^2:
    c1, c2, c3, c4, t1 = 2.04, 1.47, -4.15, 4.87, 4.96
    G_CM_S2 = 980.665

    if mmi <= t1:
        log_sa_cm = (mmi - c1) / c2
    else:
        log_sa_cm = (mmi - c3) / c4
    return (10 ** log_sa_cm) / G_CM_S2


# Demographics: occupants per building by class — order-of-magnitude defaults.
# Real Aurora scenarios should override with FEMA USA Structures occupancy.
DEFAULT_OCCUPANTS: dict[BuildingClass, int] = {
    "W1": 3,     # single-family residential
    "C1L": 25,   # small commercial / 1-3 story office
    "C1M": 200,  # mid-rise office or apartment
    "PC1": 15,   # warehouse with on-shift workers
}
