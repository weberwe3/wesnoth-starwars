-- Star Wars: Thrawn Trilogy -- tactical systems loader.
--
-- Executed by the top-level [lua] of every mission ({SW_TACTICAL_SYSTEMS},
-- utils/hte_macros.cfg), on new games and on every load. It registers the
-- event handlers and menu items; all state is in WML/unit variables, so
-- re-registering after a load restores the systems exactly.
--
-- Event precedence (all handlers are registered here, nowhere else):
--   enter_hex   1. overwatch reaction check for the moving unit
--               2. null-field refresh if the mover is a ysalamiri carrier or
--                  a Force user (suppression changes hex by hex)
--   moveto      move serial bump (duplicate guard), then null-field refresh
--   turn refresh (start of a side's turn, after the engine resets moves):
--               1. overwatch expires for that side
--               2. null-field refresh
--               3. Force regeneration, cooldowns, Mind Trick, Sense expiry
--   side turn end  AI sides may enter overwatch
--   die / unit placed  null-field refresh, Force Point initialisation
-- Force displacement (Push/Pull) moves units without firing events, so it
-- never provokes reactions; reaction fire runs under a reentrancy guard so
-- it never chains into further reactions.

local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local force = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_force.lua")
local overwatch = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_overwatch.lua")
local T = wml.tag
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

sw_systems = { core = core, force = force, overwatch = overwatch }

local function on(name, id, action)
	wesnoth.game_events.add{ name = name, id = id, first_time_only = false, action = action }
end

local function mover_matters(u)
	return u and (force.is_sensitive(u) or core.has_ability(u, force.YSALAMIRI))
end

on("prestart", "sw_sys_prestart", function()
	-- Carried-over units start a mission rested and off overwatch.
	for _, u in ipairs(core.sorted_by_id(wesnoth.units.find_on_map{})) do
		overwatch.clear(u)
		core.compact_overlays(u)
		local cfg = force.config(u)
		if cfg then force.set_fp(u, cfg.fp_max, cfg) end
	end
	wml.array_access.set("sw_ow_index", {})
	force.refresh_fields()
end)

on("enter_hex", "sw_sys_enter_hex", function()
	overwatch.on_enter_hex()
	local ctx = wesnoth.current.event_context
	if mover_matters(wesnoth.units.get(ctx.x1, ctx.y1)) then force.refresh_fields() end
end)

on("moveto", "sw_sys_moveto", function()
	overwatch.on_moveto()
	force.refresh_fields()
end)

on("turn refresh", "sw_sys_turn_refresh", function()
	local side = wesnoth.current.side
	overwatch.on_side_turn(side)
	force.refresh_fields()
	force.on_side_turn(side)
end)

on("side turn end", "sw_sys_side_turn_end", function()
	overwatch.on_side_turn_end(wesnoth.current.side)
end)

on("die", "sw_sys_die", function()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if u then
		overwatch.clear(u)
		-- The dying unit is still on the map (hitpoints <= 0) during "die";
		-- refresh_fields ignores it, so a dead carrier's field collapses now.
		if mover_matters(u) then force.refresh_fields() end
	end
end)

on("unit placed", "sw_sys_unit_placed", function()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u then return end
	force.init_unit(u)
	if mover_matters(u) then force.refresh_fields() end
end)

on("attack end", "sw_sys_attack_end", function()
	force.refresh_fields()
end)

-- Right-click menu items (contextual: shown only on the player's own units
-- that can use them, so normal attacks stay uncluttered).
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

wesnoth.interface.set_menu_item("sw_status_menu", {
	description = _ "Tactical status",
	T.show_if{ T.lua{ code = "return sw_systems.status_visible()" } },
	T.command{ T.lua{ code = "sw_systems.show_status()" } },
})

function sw_systems.status_visible()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	return u ~= nil and (force.is_sensitive(u) or u.variables.sw_ow_active == true or force.is_suppressed(u))
end

function sw_systems.show_status()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u then return end
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
	wesnoth.wml_actions.message{ speaker = "narrator", caption = _ "Tactical status",
		image = "misc/sw-objective.png", message = table.concat(lines, "\n") }
end

core.log("systems", "tactical systems loaded")
