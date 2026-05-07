# SPDX-License-Identifier: Apache-2.0
"""
Aurora case schema — Case dataclass linking a city to a hazard.

A Case is the declarative specification stored in data/cases/<case_id>.yaml.
The manifest loader reads it and synthesizes a full Scenario from the
referenced city and hazard data files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Case:
    """Declarative specification linking a city to a hazard event."""
    case_id: str
    city_id: str
    hazard_id: str
    ui_label: str
    hero_blurb: str
    gemma_settings: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Case":
        return cls(
            case_id=d["case_id"],
            city_id=d["city_id"],
            hazard_id=d["hazard_id"],
            ui_label=d.get("ui_label", d["case_id"]),
            hero_blurb=d.get("hero_blurb", ""),
            gemma_settings=d.get("gemma_settings", {}),
        )
