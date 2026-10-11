#!/usr/bin/env python3
"""Coordinator-run, ordinary-command native route proof for HttE mission one.

The add-on is copied byte-for-byte; only preferences and an application plugin
are staged outside it. This bounded automated policy is not a human playtest,
a balance verdict, or an existing-save compatibility test. --selftest exercises
the evidence classifier without launching a game.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ADDON_ID = "Star_Wars_Thrawn_Trilogy"
ADDON = ROOT / "addons" / ADDON_ID
DEFAULT_ENGINE = Path.home() / "opt/bin/wesnoth-linux"
FIRST = "sw_hte_01_ysalamiri_harvest"
NEXT = "sw_hte_02_ambush_at_bpfassh"
PREFIX = "SW_ROUTE: "
ERRORS = re.compile(
    r"\berror\s+[^:\r\n]+:|stack traceback|\bfatal\b|"
    r"assertion[^\r\n]*(?:failed|failure)|segmentation fault|core dumped|"
    r"terminate called|uncaught exception", re.IGNORECASE)
LIMITS = [
    "One automated NORMAL-difficulty route policy; CLI seed does not fix campaign/combat RNG.",
    "Ordinary recruitment, combat and enemy turns are allowed; no forced hits or enemy changes.",
    "Dialogs are skipped; on-screen presentation and human legal wins/balance are not proved.",
    "No native reload of campaign saves or engine interactive-quit claim.",
]


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"source/staged symlink is not permitted: {path}")
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def parse_records(text: str) -> tuple[list[dict], list[str]]:
    records, malformed = [], []
    for line in text.splitlines():
        if PREFIX not in line:
            continue
        raw = line.split(PREFIX, 1)[1].strip()
        try:
            record = json.loads(raw)
            if not isinstance(record, dict) or not isinstance(record.get("event"), str):
                raise ValueError("record lacks event string")
            records.append(record)
        except (ValueError, TypeError) as error:
            malformed.append(f"malformed route evidence: {error}: {raw[:400]}")
    return records, malformed


def assess(records: list[dict], exit_code: int | None, timed_out: bool,
           stop_requested: bool, errors: list[str], malformed: list[str],
           warnings: list[str] | None = None) -> dict:
    failures = list(errors) + list(malformed)
    endpoints = {1:(12,4), 2:(21,5), 3:(17,13), 4:(23,15)}
    done = [r for r in records if r["event"] == "done"]
    owned_stop = bool(stop_requested and done and exit_code in (-signal.SIGTERM, -signal.SIGKILL))
    if timed_out:
        failures.append("native route phase timed out")
    if exit_code != 0 and not owned_stop:
        failures.append(f"unexpected real process exit {exit_code}")
    if len(done) != 1 or done[0].get("success") is not True:
        failures.append("missing or unsuccessful unique completion marker")
    for r in records:
        if r["event"] == "failure" or r["event"] == "check" and r.get("ok") is not True:
            failures.append(f"reported native failure: {r}")
    if done and records[-1] is not done[-1]:
        failures.append("evidence appears after completion marker")
    entered = [r for r in records if r["event"] == "entered"]
    if len(entered) != 1 or entered[0].get("scenario") != FIRST or entered[0].get("difficulty") != "NORMAL" \
            or entered[0].get("cap") != 16 or entered[0].get("turn") != 1:
        failures.append("missing untouched NORMAL opening/16-turn budget evidence")
    negatives = [r for r in records if r["event"] == "illegal_result"]
    requests = [r for r in records if r["event"] == "illegal_request"]
    known_warning = re.compile(
        r"^(?:(?:\d{8} \d{2}:\d{2}:\d{2}(?:\.\d+)? )?"
        r"(?:warning replay: )?)?"
        r"Warning: Move with identical source and destination\. Skipping\.\.\.$")
    if len(requests) != 1 or len(negatives) != 1:
        failures.append("missing unique identical-coordinate illegal move evidence")
    else:
        negative = negatives[0]
        if negative.get("unchanged") is not True or negative.get("before") != negative.get("after"):
            failures.append("illegal-move before/after snapshots changed")
        if requests[0].get("coordinates") != [requests[0].get("actor", {}).get("x"), requests[0].get("actor", {}).get("y")] * 2:
            failures.append("illegal request did not repeat identical source/destination coordinates")
    if not any(known_warning.fullmatch(line.strip()) for line in (warnings or [])):
        failures.append("missing exact native identical-coordinate warning")
    route_maps = [r for r in records if r["event"] == "route_map"]
    if len(route_maps) != 1:
        failures.append("missing unique dynamic route map evidence")
        route_map = {}
    else:
        route_map = route_maps[0]
    width, height = route_map.get("width"), route_map.get("height")
    shuttle = route_map.get("shuttle_goals")
    component = route_map.get("recruit_component")
    keep = route_map.get("keep")
    dimensions_ok = (type(width) is int and width > 0 and type(height) is int and height > 0)
    in_bounds = lambda p: (isinstance(p, list) and len(p) == 2
        and all(type(v) is int for v in p) and dimensions_ok
        and 1 <= p[0] <= width and 1 <= p[1] <= height)
    if not dimensions_ok:
        failures.append("invalid native playable map dimensions")
    if not isinstance(shuttle, list) or not shuttle or any(not isinstance(g, dict) or not in_bounds(g.get("xy")) or g.get("code") not in ("Qkp", "Qcp") for g in (shuttle if isinstance(shuttle, list) else [])):
        failures.append("invalid or empty dynamic shuttle goals")
        shuttle = shuttle if isinstance(shuttle, list) else []
    if len({tuple(g.get("xy", [])) for g in shuttle if isinstance(g, dict)}) != len(shuttle):
        failures.append("duplicate shuttle goals")
    if isinstance(shuttle, list) and any(not isinstance(g, dict) for g in shuttle):
        failures.append("malformed dynamic shuttle goal")
    shuttle = [g for g in shuttle if isinstance(g, dict) and in_bounds(g.get("xy")) and g.get("code") in ("Qkp", "Qcp")]
    if not in_bounds(keep) or not any(g.get("xy") == keep and g.get("code") == "Qkp" for g in shuttle):
        failures.append("actual Qkp keep is absent from shuttle goals")
    if not isinstance(component, list) or not component or any(not isinstance(g, dict) or not in_bounds(g.get("xy")) or g.get("castle") is not True or not isinstance(g.get("code"), str) or not g.get("code") for g in (component if isinstance(component, list) else [])):
        failures.append("invalid or empty connected native recruit component")
        component = component if isinstance(component, list) else []
    if len({tuple(g.get("xy", [])) for g in component if isinstance(g, dict)}) != len(component) or not any(isinstance(g, dict) and g.get("xy") == keep and g.get("code") == "Qkp" for g in component):
        failures.append("recruit component is duplicate or omits the keep")
    if isinstance(component, list) and any(not isinstance(g, dict) for g in component):
        failures.append("malformed native recruit goal")
    component = [g for g in component if isinstance(g, dict) and in_bounds(g.get("xy")) and g.get("castle") is True and isinstance(g.get("code"), str) and g.get("code")]
    shuttle_codes = {tuple(g["xy"]): g["code"] for g in shuttle}
    if any(tuple(g["xy"]) in shuttle_codes and shuttle_codes[tuple(g["xy"])] != g["code"] for g in component):
        failures.append("conflicting shuttle/component native terrain codes")
    shuttle_points = {tuple(g["xy"]) for g in shuttle if isinstance(g, dict) and in_bounds(g.get("xy"))}
    component_points = {tuple(g["xy"]) for g in component if isinstance(g, dict) and in_bounds(g.get("xy"))}
    if shuttle_points - component_points:
        failures.append("shuttle goal lies outside the connected recruit component")

    def adjacent(a, b):
        ax, bx = a[0] - 1, b[0] - 1
        horizontal = abs(ax - bx)
        penalty = int((ax & 1 == 0 and bx & 1 == 1 and a[1] < b[1])
                      or (bx & 1 == 0 and ax & 1 == 1 and b[1] < a[1]))
        return max(horizontal, abs(a[1] - b[1]) + penalty + horizontal // 2) == 1

    reached = {tuple(keep)} if in_bounds(keep) else set()
    changed = True
    while changed:
        changed = False
        for point in component_points - reached:
            if any(adjacent(point, prior) for prior in reached):
                reached.add(point); changed = True
    if reached != component_points:
        failures.append("recruit goals are not one connected native component")
    terrains = [r for r in records if r["event"] == "terrain"]
    required = {(12,4): "Gll^Fsm", (21,5): "Gll^Fsm", (17,13): "Gll^Fsm", (23,15): "Gll^Fsm"}
    required.update({tuple(g["xy"]): g["code"] for g in shuttle if isinstance(g, dict) and in_bounds(g.get("xy"))})
    required.update({tuple(g["xy"]): g["code"] for g in component if isinstance(g, dict) and in_bounds(g.get("xy"))})
    for point, code in required.items():
        matching = [r for r in terrains if (r.get("x"),r.get("y")) == point]
        if not matching or any(r.get("code") != code or not isinstance(r.get("movement_alias"), list)
                              or not r["movement_alias"] or not isinstance(r.get("movement_cost"), int)
                              or r["movement_cost"] <= 0 or not isinstance(r.get("max_moves"), int) or r["max_moves"] <= 0
                              for r in matching):
            failures.append(f"missing/invalid native terrain alias and cost evidence at {point}")
    carriers = [r for r in records if r["event"] == "carrier"]
    carrier_ids = {r.get("actor", {}).get("id") for r in carriers}
    if len(carriers) != 4 or len(carrier_ids) != 4 or None in carrier_ids or {c.get("tree") for c in carriers} != {1,2,3,4}:
        failures.append("missing four distinct ordinary carrier assignments")
    for carrier in carriers:
        actor_id = carrier.get("actor", {}).get("id")
        tree_index = carrier.get("tree")
        targets = [endpoints[tree_index]] if type(tree_index) is int and tree_index in endpoints else []
        targets += [tuple(g["xy"]) for g in shuttle if isinstance(g, dict) and isinstance(g.get("xy"), list)]
        for point in targets:
            if not any(t.get("actor") == actor_id and (t.get("x"), t.get("y")) == point
                       and isinstance(t.get("movement_cost"), int) and t["movement_cost"] <= t.get("max_moves", 0)
                       for t in terrains):
                failures.append(f"carrier {actor_id} lacks native affordable terrain evidence at {point}")
    recruit_requests = [r for r in records if r["event"] == "recruit_request"]
    recruits = [r for r in records if r["event"] == "check" and r.get("name") == "native paid scout recruitment"]
    recruit_actor_ids = set()
    if len(recruit_requests) != 3 or len(recruits) != 3:
        failures.append("missing three actual paid native recruit outcomes")
    for request, outcome in zip(recruit_requests, recruits):
        point = (request.get("x"), request.get("y"))
        actor_id = outcome.get("id")
        legal = (point in component_points and request.get("type") == "sw_unit_im_scout_trooper"
                 and outcome.get("ok") is True and outcome.get("side") == 1
                 and outcome.get("type") == request.get("type")
                 and (outcome.get("x"), outcome.get("y")) == point
                 and isinstance(actor_id, str) and bool(actor_id)
                 and actor_id not in recruit_actor_ids and actor_id in carrier_ids
                 and type(outcome.get("cost")) is int and outcome["cost"] > 0
                 and request.get("cost") == outcome["cost"]
                 and request.get("gold") == outcome.get("before_gold")
                 and type(outcome.get("before_gold")) is int and type(outcome.get("after_gold")) is int
                 and outcome["before_gold"] - outcome["after_gold"] == outcome["cost"]
                 and outcome.get("moves") == 0 and outcome.get("attacks_left") == 0
                 and type(outcome.get("max_moves")) is int and outcome["max_moves"] > 0
                 and records.index(request) < records.index(outcome))
        if not legal:
            failures.append("invalid native recruitment request/outcome linkage")
        recruit_actor_ids.add(actor_id)
    move_request_list = [r for r in records if r["event"] == "move_request"]
    move_requests = {r.get("command"): r for r in move_request_list}
    moves = [r for r in records if r["event"] == "move_result"]
    if (not moves or len(move_request_list) != len(move_requests) or len(move_requests) != len(moves)
            or set(move_requests) != {r.get("command") for r in moves}):
        failures.append("incomplete actual native move outcomes")
    for r in moves:
        request = move_requests.get(r.get("command"), {})
        before, after, path = r.get("before", {}), r.get("after", {}), r.get("path", [])
        prefix, costs = r.get("reached_prefix", 0), r.get("step_costs", [])
        valid = (r.get("legal_budget") is True and isinstance(prefix, int) and 1 < prefix <= len(path)
                 and len(costs) == len(path) and costs[0] == 0
                 and all(isinstance(cost, int) and cost > 0 for cost in costs[1:])
                 and [before.get("x"),before.get("y")] == path[0]
                 and request.get("path") == path and request.get("actor", {}).get("id") == before.get("id")
                 and [after.get("x"),after.get("y")] == path[prefix-1]
                 and before.get("id") == after.get("id") and after.get("moves", -1) >= 0)
        if valid:
            spent = before["moves"] - after["moves"]
            valid = (spent == r.get("movement_spent") and sum(costs[1:prefix]) == r.get("terrain_cost_spent")
                     and sum(costs[1:prefix]) <= spent <= before["moves"]
                     and r.get("native_path_cost", before["moves"]+1) <= before["moves"])
            # Installed map/location.cpp distance_between, converting WML's
            # one-based columns to the native zero-based parity first.
            for a,b in zip(path, path[1:]):
                valid = valid and in_bounds(a) and in_bounds(b) and adjacent(a,b)
        if not valid:
            failures.append(f"invalid recorded native movement budget/path: {r.get('command')}")
        if request.get("purpose") == "parking":
            endpoint = request.get("endpoint")
            if (not in_bounds(endpoint) or tuple(endpoint) in shuttle_points
                    or endpoint != path[-1]):
                failures.append("parking move targets invalid or shuttle terrain")
    harvests = [r for r in records if r["event"] == "harvest"]
    deliveries = [r for r in records if r["event"] == "delivery"]
    for event, found in (("harvest",harvests), ("delivery",deliveries)):
        if len(found) != 4 or {r.get("tree") for r in found} != {1,2,3,4} \
                or {r.get("actor") for r in found} != carrier_ids:
            failures.append(f"missing four unique natural {event} outcomes")
    for h in harvests:
        if (h.get("x"),h.get("y")) != endpoints.get(h.get("tree")) or h.get("frame") is not True:
            failures.append("harvest does not prove real tree visit and carried frame")
    for d in deliveries:
        prior = [h for h in harvests if h.get("tree") == d.get("tree") and h.get("actor") == d.get("actor")]
        if (not prior or records.index(prior[0]) >= records.index(d)
                or type(d.get("x")) is not int or type(d.get("y")) is not int
                or not any(g.get("xy") == [d.get("x"),d.get("y")] and g.get("code") == d.get("code") for g in shuttle)
                or d.get("frame") is not False):
            failures.append("delivery lacks ordered natural harvest/shuttle evidence")
    if [d.get("count") for d in deliveries] != [1,2,3,4]:
        failures.append("natural delivery counters must progress 1,2,3,4")
    ordered = []
    for event in ("all_delivered", "victory", "next_scenario", "done"):
        found = [i for i,r in enumerate(records) if r["event"] == event]
        if len(found) != 1:
            failures.append(f"missing unique {event} evidence")
        else:
            ordered.append(found[0])
    if ordered != sorted(ordered) or len(ordered) != 4:
        failures.append("incomplete/incorrect natural victory-to-next-scenario ordering")
    all_done = next((r for r in records if r["event"] == "all_delivered"), {})
    if all_done.get("count") != 4 or all_done.get("states") != ["delivered"]*4:
        failures.append("fourth-delivery objective state not observed before cleanup")
    next_scenario = next((r for r in records if r["event"] == "next_scenario"), {})
    if next_scenario.get("scenario") != NEXT:
        failures.append("normal mission-two transition not observed")
    if not any(r["event"] == "end_turn" for r in records):
        failures.append("ordinary enemy-turn progression not observed")
    for r in records:
        if "turn" in r and (not isinstance(r["turn"], int) or not 1 <= r["turn"] <= 16):
            failures.append("recorded mission-one action exceeded native turn budget")
    return {"status": "FAIL" if failures else "PASS", "failures": list(dict.fromkeys(failures)),
            "actual_exit": exit_code, "timed_out": timed_out, "stop_requested_after_done": stop_requested,
            "owned_stop_after_completion": owned_stop, "records": records}


def run(engine: Path, addon: Path, work: Path, timeout: int, seed: int) -> dict:
    userdata = work / "userdata"
    if userdata.exists():
        raise ValueError("userdata already exists: choose a fresh workdir to preserve evidence")
    if work == addon or addon in work.parents or work in addon.parents:
        raise ValueError("workdir and source add-on must be disjoint")
    version = subprocess.run([str(engine), "--no-log-to-file", "--version"], capture_output=True, text=True, timeout=30)
    if version.returncode != 0 or not re.search(r"\b1\.19\.27\b", version.stdout + version.stderr):
        raise ValueError("fixture requires actual installed Wesnoth 1.19.27")
    source_hash = tree_digest(addon)
    staged = userdata / "data/add-ons" / ADDON_ID
    shutil.copytree(addon, staged)
    staged_hash = tree_digest(staged)
    if staged_hash != source_hash:
        raise ValueError("staged add-on differs from untouched source")
    (userdata / "logs").mkdir(parents=True)
    (userdata / "preferences").write_text("animate_map=no\nidle_anim=no\nturbo=yes\nturbo_speed=20\n",
                                           encoding="utf-8")
    plugin = work / "legal_route_plugin.lua"
    shutil.copy2(HERE / "legal_route_plugin.lua", plugin)
    stdout, stderr = work / "stdout.log", work / "stderr.log"
    command = [str(engine), "--resolution", "1024x768", "--userdata-dir", str(userdata),
               "--plugin", str(plugin), "--rng-seed", str(seed)]
    environment = dict(os.environ, SDL_VIDEO_DRIVER="offscreen", SDL_AUDIO_DRIVER="dummy")

    def streams() -> dict[str,str]:
        paths = [stdout, stderr, *sorted((userdata / "logs").glob("*.log"))]
        return {str(p): p.read_text(encoding="utf-8", errors="replace") for p in paths if p.exists()}

    def evidence(logs: dict[str,str]) -> tuple[list[dict],list[str],str]:
        # Engine logging can mirror stdout. One stream owns ordered route records;
        # all streams still contribute fatal/error diagnostics and raw evidence.
        ranked = sorted(logs.items(), key=lambda item: (-item[1].count(PREFIX),item[0]))
        source,text = ranked[0] if ranked else ("", "")
        records,malformed = parse_records(text)
        return records,malformed,source

    timed_out, stop_requested = False, False
    started = time.monotonic()
    with stdout.open("w", encoding="utf-8") as out, stderr.open("w", encoding="utf-8") as err:
        process = subprocess.Popen(command, cwd=work, env=environment, stdout=out, stderr=err)
        deadline = started + timeout
        while process.poll() is None:
            records,_,_ = evidence(streams())
            if any(r["event"] == "done" for r in records):
                # Retain unexpected post-completion aborts. Only a still-running
                # owned process receives a recorded stop after this grace period.
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    if process.poll() is None:
                        stop_requested = True
                        process.terminate()
                break
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(0.25)
        if process.poll() is None:
            if not stop_requested:
                process.terminate()  # timeout cleanup cannot qualify as an owned successful stop
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=15)
    logs = streams()
    records,malformed,authoritative = evidence(logs)
    errors = list(dict.fromkeys(line for text in logs.values() for line in text.splitlines() if ERRORS.search(line)))
    warnings = list(dict.fromkeys(line for text in logs.values() for line in text.splitlines()
                                  if "warning" in line.lower()))
    phase = assess(records,process.returncode,timed_out,stop_requested,errors,malformed,warnings)
    if tree_digest(staged) != source_hash:
        phase["failures"].append("staged campaign content changed during route proof")
        phase["status"] = "FAIL"
    phase.update({"command": command, "pid": process.pid, "elapsed_seconds": round(time.monotonic()-started,3),
                  "authoritative_record_stream": authoritative,
                  "raw_log_paths": list(logs), "raw_failure_tails":
                  {p:text[-16000:] for p,text in logs.items()} if phase["status"] != "PASS" else {},
                  "engine_errors": errors,
                  "warnings": warnings})
    return {"status": phase["status"], "phase": phase, "engine_version": version.stdout.strip(),
            "engine_version_exit": version.returncode, "addon_sha256": source_hash,
            "staged_addon_sha256": staged_hash, "plugin_sha256": hashlib.sha256(plugin.read_bytes()).hexdigest(),
            "seed": seed, "workdir": str(work), "limits": LIMITS}


class EvidenceTests(unittest.TestCase):
    WARNING = "Warning: Move with identical source and destination. Skipping..."

    @staticmethod
    def complete() -> list[dict]:
        actor = {"id":"leader", "side":1, "x":3, "y":9, "moves":8, "max_moves":8,
                 "attacks_left":1, "hitpoints":40, "experience":0, "frame":False,
                 "frame_tree":None, "variables":{}, "status":{}}
        snapshot = {"actor":actor,"units":[actor],"gold":110,"delivered":0,
                    "trees":[{"state":"ready"} for i in range(4)],"objectives":"trees remain"}
        records = [{"event":"entered", "scenario":FIRST, "difficulty":"NORMAL", "cap":16, "turn":1},
                   {"event":"illegal_request", "actor":dict(actor), "coordinates":[3,9,3,9]},
                   {"event":"illegal_result", "unchanged":True,
                    "before":json.loads(json.dumps(snapshot)), "after":json.loads(json.dumps(snapshot))},
                   {"event":"route_map","width":30,"height":20,"keep":[3,9],
                    "shuttle_goals":[{"xy":[3,9],"code":"Qkp"},{"xy":[4,9],"code":"Qcp"}],
                    "recruit_component":[{"xy":[3,9],"code":"Qkp","castle":True},
                                         {"xy":[4,9],"code":"Qcp","castle":True}]}]
        points = [(12,4,"Gll^Fsm"),(21,5,"Gll^Fsm"),(17,13,"Gll^Fsm"),(23,15,"Gll^Fsm"),
                  (3,9,"Qkp"),(4,9,"Qcp")]
        for index,xy in ((1,(12,4)),(2,(21,5)),(3,(17,13)),(4,(23,15))):
            actor_id = str(index)
            if index > 1:
                gold = 110 - (index-2)*17
                records += [{"event":"recruit_request","x":4,"y":9,"gold":gold,"cost":17,
                             "type":"sw_unit_im_scout_trooper"},
                            {"event":"check","name":"native paid scout recruitment","ok":True,
                             "before_gold":gold,"after_gold":gold-17,"cost":17,"side":1,
                             "type":"sw_unit_im_scout_trooper","id":actor_id,"x":4,"y":9,
                             "moves":0,"attacks_left":0,"max_moves":8}]
            records.append({"event":"carrier","actor":{"id":actor_id},"tree":index})
            for x,y,code in points:
                records.append({"event":"terrain","actor":actor_id,"x":x,"y":y,"code":code,
                                "movement_alias":["Gt"],"movement_cost":1,"max_moves":8})
            before = {"id":actor_id,"x":4,"y":10,"moves":8}
            path = [[4,10],[5,10]]
            records += [{"event":"move_request","command":index,"actor":before,"path":path},
                        {"event":"move_result","command":index,"legal_budget":True,
                         "before":dict(before),"after":{"id":actor_id,"x":5,"y":10,"moves":7},
                         "path":path,"step_costs":[0,1],"reached_prefix":2,
                         "native_path_cost":1,"terrain_cost_spent":1,"movement_spent":1},
                        {"event":"harvest","tree":index,"actor":actor_id,"x":xy[0],"y":xy[1],"frame":True},
                        {"event":"delivery","tree":index,"actor":actor_id,"x":4,"y":9,
                         "code":"Qcp","count":index,"frame":False}]
        records += [{"event":"end_turn","turn":2}, {"event":"all_delivered","count":4,"states":["delivered"]*4},
                    {"event":"victory"}, {"event":"next_scenario","scenario":NEXT}, {"event":"done","success":True}]
        return records

    def result(self, records=None, code=0, timed_out=False, stopped=False, errors=None, malformed=None, warnings=None):
        return assess(self.complete() if records is None else records,code,timed_out,stopped,
                      errors or [],malformed or [],[self.WARNING] if warnings is None else warnings)

    def test_valid_native_outcomes(self):
        for code,stopped in ((0,False),(-15,True),(-9,True)):
            self.assertEqual(self.result(code=code,stopped=stopped)["status"],"PASS")

    def test_unexpected_abort_after_done(self):
        for code in (-6,-11,-15,-9):
            self.assertEqual(self.result(code=code)["status"],"FAIL")
        self.assertEqual(self.result(code=-6,stopped=True)["status"],"FAIL")

    def test_timeout_despite_done(self):
        self.assertEqual(self.result(code=-15,stopped=True,timed_out=True)["status"],"FAIL")

    def test_missing_partial_or_failed_events(self):
        for event in ("entered","illegal_request","illegal_result","route_map","terrain","carrier",
                      "recruit_request","move_result","harvest","delivery","end_turn",
                      "all_delivered","victory","next_scenario","done"):
            records = [r for r in self.complete() if r["event"] != event]
            self.assertEqual(self.result(records)["status"],"FAIL",event)
        records=self.complete();records.insert(1,{"event":"check","name":"setup","ok":False})
        self.assertEqual(self.result(records)["status"],"FAIL")

    def test_negative_snapshots_are_independent(self):
        for mutation in ("actor","unit","status","variables","gold","count","tree","objectives"):
            records=self.complete(); after=records[2]["after"]
            if mutation == "actor": after["actor"]["x"]=6
            if mutation == "unit": after["units"][0]["moves"]=7
            if mutation == "status": after["units"][0]["status"]["poisoned"]=True
            if mutation == "variables": after["units"][0]["variables"]["sw_frame_tree"]=8
            if mutation == "gold": after["gold"]=109
            if mutation == "count": after["delivered"]=1
            if mutation == "tree": after["trees"][0]["state"]="harvested"
            if mutation == "objectives": after["objectives"]="changed"
            self.assertNotEqual(records[2]["before"],after,mutation)
            result=self.result(records)
            self.assertIn("illegal-move before/after snapshots changed",result["failures"],mutation)

    def test_dynamic_goal_failures(self):
        for mutation in ("dimension","goal","duplicate","disconnected","malformed","code_conflict","castle"):
            records=self.complete(); route=next(r for r in records if r["event"] == "route_map")
            if mutation == "dimension": route["width"]=[]
            if mutation == "goal": route["shuttle_goals"].append({"xy":[99,99],"code":"Qcp"})
            if mutation == "duplicate": route["shuttle_goals"].append(dict(route["shuttle_goals"][0]))
            if mutation == "disconnected": route["recruit_component"].append({"xy":[20,18],"code":"Ch","castle":True})
            if mutation == "malformed": route["shuttle_goals"]=[None]
            if mutation == "code_conflict": route["recruit_component"][0]["code"]="Qcp"
            if mutation == "castle": route["recruit_component"][1]["castle"]=False
            self.assertEqual(self.result(records)["status"],"FAIL",mutation)

    def test_per_carrier_terrain_and_recruit_linkage(self):
        records=[r for r in self.complete() if not (r["event"] == "terrain" and r.get("actor") == "2")]
        self.assertTrue(any("carrier 2 lacks" in f for f in self.result(records)["failures"]))
        for mutation in ("recruit_moves","recruit_id","recruit_xy","recruit_gold","recruit_type"):
            records=self.complete(); outcome=next(r for r in records if r["event"] == "check" and r.get("name") == "native paid scout recruitment")
            if mutation == "recruit_moves": outcome["moves"]=8
            if mutation == "recruit_id": outcome["id"]="not-a-carrier"
            if mutation == "recruit_xy": outcome["x"]=99
            if mutation == "recruit_gold": outcome["after_gold"]+=1
            if mutation == "recruit_type": outcome["type"]="other"
            self.assertIn("invalid native recruitment request/outcome linkage",self.result(records)["failures"],mutation)

    def test_budget_path_and_order_failures(self):
        for mutation in ("budget","noncontiguous","request","ordering","cap","delivery_xy","parking"):
            records=self.complete(); move=next(r for r in records if r["event"] == "move_result")
            request=next(r for r in records if r["event"] == "move_request")
            if mutation == "budget": move["after"]["moves"]=9
            if mutation == "noncontiguous": move["path"]=[[4,10],[7,10]]
            if mutation == "request": request["actor"]={"id":"other"}
            if mutation == "ordering": records[-2],records[-3]=records[-3],records[-2]
            if mutation == "cap": records[0]["cap"]=18
            if mutation == "delivery_xy": next(r for r in records if r["event"] == "delivery").pop("x")
            if mutation == "parking": request.update({"purpose":"parking","endpoint":[4,9]})
            self.assertEqual(self.result(records)["status"],"FAIL",mutation)

    def test_exact_native_warning_only(self):
        for warning in ([],["Move with identical source and destination. Skipping..."],
                        [self.WARNING[:-2]],[self.WARNING+" additional diagnostic"],
                        ["prefix "+self.WARNING],["warning other: "+self.WARNING]):
            self.assertIn("missing exact native identical-coordinate warning",self.result(warnings=warning)["failures"])
        for prefix in ("", "warning replay: ", "20261011 12:13:14 warning replay: ",
                       "20261011 12:13:14.123456 warning replay: "):
            self.assertEqual(self.result(warnings=[prefix+self.WARNING])["status"],"PASS")

    def test_duplicate_fourth_delivery_remains_a_failure(self):
        records = self.complete()
        index = max(i for i, r in enumerate(records) if r["event"] == "delivery")
        records.insert(index + 1, dict(records[index]))
        result = self.result(records)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("missing four unique natural delivery outcomes", result["failures"])
        self.assertIn("natural delivery counters must progress 1,2,3,4", result["failures"])

    def test_fatal_output_and_malformed_record(self):
        for line in ("Fatal glibc assertion failed","error replay: illegal command","stack traceback"):
            self.assertTrue(ERRORS.search(line))
            self.assertEqual(self.result(code=-15,stopped=True,errors=[line])["status"],"FAIL")
        _,bad=parse_records('SW_ROUTE: {broken}\n')
        self.assertEqual(self.result(malformed=bad)["status"],"FAIL")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine",type=Path,default=DEFAULT_ENGINE)
    parser.add_argument("--addon",type=Path,default=ADDON)
    parser.add_argument("--workdir",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--timeout",type=int,default=900)
    parser.add_argument("--seed",type=int,default=1)
    parser.add_argument("--selftest",action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceTests)).wasSuccessful() else 1
    if args.timeout <= 0 or not 0 <= args.seed <= 4294967295:
        parser.error("timeout must be positive; seed must be an unsigned 32-bit integer")
    work = args.workdir.resolve() if args.workdir else Path(tempfile.mkdtemp(prefix="sw-legal-route-"))
    work.mkdir(parents=True,exist_ok=True)
    try:
        result = run(args.engine.resolve(),args.addon.resolve(),work,args.timeout,args.seed)
    except Exception as error:
        result = {"status":"FAIL","setup_error":str(error),"workdir":str(work),"limits":LIMITS}
    output = args.output.resolve() if args.output else work / "result.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"output":str(output),"workdir":str(work)}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
