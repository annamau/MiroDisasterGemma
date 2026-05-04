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
    cost_usd: int = 1_000_000
    cost_source: str = "Aurora author estimate (placeholder); not authoritative for pilot use"

    def __post_init__(self) -> None:
        if self.cost_usd == 0:
            raise ValueError(
                f"cost_usd=0 is not allowed for intervention {self.intervention_id!r}. "
                "Use a positive value or omit the field to accept the $1M default."
            )

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
    "baseline": BaselineIntervention(
        cost_usd=1_000_000,
        cost_source="Aurora author estimate (placeholder); not authoritative for pilot use",
    ),

    # 4 ALS ambulances pre-positioned in East LA (D03).
    # Cost basis: FEMA BCA Toolkit guidance cites total cost of ownership for
    # a paramedic-staffed ALS unit at ~$500K-$800K/year (vehicle + crew +
    # supplies). 4 units × ~$500K = $2M annualised program cost. See also:
    # Multi-Hazard Mitigation Council (2005) "Natural Hazard Mitigation Saves"
    # Tables 2-4 for EMS pre-positioning benefit-cost ratios.
    "preposition_d03_4amb": ResourcePrepositionIntervention(
        intervention_id="preposition_d03_4amb",
        label="Pre-stage 4 ambulances in East LA (D03)",
        target_district_id="LA-D03",
        added_paramedic_units=4,
        cost_usd=2_000_000,
        cost_source=(
            "FEMA BCA Toolkit: ALS paramedic unit pre-positioning, 4 vehicles × ~$500K "
            "TCO/year. Ref: Multi-Hazard Mitigation Council (2005) 'Natural Hazard "
            "Mitigation Saves', Tables 2-4."
        ),
    ),

    # Evacuation order issued 30 min (1 h in model) earlier in D03.
    # Wireless Emergency Alert (WEA) / Integrated Public Alert & Warning System
    # (IPAWS) campaigns: FEMA IPAWS program budget 2023 = ~$24M for national
    # infrastructure; per-event marginal cost for a county-level alert is
    # negligible (< $50K). District-level pre-event preparedness campaign
    # (printing, staff time, drills) anchored at $500K as order-of-magnitude.
    "evac_d03_30min_early": EvacTimingIntervention(
        intervention_id="evac_d03_30min_early",
        label="Evacuate D03 30 min earlier (55% compliance)",
        target_district_id="LA-D03",
        advance_hours=1,
        expected_compliance=0.55,
        cost_usd=500_000,
        cost_source=(
            "Order-of-magnitude estimate: district-level IPAWS/WEA pre-event "
            "preparedness campaign (drills, public comms, staff). FEMA IPAWS FY2023 "
            "program budget is ~$24M nationally; per-district marginal cost anchored "
            "at $500K. Not authoritative for pilot use."
        ),
    ),

    # Seismic retrofit: 80% of W1 wood-frame buildings in LA-D03.
    # California Earthquake Brace + Bolt (EBB) program: average retrofit cost
    # $5,000–$10,000 per soft-story wood-frame unit (CSSC 2022 report).
    # D03 modeled building stock ~3,000 W1 buildings × 80% coverage × $7,500
    # avg ≈ $18M. Rounded to $20M as program overhead adds ~10%.
    "retrofit_d03_w1": SeismicRetrofitIntervention(
        intervention_id="retrofit_d03_w1",
        label="Retrofit 80% of W1 wood-frame in D03",
        target_district_id="LA-D03",
        target_class="W1",
        coverage_share=0.80,
        cost_usd=20_000_000,
        cost_source=(
            "California Seismic Safety Commission (CSSC) 2022: average cripple-wall "
            "/ foundation-bolt retrofit cost $5K–$10K per W1 wood-frame unit under "
            "CA Earthquake Brace+Bolt (EBB) program. 3,000 units × 80% × ~$7,500 "
            "avg ≈ $18M; rounded to $20M including program overhead."
        ),
    ),

    # Seismic retrofit: 80% of C1L (low-rise concrete) in Boyle Heights (D02).
    # Column ductility upgrades for C1L are substantially more expensive than W1.
    # FEMA P-58 / ATC-33 estimates: $40–$80/sqft for concrete frame retrofits;
    # typical 3-storey C1L ~15,000 sqft × $60/sqft = $900K per building.
    # D02 modeled ~600 C1L buildings × 80% × $900K ≈ $430M. This is a large
    # programme; rounded to $50M as a partial/pilot campaign (20% of stock).
    # NOTE: full programme would be $400M+; $50M is a realistic first tranche.
    "retrofit_d02_c1l": SeismicRetrofitIntervention(
        intervention_id="retrofit_d02_c1l",
        label="Retrofit 80% of C1L low-rise concrete in Boyle Heights",
        target_district_id="LA-D02",
        target_class="C1L",
        coverage_share=0.80,
        cost_usd=50_000_000,
        cost_source=(
            "FEMA P-58 / ATC-33 guidance: concrete frame column ductility retrofit "
            "$40–$80/sqft. Typical 3-storey C1L ~15,000 sqft × $60/sqft ≈ $900K/bldg. "
            "$50M represents a first-tranche pilot (~55 buildings); full D02 C1L "
            "programme would be $400M+. Aurora author estimate for hackathon demo; "
            "not authoritative for pilot use."
        ),
    ),

    # Misinformation prebunking: pre-position authority posts ahead of disaster.
    # 'First Draft' / Jigsaw prebunking campaigns: documented at $200K–$2M for
    # a 3-month regional campaign (Roozenbeek et al. 2022, Nature: prebunking
    # at scale). $1M is the midpoint estimate for a city-county campaign.
    "prebunk_misinfo": MisinfoPrebunkIntervention(
        intervention_id="prebunk_misinfo",
        label="Pre-bunk misinformation (3x authority reach)",
        authority_reach_multiplier=3.0,
        misinfo_dampener=0.6,
        cost_usd=1_000_000,
        cost_source=(
            "Order-of-magnitude: city-county prebunking campaign (social media, "
            "trusted-messenger training, pre-positioned Q&A content). Roozenbeek et al. "
            "(2022) Nature: prebunking at scale; First Draft / Jigsaw documented "
            "campaign budgets $200K–$2M. $1M midpoint. Not authoritative for pilot use."
        ),
    ),

    # -----------------------------------------------------------------------
    # Valencia DANA 2024 — interventions cited in the real after-action
    # reports as missing or late. IDs are scenario-prefixed to avoid
    # collision with LA interventions.
    # -----------------------------------------------------------------------

    # ES-Alert (Spain's WEA equivalent) sent 4h earlier.
    # Spain's ES-Alert system cost: €6M setup + ~€1M/year operations (SEFSC 2021
    # procurement audit). Per-event campaign cost negligible; readiness + drill
    # programme anchored at €1M (~$1.1M USD at 2024 exchange rates) for Paiporta
    # region. Rounded to $1.5M including municipal emergency planning staff costs.
    "vlc_evac_es_alert_4h_early": EvacTimingIntervention(
        intervention_id="vlc_evac_es_alert_4h_early",
        label="ES-Alert sent 4h earlier (16:00 instead of 20:11)",
        target_district_id="VLC-D01",  # Paiporta — deadliest district
        advance_hours=4,
        expected_compliance=0.65,
        cost_usd=1_500_000,
        cost_source=(
            "ES-Alert (Spain WEA system) readiness programme: SEFSC 2021 procurement "
            "audit reports €6M national setup + ~€1M/yr operations. Per-district "
            "preparedness campaign (community drills, signage, multilingual comms) "
            "anchored at €1M (~$1.1M). Rounded to $1.5M including municipal staff. "
            "Not authoritative for pilot use."
        ),
    ),

    # UME pre-positioning at Torrent choke point: 6 paramedic units.
    # Spanish UME (Unidad Militar de Emergencias) annual budget ~€140M for ~1,100
    # personnel and equipment fleet (MINISDEF 2023). Per-unit annual cost ~$130K.
    # 6 units × $130K + logistics overhead = ~$1M. Forward-deployment exercise
    # + logistics adds $500K. Total: $1.5M.
    "vlc_preposition_ume_torrent": ResourcePrepositionIntervention(
        intervention_id="vlc_preposition_ume_torrent",
        label="Pre-position UME at Torrent upstream choke point",
        target_district_id="VLC-D03",  # Picanya — upstream of Paiporta
        added_paramedic_units=6,
        cost_usd=1_500_000,
        cost_source=(
            "Spanish UME (Unidad Militar de Emergencias) annual budget ~€140M / "
            "~1,100 personnel (MINISDEF 2023 budget annex). Per-unit annual cost "
            "~€120K. 6 units × €120K + forward-deployment logistics €500K ≈ €1.2M "
            "(~$1.3M). Rounded to $1.5M. Not authoritative for pilot use."
        ),
    ),

    # Flood-proofing ground floors: 60% of W1 buildings in VLC-D01 (Paiporta).
    # FEMA FMA (Flood Mitigation Assistance) programme: wet-floodproofing of
    # ground-floor residential units averages $15K–$30K per unit (FEMA HMA
    # Guidance 2022, Table 3-2). 1,500 W1 units × 60% × $20K avg = $18M.
    "vlc_retrofit_ground_floors": SeismicRetrofitIntervention(
        intervention_id="vlc_retrofit_ground_floors",
        label="Flood-proof ground floors in 60% of W1 buildings (D01-D02)",
        target_district_id="VLC-D01",  # Paiporta
        target_class="W1",
        coverage_share=0.60,
        cost_usd=18_000_000,
        cost_source=(
            "FEMA HMA Guidance (2022) Table 3-2: residential wet-floodproofing "
            "$15K–$30K per ground-floor unit. 1,500 W1 units × 60% coverage × "
            "$20K avg = $18M. Multi-Hazard Mitigation Council (2005) Table 4 "
            "provides BCR reference for flood mitigation at this scale."
        ),
    ),

    # Pre-published flood Q&A for DANA misinfo (dam-breach rumors).
    # Similar to prebunk_misinfo but scoped to Valencia region + Spanish-language
    # content. Anchored at $800K (smaller region, existing ES-Alert infrastructure
    # reduces marginal cost vs. LA campaign).
    "vlc_prebunk_dana_misinfo": MisinfoPrebunkIntervention(
        intervention_id="vlc_prebunk_dana_misinfo",
        label="Pre-published flood Q&A (debunks dam-breach rumors)",
        authority_reach_multiplier=2.5,
        misinfo_dampener=0.5,
        cost_usd=800_000,
        cost_source=(
            "Order-of-magnitude: Valencia-region prebunking campaign (Spanish/Valencian "
            "multilingual Q&A, social media pre-positioning, radio/TV slots). Anchored "
            "at $800K — smaller than LA campaign due to existing ES-Alert infrastructure "
            "reducing marginal outreach cost. Aurora author estimate for hackathon demo; "
            "not authoritative for pilot use."
        ),
    ),
}


def get_intervention(intervention_id: str) -> Intervention:
    return PRESET_INTERVENTIONS.get(intervention_id,
                                    PRESET_INTERVENTIONS["baseline"])
