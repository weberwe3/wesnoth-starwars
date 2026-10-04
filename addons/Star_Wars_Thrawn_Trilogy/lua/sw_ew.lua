-- Star Wars: Thrawn Trilogy -- sensors, cloaking and electronic warfare.
--
-- Every team keeps a sensor picture of the hostile units (and decoys) it can
-- detect. Each contact has a state:
--   0 undetected  1 unknown contact  2 partially identified (class)  3 identified
-- Detection is a deterministic score (no dice), recomputed when the
-- situation changes (completed moves, attacks, deaths, placements, turn
-- starts, sweeps, decoys, reveals) -- never per movement hex:
--
--   score    = observer sensor (+ scan while sweeping) - distance / falloff
--              - jamming (enemy ECM covering observer or target, less ECCM)
--              + observer environment + scenario sensor modifier
--              + target signature (+ emissions: sweeping, firing, jamming)
--              - target cloak (while active) - target terrain concealment
--   identify = score + the team's identification bonus (Thrawn Doctrine)
--   state    = contact if score >= contact; partial if identify >= partial;
--              identified if identify >= full. Physical adjacency always
--              identifies. The best observer on the team counts.
--
-- Unit profiles: class defaults by movement type, overridden by the unit
-- type's [dummy] id=sw_ability_ew (sensor, sensor_range, signature, cloak,
-- ecm, ecm_range, eccm, scan, decoys, class, disguise_class, decoy_class,
-- decoy_type), overridden per unit by unit variables sw_ew_<field> (set with
-- the [sw_ew_profile] tag).
--
-- Engine visibility: a unit with a cloak keeps the [hides] ability
-- sw_ability_cloaked, filtered on the custom status sw_ew_concealed. This
-- module sets that status while no hostile team has identified the unit, so
-- the engine hides it (from players and the AI), adjacency still ambushes,
-- and overwatch cannot target it. Contacts that are not otherwise visible
-- are drawn as team-private hex overlays ([item] team_name=), visible in fog.
--
-- State: WML arrays sw_ew_contacts (the pictures), sw_ew_decoys,
-- sw_ew_reveals, container sw_ew_settings, array sw_ew_terrain; unit
-- variables sw_ew_sweep, sw_ew_fired, sw_ew_decoys_used, sw_ew_<field>.
-- All mission state is stamped with the scenario id (sw_ew_scenario).

local T = wml.tag
local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local ew = {}

ew.ABILITY = "sw_ability_ew"
ew.CLOAK_HIDES = "sw_ability_cloaked"
ew.CONCEALED = "sw_ew_concealed"
ew.NONE, ew.CONTACT, ew.PARTIAL, ew.FULL = 0, 1, 2, 3

ew.FIELDS = { "sensor", "sensor_range", "signature", "cloak", "ecm", "ecm_range", "eccm", "scan", "decoys" }

ew.CLASS_BY_MOVETYPE = {
	sw_capital = "capital", sw_starfighter = "starfighter", fly = "starfighter",
	sw_walker = "vehicle", sw_repulsor = "vehicle", mounted = "vehicle", sw_beast = "creature",
}
ew.CLASS_DEFAULTS = {
	capital = { sensor = 5, sensor_range = 7, signature = 8 },
	starfighter = { sensor = 3, sensor_range = 5, signature = 3 },
	vehicle = { sensor = 3, sensor_range = 4, signature = 4 },
	infantry = { sensor = 2, sensor_range = 3, signature = 2 },
	creature = { sensor = 3, sensor_range = 3, signature = 2 },
	object = { sensor = 0, sensor_range = 0, signature = 4 },
}
ew.PROFILE_DEFAULTS = { cloak = 0, ecm = 0, ecm_range = 2, eccm = 0, scan = 0, decoys = 0 }
ew.CLASS_NAMES = {
	capital = _ "capital ship", starfighter = _ "starfighter", vehicle = _ "vehicle",
	infantry = _ "infantry", creature = _ "creature", object = _ "object or debris",
}
ew.STATE_NAMES = {
	[0] = _ "undetected", [1] = _ "unknown contact", [2] = _ "partially identified", [3] = _ "identified",
}

ew.DEFAULT_SETTINGS = {
	contact = 0, partial = 3, full = 6,  -- state thresholds
	falloff = 2,                          -- hexes per -1 of sensor score
	sweep_range = 2,                      -- extra sensor range while sweeping
	sweep_signature = 3,                  -- a sweeping unit's own emissions
	fire_signature = 2,                   -- a unit that attacked this turn
	ecm_signature = 2,                    -- a jammer is loud
	decoy_signature = 6, decoy_deception = 4, decoy_turns = 2, decoy_range = 2,
	sensor_modifier = 0,                  -- scenario-wide (e.g. -2 in an ion storm)
}
-- Environment: first matching rule wins. conceal hides a target standing
-- there; sensor (usually negative) affects an observer standing there.
ew.DEFAULT_TERRAIN = {
	{ terrain = "Qsa", conceal = 2, sensor = -1 },   -- asteroid field
	{ terrain = "*^F*", conceal = 1 },                -- forest canopy
	{ terrain = "*^V*", conceal = 1 },                -- settlements, structures
	{ terrain = "M*,H*^F*", conceal = 1 },            -- mountains
}

