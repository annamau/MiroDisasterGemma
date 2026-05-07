# SPDX-License-Identifier: Apache-2.0
"""
Aurora city schema — City, District, and per-district anchor dataclasses.

These dataclasses encode the inputs that _synth_buildings_for_district
and _synth_responders consume, so city data can live in JSON files under
data/cities/ rather than hard-coded Python constants.

Note: District is defined here but also remains in scenario.py until
Commit 2 wires the full migration (to preserve existing imports).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class District:
    """Census-tract-or-similar geographic grouping (copy of scenario.District)."""
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
class DistrictBuildingAnchor:
    """Per-district inputs consumed by _synth_buildings_for_district.

    Fields match the keys from the district anchor dicts in scenario_loader.py.
    n_buildings_target corresponds to the buildings_per_district argument.
    """
    district_id: str
    name: str
    lat: float
    lon: float
    population: int
    income: int               # median income USD (maps to dist["income"])
    svi: float
    lang: str
    n_buildings_target: int   # buildings_per_district for this district


@dataclass(frozen=True)
class DistrictResponderAnchor:
    """Per-district inputs consumed by _synth_responders.

    The existing _synth_responders function uses only pop, lat, lon, id,
    name, and svi from the district dict. All other behavior is derived.
    This dataclass makes those dependencies explicit.
    """
    district_id: str
    name: str
    lat: float
    lon: float
    population: int
    svi: float


@dataclass
class City:
    """City definition that drives scenario synthesis."""
    city_id: str
    label: str
    country: str
    iso2: str
    centroid_lat: float
    centroid_lon: float
    districts: list[DistrictBuildingAnchor] = field(default_factory=list)
    building_anchors: list[DistrictBuildingAnchor] = field(default_factory=list)
    responder_anchors: list[DistrictResponderAnchor] = field(default_factory=list)
    import_provenance: dict[str, Any] = field(
        default_factory=lambda: {"sources": [], "imported_at": "2026-05-06"}
    )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "City":
        building_anchors = [
            DistrictBuildingAnchor(**a) for a in d.get("building_anchors", [])
        ]
        responder_anchors = [
            DistrictResponderAnchor(**a) for a in d.get("responder_anchors", [])
        ]
        return cls(
            city_id=d["city_id"],
            label=d["label"],
            country=d["country"],
            iso2=d["iso2"],
            centroid_lat=d["centroid_lat"],
            centroid_lon=d["centroid_lon"],
            districts=building_anchors,  # districts mirrors building_anchors
            building_anchors=building_anchors,
            responder_anchors=responder_anchors,
            import_provenance=d.get("import_provenance", {"sources": [], "imported_at": "2026-05-06"}),
        )
