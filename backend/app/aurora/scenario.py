"""
Aurora scenario domain — Pydantic-style dataclasses for a city-resilience scenario.

A scenario is the immutable input to a Monte Carlo simulation:
- `Hazard`     — what's happening to the ground (intensity field, timing).
- `Building`   — geo-located structures with HAZUS class + occupancy.
- `Hospital`   — capacity, beds, surge tolerance.
- `FireStation`— responder pool, vehicle counts, base location.
- `Shelter`    — capacity, accessibility.
- `District`   — administrative grouping with demographics + SVI.

`Scenario` aggregates all of the above and is what gets persisted to Neo4j
(see Neo4jStorage.save_scenario, called from /api/scenario/load).

Why dataclasses, not Pydantic: the rest of MiroFish-Offline avoids Pydantic
runtime cost; we mirror that for consistency and zero new dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal, Any

from .hazus_fragility import BuildingClass, DEFAULT_OCCUPANTS

HazardKind = Literal["earthquake", "flood", "wildfire", "hurricane"]


@dataclass(frozen=True)
class IntensityPoint:
    """One sample of the hazard intensity field at a (lat, lon)."""
    lat: float
    lon: float
    mmi: float                # Modified Mercalli Intensity (earthquake)
    h3_cell: str              # h3 res-9 cell containing the point


@dataclass(frozen=True)
class Hazard:
    """Hazard event metadata + intensity field."""
    kind: HazardKind
    name: str                 # human-readable: "M7.2 Puente Hills Blind Thrust"
    magnitude: float          # Mw for earthquake; affects aftershock chain
    epicenter_lat: float
    epicenter_lon: float
    origin_time_iso: str      # "2026-05-12T14:00:00-07:00"
    duration_hours: int = 72  # how long the simulator should run
    intensity_field: list[IntensityPoint] = field(default_factory=list)


@dataclass(frozen=True)
class Building:
    """One geo-located structure (representative agent for many real buildings).

    `representative_count` lets a small simulation roll up to a real city's
    structure count: each Building agent stands for N similar real buildings
    in its h3 cell. Loss totals scale linearly: total_deaths_in_cell =
    sum(per_agent_deaths * representative_count). Default 1 (1 agent = 1 bldg).
    """
    building_id: str
    lat: float
    lon: float
    h3_cell: str
    hazus_class: BuildingClass
    occupants_day: int
    occupants_night: int
    year_built: int
    district_id: str
    address_short: str = ""
    representative_count: int = 1

    @property
    def occupants_at(self, hour: int = 14) -> int:  # noqa: D401
        return self.occupants_day if 7 <= hour < 19 else self.occupants_night


@dataclass(frozen=True)
class Hospital:
    hospital_id: str
    name: str
    lat: float
    lon: float
    h3_cell: str
    beds: int
    er_capacity_per_hour: int
    district_id: str


@dataclass(frozen=True)
class FireStation:
    station_id: str
    name: str
    lat: float
    lon: float
    h3_cell: str
    engines: int
    paramedics: int
    district_id: str


@dataclass(frozen=True)
class Shelter:
    shelter_id: str
    name: str
    lat: float
    lon: float
    h3_cell: str
    capacity: int
    district_id: str


@dataclass(frozen=True)
class District:
    """Census-tract-or-similar geographic grouping."""
    district_id: str
    name: str
    centroid_lat: float
    centroid_lon: float
    h3_cell: str
    population: int
    median_income_usd: int
    svi: float                # Social Vulnerability Index 0-1 (CDC SVI)
    primary_language: str     # ISO 639-1, "en" | "es" | "zh" ...


@dataclass(frozen=True)
class Scenario:
    """The full input deck for a Monte Carlo simulation."""
    scenario_id: str
    label: str
    city: str
    hazard: Hazard
    districts: list[District]
    buildings: list[Building]
    hospitals: list[Hospital]
    fire_stations: list[FireStation]
    shelters: list[Shelter]

    # Computed for telemetry
    @property
    def total_population(self) -> int:
        return sum(d.population for d in self.districts)

    @property
    def total_buildings(self) -> int:
        return len(self.buildings)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly dump (lists of dicts, frozen-dataclass-safe)."""
        return {
            "scenario_id": self.scenario_id,
            "label": self.label,
            "city": self.city,
            "hazard": {
                **{k: v for k, v in asdict(self.hazard).items() if k != "intensity_field"},
                "intensity_field": [asdict(p) for p in self.hazard.intensity_field],
            },
            "districts": [asdict(d) for d in self.districts],
            "buildings": [asdict(b) for b in self.buildings],
            "hospitals": [asdict(h) for h in self.hospitals],
            "fire_stations": [asdict(f) for f in self.fire_stations],
            "shelters": [asdict(s) for s in self.shelters],
            "stats": {
                "total_population": self.total_population,
                "total_buildings": self.total_buildings,
                "districts": len(self.districts),
            },
        }


def occupants_for_class(cls: BuildingClass) -> tuple[int, int]:
    """Default day/night occupancy by HAZUS class (override per-building if known).

    Day = workday peak. Night = sleep hours. Used until we wire FEMA USA
    Structures occupancy schedules.
    """
    base = DEFAULT_OCCUPANTS[cls]
    if cls == "W1":
        # Residential: more people home at night than during workday
        return (max(1, base // 2), base)
    if cls in ("C1L", "C1M"):
        # Commercial: full at work hours, near-empty at night
        return (base, max(1, base // 10))
    # PC1 warehouse: day shift, very low night occupancy
    return (base, max(1, base // 5))
