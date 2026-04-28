"""
Intervention DSL — the "what if" toggles cities, agencies, and insurers
turn on to compute prevention deltas.

An intervention is a typed, declarative mutation applied BEFORE a trial
runs. Three families implemented (one per "tap" the wow-factor pitch
demands: resource pre-positioning, timing change, infrastructure hardening):

    A. RESOURCE_PREPOSITION     — add ambulances/engines/shelter beds to a district
    B. EVAC_TIMING              — issue evacuation order N hours earlier
    C. SEISMIC_RETROFIT         — upgrade fragility curve for buildings of a class
                                  in a district (W1 -> high-code, C1L pre -> high)
    D. MISINFO_PREBUNK          — pre-position trusted-source posts to dampen
                                  the misinfo:authority impressions ratio

The DSL is intentionally narrow — every intervention is a typed dataclass
with a known mutation site in `apply()`. New interventions = add a new
dataclass + a new branch in apply(). Don't grow this past 6-8 types or it
becomes a config language.

Usage:
    iv = ResourcePrepositionIntervention(
        district_id="LA-D03", added_paramedic_units=4,
    )
    mutated_scenario = iv.apply(scenario)
    runtime_overrides = iv.runtime_overrides()
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import dataclass
from typing import Any, Literal

from .hazus_fragility import BuildingClass
from .scenario import FireStation, Hospital, Scenario, Shelter

InterventionKind = Literal[
    "baseline",
    "resource_preposition",
    "evac_timing",
    "seismic_retrofit",
    "misinfo_prebunk",
]


@dataclass(frozen=True)
class Intervention:
    """Base class — concrete subclasses below."""
    intervention_id: str
    kind: InterventionKind
    label: str

    def apply(self, scenario: Scenario) -> Scenario:
        return scenario

    def runtime_overrides(self) -> dict[str, Any]:
        return {}

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass(frozen=True)
class BaselineIntervention(Intervention):
    intervention_id: str = "baseline"
    kind: InterventionKind = "baseline"
    label: str = "No intervention (baseline)"


@dataclass(frozen=True)
class ResourcePrepositionIntervention(Intervention):
    """Add additional paramedic / engine / shelter capacity to a district
    BEFORE the disaster. Models a city pre-staging mutual aid."""
    target_district_id: str = ""
    added_paramedic_units: int = 0
    added_engine_units: int = 0
    added_shelter_capacity: int = 0
    intervention_id: str = ""
    kind: InterventionKind = "resource_preposition"
    label: str = ""

    def apply(self, scenario: Scenario) -> Scenario:
        # Add pre-staged station with extra paramedic + engine units
        d = next((d for d in scenario.districts
                  if d.district_id == self.target_district_id), None)
        if d is None:
            return scenario
        new_stations = list(scenario.fire_stations)
        if self.added_engine_units or self.added_paramedic_units:
            new_stations.append(FireStation(
                station_id=f"{self.target_district_id}-PRESTAGE",
                name=f"Pre-staged Mutual Aid {self.target_district_id}",
                lat=d.centroid_lat, lon=d.centroid_lon, h3_cell=d.h3_cell,
                engines=self.added_engine_units,
                paramedics=self.added_paramedic_units * 2,
                district_id=self.target_district_id,
            ))
        new_shelters = list(scenario.shelters)
        if self.added_shelter_capacity > 0:
            new_shelters.append(Shelter(
                shelter_id=f"{self.target_district_id}-EXTRA",
                name=f"Extra Mutual Aid Shelter {self.target_district_id}",
                lat=d.centroid_lat, lon=d.centroid_lon, h3_cell=d.h3_cell,
                capacity=self.added_shelter_capacity,
                district_id=self.target_district_id,
            ))
        return dataclasses.replace(
            scenario, fire_stations=new_stations, shelters=new_shelters,
        )

    def runtime_overrides(self) -> dict[str, Any]:
        # Pre-positioned ambulances raise the hospital_capacity_floor for the
        # target district. Models the fact that BLS transports keep flowing
        # even when the local hospital's grid is degraded — the new ambulances
        # have their own routing and can divert to undamaged hospitals.
        boost = min(0.30, self.added_paramedic_units * 0.05)
        return {
            "hospital_capacity_floor_by_district": {
                self.target_district_id: 0.55 + boost,
            },
        }


@dataclass(frozen=True)
class EvacTimingIntervention(Intervention):
    """Issue evacuation order N hours earlier. Modeled by (a) reducing
    indoor occupancy at event time and (b) adjusting injury/death rate."""
    target_district_id: str = ""
    advance_hours: int = 0
    expected_compliance: float = 0.55   # fraction of pop that complies
    intervention_id: str = ""
    kind: InterventionKind = "evac_timing"
    label: str = ""

    def apply(self, scenario: Scenario) -> Scenario:
        if self.advance_hours <= 0:
            return scenario
        # Reduce occupants_day for buildings in the target district
        evac_share = min(0.95, self.expected_compliance
                         * (1 - 0.10 ** (self.advance_hours / 6.0)))
        new_buildings = []
        for b in scenario.buildings:
            if b.district_id == self.target_district_id:
                new_buildings.append(dataclasses.replace(
                    b,
                    occupants_day=max(1, int(b.occupants_day * (1 - evac_share))),
                ))
            else:
                new_buildings.append(b)
        return dataclasses.replace(scenario, buildings=new_buildings)


@dataclass(frozen=True)
class SeismicRetrofitIntervention(Intervention):
    """Retrofit a HAZUS class in a district — buildings of that class now
    use high-code fragility instead of pre-code. Approximated by clamping
    `year_built` upward (downstream picks high-code curve when year > 1980).

    For W1 wood frame: cripple-wall bracing + foundation bolting.
    For PC1 tilt-up: roof-wall connection retrofit (post-Northridge).
    For C1L/C1M: column ductility upgrades (rare and expensive).
    """
    target_district_id: str = ""
    target_class: BuildingClass = "W1"
    coverage_share: float = 0.80   # fraction of buildings retrofitted
    intervention_id: str = ""
    kind: InterventionKind = "seismic_retrofit"
    label: str = ""

    def apply(self, scenario: Scenario) -> Scenario:
        new_buildings = []
        # Deterministic: retrofit the first `coverage_share * N` of matching bldgs
        matching_idx = [
            i for i, b in enumerate(scenario.buildings)
            if b.district_id == self.target_district_id
            and b.hazus_class == self.target_class
        ]
        cutoff = int(len(matching_idx) * self.coverage_share)
        retrofit_set = set(matching_idx[:cutoff])
        for i, b in enumerate(scenario.buildings):
            if i in retrofit_set:
                new_buildings.append(dataclasses.replace(b, year_built=2020))
            else:
                new_buildings.append(b)
        return dataclasses.replace(scenario, buildings=new_buildings)


@dataclass(frozen=True)
class MisinfoPrebunkIntervention(Intervention):
    """Pre-position trusted-source posts so authority reach beats misinfo
    in the 6-24h info-vacuum phase. Modeled as a runtime override that
    multiplies authority impressions and dampens misinformer cell decisions."""
    authority_reach_multiplier: float = 3.0
    misinfo_dampener: float = 0.6
    intervention_id: str = ""
    kind: InterventionKind = "misinfo_prebunk"
    label: str = ""

    def runtime_overrides(self) -> dict[str, Any]:
        return {
            "authority_reach_multiplier": self.authority_reach_multiplier,
            "misinfo_dampener": self.misinfo_dampener,
        }


# Registry of preset interventions for the demo deck.
PRESET_INTERVENTIONS: dict[str, Intervention] = {
    "baseline": BaselineIntervention(),

    "preposition_d03_4amb": ResourcePrepositionIntervention(
        intervention_id="preposition_d03_4amb",
        label="Pre-stage 4 ambulances in East LA (D03)",
        target_district_id="LA-D03",
        added_paramedic_units=4,
    ),

    "evac_d03_30min_early": EvacTimingIntervention(
        intervention_id="evac_d03_30min_early",
        label="Evacuate D03 30 min earlier (55% compliance)",
        target_district_id="LA-D03",
        advance_hours=1,
        expected_compliance=0.55,
    ),

    "retrofit_d03_w1": SeismicRetrofitIntervention(
        intervention_id="retrofit_d03_w1",
        label="Retrofit 80% of W1 wood-frame in D03",
        target_district_id="LA-D03",
        target_class="W1",
        coverage_share=0.80,
    ),

    "retrofit_d02_c1l": SeismicRetrofitIntervention(
        intervention_id="retrofit_d02_c1l",
        label="Retrofit 80% of C1L low-rise concrete in Boyle Heights",
        target_district_id="LA-D02",
        target_class="C1L",
        coverage_share=0.80,
    ),

    "prebunk_misinfo": MisinfoPrebunkIntervention(
        intervention_id="prebunk_misinfo",
        label="Pre-bunk misinformation (3x authority reach)",
        authority_reach_multiplier=3.0,
        misinfo_dampener=0.6,
    ),
}


def get_intervention(intervention_id: str) -> Intervention:
    return PRESET_INTERVENTIONS.get(intervention_id,
                                    PRESET_INTERVENTIONS["baseline"])
