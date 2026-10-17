"""Rank abilities: what each class earns at rank I, II and III.

Owner direction (2026-10-12): a rank-up must bring a passive or active ability
specific to the unit's class and rank, so keeping a unit alive is rewarded
with something new to play with, not only a stat increase. Do not pile on
attack types: rank abilities are native abilities (steadfast, skirmisher,
ambush, regeneration, healing, auras) or a special added to a weapon the unit
already carries (first strike, marksman, slow, backstab, drain, guard, extra
damage against a target class). The aimed variant of a weapon gets the same
special as the weapon itself; no rank adds an attack.

A unit's rank is lua/sw_rank.lua's: its type's starting rank (promoted types
start at I) plus one per after-max-level advancement, up to III. When a unit
reaches a rank, sw_rank.lua adds that rank's ability as a permanent object
(id sw_rank_ability_<n>), in addition to whatever the advancement itself gave
(+3 HP or a drill). Units that only promote (troopers, militia, smugglers)
earn ranks once promoted. Vehicles, shuttles, capital ships, objects,
creatures and the enemy's named commanders have no rank abilities.

gen_hte_units.py writes the catalogue to lua/sw_rank_abilities.lua and lists
each unit's rank abilities in its description, so players see what a unit is
working towards.
"""
from __future__ import annotations


class Tr(str):
    """A translatable string (written as _ "..." in Lua)."""


# --- WML node helpers: (tag, attributes, children) ---------------------------

def node(tag: str, attrs: dict | None = None, *children) -> tuple:
    return (tag, attrs or {}, list(children))


def new_ability(ability: tuple) -> tuple:
    return node("effect", {"apply_to": "new_ability"}, node("abilities", {}, ability))


def adjacent() -> tuple:
    return node("affect_adjacent")


# --- Abilities ---------------------------------------------------------------

def steadfast(name: str, flavour: str) -> tuple:
    return node("resistance", {
        "id": "sw_rank_steadfast", "multiply": 2, "max_value": 50, "affect_self": "yes", "active_on": "defense",
        "name": Tr(name),
        "description": Tr(f"{flavour} This unit's resistances are doubled, up to 50%, when defending. "
                          "Vulnerabilities are not affected."),
    }, node("filter_base_value", {"greater_than": 0, "less_than": 50}))


def skirmisher(name: str, flavour: str) -> tuple:
    return node("skirmisher", {
        "id": "sw_rank_skirmisher", "affect_self": "yes", "name": Tr(name),
        "description": Tr(f"{flavour} This unit ignores enemy zones of control."),
    })


def hides(name: str, flavour: str, terrain: str, where: str) -> tuple:
    return node("hides", {
        "id": "sw_rank_hides", "affect_self": "yes", "name": Tr(name),
        "description": Tr(f"{flavour} This unit is hidden from enemies while it stands in {where}, unless an "
                          "enemy is next to it. An enemy that discovers it loses its remaining movement."),
    }, node("filter", {}, node("filter_location", {"terrain": terrain})))


def regenerates(name: str, flavour: str, value: int) -> tuple:
    return node("regenerate", {
        "id": "sw_rank_regenerates", "value": value, "affect_self": "yes", "poison": "cured", "name": Tr(name),
        "description": Tr(f"{flavour} This unit recovers {value} HP at the start of its turn, wherever it is."),
    })


# Unit filters have no movement-type key (installed src/units/filter.cpp
# reads type=, race=, ... but not movement_type=, and WFL units do not expose
# it either), so a [filter_*] with movement_type= matched every unit. Class
# filters list the unit types of each movetype instead. gen_hte_units.py
# fills this from its roster before rendering.
TYPES_BY_MOVETYPE: dict[str, list[str]] = {}


def unit_types(movetypes: str) -> str:
    """Comma-separated unit types of the given movetypes, for a type= filter."""
    types = [t for mt in movetypes.split(",") for t in TYPES_BY_MOVETYPE.get(mt, [])]
    if not types:
        raise ValueError(f"no unit types for movetypes {movetypes!r}")
    return ",".join(types)


