# SPDX-License-Identifier: Apache-2.0
"""
Aurora manifest loader — read City, HazardSpec, and Case from data files,
then synthesize a full Scenario identical to what the old builders produced.

File layout:
    data/cities/<city_id>.json    → City (with building_anchors)
    data/hazards/<hazard_id>.json → HazardSpec (with intensity_field)
    data/cases/<case_id>.yaml     → Case (references city_id + hazard_id)

load_case() returns the same Scenario shape as the old builders so the
agent_runtime, API, and golden-test gate see zero change.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import yaml  # pyyaml

from .case import Case
from .city import City
from .hazard import HazardSpec
from .scenario import (
    Building,
    District,
    FireStation,
    Hazard,
    Hospital,
    IntensityPoint,
    Scenario,
    Shelter,
)
from .scenario_loader import (
    _synth_buildings_for_district,
    _synth_responders,
    _h3_of,
    HAZUS_CLASS_MIX,
)

# Resolve data root relative to this file: backend/app/aurora/ → repo root / data/
_DATA_ROOT = Path(__file__).resolve().parents[4] / "data"


def load_city(city_id: str) -> City:
    """Read data/cities/<city_id>.json and return a City."""
    path = _DATA_ROOT / "cities" / f"{city_id}.json"
    data = json.loads(path.read_text())
    return City.from_dict(data)


def load_hazard(hazard_id: str) -> HazardSpec:
    """Read data/hazards/<hazard_id>.json and return a HazardSpec."""
    path = _DATA_ROOT / "hazards" / f"{hazard_id}.json"
    data = json.loads(path.read_text())
    return HazardSpec.from_dict(data)


def load_case(case_id: str) -> Scenario:
    """Read data/cases/<case_id>.yaml, load city + hazard, synthesize Scenario.

    The resulting Scenario is identical in shape and content to what the
    original builder functions produce, given the same seed and district
    anchors. This is the load-bearing guarantee for the golden test.
    """
    case_path = _DATA_ROOT / "cases" / f"{case_id}.yaml"
    case_data = yaml.safe_load(case_path.read_text())
    case = Case.from_dict(case_data)

    city = load_city(case.city_id)
    hazard_spec = load_hazard(case.hazard_id)

    seed = case_data.get("seed", 42)
    rng = random.Random(seed)

    districts: list[District] = []
    buildings: list[Building] = []
    hospitals: list[Hospital] = []
    fire_stations: list[FireStation] = []
    shelters: list[Shelter] = []

    for anchor in city.building_anchors:
        # Reconstruct the dist dict shape that _synth_buildings_for_district
        # and _synth_responders expect. Keys must match EXACTLY.
        dist: dict[str, Any] = {
            "id":     anchor.district_id,
            "name":   anchor.name,
            "lat":    anchor.lat,
            "lon":    anchor.lon,
            "pop":    anchor.population,
            "income": anchor.income,
            "svi":    anchor.svi,
            "lang":   anchor.lang,
        }

        districts.append(District(
            district_id=dist["id"],
            name=dist["name"],
            centroid_lat=dist["lat"],
            centroid_lon=dist["lon"],
            h3_cell=_h3_of(dist["lat"], dist["lon"]),
            population=dist["pop"],
            median_income_usd=dist["income"],
            svi=dist["svi"],
            primary_language=dist["lang"],
        ))
        buildings.extend(
            _synth_buildings_for_district(rng, dist, anchor.n_buildings_target)
        )
        h, fs, sh = _synth_responders(rng, dist)
        hospitals.extend(h)
        fire_stations.extend(fs)
        shelters.extend(sh)

    # Rebuild intensity field from the stored IntensityPoint list
    intensity: list[IntensityPoint] = [
        IntensityPoint(
            lat=p.lat, lon=p.lon, mmi=p.mmi, h3_cell=p.h3_cell,
        )
        for p in hazard_spec.intensity_field
    ]

    hazard = Hazard(
        kind=hazard_spec.kind,
        name=hazard_spec.label,
        magnitude=hazard_spec.magnitude,
        epicenter_lat=hazard_spec.epicenter_lat,
        epicenter_lon=hazard_spec.epicenter_lon,
        origin_time_iso=hazard_spec.origin_time_iso,
        duration_hours=hazard_spec.duration_hours,
        intensity_field=intensity,
    )

    return Scenario(
        scenario_id=case.case_id,
        label=case.ui_label,
        city=case_data.get("city_display", case.city_id),
        hazard=hazard,
        districts=districts,
        buildings=buildings,
        hospitals=hospitals,
        fire_stations=fire_stations,
        shelters=shelters,
    )
