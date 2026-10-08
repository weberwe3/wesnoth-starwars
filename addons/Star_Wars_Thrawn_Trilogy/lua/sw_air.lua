-- Star Wars: Thrawn Trilogy -- off-map air support.
--
-- Fast starfighters and bombers support ground battles as off-map sorties,
-- not map units (project scope 5.3). A side is granted a number of sorties
-- per mission ([sw_air_support] / {SW_AIR_SUPPORT}); a forward observer --
-- a unit with [dummy] id=sw_ability_forward_observer range=N -- calls one on
-- a hex its side can see or tracks on sensors, using the observer's attack.
-- At most one sortie per side per turn.
--
-- Sorties (registry: air.register_sortie):
--   strafe   Strafing run. Immediate. A line of 4 hexes from the target,
--            running away from the observer. 3 strikes x 6 fire per unit.
--   bombing  Bombing run. Telegraphed: the target and its 6 neighbours are
--            marked for everyone and hit at the start of the caller's next
--            turn. 2 strikes x 9 fire per unit, +10% accuracy.
-- Each strike hits with 100 - the unit's terrain defence + accuracy
-- modifiers (clamped 10..90), rolled on the synced RNG, so cover matters.
-- Accuracy modifiers: enemy anti-air within its radius of any struck hex
-- (-penalty each, -40 at most); enemy jamming over the target hex
-- (-10 per ECM point above the observer's ECCM).
-- Sorties hit every unit in the area, friend or foe, and never kill: a unit
-- is left with at least 1 HP (air support softens, ground forces finish; a
-- mission is never lost to an off-map strike alone).
-- AI sides with sorties use them at the end of their turn on the best
-- visible cluster of enemies; AI sides avoid hexes under an inbound bombing
-- run (AI avoid aspect) until it lands.
--
-- State: container sw_air_s<side> (scenario-stamped: sortie charges, last
-- turn used), array sw_air_inbound (telegraphed strikes), serial
-- sw_air_serial.

local T = wml.tag
local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local ew = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ew.lua")
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local air = {}

air.OBSERVER = "sw_ability_forward_observer"
air.ANTI_AIR = "sw_ability_anti_air"
air.AA_MAX = 40
air.JAM_PER_POINT = 10
air.MIN_CHANCE, air.MAX_CHANCE = 10, 90

-- Hooks: modify_accuracy(side, sortie, hexes, terms) adjusts terms.total;
-- on_call(side, sortie_id, observer, x, y); on_strike(strike, results).
air.hooks = { modify_accuracy = {}, on_call = {}, on_strike = {} }

air.sorties = {}
air.sortie_order = {}

function air.register_sortie(id, def)
	def.id = id
	air.sorties[id] = def
	table.insert(air.sortie_order, id)
end

air.register_sortie("strafe", {
	name = _ "Strafing run", length = 4, strikes = 3, damage = 6, damage_type = "fire", accuracy = 0, delay = 0,
	sound = "sw-laser-cannon.wav", impact = "sw-laser-hit.wav",
	description = _ "Starfighters rake a line of four hexes running away from the observer: three shots at every unit there, friend or foe. Strikes at once.",
})
air.register_sortie("bombing", {
	name = _ "Bombing run", radius = 1, strikes = 2, damage = 9, damage_type = "fire", accuracy = 10, delay = 1,
	sound = "sw-torpedo.wav", impact = "sw-explosion.wav",
	description = _ "Bombers saturate the target hex and the six around it: two bombs at every unit there, friend or foe. The area is marked for everyone and hit at the start of your next turn.",
})

-- ---------------------------------------------------------------- state

local function var_name(side) return "sw_air_s" .. side end

function air.load(side)
	local raw = wml.variables[var_name(side)]
	if type(raw) ~= "table" or raw.scenario ~= core.scenario_id() then
		return { side = side, scenario = core.scenario_id(), used_turn = -1, charges = {}, craft = {} }
	end
	local st = { side = side, scenario = raw.scenario, used_turn = core.number(raw.used_turn, -1), charges = {}, craft = {} }
	for _i, c in ipairs(wml.child_array(raw, "sortie")) do
		st.charges[c.id] = core.number(c.count, 0)
		st.craft[c.id] = c.craft
	end
	return st
end

function air.save(st)
	local out = { scenario = st.scenario, used_turn = st.used_turn }
	for _i, id in ipairs(core.sorted_keys(st.charges)) do
		table.insert(out, T.sortie{ id = id, count = st.charges[id], craft = st.craft[id] })
	end
	wml.variables[var_name(st.side)] = out
end

function air.ensure_scenario()
	if wml.variables.sw_air_scenario ~= core.scenario_id() then
		wml.array_access.set("sw_air_inbound", {})
		wml.variables.sw_air_serial = 0
		wml.variables.sw_air_scenario = core.scenario_id()
	end
end

-- Grant COUNT sorties of a type to a side. craft: unit type shown flying
-- the sortie (e.g. sw_unit_nr_xwing, sw_unit_im_tie_bomber).
function air.grant(side, sortie_id, count, craft)
	air.ensure_scenario()
	if not air.sorties[sortie_id] then wml.error("unknown air sortie: " .. tostring(sortie_id)) end
	local st = air.load(side)
	st.charges[sortie_id] = math.max(0, core.number(st.charges[sortie_id], 0) + (count or 1))
	if craft then st.craft[sortie_id] = craft end
	air.save(st)
	core.log("air", "side " .. side .. " granted " .. tostring(count) .. " " .. sortie_id)
end

function air.charges(side, sortie_id)
	return core.number(air.load(side).charges[sortie_id], 0)
end

function air.total_charges(side)
	local n = 0
	for _i, id in ipairs(air.sortie_order) do n = n + air.charges(side, id) end
	return n
end

-- ---------------------------------------------------------------- targeting

local function observer_range(u)
	local cfg = core.ability_cfg(u, air.OBSERVER)
	return cfg and core.number(cfg.range, 6) or nil
end

local function is_dazed(u)
	return u.variables.sw_dazed_turn ~= nil or u.variables.sw_dazed_active ~= nil
end

-- Observers of a side able to call now (attack left, not dazed), by id.
function air.observers(side)
	local out = {}
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ side = side, ability = air.OBSERVER })) do
		if u.attacks_left > 0 and not is_dazed(u) and u.hitpoints > 0 then table.insert(out, u) end
	end
	return out
