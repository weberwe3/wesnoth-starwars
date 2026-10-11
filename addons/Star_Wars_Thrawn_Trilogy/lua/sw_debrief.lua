-- Star Wars: Thrawn Trilogy -- mission debrief.
--
-- At victory the player sees how the mission went: turns used, enemies
-- destroyed, units lost, heroes withdrawn, the bonus objective (lua/sw_bonus.lua)
-- and the Hit and Run target (lua/sw_achievements.lua). One message, shown only
-- to the human player. Each victory also adds to the campaign's totals, shown
-- as a campaign summary after the finale. Counting is the only state:
-- sw_debrief (this mission, stamped with the scenario id) and
-- sw_campaign_stats (carried between the campaign's missions).

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

local function swift_now()
	local ach = sw_systems and sw_systems.achievements
	local turns = wesnoth.scenario.turns
	return ach and ach.campaign_of(wesnoth.scenario.id) and not ach.HOLD_OUT[wesnoth.scenario.id]
		and turns and turns > 0 and ach.is_swift(wesnoth.current.turn, turns)
end

local STAT_KEYS = { "missions", "kills", "losses", "withdrawn", "bonus", "swift" }

function debrief.campaign_stats()
	local raw = wml.variables.sw_campaign_stats
	local st = { last = type(raw) == "table" and raw.last or "" }
	for _i, k in ipairs(STAT_KEYS) do st[k] = type(raw) == "table" and tonumber(raw[k]) or 0 end
	return st
end

-- Add this mission to the campaign totals, once.
function debrief.record()
	local st = debrief.campaign_stats()
	if st.last == wesnoth.scenario.id then return st end
	local d = load()
	local result = wml.variables.sw_bonus_result
	st.last = wesnoth.scenario.id
	st.missions = st.missions + 1
	st.kills = st.kills + d.kills
	st.losses = st.losses + d.losses
	st.withdrawn = st.withdrawn + d.withdrawn
	if type(result) == "table" and result.scenario == wesnoth.scenario.id and result.state == "complete" then
		st.bonus = st.bonus + 1
	end
	if swift_now() then st.swift = st.swift + 1 end
	wml.variables.sw_campaign_stats = st
	return st
end

function debrief.campaign_text(st)
	local lines = {
		tostring(_ "Missions won:") .. " " .. st.missions,
		tostring(_ "Enemies destroyed:") .. " " .. st.kills .. "    " .. tostring(_ "Units lost:") .. " " .. st.losses ..
			"    " .. tostring(_ "Heroes withdrawn:") .. " " .. st.withdrawn,
		tostring(_ "Bonus objectives earned:") .. " " .. st.bonus .. "    " ..
			tostring(_ "Swift victories:") .. " " .. st.swift,
	}
	-- The campaign's command decision (lua/sw_command.lua).
	local cmd = sw_systems and sw_systems.command
	local choice = cmd and cmd.current()
	if choice and cmd.NAMES[choice] then
		table.insert(lines, tostring(_ "Command decision:") .. " " .. tostring(cmd.NAMES[choice]))
	end
	return table.concat(lines, "\n")
end

function debrief.on_victory()
	local st = debrief.record()
	local side = wesnoth.sides[debrief.PLAYER_SIDE]
	if not side or side.controller ~= "human" then return end
	wesnoth.wml_actions.message{ speaker = "narrator", image = "misc/sw-objective.png",
		caption = _ "Mission debrief", message = debrief.text() }
	local ach = sw_systems and sw_systems.achievements
	if ach and ach.FINALS[wesnoth.scenario.id] then
		wesnoth.wml_actions.message{ speaker = "narrator", image = "misc/sw-objective.png",
			caption = _ "Campaign summary", message = debrief.campaign_text(st) }
	end
end

return debrief
