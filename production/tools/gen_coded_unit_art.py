#!/usr/bin/env python3
"""Draw original, code-generated unit art for Campaign I.

Used for (a) named heroes whose likenesses an external image model refuses to
render and (b) interim art for every other unit until a Codex art job lands.
Each figure is built from simple vector shapes (no external images), drawn at
4x scale with light shading, then reduced to the 72x72 sprite set and a
256x256 portrait. Characters are identified by costume, palette, and gear;
faces are generic and never based on any real actor.

Only files that are missing are written unless --force is given, so finished
Codex art is never overwritten.

Usage: python3 production/tools/gen_coded_unit_art.py [--force] [--only ID,...]
"""
from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
ADDON = ROOT / "addons/Star_Wars_Thrawn_Trilogy"
S = 4  # supersampling factor
W = 72 * S

SKIN = {"fair": (232, 196, 168), "tan": (205, 160, 120), "brown": (150, 100, 70), "dark": (110, 72, 50),
        "blue": (88, 128, 196), "gray": (120, 124, 130), "fur": (120, 82, 48)}


@dataclass
class Look:
    kind: str = "human"            # human, wookiee, noghri, beast, walker, fighter, tie, capital, miner, bike
    skin: str = "fair"
    hair: tuple | None = (120, 80, 40)
    hair_style: str = "short"      # short, long, bun, bald, braid
    top: tuple = (60, 70, 60)
    bottom: tuple = (50, 55, 50)
    vest: tuple | None = None
    cape: tuple | None = None
    helmet: tuple | None = None
    visor: tuple | None = None
    belt: tuple = (70, 50, 30)
    weapon: str = "rifle"          # rifle, pistol, saber, bowcaster, blade, knives, none
    blade: tuple = (90, 255, 120)
    accent: tuple | None = None
    eyes: tuple = (40, 30, 30)
    extra: dict = field(default_factory=dict)