-- Extension hooks (empty by default).
--   modify_score(observer, target_info, terms)  adjust terms.total before classification
--   on_state_change(team, record, old_state)    a contact's state changed
--   on_decoy_exposed(team, decoy)               a decoy was recognised as false
--   relay(team) -> list of extra observer sides  command networks / shared sensors
--   bonus(team) -> {identify=, eccm=, discrimination=}  (Thrawn Doctrine registers one)
ew.hooks = { modify_score = {}, on_state_change = {}, on_decoy_exposed = {}, relay = {}, bonus = {} }

ew.refreshing = false   -- reentrancy guard (refresh can fire die/item events)

-- Pictures are computed once the mission's prestart has stamped the EW state
-- (sw_ew_scenario). The stamp is saved, so this holds after a reload too;
-- units placed while a scenario is still being set up are picked up then.
function ew.is_ready()
	return wml.variables.sw_ew_scenario == core.scenario_id()
end

-- ---------------------------------------------------------------- scope / settings

function ew.ensure_scenario()
	local id = core.scenario_id()
	if wml.variables.sw_ew_scenario ~= id then
		for _i, name in ipairs{ "sw_ew_contacts", "sw_ew_decoys", "sw_ew_reveals", "sw_ew_terrain" } do
			wml.array_access.set(name, {})
		end
		wml.variables.sw_ew_settings = nil
		wml.variables.sw_ew_decoy_serial = 0
		wml.variables.sw_ew_scenario = id
	end
end

function ew.settings()
	local s = {}
	for k, v in pairs(ew.DEFAULT_SETTINGS) do s[k] = v end
	local custom = wml.variables.sw_ew_settings
	if type(custom) == "table" then
		for k, v in pairs(custom) do
			if type(k) == "string" and ew.DEFAULT_SETTINGS[k] ~= nil then s[k] = core.number(v, s[k]) end
		end
		s.default_terrain = custom.default_terrain ~= false and custom.default_terrain ~= "no"
	else
		s.default_terrain = true
	end
	s.falloff = math.max(1, s.falloff)
	return s
end

local function terrain_rules(s)
	local rules = {}
	for _i, r in ipairs(wml.array_access.get("sw_ew_terrain")) do table.insert(rules, r) end
	if s.default_terrain then
		for _i, r in ipairs(ew.DEFAULT_TERRAIN) do table.insert(rules, r) end
	end
	return rules
end

-- ---------------------------------------------------------------- profiles

local type_cache = {}

local function type_profile(type_id)
	local cached = type_cache[type_id]
	if cached then return cached end
	local ut = wesnoth.unit_types[type_id]
	local cfg = ut and ut.__cfg or {}
	local ability = nil
	local abilities = wml.get_child(cfg, "abilities")
	if abilities then
		for _i, entry in ipairs(abilities) do
			if type(entry[2]) == "table" and entry[2].id == ew.ABILITY then ability = entry[2] end
		end
	end
	local class = (ability and ability.class) or ew.CLASS_BY_MOVETYPE[cfg.movement_type] or "infantry"
	if not ew.CLASS_DEFAULTS[class] then class = "infantry" end
	local p = { class = class }
	for k, v in pairs(ew.PROFILE_DEFAULTS) do p[k] = v end
	for k, v in pairs(ew.CLASS_DEFAULTS[class]) do p[k] = v end
	if ability then
		for _i, f in ipairs(ew.FIELDS) do
			if ability[f] ~= nil then p[f] = core.number(ability[f], p[f]) end
		end
		p.disguise = ability.disguise_class
		p.decoy_class = ability.decoy_class
		p.decoy_type = ability.decoy_type
	end
	type_cache[type_id] = p
	return p
end

-- The unit's effective profile: type, then per-unit overrides.
function ew.profile(u)
	local base = type_profile(u.type)
	local p = {}
	for k, v in pairs(base) do p[k] = v end
	local vars = u.variables
	for _i, f in ipairs(ew.FIELDS) do
		local v = vars["sw_ew_" .. f]
		if v ~= nil then p[f] = core.number(v, p[f]) end
	end
	if vars.sw_ew_class and ew.CLASS_DEFAULTS[vars.sw_ew_class] then p.class = vars.sw_ew_class end
	if vars.sw_ew_disguise then p.disguise = vars.sw_ew_disguise end
	return p
end

-- A cloak works only while the unit has not fired since its last turn
-- started (the engine also marks an attacking hider "uncovered").
function ew.cloak_active(u, p)
	p = p or ew.profile(u)
	return p.cloak > 0 and not u.variables.sw_ew_fired and not u.status.uncovered
end

local function emission(u, p, s)
	local sig = p.signature
	if u.variables.sw_ew_sweep then sig = sig + s.sweep_signature end
	if u.variables.sw_ew_fired then sig = sig + s.fire_signature end
	if p.ecm > 0 then sig = sig + s.ecm_signature end
	return sig
end

-- ---------------------------------------------------------------- teams

