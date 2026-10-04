-- Star Wars: Thrawn Trilogy -- Force system.
--
-- Force-sensitive units carry an ability
--   [dummy] id=sw_ability_force fp_max=8 fp_regen=2 powers=push,pull,speed,sense,deflection [/dummy]
-- Optional per-unit overrides: cost_<power>=, range_<power>=, cooldown_<power>=.
-- State (unit variables): sw_fp (current Force Points), sw_cd_<power> (turns of
-- cooldown left), sw_used_<power> (turn the power was last used, for once-per-
-- turn powers), sw_dazed_turn (Mind Trick), sw_sensed_until (Force Sense).
--
-- Ysalamiri null fields: static sources in the WML array sw_force_null_sources
-- (x, y, radius), plus every unit with [dummy] id=sw_ability_ysalamiri radius=N
-- (the field moves with its carrier). The union is kept in the WML array
-- sw_ysalamiri_zone so declarative WML filters (find_in=sw_ysalamiri_zone)
-- stay in step with it.

local T = wml.tag
local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local force = {}

force.ABILITY = "sw_ability_force"
force.YSALAMIRI = "sw_ability_ysalamiri"
force.DEFAULT_FIELD_RADIUS = 2
force.FP_ICON_MAX = 10

-- Power registry. Every power is data plus functions, so new light-side,
-- dark-side or character powers are added with force.register_power(id, def)
-- without touching the menu, cost or suppression logic.
--   target: "self", "enemy", "ally", or "any_unit"
--   per_turn: usable once per turn; cooldown: turns before it can be used again
--   valid(caster, target, power): extra target filter (true or false, reason)
--   apply(caster, target, power): the effect
--   passive: not shown in the menu (used reactively, e.g. deflection)
force.powers = {}
force.power_order = {}

function force.register_power(id, def)
	def.id = id
	force.powers[id] = def
	table.insert(force.power_order, id)
end

-- ---------------------------------------------------------------- config / state

function force.config(u)
	local cfg = core.ability_cfg(u, force.ABILITY)
	if not cfg then return nil end
	return {
		fp_max = core.number(cfg.fp_max, 6),
		fp_regen = core.number(cfg.fp_regen, 1),
		powers = core.split(cfg.powers),
		raw = cfg,
	}
end

function force.power_value(u, cfg, power, field)
	return core.number(cfg.raw[field .. "_" .. power.id], power[field])
end

function force.is_sensitive(u)
	return core.has_ability(u, force.ABILITY)
end

function force.fp(u)
	return core.number(u.variables.sw_fp, 0)
end

function force.set_fp(u, value, cfg)
	cfg = cfg or force.config(u)
	if not cfg then return end
	value = math.max(0, math.min(cfg.fp_max, value))
	u.variables.sw_fp = value
	force.update_indicator(u, cfg)
end

function force.init_unit(u)
	local cfg = force.config(u)
	if cfg and u.variables.sw_fp == nil then
		force.set_fp(u, cfg.fp_max, cfg)
	end
end

-- ---------------------------------------------------------------- null fields

-- Lua-side cache of the null field, keyed "x,y". It is rebuilt lazily from
-- the saved WML array sw_ysalamiri_zone, so it is correct after a load
-- without recomputation.
force.null_set = nil

local function null_cache()
	if force.null_set == nil then
		local set = {}
		for _i, loc in ipairs(wml.array_access.get("sw_ysalamiri_zone")) do set[core.key(loc.x, loc.y)] = true end
		force.null_set = set
	end
	return force.null_set
end

local function add_radius(set, list, x, y, radius)
	for _i, loc in ipairs(wesnoth.map.find{ x = x, y = y, radius = radius }) do
		local k = core.key(loc.x, loc.y)
		if not set[k] then
			set[k] = true
			table.insert(list, { x = loc.x, y = loc.y })
		end
	end
end

