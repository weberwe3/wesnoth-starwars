-- Star Wars: Thrawn Trilogy -- command decisions.
--
-- Once per campaign, at the start of one mission (DECISION_AT), the player
-- chooses how High Command supports them for the rest of that campaign:
--   supply   Supply convoy: +SUPPLY_GOLD credits at the start of every later
--            mission of the campaign where the player can recruit.
--   cadre    Veteran cadre: CADRE_COUNT loyal units of the player's most
--            expensive recruit join at once, half-way to their next level.
--   counter  Counter-intelligence: Thrawn's Doctrine insight is capped at
--            COUNTER_CAP in every later mission, so it never reaches its top
--            tier (Coordinated fire).
-- An AI-controlled player side (soak tests) takes the supply convoy.
--
-- State: sw_command (campaign, choice, scenario it was made in), carried
-- between the campaign's missions.

local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")
local _w = wesnoth.textdomain("wesnoth")
local T = wml.tag

local command = {}
command.PLAYER_SIDE = 1
command.SUPPLY_GOLD = 25
command.CADRE_COUNT = 2
command.COUNTER_CAP = 75
command.DECISION_AT = {
	sw_hte_04_shadows_of_kashyyyk = true,
	sw_dfr_04_the_senators_men = true,
	sw_tlc_03_the_palace_infiltrators = true,
}
command.CHOICES = { "supply", "cadre", "counter" }
command.NAMES = {
	supply = _ "Supply convoy", cadre = _ "Veteran cadre", counter = _ "Counter-intelligence",
}

local function campaign_of(scenario_id)
	local key = tostring(scenario_id or ""):match("^sw_(%l+)_%d%d_")
	return key
end

-- The choice in force for this mission's campaign, or nil.
function command.current()
	local raw = wml.variables.sw_command
	if type(raw) ~= "table" or raw.campaign ~= campaign_of(wesnoth.scenario.id) then return nil end
	return raw.choice, raw.scenario
end

local function can_recruit(side)
	local s = wesnoth.sides[side]
	if not s or #s.recruit == 0 then return false end
	return #wesnoth.units.find_on_map{ side = side, canrecruit = true } > 0
end

-- The most expensive unit type the side can recruit now, or nil.
local function best_recruit(side)
	local best, cost
	for _i, id in ipairs(wesnoth.sides[side].recruit) do
		local ut = wesnoth.unit_types[id]
		if ut and (not cost or ut.cost > cost or (ut.cost == cost and id < best)) then best, cost = id, ut.cost end
	end
	return best
end

local function grant_cadre(side)
	local type_id = best_recruit(side)
	local leader = wesnoth.units.find_on_map{ side = side, canrecruit = true }[1]
	if not type_id or not leader then return 0 end
	local placed = 0
	for _i = 1, command.CADRE_COUNT do
		-- Core TRAIT_LOYAL, written out (macros are not available to Lua).
		local u = wesnoth.units.create{ type = type_id, side = side, random_traits = true,
			T.modifications{ T.trait{ id = "loyal", male_name = _w "loyal", female_name = _w "female^loyal",
				description = _w "Zero upkeep",
				T.effect{ apply_to = "loyal" }, T.effect{ apply_to = "overlay", add = "misc/loyal-icon.png" } } } }
		u.experience = math.floor(u.max_experience / 2)
		local x, y = wesnoth.paths.find_vacant_hex(leader.x, leader.y, u)
		if x then
			u:to_map(x, y)
			placed = placed + 1
		end
	end
	return placed, type_id
end

local function apply_counter()
	local doctrine = sw_systems and sw_systems.doctrine
	if not doctrine then return end
	for _i, d in ipairs(doctrine.enabled_sides()) do
		if d.cap > command.COUNTER_CAP then doctrine.set_cap(d.side, command.COUNTER_CAP) end
	end
end

-- Record the choice and apply its immediate part.
function command.decide(choice)
	wml.variables.sw_command = { campaign = campaign_of(wesnoth.scenario.id), choice = choice,
		scenario = wesnoth.scenario.id }
	core.log("command", "chose " .. choice)
	if choice == "cadre" then return grant_cadre(command.PLAYER_SIDE) end
	if choice == "counter" then apply_counter() end
	return 0
end

local function ask()
	local labels = {
		{ label = command.NAMES.supply, image = "icons/coins_copper.png",
			description = tostring(_ "+") .. command.SUPPLY_GOLD .. " " ..
				tostring(_ "credits at the start of every later mission of this campaign where you recruit") },
		{ label = command.NAMES.cadre, image = "icons/breastplate.png",
			description = tostring(_ "Two loyal units of your best recruit join now, half-way to their next level") },
		{ label = command.NAMES.counter, image = "icons/cloak_leather_brown.png",
			description = tostring(_ "For the rest of this campaign, Thrawn's Doctrine never reaches Coordinated fire (insight capped at") ..
				" " .. command.COUNTER_CAP .. ")" },
	}
	local pick = core.choose(_ "Command decision",
		_ "High Command can spare one kind of support for the rest of this campaign. Choose carefully: the choice stands until the campaign ends.",
		labels)
	return command.CHOICES[pick] or "supply"
end

-- start: make the campaign's decision, or apply the standing one.
function command.on_start()
	local side = wesnoth.sides[command.PLAYER_SIDE]
	if not side then return end
	local choice, made_in = command.current()
	if not choice then
		if not command.DECISION_AT[wesnoth.scenario.id] then return end
		command.decide(side.controller == "human" and ask() or "supply")
		return
	end
	if made_in == wesnoth.scenario.id then return end
	if choice == "supply" and can_recruit(command.PLAYER_SIDE) then
		side.gold = side.gold + command.SUPPLY_GOLD
		if side.controller == "human" then
			wesnoth.interface.add_chat_message(tostring(command.NAMES.supply),
				tostring(_ "+") .. command.SUPPLY_GOLD .. " " .. tostring(_ "credits"))
		end
	elseif choice == "counter" then
		apply_counter()
	end
end

return command
