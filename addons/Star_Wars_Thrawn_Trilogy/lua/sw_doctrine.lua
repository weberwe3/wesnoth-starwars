-- Star Wars: Thrawn Trilogy -- Thrawn Doctrine (tactical intelligence).
--
-- A designated side ("doctrine side") accumulates Insight by observing the
-- behaviour of the enemy sides it watches -- but only what it can actually
-- observe: actions of units its team sees or tracks on sensors (sw_ew
-- contact state partially identified or better; studying a unit type needs
-- full identification). Categories:
--   move       heading of completed enemy moves
--   attack     damage type and range of enemy attacks
--   target     what enemy attacks pick (leaders, wounded, isolated, Force users, front line)
--   recruit    class of enemy reinforcements
--   formation  tight or dispersed enemy positions at the end of their turn
--   tactic     overwatch, sensor sweeps, decoys, Force powers
--   composition  each newly identified enemy unit type
-- Each observation adds its gain, limited per category per turn
-- (turn_limit). A pattern is recognised when one key reaches pattern_min
-- observations and pattern_share percent of its category; recognition adds
-- a one-off bonus. Insight never exceeds the cap.
--
-- Tiers unlock explicit effects (thresholds and values configurable):
--   summary       intelligence summary of the enemy force it has seen and tracks
--   patterns      recognised patterns listed in the summary
--   sensors       +identify / +eccm / +discrimination to its team's sensors
--                 (cloaks and jamming still apply: contact itself is not improved)
--   prediction    marks its own units most likely to be attacked next, from the
--                 recognised target pattern and known enemy positions
--   coordination  +accuracy (chance to hit, also overwatch) against studied enemy types
--
-- Scenario control (WML tag [sw_doctrine] or Lua): enable / disable / cap /
-- reset / seed / grant (Cultural and Art Intelligence: insight, studied types
-- and patterns from captured art, archives, interrogations or objectives).
-- State: container sw_doctrine_s<side> (stamped with the scenario id; kept
-- across missions only with persist=yes), list sw_doctrine_sides.

local T = wml.tag
local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local ew = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ew.lua")
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local doctrine = {}

doctrine.CATEGORIES = { "move", "attack", "target", "recruit", "formation", "tactic", "composition" }
doctrine.DEFAULTS = { cap = 100, turn_limit = 2, pattern_min = 4, pattern_share = 50, study_min = 3 }
doctrine.DEFAULT_GAINS = { move = 1, attack = 1, target = 1, recruit = 1, formation = 1, tactic = 2, composition = 1, pattern = 3 }
doctrine.DEFAULT_TIERS = {
	{ insight = 10, effect = "summary" },
	{ insight = 25, effect = "patterns" },
	{ insight = 40, effect = "sensors", identify = 2, eccm = 2, discrimination = 2 },
	{ insight = 60, effect = "prediction", targets = 3 },
	{ insight = 80, effect = "coordination", accuracy = 10 },
}
doctrine.EFFECT_NAMES = {
	summary = _ "Intelligence summary", patterns = _ "Pattern recognition", sensors = _ "Sensor doctrine",
	prediction = _ "Prediction", coordination = _ "Coordinated fire",
}
doctrine.TARGET_NAMES = {
	leader = _ "commanders", force_user = _ "Force-sensitive", wounded = _ "wounded",
	isolated = _ "isolated", frontline = _ "front-line",
}
doctrine.DIR_NAMES = { n = _ "north", ne = _ "north-east", se = _ "south-east", s = _ "south", sw = _ "south-west", nw = _ "north-west" }

-- Hooks: on_observe(side, category, key, gained), on_tier(side, tier),
-- on_grant(side, amount, source). Future command networks and scenario
-- deception can react to the doctrine through these.
doctrine.hooks = { on_observe = {}, on_tier = {}, on_grant = {} }

-- ---------------------------------------------------------------- storage

local function var_name(side) return "sw_doctrine_s" .. side end

local function sides_list()
	local out = {}
	for _i, s in ipairs(core.split(wml.variables.sw_doctrine_sides)) do table.insert(out, tonumber(s)) end
	table.sort(out)
	return out
end

local function set_sides_list(list)
	table.sort(list)
	local strs = {}
	for _i, s in ipairs(list) do table.insert(strs, tostring(s)) end
	wml.variables.sw_doctrine_sides = table.concat(strs, ",")
end

local function new_state(side)
	local d = { side = side, enabled = false, insight = 0, tier_reached = 0, scenario = core.scenario_id(),
		persist = false, watch = "", budget_turn = 0, tiers = {}, gains = {}, patterns = {}, studied = {},
		recognized = {}, budget = {}, log = {}, predicted = {}, catalogued = {} }
	for k, v in pairs(doctrine.DEFAULTS) do d[k] = v end
	for k, v in pairs(doctrine.DEFAULT_GAINS) do d.gains[k] = v end
	for _i, t in ipairs(doctrine.DEFAULT_TIERS) do
		local copy = {}
		for k, v in pairs(t) do copy[k] = v end
		table.insert(d.tiers, copy)
	end
	return d