-- Static sources belong to the mission that placed them. WML variables carry
-- over between campaign scenarios, so sources stamped with another scenario's
-- id are discarded (a field from HTE 5 must not appear in HTE 6).
function force.ensure_scenario()
	local id = core.scenario_id()
	if wml.variables.sw_force_null_scenario ~= id then
		wml.array_access.set("sw_force_null_sources", {})
		wml.variables.sw_force_null_scenario = id
		force.null_set = nil
	end
end

function force.add_static_source(x, y, radius)
	force.ensure_scenario()
	local sources = wml.array_access.get("sw_force_null_sources")
	table.insert(sources, { x = x, y = y, radius = radius })
	wml.array_access.set("sw_force_null_sources", sources)
	force.refresh_fields()
end

function force.is_suppressed_at(x, y)
	return null_cache()[core.key(x, y)] == true
end

function force.is_suppressed(u)
	return force.is_suppressed_at(u.x, u.y)
end

-- Rebuild the null set from sources and carriers, redraw the field and the
-- suppression indicators. Called after anything that can move a source or a
-- Force user: every move, displacement, death, placement and turn start.
function force.refresh_fields()
	force.ensure_scenario()
	local set, list = {}, {}
	for _i, src in ipairs(wml.array_access.get("sw_force_null_sources")) do
		add_radius(set, list, src.x, src.y, core.number(src.radius, force.DEFAULT_FIELD_RADIUS))
	end
	for _i, carrier in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ ability = force.YSALAMIRI })) do
		if carrier.hitpoints > 0 then
			local cfg = core.ability_cfg(carrier, force.YSALAMIRI) or {}
			add_radius(set, list, carrier.x, carrier.y, core.number(cfg.radius, force.DEFAULT_FIELD_RADIUS))
		end
	end
	table.sort(list, function(a, b) if a.x ~= b.x then return a.x < b.x end return a.y < b.y end)
	force.null_set = set
	wml.array_access.set("sw_ysalamiri_zone", list)
	-- Redraw the field tint: remove hexes no longer covered, add new ones.
	local drawn = {}
	for _i, loc in ipairs(wml.array_access.get("sw_force_null_drawn")) do
		if not set[core.key(loc.x, loc.y)] then
			wesnoth.interface.remove_item(loc.x, loc.y, "misc/sw-ysalamiri-zone.png")
		else
			drawn[core.key(loc.x, loc.y)] = true
		end
	end
	for _i, loc in ipairs(list) do
		if not drawn[core.key(loc.x, loc.y)] then
			wesnoth.interface.add_item_image(loc.x, loc.y, "misc/sw-ysalamiri-zone.png")
		end
	end
	wml.array_access.set("sw_force_null_drawn", list)
	for _i, u in ipairs(wesnoth.units.find_on_map{ ability = force.ABILITY }) do
		force.update_indicator(u)
	end
	core.log("force", "null field refreshed: " .. #list .. " hexes")
end

-- Force Points pips, or the suppression icon while inside a null field.
function force.update_indicator(u, cfg)
	cfg = cfg or force.config(u)
	if not cfg then return end
	if force.is_suppressed(u) then
		core.set_overlay(u, "force", "misc/sw-force-suppressed.png")
	else
		local fp = math.max(0, math.min(force.FP_ICON_MAX, force.fp(u)))
		core.set_overlay(u, "force", "misc/sw-fp-" .. fp .. ".png")
	end
end

-- ---------------------------------------------------------------- availability

-- Whether a unit can use a power now, and why not. Precedence: suppression,
-- Force Points, once-per-turn, cooldown -- the first failing rule is reported.
function force.can_use(u, power_id, cfg)
	cfg = cfg or force.config(u)
	local power = force.powers[power_id]
	if not cfg or not power then return false, _ "unknown power" end
	local has = false
	for _i, p in ipairs(cfg.powers) do if p == power_id then has = true end end
	if not has then return false, _ "not known to this unit" end
	if force.is_suppressed(u) then return false, _ "suppressed by a ysalamiri" end
	local cost = force.power_value(u, cfg, power, "cost")
	if force.fp(u) < cost then return false, _ "not enough Force Points" end
	if power.per_turn and core.number(u.variables["sw_used_" .. power_id], -1) == wesnoth.current.turn then
		return false, _ "already used this turn"
	end
	local cd = core.number(u.variables["sw_cd_" .. power_id], 0)
	if cd > 0 then return false, _ "recovering" end
	if power.needs_action and u.attacks_left < 1 then return false, _ "no action left" end
	return true
end

-- Targets in range that pass the power's rules, in a stable order.
function force.valid_targets(caster, power_id, cfg)
	cfg = cfg or force.config(caster)
	local power = force.powers[power_id]
	if power.target == "self" then return { caster } end
	local range = force.power_value(caster, cfg, power, "range")
	local out = {}
	for _i, t in ipairs(wesnoth.units.find_on_map{ T.filter_location{ x = caster.x, y = caster.y, radius = range } }) do
		local ok = t.id ~= caster.id
		if ok and power.target == "enemy" then ok = wesnoth.sides.is_enemy(caster.side, t.side) end
		if ok and power.target == "ally" then ok = not wesnoth.sides.is_enemy(caster.side, t.side) end
		-- A ysalamiri pushes the Force away: nothing inside a null field can
		-- be reached by a Force power either.
		if ok then ok = not force.is_suppressed(t) end
		if ok then ok = t:matches{ T.filter_vision{ side = caster.side, visible = true } } end
		if ok and power.valid then ok = power.valid(caster, t, power, cfg) end
		if ok then table.insert(out, t) end
	end
	table.sort(out, function(a, b)
		local da = wesnoth.map.distance_between(caster.x, caster.y, a.x, a.y)
		local db = wesnoth.map.distance_between(caster.x, caster.y, b.x, b.y)
		if da ~= db then return da < db end
		return a.id < b.id
	end)
	return out
end

-- Spend, apply, record. Returns true if the power took effect.
function force.use(caster, power_id, target)
	local cfg = force.config(caster)
	local ok, why = force.can_use(caster, power_id, cfg)
	if not ok then core.log("force", caster.id .. " cannot use " .. power_id .. ": " .. tostring(why)) return false end
	local power = force.powers[power_id]
	local cost = force.power_value(caster, cfg, power, "cost")
	force.set_fp(caster, force.fp(caster) - cost, cfg)
	if power.per_turn then caster.variables["sw_used_" .. power_id] = wesnoth.current.turn end
	local cooldown = force.power_value(caster, cfg, power, "cooldown")
	if cooldown and cooldown > 0 then caster.variables["sw_cd_" .. power_id] = cooldown end
	if power.needs_action then caster.attacks_left = 0 end
	core.log("force", caster.id .. " uses " .. power_id .. " on " .. (target and target.id or "-") .. " (cost " .. cost .. ")")
	power.apply(caster, target, power, cfg)
	force.refresh_fields()
	if force.on_power_used then force.on_power_used(caster, power_id) end   -- observation hook
	return true
end

-- ---------------------------------------------------------------- displacement

-- Move a unit one hex in a direction if the destination is on the map, empty
-- and passable for it. Displacement never fires move events, so it cannot
-- trigger objectives, overwatch or other reactions (documented precedence).
function force.displace(u, dir)
	local dest = wesnoth.map.get_direction({ u.x, u.y }, dir)
	local x, y = dest[1] or dest.x, dest[2] or dest.y
	if not wesnoth.current.map:on_board(x, y) then return false, "edge" end
	if wesnoth.units.get(x, y) then return false, "occupied" end
	if u:movement_on({ x = x, y = y }) >= 99 then return false, "impassable" end
	u:to_map(x, y)
	return true
end

-- ---------------------------------------------------------------- powers

force.register_power("push", {
	name = _ "Force Push", cost = 2, range = 2, cooldown = 1, target = "enemy", needs_action = true,
	description = _ "Hurl an enemy one hex straight away from you. If a unit, a wall or the edge of the battlefield is in the way, it slams into it for 6 impact damage and stays where it is.",
	slam_damage = 6,
	apply = function(caster, target, power)
		local dir = wesnoth.map.get_relative_dir({ caster.x, caster.y }, { target.x, target.y })
		local moved = force.displace(target, dir)
		if moved then
			core.float(target.x, target.y, _ "pushed", "#a8c8ff")
		else
			wesnoth.wml_actions.harm_unit{ T.filter{ id = target.id }, T.filter_second{ id = caster.id },
				amount = power.slam_damage, damage_type = "impact", kill = true, fire_event = true,
				animate = true, experience = true }
		end
	end,
})

force.register_power("pull", {
	name = _ "Force Pull", cost = 2, range = 3, cooldown = 1, target = "enemy", needs_action = true,
	description = _ "Drag an enemy one hex straight toward you. It must be at least two hexes away. Nothing happens if the way is blocked.",
	valid = function(caster, target)
		return wesnoth.map.distance_between(caster.x, caster.y, target.x, target.y) > 1
	end,
	apply = function(caster, target)
		local dir = wesnoth.map.get_relative_dir({ target.x, target.y }, { caster.x, caster.y })
		if force.displace(target, dir) then core.float(target.x, target.y, _ "pulled", "#a8c8ff") end
	end,
})

force.register_power("speed", {
	name = _ "Force Speed", cost = 2, range = 0, target = "self", per_turn = true, bonus_moves = 2,
	description = _ "Gain 2 extra movement points right away. They can be used until the end of this turn.",
	apply = function(caster, _target, power)
		caster.moves = caster.moves + power.bonus_moves
		core.float(caster.x, caster.y, _ "Force speed", "#a8c8ff")
	end,
})

force.register_power("sense", {
	name = _ "Force Sense", cost = 1, range = 0, target = "self", per_turn = true, radius = 4,
	description = _ "Feel every living being within 4 hexes. Hidden creatures there (such as Noghri) lose their stealth until your next turn. It cannot see through technological cloaking.",
	apply = function(caster, _target, power)
		local found = 0
		for _i, t in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{
				T.filter_location{ x = caster.x, y = caster.y, radius = power.radius },
				T.filter_side{ T.enemy_of{ side = caster.side } } })) do
			-- Only living stealth (ability ids listed in force.SENSE_REVEALS)
			-- is defeated; cloaking fields are not living presences.
			for ability_id, _v in pairs(force.SENSE_REVEALS) do
				if t:matches{ ability = ability_id } then
					t:add_modification("object", { id = "sw_force_sensed",
						T.effect{ apply_to = "remove_ability", T.abilities{ T.hides{ id = ability_id } } } })
					t.variables.sw_sensed_until = wesnoth.current.turn + 1
					t.variables.sw_sensed_side = caster.side
				end
			end
			if not force.is_suppressed(t) then found = found + 1 end
		end
		core.float(caster.x, caster.y, tostring(found) .. " " .. tostring(_ "presences"), "#a8c8ff")
	end,
})
-- Living stealth abilities that Force Sense defeats (extensible by scenarios).
force.SENSE_REVEALS = { sw_ability_noghri_stealth = true }