-- The teams in play, each with its sides, observers and doctrine bonus.
local function build_teams(s, units)
	local teams, order = {}, {}
	for _i, side in ipairs(core.active_sides()) do
		local key = core.team_key(side)
		if not teams[key] then
			teams[key] = { key = key, sides = {}, side_set = {}, human = false, observers = {}, members = {} }
			table.insert(order, key)
		end
		local t = teams[key]
		table.insert(t.sides, side)
		t.side_set[side] = true
		if wesnoth.sides[side].controller == "human" then t.human = true end
	end
	for _i, key in ipairs(order) do
		local t = teams[key]
		t.first = t.sides[1]
		-- Command networks: hooks may relay other sides' sensors to this team.
		local relay = {}
		for _i, hook in ipairs(ew.hooks.relay) do
			for _i, side in ipairs(hook(key) or {}) do relay[side] = true end
		end
		t.bonus = { identify = 0, eccm = 0, discrimination = 0 }
		for _i, hook in ipairs(ew.hooks.bonus) do
			local b = hook(key) or {}
			t.bonus.identify = t.bonus.identify + core.number(b.identify, 0)
			t.bonus.eccm = t.bonus.eccm + core.number(b.eccm, 0)
			t.bonus.discrimination = t.bonus.discrimination + core.number(b.discrimination, 0)
		end
		for _i, e in ipairs(units) do
			if t.side_set[e.u.side] then table.insert(t.members, e) end
			if (t.side_set[e.u.side] or relay[e.u.side]) and e.p.sensor_range > 0 then
				table.insert(t.observers, e)
			end
		end
	end
	return teams, order
end

local function hostile(team, side)
	return wesnoth.sides.is_enemy(team.first, side)
end

local function fogged_for_team(team, x, y)
	for _i, side in ipairs(team.sides) do
		if not wesnoth.sides.is_fogged(side, { x = x, y = y }) then return false end
	end
	return true
end

local function adjacent_member(team, x, y)
	for _i, m in ipairs(team.members) do
		if wesnoth.map.distance_between(m.u.x, m.u.y, x, y) <= 1 then return m end
	end
	return nil
end

-- ---------------------------------------------------------------- scoring

-- Best sensor score any observer on the team has against a target at x,y.
-- target = { x, y, side, sig (emitted signature), mask (cloak + terrain),
-- id }. Returns the terms of the best observer (or nil if none in range).
local function best_score(team, target, s, jammers, env_at)
	local best = nil
	for _i, o in ipairs(team.observers) do
		local sweeping = o.u.variables.sw_ew_sweep == true
		local range = o.p.sensor_range + (sweeping and s.sweep_range or 0)
		local d = wesnoth.map.distance_between(o.u.x, o.u.y, target.x, target.y)
		if d <= range and o.u.id ~= target.id then
			local ecm = 0
			for _i, j in ipairs(jammers) do
				if hostile(team, j.u.side) and j.p.ecm > ecm and
					(wesnoth.map.distance_between(j.u.x, j.u.y, target.x, target.y) <= j.p.ecm_range or
					 wesnoth.map.distance_between(j.u.x, j.u.y, o.u.x, o.u.y) <= j.p.ecm_range) then
					ecm = j.p.ecm
				end
			end
			local terms = {
				observer = o.u.id,
				sensor = o.p.sensor,
				sweep = sweeping and o.p.scan or 0,
				distance = d,
				range_loss = math.floor(d / s.falloff),
				jam = math.max(0, ecm - o.p.eccm - team.bonus.eccm),
				env = core.number(env_at(o.u.x, o.u.y).sensor, 0) + s.sensor_modifier,
				net = target.sig - target.mask,
			}
			terms.total = terms.sensor + terms.sweep - terms.range_loss - terms.jam + terms.env + terms.net
			for _i, hook in ipairs(ew.hooks.modify_score) do hook(o.u, target, terms) end
			if best == nil or terms.total > best.total or
				(terms.total == best.total and terms.observer < best.observer) then
				best = terms
			end
		end
	end
	return best
end

local function classify(terms, team, s)
	if not terms or terms.total < s.contact then return ew.NONE, nil end
	local identify = terms.total + team.bonus.identify
	if identify >= s.full then return ew.FULL, identify end
	if identify >= s.partial then return ew.PARTIAL, identify end
	return ew.CONTACT, identify
end

local function contact_image(state, class, visual, locked)
	if state == ew.CONTACT then return "misc/sw-contact.png" end
	if state == ew.PARTIAL then return "misc/sw-contact-" .. class .. ".png" end
	if state == ew.FULL and locked then return "misc/sw-contact-locked.png" end
	if state == ew.FULL and not visual then return "misc/sw-contact-" .. class .. "-id.png" end
	return nil
end

-- ---------------------------------------------------------------- refresh

local function item_name(rec)
	return "sw_ew|" .. rec.team .. "|" .. rec.key
end

local function expose_decoy(team, decoy, exposed_now)
	exposed_now[team.key .. "|" .. decoy.id] = true
	core.float_for_team(team.key, decoy.x, decoy.y, _ "false contact", "#ff9a5a")
	core.log("ew", "team " .. team.key .. " exposed decoy " .. decoy.id)
	for _i, hook in ipairs(ew.hooks.on_decoy_exposed) do hook(team.key, decoy) end
end

-- Recompute every team's sensor picture, concealment and overlays.
function ew.refresh()
	if ew.refreshing or not ew.is_ready() then return end
	ew.refreshing = true
	local ok, err = pcall(ew.refresh_now)
	ew.refreshing = false
	if not ok then error(err) end
end

