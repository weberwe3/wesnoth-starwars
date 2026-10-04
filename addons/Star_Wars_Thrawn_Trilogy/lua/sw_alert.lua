-- Star Wars: Thrawn Trilogy -- guard alertness and stealth infiltration.
--
-- A scenario enables it with [sw_alert] action=enable guard_side= intruder_side=
-- (see wesnoth.wml_actions.sw_alert in lua/sw_systems.lua). Guards of the
-- guard side start UNAWARE: they hold their posts or walk a short patrol and
-- neither attack nor chase. A guard SPOTS an intruder unit that is in its
-- line of sight within its sight radius:
--
--   sight 3 (guard variable sw_alert_sight overrides; vornskrs 4)
--   -1 when the intruder stands in cover (forest, crates, settlements,
--      castles -- any hex giving at least 50% defence)
--   -1 at night (time of day with a negative lawful bonus)
--   +1 when the intruder fought this turn (noise)
--   adjacency always spots; walls block line of sight
--
-- A guard that spots an intruder becomes ALERT and shouts: every guard
-- within 4 hexes becomes alert too. Alert guards fight normally (their
-- guardian restriction is lifted). A guard one hex beyond its sight radius
-- is SUSPICIOUS ("?"), for display only. [sw_alert] action=alarm alerts
-- every guard (e.g. when the lightsaber is taken).
--
-- Intruders can make a SILENT TAKEDOWN (right-click menu) on an adjacent
-- unaware guard, using their attack: the guard is knocked out. Any other
-- unaware guard who can see the spot is alerted. Creatures (beast movement,
-- e.g. vornskrs) cannot be taken down.
--
-- Display: "!" over alert guards, "?" over suspicious ones, and the hexes
-- each unaware guard can see (an amber tint and rim, for the intruder team
-- only; on by default, toggled in the menu). A guard's hexes vanish as soon as
-- it is alerted or dies: refresh runs after every move, on attack end and on
-- die (lua/sw_systems.lua).
--
-- State: WML container sw_alert (scenario-stamped: sides, sight display);
-- guard unit variables sw_alert_state (unaware|alert), sw_alert_sight,
-- sw_alert_patrol (x,y;x,y waypoints), sw_alert_patrol_i; intruder variable
-- sw_alert_fought_turn. Deterministic: no randomness; fixed iteration order.

local T = wml.tag
local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local alert = {}

alert.SIGHT = 3
alert.BEAST_SIGHT = 4
alert.SHOUT = 4
alert.COVER_DEFENSE = 50      -- % defence at which a hex counts as cover
alert.SIGHT_IMAGE = "misc/sw-alert-sight.png"

-- Hooks: on_spotted(guard, intruder), on_alarm(side), can_spot(guard, intruder) -> bool
alert.hooks = { on_spotted = {}, on_alarm = {}, can_spot = {} }

-- ---------------------------------------------------------------- config

function alert.config()
	local raw = wml.variables.sw_alert
	if type(raw) ~= "table" or raw.scenario ~= core.scenario_id() then return nil end
	return raw
end

local function save_config(cfg)
	cfg.scenario = core.scenario_id()
	wml.variables.sw_alert = cfg
end

function alert.enabled() return alert.config() ~= nil end

function alert.enable(guard_side, intruder_side, show_sight)
	save_config{ guard_side = guard_side, intruder_side = intruder_side,
		show_sight = show_sight ~= false, alarm = false }
	for _i, g in ipairs(alert.guards()) do
		if g.variables.sw_alert_state == nil then g.variables.sw_alert_state = "unaware" end
	end
	alert.refresh()
end

function alert.guards()
	local cfg = alert.config()
	if not cfg then return {} end
	return core.sorted_by_id(wesnoth.units.find_on_map{ side = cfg.guard_side })
end

function alert.intruders()
	local cfg = alert.config()
	if not cfg then return {} end
	return core.sorted_by_id(wesnoth.units.find_on_map{ side = cfg.intruder_side })
end

function alert.is_unaware(g) return g.variables.sw_alert_state == "unaware" end

local function sight_of(g)
	local s = tonumber(g.variables.sw_alert_sight)
	if s then return s end
	return alert.is_creature(g) and alert.BEAST_SIGHT or alert.SIGHT
end

-- ---------------------------------------------------------------- line of sight

-- Walls (impassable terrain for the guard) between two hexes block sight.
-- The line is walked hex by hex toward the target, choosing the neighbour
-- closest to the target (ties broken by direction order): deterministic.
local DIRS = { "n", "ne", "se", "s", "sw", "nw" }
function alert.line_of_sight(g, x, y)
	local cx, cy = g.x, g.y
	local guard = 0
	while (cx ~= x or cy ~= y) and guard < 30 do
		guard = guard + 1
		local best, bd = nil, nil
		for _i, dir in ipairs(DIRS) do
			local n = wesnoth.map.get_direction({ cx, cy }, dir)
			local nx, ny = n[1] or n.x, n[2] or n.y
			local d = wesnoth.map.distance_between(nx, ny, x, y)
			if bd == nil or d < bd then best, bd = { nx, ny }, d end
		end
		cx, cy = best[1], best[2]
		if (cx ~= x or cy ~= y) and g:movement_on({ x = cx, y = cy }) >= 99 then return false end
	end
	return true