end

function doctrine.load(side)
	local raw = wml.variables[var_name(side)]
	if type(raw) ~= "table" or raw.scenario == nil then return nil end
	local d = new_state(side)
	d.enabled = raw.enabled == true
	d.insight = core.number(raw.insight, 0)
	d.tier_reached = core.number(raw.tier_reached, 0)
	d.scenario = raw.scenario
	d.persist = raw.persist == true
	d.watch = raw.watch or ""
	d.budget_turn = core.number(raw.budget_turn, 0)
	for k in pairs(doctrine.DEFAULTS) do d[k] = core.number(raw[k], d[k]) end
	local tiers = wml.child_array(raw, "tier")
	if #tiers > 0 then
		d.tiers = {}
		for _i, t in ipairs(tiers) do
			local copy = {}
			for k, v in pairs(t) do if type(k) == "string" then copy[k] = v end end
			copy.insight = core.number(copy.insight, 0)
			table.insert(d.tiers, copy)
		end
	end
	local gains = wml.get_child(raw, "gains")
	if gains then for k, v in pairs(gains) do if type(k) == "string" then d.gains[k] = core.number(v, 0) end end end
	for _i, p in ipairs(wml.child_array(raw, "pattern")) do
		d.patterns[p.category] = d.patterns[p.category] or {}
		d.patterns[p.category][p.key] = core.number(p.count, 0)
	end
	for _i, p in ipairs(wml.child_array(raw, "studied")) do d.studied[p.type] = core.number(p.count, 0) end
	for _i, p in ipairs(wml.child_array(raw, "recognized")) do d.recognized[p.category .. "|" .. p.key] = true end
	for _i, p in ipairs(wml.child_array(raw, "budget")) do d.budget[p.category] = core.number(p.used, 0) end
	for _i, p in ipairs(wml.child_array(raw, "catalogued")) do d.catalogued[p.type] = true end
	for _i, p in ipairs(wml.child_array(raw, "log")) do
		table.insert(d.log, { source = p.source, text = p.text, amount = core.number(p.amount, 0), turn = core.number(p.turn, 0) })
	end
	for _i, p in ipairs(wml.child_array(raw, "predicted")) do
		table.insert(d.predicted, { id = p.id, x = core.number(p.x, 0), y = core.number(p.y, 0) })
	end
	return d
end

function doctrine.save(d)
	local out = { enabled = d.enabled, insight = d.insight, tier_reached = d.tier_reached, scenario = d.scenario,
		persist = d.persist, watch = d.watch, budget_turn = d.budget_turn }
	for k in pairs(doctrine.DEFAULTS) do out[k] = d[k] end
	for _i, t in ipairs(d.tiers) do table.insert(out, T.tier(t)) end
	local gains = {}
	for _i, k in ipairs(core.sorted_keys(d.gains)) do gains[k] = d.gains[k] end
	table.insert(out, T.gains(gains))
	for _i, cat in ipairs(core.sorted_keys(d.patterns)) do
		for _i, key in ipairs(core.sorted_keys(d.patterns[cat])) do
			table.insert(out, T.pattern{ category = cat, key = key, count = d.patterns[cat][key] })
		end
	end
	for _i, ty in ipairs(core.sorted_keys(d.studied)) do table.insert(out, T.studied{ type = ty, count = d.studied[ty] }) end
	for _i, k in ipairs(core.sorted_keys(d.recognized)) do
		local cat, key = k:match("^([^|]*)|(.*)$")
		table.insert(out, T.recognized{ category = cat, key = key })
	end
	for _i, cat in ipairs(core.sorted_keys(d.budget)) do table.insert(out, T.budget{ category = cat, used = d.budget[cat] }) end
	for _i, ty in ipairs(core.sorted_keys(d.catalogued)) do table.insert(out, T.catalogued{ type = ty }) end
	for i = math.max(1, #d.log - 7), #d.log do table.insert(out, T.log(d.log[i])) end
	for _i, p in ipairs(d.predicted) do table.insert(out, T.predicted(p)) end
	wml.variables[var_name(d.side)] = out
end

-- Stale doctrine state from an earlier mission is dropped unless persist=yes.
function doctrine.ensure_scenario()
	local id = core.scenario_id()
	local keep = {}
	for _i, side in ipairs(sides_list()) do
		local d = doctrine.load(side)
		if d and (d.scenario == id or d.persist) then
			if d.scenario ~= id then
				d.scenario = id
				d.predicted = {}
				doctrine.save(d)
			end
			table.insert(keep, side)
		else
			wml.variables[var_name(side)] = nil
		end
	end
	set_sides_list(keep)
end

-- ---------------------------------------------------------------- tiers

function doctrine.tier_count(d)
	local n = 0
	for _i, t in ipairs(d.tiers) do if d.insight >= t.insight then n = n + 1 end end
	return n
end

-- The unlocked tier providing an effect, or nil.
function doctrine.effect(d, effect)
	if not d or not d.enabled then return nil end
	for _i, t in ipairs(d.tiers) do
		if t.effect == effect and d.insight >= t.insight then return t end
	end
	return nil
end

function doctrine.enabled_sides()
	local out = {}
	for _i, side in ipairs(sides_list()) do
		local d = doctrine.load(side)
		if d and d.enabled and side <= #wesnoth.sides then table.insert(out, d) end
	end
	return out
end

-- Does doctrine side d watch this side?
local function watches(d, side)
	if not wesnoth.sides.is_enemy(d.side, side) then return false end
	if d.watch == "" then return true end
	for _i, s in ipairs(core.split(d.watch)) do if tonumber(s) == side then return true end end
	return false
end

local function top_key(counts)
	local best, best_n, total = nil, -1, 0
	for _i, k in ipairs(core.sorted_keys(counts or {})) do
		total = total + counts[k]
		if counts[k] > best_n then best, best_n = k, counts[k] end
	end
	return best, best_n, total
end

-- A recognised pattern for a category: key, count, total (or nil).
function doctrine.pattern(d, category)
	local key, n, total = top_key(d.patterns[category])
	if key and total >= d.pattern_min and n * 100 >= d.pattern_share * total then return key, n, total end
	return nil
end

-- ---------------------------------------------------------------- effects

local function leaders_of(side)
	local out = {}
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ side = side })) do
		if u.canrecruit or u:matches{ ability = "sw_ability_tactical_genius" } then table.insert(out, u) end
	end
	return out