function ew.refresh_now()
	ew.ensure_scenario()
	local s = ew.settings()
	local rules = terrain_rules(s)
	local env_cache = {}
	local function env_at(x, y)
		local k = core.key(x, y)
		local hit = env_cache[k]
		if hit == nil then
			hit = {}
			for _i, r in ipairs(rules) do
				if wesnoth.map.matches(x, y, { terrain = r.terrain }) then
					hit = { conceal = core.number(r.conceal, 0), sensor = core.number(r.sensor, 0) }
					break
				end
			end
			env_cache[k] = hit
		end
		return hit
	end

	-- Living units with their profiles, in a stable order.
	local units, jammers = {}, {}
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{})) do
		if u.hitpoints > 0 then
			local e = { u = u, p = ew.profile(u) }
			table.insert(units, e)
			if e.p.ecm > 0 then table.insert(jammers, e) end
		end
	end
	local teams, order = build_teams(s, units)

	-- Pass 1: a unit whose cloak is not active is not concealed, so the
	-- engine's own visibility can be read for it below.
	for _i, e in ipairs(units) do
		e.cloaked = ew.cloak_active(e.u, e.p)
		if not e.cloaked and e.u.status[ew.CONCEALED] then e.u.status[ew.CONCEALED] = false end
	end

	local reveals, reveal_source = {}, {}
	for _i, r in ipairs(wml.array_access.get("sw_ew_reveals")) do
		if wesnoth.current.turn < core.number(r.until_turn, 0) then
			local k = r.team .. "|" .. r.id
			reveals[k] = math.max(reveals[k] or 0, core.number(r.state, ew.FULL))
			reveal_source[k] = r.source or reveal_source[k]
		end
	end

	local old = {}
	for _i, rec in ipairs(wml.array_access.get("sw_ew_contacts")) do old[rec.team .. "|" .. rec.key] = rec end
	local records = {}
	local identified_by = {}   -- unit id -> true if some hostile team identified it

	for _i, key in ipairs(order) do
		local team = teams[key]
		for _i, e in ipairs(units) do
			local u = e.u
			if hostile(team, u.side) then
				local state, identify, terms, visual, locked = ew.NONE, nil, nil, false, false
				local env = env_at(u.x, u.y)
				local mask = (e.cloaked and e.p.cloak or 0) + core.number(env.conceal, 0)
				local target = { x = u.x, y = u.y, side = u.side, id = u.id, sig = emission(u, e.p, s), mask = mask }
				if not e.cloaked then
					-- Visible by ordinary sight: identified. Hidden by another
					-- (living) stealth ability on an unfogged hex: sensors
					-- cannot track it either -- Force Sense and keen senses can.
					local unfogged = not fogged_for_team(team, u.x, u.y)
					if unfogged then
						for _i, side in ipairs(team.sides) do
							if u:matches{ T.filter_vision{ side = side, visible = true } } then visual = true end
						end
					end
					if visual then
						state = ew.FULL
					elseif not unfogged then
						terms = best_score(team, target, s, jammers, env_at)
						state, identify = classify(terms, team, s)
					end
				else
					terms = best_score(team, target, s, jammers, env_at)
					state, identify = classify(terms, team, s)
				end
				local touching = adjacent_member(team, u.x, u.y)
				if touching then state = ew.FULL end
				local floor = reveals[key .. "|" .. u.id]
				if floor and floor > state then state = floor end
				if state == ew.FULL then identified_by[u.id] = true end
				if state > ew.NONE then
					if e.cloaked and state == ew.FULL then locked = true end
					local class = e.p.class
					if state < ew.FULL and e.p.disguise and ew.CLASS_DEFAULTS[e.p.disguise] then class = e.p.disguise end
					local rec = {
						team = key, key = "u:" .. u.id, id = u.id, x = u.x, y = u.y, side = u.side,
						state = state, class = class, type = state == ew.FULL and u.type or "",
						visual = visual, cloaked = e.cloaked, adjacent = touching ~= nil,
					}
					if terms then
						rec.score = terms.total; rec.identify = identify or terms.total
						rec.sensor = terms.sensor; rec.sweep = terms.sweep; rec.range_loss = terms.range_loss
						rec.distance = terms.distance; rec.jam = terms.jam; rec.env = terms.env; rec.net = terms.net
						rec.observer = terms.observer; rec.doctrine = team.bonus.identify
					end
					if not terms and reveal_source[key .. "|" .. u.id] then rec.source = reveal_source[key .. "|" .. u.id] end
					rec.image = team.human and contact_image(state, class, visual, locked) or nil
					table.insert(records, rec)
				end
			end
		end
	end

	-- Decoys: false contacts, scored like real ones from their own signature.
	local decoys = wml.array_access.get("sw_ew_decoys")
	local exposed_now = {}
	for _i, d in ipairs(decoys) do
		local exposed = {}
		for _i, k in ipairs(core.split(d.exposed)) do exposed[k] = true end
		for _i, key in ipairs(order) do
			local team = teams[key]
			if hostile(team, d.side) and not exposed[key] then
				local env = env_at(d.x, d.y)
				local target = { x = d.x, y = d.y, side = d.side, id = d.id,
					sig = core.number(d.signature, s.decoy_signature), mask = core.number(env.conceal, 0) }
				local terms = best_score(team, target, s, jammers, env_at)
				local state, identify = classify(terms, team, s)
				local deception = core.number(d.deception, s.decoy_deception) - team.bonus.discrimination
				local touching = adjacent_member(team, d.x, d.y)
				if touching or (identify and identify >= s.full + deception) then
					expose_decoy(team, d, exposed_now)
					exposed[key] = true
				elseif state > ew.NONE then
					local visual_hex = not fogged_for_team(team, d.x, d.y)
					-- In plain sight there is visibly nothing there, so a decoy
					-- can only pass for a cloaked (classified) contact; under
					-- fog it can pass for an identified ship.
					if state == ew.FULL and visual_hex then state = ew.PARTIAL end
					local rec = {
						team = key, key = "d:" .. d.id, id = d.id, x = d.x, y = d.y, side = d.side,
						state = state, class = d.class, type = state == ew.FULL and d.type or "",
						visual = false, cloaked = false, adjacent = false, decoy = true,
						score = terms.total, identify = identify, sensor = terms.sensor, sweep = terms.sweep,
						range_loss = terms.range_loss, distance = terms.distance, jam = terms.jam, env = terms.env,
						net = terms.net, observer = terms.observer, doctrine = team.bonus.identify,
					}
					rec.image = team.human and contact_image(state, d.class, false, false) or nil
					table.insert(records, rec)
				end
			end
		end
		local list = core.sorted_keys(exposed)
		d.exposed = table.concat(list, ",")
	end
	wml.array_access.set("sw_ew_decoys", decoys)

	-- Engine concealment: hidden while no hostile team has identified it.
	for _i, e in ipairs(units) do
		if e.cloaked then
			local conceal = not identified_by[e.u.id]
			if (e.u.status[ew.CONCEALED] == true) ~= conceal then
				e.u.status[ew.CONCEALED] = conceal
				core.log("ew", e.u.id .. (conceal and " concealed" or " revealed (identified)"))
			end
		end
		ew.update_indicator(e.u, e.p)
	end

	-- Overlays and transitions, diffed against the previous picture.
	local changed = false
	local new = {}
	for _i, rec in ipairs(records) do new[rec.team .. "|" .. rec.key] = rec end
	for _i, k in ipairs(core.sorted_keys(old)) do
		local o, n = old[k], new[k]
		if o.image and (not n or n.image ~= o.image or n.x ~= o.x or n.y ~= o.y) then
			wesnoth.interface.remove_item(o.x, o.y, item_name(o))
			changed = true
		end
	end
	for _i, rec in ipairs(records) do
		local o = old[rec.team .. "|" .. rec.key]
		if rec.image and (not o or o.image ~= rec.image or o.x ~= rec.x or o.y ~= rec.y) then
			wesnoth.wml_actions.item{ x = rec.x, y = rec.y, image = rec.image, name = item_name(rec),
				team_name = rec.team, visible_in_fog = true, redraw = false }
			changed = true
		end
		local before = o and core.number(o.state, 0) or 0
		if before ~= rec.state then
			core.log("ew", "team " .. rec.team .. ": " .. rec.key .. " " .. before .. " -> " .. rec.state ..
				(rec.score and (" (score " .. rec.score .. ", identify " .. tostring(rec.identify) .. ")") or " (visual)"))
			for _i, hook in ipairs(ew.hooks.on_state_change) do hook(rec.team, rec, before) end
		end
	end
	for _i, k in ipairs(core.sorted_keys(old)) do
		if not new[k] then
			core.log("ew", "team " .. old[k].team .. ": lost " .. old[k].key)
			local gone = { team = old[k].team, key = old[k].key, id = old[k].id, state = ew.NONE }
			for _i, hook in ipairs(ew.hooks.on_state_change) do hook(old[k].team, gone, core.number(old[k].state, 0)) end
		end
	end
	wml.array_access.set("sw_ew_contacts", records)
	if changed then wesnoth.wml_actions.redraw{} end
