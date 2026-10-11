-- Star Wars: Thrawn Trilogy -- just-in-time tips.
--
-- The tactical systems (the Force, overwatch, ranges, flanking, sensors, air
-- support, stealth, Thrawn's Doctrine, ranks) are explained in the Field
-- Manual, but a new player meets them mid-mission. Each tip appears once per
-- playthrough, the first time its system matters to the player, at the start
-- of the player's turn (side 1, human); at most one tip per turn, in the
-- order below. "Turn off tips" stops them for the rest of the playthrough.
--
-- State (WML variables, carried between missions): sw_tips_seen (comma list
-- of tip ids), sw_tips_off (yes). Scenario authors can skip all tips with
-- sw_tips_off=yes.

local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local T = wml.tag
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local tips = {}
tips.PLAYER_SIDE = 1

local function player_units(filter)
	filter = filter or {}
	filter.side = tips.PLAYER_SIDE
	return wesnoth.units.find_on_map(filter)
end

local function enemies_of_player()
	local out = {}
	for _i, u in ipairs(wesnoth.units.find_on_map{}) do
		if wesnoth.sides.is_enemy(u.side, tips.PLAYER_SIDE) then table.insert(out, u) end
	end
	return out
end

-- Each tip: id, trigger (true when the system matters now), caption, text.
tips.LIST = {
	{ id = "ranges",
	  when = function()
		for _i, u in ipairs(player_units()) do
			for _j, a in ipairs(u.attacks) do if a.range == "ranged" and (a.max_range or 1) >= 2 then return true end end
		end
	  end,
	  caption = _ "Weapon ranges",
	  text = _ "Blasters reach beyond the next hex: a rifle hits 2 hexes away, heavy weapons 3, with -10% to hit per hex beyond the first. A defender only shoots back if its weapon reaches that far, so keep your riflemen at range from pistols and blades.\n\nRight-click any unit and choose <b>Show attack range</b> to see where it can strike. Rifles also offer an <b>aimed shot</b>: one shot fewer, +20% to hit." },
	{ id = "force",
	  when = function() return #player_units{ ability = "sw_ability_force" } > 0 end,
	  caption = _ "The Force",
	  text = _ "Your Force user carries Force Points (blue pips) and regains a few each turn. Right-click them and choose <b>The Force…</b>: <b>Push</b> and <b>Pull</b> move enemies (into walls for damage), <b>Speed</b> gives extra moves, <b>Sense</b> reveals hidden enemies, and <b>Mind Trick</b> stops a weak-minded enemy from acting." },
	{ id = "overwatch",
	  when = function() return #player_units{ ability = "sw_ability_overwatch" } > 0 and #enemies_of_player() > 0 end,
	  caption = _ "Overwatch",
	  text = _ "A soldier that could still attack but ends its turn without attacking goes on <b>overwatch</b>: until your next turn it fires on an enemy that moves into range in plain sight. Holding a line of riflemen back is often stronger than charging. Choose <b>Overwatch</b> from the right-click menu to take it before moving the rest of your force." },
	{ id = "flanking",
	  when = function()
		for _i, e in ipairs(enemies_of_player()) do
			if #wesnoth.units.find_on_map{ side = tips.PLAYER_SIDE, T.filter_adjacent{ id = e.id } } > 0 then
				return true
			end
		end
	  end,
	  caption = _ "Flanking",
	  text = _ "Surround before you strike. Every one of your units standing on the far side of an enemy -- away from the attacker -- adds to the attack. Pin an enemy from the front, then hit it from behind. The enemy flanks too: do not let a hero be surrounded." },
	{ id = "sensors",
	  when = function()
		for _i, rec in ipairs(wml.array_access.get("sw_ew_contacts")) do
			if rec.team == core.team_key(tips.PLAYER_SIDE) and rec.image then return true end
		end
	  end,
	  caption = _ "Sensor contacts",
	  text = _ "The amber hexes are sensor contacts: enemies your sensors detect but your eyes cannot see. A question mark is an unknown contact; a symbol shows what it is. Some are decoys. Units with active sensors can make an <b>Active sensor sweep</b> instead of attacking to see further and identify contacts." },
	{ id = "air",
	  when = function()
		local st = sw_systems and sw_systems.air and sw_systems.air.load(tips.PLAYER_SIDE)
		for _id, count in pairs(st and st.charges or {}) do if count > 0 then return true end end
	  end,
	  caption = _ "Air support",
	  text = _ "You have starfighter sorties overhead. Right-click a hex one of your forward observers can see and call a <b>strafing run</b> (strikes at once along a line) or a <b>bombing run</b> (lands next turn on the marked hexes -- clear your own troops out). Each call uses the observer's attack." },
	{ id = "stealth",
	  when = function()
		local cfg = wml.variables.sw_alert
		return type(cfg) == "table" and tonumber(cfg.intruder_side) == tips.PLAYER_SIDE and cfg.scenario == wesnoth.scenario.id
	  end,
	  caption = _ "Getting in unseen",
	  text = _ "The guards here are unaware. Their sight is shown around them; a guard that spots you shouts and alerts every guard near it. Move through shadow and cover, and right-click a unit next to an unaware guard for a <b>Silent takedown</b>. Fighting openly is possible, but the whole garrison will come." },
	{ id = "ysalamiri",
	  when = function()
		return #wml.array_access.get("sw_ysalamiri_zone") > 0 and #player_units{ ability = "sw_ability_force" } > 0
	  end,
	  caption = _ "Ysalamiri",
	  text = _ "The violet-tinted hexes are a ysalamiri field: the creatures push back the Force. A Force user inside has no powers, no blaster deflection and no Force regeneration. Fight around the field, or send troops in instead." },
	{ id = "doctrine",
	  when = function()
		for _i, d in ipairs(sw_systems and sw_systems.doctrine and sw_systems.doctrine.enabled_sides() or {}) do
			if wesnoth.sides.is_enemy(d.side, tips.PLAYER_SIDE) then return true end
		end
	  end,
	  caption = _ "Thrawn's doctrine",
	  text = _ "Grand Admiral Thrawn studies you. His forces gain Insight from how you fight -- the tactics you repeat, the weapons and targets you favour -- and as it grows they predict your moves and counter your sensors. Vary your approach and he learns slower." },
	{ id = "ranks",
	  when = function()
		local rank = sw_systems and sw_systems.rank
		if not rank then return false end
		for _i, u in ipairs(player_units()) do
			local entry = rank.DATA[u.type]
			if entry and rank.of(u) > (entry.base or 0) then return true end
		end
	  end,
	  caption = _ "Ranks",
	  text = _ "A unit past its highest level now earns ranks -- Veteran, Seasoned veteran, Elite -- shown as insignia, and at each rank you choose a specialization: better aim, tougher armor or more speed. Many units and heroes also change their look as Seasoned veterans and Elites. Keep your veterans alive: they carry over to the next mission." },
}

local function seen_set()
	local set = {}
	for _i, id in ipairs(core.split(wml.variables.sw_tips_seen or "")) do set[id] = true end
	return set
end

function tips.off()
	local v = wml.variables.sw_tips_off
	return v == true or v == "yes"
end

-- The tip to show now (or nil): the first unseen one whose trigger holds.
function tips.next_tip()
	if tips.off() then return nil end
	local seen = seen_set()
	for _i, tip in ipairs(tips.LIST) do
		if not seen[tip.id] then
			local ok, now = pcall(tip.when)
			if ok and now then return tip end
		end
	end
	return nil
end

function tips.mark_seen(id)
	local list = core.split(wml.variables.sw_tips_seen or "")
	table.insert(list, id)
	wml.variables.sw_tips_seen = table.concat(list, ",")
end

-- side turn: the player's turn begins.
function tips.on_side_turn()
	if wesnoth.current.side ~= tips.PLAYER_SIDE then return end
	local side = wesnoth.sides[tips.PLAYER_SIDE]
	if not side or side.controller ~= "human" then return end
	local tip = tips.next_tip()
	if not tip then return end
	tips.mark_seen(tip.id)
	wesnoth.wml_actions.message{
		speaker = "narrator",
		image = "misc/sw-objective.png",
		caption = tostring(_ "Field Manual") .. " — " .. tostring(tip.caption),
		message = tip.text,
		T.option{ label = _ "Got it" },
		T.option{ label = _ "Turn off tips", T.command{ T.set_variable{ name = "sw_tips_off", value = "yes" } } },
	}
end

return tips