force.register_power("mind_trick", {
	name = _ "Mind Trick", cost = 3, range = 2, cooldown = 2, target = "enemy", needs_action = true, max_level = 2,
	description = _ "Cloud a weak-minded enemy: on its next turn it cannot move or attack, and it loses overwatch. Leaders, Force users and units above level 2 resist.",
	valid = function(caster, target, power)
		return target.level <= power.max_level and not target.canrecruit and not force.is_sensitive(target)
	end,
	apply = function(caster, target)
		target.variables.sw_dazed_turn = wesnoth.current.turn + (target.side < caster.side and 1 or 0)
		target.variables.sw_dazed_side = target.side
		if force.on_disabled then force.on_disabled(target) end
		core.set_overlay(target, "dazed", "misc/sw-dazed.png")
		core.float(target.x, target.y, _ "these aren't the droids…", "#a8c8ff")
	end,
})

force.register_power("choke", {
	name = _ "Force Choke", cost = 3, range = 3, cooldown = 1, target = "enemy", needs_action = true, damage = 10,
	alignment = "dark",
	description = _ "Crush an enemy's throat from a distance: 10 arcane damage (dark side).",
	apply = function(caster, target, power)
		wesnoth.wml_actions.harm_unit{ T.filter{ id = target.id }, T.filter_second{ id = caster.id },
			amount = power.damage, damage_type = "arcane", kill = true, fire_event = true,
			animate = true, experience = true }
	end,
})

