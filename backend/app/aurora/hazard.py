# SPDX-License-Identifier: Apache-2.0
"""
Aurora hazard schema — HazardSpec and IntensityPoint dataclasses.

HazardSpec encodes the inputs for a hazard event so that hazard data can
live in JSON files under data/hazards/ rather than hard-coded Python constants.

Note: HazardKind and IntensityPoint remain in scenario.py to preserve
existing imports. This module defines HazardSpec for the manifest system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

HazardKind = Literal["earthquake", "flood", "wildfire", "hurricane"]


@dataclass(frozen=True)
class IntensityPoint:
    """One sample of the hazard intensity field at a (lat, lon)."""
    lat: float
    lon: float
    mmi: float                # Modified Mercalli Intensity (or proxy)
    h3_cell: str              # h3 res-9 cell containing the point


@dataclass
class HazardSpec:
    """Hazard event specification that drives intensity-field synthesis."""
    hazard_id: str
    kind: HazardKind
    label: str
    magnitude: float
    epicenter_lat: float
    epicenter_lon: float
    origin_time_iso: str
    duration_hours: int
    intensity_field: list[IntensityPoint] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)
    fragility_pack: str = "hazus_eq_v2.1"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HazardSpec":
        intensity_field = [
            IntensityPoint(**p) for p in d.get("intensity_field", [])
        ]
        return cls(
            hazard_id=d["hazard_id"],
            kind=d["kind"],
            label=d["label"],
            magnitude=d["magnitude"],
            epicenter_lat=d["epicenter_lat"],
            epicenter_lon=d["epicenter_lon"],
            origin_time_iso=d["origin_time_iso"],
            duration_hours=d["duration_hours"],
            intensity_field=intensity_field,
            parameters=d.get("parameters", {}),
            fragility_pack=d.get("fragility_pack", "hazus_eq_v2.1"),
        )