end

-- Can the side's team see the hex, or does it hold a sensor contact there?
function air.hex_known(side, x, y)
	if not wesnoth.current.map:on_board(x, y) then return false end
	local team = core.team_key(side)
	for _i, s in ipairs(core.active_sides()) do
		if core.team_key(s) == team and not wesnoth.sides.is_fogged(s, { x = x, y = y }) then return true end
	end
	for _i, rec in ipairs(ew.contacts_at(team, x, y)) do
		if core.number(rec.state, 0) >= ew.PARTIAL then return true end
	end
	return false
end

-- The observer that would call a strike on x,y (closest, then by id), or nil.
function air.observer_for(side, x, y)
	if not air.hex_known(side, x, y) then return nil end
	local best, best_d = nil, nil
	for _i, u in ipairs(air.observers(side)) do
		local d = wesnoth.map.distance_between(u.x, u.y, x, y)
		if d >= 1 and d <= observer_range(u) and (best_d == nil or d < best_d) then best, best_d = u, d end
	end
	return best
end

-- Hexes struck by a sortie called by observer on x,y, in a stable order.
function air.area(sortie_id, observer, x, y)
	local def = air.sorties[sortie_id]
	local out = {}
	if def.length then
		local dir = wesnoth.map.get_relative_dir({ observer.x, observer.y }, { x, y })
		if not dir or dir == "" then dir = "n" end
		local loc = { x, y }
		for _i = 1, def.length do
			if wesnoth.current.map:on_board(loc[1], loc[2]) then table.insert(out, { x = loc[1], y = loc[2] }) end
			local nxt = wesnoth.map.get_direction(loc, dir)
			loc = { nxt[1] or nxt.x, nxt[2] or nxt.y }
		end
		out.dir = dir
	else
		for _i, loc in ipairs(wesnoth.map.find{ x = x, y = y, radius = def.radius or 1 }) do
			local lx, ly = loc[1] or loc.x, loc[2] or loc.y
			table.insert(out, { x = lx, y = ly })
		end
		table.sort(out, function(a, b) if a.x ~= b.x then return a.x < b.x end return a.y < b.y end)
		out.dir = wesnoth.map.get_relative_dir({ observer.x, observer.y }, { x, y })
	end
	return out