force.register_power("deflection", {
	name = _ "Blaster Deflection", cost = 1, target = "self", passive = true,
	description = _ "Works by itself: turns aside an overwatch volley aimed at this unit, spending 1 Force Point each time. Fails inside a ysalamiri field.",
	apply = function() end,
})

-- Reactive deflection, called by the overwatch resolver before any hit is
-- rolled (see docs/systems/FORCE_AND_OVERWATCH.md for precedence).
function force.try_deflect(target, shooter)
	local cfg = force.config(target)
	if not cfg then return false end
	local ok = force.can_use(target, "deflection", cfg)
	if not ok then return false end
	force.set_fp(target, force.fp(target) - force.power_value(target, cfg, force.powers.deflection, "cost"), cfg)
	core.float(target.x, target.y, _ "deflected", "#7cff7c")
	core.log("force", target.id .. " deflected overwatch fire from " .. shooter.id)
	return true
end

-- ---------------------------------------------------------------- turn cycle

-- At the start of a side's turn: regenerate Force Points (not inside a null
-- field), tick cooldowns, apply Mind Trick, and expire Force Sense reveals.
function force.on_side_turn(side)
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ side = side })) do
		local cfg = force.config(u)
		if cfg then
			if not force.is_suppressed(u) then
				force.set_fp(u, force.fp(u) + cfg.fp_regen, cfg)
			end
			for _i, p in ipairs(cfg.powers) do
				local cd = core.number(u.variables["sw_cd_" .. p], 0)
				if cd > 0 then u.variables["sw_cd_" .. p] = cd - 1 end
			end
		end
		if core.number(u.variables.sw_dazed_turn, -1) == wesnoth.current.turn then
			-- Mind Trick takes hold for this whole turn of the unit.
			u.moves = 0
			u.attacks_left = 0
			u.variables.sw_dazed_turn = nil
			u.variables.sw_dazed_active = wesnoth.current.turn
			core.float(u.x, u.y, _ "dazed", "#a8c8ff")
		elseif u.variables.sw_dazed_active ~= nil then
			u.variables.sw_dazed_active = nil
			u.variables.sw_dazed_side = nil
			core.set_overlay(u, "dazed", nil)
		end
	end
	-- Force Sense reveals last until the sensing side's next turn.
	for _i, u in ipairs(wesnoth.units.find_on_map{ T.filter_wml{ T.variables{ sw_sensed_side = side } } }) do
		u:remove_modifications({ id = "sw_force_sensed" }, "object")
		u.variables.sw_sensed_until = nil
		u.variables.sw_sensed_side = nil
	end