end

-- defense_on returns the unit's defence on the hex (chance to be hit is
-- 100 minus it).
function alert.in_cover(u)
	return u:defense_on({ x = u.x, y = u.y }) >= alert.COVER_DEFENSE
end

-- Creatures (beast movement, e.g. vornskrs): keener noses, no takedowns.
function alert.is_creature(u)
	local ut = wesnoth.unit_types[u.type]
	return ut ~= nil and ut.__cfg.movement_type == "sw_beast"
end

-- The radius at which this guard spots this intruder now.
local function dark_at(x, y)
	return wesnoth.schedule.get_illumination({ x = x, y = y }).lawful_bonus < 0
end

-- How far the guard sees across open ground now (night shortens it).
function alert.open_sight(g)
	local r = sight_of(g)
	if dark_at(g.x, g.y) then r = r - 1 end
	return math.max(1, r)
end

function alert.spot_radius(g, intruder)
	local r = sight_of(g)
	if dark_at(intruder.x, intruder.y) then r = r - 1 end
	if alert.in_cover(intruder) then r = r - 1 end
	if tonumber(intruder.variables.sw_alert_fought_turn) == wesnoth.current.turn then r = r + 1 end
	return math.max(1, r)
end

function alert.spots(g, intruder)
	if g.hitpoints <= 0 or intruder.hitpoints <= 0 then return false end
	local d = wesnoth.map.distance_between(g.x, g.y, intruder.x, intruder.y)
	if d <= 1 then return true end
	if d > alert.spot_radius(g, intruder) then return false end
	if not intruder:matches{ T.filter_vision{ side = g.side, visible = true } } then return false end
	if not alert.line_of_sight(g, intruder.x, intruder.y) then return false end
	for _i, hook in ipairs(alert.hooks.can_spot) do
		if hook(g, intruder) == false then return false end
	end
	return true
end

-- ---------------------------------------------------------------- state changes

local function set_alert(g)
	if not alert.is_unaware(g) then return false end
	g.variables.sw_alert_state = "alert"
	-- Alert guards hunt: drop the guardian restriction (ai_special=guardian
	-- is the unit status "guardian").
	g.status.guardian = false
	core.float(g.x, g.y, "!", "#ff5050")
	return true
end

-- A guard spots an intruder: it and every guard within shouting range.
function alert.raise(g, intruder)
	if not set_alert(g) then return end
	core.log("alert", g.id .. " spots " .. (intruder and intruder.id or "?") .. " and shouts")
	for _i, other in ipairs(alert.guards()) do
		if other.id ~= g.id and wesnoth.map.distance_between(g.x, g.y, other.x, other.y) <= alert.SHOUT then
			set_alert(other)
		end
	end
	for _i, hook in ipairs(alert.hooks.on_spotted) do hook(g, intruder) end
end

-- Every guard alert (scenario alarm).
function alert.alarm()
	local cfg = alert.config()
	if not cfg then return end
	cfg.alarm = true
	save_config(cfg)
	for _i, g in ipairs(alert.guards()) do set_alert(g) end
	core.log("alert", "alarm raised")
	for _i, hook in ipairs(alert.hooks.on_alarm) do hook(cfg.guard_side) end
	alert.refresh()
end

-- Check every unaware guard against every intruder; update indicators.
function alert.check()
	if not alert.enabled() then return end
	local intruders = alert.intruders()
	for _i, g in ipairs(alert.guards()) do
		if alert.is_unaware(g) then
			for _j, it in ipairs(intruders) do
				if alert.is_unaware(g) and alert.spots(g, it) then alert.raise(g, it) end
			end
		end
	end
	alert.refresh()
end

-- ---------------------------------------------------------------- display

function alert.refresh()
	local cfg = alert.config()
	if not cfg then return end
	local intruders = alert.intruders()
	local team = core.team_key(cfg.intruder_side)
	local sight = {}
	for _i, g in ipairs(alert.guards()) do
		local mark = nil
		if g.hitpoints <= 0 then
			-- Dying (the die event runs while the unit is still on the map): no
			-- sight hexes; the unit and its overlay go with it.
		elseif not alert.is_unaware(g) then
			mark = "misc/sw-alert-alert.png"
		else
			for _j, it in ipairs(intruders) do
				local d = wesnoth.map.distance_between(g.x, g.y, it.x, it.y)
				if d == alert.spot_radius(g, it) + 1 and alert.line_of_sight(g, it.x, it.y) then
					mark = "misc/sw-alert-suspicious.png"
				end
			end
			if cfg.show_sight then
				for _j, loc in ipairs(wesnoth.map.find{ x = g.x, y = g.y, radius = alert.open_sight(g) }) do
					local x, y = loc[1] or loc.x, loc[2] or loc.y
					if (x ~= g.x or y ~= g.y) and alert.line_of_sight(g, x, y) then sight[core.key(x, y)] = { x = x, y = y } end
				end
			end
		end
		core.set_overlay(g, "alert", mark)
	end
	-- Sight hexes: team-private items, diffed against the last drawing.
	local old = {}
	for _i, loc in ipairs(wml.array_access.get("sw_alert_drawn")) do old[core.key(loc.x, loc.y)] = loc end
	for _i, k in ipairs(core.sorted_keys(old)) do
		if not sight[k] then wesnoth.interface.remove_item(old[k].x, old[k].y, "sw_alert_sight") end
	end
	local list = {}
	for _i, k in ipairs(core.sorted_keys(sight)) do
		local loc = sight[k]
		if not old[k] then
			wesnoth.wml_actions.item{ x = loc.x, y = loc.y, image = alert.SIGHT_IMAGE, name = "sw_alert_sight",
				team_name = team, redraw = false }
		end
		table.insert(list, loc)
	end
	wml.array_access.set("sw_alert_drawn", list)
	wesnoth.wml_actions.redraw{}
