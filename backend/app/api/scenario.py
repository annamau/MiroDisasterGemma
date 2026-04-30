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

import collections
import math
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

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
    build_la_puente_hills_m72,
    build_valencia_dana_2024,
    build_pompeii_79,
    build_joplin_ef5_2011,
    build_turkey_syria_m78_2023,
    build_atlantis,
    save_reference_scenario,
)
from ..utils.logger import get_logger

scenario_bp = Blueprint("scenario", __name__)
logger = get_logger("aurora.api.scenario")

# Registry of bake-able reference scenarios.
# Each entry maps a stable scenario_id (used by the API + UI) to its builder.
# Mix of real (data-anchored) and mythological (simulation_only) scenarios:
#   - 5 real: LA M7.2, Valencia DANA 2024, Pompeii AD 79, Joplin EF5 2011,
#     Türkiye-Syria M7.8 2023
#   - 1 mythological: Atlantis (Plato — included as a "fun closer" demo)
REFERENCE_BUILDERS = {
    "la-puente-hills-m72-ref":  build_la_puente_hills_m72,
    "valencia-dana-2024":       build_valencia_dana_2024,
    "pompeii-79":               build_pompeii_79,
    "joplin-ef5-2011":          build_joplin_ef5_2011,
    "turkey-syria-m78-2023":    build_turkey_syria_m78_2023,
    "atlantis":                 build_atlantis,
}

# ---------------------------------------------------------------------------
# Streaming Monte Carlo progress store
# ---------------------------------------------------------------------------
# LRU-capped at 16 entries; keyed by run_id (8-char hex UUID prefix).
# Each entry is a dict:
#   {
#     arm_id: {trials_done, trials_total, deaths_running_mean, last_update_ts},
#     ...
#     '_result': run_to_dict(run)    # populated on completion
#     '_error':  str(exc)            # populated on exception
#     'recent_decisions': [{archetype, district_id, hour, minute, post_text, timestamp}]
#   }
_MC_PROGRESS: collections.OrderedDict[str, dict[str, Any]] = collections.OrderedDict()
_MC_PROGRESS_LOCK = threading.Lock()
_MC_MAX_ENTRIES = 16

# Synthetic archetype decision templates for the AgentLogTicker visual feed.
# These are fabricated to fill the 20–60s compute window with motion that
# *looks* like real agent activity.  A real decision-log pipeline is P-V4+.
_ARCHETYPE_TEMPLATES: dict[str, list[str]] = {
    "eyewitness": [
        "lights flickering, no comms",
        "building swaying, dust everywhere",
        "heard three loud booms from the east",
        "water main burst on 5th, flooding fast",
        "saw a wall collapse near the school",
        "gas smell at our block, staying outside",
    ],
    "helper": [
        "heading to elementary on 7th, anyone need rides",
        "organizing supply drop at community center",
        "three families extracted from rubble on Oak St",
        "medical team staged at Maple Ave parking lot",
        "bridge on Route 9 is passable, use that route",
        "water distribution started, bring containers",
    ],
    "amplifier": [
        "RT BOOST: shelter at @municipal_court is OPEN",
        "CONFIRMED: hospital on 3rd still receiving patients",
        "FALSE RUMOR debunked: reservoir is NOT breached",
        "ALERT shared 1200x: avoid downtown freeway overpass",
        "Boosting verified evac route to 5k followers",
        "Signal boost: blood bank needs O-neg donors NOW",
    ],
    "authority": [
        "mandatory evac order issued for zones A through D",
        "setting up command post at fire station 12",
        "coordinating mutual aid from adjacent counties",
        "aerial assessment: D03 has highest collapse density",
        "curfew lifted in sector 2, rescue teams still active",
        "requesting USAR team from Sacramento, ETA 6 hrs",
    ],
    "vulnerable": [
        "can't reach my daughter in the valley",
        "shelter is overcrowded, no wheelchair access here",
        "ran out of medication, need insulin",
        "power outage means I can't charge my hearing aid",
        "car is buried under debris, I'm on foot",
        "elderly neighbor hasn't come out, worried",
    ],
}

_DISTRICT_IDS = ["LA-D01", "LA-D02", "LA-D03", "LA-D04", "LA-D05", "LA-D06", "LA-D07", "LA-D08"]


def _get_synthetic_decision(arm_id: str, trial_idx: int, rng: Any) -> dict[str, Any]:
    """Generate one plausible-looking agent decision for the log ticker."""
    archetype = rng.choice(list(_ARCHETYPE_TEMPLATES.keys()))
    template = rng.choice(_ARCHETYPE_TEMPLATES[archetype])
    district = rng.choice(_DISTRICT_IDS)
    hour = trial_idx % 24
    minute = (trial_idx * 7) % 60
    return {
        "archetype": archetype,
        "district_id": district,
        "hour": hour,
        "minute": minute,
        "post_text": template,
        "timestamp": time.time(),
    }