end

-- Whether a unit is barred from acting this turn by Mind Trick (overwatch
-- exclusion hook).
function force.is_dazed(u)
	return u.variables.sw_dazed_turn ~= nil or u.variables.sw_dazed_active ~= nil
end

-- ---------------------------------------------------------------- menu

function force.menu_visible()
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	return u ~= nil and force.is_sensitive(u) and core.is_local_turn_of(u.side)
end

function force.status_text(u, cfg)
	local lines = { tostring(_ "Force Points:") .. " " .. force.fp(u) .. "/" .. cfg.fp_max ..
		"   " .. tostring(_ "regenerates") .. " " .. cfg.fp_regen .. "/" .. tostring(_ "turn") }
	if force.is_suppressed(u) then
		table.insert(lines, tostring(_ "Inside a ysalamiri field: the Force is blocked here."))
	end
	return table.concat(lines, "\n")
end

-- Two synced choices: power, then target. Unavailable powers are listed with
-- the reason so the player always knows why.
-- ---------------------------------------------------------------- push / pull preview

force.DIR_NAMES = { n = _ "north", ne = _ "north-east", se = _ "south-east", s = _ "south", sw = _ "south-west", nw = _ "north-west" }

local function unit_label(u)
	local type_name = wesnoth.unit_types[u.type] and tostring(wesnoth.unit_types[u.type].name) or u.type
	if u.name ~= "" and tostring(u.name) ~= type_name then return tostring(u.name) .. " (" .. type_name .. ")" end
	return type_name
