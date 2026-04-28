"""
Aurora /api/scenario endpoints — load + inspect city-resilience scenarios
+ Monte Carlo intervention runner.

Routes:
    POST   /api/scenario/load           bake + persist a reference scenario
    GET    /api/scenario/<scenario_id>/state    fetch current state from Neo4j
    DELETE /api/scenario/<scenario_id>          wipe a scenario subgraph
    GET    /api/scenario/list           list known scenarios
    POST   /api/scenario/<scenario_id>/baseline_loss   deterministic HAZUS run
    GET    /api/scenario/interventions               list available interventions
    POST   /api/scenario/<scenario_id>/run_mc        run Monte Carlo with N trials

All routes return {success, data | error}.
"""

from __future__ import annotations

import math
import traceback
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from ..aurora.decision_cache import get_default_cache
from ..aurora.hazus_fragility import (
    estimate_building_loss, shaking_intensity_to_sa,
)
from ..aurora.intervention_dsl import PRESET_INTERVENTIONS
from ..aurora.monte_carlo import run_monte_carlo, run_to_dict
from ..aurora.neo4j_writer import (
    delete_scenario, get_scenario_summary, write_scenario,
)
from ..aurora.scenario_loader import (
    build_la_puente_hills_m72, save_reference_scenario,
)
from ..utils.logger import get_logger

scenario_bp = Blueprint("scenario", __name__)
logger = get_logger("aurora.api.scenario")

# Registry of bake-able reference scenarios. Add more as P3 unlocks them.
REFERENCE_BUILDERS = {
    "la-puente-hills-m72-ref": build_la_puente_hills_m72,
}


def _driver():
    """Pull the live Neo4j driver out of the legacy storage extension."""
    storage = current_app.extensions.get("neo4j_storage")
    if storage is None:
        return None
    return getattr(storage, "_driver", None)


@scenario_bp.route("/list", methods=["GET"])
def list_scenarios():
    """Return the registry of bake-able scenarios + their current Neo4j state."""
    driver = _driver()
    out = []
    for sid, _builder in REFERENCE_BUILDERS.items():
        summary = None
        if driver is not None:
            try:
                summary = get_scenario_summary(driver, sid)
            except Exception:
                logger.exception("get_scenario_summary failed for %s", sid)
        out.append({
            "scenario_id": sid,
            "available_to_bake": True,
            "loaded_in_db": summary is not None,
            "summary": summary,
        })
    return jsonify({"success": True, "data": {"scenarios": out}})


@scenario_bp.route("/load", methods=["POST"])
def load_scenario():
    """Bake (or rebake) a reference scenario into Neo4j.

    Body: {"scenario_id": "la-puente-hills-m72-ref", "force_rebuild": false}
    """
    body = request.get_json(silent=True) or {}
    sid = body.get("scenario_id", "la-puente-hills-m72-ref")
    force = bool(body.get("force_rebuild", False))

    builder = REFERENCE_BUILDERS.get(sid)
    if builder is None:
        return jsonify({"success": False,
                        "error": f"Unknown scenario_id: {sid}"}), 404

    driver = _driver()
    try:
        if driver is not None and force:
            delete_scenario(driver, sid)

        # Always re-bake JSON snapshot so disk + DB stay in sync.
        json_path = save_reference_scenario()
        scenario = builder()

        counts = {}
        if driver is not None:
            counts = write_scenario(driver, scenario)

        return jsonify({
            "success": True,
            "data": {
                "scenario_id": sid,
                "label": scenario.label,
                "json_path": str(json_path),
                "neo4j_counts": counts,
                "neo4j_available": driver is not None,
            },
        })
    except Exception as exc:
        logger.exception("Scenario load failed")
        return jsonify({"success": False,
                        "error": str(exc),
                        "trace": traceback.format_exc()}), 500


@scenario_bp.route("/<scenario_id>/state", methods=["GET"])
def scenario_state(scenario_id: str):
    driver = _driver()
    if driver is None:
        return jsonify({"success": False,
                        "error": "Neo4j unavailable"}), 503
    summary = get_scenario_summary(driver, scenario_id)
    if summary is None:
        return jsonify({"success": False,
                        "error": "Scenario not loaded"}), 404
    return jsonify({"success": True, "data": summary})


@scenario_bp.route("/<scenario_id>", methods=["DELETE"])
def wipe_scenario(scenario_id: str):
    driver = _driver()
    if driver is None:
        return jsonify({"success": False,
                        "error": "Neo4j unavailable"}), 503
    deleted = delete_scenario(driver, scenario_id)
    return jsonify({"success": True, "data": {"deleted_nodes": deleted}})