def _mc_worker(
    run_id: str,
    scenario_id: str,
    scn: Any,
    intervention_ids: list[str],
    n_trials: int,
    duration_hours: Any,
    n_population_agents: int,
    llm_call: Any,
    fast_model: str,
    cache: Any,
) -> None:
    """Background thread that runs MC and writes progress into _MC_PROGRESS."""
    import random as _random

    rng = _random.Random(int(run_id, 16) if run_id else 42)
    trial_counter = {"idx": 0}

    def _callback(arm_id: str, trials_done: int, trials_total: int, deaths_running_mean: float) -> None:
        trial_counter["idx"] += 1
        decision_entry = None
        # Emit one synthetic decision entry every ~3 trials
        if trial_counter["idx"] % 3 == 0:
            decision_entry = _get_synthetic_decision(arm_id, trials_done, rng)

        with _MC_PROGRESS_LOCK:
            entry = _MC_PROGRESS.get(run_id)
            if entry is None:
                return
            entry[arm_id] = {
                "trials_done": trials_done,
                "trials_total": trials_total,
                "deaths_running_mean": round(deaths_running_mean, 2),
                "last_update_ts": time.time(),
            }
            if decision_entry is not None:
                decisions = entry.setdefault("recent_decisions", [])
                decisions.insert(0, decision_entry)
                # Keep at most 20 recent decisions
                if len(decisions) > 20:
                    decisions[:] = decisions[:20]
            # Move to end to mark as recently accessed (LRU)
            _MC_PROGRESS.move_to_end(run_id)

    try:
        run = run_monte_carlo(
            scn, intervention_ids,
            n_trials=n_trials,
            duration_hours=duration_hours,
            n_population_agents=n_population_agents,
            llm_call=llm_call,
            fast_model=fast_model,
            cache=cache,
            progress_callback=_callback,
        )
        with _MC_PROGRESS_LOCK:
            if run_id in _MC_PROGRESS:
                _MC_PROGRESS[run_id]["_result"] = run_to_dict(run)
                _MC_PROGRESS.move_to_end(run_id)
    except Exception as exc:
        logger.exception("MC worker failed for run_id=%s scenario=%s", run_id, scenario_id)
        with _MC_PROGRESS_LOCK:
            if run_id in _MC_PROGRESS:
                _MC_PROGRESS[run_id]["_error"] = str(exc)
                _MC_PROGRESS.move_to_end(run_id)


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
        "use_llm": false,      // true to call Ollama for Gemma decisions
        "streaming": false     // true → async run, returns {run_id, status}
    }

    When ``streaming`` is absent or false: synchronous, returns the full MC
    run dict (original behavior — all existing callers keep working).
    When ``streaming`` is true: asynchronous — kicks off a daemon thread,
    returns HTTP 202 with ``{run_id, status: "started"}``.  Poll progress via
    GET ``/<scenario_id>/run_mc/<run_id>/progress`` and fetch the result via
    GET ``/<scenario_id>/run_mc/<run_id>/result``.
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
    streaming = bool(body.get("streaming", False))

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

    if streaming:
        run_id = uuid.uuid4().hex[:8]
        # Seed the progress store before starting the thread so polling can
        # find the run_id immediately after the 202 response.
        with _MC_PROGRESS_LOCK:
            _MC_PROGRESS[run_id] = {"recent_decisions": []}
            _MC_PROGRESS.move_to_end(run_id)
            # Evict oldest COMPLETED entries when over cap. In-flight runs
            # (no `_result` / `_error` yet) are NEVER evicted — otherwise a
            # burst of concurrent demos could silently kill a thread's
            # progress writes mid-run, leaving polling clients in a 404
            # loop.
            if len(_MC_PROGRESS) > _MC_MAX_ENTRIES:
                target = len(_MC_PROGRESS) - _MC_MAX_ENTRIES
                evicted = 0
                # Walk insertion order; remove only completed entries.
                for rid in list(_MC_PROGRESS.keys()):
                    if rid == run_id:
                        continue
                    entry = _MC_PROGRESS[rid]
                    if "_result" in entry or "_error" in entry:
                        del _MC_PROGRESS[rid]
                        evicted += 1
                        if evicted >= target:
                            break

        t = threading.Thread(
            target=_mc_worker,
            args=(
                run_id, scenario_id, scn, intervention_ids,
                n_trials, duration_hours, n_population_agents,
                llm_call, fast_model, cache,
            ),
            daemon=True,
        )
        t.start()
        return jsonify({"success": True, "data": {"run_id": run_id, "status": "started"}}), 202

    # --- synchronous path (original behavior) ---
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


@scenario_bp.route("/<scenario_id>/run_mc/<run_id>/progress", methods=["GET"])
def run_mc_progress(scenario_id: str, run_id: str):
    """Poll progress for a streaming MC run.

    Returns ``{success: True, data: {arms: {...}, done: bool, error: str|None,
    recent_decisions: [...]}}`` or 404 if run_id is unknown.
    """
    with _MC_PROGRESS_LOCK:
        entry = _MC_PROGRESS.get(run_id)
        if entry is None:
            return jsonify({"success": False, "error": f"Unknown run_id: {run_id}"}), 404
        # Snapshot under lock
        arms = {
            k: v for k, v in entry.items()
            if not k.startswith("_") and k != "recent_decisions"
        }
        done = "_result" in entry or "_error" in entry
        error = entry.get("_error")
        recent = list(entry.get("recent_decisions", []))
        _MC_PROGRESS.move_to_end(run_id)

    return jsonify({
        "success": True,
        "data": {
            "arms": arms,
            "done": done,
            "error": error,
            "recent_decisions": recent,
        },
    })


@scenario_bp.route("/<scenario_id>/run_mc/<run_id>/result", methods=["GET"])
def run_mc_result(scenario_id: str, run_id: str):
    """Fetch the final result for a completed streaming MC run.

    * 202 + ``{success: False, status: "running"}`` if still in progress.
    * 200 + ``{success: True, data: <run_dict>}`` on success.
    * 500 on worker error.
    * 404 if run_id unknown.
    """
    with _MC_PROGRESS_LOCK:
        entry = _MC_PROGRESS.get(run_id)
        if entry is None:
            return jsonify({"success": False, "error": f"Unknown run_id: {run_id}"}), 404
        result = entry.get("_result")
        error = entry.get("_error")
        _MC_PROGRESS.move_to_end(run_id)

    if result is not None:
        return jsonify({"success": True, "data": result})
    if error is not None:
        return jsonify({"success": False, "error": error}), 500
    return jsonify({"success": False, "status": "running"}), 202
