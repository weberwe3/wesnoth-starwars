-- Star Wars: Thrawn Trilogy -- engine sounds for moves that start out of view.
--
-- Vehicles and starships play their engine sound once per move, from the
-- take-off animation ([pre_movement_anim], gen_hte_units.py MOVE_SOUNDS):
-- the movement animation loops for every hex, so a sound there would repeat.
-- But the engine only plays an animation's sound when it draws the unit
-- (src/units/frame.cpp, drawer.cpp), and it does not draw a unit the viewer
-- cannot see. An enemy speeder that starts its move in fog, or as an
-- unidentified sensor contact, therefore drove into view silently
-- (owner report 2026-10-12).
--
-- This watches each step of a move (enter_hex). If the unit was out of sight
-- where the move began, its engine sound -- the same one its take-off
-- animation uses -- plays once, at the first hex where the viewer can see it.
-- A move that starts in view is left to the take-off animation, so the sound
-- never plays twice. Display only: the state is a transient Lua table, never
-- saved and never used for game decisions.

local core = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_core.lua")
local T = wml.tag

local ms = {}
local sounds = {}     -- unit type -> take-off sound, or false
local moving = {}     -- unit id -> { done = bool } for the move in progress

-- The take-off sound of a unit type (first [frame] sound of its
-- [pre_movement_anim]), or nil.
function ms.sound_of(type_id)
	if sounds[type_id] == nil then
		sounds[type_id] = false
		local ut = wesnoth.unit_types[type_id]
		local anim = ut and wml.get_child(ut.__cfg, "pre_movement_anim")
		for _i, f in ipairs(anim and wml.child_array(anim, "frame") or {}) do
			if f.sound then
				sounds[type_id] = tostring(f.sound)
				break
			end
		end
	end
	return sounds[type_id] or nil
end

function ms.play(sound) wesnoth.audio.play(sound) end

-- One step of a move. seen_from: the viewer could see the unit where the move
-- began; seen_now: the viewer sees it on the hex it just entered. Returns true
-- if the sound played.
function ms.step(u, seen_from, seen_now)
	local sound = ms.sound_of(u.type)
	if not sound then return false end
	local st = moving[u.id]
	if not st then
		st = { done = seen_from }      -- seen at the start: the take-off played it
		moving[u.id] = st
	end
	if not st.done and seen_now then
		st.done = true
		ms.play(sound)
		return true
	end
	return false
end

function ms.finish(u)
	if u then moving[u.id] = nil end
end

local function viewer()
	local v = core.viewing_side()
	if v and v >= 1 and v <= #wesnoth.sides then return v end
	return nil
end

function ms.on_enter_hex()
	local ctx = wesnoth.current.event_context
	local u = wesnoth.units.get(ctx.x1, ctx.y1)
	local v = viewer()
	if not u or not v or not ms.sound_of(u.type) then return end
	-- Where the move began (the hex before the first step).
	local st = moving[u.id]
	local seen_from = true
	if not st then
		local ew = sw_systems and sw_systems.ew
		local concealed = ew and u.status[ew.CONCEALED] == true
		seen_from = u.side == v or not (wesnoth.sides.is_fogged(v, { ctx.x2, ctx.y2 }) or concealed)
	end
	ms.step(u, seen_from, u:matches{ T.filter_vision{ side = v, visible = true } })
end

function ms.on_moveto()
	local ctx = wesnoth.current.event_context
	ms.finish(wesnoth.units.get(ctx.x1, ctx.y1))
end

return ms
