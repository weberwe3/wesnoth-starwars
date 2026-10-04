-- Star Wars: Thrawn Trilogy -- tactical systems loader.
--
-- Executed by the top-level [lua] of every mission ({SW_TACTICAL_SYSTEMS},
-- utils/hte_macros.cfg), on new games and on every load. It registers the
-- event handlers, menu items and WML tags; all state is in WML/unit
-- variables, so re-registering after a load restores the systems exactly.
--
-- Systems: the Force (sw_force), overwatch (sw_overwatch), sensors and
-- electronic warfare (sw_ew), Thrawn Doctrine (sw_doctrine), off-map air
-- support (sw_air) and rank insignia (sw_rank).
--
-- Event precedence (all handlers are registered here, nowhere else):
--   prestart    1. carried-over state reset (overwatch, Force, EW, doctrine)
--               2. sensor pictures and concealment computed
--   enter_hex   1. overwatch reaction check for the moving unit
--               2. null-field refresh if the mover is a ysalamiri carrier or
--                  a Force user (suppression changes hex by hex)
--   moveto      1. move serial bump (overwatch duplicate guard)
--               2. null-field refresh  3. sensor pictures
--               4. doctrine observes the move (from the refreshed picture)
--   attack      doctrine observes weapon and target; both units emit
--   attack end  null-field refresh, sensor pictures
--   turn refresh (start of a side's turn, after the engine resets moves):
--               1. overwatch expires for that side  2. null-field refresh
--               3. Force regeneration, cooldowns, Mind Trick, Sense expiry
--               4. that side's telegraphed bombing runs land
--               5. EW: that side's sweeps end, decoys/reveals expire, pictures
--               6. doctrine: composition, studied marks, prediction
--   side turn end  1. doctrine observes the side's formation
--                  2. AI sides may call air support, sweep, then enter overwatch
--   post advance   rank insignia (promotion or AMLA)
--   die / unit placed / recruit  refreshes and initialisation
-- Force displacement (Push/Pull) moves units without firing events, so it
-- never provokes reactions; reaction fire runs under a reentrancy guard so
-- it never chains into further reactions. Sensor pictures are recomputed per
-- completed action, never per movement hex.

local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local force = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_force.lua")
local overwatch = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_overwatch.lua")
local ew = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ew.lua")
local doctrine = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_doctrine.lua")
local air = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_air.lua")
local rank = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_rank.lua")
local alert = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_alert.lua")
local range = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_range.lua")
local T = wml.tag
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

sw_systems = { core = core, force = force, overwatch = overwatch, ew = ew, doctrine = doctrine, air = air, rank = rank, alert = alert, range = range }

-- Cross-system wiring (hooks are plain Lua tables, rebuilt on every load).
ew.hooks.bonus = { doctrine.ew_bonus }
ew.hooks.on_decoy_exposed = { doctrine.on_decoy_exposed }
ew.on_tactic = function(u, key) doctrine.observe_tactic(u, key) end
overwatch.hooks.modify = { doctrine.overwatch_modify }
overwatch.on_enter = function(u) doctrine.observe_tactic(u, "overwatch") end
force.on_power_used = function(u, power_id) doctrine.observe_tactic(u, "force_" .. power_id) end
air.hooks.on_call = { function(side, sortie_id, observer) doctrine.observe_tactic(observer, "air_" .. sortie_id) end }

local function on(name, id, action)
	wesnoth.game_events.add{ name = name, id = id, first_time_only = false, action = action }
end

local function mover_matters(u)
	return u and (force.is_sensitive(u) or core.has_ability(u, force.YSALAMIRI))
end

on("prestart", "sw_sys_prestart", function()
	-- Carried-over units start a mission rested and off overwatch.
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{})) do
		overwatch.clear(u)
		core.compact_overlays(u)
		local cfg = force.config(u)
		if cfg then force.set_fp(u, cfg.fp_max, cfg) end
		rank.update(u)
	end
	wml.array_access.set("sw_ow_index", {})
	air.ensure_scenario()
	-- The default AI only attacks adjacent targets; give every side the
	-- stand-off ranged-fire candidate action (lua/sw_ai_ranged.lua). Done at
	-- prestart only: saved games keep their AI configuration.
	for _i, side in ipairs(core.active_sides()) do
		wesnoth.wml_actions.modify_ai{ side = side, action = "add", path = "stage[main_loop].candidate_action",
			T.candidate_action{ engine = "lua", name = "sw_ranged_fire", id = "sw_ranged_fire", max_score = 100010,
				location = "~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua" } }
	end
	force.refresh_fields()
	doctrine.on_prestart()
	ew.on_prestart()
