#!/usr/bin/env python3
"""Cost-versus-capability report for the space roster.

Reads the unit roster from gen_hte_units.py and works out exact expected
combat results (Wesnoth's strike order, firststrike, marksman, slow, chance
to hit modifiers, resistances and damage rounding) for every craft against
every enemy craft, in open space and adjacent. No engine is run: this is the
first-order check used to set space costs; the AI soak checks the missions.

For each pairing it reports the gold exchange: the share of the enemy's cost
destroyed per share of one's own cost lost, over one attack each way. 1.0
is an even trade, above 1 favours the first craft. Each craft should trade
near even across the whole enemy roster and clearly win in its role.

Usage: python3 production/tools/space_balance_report.py [--json OUT]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_hte_units as g  # noqa: E402

OPEN_SPACE = "unwalkable"       # Qsp (Open Space) is aliased to Qt
NR = ["sw_unit_nr_xwing", "sw_unit_nr_awing", "sw_unit_nr_ywing", "sw_unit_nr_boarding_shuttle"]
IM = ["sw_unit_im_tie_fighter", "sw_unit_im_tie_interceptor", "sw_unit_im_tie_bomber",
      "sw_unit_im_boarding_shuttle"]
HEROES = ["sw_hero_xwing_luke", "sw_hero_wedge"]
SHIPS = ["sw_unit_im_star_destroyer", "sw_unit_ob_dreadnaught", "sw_unit_im_minelayer"]
# Ordnance that costs a magazine volley: counted, but the report also shows
# results without it, since the magazine runs dry after a few fights.
LIMITED = {"proton_torpedoes", "concussion_missiles"}


def unit(uid: str) -> dict:
    return next(u for u in g.ROSTER if u["id"] == uid)


def defense(u: dict, terrain: str = OPEN_SPACE) -> int:
    """Chance to be hit (%) on the terrain, after the unit's own overrides."""
    return g.unit_defense(u).get(terrain, g.MOVETYPES[u["mt"]]["defense"][terrain])


def resist(u: dict, kind: str) -> int:
    """Percent damage taken."""
    return g.unit_resistance(u).get(kind, g.MOVETYPES[u["mt"]]["resist"][kind])


