"""Focused negative and determinism tests for production.inventory."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from inventory import InventoryError, _asset_reference, _safe_file, _validate_dependency_cycles, build_inventory, check_inventory, write_inventory


def _copy_repo() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1]
    temp = Path(tempfile.mkdtemp(prefix="production-inventory-"))
    shutil.copytree(root / "addons", temp / "addons")
    return root, temp


def test_dependency_cycle_is_rejected_but_transition_cycles_are_data() -> None:
    _validate_dependency_cycles([])
    try:
        _validate_dependency_cycles([{"from": "a", "to": "b"}, {"from": "b", "to": "a"}])
    except InventoryError:
        pass
    else:
        raise AssertionError("production dependency cycle was accepted")


def test_stock_art_is_external_but_missing_project_art_is_rejected() -> None:
    root = Path(__file__).resolve().parents[1]
    assert _asset_reference(root, "units/human-peasants/peasant.png") == (
        "external", "units/human-peasants/peasant.png"
    )
    try:
        _asset_reference(root, "units/sw-unit-nr-hero-commander/missing.png")
    except InventoryError:
        pass
    else:
        raise AssertionError("missing project-owned art was accepted as external")


def test_missing_transition_duplicate_id_and_unsafe_path_are_rejected() -> None:
    _, copy_root = _copy_repo()
    hte = copy_root / "addons/Star_Wars_Thrawn_Trilogy/scenarios/heir_to_the_empire"
    first = hte / "01_ysalamiri_harvest.cfg"
    original = first.read_text(encoding="utf-8")
    first.write_text(original.replace("next_scenario=sw_hte_02_ambush_at_bpfassh", "next_scenario=missing_scenario"), encoding="utf-8")
    try:
        build_inventory(copy_root)
    except InventoryError:
        pass
    else:
        raise AssertionError("missing transition was accepted")
    first.write_text(original, encoding="utf-8")
    second = hte / "02_ambush_at_bpfassh.cfg"
    second.write_text(second.read_text(encoding="utf-8").replace(
        "id=sw_hte_02_ambush_at_bpfassh", "id=sw_hte_01_ysalamiri_harvest", 1), encoding="utf-8")
    try:
        build_inventory(copy_root)
    except InventoryError:
        pass
    else:
        raise AssertionError("duplicate scenario ID was accepted")
    try:
        _safe_file(copy_root, "../outside.cfg")
    except InventoryError:
        pass
    else:
        raise AssertionError("unsafe path was accepted")


def test_inventory_is_deterministic_and_check_is_read_only() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "inventory.json"
        write_inventory(root, output)
        first = output.read_bytes()
        inventory = json.loads(first)
        map_path = "addons/Star_Wars_Thrawn_Trilogy/maps/hte_01_ysalamiri_harvest.map"
        assert map_path in {item["path"] for item in inventory["asset_references"]}
        assert map_path in {item["path"] for item in inventory["source_files"]}
        assert "addons/Star_Wars_Thrawn_Trilogy/utils/mission_events.cfg" in {
            item["path"] for item in inventory["source_files"]
        }
        assert map_path not in {item["path"] for item in inventory["external_asset_references"]}
        check_inventory(root, output)
        write_inventory(root, output)
        assert output.read_bytes() == first


def test_rejected_import_preserves_existing_inventory() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "inventory.json"
        output.write_bytes(b"existing inventory\n")
        before = output.read_bytes()
        try:
            write_inventory(root / "missing", output)
        except InventoryError:
            pass
        else:
            raise AssertionError("missing source root was accepted")
        if output.read_bytes() != before:
            raise AssertionError("rejected import changed inventory")


def test_check_rejects_non_object_json() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "inventory.json"
        output.write_text("[]\n", encoding="utf-8")
        try:
            check_inventory(root, output)
        except InventoryError:
            pass
        else:
            raise AssertionError("non-object inventory was accepted")


if __name__ == "__main__":
    test_dependency_cycle_is_rejected_but_transition_cycles_are_data()
    test_stock_art_is_external_but_missing_project_art_is_rejected()
    test_missing_transition_duplicate_id_and_unsafe_path_are_rejected()
    test_inventory_is_deterministic_and_check_is_read_only()
    test_rejected_import_preserves_existing_inventory()
    test_check_rejects_non_object_json()
