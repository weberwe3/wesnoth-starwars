"""Pre-code Wesnoth design review for bounded game-content tickets.

This gate checks coverage and provenance of a plan. It does not claim that a
documentation citation proves runtime behavior; installed-engine validation
and independent review retain that responsibility.
"""

from __future__ import annotations

from typing import Any


TARGET_ENGINE = "1.19/1.20"
ADDON_ROOT = "addons/Star_Wars_Thrawn_Trilogy"
AREA_SOURCES = {
    "campaign_flow": "https://wiki.wesnoth.org/CampaignWML",
    "scenario_objectives": "https://wiki.wesnoth.org/ScenarioWML",
    "maps_terrain": "https://wiki.wesnoth.org/TerrainCodesWML",
    "units_movement": "https://wiki.wesnoth.org/UnitsWML",
    "combat_abilities": "https://wiki.wesnoth.org/AbilitiesWML",
    "events_state": "https://wiki.wesnoth.org/EventWML",
    "ai_recruitment": "https://wiki.wesnoth.org/Wesnoth_AI_Framework",
    "lua_macros": "https://wiki.wesnoth.org/LuaAPI",
    "presentation_assets": "https://wiki.wesnoth.org/AnimationWML",
    "save_transition": "https://wiki.wesnoth.org/ScenarioWML",
    "multiplayer_sync": "https://wiki.wesnoth.org/ReferenceWML",
    "other_engine_rules": "https://wiki.wesnoth.org/ReferenceWML",
}

_AREA_ENTRY = {
    "type": "object",
    "additionalProperties": False,
    "required": ["disposition", "constraint", "design", "precode_check", "runtime_check"],
    "properties": {
        "disposition": {"type": "string", "enum": ["checked", "not_affected", "experiment"]},
        "constraint": {"type": "string", "minLength": 12, "maxLength": 500},
        "design": {"type": ["string", "null"], "maxLength": 500},
        "precode_check": {"type": ["string", "null"], "maxLength": 500},
        "runtime_check": {"type": ["string", "null"], "maxLength": 500},
    },
}

PLANNER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "target_engine", "areas"],
    "properties": {
        "schema_version": {"type": "integer", "enum": [1]},
        "target_engine": {"type": "string", "enum": [TARGET_ENGINE]},
        "areas": {
            "type": "object",
            "additionalProperties": False,
            "required": list(AREA_SOURCES),
            "properties": {area: _AREA_ENTRY for area in AREA_SOURCES},
        },
    },
}


def touches_game_content(paths: object) -> bool:
    if not isinstance(paths, list):
        return False
    return any(
        isinstance(path, str)
        and (path == ADDON_ROOT or path.startswith(ADDON_ROOT + "/")
             or path in {"addons", "addons/**"})
        for path in paths
    )


def required_areas(paths: object) -> set[str]:
    if not isinstance(paths, list):
        return set()
    required: set[str] = set()
    for path in paths:
        if not isinstance(path, str) or not path.startswith(ADDON_ROOT + "/"):
            continue
        suffix = path[len(ADDON_ROOT) + 1:]
        if suffix == "_main.cfg":
            required.add("campaign_flow")
        if suffix.startswith("scenarios/"):
            required.add("scenario_objectives")
        if suffix.startswith(("maps/", "terrain/")):
            required.add("maps_terrain")
        if suffix.startswith("units/"):
            required.add("units_movement")
        if suffix.startswith(("lua/", "utils/")):
            required.add("lua_macros")
        if suffix.startswith(("images/", "sounds/", "music/")):
            required.add("presentation_assets")
    return required


def validate_review(value: Any, *, required: bool, paths: object = None) -> dict | None:
    """Normalize a complete design matrix or raise before worker dispatch."""

    if value is None:
        if required:
            raise ValueError("game-content ticket lacks a pre-code engine compatibility review")
        return None
    if not isinstance(value, dict) or set(value) != {"schema_version", "target_engine", "areas"}:
        raise ValueError("engine compatibility review has invalid fields")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("unsupported engine compatibility review version")
    if value["target_engine"] != TARGET_ENGINE:
        raise ValueError("engine compatibility review targets the wrong engine generation")
    areas = value["areas"]
    if not isinstance(areas, dict) or set(areas) != set(AREA_SOURCES):
        raise ValueError("engine compatibility review must assess every design area")
    checked = 0
    required_for_paths = required_areas(paths)
    for area in AREA_SOURCES:
        entry = areas[area]
        fields = {"disposition", "constraint", "design", "precode_check", "runtime_check"}
        if not isinstance(entry, dict) or set(entry) != fields:
            raise ValueError(f"invalid {area} compatibility entry")
        disposition = entry["disposition"]
        if disposition not in {"checked", "not_affected", "experiment"}:
            raise ValueError(f"invalid {area} compatibility disposition")
        constraint = entry["constraint"]
        if not isinstance(constraint, str) or not 12 <= len(constraint.strip()) <= 500:
            raise ValueError(f"{area} needs a concrete documented rule or exclusion reason")
        if disposition == "not_affected":
            if area in required_for_paths:
                raise ValueError(f"{area} must be checked for the proposed paths")
            if any(entry[key] is not None for key in ("design", "precode_check", "runtime_check")):
                raise ValueError(f"{area} exclusion must not claim design or test evidence")
            continue
        for key in ("design", "precode_check", "runtime_check"):
            text = entry[key]
            if not isinstance(text, str) or not 12 <= len(text.strip()) <= 500:
                raise ValueError(f"{area} needs a bounded {key}")
        if disposition == "experiment":
            raise ValueError(
                f"{area} exceeds documented behavior; complete a separate engine spike "
                "and reviewed design decision before unattended implementation"
            )
        checked += 1
    if required and checked == 0:
        raise ValueError("game-content ticket must check at least one documented design area")
    return value