end

local function terrain_label(x, y)
	local ok, name = pcall(function()
		local code = wesnoth.current.map[{ x, y }]
		local info = wesnoth.terrain_types[code]
		return info and tostring(info.name) or code
	end)
	return ok and name or tostring(_ "terrain")
end

-- What a Push or Pull would do to a target, judged only from what the
-- caster's side can see (a hidden unit in the way is not revealed; the move
-- then fails when it is tried). Returns { dir, x, y, blocked, kind, what }:
-- kind is "edge", "unit" or "terrain" when blocked.
function force.displacement_preview(caster, target, power_id)
	local dir
	if power_id == "pull" then
		dir = wesnoth.map.get_relative_dir({ target.x, target.y }, { caster.x, caster.y })
	else
		dir = wesnoth.map.get_relative_dir({ caster.x, caster.y }, { target.x, target.y })
	end
	local d = wesnoth.map.get_direction({ target.x, target.y }, dir)
	local x, y = d[1] or d.x, d[2] or d.y
	local p = { dir = dir, x = x, y = y, blocked = false }
	if not wesnoth.current.map:on_board(x, y) then
		p.blocked, p.kind, p.what = true, "edge", tostring(_ "the edge of the battlefield")
		return p
	end
	local occupant = wesnoth.units.get(x, y)
	if occupant and occupant.id ~= caster.id and occupant:matches{ T.filter_vision{ side = caster.side, visible = true } } then
		p.blocked, p.kind, p.what = true, "unit", unit_label(occupant)
	elseif occupant and occupant.id == caster.id then
		p.blocked, p.kind, p.what = true, "unit", unit_label(occupant)
	elseif target:movement_on({ x = x, y = y }) >= 99 then
		p.blocked, p.kind, p.what = true, "terrain", terrain_label(x, y)
	end
	return p
end

function force.arrow_image(p)
	return "misc/sw-force-arrow-" .. p.dir .. (p.blocked and "-blocked" or "") .. ".png"
end

-- The outcome line shown under a Push or Pull target.
function force.displacement_text(caster, target, power_id, cfg)
	cfg = cfg or force.config(caster)
	local p = force.displacement_preview(caster, target, power_id)
	local dir = tostring(force.DIR_NAMES[p.dir] or p.dir)
	if power_id == "push" then
		if not p.blocked then
			return tostring(_ "Pushed") .. " " .. dir .. " " .. tostring(_ "to") .. " " .. p.x .. "," .. p.y .. ".", p
		end
		local dmg = force.power_value(caster, cfg, force.powers.push, "slam_damage")
		return "<b>" .. tostring(_ "Pushed") .. " " .. dir .. " " .. tostring(_ "into") .. " " .. p.what .. ": " ..
			tostring(_ "slams for") .. " " .. dmg .. " " .. tostring(_ "impact damage") .. "</b> " ..
			tostring(_ "and stays in place."), p
	end
	if not p.blocked then
		return tostring(_ "Pulled") .. " " .. dir .. " " .. tostring(_ "to") .. " " .. p.x .. "," .. p.y .. ".", p
	end
	return "<b>" .. tostring(_ "Blocked by") .. " " .. p.what .. ": " .. tostring(_ "cannot be pulled") .. "</b> " ..
		tostring(_ "(no damage)."), p
end

-- ---------------------------------------------------------------- menu