end

-- Accuracy terms for a sortie against an area: base, anti-air, jamming.
function air.accuracy(side, sortie_id, observer, hexes)
	local def = air.sorties[sortie_id]
	local terms = { base = def.accuracy or 0, anti_air = 0, jamming = 0, aa_units = 0 }
	for _i, aa in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ ability = air.ANTI_AIR })) do
		if wesnoth.sides.is_enemy(aa.side, side) and aa.hitpoints > 0 then
			local cfg = core.ability_cfg(aa, air.ANTI_AIR) or {}
			local radius = core.number(cfg.radius, 2)
			for _j, h in ipairs(hexes) do
				if wesnoth.map.distance_between(aa.x, aa.y, h.x, h.y) <= radius then
					terms.anti_air = terms.anti_air + core.number(cfg.penalty, 20)
					terms.aa_units = terms.aa_units + 1
					break
				end
			end
		end
	end
	terms.anti_air = math.min(air.AA_MAX, terms.anti_air)
	local center = hexes[1]
	if center and observer then
		local ecm = 0
		for _i, j in ipairs(wesnoth.units.find_on_map{}) do
			if wesnoth.sides.is_enemy(j.side, side) and j.hitpoints > 0 then
				local p = ew.profile(j)
				if p.ecm > ecm and wesnoth.map.distance_between(j.x, j.y, center.x, center.y) <= p.ecm_range then ecm = p.ecm end
			end
		end
		terms.jamming = math.max(0, ecm - ew.profile(observer).eccm) * air.JAM_PER_POINT
	end
	terms.total = terms.base - terms.anti_air - terms.jamming
	for _i, hook in ipairs(air.hooks.modify_accuracy) do hook(side, def, hexes, terms) end
	return terms
end

local function chance_for(u, accuracy)
	local c = 100 - u:defense_on({ x = u.x, y = u.y }) + accuracy
	return math.max(air.MIN_CHANCE, math.min(air.MAX_CHANCE, c))
end

local function units_in(hexes)
	local out = {}
	for _i, h in ipairs(hexes) do
		local u = wesnoth.units.get(h.x, h.y)
		if u and u.hitpoints > 0 then table.insert(out, u) end
	end
	return core.sorted_by_id(out)
end

-- Expected damage to each unit the caller's side can see in the area.
function air.preview(side, sortie_id, observer, x, y)
	local def = air.sorties[sortie_id]
	local hexes = air.area(sortie_id, observer, x, y)
	local terms = air.accuracy(side, sortie_id, observer, hexes)
	local p = { hexes = hexes, terms = terms, enemies = 0, friends = 0, enemy_damage = 0, friend_damage = 0 }
	for _i, u in ipairs(units_in(hexes)) do
		if u:matches{ T.filter_vision{ side = side, visible = true } } then
			local expected = def.strikes * def.damage * chance_for(u, terms.total) / 100
			if wesnoth.sides.is_enemy(u.side, side) then
				p.enemies = p.enemies + 1
				p.enemy_damage = p.enemy_damage + expected
			else
				p.friends = p.friends + 1
				p.friend_damage = p.friend_damage + expected
			end
		end
	end
	return p
end

-- ---------------------------------------------------------------- calling

function air.can_call(side, sortie_id)
	if not air.sorties[sortie_id] then return false, _ "unknown sortie" end
	if air.charges(side, sortie_id) < 1 then return false, _ "none left" end
	if air.load(side).used_turn == wesnoth.current.turn then return false, _ "one sortie per turn" end
	return true
end

local function inbound_item(strike_id) return "sw_air_inbound|" .. strike_id end

local function set_avoid(strike, on)
	-- Hostile AI sides keep out of a telegraphed bombing area until it lands.
	for _i, s in ipairs(core.active_sides()) do
		if wesnoth.sides[s].controller == "ai" then
			if on and wesnoth.sides.is_enemy(s, strike.side) then
				wesnoth.wml_actions.modify_ai{ side = s, action = "add", path = "aspect[avoid].facet",
					T.facet{ id = "sw_air_" .. strike.id, T.value{ x = strike.xs, y = strike.ys } } }
			elseif not on and wesnoth.sides.is_enemy(s, strike.side) then
				wesnoth.wml_actions.modify_ai{ side = s, action = "delete", path = "aspect[avoid].facet[sw_air_" .. strike.id .. "]" }
			end
		end
	end
