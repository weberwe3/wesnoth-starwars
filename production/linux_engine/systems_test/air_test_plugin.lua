-- Deterministic engine tests for off-map air support and rank insignia.
-- run_systems_tests.py --suite air points the campaign at sw_test_air and
-- runs this plugin. PHASE is substituted: "main" runs every test and saves;
-- "load" runs after reloading that save and checks that state survived.
-- Air strikes animate (flyover, explosions, damage), which ends a plugin
-- execute call, so each strike is resolved at the end of a step and checked
-- in the next one.
local CAMPAIGN = "Star_Wars_Thrawn_Trilogy"
local PHASE = "main"

local STEPS = {
  "rank_promotion", "rank_amla", "air_basics", "air_accuracy", "air_strafe", "check_strafe",
  "air_bombing", "land_bombing", "check_bombing", "scripted", "check_scripted", "carryover",
  "ai_avoid", "check_ai_avoid", "ai_air", "check_ai_air", "weapon_ranges", "ai_ranged", "check_ai_ranged",
  "alert_rules", "alert_takedown", "alert_ai", "check_alert_ai", "prepare_save",
}
local END_TURN_AFTER = { ai_avoid = true, ai_air = true, ai_ranged = true, alert_ai = true }

local function plugin(events, context, info)
  local function pump()
    events, context, info = wesnoth.plugin.next_slice()
    if info.name == "Dialog" then context.skip_dialog{} end
    if info.name == "Campaign Configure" then context.launch{} end
  end
  local function settle()
    for _ = 1, 30 do pump() end
    local g = 0
    repeat pump(); g = g + 1 until (info.name == "Game" and info.can_move().can_move) or g > 200000
  end
  if PHASE == "main" then
    events, context, info = wesnoth.plugin.wait_until("titlescreen")
    while info.name == "titlescreen" do context.play_campaign({}); events, context, info = coroutine.yield() end
    events, context, info = wesnoth.plugin.wait_until("Campaign Selection")
    local s = info.find_level{ id = CAMPAIGN }
    context.select_level({ index = s.index }); events, context, info = wesnoth.plugin.next_slice(); context.create{}
  end
  settle()
  if info.name ~= "Game" then std_print("SW_TEST: FAIL setup no game context"); context.exit{ code = 3 }; return end

  wesnoth.plugin.execute(context, function()
    wesnoth.interface.skip_messages(true)
    local T = wml.tag
    local air, rank, doctrine, ew, core = sw_systems.air, sw_systems.rank, sw_systems.doctrine, sw_systems.ew, sw_systems.core
    swt = { mem = {} }
    function swt.check(name, cond, detail)
      std_print("SW_TEST: " .. (cond and "PASS " or "FAIL ") .. name ..
        ((not cond and detail ~= nil) and (" -- " .. tostring(detail)) or ""))
    end
    function swt.u(id) return wesnoth.units.get(id) end
    -- Menus are probed the way the engine evaluates [show_if]: outside any
    -- event, with the hex in the WML variables x1, y1.
    function swt.probe_at(x, y)
      wml.variables.x1, wml.variables.y1 = x, y
      local ok, res = pcall(air.menu_visible)
      wml.variables.x1, wml.variables.y1 = nil, nil
      if not ok then std_print("SW_TEST: FAIL air menu show_if error -- " .. tostring(res)) return {} end
      return { air = res }
    end
    function swt.clear()
      for _i, u in ipairs(wesnoth.units.find_on_map{}) do u:erase() end
      for _i, side in ipairs{ 1, 2, 3 } do wml.variables["sw_air_s" .. side] = nil end
      wml.array_access.set("sw_air_inbound", {})
      for _i, loc in ipairs(wml.array_access.get("sw_alert_drawn")) do wesnoth.interface.remove_item(loc.x, loc.y, "sw_alert_sight") end
      wml.array_access.set("sw_alert_drawn", {})
      wml.variables.sw_alert = nil
      for _i, side in ipairs{ 1, 2, 3 } do wml.variables["sw_doctrine_s" .. side] = nil end
      wml.variables.sw_doctrine_sides = nil
    end
    function swt.place(type, side, x, y, id)
      wesnoth.wml_actions.unit{ type = type, side = side, x = x, y = y, id = id, random_traits = false, generate_name = false }
      return wesnoth.units.get(id)
    end
    function swt.move(px, py) wesnoth.wml_actions.do_command{ T.move{ x = px, y = py } } end
    function swt.move_to(id, x, y)
      local unit = wesnoth.units.get(id)
      local path = wesnoth.paths.find_path(unit, x, y)
      local xs, ys = {}, {}
      for _i, loc in ipairs(path) do table.insert(xs, loc[1] or loc.x); table.insert(ys, loc[2] or loc.y) end
      swt.move(table.concat(xs, ","), table.concat(ys, ","))
    end
    function swt.level_up(id)
      local u = wesnoth.units.get(id)
      u.experience = u.max_experience
      u:advance(false, true)
      return wesnoth.units.get(id)
    end
    function swt.objects(u, id)
      local n = 0
      local mods = wml.get_child(u.__cfg, "modifications")
      for _i, o in ipairs(mods and wml.child_array(mods, "object") or {}) do if o.id == id then n = n + 1 end end
      return n
    end
    -- Results of every strike, recorded by the on_strike hook.
    air.hooks.on_strike = { function(strike, results)
      swt.mem.strikes = swt.mem.strikes or {}
      table.insert(swt.mem.strikes, { strike = strike, results = results })
    end }
    -- Damage after the unit's resistance (harm_unit applies it), allowing
    -- for the engine's rounding.
    function swt.damage_ok(id, before, per_hit, hits, dtype)
      local unit = wesnoth.units.get(id)
      if not unit then return false end
      local loss = before - unit.hitpoints
      local raw = per_hit * hits * (100 - unit:resistance_against(dtype)) / 100
      if unit.hitpoints == 1 and raw >= before - 1 then return true end   -- never lethal
      return math.abs(loss - raw) <= 1
    end
    local check, u = swt.check, swt.u
    local S = {}
    swt.steps = S

    -- Promotion to a new type: the promoted type starts at rank I.
    function S.rank_promotion()
      swt.clear()
      local t = swt.place("sw_unit_nr_trooper", 1, 3, 3, "t_tr")
      check("a fresh trooper wears no insignia", not tostring(t.image_mods):find("sw%-rank") and rank.of(t) == 0)
      local sgt = swt.level_up("t_tr")
      check("trooper promoted to sergeant", sgt.type == "sw_unit_nr_sergeant")
      check("promotion adds the New Republic rank I chevron to the sprite",
        tostring(sgt.image_mods):find("sw%-rank%-republic%-1%.png,37,61") ~= nil, sgt.image_mods)
      local placed = swt.place("sw_unit_nr_sergeant", 1, 5, 3, "t_sgt2")
      check("a sergeant placed directly also wears rank I", tostring(placed.image_mods):find("sw%-rank%-republic%-1") ~= nil)
      swt.place("sw_unit_im_stormtrooper", 2, 7, 3, "t_st")
      local ss = swt.level_up("t_st")
      check("stormtrooper promoted: Imperial rank plaque", ss.type == "sw_unit_im_stormtrooper_sergeant" and
        tostring(ss.image_mods):find("sw%-rank%-imperial%-1") ~= nil, ss.image_mods)
      swt.place("sw_unit_im_clone_trooper", 2, 9, 3, "t_cl")
      check("clone trooper promoted: Imperial rank plaque", tostring(swt.level_up("t_cl").image_mods):find("sw%-rank%-imperial%-1") ~= nil)
      swt.place("sw_unit_sm_smuggler", 1, 11, 3, "t_sm")
      check("smuggler promoted to veteran: brass studs", tostring(swt.level_up("t_sm").image_mods):find("sw%-rank%-independent%-1") ~= nil)
      swt.place("sw_unit_nr_militia", 1, 13, 3, "t_mil")
      local mil = swt.level_up("t_mil")
      check("militia promoted to trooper: no rank yet", mil.type == "sw_unit_nr_trooper" and not tostring(mil.image_mods):find("sw%-rank"))
    end

    -- After-max-level advancements: ranks I-III, stats as the default AMLA.
    function S.rank_amla()
      swt.clear()
      local c = swt.place("sw_unit_nr_commando", 1, 3, 5, "t_cmd")
      local hp0 = c.max_hitpoints
      local shown = {}
      for i = 1, 4 do
        c = swt.level_up("t_cmd")
        table.insert(shown, tostring(c.variables.sw_rank_shown))
      end
      check("each AMLA raises the rank, capped at III", table.concat(shown, ",") == "1,2,3,3", table.concat(shown, ","))
      check("rank III insignia drawn last", tostring(c.image_mods):find("sw%-rank%-republic%-3") ~= nil)
      check("one insignia object per rank shown (none after the cap)", swt.objects(c, "sw_rank_insignia") == 3, swt.objects(c, "sw_rank_insignia"))
      check("AMLA stats unchanged from the default: +3 max HP each, full heal",
        c.max_hitpoints == hp0 + 12 and c.hitpoints == c.max_hitpoints, hp0 .. " -> " .. c.max_hitpoints)
      check("rank shown in Tactical status", rank.status_line(c) and rank.status_line(c):find("3/3") ~= nil)
      swt.place("sw_hero_han", 1, 5, 5, "t_han")
      check("heroes rank up too (Han: chevrons)", tostring(swt.level_up("t_han").image_mods):find("sw%-rank%-republic%-1") ~= nil)
      swt.place("sw_hero_cbaoth", 2, 7, 5, "t_cb")
      check("dark Jedi wear violet marks", tostring(swt.level_up("t_cb").image_mods):find("sw%-rank%-darkside%-1") ~= nil)
      swt.place("sw_hero_pellaeon", 2, 9, 5, "t_pel")
      check("Imperial officers wear the rank plaque", tostring(swt.level_up("t_pel").image_mods):find("sw%-rank%-imperial%-1") ~= nil)
      local v = swt.place("sw_unit_wl_vornskr", 3, 11, 5, "t_vor")
      local vhp = v.max_hitpoints
      v = swt.level_up("t_vor")
      check("creatures gain the AMLA but wear no insignia", v.max_hitpoints == vhp + 3 and not tostring(v.image_mods):find("sw%-rank"))
    end

    function S.air_basics()
      swt.clear()
      local obs = swt.place("sw_unit_nr_sergeant", 1, 4, 8, "t_obs")
      swt.place("sw_unit_im_stormtrooper", 2, 8, 8, "t_e1")
      check("no sorties: no menu", swt.probe_at(8, 8).air == false)
      wesnoth.wml_actions.sw_air_support{ side = 1, sortie = "strafe", count = 2, craft = "sw_unit_nr_xwing" }
      check("[sw_air_support] grants sorties", air.charges(1, "strafe") == 2 and air.load(1).craft.strafe == "sw_unit_nr_xwing")
      check("sergeants are forward observers", #air.observers(1) == 1 and air.observers(1)[1].id == "t_obs")
      check("observer found for a visible hex in range", air.observer_for(1, 8, 8) ~= nil)
      check("no observer for a hex out of range", air.observer_for(1, 20, 8) == nil)
      check("Call air support offered on a hex in range", swt.probe_at(8, 8).air == true)
      check("not offered out of range", swt.probe_at(20, 8).air == false)
      local line = air.area("strafe", obs, 8, 8)
      local ok = #line == 4 and line[1].x == 8 and line[1].y == 8
      for i = 2, #line do
        if wesnoth.map.distance_between(4, 8, line[i].x, line[i].y) <= wesnoth.map.distance_between(4, 8, line[i - 1].x, line[i - 1].y) then ok = false end
      end
      check("strafing run: four hexes running away from the observer", ok)
      check("bombing run: the target and its six neighbours", #air.area("bombing", obs, 8, 8) == 7)
      local tired = swt.place("sw_unit_nr_commando", 1, 4, 10, "t_tired")
      tired.attacks_left = 0
      check("an observer without its attack cannot call", #air.observers(1) == 1)
      local p = air.preview(1, "strafe", obs, 8, 8)
      check("preview counts the visible enemy in the area", p.enemies == 1 and p.enemy_damage > 0)
    end

    function S.air_accuracy()
      swt.clear()
      local obs = swt.place("sw_unit_nr_sergeant", 1, 4, 8, "t_obs")
      local hexes = air.area("strafe", obs, 8, 8)
      local t = air.accuracy(1, "strafe", obs, hexes)
      check("baseline accuracy: strafe 0", t.total == 0 and t.anti_air == 0 and t.jamming == 0)
      check("bombers +10", air.accuracy(1, "bombing", obs, air.area("bombing", obs, 8, 8)).total == 10)
      swt.place("sw_unit_im_at_st", 2, 9, 10, "t_aa1")
      t = air.accuracy(1, "strafe", obs, hexes)
      check("one AT-ST in range: -20 anti-air", t.anti_air == 20 and t.total == -20, t.anti_air)
      swt.place("sw_unit_im_at_st", 2, 10, 10, "t_aa2")
      swt.place("sw_unit_im_at_st", 2, 11, 10, "t_aa3")
      t = air.accuracy(1, "strafe", obs, hexes)
      check("anti-air is capped at -40", t.anti_air == 40, t.anti_air)
      swt.place("sw_unit_nr_eweb_team", 1, 9, 6, "t_own_aa")
      check("friendly anti-air does not hinder your own sorties", air.accuracy(1, "strafe", obs, hexes).anti_air == 40)
      for _i, id in ipairs{ "t_aa1", "t_aa2", "t_aa3" } do u(id):erase() end
      local j = swt.place("sw_unit_im_stormtrooper", 2, 8, 6, "t_jam")
      ew.set_profile(j, { ecm = 2, ecm_range = 2 })
      check("enemy jamming over the target: -10 per point", air.accuracy(1, "strafe", obs, hexes).jamming == 20)
      ew.set_profile(u("t_obs"), { eccm = 1 })
      check("observer ECCM offsets jamming", air.accuracy(1, "strafe", u("t_obs"), hexes).jamming == 10)
    end

    function S.air_strafe()
      swt.clear()
      local obs = swt.place("sw_unit_nr_sergeant", 1, 4, 8, "t_obs")
      air.grant(1, "strafe", 1, "sw_unit_nr_xwing")
      air.grant(1, "bombing", 1, "sw_unit_nr_ywing")
      local line = air.area("strafe", obs, 8, 8)
      swt.place("sw_unit_im_stormtrooper", 2, line[1].x, line[1].y, "t_e1")
      swt.place("sw_unit_nr_trooper", 1, line[2].x, line[2].y, "t_friend")
      local weak = swt.place("sw_unit_im_stormtrooper", 2, line[3].x, line[3].y, "t_weak")
      weak.hitpoints = 2
      swt.mem.hp = { t_e1 = u("t_e1").hitpoints, t_friend = u("t_friend").hitpoints, t_weak = 2 }
      doctrine.enable(2)
      swt.mem.strikes = {}
      swt.mem.call = air.call(1, "strafe", obs, 8, 8)
    end
    function S.check_strafe()
      check("strafing run called", swt.mem.call ~= nil)
      local s = swt.mem.strikes and swt.mem.strikes[1]
      check("strafing run resolved at once", s ~= nil and #s.results == 3, s and #s.results)
      local exact, detail = true, {}
      for _i, r in ipairs(s and s.results or {}) do
        if not swt.damage_ok(r.id, swt.mem.hp[r.id], 6, r.hits, "fire") then exact = false end
        table.insert(detail, r.id .. " " .. r.hits .. " hits " .. swt.mem.hp[r.id] .. "->" .. tostring(u(r.id) and u(r.id).hitpoints))
      end
      check("each unit takes 6 fire per hit (3 shots, after resistance), friend and foe alike", exact, table.concat(detail, "; "))
      check("sorties never kill", u("t_weak") ~= nil and u("t_weak").hitpoints >= 1)
      check("the friendly trooper in the line was also fired on", s and (function()
        for _i, r in ipairs(s.results) do if r.id == "t_friend" then return true end end return false end)())
      check("charge spent and observer's attack used", air.charges(1, "strafe") == 0 and u("t_obs").attacks_left == 0)
      local ok, why = air.can_call(1, "bombing")
      check("one sortie per side per turn", not ok and tostring(why):find("per turn") ~= nil, why)
      check("doctrine observes the enemy's air support", doctrine.load(2).patterns.tactic and
        doctrine.load(2).patterns.tactic.air_strafe == 1)
      check("strikes give the observer experience", u("t_obs").experience > 0 or (function()
        for _i, r in ipairs(s and s.results or {}) do if r.hits > 0 then return false end end return true end)())
    end

    function S.air_bombing()
      swt.clear()
      swt.mem.strikes = {}
      local obs = swt.place("sw_unit_nr_commando", 1, 4, 4, "t_obs")
      air.grant(1, "bombing", 1, "sw_unit_nr_ywing")
      swt.place("sw_unit_im_stormtrooper", 2, 8, 4, "t_e1")
      local w = swt.place("sw_unit_im_stormtrooper", 2, 9, 4, "t_weak")
      w.hitpoints = 2
      local hp = u("t_e1").hitpoints
      swt.mem.hp = { t_e1 = hp, t_weak = 2 }
      local id = air.call(1, "bombing", obs, 8, 4)
      local inbound = wml.array_access.get("sw_air_inbound")
      check("bombing run is telegraphed, not immediate", id ~= nil and #inbound == 1 and #swt.mem.strikes == 0 and
        u("t_e1").hitpoints == hp)
      local marked, public = 0, true
      for _i, h in ipairs(air.area("bombing", obs, 8, 4)) do
        for _j, it in ipairs(wesnoth.interface.get_items(h.x, h.y)) do
          if it.image == "misc/sw-air-inbound.png" then
            marked = marked + 1
            if it.team_name and it.team_name ~= "" then public = false end
          end
        end
      end
      check("all seven hexes marked inbound", marked == 7, marked)
      check("the inbound warning is visible to every side", public)
      check("it lands at the caller's next turn", tonumber(inbound[1].due_turn) == wesnoth.current.turn + 1)
    end
    function S.land_bombing()
      local inbound = wml.array_access.get("sw_air_inbound")
      inbound[1].due_turn = wesnoth.current.turn
      wml.array_access.set("sw_air_inbound", inbound)
      air.on_side_turn(1)
    end
    function S.check_bombing()
      local s = swt.mem.strikes[1]
      check("bombing run landed on the units in the area", s ~= nil and #s.results == 2, s and #s.results)
      local exact, detail = true, {}
      for _i, r in ipairs(s and s.results or {}) do
        if not swt.damage_ok(r.id, swt.mem.hp[r.id], 9, r.hits, "fire") then exact = false end
        table.insert(detail, r.id .. " " .. r.hits .. " hits " .. swt.mem.hp[r.id] .. "->" .. tostring(u(r.id) and u(r.id).hitpoints))
      end
      check("each unit takes 9 fire per bomb (2 bombs, after resistance)", exact, table.concat(detail, "; "))
      check("bombing never kills", u("t_weak") and u("t_weak").hitpoints >= 1)
      local left = 0
      for x = 6, 11 do for y = 2, 6 do
        for _j, it in ipairs(wesnoth.interface.get_items(x, y)) do if it.image == "misc/sw-air-inbound.png" then left = left + 1 end end
      end end
      check("inbound markers cleared after landing", left == 0 and #wml.array_access.get("sw_air_inbound") == 0)
    end

    function S.scripted()
      swt.clear()
      swt.mem.strikes = {}
      swt.place("sw_unit_nr_trooper", 1, 9, 12, "t_target")
      swt.place("sw_unit_im_stormtrooper", 2, 10, 12, "t_own")
      swt.mem.hp = u("t_target").hitpoints
      swt.mem.hp_own = u("t_own").hitpoints
      wesnoth.wml_actions.sw_air_strike{ side = 2, sortie = "strafe", craft = "sw_unit_im_tie_fighter", damage = 8,
        strikes = 1, certain = true, enemies_only = true, T.filter_location{ y = 12, x = "8-12" } }
    end
    function S.check_scripted()
      check("scripted strike: certain, fixed 8 damage", u("t_target").hitpoints == swt.mem.hp - 8,
        swt.mem.hp .. " -> " .. u("t_target").hitpoints)
      check("scripted strike spares the caller's side when enemies_only", u("t_own").hitpoints == swt.mem.hp_own)
      check("scripted strike uses no charge", air.charges(2, "strafe") == 0)
    end

    function S.carryover()
      swt.clear()
      air.grant(1, "strafe", 2, "sw_unit_nr_xwing")
      local st = wml.variables.sw_air_s1
      st.scenario = "some_earlier_mission"
      wml.variables.sw_air_s1 = st
      check("sorties from an earlier mission do not carry over", air.charges(1, "strafe") == 0)
      wml.array_access.set("sw_air_inbound", { { id = "old", side = 1, sortie = "bombing", xs = "3", ys = "3", due_turn = 1 } })
      wml.variables.sw_air_scenario = "some_earlier_mission"
      air.ensure_scenario()
      check("inbound strikes from an earlier mission are dropped", #wml.array_access.get("sw_air_inbound") == 0)
    end

    -- AI keeps out of a telegraphed bombing area.
    function S.ai_avoid()
      swt.clear()
      wesnoth.sides[2].controller = "ai"
      local obs = swt.place("sw_unit_nr_sergeant", 1, 4, 8, "t_obs")
      swt.place("sw_unit_nr_trooper", 1, 9, 8, "t_bait")
      swt.place("sw_unit_im_stormtrooper", 2, 13, 8, "t_ai")
      air.grant(1, "bombing", 1, "sw_unit_nr_ywing")
      air.call(1, "bombing", obs, 9, 8)
      swt.mem.area = {}
      for _i, h in ipairs(air.area("bombing", obs, 9, 8)) do swt.mem.area[h.x .. "," .. h.y] = true end
      swt.mem.ai_pos = {}
      wesnoth.game_events.add{ name = "moveto", id = "sw_test_track", first_time_only = false, action = function()
        local ec = wesnoth.current.event_context
        local m = wesnoth.units.get(ec.x1, ec.y1)
        if m and m.side == 2 then table.insert(swt.mem.ai_pos, ec.x1 .. "," .. ec.y1) end
      end }
    end
    function S.check_ai_avoid()
      local entered = false
      for _i, p in ipairs(swt.mem.ai_pos) do if swt.mem.area[p] then entered = true end end
      check("AI turn with an inbound bombing run completed", true)
      check("the AI did not move into the marked area", not entered, table.concat(swt.mem.ai_pos, " "))
      check("the bombing run landed at the caller's next turn", #wml.array_access.get("sw_air_inbound") == 0)
      wesnoth.game_events.remove("sw_test_track")
    end

    -- AI calls its own sortie on visible enemies at the end of its turn.
    function S.ai_air()
      swt.clear()
      swt.mem.strikes = {}
      swt.place("sw_unit_nr_trooper", 1, 10, 8, "t_p1")
      swt.place("sw_unit_nr_trooper", 1, 10, 9, "t_p2")
      local off = swt.place("sw_unit_im_officer", 2, 15, 8, "t_ai_off")
      off.canrecruit = true
      -- A passive leader neither moves nor attacks, so it keeps its attack to call.
      wesnoth.wml_actions.modify_side{ side = 2, T.ai{ passive_leader = true } }
      air.grant(2, "strafe", 1, "sw_unit_im_tie_fighter")
      wesnoth.sides[2].controller = "ai"
    end
    function S.check_ai_air()
      check("AI side called its strafing run", air.charges(2, "strafe") == 0)
      local s = swt.mem.strikes[1]
      check("AI strike hit the visible enemies", s ~= nil and s.strike.side == 2 and #s.results >= 1)
      wesnoth.sides[2].controller = "human"
    end

    -- Weapon ranges, accuracy falloff and aimed shots (engine combat simulation).
    function S.weapon_ranges()
      swt.clear()
      local function idx(u, name)
        for i, a in ipairs(u.attacks) do if a.name == name then return i end end
      end
      -- Chance to hit, and strikes that can actually land (0 when the weapon
      -- is out of range: the simulation then deals no damage).
      local function cth(att, name, def)
        local _a, d, aw = wesnoth.simulate_combat(att, idx(att, name), def)
        local landed = (def.hitpoints - d.average_hp) > 0.001 and aw.num_blows or 0
        return aw.chance_to_hit, landed
      end
      local tr = swt.place("sw_unit_nr_trooper", 1, 5, 8, "t_tr")
      local st = swt.place("sw_unit_im_stormtrooper", 2, 6, 8, "t_st")
      local c1, n1 = cth(tr, "blaster_rifle", st)
      st:to_map(7, 8)
      local c2, n2 = cth(tr, "blaster_rifle", st)
      check("rifle reaches 2 hexes with -10% to hit", n2 == 3 and c2 == c1 - 10, c1 .. "% -> " .. c2 .. "%")
      local rifle = tr.attacks[idx(tr, "blaster_rifle")]
      check("rifle range is 1-2 (the engine refuses targets beyond max_range)", rifle.min_range == 1 and rifle.max_range == 2)
      st:to_map(7, 8)
      local ca, na = cth(tr, "blaster_rifle_aimed", st)
      check("aimed shot: one strike fewer, +20% (net +10% at 2 hexes)", na == 2 and ca == c1 + 10, ca .. "% x" .. na)
      local aimed = tr.attacks[idx(tr, "blaster_rifle_aimed")]
      check("aimed shot needs 2 hexes (min_range 2)", aimed.min_range == 2 and aimed.max_range == 2)
      st:to_map(7, 8)
      local _a, _d, _aw, dw = wesnoth.simulate_combat(st, idx(st, "blaster_rifle"), tr)
      check("aimed shot is never used to retaliate", dw and dw.name ~= "blaster_rifle_aimed", dw and dw.name)
      local mil = swt.place("sw_unit_nr_militia", 1, 5, 6, "t_mil")
      st:to_map(7, 6)
      local pistol = mil.attacks[idx(mil, "blaster_pistol")]
      check("pistols reach only adjacent targets (max_range 1)", pistol.max_range == 1)
      local han = swt.place("sw_hero_han", 1, 3, 10, "t_han")
      st:to_map(5, 10)
      local _ch, nh = cth(han, "heavy_blaster_pistol", st)
      check("Han's DL-44 is the exception: 2 hexes", nh > 0, nh)
      local ew_ = swt.place("sw_unit_nr_eweb_team", 1, 3, 12, "t_eweb")
      st:to_map(4, 12)
      local e1 = cth(ew_, "eweb_repeater", st)
      st:to_map(6, 12)
      local e3, ne3 = cth(ew_, "eweb_repeater", st)
      check("E-Web reaches 3 hexes at -20%", ne3 == 3 and e3 == e1 - 20, e1 .. " -> " .. e3)
      local xw = swt.place("sw_unit_nr_xwing", 1, 12, 4, "t_xw")
      local tie = swt.place("sw_unit_im_tie_fighter", 2, 13, 4, "t_tie")
      local t1 = cth(xw, "proton_torpedoes", tie)
      tie:to_map(15, 4)
      local t3, nt3 = cth(xw, "proton_torpedoes", tie)
      check("guided torpedoes reach 3 hexes without falloff", nt3 > 0 and t3 == t1, t1 .. " -> " .. t3)
      local shown = false
      for _i, sp in ipairs(tr.attacks[idx(tr, "blaster_rifle")].specials) do
        if sp[2] and sp[2].id == "sw_special_range" and tostring(sp[2].name) == "range 2" then shown = true end
      end
      check("the range is listed with the weapon's specials", shown)
    end

    -- AI fires from range at a target that cannot shoot back that far.
    function S.ai_ranged()
      swt.clear()
      swt.mem.shots = {}
      wesnoth.game_events.add{ name = "attack", id = "sw_test_shots", first_time_only = false, action = function()
        local ec = wesnoth.current.event_context
        local a = wesnoth.units.get(ec.x1, ec.y1)
        if a and a.side == 2 then
          table.insert(swt.mem.shots, { d = wesnoth.map.distance_between(ec.x1, ec.y1, ec.x2, ec.y2),
            w = (wml.get_child(ec, "weapon") or {}).name })
        end
      end }
      wml.variables.sw_systems_debug = true
      swt.place("sw_unit_nr_militia", 1, 10, 8, "t_mil")
      swt.place("sw_unit_im_stormtrooper", 2, 15, 8, "t_ai_st")
      local ok, best = pcall(function()
        return wesnoth.dofile("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua").best_attack(2, {})
      end)
      check("the AI's stand-off evaluation finds a 2-hex shot", ok and type(best) == "table" and
        wesnoth.map.distance_between(best.x, best.y, 10, 8) == 2, tostring(best))
      wesnoth.sides[2].controller = "ai"
    end
    function S.check_ai_ranged()
      wesnoth.game_events.remove("sw_test_shots")
      wesnoth.sides[2].controller = "human"
      local shot = swt.mem.shots[1]
      check("the AI attacked", shot ~= nil)
      check("the AI fired from 2 hexes, out of the pistol's reach", shot and shot.d == 2,
        shot and (shot.d .. " " .. tostring(shot.w)))
    end

    -- Guard alertness and stealth (lua/sw_alert.lua).
    function S.alert_rules()
      swt.clear()
      local alert = sw_systems.alert
      local g1 = swt.place("sw_unit_sm_smuggler", 2, 10, 4, "t_g1")
      local g2 = swt.place("sw_unit_sm_smuggler", 2, 13, 5, "t_g2")
      local g3 = swt.place("sw_unit_sm_smuggler", 2, 20, 12, "t_g3")
      local spy = swt.place("sw_unit_nr_commando", 1, 3, 4, "t_spy")
      wesnoth.wml_actions.sw_alert{ action = "enable", guard_side = 2, intruder_side = 1 }
      check("guards start unaware", alert.is_unaware(u("t_g1")) and alert.is_unaware(u("t_g3")))
      local sight = 0
      for _i, loc in ipairs(wml.array_access.get("sw_alert_drawn")) do sight = sight + 1 end
      local item = wesnoth.interface.get_items(11, 4)[1]
      check("guard sight shown to the intruder team only", sight > 0 and item and item.team_name == core.team_key(1),
        sight .. " " .. tostring(item and item.team_name))
      spy:to_map(6, 4); alert.check()
      check("4 hexes away in the open: not spotted", alert.is_unaware(u("t_g1")))
      check("one hex beyond sight: the guard is suspicious (?)",
        table.concat(u("t_g1").overlays, ","):find("sw%-alert%-suspicious") ~= nil)
      -- Real move order into sight.
      u("t_spy").moves = 5
      swt.move_to("t_spy", 7, 4)
      check("3 hexes away in the open: spotted on the move", not alert.is_unaware(u("t_g1")))
      check("the shout alerts a guard within 4 hexes", not alert.is_unaware(u("t_g2")))
      check("a distant guard stays unaware", alert.is_unaware(u("t_g3")))
      check("alert guards show !", table.concat(u("t_g1").overlays, ","):find("sw%-alert%-alert") ~= nil)
      check("an alert guard is no longer a guardian", u("t_g1").status.guardian ~= true)
      -- Cover: the forest block at 14-17,11-13; g3 at 20,12.
      u("t_spy"):to_map(17, 12); alert.check()
      check("3 hexes away in cover: not spotted", alert.is_unaware(u("t_g3")))
      u("t_spy").variables.sw_alert_fought_turn = wesnoth.current.turn
      alert.check()
      check("noise from fighting extends sight by 1", not alert.is_unaware(u("t_g3")))
      -- Line of sight: a wall between.
      swt.clear()
      -- Same column, so the line of sight runs straight through 10,7.
      local g = swt.place("sw_unit_sm_smuggler", 2, 10, 8, "t_gw")
      swt.place("sw_unit_nr_commando", 1, 10, 6, "t_spy")
      wesnoth.wml_actions.terrain{ x = 10, y = 7, terrain = "Xu" }
      wesnoth.wml_actions.sw_alert{ action = "enable", guard_side = 2, intruder_side = 1 }
      alert.check()
      check("a wall between blocks sight", alert.is_unaware(u("t_gw")))
      wesnoth.wml_actions.terrain{ x = 10, y = 7, terrain = "Gg" }
      alert.check()
      check("with the wall gone the guard sees", not alert.is_unaware(u("t_gw")))
      -- Patrol and unaware guards holding still.
      swt.clear()
      local pg = swt.place("sw_unit_sm_smuggler", 2, 15, 3, "t_patrol")
      wesnoth.wml_actions.sw_alert{ action = "enable", guard_side = 2, intruder_side = 1 }
      wesnoth.wml_actions.sw_alert{ action = "guard", T.filter{ id = "t_patrol" }, patrol = "17.3,15.3" }
      alert.on_side_turn(2)
      pg = u("t_patrol")
      check("a patrolling guard walks to its next waypoint", pg.x == 17 and pg.y == 3, pg.x .. "," .. pg.y)
      check("unaware guards neither move further nor attack", pg.moves == 0 and pg.attacks_left == 0)
      alert.on_side_turn(2)
      check("and walks back along its route", u("t_patrol").x == 15)
      -- Alarm and reinforcements.
      wesnoth.wml_actions.sw_alert{ action = "alarm" }
      check("the alarm alerts every guard", not alert.is_unaware(u("t_patrol")))
      swt.place("sw_unit_sm_smuggler", 2, 20, 3, "t_late")
      check("reinforcements after the alarm arrive alert", not alert.is_unaware(u("t_late")))
    end

    function S.alert_takedown()
      swt.clear()
      local alert = sw_systems.alert
      swt.place("sw_unit_sm_smuggler", 2, 10, 8, "t_victim")
      swt.place("sw_unit_sm_smuggler", 2, 13, 8, "t_witness")     -- 3 hexes, open: sees the spot
      swt.place("sw_unit_sm_smuggler", 2, 20, 2, "t_far")
      swt.place("sw_unit_wl_vornskr", 2, 9, 9, "t_beast")
      local spy = swt.place("sw_unit_nr_commando", 1, 9, 8, "t_spy")
      wesnoth.wml_actions.sw_alert{ action = "enable", guard_side = 2, intruder_side = 1, show_sight = false }
      -- (The spy is adjacent, so the victim would spot it on the next check;
      -- the takedown happens first, as when a player sneaks up and acts.)
      wml.variables.x1, wml.variables.y1 = 9, 8
      local ok, vis = pcall(alert.takedown_menu_visible)
      wml.variables.x1, wml.variables.y1 = nil, nil
      check("Silent takedown is offered next to an unaware guard", ok and vis == true, tostring(vis))
      local ids = {}
      for _i, g in ipairs(alert.takedown_targets(spy)) do ids[g.id] = true end
      check("creatures cannot be taken down", ids.t_victim and not ids.t_beast)
      alert.takedown(u("t_spy"), u("t_victim"))
      check("the guard is knocked out", u("t_victim") == nil)
      check("a takedown uses the attack", u("t_spy").attacks_left == 0)
      check("a guard who sees the spot raises the alarm", not alert.is_unaware(u("t_witness")))
      check("a guard who cannot see it stays unaware", alert.is_unaware(u("t_far")))
      local g = swt.place("sw_unit_sm_smuggler", 2, 3, 12, "t_hit")
      g.variables.sw_alert_state = "unaware"
      wesnoth.game_events.fire("attack", { 4, 12 }, { 3, 12 }, { T.first{ name = "x", type = "fire", range = "ranged" } })
      check("an unaware guard that is attacked becomes alert", not alert.is_unaware(u("t_hit")))
    end

    -- AI: unaware guards hold their posts during the AI turn.
    function S.alert_ai()
      swt.clear()
      swt.place("sw_unit_sm_smuggler", 2, 20, 12, "t_post")
      swt.place("sw_unit_nr_commando", 1, 16, 12, "t_spy")     -- 4 hexes, in the forest: unseen
      wesnoth.wml_actions.sw_alert{ action = "enable", guard_side = 2, intruder_side = 1 }
      swt.mem.spy_hp = u("t_spy").hitpoints
      wesnoth.sides[2].controller = "ai"
    end
    function S.check_alert_ai()
      wesnoth.sides[2].controller = "human"
      local post = u("t_post")
      check("an unaware AI guard holds its post", post and post.x == 20 and post.y == 12, post and (post.x .. "," .. post.y))
      check("and does not attack", u("t_spy").hitpoints == swt.mem.spy_hp)
    end

    function S.prepare_save()
      swt.clear()
      local obs = swt.place("sw_unit_nr_commando", 1, 4, 4, "t_obs")
      for _i = 1, 2 do swt.level_up("t_obs") end
      air.grant(1, "strafe", 2, "sw_unit_nr_xwing")
      air.grant(1, "bombing", 1, "sw_unit_nr_ywing")
      air.call(1, "bombing", u("t_obs"), 8, 4)
      wml.variables.swt_digest = sw_systems.digest()
      std_print("SW_TEST: state prepared for save")
    end

    function S.load()
      check("save/load: state identical after reload", wml.variables.swt_digest == sw_systems.digest())
      check("save/load: sorties kept", air.charges(1, "strafe") == 2 and air.charges(1, "bombing") == 0)
      check("save/load: inbound bombing kept", #wml.array_access.get("sw_air_inbound") == 1)
      local marked = 0
      for _j, it in ipairs(wesnoth.interface.get_items(8, 4)) do if it.image == "misc/sw-air-inbound.png" then marked = marked + 1 end end
      check("save/load: inbound marker kept", marked == 1)
      local c = u("t_obs")
      check("save/load: rank insignia kept", c and tostring(c.image_mods):find("sw%-rank%-republic%-2") ~= nil and rank.of(c) == 2)
    end

    function swt.step(name)
      local ok, err = pcall(S[name])
      if not ok then std_print("SW_TEST: FAIL " .. name .. " -- error: " .. tostring(err)) end
    end
  end)
  settle()

  local steps = PHASE == "main" and STEPS or { "load" }
  for _, name in ipairs(steps) do
    local step = name
    wesnoth.plugin.execute(context, function() swt.step(step) end)
    settle()
    if END_TURN_AFTER[step] then
      context.end_turn{}
      local g = 0
      repeat
        settle(); g = g + 1
      until (info.name == "Game" and info.current_side and info.current_side() == 1) or g > 50
    end
  end
  if PHASE == "main" then
    context.save_game{ filename = "sw_air_test_save" }
    settle()
    std_print("SW_TEST: saved")
  end
  std_print("SW_TEST: done")
  while info.name ~= "titlescreen" do
    if info.name == "Dialog" then context.skip_dialog{} elseif context.quit then context.quit{} end
    events, context, info = wesnoth.plugin.next_slice()
  end
  context.exit{ code = 0 }
end
return plugin
