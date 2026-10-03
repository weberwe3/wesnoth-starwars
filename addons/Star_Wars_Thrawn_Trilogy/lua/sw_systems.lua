-- Star Wars: Thrawn Trilogy -- tactical systems loader.
--
-- Executed by the top-level [lua] of every mission ({SW_TACTICAL_SYSTEMS},
-- utils/hte_macros.cfg), on new games and on every load. It registers the
-- event handlers, menu items and WML tags; all state is in WML/unit
-- variables, so re-registering after a load restores the systems exactly.
--
-- Systems: the Force (sw_force), overwatch (sw_overwatch), sensors and
-- electronic warfare (sw_ew) and Thrawn Doctrine (sw_doctrine).
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
--               4. EW: that side's sweeps end, decoys/reveals expire, pictures
--               5. doctrine: composition, studied marks, prediction
--   side turn end  1. doctrine observes the side's formation
--                  2. AI sides may sweep, then enter overwatch
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
local T = wml.tag
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

sw_systems = { core = core, force = force, overwatch = overwatch, ew = ew, doctrine = doctrine }

-- Cross-system wiring (hooks are plain Lua tables, rebuilt on every load).
ew.hooks.bonus = { doctrine.ew_bonus }
ew.hooks.on_decoy_exposed = { doctrine.on_decoy_exposed }
ew.on_tactic = function(u, key) doctrine.observe_tactic(u, key) end
overwatch.hooks.modify = { doctrine.overwatch_modify }
overwatch.on_enter = function(u) doctrine.observe_tactic(u, "overwatch") end
force.on_power_used = function(u, power_id) doctrine.observe_tactic(u, "force_" .. power_id) end

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
	end
	wml.array_access.set("sw_ow_index", {})
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
end)

on("attack", "sw_sys_attack", function()
	doctrine.on_attack()
	ew.on_attack()
end)

on("turn refresh", "sw_sys_turn_refresh", function()
	local side = wesnoth.current.side
	overwatch.on_side_turn(side)
	force.refresh_fields()
	force.on_side_turn(side)
	ew.on_side_turn(side)
	doctrine.on_side_turn(side)
end)

on("side turn end", "sw_sys_side_turn_end", function()
	local side = wesnoth.current.side
	doctrine.on_side_turn_end(side)
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
	doctrine.on_unit_placed(u)
	if mover_matters(u) then force.refresh_fields() end
	ew.refresh()
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
	local ctx = wesnoth.current.event_context
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
		add(u.id, u.x, u.y, u.hitpoints, u.status[ew.CONCEALED] == true, u.variables.sw_ew_sweep == true)
	end
	local text = table.concat(parts, ",")
	local h = 5381
	for i = 1, #text do h = (h * 33 + text:byte(i)) % 2147483647 end
	return string.format("%d:%d", h, #text), text
end

core.log("systems", "tactical systems loaded")