def hit_aura(name: str, flavour: str, *, ranged_only: bool = False, craft_only: bool = False) -> tuple:
    student = []
    if craft_only:
        student.append(node("filter_student", {"type": unit_types(CRAFT)}))
    if ranged_only:
        student.append(node("filter_student", {}, node("filter_weapon", {"range": "ranged"})))
    who = "allied starfighters" if craft_only else "allies"
    what = "ranged attacks" if ranged_only else "attacks"
    return node("chance_to_hit", {
        "id": "sw_rank_hit_aura", "add": 10, "cumulative": "no", "affect_self": "no", "affect_allies": "yes",
        "name": Tr(name),
        "description": Tr(f"{flavour} Adjacent {who} have +10% chance to hit with their {what}."),
    }, adjacent(), *student)


def fear_aura(name: str, flavour: str) -> tuple:
    return node("chance_to_hit", {
        "id": "sw_rank_fear_aura", "sub": 10, "cumulative": "no", "affect_self": "no", "affect_allies": "no",
        "affect_enemies": "yes", "name": Tr(name),
        "description": Tr(f"{flavour} Adjacent enemies have -10% chance to hit with all their attacks."),
    }, adjacent())


def guard_aura(name: str, flavour: str) -> tuple:
    return node("resistance", {
        "id": "sw_rank_guard_aura", "add": 10, "max_value": 60, "cumulative": "no", "affect_self": "no",
        "affect_allies": "yes", "name": Tr(name),
        "description": Tr(f"{flavour} Adjacent allies take 10% less damage of every type (up to 60% resistance)."),
    }, adjacent())


def field_surgery() -> list:
    """Replaces heals +4 (core id healing) with heals +8."""
    return [
        node("effect", {"apply_to": "remove_ability"}, node("abilities", {}, node("heals", {"id": "healing"}))),
        new_ability(node("heals", {
            "id": "healing", "value": 8, "affect_allies": "yes", "affect_self": "no", "poison": "slowed",
            "name": Tr("field surgery"),
            "description": Tr("Trained in field surgery: adjacent allies recover up to 8 HP at the start of "
                              "this unit's turn (replaces heals +4). Poison is slowed, not cured."),
        }, adjacent())),
    ]


# --- Weapon specials ---------------------------------------------------------

def firststrike(name: str, flavour: str) -> tuple:
    return node("firststrike", {"id": "sw_rank_firststrike", "name": Tr(name),
                                "description": Tr(f"{flavour} This attack always strikes first, even when defending.")})


def marksman(name: str, flavour: str) -> tuple:
    return node("chance_to_hit", {
        "id": "sw_rank_marksman", "value": 60, "cumulative": "yes", "active_on": "offense", "name": Tr(name),
        "description": Tr(f"{flavour} When attacking, this weapon has at least a 60% chance to hit."),
    })


def slows(name: str, flavour: str) -> tuple:
    return node("slow", {"id": "sw_rank_slow", "name": Tr(name),
                         "description": Tr(f"{flavour} A hit slows the target until it ends a turn: it deals half "
                                           "damage and moves at half speed.")})


def backstab(name: str, flavour: str) -> tuple:
    return node("damage", {
        "id": "sw_rank_backstab", "multiply": 2, "active_on": "offense", "name": Tr(name),
        "description": Tr(f"{flavour} When attacking, this weapon deals double damage if an enemy of the target "
                          "stands on the opposite side of it."),
    # Core backstab's test, guarded: replays and previews evaluate the filter
    # with no opponent, or with no unit behind the target, and an unguarded
    # null raises a formula type error.
    }, node("filter_opponent", {"formula": "if(other = null(), false, "
                                           "if(unit_at(direction_from(loc, other.facing)) = null(), false, "
                                           "enemy_of(self, unit_at(direction_from(loc, other.facing))) and "
                                           "not unit_at(direction_from(loc, other.facing)).petrified))"}))


def drains(name: str, flavour: str) -> tuple:
    return node("drains", {"id": "sw_rank_drains", "value": 50, "name": Tr(name),
                           "description": Tr(f"{flavour} This unit heals itself for half the damage this attack "
                                             "deals.")})


def guard(name: str, flavour: str) -> tuple:
    return node("damage", {"id": "sw_rank_guard", "multiply": 0.5, "apply_to": "opponent", "name": Tr(name),
                           "description": Tr(f"{flavour} While fighting with this weapon, the target's strikes "
                                             "deal half damage.")})