end

-- Call a sortie. Returns the strike id (immediate strikes resolve now).
function air.call(side, sortie_id, observer, x, y)
	air.ensure_scenario()
	local ok, why = air.can_call(side, sortie_id)
	if not ok then core.log("air", "side " .. side .. " cannot call " .. sortie_id .. ": " .. tostring(why)) return nil end
	if not observer or observer.side ~= side or observer.attacks_left < 1 then return nil end
	local def = air.sorties[sortie_id]
	local st = air.load(side)
	st.charges[sortie_id] = st.charges[sortie_id] - 1
	st.used_turn = wesnoth.current.turn
	air.save(st)
	observer.attacks_left = 0
	local hexes = air.area(sortie_id, observer, x, y)
	local serial = core.number(wml.variables.sw_air_serial, 0) + 1
	wml.variables.sw_air_serial = serial
	local xs, ys = {}, {}
	for _i, h in ipairs(hexes) do table.insert(xs, h.x) table.insert(ys, h.y) end
	local strike = { id = "strike" .. serial, side = side, sortie = sortie_id, observer = observer.id,
		x = x, y = y, dir = hexes.dir or "n", xs = table.concat(xs, ","), ys = table.concat(ys, ","),
		craft = st.craft[sortie_id] or "", due_turn = wesnoth.current.turn + (def.delay or 0) }
	core.log("air", "side " .. side .. " calls " .. sortie_id .. " (" .. strike.id .. ") on " .. x .. "," .. y ..
		" via " .. observer.id .. ", " .. #hexes .. " hexes")
	for _i, hook in ipairs(air.hooks.on_call) do hook(side, sortie_id, observer, x, y) end
	if (def.delay or 0) <= 0 then
		air.resolve(strike)
	else
		local inbound = wml.array_access.get("sw_air_inbound")
		table.insert(inbound, strike)
		wml.array_access.set("sw_air_inbound", inbound)
		for _i, h in ipairs(hexes) do
			wesnoth.wml_actions.item{ x = h.x, y = h.y, image = "misc/sw-air-inbound.png", name = inbound_item(strike.id),
				visible_in_fog = true, redraw = false }
		end
		wesnoth.wml_actions.redraw{}
		set_avoid(strike, true)
		core.float(x, y, tostring(def.name) .. ": " .. tostring(_ "inbound"), "#ff9a3c")
	end
	return strike.id
end

-- ---------------------------------------------------------------- resolution

-- Craft that fly sorties carry a hidden variation with flying movement, so
-- the fake unit has a route over ground maps (gen_hte_units.py FLYOVER_CRAFT).
local function flyover_variation(craft)
	local ut = wesnoth.unit_types[craft]
	if ut and ut.variations and ut.variations.sw_flyover then return "sw_flyover" end
	return nil
end

-- Pacing of the strike effects (display only). A fake unit moves 200 ms per
-- hex (engine), so approach + strike line + exit is about 2-2.5 s; the
-- detonations then ripple along the line, one hex every step_ms.
air.PACING = { approach = 3, exit = 3, step_ms = 160, burst_frame_ms = 90, settle_ms = 350, lead_ms = 250 }

-- Craft whose ordnance has its own impact animation (halo frames centred on
-- the hex; the energy bomb falls into the hex, then bursts).
air.CRAFT_BURST = {
	sw_unit_im_tie_bomber = "misc/sw-energy-bomb-[1~4].png:70,misc/sw-energy-bomb-[5~10].png:90,misc/sw-energy-bomb-[11~16].png:130",
}

local function flyover(strike, hexes)
	if strike.craft == "" or not wesnoth.unit_types[strike.craft] or #hexes == 0 then return end
	if strike.path == "hexes" then
		-- Scripted strikes fly along their own hexes, in the given order.
		wesnoth.wml_actions.move_unit_fake{ type = strike.craft, side = strike.side, variation = flyover_variation(strike.craft), x = strike.xs, y = strike.ys }
		return
	end
	-- Approach from a few hexes out, cross the target, leave a few hexes past it.
	local back = ({ n = "s", ne = "sw", se = "nw", s = "n", sw = "ne", nw = "se" })[strike.dir] or "s"
	local path = {}
	local loc = { hexes[1].x, hexes[1].y }
	local before = {}
	for _i = 1, air.PACING.approach do
		local p = wesnoth.map.get_direction(loc, back)
		loc = { p[1] or p.x, p[2] or p.y }
		if wesnoth.current.map:on_board(loc[1], loc[2]) then table.insert(before, 1, { loc[1], loc[2] }) else break end
	end
	for _i, b in ipairs(before) do table.insert(path, b) end
	loc = { strike.x, strike.y }
	for _i = 1, #hexes + air.PACING.exit do
		if not wesnoth.current.map:on_board(loc[1], loc[2]) then break end
		table.insert(path, { loc[1], loc[2] })
		local p = wesnoth.map.get_direction(loc, strike.dir)
		loc = { p[1] or p.x, p[2] or p.y }
	end
	if #path < 2 then return end
	local xs, ys = {}, {}
	for _i, p in ipairs(path) do table.insert(xs, p[1]) table.insert(ys, p[2]) end
	wesnoth.wml_actions.move_unit_fake{ type = strike.craft, side = strike.side, variation = flyover_variation(strike.craft),
		x = table.concat(xs, ","), y = table.concat(ys, ",") }
end

-- Resolve a strike now: flyover, blasts, synced hit rolls, damage (never lethal).
function air.resolve(strike)
	local def = air.sorties[strike.sortie]
	local hexes = {}
	local xs, ys = core.split(strike.xs), core.split(strike.ys)
	for i = 1, #xs do table.insert(hexes, { x = tonumber(xs[i]), y = tonumber(ys[i]) }) end
	local observer = wesnoth.units.get(strike.observer)
	local terms = air.accuracy(strike.side, strike.sortie, observer, hexes)
	-- Flyover and blasts are display only; sw_air_effects=no turns them off
	-- (the engine's -u test mode has no textures for halos).
	local effects = wml.variables.sw_air_effects ~= "no" and wml.variables.sw_air_effects ~= false
	if effects then
		-- Engines first, then the low pass, then the bombs or bolts walk
		-- along the line one hex at a time behind the craft.
		if def.sound then wesnoth.audio.play(def.sound) end
		wesnoth.interface.delay(air.PACING.lead_ms)
		flyover(strike, hexes)
		local burst = (air.CRAFT_BURST[strike.craft] or "halo/flame-burst-[1~8].png:" .. air.PACING.burst_frame_ms)
			.. ",misc/blank-hex.png:1"
		for _i, h in ipairs(hexes) do
			wesnoth.wml_actions.item{ x = h.x, y = h.y, halo = burst, name = "sw_air_blast", redraw = false }
			wesnoth.wml_actions.redraw{}
			if def.impact then wesnoth.audio.play(def.impact) end
			wesnoth.interface.delay(air.PACING.step_ms)
		end
		wesnoth.interface.delay(air.PACING.settle_ms)
	end
	local results = {}
	for _i, u in ipairs(units_in(hexes)) do
		if strike.enemies_only == true and not wesnoth.sides.is_enemy(u.side, strike.side) then goto continue end
		do
		local chance = chance_for(u, terms.total)
		local strikes = core.number(strike.strikes, def.strikes)
		local hits = 0
		for _n = 1, strikes do
			-- Scripted strikes may be certain (fixed damage, no roll).
			if strike.certain == true or mathx.random(1, 100) <= chance then hits = hits + 1 end
		end
		table.insert(results, { id = u.id, hits = hits, chance = chance })
		core.log("air", strike.id .. " " .. u.id .. ": " .. hits .. "/" .. strikes .. " at " .. chance .. "%")
		if hits > 0 then
			local concealed = u.status[ew.CONCEALED] == true
			local cfg = { T.filter{ id = u.id }, amount = core.number(strike.damage, def.damage) * hits,
				damage_type = def.damage_type, kill = false, fire_event = true, animate = not concealed,
				experience = observer ~= nil }
			if observer then table.insert(cfg, T.filter_second{ id = observer.id }) end
			wesnoth.wml_actions.harm_unit(cfg)
		end
		end
		::continue::
	end
	if effects then
		for _i, h in ipairs(hexes) do wesnoth.interface.remove_item(h.x, h.y, "sw_air_blast") end
	end
	for _i, hook in ipairs(air.hooks.on_strike) do hook(strike, results) end
	return results
end

-- A scripted sortie ([sw_air_strike]): no observer, no charge. cfg: side,
-- sortie, craft, damage (per hit), strikes, certain (always hit: fixed
-- damage for set pieces), enemies_only, and either
-- x, y, direction (sortie's own pattern) or explicit hexes {x=, y=} in flight
-- order. Resolves at once.
function air.scripted_strike(cfg)
	air.ensure_scenario()
	local def = air.sorties[cfg.sortie or "strafe"] or wml.error("unknown air sortie")
	local hexes = cfg.hexes
	local dir = cfg.direction or "s"
	if not hexes then
		local back = ({ n = "s", ne = "sw", se = "nw", s = "n", sw = "ne", nw = "se" })[dir] or "n"
		local b = wesnoth.map.get_direction({ cfg.x, cfg.y }, back)
		hexes = air.area(def.id, { x = b[1] or b.x, y = b[2] or b.y }, cfg.x, cfg.y)
	end
	local xs, ys = {}, {}
	for _i, h in ipairs(hexes) do table.insert(xs, h.x) table.insert(ys, h.y) end
	local serial = core.number(wml.variables.sw_air_serial, 0) + 1
	wml.variables.sw_air_serial = serial
	local strike = { id = "strike" .. serial, side = cfg.side, sortie = def.id, observer = "",
		x = hexes[1] and hexes[1].x or cfg.x, y = hexes[1] and hexes[1].y or cfg.y, dir = dir,
		xs = table.concat(xs, ","), ys = table.concat(ys, ","), craft = cfg.craft or "",
		damage = cfg.damage, enemies_only = cfg.enemies_only == true or cfg.enemies_only == "yes",
		strikes = cfg.strikes, certain = cfg.certain == true or cfg.certain == "yes",
		path = cfg.hexes and "hexes" or nil }
	core.log("air", "scripted " .. def.id .. " for side " .. tostring(cfg.side) .. " on " .. #hexes .. " hexes")
	return air.resolve(strike)
end

-- Start of a side's turn: its telegraphed strikes land.
function air.on_side_turn(side)
	air.ensure_scenario()
	local keep, due = {}, {}
	for _i, s in ipairs(wml.array_access.get("sw_air_inbound")) do
		if s.side == side and wesnoth.current.turn >= core.number(s.due_turn, 0) then table.insert(due, s)
		else table.insert(keep, s) end
	end
	if #due == 0 then return end
	wml.array_access.set("sw_air_inbound", keep)
	for _i, s in ipairs(due) do
		for _j, x in ipairs(core.split(s.xs)) do
			local y = core.split(s.ys)[_j]
			wesnoth.interface.remove_item(tonumber(x), tonumber(y), inbound_item(s.id))
		end
		set_avoid(s, false)
		air.resolve(s)
	end
end

-- ---------------------------------------------------------------- AI

-- AI sides call a sortie at the end of their turn when one would hit
-- visible enemies for at least ai_min expected damage (default 8) and, for a
-- bombing run, no friendly unit is in the area. Deterministic: candidates
-- are scored, ties broken by observer id and hex.
function air.on_side_turn_end(side)
	if wml.variables.sw_air_ai == false or wml.variables.sw_air_ai == "no" then return end
	if wesnoth.sides[side].controller ~= "ai" or air.total_charges(side) == 0 then return end
	if air.load(side).used_turn == wesnoth.current.turn then return end
	local best = nil
	for _i, id in ipairs(air.sortie_order) do
		if air.can_call(side, id) then
			for _j, obs in ipairs(air.observers(side)) do
				local range = observer_range(obs)
				for _k, e in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{
						T.filter_side{ T.enemy_of{ side = side } },
						T.filter_location{ x = obs.x, y = obs.y, radius = range } })) do
					if e:matches{ T.filter_vision{ side = side, visible = true } } and air.hex_known(side, e.x, e.y)
						and wesnoth.map.distance_between(obs.x, obs.y, e.x, e.y) >= 1 then
						local p = air.preview(side, id, obs, e.x, e.y)
						local def = air.sorties[id]
						local score = p.enemy_damage - 2 * p.friend_damage
						local allowed = p.enemies > 0 and not (def.delay and def.delay > 0 and p.friends > 0)
						if allowed and score >= core.number(wml.variables.sw_air_ai_min, 8) and
							(best == nil or score > best.score) then
							best = { score = score, id = id, obs = obs, x = e.x, y = e.y }
						end
					end
				end
			end
		end
	end
	if best then
		core.log("air", "AI side " .. side .. " calls " .. best.id .. " on " .. best.x .. "," .. best.y ..
			string.format(" (expected %.1f)", best.score))
		air.call(side, best.id, best.obs, best.x, best.y)
	end
end

-- ---------------------------------------------------------------- menu / text

function air.menu_visible()
	local side = core.viewing_side()
	if not side or not core.is_local_turn_of(side) or air.total_charges(side) == 0 then return false end
	if air.load(side).used_turn == wesnoth.current.turn then return false end
	local ctx = core.menu_context()
	return air.observer_for(side, ctx.x1, ctx.y1) ~= nil
end

function air.describe(side, sortie_id, observer, x, y)
	local def = air.sorties[sortie_id]
	local p = air.preview(side, sortie_id, observer, x, y)
	local t = p.terms
	local lines = { "<b>" .. tostring(def.name) .. "</b> (" .. air.charges(side, sortie_id) .. " " .. tostring(_ "left") .. ")",
		tostring(def.description) }
	local acc = { tostring(_ "Accuracy") .. " " .. (t.total >= 0 and "+" or "") .. t.total .. "%" }
	if t.base ~= 0 then table.insert(acc, tostring(_ "bombers") .. " +" .. t.base) end
	if t.anti_air > 0 then table.insert(acc, tostring(_ "anti-air") .. " −" .. t.anti_air) end
	if t.jamming > 0 then table.insert(acc, tostring(_ "jamming") .. " −" .. t.jamming) end
	table.insert(lines, table.concat(acc, ", ") .. " " .. tostring(_ "(plus each target's terrain cover)"))
	table.insert(lines, tostring(_ "In the area:") .. " " .. p.enemies .. " " .. tostring(_ "enemy") .. ", " ..
		p.friends .. " " .. tostring(_ "friendly") .. string.format(" — %s %.0f / %.0f",
		tostring(_ "expected damage to enemies / friends:"), p.enemy_damage, p.friend_damage))
	if p.friends > 0 then table.insert(lines, "<span color='#ff8060'>" .. tostring(_ "Danger close: friendly units in the area!") .. "</span>") end
	table.insert(lines, tostring(_ "Called by") .. " " .. tostring(observer.name ~= "" and observer.name or
		wesnoth.unit_types[observer.type].name) .. " (" .. tostring(_ "uses its attack") .. ")")
	return table.concat(lines, "\n")
end

function air.menu_command()
	local side = wesnoth.current.side
	local ctx = core.menu_context()
	local x, y = ctx.x1, ctx.y1
	local observer = air.observer_for(side, x, y)
	if not observer then return end
	local labels, ids, texts = {}, {}, {}
	for _i, id in ipairs(air.sortie_order) do
		if air.charges(side, id) > 0 then
			local ok, why = air.can_call(side, id)
			local label = tostring(air.sorties[id].name) .. " ×" .. air.charges(side, id)
			if not ok then label = "<span color='#888888'>" .. label .. " — " .. tostring(why) .. "</span>" end
			table.insert(labels, label)
			table.insert(ids, { id = id, ok = ok })
			table.insert(texts, air.describe(side, id, observer, x, y))
		end
	end
	table.insert(labels, tostring(_ "Cancel"))
	local pick = core.choose(_ "Air support", table.concat(texts, "\n\n"), labels, "misc/sw-air-inbound.png")
	local chosen = ids[pick]
	if chosen and chosen.ok then air.call(side, chosen.id, observer, x, y) end
end

-- Tactical status line for a forward observer's side.
function air.status_line(u)
	if not u:matches{ ability = air.OBSERVER } then return nil end
	local parts = {}
	for _i, id in ipairs(air.sortie_order) do
		local n = air.charges(u.side, id)
		if n > 0 then table.insert(parts, tostring(air.sorties[id].name) .. " ×" .. n) end
	end
	return tostring(_ "Forward observer, range") .. " " .. observer_range(u) .. ". " .. tostring(_ "Air support:") .. " " ..
		(#parts > 0 and table.concat(parts, ", ") or tostring(_ "none available"))
end

return air