end

-- ---------------------------------------------------------------- turn cycle

-- Start of the guard side's turn: patrols take a step; unaware guards
-- neither move further nor attack this turn.
function alert.on_side_turn(side)
	local cfg = alert.config()
	if not cfg or side ~= cfg.guard_side then
		if cfg then alert.check() end
		return
	end
	for _i, g in ipairs(alert.guards()) do
		if alert.is_unaware(g) then
			local route = core.split(g.variables.sw_alert_patrol or "")
			if #route > 0 then
				local i = (tonumber(g.variables.sw_alert_patrol_i) or 0) % #route + 1
				local x, y = route[i]:match("(%d+)%.(%d+)")
				x, y = tonumber(x), tonumber(y)
				if x and not wesnoth.units.get(x, y) then
					wesnoth.wml_actions.move_unit{ id = g.id, to_x = x, to_y = y, fire_event = true }
				end
				g = wesnoth.units.get(g.id)
				if g then g.variables.sw_alert_patrol_i = i end
			end
			if g and alert.is_unaware(g) then
				g.moves = 0
				g.attacks_left = 0
			end
		end
	end
	alert.check()
end

-- attack event: both sides of a fight make noise this turn.
function alert.on_attack()
	if not alert.enabled() then return end
	local ctx = wesnoth.current.event_context
	for _i, loc in ipairs{ { ctx.x1, ctx.y1 }, { ctx.x2, ctx.y2 } } do
		local u = wesnoth.units.get(loc[1], loc[2])
		if u then u.variables.sw_alert_fought_turn = wesnoth.current.turn end
		-- An unaware guard that is attacked knows it.
		if u and alert.is_unaware(u) then alert.raise(u, nil) end
	end
end

-- ---------------------------------------------------------------- takedown

function alert.takedown_targets(u)
	local cfg = alert.config()
	if not cfg or u.side ~= cfg.intruder_side or u.attacks_left < 1 then return {} end
	local out = {}
	for _i, g in ipairs(alert.guards()) do
		if alert.is_unaware(g) and not alert.is_creature(g) and
			wesnoth.map.distance_between(u.x, u.y, g.x, g.y) == 1 then
			table.insert(out, g)
		end
	end
	return out
end

function alert.takedown(u, g)
	if not alert.is_unaware(g) or u.attacks_left < 1 then return false end
	u.attacks_left = 0
	local x, y = g.x, g.y
	core.log("alert", u.id .. " takes down " .. g.id)
	core.float(x, y, _ "knocked out", "#cfd8ff")
	wesnoth.wml_actions.kill{ id = g.id, animate = true, fire_event = true }
	-- Witnesses: any other unaware guard who can see the spot.
	for _i, other in ipairs(alert.guards()) do
		if alert.is_unaware(other) and wesnoth.map.distance_between(other.x, other.y, x, y) <= alert.open_sight(other)
			and alert.line_of_sight(other, x, y) then
			alert.raise(other, u)
		end
	end
	alert.check()
	return true
end

function alert.takedown_menu_visible()
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	return u ~= nil and core.is_local_turn_of(u.side) and #alert.takedown_targets(u) > 0
end

function alert.takedown_menu_command()
	local ctx = core.menu_context()
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u then return end
	local targets = alert.takedown_targets(u)
	local target = targets[1]
	if #targets > 1 then
		local labels = {}
		for _i, g in ipairs(targets) do
			table.insert(labels, tostring(wesnoth.unit_types[g.type].name) .. " (" .. g.x .. "," .. g.y .. ")")
		end
		table.insert(labels, tostring(_ "Cancel"))
		target = targets[core.choose(_ "Silent takedown",
			_ "Knock out an unaware guard next to you. It uses your attack. Any other guard who can see this spot will raise the alarm.",
			labels)]
	end
	if target then alert.takedown(u, target) end
end

function alert.sight_menu_visible()
	local cfg = alert.config()
	local side = core.viewing_side()
	return cfg ~= nil and side == cfg.intruder_side and core.is_local_turn_of(side)
end

function alert.sight_menu_command()
	local cfg = alert.config()
	if not cfg then return end
	cfg.show_sight = not cfg.show_sight
	save_config(cfg)
	alert.refresh()
end

return alert