def bane(name: str, flavour: str, movetypes: str, targets: str, pct: int = 50) -> tuple:
    return node("damage", {
        "id": "sw_rank_bane", "multiply": 1 + pct / 100, "name": Tr(name),
        "description": Tr(f"{flavour} This attack deals +{pct}% damage against {targets}."),
    }, node("filter_opponent", {"type": unit_types(movetypes)}))


# --- Catalogue ---------------------------------------------------------------
# key -> (player-facing name, kind, builder). kind "ability" builds one ability,
# "special" a weapon special (with the weapon it goes on, per unit), "effects"
# a list of effects.

ARMOUR = "sw_armored_trooper,sw_walker"
VEHICLES = "sw_walker,sw_repulsor,sw_capital"
CRAFT = "sw_starfighter"
CAPITAL = "sw_capital"

CATALOG = {
    "fire_discipline": ("Fire discipline", "ability", lambda: hit_aura(
        "fire discipline", "Calls targets and keeps the squad's fire steady.", ranged_only=True)),
    "hold_the_line": ("Hold the line", "ability", lambda: steadfast(
        "hold the line", "Has held positions that should have fallen.")),
    "covering_fire": ("Covering fire", "special", lambda: firststrike(
        "covering fire", "Fires first, from long habit.")),
    "jungle_fighter": ("Jungle fighter", "ability", lambda: hides(
        "jungle fighter", "Moves unseen through the trees.", "*^F*", "forest or jungle")),
    "knife_work": ("Knife work", "special", lambda: backstab("knife work", "Strikes where the guard is weakest.")),
    "saboteur": ("Saboteur", "special", lambda: bane(
        "saboteur", "Knows where to place a charge.", VEHICLES, "walkers, speeders and installations")),
    "disciplined": ("Disciplined", "ability", lambda: steadfast(
        "disciplined", "A private army's drill holds under fire.")),
    "marksman_training": ("Marksman training", "special", lambda: marksman(
        "marksman training", "Trained to make the first shot count.")),
    "corellian_tactics": ("Corellian tactics", "ability", lambda: skirmisher(
        "Corellian tactics", "Fights the way the Senator taught: never where the enemy expects.")),
    "dug_in": ("Dug in", "ability", lambda: steadfast("dug in", "A crew that has learned to fortify any position.")),
    "suppressing_fire": ("Suppressing fire", "special", lambda: slows(
        "suppressing fire", "Sustained fire that pins the target down.")),
    "armour_piercing": ("Armour-piercing", "special", lambda: bane(
        "armour-piercing", "Loaded and aimed to punch through plate.", ARMOUR, "armoured troopers and walkers")),
    "field_surgery": ("Field surgery", "effects", field_surgery),
    "field_dressings": ("Field dressings", "ability", lambda: guard_aura(
        "field dressings", "Patches wounds before they can tell.")),
    "rapid_evac": ("Rapid evacuation", "ability", lambda: skirmisher(
        "rapid evacuation", "Reaches the wounded through any gap in the line.")),
    "battle_roar": ("Battle roar", "ability", lambda: fear_aura("battle roar", "A Wookiee roar that shakes the nerve.")),
    "thick_hide": ("Thick hide", "ability", lambda: steadfast("thick hide", "Shrugs off blows that would fell others.")),
    "wookiee_fury": ("Wookiee fury", "special", lambda: drains(
        "Wookiee fury", "Fury keeps the warrior standing.")),
    "sniper_perch": ("Sniper's perch", "special", lambda: marksman(
        "sniper's perch", "Takes the shot from the high branches.")),
    "forest_ghost": ("Forest ghost", "ability", lambda: hides(
        "forest ghost", "Vanishes into the canopy.", "*^F*", "forest or jungle")),
    "pinning_shot": ("Pinning shot", "special", lambda: slows(
        "pinning shot", "A bowcaster quarrel through the leg.")),
    "wingman": ("Wingman", "ability", lambda: hit_aura(
        "wingman", "Calls the break and covers the leader's tail.", craft_only=True)),
    "deflector_shields": ("Tuned deflectors", "ability", lambda: steadfast(
        "tuned deflectors", "Deflector shields tuned by a crew chief who knows this pilot.")),
    "ace": ("Ace", "special", lambda: marksman("ace", "An ace's eye for the deflection shot.")),
    "afterburners": ("Afterburners", "ability", lambda: skirmisher(
        "afterburners", "Too fast to be pinned by escorts.")),
    "dogfighter": ("Dogfighter", "special", lambda: bane(
        "dogfighter", "Lives for the turning fight.", CRAFT, "starfighters and shuttles", 25)),
    "ion_lock": ("Ion lock", "special", lambda: marksman("ion lock", "Holds the ion stream on target.")),
    "armoured_hull": ("Armoured hull", "ability", lambda: steadfast("armoured hull", "Heavy plating, well maintained.")),
    "ship_killer": ("Ship-killer", "special", lambda: bane(
        "ship-killer", "Knows a capital ship's weak points.", CAPITAL, "capital ships and installations")),
    "bombardier": ("Bombardier", "special", lambda: marksman("bombardier", "Releases on target, every time.")),
    "speeder_jockey": ("Speeder jockey", "ability", lambda: skirmisher(
        "speeder jockey", "Threads the speeder between enemy lines.")),
    "strafing": ("Strafing run", "special", lambda: firststrike("strafing run", "Fires before the target can react.")),
    "ramming_speed": ("Ramming speed", "special", lambda: node("damage", {
        "id": "sw_rank_charge", "multiply": 2, "apply_to": "both", "active_on": "offense", "name": Tr("ramming speed"),
        "description": Tr("Hits at full throttle. When attacking, this attack deals double damage, and the "
                          "target's strikes back deal double damage too."),
    })),
    "expert_marksman": ("Expert marksman", "special", lambda: marksman(
        "expert marksman", "An officer who still practices on the range.")),
    "elevated_targeting": ("Elevated targeting", "special", lambda: marksman(
        "elevated targeting", "Lobs grenades from the walker's height.")),
    "stun_mastery": ("Stun mastery", "special", lambda: slows("stun mastery", "Stun bolts placed to disable.")),
    "ghost": ("Ghost", "ability", lambda: skirmisher("ghost", "Passes between guards like smoke.")),
    "death_from_shadows": ("Death from the shadows", "special", lambda: marksman(
        "death from the shadows", "The first blow rarely misses.")),
    "imperial_guard": ("Imperial Guard", "ability", lambda: steadfast(
        "Imperial Guard", "Trained never to yield a step.")),
    "bodyguard": ("Bodyguard", "ability", lambda: guard_aura("bodyguard", "Puts the pike between harm and its charge.")),
    "riposte": ("Riposte", "special", lambda: guard("riposte", "Every thrust turned aside.")),
    "silent_kill": ("Silent kill", "special", lambda: firststrike("silent kill", "Strikes before the guard can.")),
    "stun_setting": ("Stun setting", "special", lambda: slows("stun setting", "Bolts set to disable, not kill.")),
    "reinforced_plating": ("Reinforced plating", "ability", lambda: steadfast(
        "reinforced plating", "Extra plating welded on in the field.")),
    "self_repair": ("Self-repair", "ability", lambda: regenerates(
        "self-repair", "Repair routines patch the hull.", 4)),
    "caustic_spray": ("Caustic spray", "special", lambda: marksman(
        "caustic spray", "A wide, drifting cloud that is hard to dodge.")),
    "quick_draw": ("Quick draw", "special", lambda: firststrike("quick draw", "Clears leather first.")),
    "dirty_fighting": ("Dirty fighting", "special", lambda: backstab(
        "dirty fighting", "Never fights fair if fair can be avoided.")),
    "old_hand": ("Old hand", "ability", lambda: steadfast("old hand", "Has been shot at by better.")),
    "slip_away": ("Slip away", "ability", lambda: skirmisher("slip away", "Gone before anyone looks up.")),
    "overload_shot": ("Overload shot", "special", lambda: slows(
        "overload shot", "A pistol rigged to fry electronics and nerves alike.")),
    "street_camouflage": ("Street camouflage", "ability", lambda: hides(
        "street camouflage", "Just another face in town.", "*^V*", "a village or settlement")),
    "bow_mastery": ("Bow mastery", "special", lambda: marksman("bow mastery", "Hunts with the bow from childhood.")),
    "steady": ("Steady", "ability", lambda: steadfast("steady", "Holds ground against any charge.")),
    "war_cry": ("War cry", "ability", lambda: fear_aura("war cry", "A plains war cry that unnerves the enemy.")),
    "stone_hide": ("Stone hide", "ability", lambda: steadfast("stone hide", "A hide like rock.")),
    "crushing_blow": ("Crushing blow", "special", lambda: slows("crushing blow", "Blows that stagger.")),
    "recuperation": ("Recuperation", "ability", lambda: regenerates(
        "recuperation", "Heals fast, as its people do.", 4)),
    # Heroes (each adds to the hero's own specialization choices, never repeats them).
    "jedi_reflexes": ("Jedi reflexes", "ability", lambda: skirmisher(
        "Jedi reflexes", "The Force shows the gaps in the line.")),
    "lightsaber_form": ("Lightsaber form", "special", lambda: firststrike(
        "lightsaber form", "A Jedi's guard that moves before the enemy's blade.")),
    "jedi_serenity": ("Jedi serenity", "ability", lambda: steadfast("Jedi serenity", "Calm at the centre of battle.")),
    "rally": ("Rally", "ability", lambda: hit_aura(
        "rally", "Her voice steadies every gun around her.", ranged_only=True)),
    "force_intuition": ("Force intuition", "ability", lambda: skirmisher(
        "Force intuition", "Senses where the enemy is not.")),
    "trick_shot": ("Trick shot", "special", lambda: marksman("trick shot", "Shots no one else would try.")),
    "smugglers_nerve": ("Smuggler's nerve", "ability", lambda: steadfast("smuggler's nerve", "Has seen worse odds.")),
    "fearless": ("Fearless", "ability", lambda: hit_aura(
        "fearless", "Never tells anyone the odds.", ranged_only=True)),
    "wookiee_recovery": ("Wookiee recovery", "ability", lambda: regenerates(
        "Wookiee recovery", "Wookiees heal astonishingly fast.", 8)),
    "gamblers_nerve": ("Gambler's nerve", "ability", lambda: steadfast(
        "gambler's nerve", "Plays every hand as if it were a winning one.")),
    "emperors_hand": ("Emperor's Hand", "special", lambda: firststrike(
        "Emperor's Hand", "Training for the deadliest of duels.")),
    "hardened": ("Hardened", "ability", lambda: steadfast("hardened", "Years alone have made her hard to break.")),
    "assassin": ("Assassin", "special", lambda: backstab("assassin", "The blow from behind.")),
    "old_fox": ("Old fox", "ability", lambda: steadfast("old fox", "Never where he can be cornered.")),
    "contingency": ("Contingency plan", "ability", lambda: skirmisher(
        "contingency plan", "There is always a back way out.")),
    "clan_honour": ("Clan honour", "special", lambda: marksman(
        "clan honour", "Fights to restore his clan's honour.")),
    "veteran_commander": ("Veteran commander", "ability", lambda: steadfast(
        "veteran commander", "Has outlasted every war he fought.")),
}