LOOKS: dict[str, Look] = {
    # heroes
    "sw_hero_luke": Look(hair=(196, 160, 90), top=(28, 28, 32), bottom=(28, 28, 32), weapon="saber",
                         blade=(110, 255, 120), belt=(50, 45, 40)),
    "sw_hero_xwing_luke": Look(kind="fighter", top=(225, 228, 232), accent=(200, 60, 40)),
    "sw_hero_leia": Look(hair=(70, 45, 30), hair_style="braid", top=(232, 232, 228), bottom=(232, 232, 228),
                         weapon="pistol", belt=(140, 140, 150)),
    "sw_hero_han": Look(skin="tan", hair=(90, 60, 35), top=(232, 225, 205), vest=(30, 30, 34),
                        bottom=(40, 50, 80), weapon="pistol", accent=(170, 40, 40)),
    "sw_hero_chewbacca": Look(kind="wookiee", skin="fur", weapon="bowcaster", belt=(80, 60, 40)),
    "sw_hero_lando": Look(skin="brown", hair=(30, 22, 18), top=(70, 110, 150), cape=(40, 70, 110),
                          bottom=(60, 60, 70), weapon="pistol", accent=(220, 190, 90)),
    "sw_hero_mara": Look(hair=(190, 70, 40), hair_style="long", top=(30, 30, 36), bottom=(30, 30, 36),
                         weapon="blade", blade=(170, 200, 230), eyes=(60, 140, 90)),
    "sw_hero_karrde": Look(hair=(60, 45, 35), top=(110, 90, 70), vest=(70, 60, 50), bottom=(60, 50, 45),
                           weapon="pistol"),
    "sw_hero_wedge": Look(kind="fighter", top=(220, 222, 226), accent=(200, 140, 40)),
    "sw_hero_pellaeon": Look(hair=(200, 200, 200), top=(110, 116, 112), bottom=(40, 42, 44),
                             weapon="pistol", accent=(200, 60, 50)),
    "sw_hero_thrawn": Look(skin="blue", hair=(18, 20, 28), top=(236, 236, 232), bottom=(236, 236, 232),
                           weapon="none", eyes=(230, 30, 30), accent=(220, 190, 80)),
    # New Republic
    "sw_unit_nr_trooper": Look(skin="tan", helmet=(150, 150, 130), top=(90, 100, 60), vest=(130, 130, 125),
                               bottom=(90, 100, 60)),
    "sw_unit_nr_sergeant": Look(helmet=(150, 150, 130), top=(90, 100, 60), vest=(130, 130, 125),
                                bottom=(90, 100, 60), accent=(220, 190, 80)),
    "sw_unit_nr_commando": Look(skin="brown", helmet=(60, 70, 50), top=(60, 70, 50), bottom=(50, 60, 45),
                                weapon="rifle"),
    "sw_unit_nr_eweb_team": Look(helmet=(150, 150, 130), top=(90, 100, 60), vest=(130, 130, 125),
                                 bottom=(90, 100, 60), weapon="heavy"),
    "sw_unit_nr_field_medic": Look(hair=(60, 40, 30), top=(220, 220, 215), vest=(200, 60, 60),
                                   bottom=(90, 100, 60), weapon="pistol"),
    "sw_unit_nr_militia": Look(skin="tan", hair=(50, 35, 25), top=(130, 110, 80), bottom=(80, 70, 60),
                               weapon="pistol"),
    "sw_unit_wk_warrior": Look(kind="wookiee", skin="fur", weapon="blade", blade=(200, 200, 200)),
    "sw_unit_wk_lookout": Look(kind="wookiee", skin="fur", weapon="bowcaster", belt=(60, 90, 50)),
    "sw_unit_nr_xwing": Look(kind="fighter", top=(220, 222, 226), accent=(200, 60, 40)),
    "sw_unit_nr_awing": Look(kind="fighter", top=(220, 222, 226), accent=(190, 40, 40), extra={"wedge": True}),
    "sw_unit_nr_ywing": Look(kind="fighter", top=(200, 200, 190), accent=(220, 170, 50), extra={"long": True}),
    "sw_unit_nr_docked_warship": Look(kind="capital", top=(190, 190, 185), accent=(200, 60, 40)),
    # Imperial
    "sw_unit_im_stormtrooper": Look(helmet=(240, 240, 240), visor=(20, 20, 20), top=(240, 240, 240),
                                    bottom=(240, 240, 240), belt=(30, 30, 30), skin="gray"),
    "sw_unit_im_stormtrooper_sergeant": Look(helmet=(240, 240, 240), visor=(20, 20, 20), top=(240, 240, 240),
                                             bottom=(240, 240, 240), belt=(30, 30, 30), accent=(200, 120, 40),
                                             skin="gray"),
    "sw_unit_im_scout_trooper": Look(kind="bike", helmet=(235, 235, 235), top=(30, 30, 30)),
    "sw_unit_im_officer": Look(hair=(80, 60, 40), helmet=(100, 106, 100), top=(100, 106, 100),
                               bottom=(40, 42, 44), weapon="pistol", accent=(200, 60, 50)),
    "sw_unit_im_at_st": Look(kind="walker", top=(150, 152, 156)),
    "sw_unit_im_noghri": Look(kind="noghri", skin="gray", top=(40, 40, 46), weapon="knives"),
    "sw_unit_im_tie_fighter": Look(kind="tie", top=(120, 124, 132)),
    "sw_unit_im_tie_interceptor": Look(kind="tie", top=(120, 124, 132), extra={"dagger": True}),
    "sw_unit_im_tie_bomber": Look(kind="tie", top=(120, 124, 132), extra={"bomber": True}),
    "sw_unit_im_mole_miner": Look(kind="miner", top=(170, 140, 70)),
    "sw_unit_im_star_destroyer": Look(kind="capital", top=(200, 202, 206), extra={"wedge": True}),
    # Smugglers and wildlife
    "sw_unit_sm_smuggler": Look(skin="tan", hair=(40, 30, 25), top=(150, 120, 90), vest=(80, 60, 45),
                                bottom=(70, 60, 50), weapon="pistol"),
    "sw_unit_sm_veteran": Look(skin="dark", hair=(20, 18, 16), hair_style="bald", top=(90, 90, 100),
                               vest=(60, 50, 40), bottom=(60, 55, 50), weapon="rifle"),
    "sw_unit_wl_vornskr": Look(kind="beast", skin="gray"),
    # Campaign II
    "sw_hero_khabarakh": Look(kind="noghri", skin="gray", top=(46, 44, 52), weapon="knives"),
    "sw_hero_cbaoth": Look(hair=(236, 236, 236), hair_style="long", top=(110, 80, 50), bottom=(96, 70, 46),
                           cape=(90, 64, 40), weapon="saber", blade=(120, 255, 130), belt=(60, 44, 30),
                           extra={"beard": True}),
    "sw_hero_bel_iblis": Look(hair=(200, 200, 205), top=(70, 80, 70), cape=(60, 66, 58), bottom=(50, 52, 50),
                              weapon="pistol", accent=(200, 160, 60)),
    "sw_unit_bi_commando": Look(helmet=(110, 100, 80), top=(100, 92, 70), vest=(80, 74, 60), bottom=(90, 84, 66)),
    "sw_unit_im_clone_trooper": Look(helmet=(236, 236, 236), visor=(20, 20, 20), top=(236, 236, 236),
                                     bottom=(236, 236, 236), belt=(30, 30, 30), skin="gray", accent=(60, 60, 64)),
    "sw_unit_im_decon_droid": Look(kind="walker", top=(130, 120, 90)),
    "sw_unit_ob_dreadnaught": Look(kind="capital", top=(170, 160, 150), accent=(120, 60, 50)),
    "sw_unit_nr_boarding_shuttle": Look(kind="fighter", top=(200, 200, 196), accent=(60, 120, 200), extra={"long": True}),
    "sw_unit_im_boarding_shuttle": Look(kind="fighter", top=(150, 154, 160), accent=(40, 40, 44), extra={"wedge": True}),
}