end

-- ---------------------------------------------------------------- queries

function ew.team_of_side(side)
	return core.team_key(side)
end

-- The team's contact record for a unit (or decoy) id, or nil.
function ew.record(team, id)
	for _i, rec in ipairs(wml.array_access.get("sw_ew_contacts")) do
		if rec.team == team and rec.id == id then return rec end
	end
	return nil
end

-- Detection state of a unit for a team (0 if unknown to it).
function ew.state_for(team, id)
	local rec = ew.record(team, id)
	return rec and core.number(rec.state, 0) or ew.NONE
end

-- The team's contact records on a hex (as its players see them: real
-- contacts and undetected-as-false decoys look the same).
function ew.contacts_at(team, x, y)
	local out = {}
	for _i, rec in ipairs(wml.array_access.get("sw_ew_contacts")) do
		if rec.team == team and rec.x == x and rec.y == y and rec.image then table.insert(out, rec) end
	end
	return out
end

function ew.contacts_of(team)
	local out = {}
	for _i, rec in ipairs(wml.array_access.get("sw_ew_contacts")) do
		if rec.team == team then table.insert(out, rec) end
	end
	return out
end

-- ---------------------------------------------------------------- indicators

function ew.update_indicator(u, p)
	p = p or ew.profile(u)
	local image = nil
	if u.variables.sw_ew_sweep then image = "misc/sw-ew-sweep.png"
	elseif p.cloak > 0 and ew.cloak_active(u, p) then image = "misc/sw-ew-cloak.png"
	elseif p.ecm > 0 then image = "misc/sw-ew-ecm.png" end
	core.set_overlay(u, "ew", image)
end

-- ---------------------------------------------------------------- actions

-- Active sensor sweep: commits the unit's attack this turn; until its side's
-- next turn it adds its scan rating and +sweep_range to its sensors, and its
-- own emissions rise (it is easier to detect).
function ew.can_sweep(u)
	local p = ew.profile(u)
	if p.scan <= 0 then return false, _ "no active sensors" end
	if u.variables.sw_ew_sweep then return false, _ "already sweeping" end
	if u.attacks_left < 1 then return false, _ "no attack left" end
	return true