end

function doctrine.update_indicator(d)
	local n = d.enabled and math.min(5, doctrine.tier_count(d)) or nil
	for _i, u in ipairs(leaders_of(d.side)) do
		core.set_overlay(u, "intel", n and ("misc/sw-insight-" .. n .. ".png") or nil)
	end
end

-- The coordinated-fire ability. Added once to each unit of the doctrine
-- side (adding never rebuilds the unit); it is active only while the unit
-- has status sw_doctrine_coordination (tier unlocked) and only against
-- opponents with status sw_studied_s<side>. Its tooltip states both.
local function coordination_object(d, u)
	local tier = nil
	for _i, t in ipairs(d.tiers) do if t.effect == "coordination" then tier = t end end
	if not tier or u.variables.sw_doctrine_coord_obj then return end
	local add = core.number(tier.accuracy, 10)
	u:add_modification("object", { id = "sw_doctrine_coordination", T.effect{ apply_to = "new_ability", T.abilities{
		T.chance_to_hit{
			id = "sw_ability_doctrine_coordination",
			name = _ "doctrine: coordinated fire",
			description = tostring(_ "Thrawn's doctrine (Coordinated fire tier): +") .. add ..
				tostring(_ "% chance to hit enemies of a kind his staff has studied (seen in action at least three times). Inactive until the side's Insight reaches that tier."),
			add = add, affect_self = true, cumulative = true,
			T.filter{ status = "sw_doctrine_coordination" },
			T.filter_opponent{ status = "sw_studied_s" .. d.side },
		} } } })
	u.variables.sw_doctrine_coord_obj = d.side
end

-- Apply the state of every effect (idempotent; statuses never rebuild units).
function doctrine.apply_effects(d)
	local coord = doctrine.effect(d, "coordination") ~= nil
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ side = d.side })) do
		if d.enabled then coordination_object(d, u) end
		u.status.sw_doctrine_coordination = coord
	end
	local status = "sw_studied_s" .. d.side
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{})) do
		local studied = coord and watches(d, u.side) and core.number(d.studied[u.type], 0) >= d.study_min
		if (u.status[status] == true) ~= studied then u.status[status] = studied end
	end
	doctrine.update_indicator(d)
end

local function check_tiers(d)
	local n = doctrine.tier_count(d)
	if n ~= d.tier_reached then
		local old = d.tier_reached
		d.tier_reached = n
		if n > old then
			for i = old + 1, n do
				local t = d.tiers[i]
				core.log("doctrine", "side " .. d.side .. " unlocks " .. tostring(t.effect) .. " at " .. d.insight)
				for _i, leader in ipairs(leaders_of(d.side)) do
					if leader:matches{ T.filter_vision{ side = core.viewing_side() or d.side, visible = true } } then
						core.float(leader.x, leader.y, tostring(_ "doctrine:") .. " " ..
							tostring(doctrine.EFFECT_NAMES[t.effect] or t.effect), "#c9a6ff")
					end
					break
				end
				for _i, hook in ipairs(doctrine.hooks.on_tier) do hook(d.side, t) end
			end
		end
		return true
	end
	return false
end

-- Persist, then apply any effect change (and the sensor bonus).
local function commit(d)
	local changed = check_tiers(d)
	doctrine.save(d)
	if changed then
		doctrine.apply_effects(d)
		ew.refresh()
	else
		doctrine.update_indicator(d)
	end