# Unit type -> {rank: (catalogue key, weapon for specials or None)}.
NCO = {1: ("fire_discipline", None), 2: ("hold_the_line", None), 3: ("covering_fire", "blaster_rifle")}
FIGHTER = {1: ("wingman", None), 2: ("dogfighter", "laser_cannons"), 3: ("ace", "laser_cannons")}
ASSIGNMENTS = {
    "sw_unit_nr_sergeant": NCO,
    "sw_unit_im_stormtrooper_sergeant": NCO,
    "sw_unit_nr_commando": {1: ("jungle_fighter", None), 2: ("knife_work", "vibroknife"),
                            3: ("saboteur", "blaster_carbine")},
    "sw_unit_bi_commando": {1: ("disciplined", None), 2: ("marksman_training", "blaster_rifle"),
                            3: ("corellian_tactics", None)},
    "sw_unit_nr_eweb_team": {1: ("dug_in", None), 2: ("suppressing_fire", "eweb_repeater"),
                             3: ("armour_piercing", "eweb_repeater")},
    "sw_unit_nr_field_medic": {1: ("field_surgery", None), 2: ("field_dressings", None), 3: ("rapid_evac", None)},
    "sw_unit_wk_suppressor": {1: ("thick_hide", None), 2: ("covering_fire", "bowcaster"),
                              3: ("fire_discipline", None)},
    "sw_unit_wk_warrior": {1: ("battle_roar", None), 2: ("thick_hide", None), 3: ("wookiee_fury", "ryyk_blade")},
    "sw_unit_wk_lookout": {1: ("sniper_perch", "bowcaster"), 2: ("forest_ghost", None),
                           3: ("pinning_shot", "bowcaster")},
    "sw_unit_nr_xwing": {1: ("wingman", None), 2: ("deflector_shields", None), 3: ("ace", "laser_cannons")},
    "sw_unit_nr_awing": {1: ("wingman", None), 2: ("dogfighter", "laser_cannons"),
                         3: ("ace", "laser_cannons")},
    "sw_unit_nr_ywing": {1: ("ion_lock", "ion_cannon"), 2: ("armoured_hull", None),
                         3: ("ship_killer", "proton_torpedoes")},
    "sw_unit_im_tie_fighter": FIGHTER,
    "sw_unit_im_tie_interceptor": {1: ("afterburners", None), 2: ("dogfighter", "laser_cannons"),
                                   3: ("ace", "laser_cannons")},
    "sw_unit_im_tie_bomber": {1: ("bombardier", "concussion_bombs"), 2: ("armoured_hull", None),
                              3: ("ship_killer", "concussion_bombs")},
    "sw_unit_im_scout_trooper": {1: ("speeder_jockey", None), 2: ("strafing", "bike_blaster"),
                                 3: ("ramming_speed", "ram")},
    "sw_unit_im_officer": {1: ("fire_discipline", None), 2: ("hold_the_line", None),
                           3: ("expert_marksman", "blaster_pistol")},
    "sw_unit_im_at_st": {1: ("armoured_hull", None), 2: ("suppressing_fire", "twin_blaster_cannon"),
                         3: ("elevated_targeting", "concussion_grenade")},
    "sw_unit_im_noghri": {1: ("stun_mastery", "stun_blaster"), 2: ("ghost", None),
                          3: ("death_from_shadows", "noghri_knives")},
    "sw_unit_im_royal_guard": {1: ("imperial_guard", None), 2: ("bodyguard", None), 3: ("riposte", "force_pike")},
    "sw_unit_im_infiltrator": {1: ("ghost", None), 2: ("stun_setting", "blaster_pistol"),
                               3: ("silent_kill", "vibroknife")},
    "sw_unit_im_decon_droid": {1: ("reinforced_plating", None), 2: ("self_repair", None),
                               3: ("caustic_spray", "sprayer")},
    "sw_unit_sm_veteran": {1: ("quick_draw", "blaster_pistol"), 2: ("dirty_fighting", "vibroknife"),
                           3: ("old_hand", None)},
    "sw_unit_sm_slicer": {1: ("slip_away", None), 2: ("overload_shot", "blaster_pistol"),
                          3: ("street_camouflage", None)},
    "sw_unit_wy_myneyrshi": {1: ("bow_mastery", "bow"), 2: ("steady", None), 3: ("war_cry", None)},
    "sw_unit_wy_field_medic": {1: ("forest_ghost", None), 2: ("field_surgery", None), 3: ("rapid_evac", None)},
    "sw_unit_wy_psadan": {1: ("stone_hide", None), 2: ("crushing_blow", "war_club"), 3: ("recuperation", None)},
    # Heroes.
    "sw_hero_luke": {1: ("jedi_reflexes", None), 2: ("lightsaber_form", "lightsaber"), 3: ("jedi_serenity", None)},
    "sw_hero_xwing_luke": {1: ("wingman", None), 2: ("deflector_shields", None), 3: ("ace", "laser_cannons")},
    "sw_hero_leia": {1: ("rally", None), 2: ("hold_the_line", None), 3: ("force_intuition", None)},
    "sw_hero_han": {1: ("trick_shot", "heavy_blaster_pistol"), 2: ("smugglers_nerve", None), 3: ("fearless", None)},
    "sw_hero_chewbacca": {1: ("battle_roar", None), 2: ("thick_hide", None), 3: ("wookiee_recovery", None)},
    "sw_hero_lando": {1: ("gamblers_nerve", None), 2: ("fire_discipline", None),
                      3: ("expert_marksman", "blaster_pistol")},
    "sw_hero_mara": {1: ("emperors_hand", "vibroblade"), 2: ("hardened", None), 3: ("assassin", "vibroblade")},
    "sw_hero_karrde": {1: ("old_fox", None), 2: ("fire_discipline", None), 3: ("contingency", None)},
    "sw_hero_wedge": {1: ("wingman", None), 2: ("deflector_shields", None), 3: ("ace", "laser_cannons")},
    "sw_hero_khabarakh": {1: ("stun_mastery", "stun_blaster"), 2: ("silent_kill", "noghri_knives"),
                          3: ("clan_honour", "noghri_knives")},
    "sw_hero_bel_iblis": {1: ("veteran_commander", None), 2: ("fire_discipline", None),
                          3: ("corellian_tactics", None)},
}
RANK_LABELS = {1: "Veteran", 2: "Seasoned veteran", 3: "Elite"}


