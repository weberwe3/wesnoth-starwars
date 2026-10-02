-- Star Wars: Thrawn Trilogy -- shared helpers for the tactical systems.
--
-- Loaded by lua/sw_systems.lua in every mission (utils/hte_macros.cfg). All
-- persistent state lives in WML variables and unit variables so it survives
-- save/load and replays; nothing here keeps gameplay state in Lua tables
-- across events except caches that are rebuilt from that state.

local T = wml.tag
local core = {}

-- Debug logging: set the WML variable sw_systems_debug=yes (or call
-- sw_systems.core.set_debug(true)) to print system decisions to the log.
function core.debug_enabled()
	return wml.variables.sw_systems_debug == true or wml.variables.sw_systems_debug == "yes"
end

function core.log(system, text)
	if core.debug_enabled() then
		std_print("SW_SYSTEMS[" .. system .. "]: " .. text)
	end
end

function core.set_debug(on)
	wml.variables.sw_systems_debug = on and true or nil
end

-- Read the attributes of an ability (any tag, matched by id) on a unit. Unit
-- authors configure the systems declaratively, e.g.
--   [dummy] id=sw_ability_force fp_max=8 fp_regen=2 powers=push,pull [/dummy]
-- Returns the attribute table, or nil if the unit lacks the ability.
function core.ability_cfg(u, ability_id)
	local abilities = wml.get_child(u.__cfg, "abilities")
	if not abilities then return nil end
	for _, entry in ipairs(abilities) do
		local content = entry[2]
		if type(content) == "table" and content.id == ability_id then
			return content
		end
	end
	return nil
end

function core.has_ability(u, ability_id)
	return u:matches{ ability = ability_id }
end

function core.split(list)
	local out = {}
	for item in tostring(list or ""):gmatch("[^,%s]+") do table.insert(out, item) end
	return out
end

function core.number(value, default)
	local n = tonumber(value)
	if n == nil then return default end
	return n
end

function core.key(x, y)
	return x .. "," .. y
end

-- Deterministic player choice. [message] options are synced choices in
-- Wesnoth, so the selected index is recorded in replays and identical on
-- every multiplayer client. Returns the 1-based index, or 0 if dismissed.
function core.choose(caption, text, labels, image)
	local options = {}
	for i, label in ipairs(labels) do
		table.insert(options, T.option{
			label = label,
			T.command{ T.set_variable{ name = "sw_systems_choice", value = i } },
		})
	end
	wml.variables.sw_systems_choice = 0
	local cfg = {
		speaker = "narrator",
		caption = caption,
		message = text,
		image = image or "misc/sw-objective.png",
	}
	for _, o in ipairs(options) do table.insert(cfg, o) end
	wesnoth.wml_actions.message(cfg)
	local choice = tonumber(wml.variables.sw_systems_choice) or 0
	wml.variables.sw_systems_choice = nil
	return choice
end

-- A small transient label over a hex (display only; no gameplay effect).
function core.float(x, y, text, color)
	wesnoth.interface.float_label(x, y, "<span color='" .. (color or "#ffffff") .. "'>" .. text .. "</span>")
end

-- Show one indicator image in a named slot (e.g. "force", "overwatch"), or
-- clear it with nil. Like the core [unit_overlay] action, this only ever ADDS
-- overlay add/remove objects: removing a modification rebuilds the unit, which
-- would reset transient state such as extra movement mid-turn. The current
-- image is tracked in a unit variable so unchanged indicators cost nothing.
-- core.compact_overlays collapses the accumulated objects at mission start.
function core.set_overlay(u, slot, image)
	local key = "sw_overlay_" .. slot
	local current = u.variables[key]
	if current == image then return end
	if current then
		u:add_modification("object", { id = "sw_ui_overlay", T.effect{ apply_to = "overlay", remove = current } })
	end
	if image then
		u:add_modification("object", { id = "sw_ui_overlay", T.effect{ apply_to = "overlay", add = image } })
	end
	u.variables[key] = image
end

core.OVERLAY_SLOTS = { "force", "overwatch", "dazed" }

-- At mission start (units are at full moves, so a rebuild is harmless):
-- replace all indicator objects with one per shown image.
function core.compact_overlays(u)
	u:remove_modifications({ id = "sw_ui_overlay" }, "object")
	for _, slot in ipairs(core.OVERLAY_SLOTS) do
		local image = u.variables["sw_overlay_" .. slot]
		if image then
			u:add_modification("object", { id = "sw_ui_overlay", T.effect{ apply_to = "overlay", add = image } })
		end
	end
end

-- Units in a stable order (by id) so every client iterates identically.
function core.sorted_by_id(units)
	table.sort(units, function(a, b) return a.id < b.id end)
	return units
end

-- Whether it is a human player's own turn for this side (menu visibility).
function core.is_local_turn_of(side)
	return wesnoth.current.side == side and wesnoth.sides[side].is_local
		and wesnoth.sides[side].controller == "human"
end

return core