FRAMES = ("standing", "idle-1", "idle-2", "move-1", "move-2", "melee-1", "melee-2",
          "ranged-1", "ranged-2", "defend", "death-1", "death-2")


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3]) + ((c[3],) if len(c) > 3 else (255,))


def poly(d, pts, color, outline=True):
    d.polygon([(x * S, y * S) for x, y in pts], fill=shade(color, 1.0),
              outline=shade(color, 0.55) if outline else None)


def ell(d, box, color, outline=True):
    x1, y1, x2, y2 = box
    d.ellipse((x1 * S, y1 * S, x2 * S, y2 * S), fill=shade(color, 1.0),
              outline=shade(color, 0.55) if outline else None, width=S)


def line(d, pts, color, width):
    d.line([(x * S, y * S) for x, y in pts], fill=shade(color, 1.0), width=int(width * S))


# --- figure painters (coordinates in 72x72 space) -----------------------------

def paint_human(d, L: Look, pose: str):
    skin = SKIN[L.skin]
    lean = {"move-1": 1.5, "move-2": -1, "melee-1": -2, "melee-2": 3, "defend": -2}.get(pose, 0)
    bob = {"idle-1": 0.5, "idle-2": -0.5, "move-1": -1, "move-2": 0}.get(pose, 0)
    cx = 36 + lean
    top = 14 + bob
    # legs
    stride = {"move-1": 5, "move-2": -4, "melee-2": 4}.get(pose, 2)
    poly(d, [(cx - 6, top + 26), (cx - 1, top + 26), (cx - 2 - stride / 2, top + 46), (cx - 7 - stride / 2, top + 46)], L.bottom)
    poly(d, [(cx + 1, top + 26), (cx + 6, top + 26), (cx + 7 + stride / 2, top + 46), (cx + 2 + stride / 2, top + 46)], shade(L.bottom, 0.85))
    ell(d, (cx - 9 - stride / 2, top + 44, cx - 1 - stride / 2, top + 48), (30, 26, 24))
    ell(d, (cx + 1 + stride / 2, top + 44, cx + 9 + stride / 2, top + 48), (30, 26, 24))
    if L.cape:
        poly(d, [(cx - 8, top + 10), (cx + 8, top + 10), (cx + 11, top + 36), (cx - 11, top + 36)], L.cape)
    # torso
    poly(d, [(cx - 8, top + 9), (cx + 8, top + 9), (cx + 7, top + 27), (cx - 7, top + 27)], L.top)
    if L.vest:
        poly(d, [(cx - 7, top + 10), (cx - 1, top + 10), (cx - 1, top + 24), (cx - 6, top + 24)], L.vest)
        poly(d, [(cx + 1, top + 10), (cx + 7, top + 10), (cx + 6, top + 24), (cx + 1, top + 24)], L.vest)
    line(d, [(cx - 7, top + 24), (cx + 7, top + 24)], L.belt, 2.2)
    if L.accent:
        poly(d, [(cx - 7, top + 12), (cx - 3, top + 12), (cx - 3, top + 15), (cx - 7, top + 15)], L.accent, False)
    # arms and weapon
    arm = shade(L.top, 0.9)
    if L.weapon == "saber":
        ang = {"melee-1": -2.2, "melee-2": 0.4, "defend": -1.2}.get(pose, -1.0)
        hx, hy = cx + 7, top + 18
        line(d, [(cx + 6, top + 11), (hx, hy)], arm, 3.2)
        ex, ey = hx + 22 * math.cos(ang), hy + 22 * math.sin(ang)
        line(d, [(hx, hy), (ex, ey)], shade(L.blade, 0.7), 3.6)
        line(d, [(hx, hy), (ex, ey)], (235, 255, 235), 1.4)
        line(d, [(hx - 2 * math.cos(ang), hy - 2 * math.sin(ang)), (hx, hy)], (160, 160, 170), 2.6)
    elif L.weapon in ("rifle", "heavy", "bowcaster"):
        gy = top + 17 + (1 if pose.startswith("ranged") else 0)
        length = 20 if L.weapon != "heavy" else 24
        line(d, [(cx - 6, top + 11), (cx - 1, gy + 1)], arm, 3.2)
        line(d, [(cx + 6, top + 11), (cx + 9, gy)], arm, 3.2)
        color = (60, 60, 66) if L.weapon != "bowcaster" else (110, 80, 50)
        line(d, [(cx - 4, gy + 1), (cx - 4 + length, gy - 1)], color, 3.0 if L.weapon != "heavy" else 4.2)
        if L.weapon == "bowcaster":
            line(d, [(cx + 8, gy - 6), (cx + 8, gy + 5)], (150, 150, 160), 1.6)
        if pose == "ranged-2":
            ell(d, (cx - 7 + length, gy - 5, cx + 1 + length, gy + 3), (255, 120, 90), False)
    elif L.weapon == "pistol":
        line(d, [(cx - 6, top + 11), (cx - 7, top + 23)], arm, 3.0)
        ex = cx + (16 if pose.startswith("ranged") else 9)
        ey = top + (14 if pose.startswith("ranged") else 21)
        line(d, [(cx + 6, top + 11), (ex, ey)], arm, 3.0)
        line(d, [(ex - 1, ey), (ex + 6, ey - 1)], (50, 50, 56), 2.6)
        if pose == "ranged-2":
            ell(d, (ex + 5, ey - 4, ex + 11, ey + 2), (255, 120, 90), False)
    elif L.weapon in ("blade", "knives"):
        ang = {"melee-1": -1.8, "melee-2": 0.5}.get(pose, -0.6)
        hx, hy = cx + 9, top + 18
        line(d, [(cx + 6, top + 11), (hx, hy)], arm, 3.0)
        line(d, [(hx, hy), (hx + 12 * math.cos(ang), hy + 12 * math.sin(ang))], L.blade, 2.0)
        line(d, [(cx - 6, top + 11), (cx - 8, top + 23)], arm, 3.0)
    else:  # hands clasped behind the back
        line(d, [(cx - 6, top + 11), (cx - 4, top + 22)], arm, 3.0)
        line(d, [(cx + 6, top + 11), (cx + 4, top + 22)], arm, 3.0)
    # head
    ell(d, (cx - 5, top - 2, cx + 5, top + 9), skin)
    ell(d, (cx + 1.5, top + 2.5, cx + 3, top + 4), L.eyes, False)
    if L.helmet:
        poly(d, [(cx - 6, top + 4), (cx - 5.5, top - 2), (cx, top - 4), (cx + 5.5, top - 2), (cx + 6, top + 4)], L.helmet)
        if L.visor:
            poly(d, [(cx - 1, top + 2), (cx + 6, top + 2), (cx + 5, top + 5), (cx - 1, top + 5)], L.visor, False)
    if L.extra.get("beard"):
        poly(d, [(cx - 4, top + 6), (cx + 5, top + 6), (cx + 3, top + 15), (cx, top + 17), (cx - 3, top + 14)], L.hair or (220, 220, 220))
    if L.helmet:
        pass
    elif L.hair and L.hair_style != "bald":
        poly(d, [(cx - 5.5, top + 3), (cx - 5, top - 2), (cx, top - 3.5), (cx + 5, top - 2), (cx + 5, top + 1),
                 (cx + 1, top), (cx - 3, top + 1)], L.hair)
        if L.hair_style == "long":
            poly(d, [(cx - 6, top + 1), (cx - 2, top + 1), (cx - 3, top + 14), (cx - 7, top + 12)], L.hair)
        if L.hair_style == "braid":
            ell(d, (cx - 8, top - 4, cx - 2, top + 2), L.hair)
            ell(d, (cx - 2, top - 5, cx + 4, top), L.hair)


