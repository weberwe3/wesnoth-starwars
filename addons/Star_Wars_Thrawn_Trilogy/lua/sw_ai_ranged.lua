-- Star Wars: Thrawn Trilogy -- AI candidate action: ranged fire and withdrawal.
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

local function can_act(u, side)
	return u and u.side == side and u.hitpoints > 0 and u.max_attacks > 0
		and u.attacks_left > 0 and not u.status.petrified
end

-- Planning has the same information a player on this side could see. In
-- particular, a hidden occupant must not silently veto a reachable hex.
local function known_units(side)
	local list = wesnoth.units.find_on_map{ T.filter_vision{ side = side, visible = true } }
	table.sort(list, function(a, b) return a.id < b.id end)
	local occupied = {}
	for _i, u in ipairs(list) do occupied[u.x .. "," .. u.y] = u end
	return list, occupied
end

local function unaware(u)
	return sw_systems and sw_systems.alert and sw_systems.alert.is_unaware(u)
end

-- Weapon:matches has no opponent/combat-context argument (LuaAPI/types#Weapon).
-- Do not query active specials through its context-free fallback. Conditional
-- weapon filters requiring that context remain uncertain, rather than being
-- mistaken for an inactive disable. Plain weapon filters use the native matcher.
local function contextual_weapon_filter(cfg)
	if cfg.special_active or cfg.special_id_active or cfg.special_type_active or cfg.formula then return true end
	for _i, child in ipairs(cfg) do
		if child[1] == "experimental_filter_specials" and child[2].active then return true end
		if contextual_weapon_filter(child[2]) then return true end
	end
	return false
end

local function special_unit_matches(u, other, filter, weapon)
	if not filter then return true end
	if not u:matches(filter, other) then return false end
	local wf = wml.get_child(filter, "filter_weapon")
	if wf and weapon and not contextual_weapon_filter(wf) then return weapon:matches(wf) end
	-- The defender's eventual retaliation weapon is not known to this model.
	-- If its unit filter matches, a weapon-filtered disable may be active.
	return true
end

-- AbilitiesWML: active_on defaults to both, apply_to to self; filters must
-- match before [disable] takes effect. Mirror installed 1.19.27
-- specials_context_t::is_special_active using native SUFs, not special IDs.
-- Its deprecated adjacent filters are normalized into filter_self by core.
-- Look-ahead uses a private clone, never a temporary change to the map. The
-- authoritative check repeats with the actual units after ai.move/events.
local function disabled_on_offense(u, a, target, x, y)
	local self = u
	for _i, sp in ipairs(a.specials or {}) do
		local tag, cfg = sp[1], sp[2] or {}
		if tag == "disable" and cfg.active_on ~= "defense"
			and cfg.apply_to ~= "opponent" and cfg.apply_to ~= "defender" then
			if self == u and (u.x ~= x or u.y ~= y) then
				self = u:clone()
				self.loc = { x, y }
			end
			if special_unit_matches(self, target, wml.get_child(cfg, "filter_self"), a)
				and special_unit_matches(self, target, wml.get_child(cfg, "filter_attacker"), a)
				and special_unit_matches(target, self, wml.get_child(cfg, "filter_opponent"))
				and special_unit_matches(target, self, wml.get_child(cfg, "filter_defender")) then
				return true
			end
		end
	end
	return false
end

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
		if a.range == "ranged" and (a.max_range or 1) >= 2 and (a.attacks_used or 1) <= u.attacks_left then
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
local function flank_bonus(target, x, y, mover, occupied)
	if not occupied then local _known; _known, occupied = known_units(mover.side) end
	local d = wesnoth.map.distance_between(x, y, target.x, target.y)
	local n = 0
	for _i, loc in ipairs(wesnoth.map.find{ T.filter_adjacent_location{ x = target.x, y = target.y } }) do
		local lx, ly = loc[1] or loc.x, loc[2] or loc.y
		local f = occupied[lx .. "," .. ly]
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

-- These are preferences between otherwise worthwhile, legal attacks, never
-- damage or accuracy bonuses. Nearby armed allies protect a target; invisible
-- support cannot influence this rating. Each term is capped at four points.
local function target_priority(target, known)
	local support = 0
	for _i, friend in ipairs(known) do
		if friend.id ~= target.id and friend.hitpoints > 0 and not friend.status.petrified
			and #friend.attacks > 0 and not wesnoth.sides.is_enemy(friend.side, target.side)
			and wesnoth.map.distance_between(friend.x, friend.y, target.x, target.y) <= 2 then
			support = support + 1
		end
	end
	local wounded = 4 * math.max(0, 1 - target.hitpoints / math.max(1, target.max_hitpoints))
	return wounded + math.max(0, 4 - support * 2)
end

local function can_withdraw(u, side)
	return u and u.side == side and u.hitpoints > 0 and u.moves > 0
		and not u.canrecruit and not u.status.petrified and not unaware(u)
		and u.hitpoints <= u.max_hitpoints * 0.4
end

-- Core's ca_retreat_injured primarily sends non-regenerating troops to healing
-- locations. This covers wounded troops exposed on maps without reachable
-- healing: move beyond visible weapons and toward cover/support, then stand
-- down for this turn. Native reach retains terrain costs and zones of control.
local function best_withdrawal(side, tried, avoid)
	local wounded = {}
	for _i, u in ipairs(sorted_units{ side = side }) do
		if can_withdraw(u, side) and not tried[u.id] then wounded[#wounded + 1] = u end
	end
	if #wounded == 0 then return nil end
	local known, occupied = known_units(side)
	local enemies, blocked = {}, {}
	for _i, u in ipairs(known) do
		if wesnoth.sides.is_enemy(u.side, side) and u.hitpoints > 0
			and not u.status.petrified and #u.attacks > 0 then
			local range = 1
			for _j, weapon in ipairs(u.attacks) do range = math.max(range, weapon.max_range or 1) end
			enemies[#enemies + 1] = { unit = u, range = range }
		end
	end
	if #enemies == 0 then return nil end
	for _i, loc in ipairs(avoid or {}) do
		blocked[(loc[1] or loc.x) .. "," .. (loc[2] or loc.y)] = true
	end
	local function distances(x, y)
		local nearest, exposed = math.huge, false
		for _i, threat in ipairs(enemies) do
			local d = wesnoth.map.distance_between(x, y, threat.unit.x, threat.unit.y)
			nearest = math.min(nearest, d)
			if d <= threat.range then exposed = true end
		end
		return nearest, exposed
	end
	local best
	for _i, u in ipairs(wounded) do
		if can_withdraw(u, side) and not tried[u.id] then
			local nearest = distances(u.x, u.y)
			local near_threat = false
			for _j, threat in ipairs(enemies) do
				if wesnoth.map.distance_between(u.x, u.y, threat.unit.x, threat.unit.y) <= threat.range + 1 then
					near_threat = true
				end
			end
			if near_threat then
				local reach = wesnoth.paths.find_reach(u, { viewing_side = side })
				table.sort(reach, function(a, b)
					local ax, ay, bx, by = a[1] or a.x, a[2] or a.y, b[1] or b.x, b[2] or b.y
					return ax < bx or (ax == bx and ay < by)
				end)
				for _j, loc in ipairs(reach) do
					local x, y = loc[1] or loc.x, loc[2] or loc.y
					local distance, exposed = distances(x, y)
					local key = x .. "," .. y
					if not occupied[key] and not blocked[key] and not exposed and distance >= nearest + 2 then
						local support = 0
						for _k, friend in ipairs(known) do
							if friend.id ~= u.id and not wesnoth.sides.is_enemy(friend.side, side)
								and friend.hitpoints > 0 and not friend.status.petrified and #friend.attacks > 0
								and wesnoth.map.distance_between(x, y, friend.x, friend.y) <= 2 then
									support = support + 1
								end
						end
						local terrain = wesnoth.current.map[{x, y}]
						local healing = wesnoth.terrain_types[terrain].healing or 0
						local rating = math.min(6, distance) * 3 + u:defense_on(terrain) / 20
							+ math.min(2, support) * 2 + ((healing == true or healing > 0) and 4 or 0)
							- wesnoth.map.distance_between(u.x, u.y, x, y) * 0.25
						if not best or rating > best.rating then
							best = { kind = "withdraw", rating = rating, unit = u.id, side = side,
								x = x, y = y, turn = wesnoth.current.turn }
						end
					end
				end
			end
		end
	end
	return best
end

-- Best stand-off attack for the side, or nil. tried: unit ids to skip.
local function best_attack(side, tried)
	local known, occupied = known_units(side)
	local enemies = sorted_units{ T.filter_side{ T.enemy_of{ side = side } },
		T.filter_vision{ side = side, visible = true } }
	if #enemies == 0 then return nil end
	local priorities = {}
	for _i, e in ipairs(enemies) do priorities[e.id] = target_priority(e, known) end
	local best = nil
	for _i, u in ipairs(sorted_units{ side = side }) do
		local weapons = (can_act(u, side) and not tried[u.id]) and ranged_weapons(u) or {}
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
				if e.hitpoints > 0 and not e.status.petrified
					and wesnoth.map.distance_between(u.x, u.y, e.x, e.y) <= u.moves + maxr then
					local e_loc = { x = e.x, y = e.y }
					for _l, loc in ipairs(reach) do
						local x, y = loc[1] or loc.x, loc[2] or loc.y
						local occupant = occupied[x .. "," .. y]
						if not occupant or occupant.id == u.id then
							local d = wesnoth.map.distance_between(x, y, e.x, e.y)
							for _m, w in ipairs(weapons) do
								if d >= w.min and d <= w.max and not disabled_on_offense(u, w.attack, e, x, y) then
									local dealt = math.min(e.hitpoints,
										expected(w.attack, w.falloff, w.bonus, d, e, e_loc, flank_bonus(e, x, y, u, occupied)))
									local taken = math.min(u.hitpoints, return_fire(e, u, { x = x, y = y }, d))
									local kill = dealt >= e.hitpoints * 0.9 and e.max_hitpoints * 0.3 or 0
									local rating = dealt + kill - taken * 0.8
									if rating >= MIN_RATING then rating = rating + priorities[e.id] end
									if rating >= MIN_RATING and (best == nil or rating > best.rating) then
										best = { rating = rating, unit = u.id, side = side, x = x, y = y,
											target = e.id, weapon = w.index, weapon_name = w.attack.name }
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
	local best = best_withdrawal(wesnoth.current.side, data.sw_ranged_tried, ai.aspects.avoid)
		or best_attack(wesnoth.current.side, data.sw_ranged_tried)
	if not best then return 0 end
	data.sw_ranged_fire = best
	return cfg.max_score or 100010
end

function ca:execution(cfg, data)
	local best = data.sw_ranged_fire
	data.sw_ranged_fire = nil
	if not best then return end
	data.sw_ranged_tried[best.unit] = true
	if best.kind == "withdraw" then
		local u = wesnoth.units.get(best.unit)
		if best.side ~= wesnoth.current.side or best.turn ~= wesnoth.current.turn
			or not can_withdraw(u, best.side) then return end
		local x, y = u.x, u.y
		ai.move_full(u, best.x, best.y)
		u = wesnoth.units.get(best.unit)
		-- An ambush may interrupt the move. Stop the surviving withdrawing unit
		-- at its actual hex so default combat cannot send it straight back.
		if u and u.side == best.side and u.hitpoints > 0 and (u.x ~= x or u.y ~= y) then
			-- A native stopunit is AI-local and is omitted from replay. End-turn
			-- air/overwatch must see the same spent actions in play and playback.
			wesnoth.sync.invoke_command("sw_ai_withdraw_stand_down", {
				unit = u.id, side = u.side, x = u.x, y = u.y, turn = wesnoth.current.turn })
			if sw_systems and sw_systems.core then
				sw_systems.core.log("ai", u.id .. " withdraws to " .. u.x .. "," .. u.y)
			end
		end
		return
	end
	local u = wesnoth.units.get(best.unit)
	local target = wesnoth.units.get(best.target)
	if best.side ~= wesnoth.current.side or not can_act(u, best.side) or not target then return end
	if u.x ~= best.x or u.y ~= best.y then
		ai.move(u, best.x, best.y)
		u = wesnoth.units.get(best.unit)
		target = wesnoth.units.get(best.target)
	end
	-- Movement can trigger ambushes or WML that changes either combatant and
	-- its weapons. Reacquired IDs alone do not authorize the cached command.
	if not can_act(u, best.side) or not target or target.hitpoints <= 0 or target.status.petrified
		or u.x ~= best.x or u.y ~= best.y or not wesnoth.sides.is_enemy(u.side, target.side)
		or not target:matches{ T.filter_vision{ side = u.side, visible = true } } then return end
	local a = u.attacks[best.weapon]
	if not a or a.name ~= best.weapon_name or a.range ~= "ranged"
		or (a.attacks_used or 1) > u.attacks_left then return end
	local d = wesnoth.map.distance_between(u.x, u.y, target.x, target.y)
	if d < math.max(2, a.min_range or 1) or d > (a.max_range or 1)
		or disabled_on_offense(u, a, target, u.x, u.y) then return end
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
ca.best_withdrawal = best_withdrawal
ca.target_priority = target_priority

return ca