end)

on("enter_hex", "sw_sys_enter_hex", function()
	overwatch.on_enter_hex()
	local ctx = wesnoth.current.event_context
	if mover_matters(wesnoth.units.get(ctx.x1, ctx.y1)) then force.refresh_fields() end
end)

on("moveto", "sw_sys_moveto", function()
	overwatch.on_moveto()
	force.refresh_fields()
	ew.refresh()
	doctrine.on_moveto()
	alert.check()
	range.on_moveto()
end)

on("attack", "sw_sys_attack", function()
	doctrine.on_attack()
	ew.on_attack()
	alert.on_attack()
end)

on("turn refresh", "sw_sys_turn_refresh", function()
	local side = wesnoth.current.side
	range.on_turn()
	overwatch.on_side_turn(side)
	force.refresh_fields()
	force.on_side_turn(side)
	air.on_side_turn(side)
	ew.on_side_turn(side)
	doctrine.on_side_turn(side)
	alert.on_side_turn(side)
end)

on("side turn end", "sw_sys_side_turn_end", function()
	local side = wesnoth.current.side
	doctrine.on_side_turn_end(side)
	air.on_side_turn_end(side)
	ew.on_side_turn_end(side)
	overwatch.on_side_turn_end(side)
end)

on("die", "sw_sys_die", function()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if u then
		overwatch.clear(u)
		-- The dying unit is still on the map (hitpoints <= 0) during "die";
		-- refresh_fields and ew.refresh ignore it, so a dead carrier's field
		-- collapses and its contacts disappear now.
		if mover_matters(u) then force.refresh_fields() end
		ew.refresh()
	end
end)

on("unit placed", "sw_sys_unit_placed", function()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u then return end
	force.init_unit(u)
	rank.update(u)
	local acfg = alert.config()
	if acfg and u.side == acfg.guard_side and u.variables.sw_alert_state == nil then
		-- Reinforcements arriving after the alarm come in alert.
		u.variables.sw_alert_state = acfg.alarm and "alert" or "unaware"
	end
	doctrine.on_unit_placed(u)
	if mover_matters(u) then force.refresh_fields() end
	ew.refresh()
end)

on("post advance", "sw_sys_post_advance", function()
	rank.on_post_advance()
end)

on("recruit", "sw_sys_recruit", function()
	doctrine.on_recruit()
end)

on("attack end", "sw_sys_attack_end", function()
	force.refresh_fields()
	ew.refresh()
end)

-- Right-click menu items (contextual: shown only where they apply, so normal
-- play stays uncluttered).
wesnoth.interface.set_menu_item("sw_force_menu", {
	description = _ "The Force…",
	image = "misc/sw-menu-force.png",
	T.show_if{ T.lua{ code = "return sw_systems.force.menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.force.open_menu()" } },
})

wesnoth.interface.set_menu_item("sw_overwatch_menu", {
	description = _ "Overwatch (commits this turn's attack)",
	image = "misc/sw-menu-overwatch.png",
	T.show_if{ T.lua{ code = "return sw_systems.overwatch.menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.overwatch.menu_command()" } },
})

wesnoth.interface.set_menu_item("sw_ew_sweep_menu", {
	description = _ "Active sensor sweep (commits this turn's attack)",
	image = "misc/sw-menu-sensor.png",
	T.show_if{ T.lua{ code = "return sw_systems.ew.sweep_menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.ew.sweep_menu_command()" } },
})

wesnoth.interface.set_menu_item("sw_ew_decoy_menu", {
	description = _ "Launch sensor decoy…",
	image = "misc/sw-menu-decoy.png",
	T.show_if{ T.lua{ code = "return sw_systems.ew.decoy_menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.ew.decoy_menu_command()" } },
})

