"""Exercise First Battle's legal archive-recovery route in isolated engine test mode.

The source scenario body and AI side remain intact. Only its root becomes a
Wesnoth [test] and test events issue player moves. Victory requires two
prerequisites: (1) the Recon Squad recovers the archive records at (14,4) and
delivers them to command at (3,7); (2) the Imperial Remnant Captain (leader2)
is eliminated. A prestart fixture silently removes all other side-2 units
(they are not leaders, so no defeat event fires); this isolates the
moveto->deliver->die->victory->next_scenario wiring from combat RNG. Combat
balance is explicitly untested here.
This does not establish campaign entry, normal GUI play, transition execution,
or save/load.

Headless note: the source scenario shows unconditional [message] dialogs in
the start event and each victory/defeat path; a [message] shown mid-run waits
for dismissal that never comes in headless mode, so the fixture strips every
[message] block -- dialog text is not what's under test.

Route plan (Recon Squad, turns=20):
- Prestart boosts recon movement to 99 (fixture-only; the audit verified the
  physical route is feasible at MP 2). This isolates the event wiring from
  pathfinding mechanics.
- Phase 'acquire': single [do_command][move] from (3,7) to (14,4); the
  acquisition moveto sets sw_first_battle_archive_records_acquired=yes. The
  acquisition spawns an alarm reserve at (16,3); the per-turn sweep clears it
  (and any other spawned side-2 units) before moving.
- Phase 'return': single [do_command][move] from (14,4) to (3,7); the delivery
  moveto sets sw_first_battle_archive_records_delivered=yes.
- Phase 'kill_captain': [kill] leader2 with fire_event=yes to exercise the
  real die-event wiring; victory fires because delivered=yes.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from sequence_load_probe import ADDON_ID, _latest_log, _sha256


SCENARIO_ID = "01_First_Battle"
TEST_ID = "sw_first_battle_objective_route"
VICTORY_MARKER = "sw_first_battle_route_verified"
RECON_ID = "sw_nr_recon_squad"
CAPTAIN_ID = "leader2"
ACQUIRE_X, ACQUIRE_Y = 14, 4
DELIVER_X, DELIVER_Y = 3, 7


def _strip_messages(source: str) -> tuple[str, int]:
    """Remove every [message]...[/message] block; return (stripped, count)."""
    stripped, count = re.subn(r"\[message\].*?\[/message\]", "", source, flags=re.DOTALL)
    return stripped, count


def _fixture(source: str) -> str:
    if (source.count("[scenario]") != 1 or source.count("[/scenario]") != 1
            or source.count("id=" + SCENARIO_ID) != 1):
        raise ValueError("First Battle structure changed; refusing fixture transformation")
    if source.count("id=" + RECON_ID) < 1:
        raise ValueError("recon squad unit missing; refusing fixture transformation")
    if source.count("id=" + CAPTAIN_ID) < 1:
        raise ValueError("captain unit missing; refusing fixture transformation")
    if source.count("sw_first_battle_archive_records_acquired") < 1:
        raise ValueError("acquisition variable missing; refusing fixture transformation")
    if source.count("sw_first_battle_archive_records_delivered") < 1:
        raise ValueError("delivery variable missing; refusing fixture transformation")
    # Dialogs block headless execution; strip them fixture-side only.
    expected_messages = len(re.findall(r"\[message\].*?\[/message\]", source, flags=re.DOTALL))
    transformed, stripped = _strip_messages(source)
    if stripped != expected_messages or stripped == 0:
        raise ValueError("message strip count changed; refusing fixture transformation")
    transformed = transformed.replace("[scenario]", "[test]\n    is_unit_test=yes", 1)
    transformed = transformed.replace("id=" + SCENARIO_ID, "id=" + TEST_ID, 1)
    events = f"""
    # Fixture: silently clear all side-2 units except the captain. They are
    # not leaders, so no defeat event fires. The captain must stay alive until
    # the kill_captain phase so the real die-event wiring is exercised.
    # Boost the recon's movement to 99 (fixture-only) so the route completes
    # in single moves; the audit verified the physical route is feasible, and
    # this probe isolates the moveto->variable->victory event wiring.
    [event]
        name=prestart
        [kill]
            side=2
            [not]
                id={CAPTAIN_ID}
            [/not]
            fire_event=no
            animate=no
        [/kill]
        # Boost the recon's max movement to 99 (fixture-only) via an object
        # effect; the audit verified the physical route is feasible at MP 2.
        # This isolates the event wiring from pathfinding mechanics.
        [object]
            silent=yes
            [filter]
                id={RECON_ID}
            [/filter]
            [effect]
                apply_to=movement
                increase=97
            [/effect]
        [/object]
        [set_variable]
            name=sw_route_phase
            value=acquire
        [/set_variable]
    [/event]
    [event]
        name=side 1 turn
        first_time_only=no
        # Per-turn sweep: clear spawned side-2 units (alarm reserve, jammer,
        # reinforcements) before moving. The captain is spared until the
        # kill_captain phase.
        [kill]
            side=2
            [not]
                id={CAPTAIN_ID}
            [/not]
            fire_event=no
            animate=no
        [/kill]
        [if]
            [variable]
                name=sw_route_phase
                equals=acquire
            [/variable]
            [then]
                # Single move from the known start (3,7) to the archive.
                # Movement is boosted to 99 in prestart, so this reaches in
                # one turn and fires the acquisition moveto event.
                [do_command]
                    [move]
                        x=3,{ACQUIRE_X}
                        y=7,{ACQUIRE_Y}
                    [/move]
                [/do_command]
                [if]
                    [variable]
                        name=sw_first_battle_archive_records_acquired
                        equals=yes
                    [/variable]
                    [then]
                        [set_variable]
                            name=sw_route_phase
                            value=return
                        [/set_variable]
                    [/then]
                [/if]
            [/then]
            [else]
                [if]
                    [variable]
                        name=sw_route_phase
                        equals=return
                    [/variable]
                    [then]
                        # Single move from the archive back to command.
                        [do_command]
                            [move]
                                x={ACQUIRE_X},{DELIVER_X}
                                y={ACQUIRE_Y},{DELIVER_Y}
                            [/move]
                        [/do_command]
                        [if]
                            [variable]
                                name=sw_first_battle_archive_records_delivered
                                equals=yes
                            [/variable]
                            [then]
                                [set_variable]
                                    name=sw_route_phase
                                    value=kill_captain
                                [/set_variable]
                            [/then]
                        [/if]
                    [/then]
                    [else]
                        # kill_captain phase: exercise the real die-event
                        # wiring with fire_event=yes. Victory fires because
                        # the records were delivered.
                        [kill]
                            id={CAPTAIN_ID}
                            fire_event=yes
                            animate=no
                        [/kill]
                    [/else]
                [/if]
            [/else]
        [/if]
        [end_turn]
        [/end_turn]
    [/event]
    [event]
        name=victory
        {{ASSERT (
            [variable]
                name=sw_first_battle_archive_records_delivered
                equals=yes
            [/variable]
        )}}
        {{ASSERT (
            [variable]
                name=sw_first_battle_captain_defeated
                equals=yes
            [/variable]
        )}}
        [wml_message]
            logger=warning
            message={VICTORY_MARKER}
        [/wml_message]
        {{SUCCEED}}
    [/event]
    [event]
        name=defeat
        {{FAIL}}
    [/event]"""
    return transformed.replace("[/scenario]", events + "\n[/test]", 1)


def probe(root: Path, engine: Path) -> dict:
    root = root.resolve(strict=True)
    if not engine.is_absolute() or engine.is_symlink() or not engine.is_file():
        raise ValueError("installed engine is missing or symlinked")
    engine = engine.resolve(strict=True)
    addon_source = root / "addons" / ADDON_ID
    source_path = addon_source / "scenarios" / "01_first_battle.cfg"
    with tempfile.TemporaryDirectory(prefix="sw-first-battle-route-") as temporary:
        userdata = Path(temporary)
        addon = userdata / "data" / "add-ons" / ADDON_ID
        shutil.copytree(addon_source, addon)
        fixtures = addon / "probe-tests"
        fixtures.mkdir()
        fixture_path = fixtures / "route.cfg"
        fixture_path.write_text(_fixture(source_path.read_text(encoding="utf-8")), encoding="utf-8")
        (addon / "_main.cfg").write_text(
            "#ifdef TEST\n"
            "[binary_path]\n    path=data/add-ons/" + ADDON_ID + "\n[/binary_path]\n"
            "[+units]\n    {~add-ons/" + ADDON_ID + "/units}\n[/units]\n"
            "{~add-ons/" + ADDON_ID + "/utils/mission_events.cfg}\n"
            "{~add-ons/" + ADDON_ID + "/probe-tests}\n"
            "#endif\n", encoding="utf-8")
        try:
            completed = subprocess.run(
                [str(engine), "--log-to-file", "--userdata-dir", str(userdata), "-u", TEST_ID],
                cwd=engine.parent, capture_output=True, text=True, timeout=180, check=False)
            exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            exit_code = None
        log = _latest_log(userdata)
        passed = (exit_code == 8 and f"PASS TEST (VICTORY) (8): {TEST_ID}" in log
                  and VICTORY_MARKER in log
                  and "conditional test unexpectedly failed" not in log
                  and "Error via [do_command]" not in log
                  and "FAIL TEST" not in log)
        return {"schema_id": "wesnoth-starwars.production.first-battle-route-probe",
                "schema_version": 1, "exercise_type": "isolated_legal_player_objective_route",
                "scenario_id": SCENARIO_ID, "test_id": TEST_ID,
                "source_sha256": _sha256(source_path),
                "fixture_sha256": _sha256(fixture_path),
                "engine_sha256": _sha256(engine),
                "probe_sha256": _sha256(Path(__file__)),
                "exit_code": exit_code, "pass": passed,
                "transition": "unassessed", "save_reload": "unassessed",
                "normal_gui_play": "unassessed",
                "combat_balance": "unassessed",
                "diagnostic_tail": log[-3000:]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1]
                        / "agent/runtime/first-battle-route-probe.json")
    args = parser.parse_args()
    try:
        result = probe(args.repo_root, args.engine)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".first-battle-route-",
                                     suffix=".tmp", dir=args.output.parent, delete=False) as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, args.output)
    print(json.dumps({"pass": result["pass"], "exit_code": result["exit_code"],
                      "output": str(args.output)}))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
