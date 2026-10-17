-- Kill experience scaled by how hard the victim was to kill.
--
-- Owner direction (2026-10-16): destroying a capital ship must be worth far
-- more experience than shooting down a stormtrooper. The engine already gives
-- kill_experience (8) x the victim's level (half of 8 for level 0). On top of
-- that, the killer earns 1 XP for every 4 HP the victim had beyond a typical
-- unit of its level (22 + 14 x level: 36 at level 1, 78 at level 4), so tough
-- targets pay in proportion to the hits it took to bring them down:
--   stormtrooper (L1, 36 HP) 8 XP, AT-ST (L2, 64 HP) 16+4, Imperial minelayer
--   (L2, 90 HP) 16+10, Katana Dreadnaught (L3, 160 HP) 24+24, Imperial Star
--   Destroyer (L4, 220 HP) 32+36. Halves round up.
-- Unarmed set pieces (shield generators, cloning cylinders, docked or
-- derelict hulks) give no bonus: they do not fight back.
--
-- Applied in the "die" event (sw_systems.lua), before the engine checks the
-- killer for advancement at the end of the fight.

local xp = {}
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

xp.HP_BASE = 22
xp.HP_PER_LEVEL = 14
xp.HP_PER_XP = 4

-- Bonus experience for killing this unit (0 for ordinary units).
function xp.kill_bonus(victim)
	if not victim or #victim.attacks == 0 then return 0 end
	local typical = xp.HP_BASE + xp.HP_PER_LEVEL * math.max(0, victim.level)
	return math.max(0, math.floor((victim.max_hitpoints - typical) / xp.HP_PER_XP + 0.5))
end

-- die event: victim at x1,y1, killer (if any) at x2,y2.
function xp.on_die()
	local ctx = wesnoth.current.event_context
	if not ctx.x2 or not ctx.y2 then return end
	local victim = wesnoth.units.get(ctx.x1, ctx.y1)
	local killer = wesnoth.units.get(ctx.x2, ctx.y2)
	if not victim or not killer or killer.hitpoints <= 0 or killer.side == victim.side then return end
	local bonus = xp.kill_bonus(victim)
	if bonus <= 0 then return end
	killer.experience = killer.experience + bonus
	wesnoth.interface.float_label(killer.x, killer.y,
		"<span color='#a0e0ff'>+" .. bonus .. " " .. tostring(_ "XP (tough kill)") .. "</span>")
end

return xp