def effects_for(unit: dict, key: str, weapon: str | None, expanded: list[dict]) -> list:
    _label, kind, build = CATALOG[key]
    if kind == "effects":
        assert weapon is None, key
        return build()
    if kind == "ability":
        assert weapon is None, key
        return [new_ability(build())]
    names = [a["name"] for a in expanded if a["name"] in {weapon, weapon + "_aimed"}]
    assert names, f"{unit['id']}: rank special {key} needs weapon {weapon}"
    special = build()
    for a in unit["attacks"]:
        if a["name"] == weapon:
            existing = {s for s in a.get("specials", [])}
            # Never give a weapon a special it already has under its own name.
            assert not ({"firststrike": "firststrike", "chance_to_hit": "marksman", "slow": "slow",
                         "drains": "drains"}.get(special[0]) in existing), f"{unit['id']}/{weapon}: {key} duplicates"
    return [node("effect", {"apply_to": "attack", "name": ",".join(names)},
                 node("set_specials", {"mode": "append"}, special))]


# What each rank ability does, for the unit's help page: the ability's own
# description without its opening flavour sentence. "effects" entries have no
# description of their own.
EFFECT_TEXT = {
    "field_surgery": "Heals adjacent allies 8 HP each turn instead of 4.",
}


def effect_text(key: str) -> str:
    if key in EFFECT_TEXT:
        return EFFECT_TEXT[key]
    built = CATALOG[key][2]()
    text = str(built[1]["description"])
    _flavour, _sep, rules = text.partition(". ")
    return rules or text