end

-- ---------------------------------------------------------------- observation

local function add_insight(d, amount)
	d.insight = math.max(0, math.min(d.cap, d.insight + amount))
end

-- Record one observation for doctrine side d. Returns the insight gained.
function doctrine.record(d, category, key, actor_type)
	if not d.enabled then return 0 end
	if d.budget_turn ~= wesnoth.current.turn then
		d.budget = {}
		d.budget_turn = wesnoth.current.turn
	end
	d.patterns[category] = d.patterns[category] or {}
	d.patterns[category][key] = core.number(d.patterns[category][key], 0) + 1
	if actor_type then d.studied[actor_type] = core.number(d.studied[actor_type], 0) + 1 end
	local before = d.insight
	if core.number(d.budget[category], 0) < d.turn_limit then
		d.budget[category] = core.number(d.budget[category], 0) + 1
		add_insight(d, core.number(d.gains[category], 0))
	end
	local pkey = doctrine.pattern(d, category)
	if pkey and not d.recognized[category .. "|" .. pkey] then
		d.recognized[category .. "|" .. pkey] = true
		add_insight(d, core.number(d.gains.pattern, 0))
		core.log("doctrine", "side " .. d.side .. " recognises " .. category .. " pattern '" .. pkey .. "'")
	end
	local gained = d.insight - before
	core.log("doctrine", "side " .. d.side .. " observes " .. category .. "=" .. key ..
		(actor_type and (" by " .. actor_type) or "") .. " (+" .. gained .. ", insight " .. d.insight .. ")")
	for _i, hook in ipairs(doctrine.hooks.on_observe) do hook(d.side, category, key, gained) end
	return gained
end

-- Observe an enemy action for every doctrine side that watches the acting
-- side and can observe it. need: minimum sensor state of the actor for the
-- doctrine side's team (FULL also lets it study the actor's type).
function doctrine.observe(actor_side, category, key, actor, need)
	for _i, d in ipairs(doctrine.enabled_sides()) do
		if watches(d, actor_side) then
			local state = ew.FULL
			if actor then state = ew.state_for(core.team_key(d.side), actor.id) end
			if state >= (need or ew.PARTIAL) then
				doctrine.record(d, category, key, (actor and state == ew.FULL) and actor.type or nil)
				commit(d)
			end
		end
	end
end

function doctrine.on_moveto()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u or not ctx.x2 or not ctx.y2 or (ctx.x2 == ctx.x1 and ctx.y2 == ctx.y1) then return end
	local dir = wesnoth.map.get_relative_dir({ ctx.x2, ctx.y2 }, { ctx.x1, ctx.y1 })
	if dir and dir ~= "" then doctrine.observe(u.side, "move", dir, u, ew.PARTIAL) end
end

local function target_key(t)
	if t.canrecruit then return "leader" end
	if t:matches{ ability = "sw_ability_force" } then return "force_user" end
	if t.hitpoints * 2 < t.max_hitpoints then return "wounded" end
	local friends = wesnoth.units.find_on_map{ side = t.side, T.filter_adjacent{ id = t.id } }
	if #friends == 0 then return "isolated" end
	return "frontline"
end

-- attack event (before combat): the attack's weapon and the choice of target.
function doctrine.on_attack()
	local ctx = wesnoth.current.event_context
	local a = wesnoth.units.get(ctx.x1, ctx.y1)
	local t = wesnoth.units.get(ctx.x2, ctx.y2)
	if not a or not t then return end
	-- The attacker's weapon is the [weapon] child of the event context.
	local weapon = wml.get_child(ctx, "weapon")
	for _i, d in ipairs(doctrine.enabled_sides()) do
		if watches(d, a.side) then
			-- The defender's own side always sees who attacks it.
			local state = ew.state_for(core.team_key(d.side), a.id)
			if not wesnoth.sides.is_enemy(d.side, t.side) then state = ew.FULL end
			if state >= ew.PARTIAL then
				local actor_type = state == ew.FULL and a.type or nil
				if weapon and weapon.type then
					doctrine.record(d, "attack", tostring(weapon.type) .. "/" .. tostring(weapon.range), actor_type)
				end
				doctrine.record(d, "target", target_key(t), nil)
				commit(d)
			end
		end
	end
end

function doctrine.on_recruit()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u then return end
	doctrine.observe(u.side, "recruit", ew.profile(u).class, u, ew.FULL)
	for _i, d in ipairs(doctrine.enabled_sides()) do
		if d.side == u.side then
			coordination_object(d, u)
			u.status.sw_doctrine_coordination = doctrine.effect(d, "coordination") ~= nil
		end
	end
end

