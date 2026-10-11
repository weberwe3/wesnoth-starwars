-- Star Wars: Thrawn Trilogy -- mission debrief.
--
-- At victory the player sees how the mission went: turns used, enemies
-- destroyed, units lost, heroes withdrawn, the bonus objective (lua/sw_bonus.lua)
-- and the Hit and Run target (lua/sw_achievements.lua). One message, shown only
-- to the human player; counting is the only state (sw_debrief, stamped with
-- the scenario id).

local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local debrief = {}
debrief.PLAYER_SIDE = 1

local function load()
	local raw = wml.variables.sw_debrief
	if type(raw) ~= "table" or raw.scenario ~= wesnoth.scenario.id then
		return { scenario = wesnoth.scenario.id, kills = 0, losses = 0, withdrawn = 0 }
	end
	return { scenario = raw.scenario, kills = tonumber(raw.kills) or 0, losses = tonumber(raw.losses) or 0,
		withdrawn = tonumber(raw.withdrawn) or 0 }
end

local function save(d) wml.variables.sw_debrief = d end

function debrief.on_die()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if not u then return end
	local d = load()
	if u.side == debrief.PLAYER_SIDE then
		d.losses = d.losses + 1
	elseif wesnoth.sides.is_enemy(u.side, debrief.PLAYER_SIDE) and #u.attacks > 0 then
		d.kills = d.kills + 1
	end
	save(d)
end

function debrief.on_withdraw(_id)
	local d = load()
	d.withdrawn = d.withdrawn + 1
	save(d)
end

-- The debrief text for this victory (used by on_victory and the tests).
function debrief.text()
	local d = load()
	local turns = wesnoth.scenario.turns
	local lines = {}
	if turns and turns > 0 then
		table.insert(lines, tostring(_ "Mission complete on turn") .. " " .. wesnoth.current.turn .. " " ..
			tostring(_ "of") .. " " .. turns .. ".")
	end
	table.insert(lines, tostring(_ "Enemies destroyed:") .. " " .. d.kills .. "    " ..
		tostring(_ "Units lost:") .. " " .. d.losses .. "    " .. tostring(_ "Heroes withdrawn:") .. " " .. d.withdrawn)
	local result = wml.variables.sw_bonus_result
	if type(result) == "table" and result.scenario == wesnoth.scenario.id then
		if result.state == "complete" then
			table.insert(lines, tostring(_ "Bonus objective complete:") .. " " .. tostring(result.gold) .. " " ..
				tostring(_ "credits banked, paid in full at the start of the next mission where you can recruit."))
		else
			table.insert(lines, tostring(_ "Bonus objective missed."))
		end
	end
	local ach = sw_systems and sw_systems.achievements
	if ach and ach.campaign_of(wesnoth.scenario.id) and not ach.HOLD_OUT[wesnoth.scenario.id] and turns and turns > 0 then
		if ach.is_swift(wesnoth.current.turn, turns) then
			table.insert(lines, tostring(_ "Hit and Run: a swift victory."))
		else
			table.insert(lines, tostring(_ "Hit and Run: win by turn") .. " " .. (turns - math.ceil(turns / 3)) .. " " ..
				tostring(_ "for a swift victory."))
		end
	end
	return table.concat(lines, "\n")
end

function debrief.on_victory()
	local side = wesnoth.sides[debrief.PLAYER_SIDE]
	if not side or side.controller ~= "human" then return end
	wesnoth.wml_actions.message{ speaker = "narrator", image = "misc/sw-objective.png",
		caption = _ "Mission debrief", message = debrief.text() }
end

return debrief
