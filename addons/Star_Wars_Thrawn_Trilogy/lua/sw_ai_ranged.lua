-- Star Wars: Thrawn Trilogy -- AI candidate action: stand-off ranged fire.
--
-- The engine's default AI only attacks from adjacent hexes, so it would
-- never use weapon ranges (rifles reach 2 hexes, heavy weapons 3). This
-- candidate action finds, for each of the side's units with an attack left,
-- the best attack it can make from a reachable hex 2+ hexes from a visible
-- enemy, rating expected damage dealt (and a likely kill) against the return
-- fire it would take there -- none if the target's weapons cannot reach that
-- far. It runs before the default combat CA only when the best such attack
-- is worth it; otherwise the default AI acts. Deterministic: units, targets
-- and hexes are visited in a fixed order.
--
-- The rating is a simple expected-damage model rather than the engine's
-- combat preview: the preview evaluates range specials from the unit's real
-- position, not the candidate hex being considered.
-- Registered for every side at prestart by lua/sw_systems.lua.

local T = wml.tag

local ca = {}

local MIN_RATING = 4

-- Accuracy terms of a weapon from its specials: range falloff per hex beyond
-- the first (0 for guided weapons) and the aimed-shot bonus.
local function accuracy_terms(a)
	local falloff, bonus, aimed = 0, 0, false
	for _i, sp in ipairs(a.specials or {}) do
		local tag, cfg = sp[1], sp[2]
		if tag == "chance_to_hit" and cfg then
			if cfg.id == "sw_special_range" and cfg.sub then falloff = 10 end
			if cfg.id == "sw_special_aimed" then bonus = tonumber(cfg.add) or 0 aimed = true end
		end
	end
	return falloff, bonus, aimed
end

local function ranged_weapons(u)
	local out = {}
	for i, a in ipairs(u.attacks) do
		if a.range == "ranged" and (a.max_range or 1) >= 2 then
			local falloff, bonus = accuracy_terms(a)
			table.insert(out, { index = i, min = math.max(2, a.min_range or 1), max = a.max_range, attack = a,
				falloff = falloff, bonus = bonus })
		end
	end
	return out
end

-- Flanking bonus for an attack on target from hex (x, y), mirroring the
-- sw_special_flanking weapon special (units/00_sw_specials.cfg): +10% for each
-- armed, non-petrified unit hostile to the target adjacent to it and farther
-- from the attacking hex than the target is, at most +20%. mover is the
-- attacking unit, which leaves its current hex to fire, so it never counts.
local function flank_bonus(target, x, y, mover)
	local d = wesnoth.map.distance_between(x, y, target.x, target.y)
	local n = 0
	for _i, loc in ipairs(wesnoth.map.find{ T.filter_adjacent_location{ x = target.x, y = target.y } }) do
		local lx, ly = loc[1] or loc.x, loc[2] or loc.y
		local f = wesnoth.units.get(lx, ly)
		if f and f.id ~= mover.id and wesnoth.map.distance_between(lx, ly, x, y) > d
			and wesnoth.sides.is_enemy(f.side, target.side) and not f.status.petrified and #f.attacks > 0 then
			n = n + 1
		end
	end
	return math.min(2, n) * 10
end

-- Expected damage of one weapon from distance d against a target standing on
-- target_loc, honouring its defence and resistance, falloff, aim and any
-- flanking bonus (flank; none for return fire, as flanking is offense only).
local function expected(a, falloff, bonus, d, target, target_loc, flank)
	local cth = 100 - target:defense_on(target_loc) + bonus + (flank or 0) - falloff * (d - 1)
	cth = math.max(0, math.min(100, cth))
	local dmg = a.damage * (100 - target:resistance_against(a.type)) / 100
	return a.number * dmg * cth / 100
end

-- The defender's best return fire at distance d (0 if nothing reaches).
-- Aimed shots are attack-only and never return fire.
local function return_fire(defender, attacker, attacker_loc, d)
	local best = 0
	for _i, a in ipairs(defender.attacks) do
		local falloff, bonus, aimed = accuracy_terms(a)
		if a.range == "ranged" and not aimed and d >= (a.min_range or 1) and d <= (a.max_range or 1) then
			best = math.max(best, expected(a, falloff, bonus, d, attacker, attacker_loc))
		end
	end
	return best