-- unit placed: doctrine units get the (inactive) coordination ability.
function doctrine.on_unit_placed(u)
	for _i, d in ipairs(doctrine.enabled_sides()) do
		if d.side == u.side then
			coordination_object(d, u)
			u.status.sw_doctrine_coordination = doctrine.effect(d, "coordination") ~= nil
		elseif doctrine.effect(d, "coordination") and watches(d, u.side) then
			u.status["sw_studied_s" .. d.side] = core.number(d.studied[u.type], 0) >= d.study_min
		end
	end
end

-- End of an enemy side's turn: its formation, from the units the doctrine
-- side's team has identified.
function doctrine.on_side_turn_end(side)
	for _i, d in ipairs(doctrine.enabled_sides()) do
		if watches(d, side) then
			local team = core.team_key(d.side)
			local known = {}
			for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ side = side })) do
				if ew.state_for(team, u.id) == ew.FULL then table.insert(known, u) end
			end
			if #known >= 3 then
				local tight = 0
				for _i, u in ipairs(known) do
					local n = #wesnoth.units.find_on_map{ side = side, T.filter_adjacent{ id = u.id } }
					if n >= 2 then tight = tight + 1 end
				end
				doctrine.record(d, "formation", tight * 2 >= #known and "tight" or "dispersed", nil)
				commit(d)
			end
		end
	end
end

-- Tactical choices reported by the other systems (overwatch, sweeps, Force).
function doctrine.observe_tactic(u, key)
	doctrine.observe(u.side, "tactic", key, u, ew.FULL)
end

-- ---------------------------------------------------------------- prediction

local function clear_predictions(d)
	for _i, p in ipairs(d.predicted) do
		wesnoth.interface.remove_item(p.x, p.y, "sw_doctrine|" .. d.side .. "|" .. p.id)
	end
	d.predicted = {}
end

-- Limited prediction: needs a recognised target pattern; marks up to
-- tier.targets own units matching it that known enemies can reach.
function doctrine.predict(d)
	clear_predictions(d)
	local tier = doctrine.effect(d, "prediction")
	local key = doctrine.pattern(d, "target")
	if not tier or not key then return {} end
	local team = core.team_key(d.side)
	local threats = {}
	for _i, rec in ipairs(ew.contacts_of(team)) do
		if core.number(rec.state, 0) >= ew.PARTIAL and watches(d, rec.side) then
			local reach = 6
			if rec.type ~= "" and wesnoth.unit_types[rec.type] then reach = wesnoth.unit_types[rec.type].max_moves + 1 end
			table.insert(threats, { x = rec.x, y = rec.y, reach = reach })
		end
	end
	local cands = {}
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ side = d.side })) do
		if target_key(u) == key then
			local n, nearest = 0, 999
			for _i, t in ipairs(threats) do
				local dist = wesnoth.map.distance_between(u.x, u.y, t.x, t.y)
				if dist <= t.reach then n = n + 1 end
				nearest = math.min(nearest, dist)
			end
			if n > 0 then table.insert(cands, { u = u, n = n, nearest = nearest }) end
		end
	end
	table.sort(cands, function(a, b)
		if a.n ~= b.n then return a.n > b.n end
		if a.nearest ~= b.nearest then return a.nearest < b.nearest end
		return a.u.id < b.u.id
	end)
	local human = false
	for _i, s in ipairs(core.active_sides()) do
		if core.team_key(s) == team and wesnoth.sides[s].controller == "human" then human = true end
	end
	local out = {}
	for i = 1, math.min(core.number(tier.targets, 3), #cands) do
		local u = cands[i].u
		table.insert(d.predicted, { id = u.id, x = u.x, y = u.y })
		table.insert(out, u)
		if human then
			wesnoth.wml_actions.item{ x = u.x, y = u.y, image = "misc/sw-doctrine-threat.png",
				name = "sw_doctrine|" .. d.side .. "|" .. u.id, team_name = team, redraw = false }
		end
	end
	core.log("doctrine", "side " .. d.side .. " predicts " .. #out .. " likely target(s) (" .. key .. ")")
	return out
end

-- ---------------------------------------------------------------- turn cycle

-- Start of a doctrine side's turn: catalogue newly identified enemy types,
-- refresh studied marks, prediction and indicator.
function doctrine.on_side_turn(side)
	local d = doctrine.load(side)
	if not d or not d.enabled then return end
	local team = core.team_key(side)
	local seen = {}
	for _i, rec in ipairs(ew.contacts_of(team)) do
		if core.number(rec.state, 0) == ew.FULL and rec.type ~= "" and not rec.decoy and watches(d, rec.side) then
			seen[rec.type] = true
		end
	end
	for _i, ty in ipairs(core.sorted_keys(seen)) do
		if not d.catalogued[ty] then
			d.catalogued[ty] = true
			doctrine.record(d, "composition", ty, nil)
		end
	end
	doctrine.predict(d)
	commit(d)
	doctrine.apply_effects(d)
end

function doctrine.on_prestart()
	doctrine.ensure_scenario()
	for _i, d in ipairs(doctrine.enabled_sides()) do
		check_tiers(d)
		doctrine.save(d)
		doctrine.apply_effects(d)
	end
end

-- ---------------------------------------------------------------- integration

-- Sensor doctrine: explicit bonuses to the team's identification, ECCM and
-- decoy discrimination (+2 more once the enemy's decoy use is recognised).
-- Contact detection itself is not improved, so cloaks still hide.
function doctrine.ew_bonus(team)
	local b = { identify = 0, eccm = 0, discrimination = 0 }
	for _i, d in ipairs(doctrine.enabled_sides()) do
		if core.team_key(d.side) == team then
			local t = doctrine.effect(d, "sensors")
			if t then
				b.identify = b.identify + core.number(t.identify, 0)
				b.eccm = b.eccm + core.number(t.eccm, 0)
				b.discrimination = b.discrimination + core.number(t.discrimination, 0)
				if d.recognized["tactic|decoy"] then b.discrimination = b.discrimination + 2 end
			end
		end
	end
	return b
end

-- Overwatch: coordinated fire adds its accuracy to reaction shots too.
function doctrine.overwatch_modify(shooter, target, shot)
	local d = doctrine.load(shooter.side)
	local t = d and doctrine.effect(d, "coordination")
	if t and target.status["sw_studied_s" .. shooter.side] then
		shot.accuracy = shot.accuracy + core.number(t.accuracy, 10)
	end
end

function doctrine.on_decoy_exposed(team, decoy)
	for _i, d in ipairs(doctrine.enabled_sides()) do
		if core.team_key(d.side) == team and watches(d, decoy.side) then
			doctrine.record(d, "tactic", "decoy", nil)
			commit(d)
		end
	end
end

-- ---------------------------------------------------------------- scenario control

local function apply_seeds(d, cfg)
	for _i, s in ipairs(wml.child_array(cfg, "study")) do
		if s.type then d.studied[s.type] = core.number(d.studied[s.type], 0) + core.number(s.count, d.study_min) end
	end
	for _i, p in ipairs(wml.child_array(cfg, "pattern")) do
		if p.category and p.key then
			d.patterns[p.category] = d.patterns[p.category] or {}
			d.patterns[p.category][p.key] = core.number(d.patterns[p.category][p.key], 0) + core.number(p.count, d.pattern_min)
		end
	end
end

function doctrine.enable(side, cfg)
	cfg = cfg or {}
	doctrine.ensure_scenario()
	local d = doctrine.load(side) or new_state(side)
	d.enabled = true
	d.scenario = core.scenario_id()
	for k in pairs(doctrine.DEFAULTS) do if cfg[k] ~= nil then d[k] = core.number(cfg[k], d[k]) end end
	if cfg.watch ~= nil then d.watch = tostring(cfg.watch) end
	if cfg.persist ~= nil then d.persist = cfg.persist == true or cfg.persist == "yes" end
	local tiers = wml.child_array(cfg, "tier")
	if #tiers > 0 then
		d.tiers = {}
		for _i, t in ipairs(tiers) do
			local copy = {}
			for k, v in pairs(t) do if type(k) == "string" then copy[k] = v end end
			copy.insight = core.number(copy.insight, 0)
			table.insert(d.tiers, copy)
		end
		table.sort(d.tiers, function(a, b) return a.insight < b.insight end)
	end
	local gains = wml.get_child(cfg, "gains")
	if gains then for k, v in pairs(gains) do if type(k) == "string" then d.gains[k] = core.number(v, 0) end end end
	add_insight(d, 0)
	local list = sides_list()
	local present = false
	for _i, s in ipairs(list) do if s == side then present = true end end
	if not present then table.insert(list, side) set_sides_list(list) end
	check_tiers(d)
	doctrine.save(d)
	doctrine.apply_effects(d)
	core.log("doctrine", "enabled for side " .. side .. " (cap " .. d.cap .. ", insight " .. d.insight .. ")")
	ew.refresh()
	return d
end

function doctrine.disable(side)
	local d = doctrine.load(side)
	if not d then return end
	d.enabled = false
	clear_predictions(d)
	doctrine.save(d)
	-- Effects off: statuses cleared, the sensor bonus disappears.
	for _i, u in ipairs(wesnoth.units.find_on_map{ side = side }) do u.status.sw_doctrine_coordination = false end
	for _i, u in ipairs(wesnoth.units.find_on_map{}) do u.status["sw_studied_s" .. side] = false end
	doctrine.update_indicator(d)
	ew.refresh()
end

function doctrine.set_cap(side, cap)
	local d = doctrine.load(side) or doctrine.enable(side)
	d.cap = math.max(0, cap)
	add_insight(d, 0)
	commit(d)
	doctrine.apply_effects(d)
end

function doctrine.reset(side)
	local d = doctrine.load(side)
	if not d then return end
	clear_predictions(d)
	d.insight = 0
	d.patterns, d.studied, d.recognized, d.budget, d.catalogued, d.log = {}, {}, {}, {}, {}, {}
	commit(d)
	doctrine.apply_effects(d)
end

-- Pre-seed: set Insight to an exact amount (capped) plus optional studied
-- types and patterns.
function doctrine.seed(side, amount, cfg)
	local d = doctrine.load(side) or doctrine.enable(side)
	d.insight = 0
	add_insight(d, amount or 0)
	if cfg then apply_seeds(d, cfg) end
	commit(d)
	doctrine.apply_effects(d)
end

-- Cultural and Art Intelligence: Insight granted by the story (captured art,
-- archives, interrogations, completed objectives), with its source logged
-- and shown in the summary. Ignores the per-turn limit, respects the cap.
function doctrine.grant(side, amount, source, text, cfg)
	local d = doctrine.load(side)
	if not d or not d.enabled then
		core.log("doctrine", "grant to side " .. side .. " ignored: doctrine not enabled")
		return 0
	end
	local before = d.insight
	add_insight(d, amount or 0)
	if cfg then apply_seeds(d, cfg) end
	table.insert(d.log, { source = source or "intelligence", text = text or "", amount = d.insight - before,
		turn = wesnoth.current.turn })
	core.log("doctrine", "side " .. side .. " granted " .. (d.insight - before) .. " insight from " .. tostring(source))
	commit(d)
	doctrine.apply_effects(d)
	for _i, leader in ipairs(leaders_of(side)) do
		core.float_for_team(core.team_key(side), leader.x, leader.y,
			"+" .. (d.insight - before) .. " " .. tostring(_ "insight"), "#c9a6ff")
		break
	end
	for _i, hook in ipairs(doctrine.hooks.on_grant) do hook(side, d.insight - before, source) end
	return d.insight - before
end

-- ---------------------------------------------------------------- text / menus

local SOURCE_NAMES = { art = _ "captured art", archive = _ "archives", intelligence = _ "intelligence report",
	conversation = _ "interrogation", objective = _ "objective" }

local function pattern_line(d, category)
	local key, n, total = doctrine.pattern(d, category)
	if not key then return nil end
	local frac = " (" .. n .. "/" .. total .. ")"
	if category == "move" then
		return tostring(_ "Their units mostly advance toward the") .. " " .. tostring(doctrine.DIR_NAMES[key] or key) .. frac
	elseif category == "attack" then
		local ty, rng = key:match("^([^/]*)/(.*)$")
		return tostring(_ "Favoured attack:") .. " " .. tostring(ty) .. ", " .. tostring(rng) .. frac
	elseif category == "target" then
		return tostring(_ "They single out") .. " " .. tostring(doctrine.TARGET_NAMES[key] or key) .. " " .. tostring(_ "targets") .. frac
	elseif category == "recruit" then
		return tostring(_ "Reinforcements are mostly") .. " " .. tostring(ew.CLASS_NAMES[key] or key) .. frac
	elseif category == "formation" then
		return tostring(key == "tight" and _ "They fight in tight formations" or _ "They fight dispersed") .. frac
	elseif category == "tactic" then
		return tostring(_ "Recurring tactic:") .. " " .. key .. frac
	end
	return nil
end

-- Explicit description of the doctrine side's state (shown to its players,
-- and the tier summary to opponents via Tactical status).
function doctrine.status_line(d)
	local n = doctrine.tier_count(d)
	local names = {}
	for i = 1, n do table.insert(names, tostring(doctrine.EFFECT_NAMES[d.tiers[i].effect] or d.tiers[i].effect)) end
	local line = tostring(_ "Thrawn's doctrine — Insight") .. " " .. d.insight .. "/" .. d.cap
	if #names > 0 then line = line .. ". " .. tostring(_ "Active:") .. " " .. table.concat(names, ", ") end
	local nxt = d.tiers[n + 1]
	if nxt then
		line = line .. ". " .. tostring(_ "Next:") .. " " .. tostring(doctrine.EFFECT_NAMES[nxt.effect] or nxt.effect) ..
			" " .. tostring(_ "at") .. " " .. nxt.insight
	end
	if not d.enabled then line = line .. " (" .. tostring(_ "disabled") .. ")" end
	return line
end

function doctrine.summary_text(d)
	local lines = { "<b>" .. doctrine.status_line(d) .. "</b>" }
	local team = core.team_key(d.side)
	if doctrine.effect(d, "summary") then
		local identified, classes, unknown = {}, {}, 0
		for _i, rec in ipairs(ew.contacts_of(team)) do
			if watches(d, rec.side) then
				local st = core.number(rec.state, 0)
				-- What the team believes: decoys appear exactly as they are read.
				if st == ew.FULL and rec.type ~= "" then identified[rec.type] = core.number(identified[rec.type], 0) + 1
				elseif st >= ew.PARTIAL then classes[rec.class] = core.number(classes[rec.class], 0) + 1
				elseif st == ew.CONTACT then unknown = unknown + 1 end
			end
		end
		local parts = {}
		for _i, ty in ipairs(core.sorted_keys(identified)) do
			table.insert(parts, identified[ty] .. "× " .. tostring(wesnoth.unit_types[ty] and wesnoth.unit_types[ty].name or ty))
		end
		table.insert(lines, tostring(_ "Identified enemy forces:") .. " " .. (#parts > 0 and table.concat(parts, ", ") or "—"))
		parts = {}
		for _i, c in ipairs(core.sorted_keys(classes)) do
			table.insert(parts, classes[c] .. "× " .. tostring(ew.CLASS_NAMES[c] or c))
		end
		if #parts > 0 then
			table.insert(lines, tostring(_ "Classified contacts (unconfirmed, may be decoys):") .. " " .. table.concat(parts, ", "))
		end
		if unknown > 0 then table.insert(lines, tostring(_ "Unknown contacts:") .. " " .. unknown) end
		local studied = {}
		for _i, ty in ipairs(core.sorted_keys(d.studied)) do
			if d.studied[ty] >= d.study_min and wesnoth.unit_types[ty] then table.insert(studied, tostring(wesnoth.unit_types[ty].name)) end
		end
		if #studied > 0 then table.insert(lines, tostring(_ "Studied:") .. " " .. table.concat(studied, ", ")) end
	end
	if doctrine.effect(d, "patterns") then
		for _i, cat in ipairs{ "move", "attack", "target", "recruit", "formation", "tactic" } do
			local l = pattern_line(d, cat)
			if l then table.insert(lines, "• " .. l) end
		end
	end
	local sensors = doctrine.effect(d, "sensors")
	if sensors then
		table.insert(lines, tostring(_ "Sensor doctrine: identification") .. " +" .. core.number(sensors.identify, 0) ..
			", ECCM +" .. core.number(sensors.eccm, 0) .. ", " .. tostring(_ "decoy discrimination") .. " +" ..
			core.number(sensors.discrimination, 0) .. ".")
		-- Counter-deployment: which of our deployed unit types resists their
		-- favoured damage type best.
		local key = doctrine.pattern(d, "attack")
		if key then
			local dmg = key:match("^([^/]*)/")
			local best, best_r = nil, -999
			for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{ side = d.side })) do
				-- resistance_against returns the resistance percentage (damage taken is 100 - it).
				local r = u:resistance_against(dmg)
				if r > best_r then best, best_r = u, r end
			end
			if best then
				table.insert(lines, tostring(_ "Counter-deployment: against their") .. " " .. dmg .. " " ..
					tostring(_ "attacks, put") .. " " .. tostring(best.name ~= "" and best.name or best.type) ..
					" (" .. tostring(wesnoth.unit_types[best.type].name) .. ", " .. best_r .. "% " .. tostring(_ "resistance") ..
					") " .. tostring(_ "in front."))
			end
		end
	end
	if doctrine.effect(d, "prediction") then
		local names = {}
		for _i, p in ipairs(d.predicted) do
			local u = wesnoth.units.get(p.id)
			if u then table.insert(names, tostring(u.name ~= "" and u.name or wesnoth.unit_types[u.type].name)) end
		end
		table.insert(lines, tostring(_ "Predicted targets (marked):") .. " " .. (#names > 0 and table.concat(names, ", ") or
			tostring(_ "none — no recognised targeting pattern, or no known enemy within reach")))
	end
	local coord = doctrine.effect(d, "coordination")
	if coord then
		table.insert(lines, tostring(_ "Coordinated fire: +") .. core.number(coord.accuracy, 10) ..
			tostring(_ "% to hit studied enemy types (attacks and overwatch)."))
	end
	if #d.log > 0 then
		table.insert(lines, tostring(_ "Intelligence:"))
		for i = math.max(1, #d.log - 2), #d.log do
			local e = d.log[i]
			table.insert(lines, "  " .. tostring(SOURCE_NAMES[e.source] or e.source) .. " (+" .. e.amount .. ")" ..
				((e.text and e.text ~= "") and (": " .. tostring(e.text)) or ""))
		end
	end
	return table.concat(lines, "\n")
end

function doctrine.menu_visible()
	local side = core.viewing_side()
	if not side or not core.is_local_turn_of(side) then return false end
	local d = doctrine.load(side)
	return d ~= nil and d.enabled
end

function doctrine.menu_command()
	local d = doctrine.load(wesnoth.current.side)
	if not d then return end
	wesnoth.wml_actions.message{ speaker = "narrator", caption = _ "Thrawn's doctrine", side_for = wesnoth.current.side,
		image = "misc/sw-menu-doctrine.png~SCALE(72,72)", message = doctrine.summary_text(d) }
end

-- For Tactical status on a doctrine side's commander: the visible, explicit
-- state of the doctrine (no hidden bonuses).
function doctrine.leader_status(u)
	if not (u.canrecruit or u:matches{ ability = "sw_ability_tactical_genius" }) then return nil end
	local d = doctrine.load(u.side)
	if not d then return nil end
	return doctrine.status_line(d)
end

return doctrine
