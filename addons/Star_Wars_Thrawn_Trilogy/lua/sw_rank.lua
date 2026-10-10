-- Star Wars: Thrawn Trilogy -- rank insignia.
--
-- A unit's rank is its type's starting rank (promoted types such as the New
-- Republic Sergeant, Stormtrooper Sergeant and Smuggler Veteran start at I)
-- plus one per after-max-level advancement (AMLA), shown up to III:
--   I Veteran, II Seasoned veteran, III Elite.
-- The insignia is drawn into the unit's own sprite (image_mod BLIT on every
-- frame), not as an overlay: overlays are hidden whenever a unit animation
-- turns its bars off (lesson #303). Styles per faction come from the
-- generated lua/sw_rank_data.lua: New Republic gold chevrons, Imperial red
-- over blue rank plaque, independent brass studs, dark Jedi violet marks.
-- Creatures and objects have no style and no insignia. Stats are not
-- changed: AMLAs keep the engine's default bonus (+3 HP, +20% XP, full heal).
-- Units with redrawn rank designs (DATA designs) also change to them at
-- rank II and III: same poses, gear earned in the field.
--
-- Each new rank adds one object (id sw_rank_insignia) whose plate covers the
-- previous one exactly; objects are only ever added, so no unit is rebuilt
-- mid-turn. State: unit variable sw_rank_shown.

local T = wml.tag
local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local _ = wesnoth.textdomain("wesnoth-Star_Wars_Thrawn_Trilogy")

local rank = {}

rank.DATA = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_rank_data.lua")
rank.MAX = 3
rank.X, rank.Y = 37, 61     -- plate position in the 72x72 sprite (bottom, right of centre)
rank.NAMES = { _ "Veteran", _ "Seasoned veteran", _ "Elite" }

-- Scenario or add-on extensions may register more types:
--   sw_systems.rank.DATA["my_type"] = { style = "republic", base = 0 }
function rank.style(u)
	local entry = rank.DATA[u.type]
	return entry and entry.style or nil
end

-- Number of after-max-level advancements the unit has taken.
function rank.amla_count(u)
	local mods = wml.get_child(u.__cfg, "modifications")
	if not mods then return 0 end
	return #wml.child_array(mods, "advancement")
end

function rank.of(u)
	local entry = rank.DATA[u.type]
	if not entry then return 0 end
	return math.min(rank.MAX, core.number(entry.base, 0) + rank.amla_count(u))
end

function rank.image(style, n)
	return "misc/sw-rank-" .. style .. "-" .. n .. ".png"
end

-- The rank design (variation rank2/rank3, gen_hte_units.py RANK_NAMES) the
-- unit should wear: the highest redrawn design at or below its rank, or ""
-- for the base art. nil when the unit is in a variation the rank system does
-- not own (e.g. "unarmed", SW_UNARMED): that look wins until SW_ARMED.
function rank.design_for(u)
	local entry = rank.DATA[u.type]
	local current = u.variation or ""
	if current ~= "" and not current:match("^rank%d$") then return nil end
	local want = ""
	for _i, n in ipairs(entry and entry.designs or {}) do
		if rank.of(u) >= n then want = "rank" .. n end
	end
	return want
end

-- Switch the unit to its rank design. Returns true if it changed.
function rank.apply_design(u)
	local want = rank.design_for(u)
	if want == nil or want == (u.variation or "") then return false end
	wesnoth.wml_actions.modify_unit{ T.filter{ id = u.id }, variation = want }
	core.log("rank", u.id .. " wears design " .. (want == "" and "base" or want))
	return true
end

-- Make the insignia and design match the unit's rank. Returns true if the
-- insignia changed. The unit proxy u stays valid (modify_unit keeps the unit).
function rank.update(u)
	local style = rank.style(u)
	if not style then return false end
	rank.apply_design(u)
	local n = rank.of(u)
	local shown = core.number(u.variables.sw_rank_shown, 0)
	if n <= shown then return false end
	u:add_modification("object", { id = "sw_rank_insignia", T.effect{ apply_to = "image_mod",
		add = "BLIT(" .. rank.image(style, n) .. "," .. rank.X .. "," .. rank.Y .. ")" } })
	u.variables.sw_rank_shown = n
	core.log("rank", u.id .. " shows rank " .. n .. " (" .. style .. ")")
	return true
end

function rank.status_line(u)
	local n = rank.of(u)
	if n <= 0 or not rank.style(u) then return nil end
	return tostring(_ "Rank:") .. " " .. tostring(rank.NAMES[n]) .. " (" .. n .. "/" .. rank.MAX .. ")"
end

-- post advance: promotion or AMLA. The engine already plays the advancement
-- effect; the insignia is updated and the new rank named over the unit.
function rank.on_post_advance()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	if u and rank.update(u) then
		local viewer = core.viewing_side()
		if viewer == nil or viewer < 1 then viewer = u.side end
		if u:matches{ T.filter_vision{ side = viewer, visible = true } } then
			core.float(u.x, u.y, tostring(rank.NAMES[rank.of(u)]), "#ffd75a")
		end
	end
end

return rank
