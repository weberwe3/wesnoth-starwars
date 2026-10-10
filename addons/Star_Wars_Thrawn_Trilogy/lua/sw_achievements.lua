-- Star Wars: Thrawn Trilogy -- achievements (definitions: achievements.cfg).
--
-- Registered by sw_systems.lua in every mission. Only the human player's side
-- (side 1) earns them; the engine itself skips saving progress in replays
-- (game_lua_kernel.cpp, intf_set_achievement). Scenarios outside the three
-- campaigns (engine tests) are ignored.
--
--   sw_complete / sw_hard  victory in the campaign's last mission (Hard: on Hard)
--   sw_unbroken            ... with no hero withdrawn all campaign
--                          (WML variable sw_ach_withdrawals, SW_HERO_WITHDRAWS)
--   sw_swift               sub-achievement per mission: victory with at least
--                          a third of the turns unused (hold-out missions excluded)
--   sw_ace                 progress: enemy starfighters/warships destroyed by side 1
--   Tactics group          trilogy complete; Force powers, overwatch, sweeps, air calls

local ach = {}

ach.TACTICS = "Star_Wars_Thrawn_Trilogy_Tactics"
ach.CAMPAIGNS = {
	hte = "Star_Wars_Thrawn_Trilogy",
	dfr = "Star_Wars_Thrawn_Trilogy_Dark_Force_Rising",
	tlc = "Star_Wars_Thrawn_Trilogy_The_Last_Command",
}
ach.FINALS = {
	sw_hte_10_thrawns_gambit = true,
	sw_dfr_10_honoghrs_choice = true,
	sw_tlc_10_the_last_command = true,
}
-- Won by holding out until the last turn: no swift victory possible.
ach.HOLD_OUT = {
	sw_hte_03_adrift = true, sw_hte_04_shadows_of_kashyyyk = true,
	sw_hte_08_nomad_city = true, sw_hte_10_thrawns_gambit = true,
	sw_dfr_05_peregrines_nest = true, sw_dfr_10_honoghrs_choice = true,
	sw_tlc_02_the_smugglers_council = true,
}
ach.SHIPS = { sw_starfighter = true, sw_capital = true }
ach.PLAYER_SIDE = 1

-- The campaign id (achievement group) of a mission id, or nil.
function ach.campaign_of(scenario_id)
	local key = tostring(scenario_id or ""):match("^sw_(%l+)_%d%d_")
	return key and ach.CAMPAIGNS[key]
end

-- At least a third of the turn limit left unused.
function ach.is_swift(turn, turns)
	return turns ~= nil and turns > 0 and (turns - turn) * 3 >= turns
end

local function player_is_human()
	local side = wesnoth.sides[ach.PLAYER_SIDE]
	return side ~= nil and side.controller == "human"
end

-- Achievement calls raise an error when the group is missing (e.g. the add-on
-- was installed without achievements.cfg); never let that break a mission.
local function call(f, ...)
	local ok, err = pcall(f, ...)
	if not ok then wesnoth.log("warning", "sw_achievements: " .. tostring(err)) end
end

function ach.set(group, id) call(wesnoth.achievements.set, group, id) end
function ach.progress(group, id) call(wesnoth.achievements.progress, group, id, 1) end
function ach.set_sub(group, id, sub) call(wesnoth.achievements.set_sub_achievement, group, id, sub) end

function ach.on_victory()
	local scenario = wesnoth.scenario.id
	local group = ach.campaign_of(scenario)
	if not group or not player_is_human() then return end
	if not ach.HOLD_OUT[scenario] and ach.is_swift(wesnoth.current.turn, wesnoth.scenario.turns) then
		ach.set_sub(group, "sw_swift", scenario)
	end
	if not ach.FINALS[scenario] then return end
	ach.set(group, "sw_complete")
	if wesnoth.scenario.difficulty == "HARD" then ach.set(group, "sw_hard") end
	if (tonumber(wml.variables.sw_ach_withdrawals) or 0) == 0 then ach.set(group, "sw_unbroken") end
	local all = true
	for _key, other in pairs(ach.CAMPAIGNS) do
		if not wesnoth.achievements.has(other, "sw_complete") then all = false end
	end
	if all then ach.set(ach.TACTICS, "sw_trilogy") end
end

function ach.on_die()
	local ctx = wesnoth.current.event_context
	local group = ach.campaign_of(wesnoth.scenario.id)
	if not group or not ctx.x2 or not player_is_human() then return end
	local victim = wesnoth.units.get(ctx.x1, ctx.y1)
	local killer = wesnoth.units.get(ctx.x2, ctx.y2)
	if not victim or not killer or killer.side ~= ach.PLAYER_SIDE then return end
	if not wesnoth.sides.is_enemy(victim.side, ach.PLAYER_SIDE) then return end
	local ut = wesnoth.unit_types[victim.type]
	if ut and ach.SHIPS[ut.__cfg.movement_type] then ach.progress(group, "sw_ace") end
end

-- A tactic used by unit u (Force power, overwatch, sweep) or air support for a side.
function ach.on_tactic(side, id)
	if side ~= ach.PLAYER_SIDE or not ach.campaign_of(wesnoth.scenario.id) or not player_is_human() then return end
	ach.progress(ach.TACTICS, id)
end

return ach
