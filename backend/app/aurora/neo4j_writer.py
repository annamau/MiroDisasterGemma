"""
Aurora -> Neo4j writer.

Persists a Scenario into the same Neo4j instance the legacy MiroFish graph
lives in, namespaced by `scenario_id`. Mirrors the (:Entity {uuid})
unique-constraint pattern with composite (scenario_id, *_id) keys.

Why we write the whole scenario as a graph (vs keeping it in JSON):
- The simulator + report agent both already query Neo4j; one storage layer.
- Spatial queries (`MATCH (b:Building)-[:IN_CELL]->(c) WHERE c.h3 = ...`)
  become trivial Cypher.
- Interventions can mutate node properties cheaply per Monte Carlo trial.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any

from .scenario import Scenario

logger = logging.getLogger("aurora.neo4j_writer")


def _safe_dict(node: Any) -> dict[str, Any]:
    """asdict but flatten nested dicts (Neo4j props are scalar-only)."""
    d = asdict(node)
    return {k: v for k, v in d.items() if not isinstance(v, (dict, list))}


def write_scenario(driver, scenario: Scenario) -> dict[str, int]:
    """Write all scenario nodes + relationships to Neo4j. Idempotent on
    composite keys (scenario_id + *_id). Returns counts."""
    counts = {
        "scenarios": 0, "districts": 0, "buildings": 0,
        "hospitals": 0, "fire_stations": 0, "shelters": 0,
        "intensity_points": 0,
    }
    sid = scenario.scenario_id
    with driver.session() as s:
        # Scenario root
        s.run(
            """
            MERGE (sc:Scenario {scenario_id: $sid})
            SET sc.label=$label, sc.city=$city,
                sc.hazard_kind=$kind, sc.hazard_name=$hname,
                sc.magnitude=$mag,
                sc.epicenter_lat=$elat, sc.epicenter_lon=$elon,
                sc.origin_time_iso=$ot, sc.duration_hours=$dur,
                sc.population=$pop, sc.building_agent_count=$bac
            """,
            sid=sid, label=scenario.label, city=scenario.city,
            kind=scenario.hazard.kind, hname=scenario.hazard.name,
            mag=scenario.hazard.magnitude,
            elat=scenario.hazard.epicenter_lat,
            elon=scenario.hazard.epicenter_lon,
            ot=scenario.hazard.origin_time_iso,
            dur=scenario.hazard.duration_hours,
            pop=scenario.total_population,
            bac=scenario.total_buildings,
        )
        counts["scenarios"] = 1

        # Districts
        for d in scenario.districts:
            s.run(
                """
                MERGE (dt:District {scenario_id: $sid, district_id: $did})
                SET dt += $props
                MERGE (sc:Scenario {scenario_id: $sid})
                MERGE (dt)-[:IN_SCENARIO]->(sc)
                """,
                sid=sid, did=d.district_id, props=_safe_dict(d),
            )
        counts["districts"] = len(scenario.districts)

        # Buildings — UNWIND for batch insert
        bldg_props = [_safe_dict(b) for b in scenario.buildings]
        s.run(
            """
            UNWIND $rows AS row
            MERGE (b:Building {scenario_id: $sid, building_id: row.building_id})
            SET b += row
            WITH b, row
            MATCH (dt:District {scenario_id: $sid, district_id: row.district_id})
            MERGE (b)-[:IN_DISTRICT]->(dt)
            """,
            sid=sid, rows=bldg_props,
        )
        counts["buildings"] = len(scenario.buildings)

        # Responder + shelter nodes (smaller, can MERGE one-by-one)
        for h in scenario.hospitals:
            s.run(
                """
                MERGE (h:Hospital {scenario_id: $sid, hospital_id: $hid})
                SET h += $props
                WITH h
                MATCH (dt:District {scenario_id: $sid, district_id: $did})
                MERGE (h)-[:IN_DISTRICT]->(dt)
                """,
                sid=sid, hid=h.hospital_id, did=h.district_id, props=_safe_dict(h),
            )
        counts["hospitals"] = len(scenario.hospitals)

        for f in scenario.fire_stations:
            s.run(
                """
                MERGE (f:FireStation {scenario_id: $sid, station_id: $fid})
                SET f += $props
                WITH f
                MATCH (dt:District {scenario_id: $sid, district_id: $did})
                MERGE (f)-[:IN_DISTRICT]->(dt)
                """,
                sid=sid, fid=f.station_id, did=f.district_id, props=_safe_dict(f),
            )
        counts["fire_stations"] = len(scenario.fire_stations)

        for sh in scenario.shelters:
            s.run(
                """
                MERGE (sh:Shelter {scenario_id: $sid, shelter_id: $shid})
                SET sh += $props
                WITH sh
                MATCH (dt:District {scenario_id: $sid, district_id: $did})
                MERGE (sh)-[:IN_DISTRICT]->(dt)
                """,
                sid=sid, shid=sh.shelter_id, did=sh.district_id, props=_safe_dict(sh),
            )
        counts["shelters"] = len(scenario.shelters)

        # Intensity field
        ip_rows = [
            {"lat": p.lat, "lon": p.lon, "mmi": p.mmi, "h3_cell": p.h3_cell, "idx": i}
            for i, p in enumerate(scenario.hazard.intensity_field)
        ]
        if ip_rows:
            s.run(
                """
                UNWIND $rows AS row
                MERGE (ip:IntensityPoint {scenario_id: $sid, idx: row.idx})
                SET ip.lat=row.lat, ip.lon=row.lon, ip.mmi=row.mmi, ip.h3_cell=row.h3_cell
                WITH ip
                MATCH (sc:Scenario {scenario_id: $sid})
                MERGE (ip)-[:IN_SCENARIO]->(sc)
                """,
                sid=sid, rows=ip_rows,
            )
        counts["intensity_points"] = len(ip_rows)

    logger.info("Aurora scenario %s written to Neo4j: %s", sid, counts)
    return counts


def delete_scenario(driver, scenario_id: str) -> int:
    """Wipe a scenario subgraph. Returns deleted node count."""
    with driver.session() as s:
        result = s.run(
            """
            MATCH (n) WHERE n.scenario_id = $sid
            DETACH DELETE n
            RETURN count(n) AS deleted
            """,
            sid=scenario_id,
        )
        rec = result.single()
        return rec["deleted"] if rec else 0


def get_scenario_summary(driver, scenario_id: str) -> dict[str, Any] | None:
    """Read-back scenario stats for the API."""
    with driver.session() as s:
        rec = s.run(
            """
            MATCH (sc:Scenario {scenario_id: $sid})
            OPTIONAL MATCH (b:Building {scenario_id: $sid})
            OPTIONAL MATCH (dt:District {scenario_id: $sid})
            OPTIONAL MATCH (h:Hospital {scenario_id: $sid})
            OPTIONAL MATCH (f:FireStation {scenario_id: $sid})
            OPTIONAL MATCH (sh:Shelter {scenario_id: $sid})
            RETURN sc{.*} AS scenario,
                   count(DISTINCT b) AS bldg, count(DISTINCT dt) AS dst,
                   count(DISTINCT h) AS hsp, count(DISTINCT f) AS fst,
                   count(DISTINCT sh) AS shl
            """,
            sid=scenario_id,
        ).single()
        if not rec or not rec["scenario"]:
            return None
        return {
            "scenario": dict(rec["scenario"]),
            "counts": {
                "buildings": rec["bldg"], "districts": rec["dst"],
                "hospitals": rec["hsp"], "fire_stations": rec["fst"],
                "shelters": rec["shl"],
            },
        }
