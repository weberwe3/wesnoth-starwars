-- Star Wars: Thrawn Trilogy -- attack range display.
--
-- Right-click any unit the viewer can see and choose "Show attack range":
--   solid markers  hexes it can attack from where it stands (each weapon's
--                  min_range..max_range, so a rifle marks 1-2, an aimed shot
--                  only 2, a pistol 1)
--   dotted markers hexes it could attack after moving (its own units: the
--                  moves it has left; other units: a full move)
-- One display per team at a time, visible to that team only. It clears when
-- the unit moves, at the start of the next turn, or with "Hide attack
-- range". (Wesnoth gives add-ons no safe hook on unit selection, so the
-- display is a menu command; it is synced and multiplayer-safe.)
--
-- State: WML array sw_range_shown (team, unit, x, y, kind) per drawn hex.

local T = wml.tag
local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local range = {}

-- Distances (as a set) at which the unit has a usable weapon.
function range.distances(u)
	local out, maxd = {}, 0
	for _i, a in ipairs(u.attacks) do
		local lo, hi = a.min_range or 1, a.max_range or 1
		for d = lo, hi do out[d] = true end
		maxd = math.max(maxd, hi)
	end
	return out, maxd
end

-- Hexes the unit can attack from where it stands, and after moving.
function range.zones(u, full_move)
	local dists, maxd = range.distances(u)
	local direct, moving = {}, {}
	if maxd == 0 then return direct, moving end
	for _i, loc in ipairs(wesnoth.map.find{ x = u.x, y = u.y, radius = maxd }) do
		local x, y = loc[1] or loc.x, loc[2] or loc.y
		if dists[wesnoth.map.distance_between(u.x, u.y, x, y)] then direct[core.key(x, y)] = { x = x, y = y } end
	end
	local reach = wesnoth.paths.find_reach(u, { moves = full_move and "max" or "current" })
	for _i, r in ipairs(reach) do
		local rx, ry = r[1] or r.x, r[2] or r.y
		local occupant = wesnoth.units.get(rx, ry)
		if not occupant or occupant.id == u.id then
			for _j, loc in ipairs(wesnoth.map.find{ x = rx, y = ry, radius = maxd }) do
				local x, y = loc[1] or loc.x, loc[2] or loc.y
				local k = core.key(x, y)
				if not direct[k] and dists[wesnoth.map.distance_between(rx, ry, x, y)] then moving[k] = { x = x, y = y } end
			end
		end
	end
	return direct, moving
end

local function item_name(kind) return "sw_range_" .. kind end

-- Remove a team's display (or every team's when team is nil).
function range.clear(team)
	local keep = {}
	local changed = false
	for _i, e in ipairs(wml.array_access.get("sw_range_shown")) do
		if team == nil or e.team == team then
			wesnoth.interface.remove_item(e.x, e.y, item_name(e.kind))
			changed = true
		else
			table.insert(keep, e)
		end
	end
	wml.array_access.set("sw_range_shown", keep)
	if changed then wesnoth.wml_actions.redraw{} end
end

function range.shown_unit(team)
	for _i, e in ipairs(wml.array_access.get("sw_range_shown")) do
		if e.team == team then return e.unit end
	end
	return nil
end

function range.show(u, side)
	local team = core.team_key(side)
	range.clear(team)
	local direct, moving = range.zones(u, u.side ~= side)
	local shown = wml.array_access.get("sw_range_shown")
	for _i, pair in ipairs{ { direct, "direct" }, { moving, "move" } } do
		local zone, kind = pair[1], pair[2]
		for _j, k in ipairs(core.sorted_keys(zone)) do
			local h = zone[k]
			wesnoth.wml_actions.item{ x = h.x, y = h.y, image = "misc/sw-range-" .. kind .. ".png",
				name = item_name(kind), team_name = team, redraw = false }
			table.insert(shown, { team = team, unit = u.id, x = h.x, y = h.y, kind = kind })
		end
	end
	wml.array_access.set("sw_range_shown", shown)
	wesnoth.wml_actions.redraw{}
	core.log("range", "team " .. team .. " shows the attack range of " .. u.id)
end

-- moveto: a moved unit's display is out of date.
function range.on_moveto()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u then return end
	local stale = {}
	for _i, e in ipairs(wml.array_access.get("sw_range_shown")) do
		if e.unit == u.id then stale[e.team] = true end
	end
	for _i, team in ipairs(core.sorted_keys(stale)) do range.clear(team) end
end

function range.on_turn() range.clear(nil) end

-- ---------------------------------------------------------------- menus

local function seen_unit()
	local side = core.viewing_side()
	if not side or side < 1 then return nil end
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u or #u.attacks == 0 then return nil end
	if not u:matches{ T.filter_vision{ side = side, visible = true } } then return nil end
	return u, side
end

function range.show_menu_visible()
	local u, side = seen_unit()
	return u ~= nil and range.shown_unit(core.team_key(side)) ~= u.id
end

function range.hide_menu_visible()
	local side = core.viewing_side()
	return side ~= nil and side >= 1 and range.shown_unit(core.team_key(side)) ~= nil
end

function range.show_menu_command()
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u or not u:matches{ T.filter_vision{ side = wesnoth.current.side, visible = true } } then return end
	range.show(u, wesnoth.current.side)
end

function range.hide_menu_command()
	range.clear(core.team_key(wesnoth.current.side))
end

return range
