"""
Responder generator — fire/EMS/police agents from scenario fire stations.

Each FireStation in the scenario produces N engine + paramedic units. Each unit
is an agent with:
- Position (starts at station, mutates during sim)
- Resource budget (water, paramedic-hours, fuel) — *finite*, drives realism
- Decision policy (LLM-routed for non-trivial choices, fast deterministic
  rules for low-stakes triage)
- Comms state (radio + cellular; affected by infrastructure cascade)

Why we model resources as scarce
--------------------------------
The single biggest finding from PHBT M7.2 / Northridge / Big-One studies is
that response capacity is overwhelmed in the first 6 hours: hospitals fill in
~90 min, ambulances are saturated within 2 hours. Without finite resources,
"prevention" interventions look indistinguishable in MC because every life
gets saved. The whole point of the simulator is to surface the trade-offs
that exist BECAUSE responders run out of capacity. This module is what makes
those trade-offs computable.

Reference numbers (LAFD 2023 ops report, FEMA NIMS):
- Engine company water budget: 500 gal onboard + ~200 gal/min from hydrant
  (when grid is up — hydrant flow drops to 30% in widespread main breaks).
- Paramedic unit: 2 medics, 30-90 min per BLS transport round trip.
- Engine deploy radius from base in surface-street disaster: ~3-5 km / hour.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .scenario import FireStation, Hospital, Scenario

ResponderKind = Literal["engine", "paramedic", "police"]


@dataclass
class ResponderAgent:
    """One responder unit. Mutable during simulation (state changes per tick)."""
    agent_id: str
    kind: ResponderKind
    home_station_id: str
    home_lat: float
    home_lon: float
    cur_lat: float
    cur_lon: float
    crew_size: int
    # Resource budgets
    water_gallons: float                # engines only; 0 for paramedic/police
    paramedic_capacity_per_hr: int      # patients per hour
    fuel_hours: float                   # operational time before refuel
    # State
    status: str = "ready"               # ready | enroute | onscene | returning | offline
    assigned_incident: str | None = None
    radio_ok: bool = True
    cellular_ok: bool = True
    fatigue_level: float = 0.0          # 0-1; degrades decision quality

    def to_neo4j_props(self) -> dict[str, Any]:
        return asdict(self)


def _engine_unit(station: FireStation, idx: int, rng: random.Random) -> ResponderAgent:
    return ResponderAgent(
        agent_id=f"E-{station.station_id}-{idx}",
        kind="engine",
        home_station_id=station.station_id,
        home_lat=station.lat,
        home_lon=station.lon,
        cur_lat=station.lat,
        cur_lon=station.lon,
        crew_size=4,
        water_gallons=500.0,
        paramedic_capacity_per_hr=0,
        fuel_hours=8.0 + rng.uniform(-0.5, 0.5),
    )


def _paramedic_unit(
    station: FireStation, idx: int, rng: random.Random,
) -> ResponderAgent:
    return ResponderAgent(
        agent_id=f"M-{station.station_id}-{idx}",
        kind="paramedic",
        home_station_id=station.station_id,
        home_lat=station.lat,
        home_lon=station.lon,
        cur_lat=station.lat,
        cur_lon=station.lon,
        crew_size=2,
        water_gallons=0.0,
        paramedic_capacity_per_hr=4,   # ~15 min per BLS in optimal conds
        fuel_hours=10.0 + rng.uniform(-0.5, 0.5),
    )


def generate_responders(
    scenario: Scenario,
    *,
    seed: int = 17,
) -> list[ResponderAgent]:
    """One engine per `engines` count + (paramedics // 2) ambulance units
    per station. Police units are NOT yet modeled here — added in P3 if
    the demo benefits."""
    rng = random.Random(seed)
    out: list[ResponderAgent] = []
    for st in scenario.fire_stations:
        for i in range(st.engines):
            out.append(_engine_unit(st, i, rng))
        # Paramedic count in scenario is medics-on-shift, ~2 per ambulance
        n_amb = max(1, st.paramedics // 2)
        for i in range(n_amb):
            out.append(_paramedic_unit(st, i, rng))
    return out


def responder_summary(units: list[ResponderAgent]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    total_water = 0.0
    total_paramedic_cap = 0
    for u in units:
        by_kind[u.kind] = by_kind.get(u.kind, 0) + 1
        total_water += u.water_gallons
        total_paramedic_cap += u.paramedic_capacity_per_hr
    return {
        "n_units": len(units),
        "by_kind": by_kind,
        "total_water_gallons": int(total_water),
        "paramedic_capacity_per_hour": total_paramedic_cap,
    }


def hospital_capacity(scenario: Scenario) -> dict[str, Any]:
    """Aggregate hospital surge picture. Used by the simulator to decide
    when patients overflow and turn into deaths-from-untreated-injury."""
    return {
        "total_beds": sum(h.beds for h in scenario.hospitals),
        "er_capacity_per_hr": sum(h.er_capacity_per_hour
                                  for h in scenario.hospitals),
        "by_district": {h.district_id: {"beds": h.beds,
                                        "er_per_hr": h.er_capacity_per_hour}
                        for h in scenario.hospitals},
    }