wesnoth.interface.set_menu_item("sw_ew_contact_menu", {
	description = _ "Sensor contact",
	image = "misc/sw-menu-sensor.png",
	T.show_if{ T.lua{ code = "return sw_systems.ew.contact_menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.ew.contact_menu_command()" } },
})

wesnoth.interface.set_menu_item("sw_air_menu", {
	description = _ "Call air support…",
	image = "misc/sw-menu-air.png",
	T.show_if{ T.lua{ code = "return sw_systems.air.menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.air.menu_command()" } },
})

wesnoth.interface.set_menu_item("sw_alert_takedown_menu", {
	description = _ "Silent takedown",
	image = "misc/sw-menu-takedown.png",
	T.show_if{ T.lua{ code = "return sw_systems.alert.takedown_menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.alert.takedown_menu_command()" } },
})

wesnoth.interface.set_menu_item("sw_alert_sight_menu", {
	description = _ "Show or hide guard sight",
	image = "misc/sw-alert-suspicious.png~SCALE(16,16)",
	T.show_if{ T.lua{ code = "return sw_systems.alert.sight_menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.alert.sight_menu_command()" } },
})

wesnoth.interface.set_menu_item("sw_range_show_menu", {
	description = _ "Show attack range",
	image = "misc/sw-menu-range.png",
	T.show_if{ T.lua{ code = "return sw_systems.range.show_menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.range.show_menu_command()" } },
})

wesnoth.interface.set_menu_item("sw_range_hide_menu", {
	description = _ "Hide attack range",
	image = "misc/sw-menu-range.png",
	T.show_if{ T.lua{ code = "return sw_systems.range.hide_menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.range.hide_menu_command()" } },
})

wesnoth.interface.set_menu_item("sw_doctrine_menu", {
	description = _ "Thrawn's doctrine",
	image = "misc/sw-menu-doctrine.png",
	T.show_if{ T.lua{ code = "return sw_systems.doctrine.menu_visible()" } },
	T.command{ T.lua{ code = "sw_systems.doctrine.menu_command()" } },
})

wesnoth.interface.set_menu_item("sw_status_menu", {
	description = _ "Tactical status",
	T.show_if{ T.lua{ code = "return sw_systems.status_visible()" } },
	T.command{ T.lua{ code = "sw_systems.show_status()" } },
})

-- A unit on the clicked hex that the given side can see (never a hidden one:
-- a menu that appeared over an "empty" hex would betray it).
local function seen_unit(side)
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if u == nil or side == nil or side < 1 then return nil end
	if not u:matches{ T.filter_vision{ side = side, visible = true } } then return nil end
	return u
end

function sw_systems.status_visible()
	return seen_unit(core.viewing_side()) ~= nil
end

function sw_systems.show_status()
	local u = seen_unit(wesnoth.current.side)
	if not u then return end
	local viewer_team = core.team_key(wesnoth.current.side)
	local lines = {}
	local cfg = force.config(u)
	if cfg then table.insert(lines, force.status_text(u, cfg)) end
	if force.is_suppressed(u) and not cfg then
		table.insert(lines, tostring(_ "Inside a ysalamiri field: the Force is blocked here."))
	end
	if u.variables.sw_ow_active then
		table.insert(lines, tostring(_ "On overwatch:") .. " " .. core.number(u.variables.sw_ow_shots, 0) .. " " ..
			tostring(_ "reaction(s) left, range") .. " " .. core.number(u.variables.sw_ow_range, 0))
	end
	for _i, l in ipairs(ew.status_lines(u, viewer_team)) do table.insert(lines, l) end
	local dl = doctrine.leader_status(u)
	if dl then table.insert(lines, dl) end
	local rl = rank.status_line(u)
	if rl then table.insert(lines, rl) end
	if u.side == wesnoth.current.side then
		local al = air.status_line(u)
		if al then table.insert(lines, al) end
	end
	-- side_for: only the player who asked sees the answer (multiplayer).
	wesnoth.wml_actions.message{ speaker = "narrator", caption = _ "Tactical status", side_for = wesnoth.current.side,
		image = "misc/sw-objective.png", message = table.concat(lines, "\n") }
end

-- ---------------------------------------------------------------- WML tags

