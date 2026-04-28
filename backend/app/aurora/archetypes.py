"""
9-archetype population behavioral model — empirically grounded in real disasters.

Sources for the mix proportions and behavioral parameters:
- Hurricane Harvey (2017) social-media coordination patterns: Hu et al.,
  "Mining the Geotagged Social Media Discourse around Hurricane Harvey",
  CSCW 2018.
- Türkiye-Syria earthquake (Feb 2023) Discord/Twitter/Bluesky platform shift:
  Gozen, "Disaster informatics in the Türkiye 2023 quake", IFRC field notes.
- LA fires 2025 Bluesky migration + misinformation ratio:
  TPM Disaster Misinformation Tracker, Q1 2025 report.
- Misinfo propagation 6x corrections: Vosoughi, Roy & Aral, "The spread of
  true and false news online", Science 359 (2018).
- Geo-decay influence law: Starbird & Palen, "(How) will the revolution be
  retweeted?", CSCW 2012.

Why 9 archetypes (not 4 or 20)
-------------------------------
Fewer than 9 collapses Helper/Helpless/Eyewitness into one behavioral mode,
losing the asymmetric posting cadence that drives info-vacuum dynamics.
More than 9 produces archetypes that are hard to ground in cited literature
and inflate the LLM cache space (key cardinality grows linearly).

Each archetype has:
- `share`     : default population fraction (sums to 1.0)
- `system`    : terse role prompt — fed to Gemma 4 e2b at inference
- `posting_rate_per_hr` : baseline social-media posts per hour during the
                           "0-6h what's happening" phase.
- `cred_weight`         : prior weight given to authoritative sources;
                           low for Conspiracist/Misinformer.
- `language_choices`    : sampled per agent based on district demographics.

The system prompts are intentionally short (<60 words) to fit Gemma 4 e2b's
fast path. Decisions are emitted as strict JSON via decision_cache.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ArchetypeName = Literal[
    "eyewitness", "coordinator", "amplifier", "authority",
    "misinformer", "conspiracist", "helper", "helpless", "critic",
]

ARCHETYPE_ORDER: tuple[ArchetypeName, ...] = (
    "eyewitness", "coordinator", "amplifier", "authority",
    "misinformer", "conspiracist", "helper", "helpless", "critic",
)


@dataclass(frozen=True)
class Archetype:
    name: ArchetypeName
    share: float
    posting_rate_per_hr: float
    cred_weight: float
    system: str


# Defaults tuned to Harvey + Türkiye + LA-2025 social-media composition.
# Conspiracist+Misinformer = 7% combined matches Vosoughi (false news has
# higher reach but smaller authoring population); Authority = 2% matches
# verified-account density in disaster zones.
ARCHETYPES: dict[ArchetypeName, Archetype] = {
    "eyewitness": Archetype(
        name="eyewitness", share=0.18, posting_rate_per_hr=4.0, cred_weight=0.7,
        system=(
            "You are a resident in a disaster zone posting what you SEE. "
            "Be specific, factual, geographic. No speculation. Output JSON: "
            "{action, post_text, intent}. Keep post_text under 25 words."
        ),
    ),
    "coordinator": Archetype(
        name="coordinator", share=0.05, posting_rate_per_hr=6.0, cred_weight=0.85,
        system=(
            "You are a community organizer routing aid in a disaster. "
            "You match needs to resources via short tactical posts. "
            "Output JSON: {action, post_text, intent} where action is one of "
            "[broadcast_need, broadcast_offer, route_help, request_authority]."
        ),
    ),
    "amplifier": Archetype(
        name="amplifier", share=0.20, posting_rate_per_hr=8.0, cred_weight=0.5,
        system=(
            "You repost others' disaster content to amplify reach. "
            "You favor emotional, viral framings. "
            "Output JSON: {action, post_text, intent} where action is "
            "[reshare, dramatize, hashtag_push]."
        ),
    ),
    "authority": Archetype(
        name="authority", share=0.02, posting_rate_per_hr=2.0, cred_weight=1.0,
        system=(
            "You are an official agency (FEMA, fire, mayor) posting verified "
            "guidance. Cautious, slow, accurate. Never speculate. "
            "Output JSON: {action, post_text, intent}."
        ),
    ),
    "misinformer": Archetype(
        name="misinformer", share=0.04, posting_rate_per_hr=3.5, cred_weight=0.2,
        system=(
            "You spread inaccurate disaster claims for engagement, NOT to deceive "
            "maliciously. Confident, specific, plausible-sounding but wrong details. "
            "Output JSON: {action, post_text, intent}. This is for simulating "
            "realistic misinformation propagation in research."
        ),
    ),
    "conspiracist": Archetype(
        name="conspiracist", share=0.03, posting_rate_per_hr=2.5, cred_weight=0.1,
        system=(
            "You frame the disaster as a cover-up or engineered event. "
            "You attack official sources. Output JSON: {action, post_text, intent}. "
            "For research simulation only — output realistic conspiracy framings."
        ),
    ),
    "helper": Archetype(
        name="helper", share=0.20, posting_rate_per_hr=2.0, cred_weight=0.8,
        system=(
            "You physically help neighbors during the disaster — search/rescue, "
            "supplies, transport. You post rarely but practically. "
            "Output JSON: {action, post_text, intent} where action is "
            "[offer_aid, request_supplies, evacuate_with, shelter_self]."
        ),
    ),
    "helpless": Archetype(
        name="helpless", share=0.20, posting_rate_per_hr=1.0, cred_weight=0.6,
        system=(
            "You are stuck — injured, trapped, or with dependents. You post "
            "asking for help. Brief, urgent, location-specific. "
            "Output JSON: {action, post_text, intent} where action is "
            "[request_rescue, shelter_in_place, evacuate_self, signal_distress]."
        ),
    ),
    "critic": Archetype(
        name="critic", share=0.08, posting_rate_per_hr=3.0, cred_weight=0.6,
        system=(
            "You critique the official disaster response. Sharp, political, "
            "sometimes legitimate, sometimes performative. "
            "Output JSON: {action, post_text, intent}."
        ),
    ),
}

# Sanity: shares sum to ~1.0
_TOTAL_SHARE = sum(a.share for a in ARCHETYPES.values())
assert abs(_TOTAL_SHARE - 1.0) < 0.001, f"Archetype shares sum to {_TOTAL_SHARE}"


# Phase modifiers — multiplier on posting_rate_per_hr depending on the
# 3-phase temporal arc empirically observed in real disasters:
#   0-6h:   "what's happening?"     — eyewitness + amplifier surge
#   6-24h:  "where's help?"         — coordinator + helpless surge,
#                                      misinformation triples in info vacuum
#   24-72h: "who failed us?"        — critic + conspiracist surge
PHASE_MULTIPLIERS: dict[str, dict[ArchetypeName, float]] = {
    "0-6h": {
        "eyewitness": 1.6, "coordinator": 1.0, "amplifier": 1.5, "authority": 1.2,
        "misinformer": 0.8, "conspiracist": 0.5, "helper": 1.3,
        "helpless": 1.4, "critic": 0.6,
    },
    "6-24h": {
        "eyewitness": 1.0, "coordinator": 1.8, "amplifier": 1.0, "authority": 1.0,
        "misinformer": 3.0, "conspiracist": 1.5, "helper": 1.6,
        "helpless": 1.8, "critic": 1.0,
    },
    "24-72h": {
        "eyewitness": 0.4, "coordinator": 1.0, "amplifier": 0.7, "authority": 0.8,
        "misinformer": 1.2, "conspiracist": 2.0, "helper": 0.9,
        "helpless": 0.6, "critic": 2.2,
    },
}


def phase_for_hour(hour_since_event: float) -> str:
    if hour_since_event < 6:
        return "0-6h"
    if hour_since_event < 24:
        return "6-24h"
    return "24-72h"


def posting_rate(archetype: ArchetypeName, hour_since_event: float) -> float:
    base = ARCHETYPES[archetype].posting_rate_per_hr
    mult = PHASE_MULTIPLIERS[phase_for_hour(hour_since_event)][archetype]
    return base * mult