def round_damage(base: int, num: int, den: int) -> int:
    """src/utils/math.hpp round_damage: round to nearest, ties toward base."""
    if base == 0:
        return 0
    rounding = den // 2 - (0 if base * num >= den else 1)
    return max(1, (base * num + rounding) // den)


# Special effects this report models, keyed by the generator's special name.
def special_effects(a: dict, me: dict, foe: dict) -> dict:
    eff = {"firststrike": False, "marksman": False, "magical": False, "slow": False, "cth_add": 0, "mult": 1.0}
    for sp in a["specials"]:
        if sp in ("firststrike", "marksman", "magical", "slow"):
            eff[sp] = True
        elif sp == "tie_pack":
            eff["cth_add"] += 10                    # assumes a wingmate alongside
        elif sp in g.SPACE_DAMAGE_SPECIALS:
            mult, movetypes = g.SPACE_DAMAGE_SPECIALS[sp]
            if foe["mt"] in movetypes:
                eff["mult"] *= mult
    return eff


def strikes(att: dict, aw: dict, de: dict, dw: dict | None, attacking: bool):
    """Per-strike (damage, chance) for both sides of one fight."""
    def side(me, w, foe, offense):
        eff = special_effects(w, me, foe)
        cth = defense(foe)
        if eff["magical"] and offense:
            cth = 70
        elif eff["marksman"] and offense:
            cth = max(cth, 60)
        cth = max(0, min(100, cth + eff["cth_add"]))
        r = resist(foe, w["type"])
        base = round(w["damage"] * eff["mult"])
        return dict(dmg=round_damage(base, r, 100), n=w["number"], p=cth / 100, slow=eff["slow"],
                    fs=eff["firststrike"])
    a = side(att, aw, de, True)
    d = side(de, dw, att, False) if dw else None
    return a, d


def fight(att: dict, aw: dict, de: dict, dw: dict | None) -> tuple[float, float, float, float]:
    """Exact expected HP lost by (attacker, defender) and kill chances."""
    a, d = strikes(att, aw, de, dw, True)
    order = []
    na, nd = a["n"], d["n"] if d else 0
    first_def = d is not None and d["fs"] and not a["fs"]
    ia = id_ = 0
    turn = "d" if first_def else "a"
    while ia < na or id_ < nd:
        if turn == "a" and ia < na:
            order.append("a"); ia += 1
        elif turn == "d" and id_ < nd:
            order.append("d"); id_ += 1
        turn = "d" if turn == "a" else "a"
    # state: (hp_att, hp_def, att_slowed, def_slowed) -> probability
    states = {(att["hp"], de["hp"], False, False): 1.0}
    for who in order:
        nxt: dict = {}
        for (ha, hd, sa, sd), pr in states.items():
            if ha <= 0 or hd <= 0:
                nxt[(ha, hd, sa, sd)] = nxt.get((ha, hd, sa, sd), 0) + pr
                continue
            s = a if who == "a" else d
            slowed = sa if who == "a" else sd
            dmg = s["dmg"] // 2 if slowed else s["dmg"]
            miss = (ha, hd, sa, sd)
            if who == "a":
                hit = (ha, hd - dmg, sa, sd or s["slow"])
            else:
                hit = (ha - dmg, hd, sa or s["slow"], sd)
            nxt[hit] = nxt.get(hit, 0) + pr * s["p"]
            nxt[miss] = nxt.get(miss, 0) + pr * (1 - s["p"])
        states = nxt
    lost_a = sum(pr * (att["hp"] - max(0, ha)) for (ha, hd, _, _), pr in states.items())
    lost_d = sum(pr * (de["hp"] - max(0, hd)) for (ha, hd, _, _), pr in states.items())
    kill_d = sum(pr for (ha, hd, _, _), pr in states.items() if hd <= 0)
    kill_a = sum(pr for (ha, hd, _, _), pr in states.items() if ha <= 0)
    return lost_a, lost_d, kill_a, kill_d


def ranged(u: dict, limited: bool) -> list[dict]:
    return [a for a in u["attacks"] if a["range"] == "ranged" and (limited or a["name"] not in LIMITED)]


def best_attack(att: dict, de: dict, limited: bool = True) -> dict:
    """The attacker's best weapon by gold traded; the defender answers with
    its own best ranged weapon by damage dealt (all craft fire ranged)."""
    best = None
    for aw in ranged(att, limited):
        options = ranged(de, limited) or [None]
        dw = max(options, key=lambda w: (fight(att, aw, de, w)[0] if w else 0))
        la, ld, ka, kd = fight(att, aw, de, dw)
        score = ld / de["hp"] * value(de) - la / att["hp"] * value(att)
        if best is None or score > best["score"]:
            best = dict(weapon=aw["name"], lost_att=la, lost_def=ld, kill_att=ka, kill_def=kd, score=score)
    return best


def value(u: dict) -> float:
    # Set-piece warships cost no gold; value them by hitpoints so the
    # report can still show how hard each craft hits them.
    return u["cost"] or u["hp"] / 2


def exchange(x: dict, y: dict, limited: bool = True) -> float:
    """Gold destroyed over gold lost, X attacking Y and Y attacking X."""
    one, two = best_attack(x, y, limited), best_attack(y, x, limited)
    dealt = (one["lost_def"] + two["lost_att"]) / y["hp"] * value(y)
    taken = (one["lost_att"] + two["lost_def"]) / x["hp"] * value(x)
    return dealt / taken if taken else math.inf


def report(limited: bool = True) -> dict:
    out = {}
    for side, foes in ((NR + HEROES, IM), (IM, NR)):
        for uid in side:
            x = unit(uid)
            row = {fid: exchange(x, unit(fid), limited) for fid in foes}
            fighters = [v for k, v in row.items() if "shuttle" not in k]
            ships = {sid: best_attack(x, unit(sid), limited)["lost_def"] for sid in SHIPS}
            out[uid] = dict(cost=x["cost"], hp=x["hp"], evasion=100 - defense(x), vs=row,
                            mean=math.exp(sum(map(math.log, fighters)) / len(fighters)),
                            ship_damage=ships,
                            ship_damage_per_gold=sum(ships.values()) / len(SHIPS) / value(x))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--json")
    ap.add_argument("--no-ordnance", action="store_true", help="leave out magazine weapons (dry magazine)")
    args = ap.parse_args()
    data = report(limited=not args.no_ordnance)
    short = {k: k.replace("sw_unit_", "").replace("sw_hero_", "hero_") for k in data}
    foes_nr = [short[k] for k in IM]
    print(f"{'craft':26} cost  hp ev%  " + " ".join(f"{f[:13]:>13}" for f in foes_nr) + "   mean  ship/g")
    for uid, r in data.items():
        cells = " ".join(f"{v:13.2f}" for v in r["vs"].values())
        if len(r["vs"]) == len(foes_nr):
            print(f"{short[uid]:26} {r['cost']:4} {r['hp']:3} {r['evasion']:3}  {cells}  {r['mean']:5.2f}  "
                  f"{r['ship_damage_per_gold']:5.2f}")
        else:
            print(f"{short[uid]:26} {r['cost']:4} {r['hp']:3} {r['evasion']:3}  {cells}  {r['mean']:5.2f}  "
                  f"{r['ship_damage_per_gold']:5.2f}   (vs " + ", ".join(short[k] for k in r["vs"]) + ")")
    if args.json:
        Path(args.json).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