-- [sw_doctrine] action=enable|disable|cap|reset|seed|grant side=N
--   enable: cap= turn_limit= pattern_min= pattern_share= study_min= watch=1,3
--           persist=yes [tier] insight= effect= ... [/tier] [gains] move= ... [/gains]
--   cap: cap=   seed: amount= [study] type= count= [/study] [pattern] category= key= count= [/pattern]
--   grant: amount= source=art|archive|intelligence|conversation|objective text= (+ [study]/[pattern])
function wesnoth.wml_actions.sw_doctrine(cfg)
	cfg = wml.parsed(cfg)
	local action = cfg.action or "enable"
	local side = tonumber(cfg.side) or wml.error("[sw_doctrine] needs side=")
	if action == "enable" then doctrine.enable(side, cfg)
	elseif action == "disable" then doctrine.disable(side)
	elseif action == "cap" then doctrine.set_cap(side, tonumber(cfg.cap) or 100)
	elseif action == "reset" then doctrine.reset(side)
	elseif action == "seed" then doctrine.seed(side, tonumber(cfg.amount) or 0, cfg)
	elseif action == "grant" then doctrine.grant(side, tonumber(cfg.amount) or 0, cfg.source, cfg.text, cfg)
	else wml.error("[sw_doctrine] unknown action=" .. tostring(action)) end
end

-- [sw_ew_profile] [filter] ... [/filter] sensor= sensor_range= signature= cloak= ecm=
-- ecm_range= eccm= scan= decoys= class= disguise_class=
function wesnoth.wml_actions.sw_ew_profile(cfg)
	cfg = wml.parsed(cfg)
	local filter = wml.get_child(cfg, "filter") or wml.error("[sw_ew_profile] needs [filter]")
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map(filter))) do ew.set_profile(u, cfg) end
	ew.refresh()
end

-- [sw_ew_reveal] [filter] ... [/filter] side= (the side, i.e. its team, that
-- learns) state=contact|partial|full turns=1
function wesnoth.wml_actions.sw_ew_reveal(cfg)
	cfg = wml.parsed(cfg)
	local filter = wml.get_child(cfg, "filter") or wml.error("[sw_ew_reveal] needs [filter]")
	local side = tonumber(cfg.side) or wml.error("[sw_ew_reveal] needs side=")
	local states = { contact = ew.CONTACT, partial = ew.PARTIAL, full = ew.FULL }
	local state = states[cfg.state or "full"] or ew.FULL
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map(filter))) do
		ew.reveal(u, core.team_key(side), state, tonumber(cfg.turns) or 1)
	end
end

-- [sw_ew_decoy] x= y= side= class= type= signature= deception= turns=
function wesnoth.wml_actions.sw_ew_decoy(cfg)
	cfg = wml.parsed(cfg)
	ew.add_decoy{ x = tonumber(cfg.x), y = tonumber(cfg.y), side = tonumber(cfg.side) or 1, class = cfg.class,
		type = cfg.type, signature = cfg.signature, deception = cfg.deception, turns = cfg.turns }
end

-- [sw_air_support] side= sortie=strafe|bombing count=1 craft=<unit type>
-- Grants off-map sorties for this mission (see sw_air.lua).
function wesnoth.wml_actions.sw_air_support(cfg)
	cfg = wml.parsed(cfg)
	air.grant(tonumber(cfg.side) or wml.error("[sw_air_support] needs side="), cfg.sortie or "strafe",
		tonumber(cfg.count) or 1, cfg.craft)
end

-- [sw_air_strike] side= sortie= craft= damage= strikes= certain=yes|no enemies_only=yes|no and either
-- x= y= direction= or a [filter_location] (hexes flown in x order): a
-- scripted sortie with no observer and no charge, resolved at once.
function wesnoth.wml_actions.sw_air_strike(cfg)
	cfg = wml.parsed(cfg)
	local hexes = nil
	local fl = wml.get_child(cfg, "filter_location")
	if fl then
		hexes = {}
		for _i, loc in ipairs(wesnoth.map.find(fl)) do table.insert(hexes, { x = loc[1] or loc.x, y = loc[2] or loc.y }) end
		table.sort(hexes, function(a, b) if a.x ~= b.x then return a.x < b.x end return a.y < b.y end)
	end
	air.scripted_strike{ side = tonumber(cfg.side) or 1, sortie = cfg.sortie, craft = cfg.craft,
		damage = tonumber(cfg.damage), strikes = tonumber(cfg.strikes), certain = cfg.certain,
		enemies_only = cfg.enemies_only, hexes = hexes,
		x = tonumber(cfg.x), y = tonumber(cfg.y), direction = cfg.direction }