end

local function sorted_units(filter)
	local list = wesnoth.units.find_on_map(filter)
	table.sort(list, function(a, b) return a.id < b.id end)
	return list
end

-- Best stand-off attack for the side, or nil. tried: unit ids to skip.
local function best_attack(side, tried)
	local enemies = sorted_units{ T.filter_side{ T.enemy_of{ side = side } },
		T.filter_vision{ side = side, visible = true } }
	if #enemies == 0 then return nil end
	local best = nil
	for _i, u in ipairs(sorted_units{ side = side }) do
		local weapons = (u.attacks_left > 0 and u.hitpoints > 0 and not tried[u.id]) and ranged_weapons(u) or {}
		if #weapons > 0 then
			local maxr = 0
			for _j, w in ipairs(weapons) do maxr = math.max(maxr, w.max) end
			local reach = wesnoth.paths.find_reach(u)
			table.sort(reach, function(a, b)
				local ax, ay = a[1] or a.x, a[2] or a.y
				local bx, by = b[1] or b.x, b[2] or b.y
				if ax ~= bx then return ax < bx end
				return ay < by
			end)
			for _k, e in ipairs(enemies) do
				if wesnoth.map.distance_between(u.x, u.y, e.x, e.y) <= u.moves + maxr then
					local e_loc = { x = e.x, y = e.y }
					for _l, loc in ipairs(reach) do
						local x, y = loc[1] or loc.x, loc[2] or loc.y
						local occupant = wesnoth.units.get(x, y)
						if not occupant or occupant.id == u.id then
							local d = wesnoth.map.distance_between(x, y, e.x, e.y)
							for _m, w in ipairs(weapons) do
								if d >= w.min and d <= w.max then
									local dealt = math.min(e.hitpoints,
										expected(w.attack, w.falloff, w.bonus, d, e, e_loc, flank_bonus(e, x, y, u)))
									local taken = math.min(u.hitpoints, return_fire(e, u, { x = x, y = y }, d))
									local kill = dealt >= e.hitpoints * 0.9 and e.max_hitpoints * 0.3 or 0
									local rating = dealt + kill - taken * 0.8
									if rating >= MIN_RATING and (best == nil or rating > best.rating) then
										best = { rating = rating, unit = u.id, x = x, y = y, target = e.id, weapon = w.index }
									end
								end
							end
						end
					end
				end
			end
		end
	end
	return best
end

function ca:evaluation(cfg, data)
	-- Each unit is tried at most once per turn, so a failed attempt (an
	-- ambush on the way, say) never loops.
	if data.sw_ranged_turn ~= wesnoth.current.turn or data.sw_ranged_side ~= wesnoth.current.side then
		data.sw_ranged_turn, data.sw_ranged_side, data.sw_ranged_tried = wesnoth.current.turn, wesnoth.current.side, {}
	end
	local best = best_attack(wesnoth.current.side, data.sw_ranged_tried)
	if not best then return 0 end
	data.sw_ranged_fire = best
	return cfg.max_score or 100010
end

function ca:execution(cfg, data)
	local best = data.sw_ranged_fire
	data.sw_ranged_fire = nil
	if not best then return end
	data.sw_ranged_tried[best.unit] = true
	local u = wesnoth.units.get(best.unit)
	local target = wesnoth.units.get(best.target)
	if not u or not target then return end
	if u.x ~= best.x or u.y ~= best.y then
		ai.move(u, best.x, best.y)
		u = wesnoth.units.get(best.unit)
		target = wesnoth.units.get(best.target)
		if not u or not target or u.x ~= best.x or u.y ~= best.y then return end
	end
	if sw_systems and sw_systems.core then
		sw_systems.core.log("ai", u.id .. " fires from " .. best.x .. "," .. best.y .. " at " .. target.id ..
			string.format(" (rating %.1f)", best.rating))
	end
	-- ai.attack only accepts adjacent targets, so issue the same synced attack
	-- command a player's click does (it honours the weapon's range).
	wesnoth.wml_actions.do_command{ T.attack{ weapon = best.weapon - 1,
		T.source{ x = u.x, y = u.y }, T.destination{ x = target.x, y = target.y } } }
end

-- Exposed for the engine tests.
ca.best_attack = best_attack
ca.flank_bonus = flank_bonus

return ca