end

function ew.sweep(u)
	local ok, why = ew.can_sweep(u)
	if not ok then core.log("ew", u.id .. " cannot sweep: " .. tostring(why)) return false end
	local team = core.team_key(u.side)
	local before = 0
	for _i, rec in ipairs(ew.contacts_of(team)) do if not rec.visual then before = before + 1 end end
	u.attacks_left = 0
	u.variables.sw_ew_sweep = true
	ew.update_indicator(u)
	ew.refresh()
	local after = 0
	for _i, rec in ipairs(ew.contacts_of(team)) do if not rec.visual then after = after + 1 end end
	core.float_for_team(team, u.x, u.y, tostring(_ "sensor sweep:") .. " " .. after .. " " .. tostring(_ "contact(s)"), "#9fe8ff")
	core.log("ew", u.id .. " sweeps: " .. before .. " -> " .. after .. " sensor contacts")
	if ew.on_tactic then ew.on_tactic(u, "sweep") end
	return true
end

function ew.can_decoy(u)
	local p = ew.profile(u)
	if p.decoys <= 0 then return false, _ "no decoys" end
	if core.number(u.variables.sw_ew_decoys_used, 0) >= p.decoys then return false, _ "decoys expended" end
	if u.attacks_left < 1 then return false, _ "no attack left" end
	return true
end

-- Hexes a decoy can be launched to: decoy_range hexes out in each of the six
-- directions, on the map. Occupancy is not checked (a hidden enemy's hex is
-- valid, so the list leaks nothing).
function ew.decoy_hexes(u)
	local s = ew.settings()
	local out = {}
	for _i, dir in ipairs{ "n", "ne", "se", "s", "sw", "nw" } do
		local loc = { u.x, u.y }
		for _n = 1, s.decoy_range do
			local nxt = wesnoth.map.get_direction(loc, dir)
			loc = { nxt[1] or nxt.x, nxt[2] or nxt.y }
		end
		if wesnoth.current.map:on_board(loc[1], loc[2]) then
			table.insert(out, { x = loc[1], y = loc[2], dir = dir })
		end
	end
	return out
end

-- Add a decoy (false contact). cfg: x, y, side, class, type, signature,
-- deception, turns. Used by units and by the [sw_ew_decoy] tag.
function ew.add_decoy(cfg)
	ew.ensure_scenario()
	local s = ew.settings()
	local serial = core.number(wml.variables.sw_ew_decoy_serial, 0) + 1
	wml.variables.sw_ew_decoy_serial = serial
	local decoys = wml.array_access.get("sw_ew_decoys")
	local class = cfg.class
	if not ew.CLASS_DEFAULTS[class or ""] then class = "capital" end
	table.insert(decoys, {
		id = "decoy" .. serial, x = cfg.x, y = cfg.y, side = cfg.side, class = class, type = cfg.type or "",
		signature = core.number(cfg.signature, s.decoy_signature),
		deception = core.number(cfg.deception, s.decoy_deception),
		expires = wesnoth.current.turn + core.number(cfg.turns, s.decoy_turns), exposed = "",
	})
	wml.array_access.set("sw_ew_decoys", decoys)
	core.log("ew", "decoy" .. serial .. " at " .. cfg.x .. "," .. cfg.y .. " for side " .. cfg.side .. " as " .. class)
	ew.refresh()
	return "decoy" .. serial
end

function ew.deploy_decoy(u, x, y)
	local ok, why = ew.can_decoy(u)
	if not ok then core.log("ew", u.id .. " cannot deploy a decoy: " .. tostring(why)) return nil end
	local p = ew.profile(u)
	u.attacks_left = 0
	u.variables.sw_ew_decoys_used = core.number(u.variables.sw_ew_decoys_used, 0) + 1
	return ew.add_decoy{ x = x, y = y, side = u.side, class = p.decoy_class or p.class,
		type = p.decoy_type or u.type }
end

-- Scenario intelligence: a team learns of a unit at least to the given state
-- for a number of turns.
-- source: "intelligence" (default) or "force" (Force Sense), shown in the
-- Sensor contact description.
function ew.reveal(u, team, state, turns, source)
	ew.ensure_scenario()
	local reveals = wml.array_access.get("sw_ew_reveals")
	table.insert(reveals, { team = team, id = u.id, state = state or ew.FULL,
		until_turn = wesnoth.current.turn + (turns or 1), source = source or "intelligence" })
	wml.array_access.set("sw_ew_reveals", reveals)
	core.log("ew", "team " .. team .. " given intelligence on " .. u.id .. " (state " .. (state or ew.FULL) .. ")")
	ew.refresh()
end

-- ---------------------------------------------------------------- turn cycle

function ew.on_prestart()
	ew.ensure_scenario()
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{})) do
		u.variables.sw_ew_sweep = nil
		u.variables.sw_ew_fired = nil
		u.variables.sw_ew_decoys_used = nil
	end
	ew.refresh()
end

-- Start of a side's turn: its sweeps and firing emissions end, decoys it
-- launched may expire, intelligence reveals expire.
function ew.on_side_turn(side)
	ew.ensure_scenario()
	for _i, u in ipairs(wesnoth.units.find_on_map{ side = side }) do
		u.variables.sw_ew_sweep = nil
		u.variables.sw_ew_fired = nil
	end
	local keep = {}
	for _i, d in ipairs(wml.array_access.get("sw_ew_decoys")) do
		if not (d.side == side and wesnoth.current.turn >= core.number(d.expires, 0)) then table.insert(keep, d) end
	end
	wml.array_access.set("sw_ew_decoys", keep)
	local reveals = {}
	for _i, r in ipairs(wml.array_access.get("sw_ew_reveals")) do
		if wesnoth.current.turn < core.number(r.until_turn, 0) then table.insert(reveals, r) end
	end
	wml.array_access.set("sw_ew_reveals", reveals)
	ew.refresh()
