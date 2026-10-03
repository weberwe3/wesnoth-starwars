-- Star Wars: Thrawn Trilogy -- overwatch / reaction fire.
--
-- A unit capable of overwatch carries
--   [dummy] id=sw_ability_overwatch reactions=1 range=2 weapons=blaster_rifle
--           accuracy=-10 damage=100 arc=all commit_moves=yes [/dummy]
-- (all attributes optional; weapons defaults to the unit's ranged attacks).
-- Entering overwatch commits the unit's attack for the turn. Until the start
-- of its side's next turn, an enemy that enters a hex within range, visible to
-- the shooter's side and inside the firing arc draws a reaction volley.
--
-- State (unit variables): sw_ow_active, sw_ow_shots (reactions left),
-- sw_ow_range, sw_ow_weapon, sw_ow_accuracy, sw_ow_damage, sw_ow_arc,
-- sw_ow_facing, sw_ow_fired (per-target duplicate guard), sw_move_serial
-- (bumped on every completed move). Index: WML array sw_ow_index (ids of
-- units on overwatch) so a moving unit only checks active watchers.

local T = wml.tag
local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local force = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_force.lua")
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local ow = {}
ow.ABILITY = "sw_ability_overwatch"

-- Extension hooks (each may veto or modify; empty by default). Future
-- suppression, cover, cloaking/detection and command bonuses plug in here.
--   can_react(shooter, target) -> bool        (false vetoes the reaction)
--   modify(shooter, target, shot) -> nil       (adjust shot.accuracy/.damage)
ow.hooks = { can_react = {}, modify = {} }

-- Reentrancy guard: while a reaction resolves, any event it causes (death,
-- scenario scripts) cannot start another reaction.
ow.resolving = false

-- ---------------------------------------------------------------- config

function ow.config(u)
	local cfg = core.ability_cfg(u, ow.ABILITY)
	if not cfg then return nil end
	local weapons = core.split(cfg.weapons)
	if #weapons == 0 then
		for _i, a in ipairs(u.attacks) do
			if a.range == "ranged" then table.insert(weapons, a.name) end
		end
	end
	return {
		reactions = core.number(cfg.reactions, 1),
		range = core.number(cfg.range, 2),
		weapons = weapons,
		accuracy = core.number(cfg.accuracy, -10),
		damage = core.number(cfg.damage, 100),
		arc = cfg.arc or "all",
		commit_moves = cfg.commit_moves ~= false and cfg.commit_moves ~= "no",
	}
end

local function find_attack(u, names)
	for _i, name in ipairs(names) do
		for _i, a in ipairs(u.attacks) do
			if a.name == name then return a end
		end
	end
	return nil
end

-- ---------------------------------------------------------------- index

local function index_ids()
	local ids = {}
	for _i, e in ipairs(wml.array_access.get("sw_ow_index")) do table.insert(ids, e.id) end
	table.sort(ids)
	return ids
end

local function index_set(ids)
	local arr = {}
	table.sort(ids)
	for _i, id in ipairs(ids) do table.insert(arr, { id = id }) end
	wml.array_access.set("sw_ow_index", arr)
end

-- ---------------------------------------------------------------- enter / clear

function ow.can_enter(u)
	local cfg = ow.config(u)
	if not cfg then return false, _ "cannot hold overwatch" end
	if u.variables.sw_ow_active then return false, _ "already on overwatch" end
	if u.attacks_left < 1 then return false, _ "no attack left" end
	if force.is_dazed(u) then return false, _ "dazed" end
	if not find_attack(u, cfg.weapons) then return false, _ "no suitable weapon" end
	return true, nil, cfg
end

function ow.enter(u)
	local ok, why, cfg = ow.can_enter(u)
	if not ok then core.log("overwatch", u.id .. " cannot enter: " .. tostring(why)) return false end
	local weapon = find_attack(u, cfg.weapons)
	u.attacks_left = 0
	if cfg.commit_moves then u.moves = 0 end
	u.variables.sw_ow_active = true
	u.variables.sw_ow_shots = cfg.reactions
	u.variables.sw_ow_range = cfg.range
	u.variables.sw_ow_weapon = weapon.name
	u.variables.sw_ow_accuracy = cfg.accuracy
	u.variables.sw_ow_damage = cfg.damage
	u.variables.sw_ow_arc = cfg.arc
	u.variables.sw_ow_facing = u.facing
	u.variables.sw_ow_fired = nil
	local ids = index_ids()
	table.insert(ids, u.id)
	index_set(ids)
	ow.update_indicator(u)
	core.float(u.x, u.y, _ "overwatch", "#ffd27a")
	core.log("overwatch", u.id .. " on overwatch: " .. cfg.reactions .. " reaction(s), range " .. cfg.range)
	if ow.on_enter then ow.on_enter(u) end   -- observation hook (Thrawn Doctrine)
	return true
end

function ow.clear(u)
	if not u.variables.sw_ow_active then return end
	for _i, k in ipairs{ "sw_ow_active", "sw_ow_shots", "sw_ow_range", "sw_ow_weapon", "sw_ow_accuracy",
			"sw_ow_damage", "sw_ow_arc", "sw_ow_facing", "sw_ow_fired" } do
		u.variables[k] = nil
	end
	local ids = {}
	for _i, id in ipairs(index_ids()) do if id ~= u.id then table.insert(ids, id) end end
	index_set(ids)
	core.set_overlay(u, "overwatch", nil)
end

function ow.update_indicator(u)
	local shots = core.number(u.variables.sw_ow_shots, 0)
	if u.variables.sw_ow_active and shots > 0 then
		core.set_overlay(u, "overwatch", "misc/sw-overwatch-" .. math.min(shots, 3) .. ".png")
	else
		core.set_overlay(u, "overwatch", nil)
	end
end

-- Overwatch lasts until the start of its side's next turn (no stale state).
function ow.on_side_turn(side)
	for _i, id in ipairs(index_ids()) do
		local u = wesnoth.units.get(id)
		if not u then
			-- Unit died or left the map: drop it from the index.
			local ids = {}
			for _i, other in ipairs(index_ids()) do if other ~= id then table.insert(ids, other) end end
			index_set(ids)
		elseif u.side == side then
			ow.clear(u)
		end
	end
end

-- ---------------------------------------------------------------- reaction

local ARCS = {
	-- Directions within the arc relative to the facing direction.
	front = 1,   -- facing direction and its two neighbours
	all = 3,
}

local DIRS = { "n", "ne", "se", "s", "sw", "nw" }
local function dir_index(d)
	for i, v in ipairs(DIRS) do if v == d then return i end end
	return 1
end

function ow.in_arc(shooter, target)
	local arc = shooter.variables.sw_ow_arc or "all"
	if arc == "all" then return true end
	local facing = dir_index(shooter.variables.sw_ow_facing or shooter.facing)
	local toward = dir_index(wesnoth.map.get_relative_dir({ shooter.x, shooter.y }, { target.x, target.y }))
	local diff = math.abs(facing - toward)
	diff = math.min(diff, 6 - diff)
	return diff <= (ARCS[arc] or 3)
end

-- Every rule a reaction must pass, in order. Returns ok, reason.
function ow.eligible(shooter, target)
	if not shooter.variables.sw_ow_active then return false, "not on overwatch" end
	if core.number(shooter.variables.sw_ow_shots, 0) < 1 then return false, "no reactions left" end
	if shooter.hitpoints <= 0 then return false, "dead" end
	if not wesnoth.sides.is_enemy(shooter.side, target.side) then return false, "not an enemy" end
	if force.is_dazed(shooter) then return false, "dazed" end
	if shooter.status.petrified or shooter.status.stunned then return false, "disabled" end
	local dist = wesnoth.map.distance_between(shooter.x, shooter.y, target.x, target.y)
	if dist > core.number(shooter.variables.sw_ow_range, 1) then return false, "out of range" end
	if not ow.in_arc(shooter, target) then return false, "outside firing arc" end
	-- Visibility: the shooter's side must see the hex and the unit. Hidden
	-- (stealthed, cloaked) units cannot be targeted -- the cloaking hook.
	if wesnoth.sides.is_fogged(shooter.side, { x = target.x, y = target.y }) then return false, "fogged" end
	if not target:matches{ T.filter_vision{ side = shooter.side, visible = true } } then return false, "not visible" end
	local serial = core.number(target.variables.sw_move_serial, 0)
	if shooter.variables.sw_ow_fired == target.id .. "#" .. serial then return false, "already fired this move" end
	for _i, hook in ipairs(ow.hooks.can_react) do
		if not hook(shooter, target) then return false, "vetoed by hook" end
	end
	return true
end

-- Resolve one volley. Precedence: (1) eligibility, (2) the target's reactive
-- Force deflection, (3) hit rolls on the synced RNG, (4) damage and death.
function ow.resolve(shooter, target)
	local weapon = find_attack(shooter, { shooter.variables.sw_ow_weapon })
	if not weapon then return end
	shooter.variables.sw_ow_shots = core.number(shooter.variables.sw_ow_shots, 1) - 1
	shooter.variables.sw_ow_fired = target.id .. "#" .. core.number(target.variables.sw_move_serial, 0)
	ow.update_indicator(shooter)
	core.float(shooter.x, shooter.y, _ "reaction fire", "#ffd27a")
	if force.try_deflect(target, shooter) then
		wesnoth.wml_actions.animate_unit{ flag = "attack", hits = false,
			T.filter{ id = shooter.id }, T.primary_attack{ name = weapon.name },
			T.facing{ x = target.x, y = target.y },
			T.animate{ flag = "defend", hits = false, T.filter{ id = target.id } } }
		return
	end
	local shot = {
		accuracy = core.number(shooter.variables.sw_ow_accuracy, 0),
		damage = math.max(1, math.floor(weapon.damage * core.number(shooter.variables.sw_ow_damage, 100) / 100 + 0.5)),
		strikes = weapon.number,
	}
	for _i, hook in ipairs(ow.hooks.modify) do hook(shooter, target, shot) end
	local chance = math.max(0, math.min(100, 100 - target:defense_on({ x = target.x, y = target.y }) + shot.accuracy))
	local hits = 0
	for _n = 1, shot.strikes do
		if mathx.random(1, 100) <= chance then hits = hits + 1 end
	end
	core.log("overwatch", shooter.id .. " fires at " .. target.id .. ": " .. hits .. "/" .. shot.strikes ..
		" at " .. chance .. "%, " .. shot.damage .. " each")
	if hits == 0 then
		wesnoth.wml_actions.animate_unit{ flag = "attack", hits = false,
			T.filter{ id = shooter.id }, T.primary_attack{ name = weapon.name },
			T.facing{ x = target.x, y = target.y },
			T.animate{ flag = "defend", hits = false, T.filter{ id = target.id } } }
		core.float(target.x, target.y, _ "miss", "#cccccc")
		return
	end
	wesnoth.wml_actions.harm_unit{
		T.filter{ id = target.id }, T.filter_second{ id = shooter.id },
		amount = shot.damage * hits, damage_type = weapon.type, alignment = shooter.alignment,
		kill = true, fire_event = true, animate = true, experience = true,
		T.primary_attack{ name = weapon.name },
	}
end

-- enter_hex handler: the moving unit just entered (x1, y1).
function ow.on_enter_hex()
	if ow.resolving then return end
	local ctx = wesnoth.current.event_context
	local mover = wesnoth.units.get(ctx.x1, ctx.y1)
	if not mover then return end
	local ids = index_ids()
	if #ids == 0 then return end
	local reacted = false
	ow.resolving = true
	local ok, err = pcall(function()
		for _i, id in ipairs(ids) do
			local shooter = wesnoth.units.get(id)
			local target = wesnoth.units.get(ctx.x1, ctx.y1)
			if not target or target.id ~= mover.id then break end -- target died
			if shooter then
				local can, why = ow.eligible(shooter, target)
				if can then
					ow.resolve(shooter, target)
					reacted = true
				else
					core.log("overwatch", id .. " holds fire on " .. mover.id .. ": " .. why)
				end
			end
		end
	end)
	ow.resolving = false
	if not ok then error(err) end
	-- Reaction fire pauses the move. A survivor keeps its remaining movement
	-- points and may continue with a new move order (engine limitation:
	-- an interrupted move cannot be resumed automatically).
	if reacted and wesnoth.units.get(ctx.x1, ctx.y1) then
		wesnoth.wml_actions.cancel_action{}
	end
end

-- Completed moves get a new serial, so a watcher may fire again at the same
-- unit on its next move order but never twice during one.
function ow.on_moveto()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if u then u.variables.sw_move_serial = core.number(u.variables.sw_move_serial, 0) + 1 end
end

-- Units disabled by Mind Trick (or future suppression) lose overwatch.
force.on_disabled = function(u) ow.clear(u) end

-- AI sides: units that kept their attack enter overwatch at the end of the
-- side's turn, so the AI uses the system too. Disable with
-- sw_overwatch_ai=no.
function ow.on_side_turn_end(side)
	if wml.variables.sw_overwatch_ai == false or wml.variables.sw_overwatch_ai == "no" then return end
	if wesnoth.sides[side].controller ~= "ai" then return end
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ side = side, ability = ow.ABILITY })) do
		if ow.can_enter(u) then ow.enter(u) end
	end
end

-- ---------------------------------------------------------------- menu

function ow.menu_visible()
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	return u ~= nil and core.is_local_turn_of(u.side) and ow.config(u) ~= nil and (ow.can_enter(u))
end

function ow.menu_command()
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if u then ow.enter(u) end
end

return ow