def paint_wookiee(d, L: Look, pose: str):
    fur = SKIN["fur"]
    bob = {"idle-1": 0.5, "idle-2": -0.5, "move-1": -1}.get(pose, 0)
    lean = {"move-1": 1.5, "melee-2": 3, "defend": -2}.get(pose, 0)
    cx, top = 36 + lean, 8 + bob
    stride = {"move-1": 5, "move-2": -4}.get(pose, 2)
    poly(d, [(cx - 8, top + 32), (cx - 1, top + 32), (cx - 3 - stride / 2, top + 54), (cx - 9 - stride / 2, top + 54)], shade(fur, 0.9))
    poly(d, [(cx + 1, top + 32), (cx + 8, top + 32), (cx + 9 + stride / 2, top + 54), (cx + 3 + stride / 2, top + 54)], shade(fur, 0.8))
    poly(d, [(cx - 10, top + 10), (cx + 10, top + 10), (cx + 9, top + 34), (cx - 9, top + 34)], fur)
    line(d, [(cx - 9, top + 12), (cx + 8, top + 30)], L.belt, 2.4)
    for i in range(6):
        line(d, [(cx - 8 + i * 3, top + 13 + i * 3), (cx - 7 + i * 3, top + 16 + i * 3)], (170, 170, 175), 1.2)
    paint_human(d, Look(skin="fur", hair=None, top=fur, bottom=fur, weapon=L.weapon, blade=L.blade,
                        belt=L.belt, eyes=(30, 30, 30)), "__arms_only__") if False else None
    arm = shade(fur, 0.85)
    if L.weapon == "bowcaster":
        gy = top + 20
        line(d, [(cx - 8, top + 13), (cx - 2, gy)], arm, 4.0)
        line(d, [(cx + 8, top + 13), (cx + 11, gy)], arm, 4.0)
        line(d, [(cx - 4, gy), (cx + 18, gy - 2)], (110, 80, 50), 3.2)
        line(d, [(cx + 10, gy - 7), (cx + 10, gy + 5)], (150, 150, 160), 1.8)
        if pose == "ranged-2":
            ell(d, (cx + 16, gy - 6, cx + 24, gy + 2), (120, 200, 255), False)
    else:
        ang = {"melee-1": -1.8, "melee-2": 0.5}.get(pose, -0.6)
        hx, hy = cx + 11, top + 22
        line(d, [(cx + 8, top + 13), (hx, hy)], arm, 4.0)
        line(d, [(hx, hy), (hx + 14 * math.cos(ang), hy + 14 * math.sin(ang))], L.blade, 2.4)
        line(d, [(cx - 8, top + 13), (cx - 10, top + 30)], arm, 4.0)
    ell(d, (cx - 7, top - 4, cx + 7, top + 12), fur)
    ell(d, (cx - 2, top + 5, cx + 7, top + 11), shade(fur, 1.25))
    ell(d, (cx + 1, top + 1, cx + 3, top + 3), (20, 20, 20), False)


