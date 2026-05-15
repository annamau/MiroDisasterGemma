# SPDX-License-Identifier: Apache-2.0
"""
Phase 2a — Scenario-aware catalog filter in propose_interventions.

Falsifying gate: a Valencia propose call MUST NOT return any LA-prefixed
intervention_ids; conversely an LA call must NOT return any vlc_ ids;
and scenarios with no catalog (Pompeii/Joplin/Turkey/Atlantis) must
return an empty proposals list with an honest "no interventions modelled"
summary instead of forcing an LA-fallback (the demo-killer from the
red-team review where deaths_saved would be 0 across the board).
"""

from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app  # noqa: E402


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# Force the deterministic-fallback branch by stubbing chat_json to return
# (None, raw) — the propose endpoint must still produce filtered catalog.
@pytest.fixture(autouse=True)
def _stub_llm(monkeypatch):
    """Make every chat_json call return no parsed JSON, so propose falls
    through to the deterministic ranking path. We still want to verify
    that the deterministic ranking ALSO honours the scenario filter."""
    from app.services import llm_client as _llm

    class _StubResp:
        content = ""

    def _stub_chat_json(self, *args, **kwargs):
        return None, _StubResp()

    monkeypatch.setattr(_llm.LLMClient, "chat_json", _stub_chat_json)


_LA_PREFIXES = (
    "preposition_d03_",
    "evac_d03_",
    "retrofit_d0",
    "prebunk_misinfo",
    "fire_break_",
)


def test_la_propose_returns_only_la_interventions(client):
    """U1 — Filter keeps every proposal within the LA prefix set."""
    resp = client.post(
        "/api/scenario/la-puente-hills-m72-ref/interventions/propose",
        json={
            "baseline": {
                "deaths": 1000,
                "deaths_by_district": {"LA-D03": 800},
            },
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["proposals"], "LA must return ≥1 proposal"
    for p in data["proposals"]:
        iid = p["intervention_id"]
        assert iid.startswith(_LA_PREFIXES), (
            f"LA proposal {iid!r} not in allowed prefix set"
        )
        assert not iid.startswith("vlc_"), f"LA proposal leaked Valencia id {iid!r}"


def test_valencia_propose_returns_only_vlc(client):
    """U2 — Filter strips all non-vlc_ catalog items on Valencia."""
    resp = client.post(
        "/api/scenario/valencia-dana-2024/interventions/propose",
        json={
            "baseline": {
                "deaths": 200,
                "deaths_by_district": {},
            },
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["proposals"], "Valencia must return ≥1 proposal"
    for p in data["proposals"]:
        iid = p["intervention_id"]
        assert iid.startswith("vlc_"), f"Valencia proposal leaked non-vlc id {iid!r}"


def test_pompeii_propose_returns_empty(client):
    """U3 — Pompeii has no modelled interventions yet. Empty + honest."""
    resp = client.post(
        "/api/scenario/pompeii-79/interventions/propose",
        json={"baseline": {"deaths": 10000}},
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()["data"]
    assert data["proposals"] == [], (
        "Pompeii must return empty proposals, NOT LA fallbacks "
        "(deaths_saved would be 0 across the board on a non-LA city)"
    )
    assert "No interventions modelled" in data["summary"]
    assert data["model"] == "none"


def test_propose_for_each_scenario(client):
    """I1 — Sweep all 6 scenarios. Cities without a catalog return [];
    cities with one return proposals scoped to that city only."""
    scenarios = [
        "la-puente-hills-m72-ref",
        "valencia-dana-2024",
        "pompeii-79",
        "joplin-ef5-2011",
        "turkey-syria-m78-2023",
        "atlantis",
    ]
    with_catalog = {"la-puente-hills-m72-ref", "valencia-dana-2024"}

    for sid in scenarios:
        resp = client.post(
            f"/api/scenario/{sid}/interventions/propose",
            json={"baseline": {"deaths": 100}},
        )
        assert resp.status_code == 200, f"{sid} -> {resp.status_code}"
        data = resp.get_json()["data"]

        if sid in with_catalog:
            assert data["proposals"], f"{sid} should have ≥1 proposal"
        else:
            assert data["proposals"] == [], (
                f"{sid} should have empty proposals (no catalog yet) "
                f"— got {data['proposals']!r}"
            )
            # Honest summary, not "deterministic fallback"
            assert "No interventions modelled" in data["summary"]