end

-- [sw_alert] action=enable guard_side= intruder_side= show_sight=yes|no
-- [sw_alert] action=alarm                         every guard becomes alert
-- [sw_alert] action=guard [filter]...[/filter] sight=3 patrol=x.y,x.y,...
function wesnoth.wml_actions.sw_alert(cfg)
	cfg = wml.parsed(cfg)
	local action = cfg.action or "enable"
	if action == "enable" then
		alert.enable(tonumber(cfg.guard_side) or wml.error("[sw_alert] needs guard_side="),
			tonumber(cfg.intruder_side) or wml.error("[sw_alert] needs intruder_side="),
			cfg.show_sight ~= false and cfg.show_sight ~= "no")
	elseif action == "alarm" then
		alert.alarm()
	elseif action == "guard" then
		local filter = wml.get_child(cfg, "filter") or wml.error("[sw_alert] action=guard needs [filter]")
		for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map(filter))) do
			if cfg.sight then u.variables.sw_alert_sight = tonumber(cfg.sight) end
			if cfg.patrol then u.variables.sw_alert_patrol = cfg.patrol end
		end
		alert.refresh()
	else
		wml.error("[sw_alert] unknown action=" .. tostring(action))
	end
end

-- [sw_ew_settings] thresholds/modifiers, [terrain] rules (see sw_ew.lua)
function wesnoth.wml_actions.sw_ew_settings(cfg)
	ew.configure(wml.parsed(cfg))
end

-- A compact fingerprint of all intelligence-system state (sensor pictures,
-- decoys, doctrine, concealment, unit positions). Used by the engine tests
-- to prove that save/load and replays reproduce exactly the same state.
function sw_systems.digest()
	local parts = {}
	local function add(...) for _i, v in ipairs{ ... } do table.insert(parts, tostring(v)) end table.insert(parts, ";") end
	local recs = wml.array_access.get("sw_ew_contacts")
	table.sort(recs, function(a, b) return (a.team .. "|" .. a.key) < (b.team .. "|" .. b.key) end)
	for _i, r in ipairs(recs) do add(r.team, r.key, r.x, r.y, r.state, r.class, r.type, r.image, r.score, r.identify) end
	for _i, d in ipairs(wml.array_access.get("sw_ew_decoys")) do add(d.id, d.x, d.y, d.side, d.class, d.exposed, d.expires) end
	for _i, d in ipairs(doctrine.enabled_sides()) do
		add("doctrine", d.side, d.insight, d.tier_reached)
		for _i, cat in ipairs(core.sorted_keys(d.patterns)) do
			for _i, k in ipairs(core.sorted_keys(d.patterns[cat])) do add(cat, k, d.patterns[cat][k]) end
		end
		for _i, ty in ipairs(core.sorted_keys(d.studied)) do add(ty, d.studied[ty]) end
	end
	for _i, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{})) do
		add(u.id, u.x, u.y, u.hitpoints, u.status[ew.CONCEALED] == true, u.variables.sw_ew_sweep == true,
			u.variables.sw_rank_shown or 0, u.experience)
	end
	for _i, side in ipairs(core.active_sides()) do
		local st = air.load(side)
		add("air", side, st.used_turn)
		for _j, id in ipairs(core.sorted_keys(st.charges)) do add(id, st.charges[id]) end
	end
	for _i, s in ipairs(wml.array_access.get("sw_air_inbound")) do add(s.id, s.side, s.sortie, s.xs, s.ys, s.due_turn) end
	local text = table.concat(parts, ",")
	local h = 5381
	for i = 1, #text do h = (h * 33 + text:byte(i)) % 2147483647 end
	return string.format("%d:%d", h, #text), text
end

core.log("systems", "tactical systems loaded")