def paint_noghri(d, L: Look, pose: str):
    paint_human(d, Look(skin="gray", hair=None, hair_style="bald", top=(40, 40, 46), bottom=(36, 36, 42),
                        belt=(20, 20, 24), weapon="knives", blade=(190, 190, 200), eyes=(10, 10, 10)), pose)
    # jutting jaw
    cx = 36 + {"move-1": 1.5, "move-2": -1, "melee-1": -2, "melee-2": 3, "defend": -2}.get(pose, 0)
    top = 14 + {"idle-1": 0.5, "idle-2": -0.5, "move-1": -1}.get(pose, 0)
    poly(d, [(cx + 2, top + 5), (cx + 8, top + 7), (cx + 3, top + 9)], SKIN["gray"])


def paint_beast(d, L: Look, pose: str):
    c = (95, 100, 105)
    step = {"move-1": 3, "move-2": -3, "melee-1": -3, "melee-2": 4}.get(pose, 0)
    ell(d, (14 + step, 30, 50 + step, 46), c)
    for lx in (18, 26, 38, 46):
        line(d, [(lx + step, 42), (lx + step + (2 if lx > 30 else -1), 56)], shade(c, 0.8), 3)
    ell(d, (44 + step, 26, 60 + step, 38), shade(c, 1.1))
    poly(d, [(56 + step, 32), (64 + step, 34), (56 + step, 36)], (230, 230, 230), False)
    ell(d, (53 + step, 29, 55 + step, 31), (220, 40, 30), False)
    line(d, [(14 + step, 36), (4, 30 if pose != "melee-2" else 44), (2, 24)], shade(c, 0.7), 2.4)