@scenario_bp.route("/<scenario_id>/baseline_loss", methods=["POST"])
def baseline_loss(scenario_id: str):
    """Deterministic HAZUS aggregate loss for the loaded scenario.

    This is the "no intervention, no Monte Carlo" baseline number. The
    simulator's job is to compute deltas vs this. Returns aggregate +
    per-district breakdown.
    """
    builder = REFERENCE_BUILDERS.get(scenario_id)
    if builder is None:
        return jsonify({"success": False,
                        "error": f"Unknown scenario_id: {scenario_id}"}), 404
    scn = builder()

    # Re-derive MMI per building from the radial decay used at bake time
    epi = (scn.hazard.epicenter_lat, scn.hazard.epicenter_lon)

    def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
        lat1, lon1 = math.radians(a[0]), math.radians(a[1])
        lat2, lon2 = math.radians(b[0]), math.radians(b[1])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        h = (math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2)
             * math.sin(dlon/2)**2)
        return 6371.0 * 2 * math.asin(math.sqrt(h))

    def _mmi_at(lat: float, lon: float) -> float:
        d = _haversine_km(epi, (lat, lon))
        if d <= 3.0:
            return 9.0
        anchors = [(3.0, 9.0), (10.0, 8.0), (20.0, 7.0), (40.0, 6.0), (100.0, 5.5)]
        for (d1, m1), (d2, m2) in zip(anchors, anchors[1:]):
            if d <= d2:
                t = ((math.log10(d) - math.log10(d1))
                     / (math.log10(d2) - math.log10(d1)))
                return m1 + (m2 - m1) * t
        return 5.5

    by_district: dict[str, dict[str, float]] = {}
    total_deaths = total_inj = 0.0
    total_collapsed = 0.0
    total_occupants = 0
    for b in scn.buildings:
        mmi = _mmi_at(b.lat, b.lon)
        sa = shaking_intensity_to_sa(mmi)
        est = estimate_building_loss(b.hazus_class, sa)
        rep = b.representative_count
        occ = b.occupants_day * rep
        deaths = est.expected_death_rate * occ
        inj = est.expected_injury_rate * occ
        collapsed = est.collapse_probability * rep
        total_deaths += deaths
        total_inj += inj
        total_collapsed += collapsed
        total_occupants += occ
        d = by_district.setdefault(
            b.district_id,
            {"deaths": 0.0, "injuries": 0.0,
             "collapsed_buildings": 0.0, "indoor_occupants_day": 0},
        )
        d["deaths"] += deaths
        d["injuries"] += inj
        d["collapsed_buildings"] += collapsed
        d["indoor_occupants_day"] += occ

    return jsonify({
        "success": True,
        "data": {
            "scenario_id": scenario_id,
            "phase": "deterministic-baseline",
            "method": "HAZUS-MH 2.1 fragility curves @ Worden 2012 MMI->Sa",
            "totals": {
                "expected_deaths": int(round(total_deaths)),
                "expected_injuries": int(round(total_inj)),
                "expected_collapsed_buildings": int(round(total_collapsed)),
                "indoor_occupants_day": int(total_occupants),
            },
            "by_district": {k: {kk: round(vv, 1) for kk, vv in v.items()}
                            for k, v in by_district.items()},
        },
    })


@scenario_bp.route("/interventions", methods=["GET"])
def list_interventions():
    """Return the registry of preset interventions for the UI Designer."""
    out = []
    for iid, iv in PRESET_INTERVENTIONS.items():
        out.append({
            "intervention_id": iid,
            "kind": iv.kind,
            "label": iv.label,
            "params": {
                k: v for k, v in iv.to_dict().items()
                if k not in ("intervention_id", "kind", "label")
            },
        })
    return jsonify({"success": True, "data": {"interventions": out}})


@scenario_bp.route("/<scenario_id>/run_mc", methods=["POST"])
def run_mc(scenario_id: str):
    """Run a Monte Carlo experiment: N trials per intervention vs baseline.

    Body: {
        "intervention_ids": ["preposition_d03_4amb", "evac_d03_30min_early"],
        "n_trials": 50,
        "duration_hours": 72,
        "n_population_agents": 200,
        "use_llm": false       // true to call Ollama for Gemma decisions
    }

    Returns the full MC run dict — baseline outcome, treated outcomes, and
    paired delta CIs (lives_saved, dollars_saved, misinfo_ratio_change).
    """
    builder = REFERENCE_BUILDERS.get(scenario_id)
    if builder is None:
        return jsonify({"success": False,
                        "error": f"Unknown scenario_id: {scenario_id}"}), 404

    body = request.get_json(silent=True) or {}
    intervention_ids = body.get("intervention_ids") or []
    n_trials = int(body.get("n_trials", 50))
    duration_hours = body.get("duration_hours")
    n_population_agents = int(body.get("n_population_agents", 200))
    use_llm = bool(body.get("use_llm", False))
    fast_model = body.get("fast_model", "gemma4:e2b")

    # Validate interventions
    unknown = [iid for iid in intervention_ids
               if iid not in PRESET_INTERVENTIONS]
    if unknown:
        return jsonify({"success": False,
                        "error": f"Unknown intervention_ids: {unknown}"}), 400

    # Hardening: keep MC bounded so demo box can't accidentally launch a
    # 50,000-trial job. Adjust if/when the simulator gets faster.
    n_trials = max(1, min(n_trials, 200))
    n_population_agents = max(20, min(n_population_agents, 500))

    scn = builder()

    llm_call = None
    if use_llm:
        try:
            from ..services.llm_client import get_default_client
            llm_call = get_default_client().chat_json
        except Exception:
            logger.exception("LLM client unavailable; falling back to synth")

    cache = get_default_cache()
    try:
        run = run_monte_carlo(
            scn, intervention_ids,
            n_trials=n_trials,
            duration_hours=duration_hours,
            n_population_agents=n_population_agents,
            llm_call=llm_call,
            fast_model=fast_model,
            cache=cache,
        )
        return jsonify({
            "success": True,
            "data": run_to_dict(run),
        })
    except Exception as exc:
        logger.exception("MC run failed for %s", scenario_id)
        return jsonify({"success": False,
                        "error": str(exc),
                        "trace": traceback.format_exc()}), 500
