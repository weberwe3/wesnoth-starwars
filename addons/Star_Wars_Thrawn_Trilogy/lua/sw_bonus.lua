-- Star Wars: Thrawn Trilogy -- bonus objectives.
--
-- Each mission (except the campaign finales) has one optional objective that
-- rewards a different way of playing it: secure the settlements, bring
-- everyone home, keep named heroes in the fight, stay undetected, or the
-- mission's own challenge. The objective is shown in the mission objectives
-- (SW_BONUS_OBJECTIVE) and configured by SW_BONUS (utils/hte_macros.cfg).
--
-- Reward: credits banked at victory and paid in full -- not cut by the 40%
-- gold carryover -- at the start of the next mission where the player can
-- recruit (sw_bonus_bank, carried between missions).
--
-- State: sw_bonus (this mission's objective: scenario, kind, value, gold,
-- failed, label), sw_bonus_bank (credits waiting).
--
-- Kinds: villages N (hold N villages at victory); no_losses (no unit of the
-- player's dies); heroes ID,ID (those units still on the map at victory);
-- undetected (the alarm is never raised: sw_alert); flag VAR (a scenario
-- variable is yes at victory).

local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local bonus = {}
bonus.PLAYER_SIDE = 1

function bonus.config()
	local raw = wml.variables.sw_bonus
	if type(raw) ~= "table" or raw.scenario ~= wesnoth.scenario.id then return nil end
	return raw
end

local function save(cfg) wml.variables.sw_bonus = cfg end

-- Set by SW_BONUS at prestart.
function bonus.define(kind, value, gold)
	save{ scenario = wesnoth.scenario.id, kind = kind, value = tostring(value or ""), gold = tonumber(gold) or 40,
		failed = false }
end

local function fail(cfg, why)
	if cfg.failed then return end
	cfg.failed = true
	save(cfg)
	if wesnoth.sides[bonus.PLAYER_SIDE].controller == "human" then
		wesnoth.wml_actions.message{ speaker = "narrator", image = "misc/sw-objective.png",
			caption = _ "Bonus objective", message = tostring(_ "The bonus objective is lost: ") .. tostring(why) }
	end
end

function bonus.met(cfg)
	if cfg.failed then return false end
	local kind, value = cfg.kind, cfg.value
	if kind == "villages" then
		return #wesnoth.map.find{ gives_income = true, owner_side = bonus.PLAYER_SIDE } >= (tonumber(value) or 1)
	elseif kind == "no_losses" then
		return true
	elseif kind == "heroes" then
		for _i, id in ipairs(core.split(value)) do
			local u = wesnoth.units.get(id)
			if not u or u.side ~= bonus.PLAYER_SIDE then return false end
		end
		return true
	elseif kind == "undetected" then
		local a = wml.variables.sw_alert
		return not (type(a) == "table" and a.alarm == true)
	elseif kind == "flag" then
		local v = wml.variables[value]
		return v == true or v == "yes"
	end
	return false
end

-- die: a player unit's death loses "no_losses".
function bonus.on_die()
	local cfg = bonus.config()
	if not cfg or cfg.kind ~= "no_losses" then return end
	local u = wesnoth.units.get(wesnoth.current.event_context.x1, wesnoth.current.event_context.y1)
	if u and u.side == bonus.PLAYER_SIDE then fail(cfg, _ "a unit was lost.") end
end

-- A hero withdraws (SW_HERO_WITHDRAWS): "heroes" naming it is lost.
function bonus.on_withdraw(id)
	local cfg = bonus.config()
	if not cfg or cfg.kind ~= "heroes" then return end
	for _i, h in ipairs(core.split(cfg.value)) do
		if h == id then fail(cfg, _ "a hero had to withdraw.") return end
	end
end

-- Alarm raised: "undetected" is lost.
function bonus.on_alarm()
	local cfg = bonus.config()
	if cfg and cfg.kind == "undetected" then fail(cfg, _ "the alarm was raised.") end
end

-- victory: bank the reward.
function bonus.on_victory()
	local cfg = bonus.config()
	if not cfg or cfg.paid then return end
	local met = bonus.met(cfg)
	local gold = tonumber(cfg.gold) or 0
	if met then
		wml.variables.sw_bonus_bank = (tonumber(wml.variables.sw_bonus_bank) or 0) + gold
	end
	cfg.paid = true      -- decided once
	cfg.failed = true
	save(cfg)
	-- Reported by the mission debrief (lua/sw_debrief.lua).
	wml.variables.sw_bonus_result = { scenario = wesnoth.scenario.id, state = met and "complete" or "missed", gold = gold }
end

local function can_recruit(side)
	local s = wesnoth.sides[side]
	if not s or #s.recruit == 0 then return false end
	return #wesnoth.units.find_on_map{ side = side, canrecruit = true } > 0
end

-- start (after the scenario's prestart has placed the leader): pay the bank.
function bonus.on_start()
	local bank = tonumber(wml.variables.sw_bonus_bank) or 0
	if bank <= 0 or not can_recruit(bonus.PLAYER_SIDE) then return end
	local side = wesnoth.sides[bonus.PLAYER_SIDE]
	side.gold = side.gold + bank
	wml.variables.sw_bonus_bank = nil
	core.log("bonus", "paid " .. bank .. " banked credits")
	if side.controller == "human" then
		wesnoth.wml_actions.message{ speaker = "narrator", image = "misc/sw-objective.png",
			caption = _ "Bonus credits", message = tostring(_ "Your bonus objectives earned ") .. bank ..
				tostring(_ " credits for this mission.") }
	end
end

return bonus