def paint_walker(d, L: Look, pose: str):
    c = L.top
    step = {"move-1": 4, "move-2": -4}.get(pose, 0)
    line(d, [(30, 30), (24 - step, 44), (28 - step, 62)], shade(c, 0.8), 4)
    line(d, [(42, 30), (48 + step, 44), (44 + step, 62)], shade(c, 0.75), 4)
    poly(d, [(18, 10), (52, 10), (58, 22), (50, 32), (22, 32), (16, 22)], c)
    poly(d, [(46, 16), (56, 18), (52, 24), (44, 22)], (40, 40, 44))
    line(d, [(54, 26), (64, 26)], (60, 60, 64), 2.4)
    line(d, [(54, 29), (63, 30)], (60, 60, 64), 2.0)
    if pose == "ranged-2":
        ell(d, (62, 22, 70, 30), (255, 110, 80), False)


def paint_fighter(d, L: Look, pose: str):
    c, a = L.top, (L.accent or (200, 60, 40))
    dx = {"move-1": 2, "move-2": -1, "defend": -3}.get(pose, 0)
    if L.extra.get("wedge"):
        poly(d, [(14 + dx, 26), (60 + dx, 36), (14 + dx, 46), (20 + dx, 36)], c)
        line(d, [(18 + dx, 30), (50 + dx, 36)], a, 2.4)
    elif L.extra.get("long"):
        line(d, [(12 + dx, 36), (62 + dx, 36)], c, 5)
        ell(d, (46 + dx, 31, 60 + dx, 41), shade(c, 1.05))
        line(d, [(18 + dx, 24), (18 + dx, 48)], shade(c, 0.85), 4)
        line(d, [(22 + dx, 33), (40 + dx, 33)], a, 2)
    else:
        poly(d, [(16 + dx, 33), (60 + dx, 35), (60 + dx, 37), (16 + dx, 39)], c)
        for wy in (20, 52):
            line(d, [(22 + dx, 36), (34 + dx, wy)], shade(c, 0.9), 3.4)
            line(d, [(34 + dx, wy), (46 + dx, wy)], shade(c, 0.9), 2.4)
        line(d, [(22 + dx, 34), (36 + dx, 34)], a, 2)
        ell(d, (40 + dx, 31, 48 + dx, 37), (60, 80, 110))
    if pose.startswith("ranged"):
        for y in (32, 40):
            line(d, [(62 + dx, y), (70, y)], (255, 90, 80) if pose == "ranged-2" else (255, 160, 140), 1.6)


