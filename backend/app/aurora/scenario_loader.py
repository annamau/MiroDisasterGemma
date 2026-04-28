"""
Aurora scenario loader — bake a defensible reference scenario from public data.

Sources & rationale
-------------------
1. USGS Puente Hills Blind Thrust (PHBT) M7.2 ShakeMap scenario:
   https://earthquake.usgs.gov/scenarios/eventpage/bssc2014pthrustss15_se
   We use the published intensity bands as the basis for our MMI field.
2. LA County administrative boundaries / districts:
   approximations of LA city council districts and key sub-areas.
3. FEMA HAZUS general building stock distribution for LA County, 2010 census
   tract roll-up: ~75% W1 (wood), ~12% C1L, ~5% C1M, ~3% PC1, ~5% other.
4. CDC SVI (Social Vulnerability Index) bands for LA tracts (qualitative).

What this module does NOT do
----------------------------
- Pull live USGS/FEMA APIs (those require auth + on-the-day download).
  Instead we **bake** a deterministic snapshot into a JSON file in
  data/reference_scenarios/. That file is the source of truth at demo time
  and ships with the repo so the demo plays back offline.
- Render real GeoTIFF rasters. We sample the field at building locations
  using a simple radial decay model anchored to the published USGS bands.

When real data arrives (P3 stretch goal), swap `_synth_*` with calls to:
    https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=...&format=geojson
    + FEMA USA Structures GPKG (county subset).
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

from .scenario import (
    Building,
    District,
    FireStation,
    Hazard,
    Hospital,
    IntensityPoint,
    Scenario,
    Shelter,
    occupants_for_class,
)
from .hazus_fragility import BuildingClass

# ----- LA Puente Hills Blind Thrust M7.2 anchor data -----

PUENTE_HILLS_EPICENTER = (34.018, -118.060)  # ~Whittier Narrows, USGS ScenarioMap
PUENTE_HILLS_LABEL = "M7.2 Puente Hills Blind Thrust"
PUENTE_HILLS_ORIGIN_ISO = "2026-05-12T14:00:00-07:00"  # midweek, 2pm — workday peak

# USGS-published MMI peak in the LA Basin for PHBT M7.2 is ~IX (violent)
# in a ~10km radius around the epicenter, attenuating to VI by ~40km.
# Ref: USGS ShakeMap PHBT scenario page (intensity contours).
MMI_AT_EPICENTER = 9.0
MMI_FAR_FIELD = 5.5
DECAY_RADIUS_KM = 40.0

# LA city districts anchor list — coarse (8 districts to keep N_buildings tractable
# at ~250 buildings total). Lat/lon are district centroids. Pop / SVI / income
# are 2020 American Community Survey 5-year approximations rolled up to council
# district. Real demos will swap in tract-level data.
LA_DISTRICTS_ANCHOR: list[dict[str, Any]] = [
    {"id": "LA-D01", "name": "Downtown / Little Tokyo", "lat": 34.052, "lon": -118.244,
     "pop": 78_000, "income": 38_000, "svi": 0.78, "lang": "en"},
    {"id": "LA-D02", "name": "Boyle Heights",          "lat": 34.030, "lon": -118.205,
     "pop": 95_000, "income": 36_000, "svi": 0.86, "lang": "es"},
    {"id": "LA-D03", "name": "East LA / Whittier Nar.", "lat": 34.024, "lon": -118.160,
     "pop": 119_000, "income": 41_000, "svi": 0.81, "lang": "es"},
    {"id": "LA-D04", "name": "Koreatown",              "lat": 34.062, "lon": -118.302,
     "pop": 124_000, "income": 42_000, "svi": 0.69, "lang": "ko"},
    {"id": "LA-D05", "name": "Hollywood",              "lat": 34.098, "lon": -118.327,
     "pop": 90_000, "income": 56_000, "svi": 0.55, "lang": "en"},
    {"id": "LA-D06", "name": "Westlake / MacArthur",   "lat": 34.057, "lon": -118.275,
     "pop": 102_000, "income": 33_000, "svi": 0.91, "lang": "es"},
    {"id": "LA-D07", "name": "South LA / Vernon",      "lat": 34.000, "lon": -118.245,
     "pop": 158_000, "income": 35_000, "svi": 0.88, "lang": "es"},
    {"id": "LA-D08", "name": "Mid-City / Crenshaw",    "lat": 34.041, "lon": -118.330,
     "pop": 108_000, "income": 48_000, "svi": 0.72, "lang": "en"},
]

# HAZUS LA-County general-building-stock proportions (post-1980 high-code default)
HAZUS_CLASS_MIX: dict[BuildingClass, float] = {
    "W1":  0.75,
    "C1L": 0.12,
    "C1M": 0.05,
    "PC1": 0.03,
    # Note: 5% remainder is "other" (URM, steel) — folded into PC1 for now.
}
# Renormalize HAZUS_CLASS_MIX to sum to 1 with PC1 absorbing the "other" 5%
_HAZUS_OTHER = 1.0 - sum(HAZUS_CLASS_MIX.values())
HAZUS_CLASS_MIX["PC1"] += _HAZUS_OTHER

H3_RES = 9   # ~150m hex edge — fine enough for building -> cell aggregation


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _h3_of(lat: float, lon: float, res: int = H3_RES) -> str:
    """Lightweight h3-compatible cell ID — quantized lat/lon hash.

    Real h3 res-9 cells have ~150m edge length. Our quantization is
    ~150m (0.0015 deg lat ~ 167m, 0.0018 deg lon at LA latitude ~ 167m).
    This is good enough for "buildings in the same cell aggregate together"
    queries; the wire format mimics h3's `'89...'` prefix so downstream
    code can be swapped for real h3 by upgrading this function.
    """
    qlat = round(lat / 0.0015) * 0.0015
    qlon = round(lon / 0.0018) * 0.0018
    # Pseudo-h3 string: keeps it short, deterministic, sortable by location.
    h = (int((qlat + 90) * 1e4) * 1_000_000) + int((qlon + 180) * 1e4)
    return f"89{h:013d}"


def _mmi_at(lat: float, lon: float) -> float:
    """Radial attenuation from epicenter, anchored to USGS PHBT contours.

    Piecewise-linear-in-log10(d_km) approximation of the USGS ShakeMap
    Puente Hills M7.2 scenario intensity contours:
        d <=  3 km : MMI 9.0   (violent — at epicenter / Whittier Narrows)
        d ~  10 km : MMI 8.0   (severe — Boyle Heights, Downtown LA)
        d ~  20 km : MMI 7.0   (very strong — Hollywood, Mid-City)
        d ~  40 km : MMI 6.0   (strong — far west / SF Valley fringe)
        d > 100 km : MMI 5.5   (light — perceptible but not damaging)
    """
    d = _haversine_km(PUENTE_HILLS_EPICENTER, (lat, lon))
    if d <= 3.0:
        return 9.0
    # Linear in log10(d) from anchors.
    anchors = [(3.0, 9.0), (10.0, 8.0), (20.0, 7.0), (40.0, 6.0), (100.0, 5.5)]
    for (d1, m1), (d2, m2) in zip(anchors, anchors[1:]):
        if d <= d2:
            t = (math.log10(d) - math.log10(d1)) / (math.log10(d2) - math.log10(d1))
            return m1 + (m2 - m1) * t
    return MMI_FAR_FIELD


def _draw_class(rng: random.Random) -> BuildingClass:
    r = rng.random()
    cum = 0.0
    for cls, p in HAZUS_CLASS_MIX.items():
        cum += p
        if r <= cum:
            return cls
    return "W1"


def _synth_buildings_for_district(
    rng: random.Random, dist: dict[str, Any], n_buildings: int,
) -> list[Building]:
    """Place buildings on a small jittered cloud around the district centroid.

    Occupancy bookkeeping (the hard part):
    - We want sum_over_agents(occupants_day * representative_count) ~ district daytime pop.
    - LA workday daytime population = residents - 0.55 * residents (workers commuting out)
      + 0.85 * residents-equivalent of inbound commuters (jobs in district).
    - For a residential-heavy district that nets to ~0.85 * pop daytime indoors.
    - For Downtown / Koreatown (job centers) it can exceed 1.0 of resident pop.
    We use a flat 0.9x factor on resident pop as a defensible mid-range default.
    """
    # Total buildings in district (real-world count) ~ pop/2.9 households + ~18% non-resi.
    est_total_buildings = max(1, int(dist["pop"] / 2.9 * 1.18))
    rep_count = max(1, est_total_buildings // n_buildings)

    daytime_indoor_pop = int(dist["pop"] * 0.9)
    nighttime_indoor_pop = int(dist["pop"] * 0.95)
    # Per AGENT (each agent stands for rep_count buildings, so its represented
    # daytime headcount is daytime_indoor_pop / n_buildings):
    per_agent_day_total = daytime_indoor_pop / n_buildings
    per_agent_night_total = nighttime_indoor_pop / n_buildings
    # That total is the "occupants_day * representative_count" budget. We split
    # it: each agent's `occupants_day` field = per_agent_day_total / rep_count.

    out: list[Building] = []
    for i in range(n_buildings):
        dlat = rng.uniform(-0.012, 0.012)
        dlon = rng.uniform(-0.014, 0.014)
        lat = dist["lat"] + dlat
        lon = dist["lon"] + dlon
        cls = _draw_class(rng)
        # Class-weighted share of district pop. Residences hold most occupants
        # at night, commercial holds them by day. Weights are proxies — sum
        # within district stays ~constant.
        day_w = {"W1": 0.4, "C1L": 1.6, "C1M": 4.0, "PC1": 1.5}.get(cls, 1.0)
        night_w = {"W1": 1.6, "C1L": 0.2, "C1M": 0.4, "PC1": 0.3}.get(cls, 1.0)
        day = max(1, int(per_agent_day_total / rep_count * day_w))
        night = max(1, int(per_agent_night_total / rep_count * night_w))
        if dist["svi"] > 0.8:
            night = int(night * 1.15)  # overcrowding factor at night
        year = rng.choice([1965, 1972, 1985, 1995, 2005, 2015]) if dist["svi"] < 0.7 \
            else rng.choice([1955, 1965, 1972, 1985, 1995])
        out.append(Building(
            building_id=f"{dist['id']}-B{i:03d}",
            lat=lat, lon=lon,
            h3_cell=_h3_of(lat, lon),
            hazus_class=cls,
            occupants_day=day,
            occupants_night=night,
            year_built=year,
            district_id=dist["id"],
            address_short=f"{dist['name'][:18]} #{i}",
            representative_count=rep_count,
        ))
    return out


def _synth_responders(
    rng: random.Random, dist: dict[str, Any],
) -> tuple[list[Hospital], list[FireStation], list[Shelter]]:
    """One small responder + shelter cluster per district. Capacities scale with pop."""
    pop = dist["pop"]
    # Hospital: 1 ~30km^2 LA district usually has 1 small/mid hospital
    h = Hospital(
        hospital_id=f"{dist['id']}-H1",
        name=f"{dist['name']} General",
        lat=dist["lat"] + rng.uniform(-0.003, 0.003),
        lon=dist["lon"] + rng.uniform(-0.003, 0.003),
        h3_cell=_h3_of(dist["lat"], dist["lon"]),
        beds=max(50, pop // 1500),
        er_capacity_per_hour=max(8, pop // 12_000),
        district_id=dist["id"],
    )
    # 2 fire stations per district (LAFD has ~106 stations, ~13 per council district)
    fs: list[FireStation] = []
    for k in range(2):
        fs.append(FireStation(
            station_id=f"{dist['id']}-F{k+1}",
            name=f"LAFD Station {dist['id']}-{k+1}",
            lat=dist["lat"] + rng.uniform(-0.008, 0.008),
            lon=dist["lon"] + rng.uniform(-0.008, 0.008),
            h3_cell=_h3_of(dist["lat"], dist["lon"]),
            engines=rng.randint(2, 4),
            paramedics=rng.randint(4, 10),
            district_id=dist["id"],
        ))
    # 1-2 shelters per district (schools / community centers)
    sh: list[Shelter] = []
    n_shel = 2 if dist["svi"] > 0.75 else 1
    for k in range(n_shel):
        sh.append(Shelter(
            shelter_id=f"{dist['id']}-S{k+1}",
            name=f"{dist['name']} Shelter {k+1}",
            lat=dist["lat"] + rng.uniform(-0.006, 0.006),
            lon=dist["lon"] + rng.uniform(-0.006, 0.006),
            h3_cell=_h3_of(dist["lat"], dist["lon"]),
            capacity=max(150, pop // 800),
            district_id=dist["id"],
        ))
    return [h], fs, sh


def build_la_puente_hills_m72(
    *, seed: int = 20260512, buildings_per_district: int = 32,
) -> Scenario:
    """Synthesize the LA Puente Hills M7.2 reference scenario.

    Deterministic given `seed`. Default seed is the scenario origin date as int.
    `buildings_per_district=32` × 8 districts = 256 buildings — matches the
    'hackathon target ≥200 agents' KPI.
    """
    rng = random.Random(seed)

    districts: list[District] = []
    buildings: list[Building] = []
    hospitals: list[Hospital] = []
    fire_stations: list[FireStation] = []
    shelters: list[Shelter] = []

    for d in LA_DISTRICTS_ANCHOR:
        districts.append(District(
            district_id=d["id"],
            name=d["name"],
            centroid_lat=d["lat"],
            centroid_lon=d["lon"],
            h3_cell=_h3_of(d["lat"], d["lon"]),
            population=d["pop"],
            median_income_usd=d["income"],
            svi=d["svi"],
            primary_language=d["lang"],
        ))
        buildings.extend(_synth_buildings_for_district(rng, d, buildings_per_district))
        h, fs, sh = _synth_responders(rng, d)
        hospitals.extend(h)
        fire_stations.extend(fs)
        shelters.extend(sh)

    # Build intensity field by sampling at every district centroid + a 5x5 grid
    # over the bounding box. This is what the simulator queries per building.
    intensity: list[IntensityPoint] = []
    seen_cells: set[str] = set()
    for d in LA_DISTRICTS_ANCHOR:
        cell = _h3_of(d["lat"], d["lon"])
        if cell not in seen_cells:
            intensity.append(IntensityPoint(
                lat=d["lat"], lon=d["lon"],
                mmi=_mmi_at(d["lat"], d["lon"]),
                h3_cell=cell,
            ))
            seen_cells.add(cell)
    # Add a coarse 5x5 grid covering roughly 34.00..34.10 lat / -118.34..-118.16 lon
    for i in range(5):
        for j in range(5):
            lat = 34.00 + i * 0.025
            lon = -118.34 + j * 0.045
            cell = _h3_of(lat, lon)
            if cell in seen_cells:
                continue
            intensity.append(IntensityPoint(
                lat=lat, lon=lon, mmi=_mmi_at(lat, lon), h3_cell=cell,
            ))
            seen_cells.add(cell)

    hazard = Hazard(
        kind="earthquake",
        name=PUENTE_HILLS_LABEL,
        magnitude=7.2,
        epicenter_lat=PUENTE_HILLS_EPICENTER[0],
        epicenter_lon=PUENTE_HILLS_EPICENTER[1],
        origin_time_iso=PUENTE_HILLS_ORIGIN_ISO,
        duration_hours=72,
        intensity_field=intensity,
    )

    return Scenario(
        scenario_id="la-puente-hills-m72-ref",
        label=PUENTE_HILLS_LABEL,
        city="Los Angeles, CA",
        hazard=hazard,
        districts=districts,
        buildings=buildings,
        hospitals=hospitals,
        fire_stations=fire_stations,
        shelters=shelters,
    )


def save_reference_scenario(out_path: Path | str | None = None) -> Path:
    """Bake the LA M7.2 reference scenario to JSON. Idempotent."""
    scn = build_la_puente_hills_m72()
    out_path = Path(out_path) if out_path else (
        Path(__file__).resolve().parents[3] / "data" / "reference_scenarios"
        / "la_puente_hills_m72.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scn.to_dict(), indent=2))
    return out_path


def load_reference_scenario(path: Path | str) -> dict[str, Any]:
    """Load a baked scenario JSON. Returns the dict; deserialization to
    Scenario dataclass is the caller's job (typically the API layer)."""
    return json.loads(Path(path).read_text())