end

-- attack event: both combatants are emitting this turn; an attacking cloaked
-- unit drops its cloak until its next turn.
function ew.on_attack()
	local ctx = wesnoth.current.event_context
	for _i, loc in ipairs{ { ctx.x1, ctx.y1 }, { ctx.x2, ctx.y2 } } do
		local u = wesnoth.units.get(loc[1], loc[2])
		if u then u.variables.sw_ew_fired = true end
	end
end

-- AI sides sweep at the end of their turn when a unit kept its attack and
-- the team holds unidentified contacts (so their overwatch can see them).
-- Disable with sw_ew_ai=no.
function ew.on_side_turn_end(side)
	if wml.variables.sw_ew_ai == false or wml.variables.sw_ew_ai == "no" then return end
	if wesnoth.sides[side].controller ~= "ai" then return end
	local team = core.team_key(side)
	local unidentified = false
	for _i, rec in ipairs(ew.contacts_of(team)) do
		if core.number(rec.state, 0) < ew.FULL then unidentified = true end
	end
	if not unidentified then return end
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ side = side })) do
		if ew.can_sweep(u) then ew.sweep(u) return end
	end
end

-- ---------------------------------------------------------------- configuration

-- [sw_ew_settings] contact= partial= full= falloff= sweep_range= ... sensor_modifier=
-- default_terrain=yes|no, [terrain] terrain= conceal= sensor= [/terrain] (replaces
-- earlier scenario rules; checked before the defaults).
function ew.configure(cfg)
	ew.ensure_scenario()
	local current = wml.variables.sw_ew_settings
	local merged = {}
	if type(current) == "table" then for k, v in pairs(current) do if type(k) == "string" then merged[k] = v end end end
	for k, v in pairs(cfg) do
		if type(k) == "string" and (ew.DEFAULT_SETTINGS[k] ~= nil or k == "default_terrain") then merged[k] = v end
	end
	wml.variables.sw_ew_settings = merged
	local rules = {}
	for _i, r in ipairs(wml.child_array(cfg, "terrain")) do
		table.insert(rules, { terrain = r.terrain, conceal = core.number(r.conceal, 0), sensor = core.number(r.sensor, 0) })
	end
	if #rules > 0 then wml.array_access.set("sw_ew_terrain", rules) end
	ew.refresh()
end

-- [sw_ew_profile] [filter] SUF [/filter] sensor= ... decoys= class= disguise_class= :
-- per-unit overrides. A unit given a cloak also gets the concealment [hides].
function ew.set_profile(u, cfg)
	for _i, f in ipairs(ew.FIELDS) do
		if cfg[f] ~= nil then u.variables["sw_ew_" .. f] = core.number(cfg[f], 0) end
	end
	if cfg.class then u.variables.sw_ew_class = cfg.class end
	if cfg.disguise_class then u.variables.sw_ew_disguise = cfg.disguise_class end
	if core.number(cfg.cloak, 0) > 0 and not u:matches{ ability = ew.CLOAK_HIDES } then
		u:add_modification("object", { id = "sw_ew_cloak_device", T.effect{ apply_to = "new_ability",
			T.abilities{ ew.cloak_hides_cfg() } } })
	end
end

-- The concealment [hides] (also generated into cloaked unit types).
function ew.cloak_hides_cfg()
	return T.hides{
		id = ew.CLOAK_HIDES,
		name = _ "cloaked",
		description = _ "A cloaking field hides this unit until an enemy team identifies it (sensor sweeps, close sensors or physical contact) or it fires. Partial sensor contacts are shown to the enemy as markers.",
		affect_self = true,
		T.filter{ status = ew.CONCEALED },
	}
end

-- ---------------------------------------------------------------- menus / text

local function viewing_team()
	local side = core.viewing_side()
	if not side or side < 1 or side > #wesnoth.sides then return nil end
	return core.team_key(side), side
end

function ew.sweep_menu_visible()
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	return u ~= nil and core.is_local_turn_of(u.side) and ew.profile(u).scan > 0 and (ew.can_sweep(u))
end

function ew.sweep_menu_command()
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if u then ew.sweep(u) end
end

function ew.decoy_menu_visible()
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	return u ~= nil and core.is_local_turn_of(u.side) and ew.profile(u).decoys > 0 and (ew.can_decoy(u))
end

local DIR_NAMES = { n = _ "north", ne = _ "north-east", se = _ "south-east", s = _ "south", sw = _ "south-west", nw = _ "north-west" }

function ew.decoy_menu_command()
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u then return end
	local hexes = ew.decoy_hexes(u)
	local labels = {}
	for _i, h in ipairs(hexes) do
		table.insert(labels, tostring(DIR_NAMES[h.dir]) .. " (" .. h.x .. "," .. h.y .. ")")
	end
	table.insert(labels, tostring(_ "Cancel"))
	local p = ew.profile(u)
	local pick = core.choose(_ "Sensor decoy",
		tostring(_ "Launch a decoy that enemy sensors read as a") .. " " .. tostring(ew.CLASS_NAMES[p.decoy_class or p.class]) ..
		". " .. tostring(_ "It lasts until your turn after next, or until enemy sensors see through it. Uses this turn's attack.") ..
		" (" .. (p.decoys - core.number(u.variables.sw_ew_decoys_used, 0)) .. " " .. tostring(_ "left") .. ")",
		labels)
	local h = hexes[pick]
	if h then ew.deploy_decoy(u, h.x, h.y) end