def paint_tie(d, L: Look, pose: str):
    c = L.top
    dx = {"move-1": 2, "move-2": -1}.get(pose, 0)
    if L.extra.get("bomber"):
        ell(d, (24 + dx, 30, 40 + dx, 42), c)
        ell(d, (38 + dx, 30, 54 + dx, 42), c)
    else:
        ell(d, (28 + dx, 28, 44 + dx, 44), c)
        ell(d, (33 + dx, 33, 39 + dx, 39), (40, 50, 60))
    for wx in (14, 58):
        if L.extra.get("dagger"):
            poly(d, [(wx + dx, 14), (wx + 4 + dx, 36), (wx + dx, 58), (wx - 3 + dx, 36)], (50, 52, 60))
        else:
            poly(d, [(wx - 4 + dx, 14), (wx + 4 + dx, 14), (wx + 4 + dx, 58), (wx - 4 + dx, 58)], (50, 52, 60))
        line(d, [(wx + dx, 36), (36 + dx, 36)], shade(c, 0.85), 2.4)
    if pose == "ranged-2":
        line(d, [(46 + dx, 37), (70, 37)], (120, 255, 120), 1.6)


def paint_capital(d, L: Look, pose: str):
    c, a = L.top, (L.accent or (90, 90, 90))
    if L.extra.get("wedge"):
        poly(d, [(6, 30), (68, 36), (6, 44)], c)
        poly(d, [(12, 28), (24, 28), (26, 34), (12, 34)], shade(c, 0.85))
        line(d, [(16, 26), (16, 22)], shade(c, 0.7), 2)
    else:
        poly(d, [(8, 30), (60, 30), (66, 36), (60, 42), (8, 42)], c)
        line(d, [(14, 33), (54, 33)], a, 2)
        poly(d, [(16, 24), (30, 24), (30, 30), (16, 30)], shade(c, 0.85))
    if pose == "ranged-2":
        line(d, [(60, 34), (70, 30)], (120, 255, 120), 2)


def paint_miner(d, L: Look, pose: str):
    c = L.top
    ell(d, (16, 24, 52, 48), c)
    poly(d, [(50, 30), (66, 36), (50, 42)], (90, 90, 96))
    if pose.startswith("melee"):
        ell(d, (60, 30, 70, 42), (120, 200, 255), False)
    line(d, [(18, 30), (48, 30)], shade(c, 0.7), 1.6)