-- Second line for a power in the menu: what it does and what it costs.
function force.power_summary(caster, power_id, cfg)
	cfg = cfg or force.config(caster)
	local power = force.powers[power_id]
	local parts = {}
	if power.passive then
		table.insert(parts, tostring(_ "passive"))
		table.insert(parts, force.power_value(caster, cfg, power, "cost") .. " " .. tostring(_ "FP each time"))
	else
		table.insert(parts, force.power_value(caster, cfg, power, "cost") .. " " .. tostring(_ "FP"))
		local range = force.power_value(caster, cfg, power, "range")
		if power.target == "self" then
			table.insert(parts, tostring(_ "self"))
		elseif range then
			table.insert(parts, tostring(_ "range") .. " " .. range)
		end
		local cooldown = force.power_value(caster, cfg, power, "cooldown")
		if cooldown and cooldown > 0 then
			table.insert(parts, tostring(_ "recovers in") .. " " .. cooldown .. " " .. tostring(_ "turn(s)"))
		end
		if power.per_turn then table.insert(parts, tostring(_ "once per turn")) end
		if power.needs_action then table.insert(parts, tostring(_ "uses your attack")) end
	end
	return tostring(power.description) .. "\n<small>" .. table.concat(parts, " · ") .. "</small>"
end

local function power_known(cfg, id)
	for _i, p in ipairs(cfg.powers) do if p == id then return true end end
	return false
end

-- Two synced choices: power, then target. Every power shows what it does;
-- unavailable ones are greyed with the reason. Push and Pull always ask for
-- the target, showing the direction (arrow in the list and on the map) and
-- whether the target would slam into something.
function force.open_menu()
	local ctx = core.menu_context()
	local caster = wesnoth.units.get(ctx.x1, ctx.y1)
	if not caster then return end
	local cfg = force.config(caster)
	if not cfg then return end
	local options, ids = {}, {}
	for _i, id in ipairs(force.power_order) do
		local power = force.powers[id]
		if power_known(cfg, id) then
			local label, ok, why
			if power.passive then
				ok = false
				label = "<span color='#a8c8ff'>" .. tostring(power.name) .. "</span>"
			else
				ok, why = force.can_use(caster, id, cfg)
				label = tostring(power.name) .. " (" .. force.power_value(caster, cfg, power, "cost") .. " FP)"
				if ok and #force.valid_targets(caster, id, cfg) == 0 then ok, why = false, _ "no valid target in range" end
				if not ok then label = "<span color='#888888'>" .. label .. " — " .. tostring(why) .. "</span>" end
			end
			table.insert(options, { label = label, description = force.power_summary(caster, id, cfg) })
			table.insert(ids, { id = id, ok = ok })
		end
	end
	table.insert(options, tostring(_ "Close"))
	local pick = core.choose(_ "The Force", force.status_text(caster, cfg), options)
	local chosen = ids[pick]
	if not chosen or not chosen.ok then return end
	local power = force.powers[chosen.id]
	local targets = force.valid_targets(caster, chosen.id, cfg)
	local target = targets[1]
	local directional = chosen.id == "push" or chosen.id == "pull"
	if power.target ~= "self" and (#targets > 1 or directional) then
		local toptions, marks = {}, {}
		for _i, t in ipairs(targets) do
			local opt = { label = unit_label(t) .. " (" .. t.x .. "," .. t.y .. ")" }
			if directional then
				local text, p = force.displacement_text(caster, t, chosen.id, cfg)
				opt.description = text
				opt.image = force.arrow_image(p) .. "~SCALE(48,48)"
				-- The same arrow on the target's hex, for the caster's team only.
				local name = "sw_force_arrow|" .. t.id
				wesnoth.wml_actions.item{ x = t.x, y = t.y, image = force.arrow_image(p), name = name,
					team_name = core.team_key(caster.side), redraw = false }
				table.insert(marks, { x = t.x, y = t.y, name = name })
			end
			table.insert(toptions, opt)
		end
		table.insert(toptions, tostring(_ "Cancel"))
		if #marks > 0 then wesnoth.wml_actions.redraw{} end
		local tpick = core.choose(power.name, power.description, toptions)
		for _i, m in ipairs(marks) do wesnoth.interface.remove_item(m.x, m.y, m.name) end
		if #marks > 0 then wesnoth.wml_actions.redraw{} end
		target = targets[tpick]
	end
	if target then force.use(caster, chosen.id, target) end
end

return force