def description_suffix(unit_id: str) -> str:
    """Rank abilities listed with what they do, one line each."""
    ranks = ASSIGNMENTS.get(unit_id)
    if not ranks:
        return ""
    lines = []
    for n in sorted(ranks):
        key, weapon = ranks[n]
        name = CATALOG[key][0]
        where = f" ({weapon.replace('_', ' ')})" if weapon else ""
        lines.append(f"• {RANK_LABELS[n]} — {name}{where}: {effect_text(key)}")
    return "\n\nRank abilities, gained as the unit rises in rank:\n" + "\n".join(lines)


# --- Lua output --------------------------------------------------------------

def _lua_value(v) -> str:
    if isinstance(v, Tr):
        return '_ "' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _lua_node(n: tuple, depth: int) -> str:
    tag, attrs, children = n
    pad = "\t" * (depth + 1)
    parts = [f"{pad}{k} = {_lua_value(v)}," for k, v in attrs.items()]
    parts += [_lua_node(c, depth + 1) + "," for c in children]
    inner = "\n".join(parts)
    return ("\t" * depth) + f"T.{tag} {{\n{inner}\n" + ("\t" * depth) + "}" if parts else ("\t" * depth) + f"T.{tag} {{}}"


def lua(roster: list[dict], expanded_attacks) -> str:
    by_id = {u["id"]: u for u in roster}
    out = [
        "-- Generated by production/tools/gen_hte_units.py from production/tools/rank_abilities.py: do not edit.",
        "-- Rank abilities per unit type (lua/sw_rank.lua): rank -> { key, name, effects }.",
        'local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")',
        "local T = wml.tag",
        "return {",
    ]
    for uid, ranks in ASSIGNMENTS.items():
        unit = by_id[uid]
        assert unit["advances"] is None, f"{uid} promotes; its rank abilities belong to the promoted type"
        out.append(f"\t{uid} = {{")
        for n in sorted(ranks):
            key, weapon = ranks[n]
            effects = effects_for(unit, key, weapon, expanded_attacks(unit))
            body = ",\n".join(_lua_node(e, 4) for e in effects)
            out.append(f'\t\t[{n}] = {{ key = "{key}", name = {_lua_value(Tr(CATALOG[key][0]))}, effects = {{\n'
                       f"{body},\n\t\t\t}} }},")
        out.append("\t},")
    out.append("}")
    return "\n".join(out) + "\n"