def paint_bike(d, L: Look, pose: str):
    dx = {"move-1": 3, "move-2": -2}.get(pose, 0)
    line(d, [(10 + dx, 44), (62 + dx, 40)], (60, 62, 66), 4)
    poly(d, [(20 + dx, 36), (44 + dx, 34), (46 + dx, 44), (22 + dx, 46)], (80, 82, 86))
    paint_human(d, Look(helmet=(235, 235, 235), visor=(20, 20, 20), top=(30, 30, 32), bottom=(30, 30, 32),
                        weapon="none", skin="gray"), "standing") if False else None
    poly(d, [(28 + dx, 18), (38 + dx, 18), (38 + dx, 34), (28 + dx, 34)], (30, 30, 32))
    ell(d, (28 + dx, 8, 38 + dx, 19), (235, 235, 235))
    poly(d, [(33 + dx, 12), (39 + dx, 12), (39 + dx, 15), (33 + dx, 15)], (20, 20, 20), False)
    line(d, [(36 + dx, 24), (46 + dx, 32)], (30, 30, 32), 2.6)
    if pose == "ranged-2":
        line(d, [(62 + dx, 40), (70, 39)], (255, 100, 80), 1.6)


PAINTERS = {"human": paint_human, "wookiee": paint_wookiee, "noghri": paint_noghri, "beast": paint_beast,
            "walker": paint_walker, "fighter": paint_fighter, "tie": paint_tie, "capital": paint_capital,
            "miner": paint_miner, "bike": paint_bike}


def render_frame(L: Look, pose: str) -> Image.Image:
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    PAINTERS[L.kind](d, L, "standing" if pose.startswith("death") else pose)
    if pose == "defend":
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        alpha = img.split()[3].point(lambda a: int(a * 0.25))
        overlay.putalpha(alpha)
        img = Image.alpha_composite(img, overlay)
    if pose.startswith("death"):
        angle = 35 if pose == "death-1" else 80
        img = img.rotate(-angle, resample=Image.BICUBIC, center=(W // 2, int(W * 0.8)))
        fade = 0.75 if pose == "death-1" else 0.4
        img.putalpha(img.split()[3].point(lambda a: int(a * fade)))
    img = img.filter(ImageFilter.GaussianBlur(radius=S * 0.15))
    return img.resize((72, 72), Image.LANCZOS)


def render_portrait(L: Look, unit_id: str) -> Image.Image:
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    big = render_frame(L, "standing").resize((288, 288), Image.LANCZOS)
    # Frame the head and shoulders of the figure (upper half of the sprite).
    crop_box = (36, 0, 252, 216) if L.kind in ("human", "wookiee", "noghri") else (0, 36, 288, 252)
    head = big.crop(crop_box).resize((size, size), Image.LANCZOS)
    bg = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(bg)
    for r in range(110, 0, -4):
        a = int(150 * (1 - r / 110))
        d.ellipse((128 - r, 120 - r, 128 + r, 120 + r), fill=(40, 50, 70, a))
    img = Image.alpha_composite(bg, head)
    del unit_id
    return img


def unit_ids() -> list[str]:
    ids = []
    for f in sorted([*(ADDON / "units").glob("hte_*.cfg"), *(ADDON / "units").glob("dfr_*.cfg")]):
        ids += re.findall(r"(?m)^\s*id=(sw_[a-z0-9_]+)\s*$", f.read_text(encoding="utf-8"))
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--only")
    args = parser.parse_args()
    only = set(args.only.split(",")) if args.only else None
    written = 0
    for uid in unit_ids():
        if uid.startswith("sw_ability") or uid.startswith("sw_special"):
            continue
        if only and uid not in only:
            continue
        L = LOOKS.get(uid)
        if L is None:
            print(f"no look defined for {uid}")
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", uid).strip("-")
        out = ADDON / "images/units" / slug
        out.mkdir(parents=True, exist_ok=True)
        for pose in FRAMES:
            path = out / f"{pose}.png"
            if args.force or not path.exists() or path.stat().st_size < 400:
                render_frame(L, pose).save(path, optimize=True)
                written += 1
        portrait = ADDON / "images/portraits" / f"{slug}.png"
        if args.force or not portrait.exists() or portrait.stat().st_size < 400:
            render_portrait(L, uid).save(portrait, optimize=True)
            written += 1
    print(f"wrote {written} images")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