end

-- "Sensor contact" appears on a hex only where the viewing team has a drawn
-- contact (so it never hints at undetected units).
function ew.contact_menu_visible()
	local team = viewing_team()
	if not team then return false end
	local ctx = core.menu_context()
	return #ew.contacts_at(team, ctx.x1, ctx.y1) > 0
end

function ew.describe(rec, s)
	s = s or ew.settings()
	local state = core.number(rec.state, 0)
	local lines = {}
	local head = tostring(ew.STATE_NAMES[state])
	if state >= ew.PARTIAL then head = head .. ": " .. tostring(ew.CLASS_NAMES[rec.class] or rec.class) end
	if state == ew.FULL and rec.type ~= "" and wesnoth.unit_types[rec.type] then
		head = head .. " — " .. tostring(wesnoth.unit_types[rec.type].name)
	end
	table.insert(lines, "<b>" .. head .. "</b>")
	if rec.adjacent then
		table.insert(lines, tostring(_ "In physical contact with your forces."))
	elseif rec.score then
		table.insert(lines, tostring(_ "Sensor strength") .. " " .. rec.score ..
			"  (" .. tostring(_ "contact") .. " ≥" .. s.contact .. ", " .. tostring(_ "classify") .. " ≥" .. s.partial ..
			", " .. tostring(_ "identify") .. " ≥" .. s.full .. ")")
		local parts = { tostring(_ "sensors") .. " +" .. rec.sensor }
		if core.number(rec.sweep, 0) > 0 then table.insert(parts, tostring(_ "sweep") .. " +" .. rec.sweep) end
		table.insert(parts, tostring(_ "range") .. " " .. rec.distance .. " −" .. rec.range_loss)
		if core.number(rec.jam, 0) > 0 then table.insert(parts, tostring(_ "jamming") .. " −" .. rec.jam) end
		if core.number(rec.env, 0) ~= 0 then table.insert(parts, tostring(_ "environment") .. " " .. rec.env) end
		table.insert(parts, tostring(_ "target emissions (net of cloak and cover)") .. " " .. rec.net)
		if core.number(rec.doctrine, 0) > 0 then table.insert(parts, tostring(_ "doctrine identification") .. " +" .. rec.doctrine) end
		table.insert(lines, table.concat(parts, ", "))
		if state < ew.FULL then
			table.insert(lines, tostring(_ "To identify: an active sweep, closer sensors, ECCM against jamming, or contact."))
		end
	elseif rec.source == "force" then
		table.insert(lines, tostring(_ "Felt through the Force: a living presence, not yet seen."))
	else
		table.insert(lines, tostring(_ "From intelligence reports."))
	end
	return table.concat(lines, "\n")
end

function ew.contact_menu_command()
	local team = core.team_key(wesnoth.current.side)
	local ctx = core.menu_context()
	local recs = ew.contacts_at(team, ctx.x1, ctx.y1)
	local texts = {}
	local s = ew.settings()
	for _i, rec in ipairs(recs) do table.insert(texts, ew.describe(rec, s)) end
	wesnoth.wml_actions.message{ speaker = "narrator", caption = _ "Sensor contact", image = "misc/sw-contact.png",
		side_for = wesnoth.current.side,
		message = table.concat(texts, "\n\n") }
end

-- Lines for the Tactical status window of a unit visible to the viewer.
function ew.status_lines(u, viewer_team)
	local p = ew.profile(u)
	local lines = {}
	local parts = { tostring(ew.CLASS_NAMES[p.class]),
		tostring(_ "sensors") .. " " .. p.sensor .. "/" .. p.sensor_range .. " " .. tostring(_ "hexes"),
		tostring(_ "signature") .. " " .. p.signature }
	if p.cloak > 0 then
		table.insert(parts, tostring(_ "cloak") .. " " .. p.cloak .. " (" ..
			tostring(ew.cloak_active(u, p) and _ "active" or _ "down: fired this turn") .. ")")
	end
	if p.ecm > 0 then table.insert(parts, tostring(_ "ECM") .. " " .. p.ecm .. "/" .. p.ecm_range .. " " .. tostring(_ "hexes")) end
	if p.eccm > 0 then table.insert(parts, tostring(_ "ECCM") .. " " .. p.eccm) end
	if p.scan > 0 then table.insert(parts, tostring(_ "sweep") .. " +" .. p.scan) end
	table.insert(lines, tostring(_ "Sensors & EW:") .. " " .. table.concat(parts, ", "))
	if u.variables.sw_ew_sweep then table.insert(lines, tostring(_ "Sweeping: sensors boosted, emissions raised until its next turn.")) end
	if viewer_team and core.team_key(u.side) ~= viewer_team then
		local rec = ew.record(viewer_team, u.id)
		if rec and not rec.visual then
			table.insert(lines, tostring(_ "Your sensors:") .. " " .. tostring(ew.STATE_NAMES[core.number(rec.state, 0)]))
		end
	end
	return lines
end

return ew
