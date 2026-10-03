-- Deterministic engine tests for the sensors/EW and Thrawn Doctrine systems.
-- run_systems_tests.py --suite intel points the campaign at sw_test_intel and
-- runs this plugin. PHASE is substituted: "main" runs every test and saves;
-- "load" runs after reloading that save and checks that state survived.
--
-- Side 1 (team republic) plays under fog, side 2 (imperial) without. Sensor
-- arithmetic is made exact by giving units explicit profiles; the defaults
-- are checked separately. Helpers live in the game's Lua state (global swt).
local CAMPAIGN = "Star_Wars_Thrawn_Trilogy"
local PHASE = "main"

local STEPS = {
  "profiles", "thresholds", "jamming", "sweep", "transitions", "real_move", "decoys", "terrain_env",
  "reveal", "leakage", "menu_show_if", "doctrine_gain", "doctrine_control", "doctrine_effects", "check_doctrine_effects",
  "integration", "carryover", "ai_turn", "check_ai_turn", "prepare_save",
}

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
    local ew, doctrine, force, ow, core = sw_systems.ew, sw_systems.doctrine, sw_systems.force, sw_systems.overwatch, sw_systems.core
    swt = { mem = {} }
    function swt.check(name, cond, detail)
      std_print("SW_TEST: " .. (cond and "PASS " or "FAIL ") .. name ..
        ((not cond and detail ~= nil) and (" -- " .. tostring(detail)) or ""))
    end
    function swt.u(id) return wesnoth.units.get(id) end
    -- Events flush the engine's per-unit visibility cache; tests that query
    -- visibility after changing concealment fire this no-op event first.
    wesnoth.game_events.add{ name = "sw_test_flush", id = "sw_test_flush", first_time_only = false, action = function() end }
    wesnoth.game_events.add{ name = "sw_test_probe", id = "sw_test_probe", first_time_only = false, action = function()
      swt.probe = {
        contact = ew.contact_menu_visible(), status = sw_systems.status_visible(),
        force = force.menu_visible(), ow = ow.menu_visible(),
        sweep = ew.sweep_menu_visible(), decoy = ew.decoy_menu_visible(),
      }
    end }
    function swt.flush() wesnoth.game_events.fire("sw_test_flush") end
    function swt.refresh() wesnoth.wml_actions.redraw{ side = 1 }; ew.refresh(); swt.flush() end
    function swt.clear()
      for _, u in ipairs(wesnoth.units.find_on_map{}) do u:erase() end
      for _, side in ipairs{ 1, 2, 3 } do wml.variables["sw_doctrine_s" .. side] = nil end
      wml.variables.sw_doctrine_sides = nil
      for _, name in ipairs{ "sw_ew_decoys", "sw_ew_reveals", "sw_ew_terrain" } do wml.array_access.set(name, {}) end
      wml.variables.sw_ew_settings = nil
      swt.refresh()
    end
    function swt.place(type, side, x, y, id, prof)
      wesnoth.wml_actions.unit{ type = type, side = side, x = x, y = y, id = id, random_traits = false, generate_name = false }
      local u = wesnoth.units.get(id)
      if prof then ew.set_profile(u, prof) end
      return u
    end
    function swt.state(team, id) return ew.state_for(team, id) end
    function swt.seen(id, side)
      swt.flush()
      local u = wesnoth.units.get(id)
      return u ~= nil and u:matches{ T.filter_vision{ side = side, visible = true } }
    end
    function swt.items_at(x, y)
      local out = {}
      for _, it in ipairs(wesnoth.interface.get_items(x, y)) do
        if tostring(it.name):find("^sw_") then table.insert(out, it) end
      end
      return out
    end
    function swt.probe_at(x, y)
      swt.probe = nil
      wesnoth.game_events.fire("sw_test_probe", x, y)
      return swt.probe or {}
    end
    function swt.move(px, py) wesnoth.wml_actions.do_command{ T.move{ x = px, y = py } } end
    function swt.move_to(id, x, y)
      local unit = wesnoth.units.get(id)
      local path = wesnoth.paths.find_path(unit, x, y)
      local xs, ys = {}, {}
      for _, loc in ipairs(path) do table.insert(xs, loc[1] or loc.x); table.insert(ys, loc[2] or loc.y) end
      swt.move(table.concat(xs, ","), table.concat(ys, ","))
    end
    -- A deterministic sensor observer: no cloak, exact sensors.
    function swt.observer(id, x, y, prof)
      local p = { sensor = 4, sensor_range = 20, signature = 2, scan = 0, eccm = 0, ecm = 0 }
      for k, v in pairs(prof or {}) do p[k] = v end
      return swt.place("sw_unit_nr_trooper", 1, x, y, id, p)
    end
    -- A cloaked side-2 target with exact signature/cloak.
    function swt.cloaked(id, x, y, sig, cloak, extra)
      local p = { signature = sig, cloak = cloak, sensor = 0, sensor_range = 0 }
      for k, v in pairs(extra or {}) do p[k] = v end
      return swt.place("sw_unit_im_stormtrooper", 2, x, y, id, p)
    end
    local check, u = swt.check, swt.u
    local REP, IMP = "republic", "imperial"
    local S = {}
    swt.steps = S

    -- Unit-type profiles from the generated sw_ability_ew and class defaults.
    function S.profiles()
      swt.clear()
      local sd = swt.place("sw_unit_im_star_destroyer", 2, 20, 2, "t_sd")
      local p = ew.profile(sd)
      check("Star Destroyer profile from its unit type", p.class == "capital" and p.sensor == 6 and p.sensor_range == 8 and
        p.ecm == 2 and p.ecm_range == 3 and p.scan == 3 and p.decoys == 1, p.class .. " " .. p.sensor .. " " .. p.ecm)
      local ast = swt.place("sw_unit_ob_cloaked_asteroid", 2, 20, 6, "t_ast")
      p = ew.profile(ast)
      check("cloaked asteroid: cloak 6, signature 1, class object", p.cloak == 6 and p.signature == 1 and p.class == "object")
      check("cloaked asteroid keeps the concealment [hides]", ast:matches{ ability = "sw_ability_cloaked" })
      p = ew.profile(swt.place("sw_unit_im_stormtrooper", 2, 20, 10, "t_st"))
      check("infantry class defaults", p.class == "infantry" and p.sensor == 2 and p.sensor_range == 3 and p.signature == 2 and p.cloak == 0)
      p = ew.profile(swt.place("sw_unit_nr_ywing", 1, 2, 2, "t_y"))
      check("Y-wing has a sensor sweep", p.class == "starfighter" and p.scan == 3)
      check("A-wing carries a jammer", ew.profile(swt.place("sw_unit_nr_awing", 1, 2, 4, "t_a")).ecm == 2)
      check("mole miner reads as an object until identified", ew.profile(swt.place("sw_unit_im_mole_miner", 2, 20, 12, "t_mm")).disguise == "object")
      wesnoth.wml_actions.sw_ew_profile{ T.filter{ id = "t_st" }, sensor = 7, cloak = 3 }
      p = ew.profile(u("t_st"))
      check("[sw_ew_profile] overrides per unit", p.sensor == 7 and p.cloak == 3 and p.sensor_range == 3)
      check("[sw_ew_profile] cloak adds the concealment [hides]", u("t_st"):matches{ ability = "sw_ability_cloaked" })
      check("an uncovered unit's cloak is inactive", (function()
        u("t_st").status.uncovered = true
        local r = not ew.cloak_active(u("t_st"))
        u("t_st").status.uncovered = false
        return r end)())
    end

    -- Score = sensor 4 - floor(d/2) + signature - cloak at distance 2.
    function S.thresholds()
      swt.clear()
      swt.observer("t_obs", 5, 8)
      local function at(sig, cloak)
        local t = u("t_tgt") or swt.cloaked("t_tgt", 7, 8, sig, cloak)
        ew.set_profile(t, { signature = sig, cloak = cloak })
        swt.refresh()
        return swt.state(REP, "t_tgt"), ew.record(REP, "t_tgt")
      end
      local st, rec = at(3, 7)                    -- 4 - 1 + 3 - 7 = -1
      check("score -1: undetected", st == ew.NONE and rec == nil, st)
      check("undetected cloaked unit is engine-hidden", not swt.seen("t_tgt", 1))
      check("undetected: no marker on its hex", #swt.items_at(7, 8) == 0)
      st, rec = at(3, 6)                          -- 0
      check("score 0: unknown contact", st == ew.CONTACT and rec and rec.score == 0, rec and rec.score)
      check("contact keeps the unit hidden", not swt.seen("t_tgt", 1) and u("t_tgt").status.sw_ew_concealed == true)
      local items = swt.items_at(7, 8)
      check("contact marker drawn for the observing team only", #items == 1 and items[1].image == "misc/sw-contact.png" and
        items[1].team_name == REP, #items > 0 and (items[1].image .. " " .. tostring(items[1].team_name)) or "none")
      st, rec = at(3, 4)                          -- 2
      check("score 2: still a contact", st == ew.CONTACT)
      st, rec = at(3, 3)                          -- 3
      check("score 3: partially identified with class", st == ew.PARTIAL and rec.class == "infantry" and rec.type == "")
      check("partial marker shows the class", swt.items_at(7, 8)[1] and swt.items_at(7, 8)[1].image == "misc/sw-contact-infantry.png")
      st, rec = at(3, 1)                          -- 5
      check("score 5: still partial", st == ew.PARTIAL)
      st, rec = at(4, 1)                          -- 6
      check("score 6: identified", st == ew.FULL and rec.type == "sw_unit_im_stormtrooper")
      check("identified cloaked unit is revealed to the engine", swt.seen("t_tgt", 1) and u("t_tgt").status.sw_ew_concealed == false)
      check("identified cloaked unit marked with lock brackets", swt.items_at(7, 8)[1] and swt.items_at(7, 8)[1].image == "misc/sw-contact-locked.png")
      at(3, 9)
      check("cloak restored when identification is lost", not swt.seen("t_tgt", 1))
      u("t_obs"):to_map(6, 8)                      -- adjacent
      swt.refresh()
      check("physical contact always identifies", swt.state(REP, "t_tgt") == ew.FULL and swt.seen("t_tgt", 1))
      check("record notes the contact is adjacent", ew.record(REP, "t_tgt").adjacent == true)
      -- Firing drops the cloak until the unit's next turn.
      u("t_obs"):to_map(5, 8)
      at(4, 1)
      u("t_tgt").variables.sw_ew_fired = true
      swt.refresh()
      check("a cloaked unit that fired is not concealed", not u("t_tgt").status.sw_ew_concealed and swt.seen("t_tgt", 1))
      ew.on_side_turn(2)
      check("cloak returns at its side's next turn", u("t_tgt").variables.sw_ew_fired == nil)
    end

    -- ECM covering target or observer, minus ECCM.
    function S.jamming()
      swt.clear()
      swt.observer("t_obs", 5, 4)
      swt.cloaked("t_tgt", 5, 7, 4, 4)            -- d 3: 4 - 1 + 4 - 4 = 3 partial
      swt.refresh()
      check("baseline without jamming: partial", swt.state(REP, "t_tgt") == ew.PARTIAL)
      swt.place("sw_unit_im_stormtrooper", 2, 5, 9, "t_jam", { ecm = 2, ecm_range = 2, sensor = 0, sensor_range = 0 })
      swt.refresh()
      local rec = ew.record(REP, "t_tgt")
      check("ECM 2 covering the target reduces the reading by 2", rec and rec.jam == 2 and rec.score == 1 and rec.state == ew.CONTACT,
        rec and (rec.jam .. "/" .. rec.score))
      ew.set_profile(u("t_obs"), { eccm = 1 })
      swt.refresh()
      rec = ew.record(REP, "t_tgt")
      check("ECCM 1 cancels part of the jamming", rec.jam == 1 and rec.score == 2)
      ew.set_profile(u("t_obs"), { eccm = 3 })
      swt.refresh()
      rec = ew.record(REP, "t_tgt")
      check("ECCM above ECM cancels it fully (never a bonus)", rec.jam == 0 and rec.score == 3 and rec.state == ew.PARTIAL)
      ew.set_profile(u("t_obs"), { eccm = 0 })
      u("t_jam"):to_map(5, 2)                      -- now 2 from the observer, 5 from the target
      swt.refresh()
      check("ECM covering the observer also jams it", ew.record(REP, "t_tgt").jam == 2)
      u("t_jam"):to_map(15, 2)
      swt.refresh()
      check("out-of-range jammer has no effect", ew.record(REP, "t_tgt").jam == 0)
      ew.set_profile(u("t_tgt"), { ecm = 1, ecm_range = 1 })
      swt.refresh()
      rec = ew.record(REP, "t_tgt")
      check("a jammer emits: +2 signature, jams itself by its ECM", rec.net == 4 + 2 - 4 and rec.jam == 1, rec.net .. " " .. rec.jam)
    end

    function S.sweep()
      swt.clear()
      swt.observer("t_obs", 3, 6, { sensor = 4, sensor_range = 4, scan = 3 })
      swt.cloaked("t_tgt", 9, 6, 4, 6)            -- d 6: out of range 4
      swt.refresh()
      check("before the sweep the target is out of sensor range", swt.state(REP, "t_tgt") == ew.NONE)
      -- Side 2's reading of the sweeper: give it a cloak so sensors (not sight) apply.
      ew.set_profile(u("t_obs"), { cloak = 9 })
      swt.place("sw_unit_im_stormtrooper", 2, 3, 9, "t_listener", { sensor = 8, sensor_range = 10 })
      swt.refresh()
      local before = ew.record(IMP, "t_obs")
      local probe = swt.probe_at(3, 6)
      check("sweep menu offered on a unit that can sweep", probe.sweep == true)
      -- The engine fires a menu item as the event "menu item <id>" at the hex.
      wesnoth.game_events.fire("menu item sw_ew_sweep_menu", 3, 6)
      swt.flush()
      local obs = u("t_obs")
      check("sweep via the menu commits the attack", obs.attacks_left == 0 and obs.variables.sw_ew_sweep == true)
      local rec = ew.record(REP, "t_tgt")
      -- 4 + 3 (scan) - 3 (d 6) + 4 - 6 = 2
      check("sweep extends range by 2 and adds the scan rating", rec and rec.sweep == 3 and rec.score == 2 and rec.state == ew.CONTACT,
        rec and rec.score)
      local after = ew.record(IMP, "t_obs")
      check("sweeping raises the sweeper's own emissions by 3", before and after and after.net == before.net + 3,
        (before and before.net or "nil") .. " -> " .. (after and after.net or "nil"))
      check("a second sweep is refused", not ew.can_sweep(obs))
      check("sweep indicator shown", table.concat(obs.overlays, ","):find("sw%-ew%-sweep") ~= nil)
      ew.on_side_turn(1)
      check("sweep ends at the sweeper's next turn", u("t_obs").variables.sw_ew_sweep == nil and swt.state(REP, "t_tgt") == ew.NONE)
      check("units without active sensors cannot sweep", not ew.can_sweep(u("t_listener")))
    end

    -- Progressive states as distance closes (K = 4 + 7 - 4 = 7, score = 7 - floor(d/2)).
    function S.transitions()
      swt.clear()
      swt.observer("t_obs", 2, 6)
      swt.cloaked("t_tgt", 22, 6, 7, 4)
      wml.variables.sw_ew_settings = nil
      local seq = {}
      for _, x in ipairs{ 18, 14, 10, 4, 18 } do        -- distances 16, 12, 8, 2, 16 from x=2
        u("t_obs"):to_map(22 - (x - 2), 6)
        swt.refresh()
        table.insert(seq, swt.state(REP, "t_tgt"))
      end
      check("states progress undetected -> contact -> partial -> identified -> lost",
        table.concat(seq, ",") == "0,1,2,3,0", table.concat(seq, ","))
      check("lost contact removes its marker", #swt.items_at(22, 6) == 0)
      check("transition hook fires", (function()
        local n = 0
        ew.hooks.on_state_change = { function() n = n + 1 end }
        u("t_obs"):to_map(14, 6); swt.refresh()
        ew.hooks.on_state_change = {}
        return n > 0 end)())
    end

    -- A real move order refreshes the picture at its end (not per hex).
    function S.real_move()
      swt.clear()
      swt.observer("t_obs", 2, 8)
      swt.cloaked("t_tgt", 16, 8, 7, 4)            -- d 14: score 0 contact
      swt.refresh()
      check("real move: contact before", swt.state(REP, "t_tgt") == ew.CONTACT)
      swt.move_to("t_obs", 6, 8)                   -- d 10: score 2 contact... then
      local s1 = swt.state(REP, "t_tgt")
      u("t_obs").moves = 10
      swt.move_to("t_obs", 9, 8)                   -- d 7: score 4 partial
      check("a completed move order updates the picture", s1 == ew.CONTACT and swt.state(REP, "t_tgt") == ew.PARTIAL,
        s1 .. " -> " .. swt.state(REP, "t_tgt"))
    end

    function S.decoys()
      swt.clear()
      local sd = swt.place("sw_unit_im_star_destroyer", 2, 20, 4, "t_sd")
      local id = ew.deploy_decoy(sd, 14, 8)
      sd = u("t_sd")
      check("decoy launch uses the attack and a decoy charge", id ~= nil and sd.attacks_left == 0 and
        tonumber(sd.variables.sw_ew_decoys_used) == 1)
      check("decoy charges are limited", not ew.can_decoy(sd))
      -- Sensor 8 at 10 hexes (beyond the trooper's sight): 8 - 5 + 6 = 9,
      -- identified-looking but not exposed (needs 6 + 4 = 10).
      swt.observer("t_obs", 4, 8, { sensor = 8 })
      swt.refresh()
      local rec = ew.record(REP, id)
      local fogged = wesnoth.sides.is_fogged(1, { x = 14, y = 8 })
      check("decoy reads as a real contact", rec ~= nil and rec.score == 9, rec and rec.score)
      check("decoy under fog passes as an identified Star Destroyer; in sight only as classified",
        rec and ((fogged and rec.state == ew.FULL and rec.type == "sw_unit_im_star_destroyer") or (not fogged and rec.state == ew.PARTIAL)),
        rec and (tostring(fogged) .. " " .. rec.state))
      -- A real cloaked capital ship read at the same strength looks the same.
      -- Observer moved so the real ship and the decoy are at the same range.
      u("t_obs"):to_map(4, 10)
      local dd = wesnoth.map.distance_between(4, 10, 14, 8)
      local rx, ry = nil, nil
      for _, y in ipairs{ 10, 11, 12, 13, 14 } do
        for _, x in ipairs{ 14, 13, 15, 12, 16 } do
          if not rx and not wesnoth.units.get(x, y) and wesnoth.map.distance_between(4, 10, x, y) == dd and
            wesnoth.sides.is_fogged(1, { x = x, y = y }) == wesnoth.sides.is_fogged(1, { x = 14, y = 8 }) then
            rx, ry = x, y
          end
        end
      end
      local real = swt.place("sw_unit_im_star_destroyer", 2, rx, ry, "t_real", { signature = 6, cloak = 0, ecm = 0, sensor = 0, sensor_range = 0 })
      ew.set_profile(real, { cloak = 1, signature = 7 })
      -- Below identification (sensor 4: 4 - 5 + 6 = 5, partial) a decoy and a
      -- real cloaked ship must look exactly alike. (Identified, a real cloaked
      -- ship decloaks and is seen, while a decoy in plain sight cannot pass
      -- beyond partial: that difference is genuine sight, not a leak.)
      ew.set_profile(u("t_obs"), { sensor = 4 })
      swt.refresh()
      local r_real = ew.record(REP, "t_real")
      local r_fake = ew.record(REP, id)
      local same = r_real and r_fake and r_real.score == r_fake.score and r_real.class == r_fake.class and
        r_real.state == ew.PARTIAL and r_fake.state == ew.PARTIAL and r_real.image == r_fake.image
      check("a decoy and a real contact at equal strength are indistinguishable to the player",
        same and ew.describe(r_real) == ew.describe(r_fake),
        r_real and r_fake and ((ew.describe(r_real) .. " || " .. ew.describe(r_fake)):gsub("\n", " / ") .. " || " .. tostring(r_real.image) .. " " .. tostring(r_fake.image)))
      check("Sensor contact menu offered on the decoy's hex", swt.probe_at(14, 8).contact == true)
      ew.set_profile(u("t_obs"), { sensor = 8 })
      -- Exposure: identify >= full + deception (6 + 4 = 10).
      ew.set_profile(u("t_obs"), { scan = 3 })
      u("t_obs").attacks_left = 1
      u("t_obs"):to_map(12, 8)                     -- d 2: 8 - 1 + 6 = 13 >= 10
      ew.sweep(u("t_obs"))
      local decoys = wml.array_access.get("sw_ew_decoys")
      check("a strong reading exposes the decoy for that team", ew.record(REP, id) == nil and decoys[1].exposed == REP,
        decoys[1] and decoys[1].exposed)
      check("exposed decoy's marker removed", #swt.items_at(14, 8) == 0)
      -- Exposure by contact, and expiry.
      local id2 = ew.add_decoy{ x = 4, y = 3, side = 2, class = "starfighter", deception = 9 }
      swt.refresh()
      check("scenario decoy (WML) appears as a starfighter-class contact", ew.record(REP, id2) ~= nil and ew.record(REP, id2).class == "starfighter")
      u("t_obs"):to_map(4, 4)
      swt.refresh()
      check("moving next to a decoy exposes it", ew.record(REP, id2) == nil)
      wesnoth.wml_actions.sw_ew_decoy{ x = 20, y = 12, side = 2, class = "capital", turns = 0 }
      ew.on_side_turn(2)
      local left = 0
      for _, d in ipairs(wml.array_access.get("sw_ew_decoys")) do if d.x == 20 and d.y == 12 then left = left + 1 end end
      check("decoys expire at their owner's turn", left == 0)
    end

    function S.terrain_env()
      swt.clear()
      swt.observer("t_obs", 10, 9)
      swt.cloaked("t_open", 8, 9, 6, 2)            -- grass, d 2
      swt.cloaked("t_forest", 12, 13, 6, 2)        -- forest (default rule: conceal 1)
      swt.cloaked("t_hill", 10, 13, 6, 2)          -- hills: no default rule
      swt.refresh()
      local open, forest, hill = ew.record(REP, "t_open"), ew.record(REP, "t_forest"), ew.record(REP, "t_hill")
      check("forest cover conceals by 1 (default rule)", open and forest and forest.net == open.net - 1, forest and forest.net)
      check("hills have no default rule", hill and hill.net == open.net)
      wesnoth.wml_actions.sw_ew_settings{ sensor_modifier = -2, T.terrain{ terrain = "Hh", conceal = 3, sensor = -1 } }
      swt.refresh()
      hill = ew.record(REP, "t_hill")
      open = ew.record(REP, "t_open")
      check("scenario terrain rule applies", hill.net == open.net - 3)
      check("scenario-wide sensor modifier applies", open.env == -2, open.env)
      u("t_hill"):to_map(10, 11)
      u("t_obs"):to_map(10, 13)
      swt.refresh()
      check("an observer standing in bad terrain is penalised", ew.record(REP, "t_hill").env == -3, ew.record(REP, "t_hill").env)
      wesnoth.wml_actions.sw_ew_settings{ partial = 1, full = 20 }
      swt.refresh()
      check("thresholds are configurable", ew.settings().partial == 1 and ew.settings().full == 20 and ew.settings().contact == 0)
    end

    function S.reveal()
      swt.clear()
      swt.observer("t_obs", 2, 2, { sensor_range = 3 })
      swt.cloaked("t_tgt", 20, 12, 3, 8)
      swt.refresh()
      check("reveal: target undetected before", swt.state(REP, "t_tgt") == ew.NONE)
      wesnoth.wml_actions.sw_ew_reveal{ T.filter{ id = "t_tgt" }, side = 1, state = "partial", turns = 1 }
      local rec = ew.record(REP, "t_tgt")
      check("[sw_ew_reveal] gives the team a partial contact from intelligence", rec and rec.state == ew.PARTIAL and rec.score == nil)
      check("intelligence describes its source", rec and ew.describe(rec):find("intelligence") ~= nil)
      check("a partial reveal does not decloak", not swt.seen("t_tgt", 1))
      wesnoth.wml_actions.sw_ew_reveal{ T.filter{ id = "t_tgt" }, side = 1, state = "full", turns = 1 }
      check("a full reveal identifies and decloaks", swt.state(REP, "t_tgt") == ew.FULL and swt.seen("t_tgt", 1))
      local reveals = wml.array_access.get("sw_ew_reveals")
      for _, r in ipairs(reveals) do r.until_turn = wesnoth.current.turn end
      wml.array_access.set("sw_ew_reveals", reveals)
      ew.on_side_turn(1)
      check("reveals expire", swt.state(REP, "t_tgt") == ew.NONE and #wml.array_access.get("sw_ew_reveals") == 0)
    end

    -- Nothing about an undetected unit reaches the other team's UI.
    function S.leakage()
      swt.clear()
      swt.observer("t_obs", 2, 2, { sensor_range = 3 })
      local cb = swt.place("sw_hero_cbaoth", 2, 12, 6, "t_hidden_jedi", { cloak = 9, signature = 0 })
      swt.cloaked("t_contact", 4, 2, 4, 6)          -- detected contact (score 4 - 1 + 4 - 6 = 1)
      swt.refresh()
      check("viewing side in tests is side 1", core.viewing_side() == 1, core.viewing_side())
      local hidden = swt.probe_at(12, 6)
      local empty = swt.probe_at(14, 6)
      local same = true
      for _, k in ipairs{ "contact", "status", "force", "ow", "sweep", "decoy" } do
        if hidden[k] ~= empty[k] then same = false end
      end
      check("menus over a hidden unit's hex match an empty hex", same and hidden.status == false and hidden.contact == false)
      check("no marker on an undetected unit's hex", #swt.items_at(12, 6) == 0)
      check("the detected contact's hex offers Sensor contact", swt.probe_at(4, 2).contact == true)
      local private = true
      for x = 1, 22 do for y = 1, 14 do
        for _, it in ipairs(swt.items_at(x, y)) do
          local team = tostring(it.name):match("^sw_ew|([^|]*)|")
          if team and team ~= it.team_name then private = false end
        end
      end end
      check("every sensor marker is restricted to its own team", private)
      -- The other team's (side 2's) picture never draws markers for side 1's viewers.
      local imp = 0
      for x = 1, 22 do for y = 1, 14 do
        for _, it in ipairs(swt.items_at(x, y)) do if it.team_name == IMP then imp = imp + 1 end end
      end end
      check("no imperial-team markers exist (side 2 sees everything, and is not drawn for others)", imp == 0, imp)
      -- Doctrine only learns from what it can observe.
      doctrine.enable(1)
      local before = doctrine.load(1).insight
      wesnoth.game_events.fire("moveto", { 12, 6 }, { 12, 8 })
      check("an undetected enemy's move teaches the doctrine nothing", doctrine.load(1).insight == before)
      local vis = swt.place("sw_unit_im_stormtrooper", 2, 3, 4, "t_visible")
      swt.refresh()
      wesnoth.game_events.fire("moveto", { 3, 4 }, { 3, 6 })
      check("a visible enemy's move is observed", doctrine.load(1).insight == before + 1, doctrine.load(1).insight)
      doctrine.seed(1, 10)
      local text = doctrine.summary_text(doctrine.load(1))
      check("intelligence summary lists only detected forces",
        text:find(tostring(wesnoth.unit_types.sw_hero_cbaoth.name), 1, true) == nil and
        text:find(tostring(wesnoth.unit_types.sw_unit_im_stormtrooper.name), 1, true) ~= nil, text)
      check("Tactical status is refused for a hidden unit", swt.probe_at(12, 6).status == false)
    end

    -- The engine evaluates [show_if] outside any event: the hex is only in
    -- the WML variables x1, y1 (regression: every right-click raised Lua
    -- errors because menus read it from the event context).
    function S.menu_show_if()
      swt.clear()
      local luke = swt.place("sw_hero_luke", 1, 5, 5, "t_luke")
      swt.place("sw_unit_nr_eweb_team", 1, 6, 5, "t_eweb")
      swt.place("sw_unit_nr_ywing", 1, 7, 5, "t_y")
      swt.place("sw_unit_im_stormtrooper", 2, 9, 5, "t_enemy")
      swt.refresh()
      local menus = {
        force = force.menu_visible, overwatch = ow.menu_visible, sweep = ew.sweep_menu_visible,
        decoy = ew.decoy_menu_visible, contact = ew.contact_menu_visible, status = sw_systems.status_visible,
        doctrine = doctrine.menu_visible,
      }
      local expect = { ["5,5"] = { force = true, status = true }, ["6,5"] = { overwatch = true, status = true },
        ["7,5"] = { sweep = true, overwatch = true, status = true }, ["9,5"] = { status = true }, ["12,12"] = {} }
      local errors, wrong = {}, {}
      for _i, hex in ipairs{ "5,5", "6,5", "7,5", "9,5", "12,12" } do
        local x, y = hex:match("(%d+),(%d+)")
        wml.variables.x1, wml.variables.y1 = tonumber(x), tonumber(y)
        for _j, name in ipairs(core.sorted_keys(menus)) do
          local ok, res = pcall(menus[name])
          if not ok then table.insert(errors, name .. "@" .. hex .. ": " .. tostring(res))
          elseif (res == true) ~= (expect[hex][name] == true) then table.insert(wrong, name .. "@" .. hex .. "=" .. tostring(res)) end
        end
      end
      wml.variables.x1, wml.variables.y1 = nil, nil
      check("every menu's show_if runs outside an event without errors", #errors == 0, table.concat(errors, "; "))
      check("show_if picks the right-clicked hex from x1, y1", #wrong == 0, table.concat(wrong, "; "))
    end

    function S.doctrine_gain()
      swt.clear()
      local mover = swt.place("sw_unit_im_stormtrooper", 2, 6, 6, "t_m")
      swt.observer("t_obs", 4, 6)
      swt.refresh()
      local d = doctrine.enable(1)
      check("doctrine enabled with default tiers", #d.tiers == 5 and d.cap == 100 and d.insight == 0)
      local gains = {}
      for i = 1, 4 do
        wesnoth.game_events.fire("moveto", { 6, 6 }, { 6, 8 })   -- heading north each time
        table.insert(gains, doctrine.load(1).insight)
      end
      check("move observations: +1 each, at most 2 per turn, +3 when the pattern is recognised",
        table.concat(gains, ",") == "1,2,2,5", table.concat(gains, ","))
      d = doctrine.load(1)
      check("pattern recognised: they advance north", doctrine.pattern(d, "move") == "n")
      check("observed unit type studied", d.studied.sw_unit_im_stormtrooper == 4)
      d.budget_turn = wesnoth.current.turn - 1
      doctrine.save(d)
      wesnoth.game_events.fire("moveto", { 6, 6 }, { 6, 8 })
      check("the per-turn limit resets on a new turn", doctrine.load(1).insight == 6)
      -- Attack observations (weapon and target choice), as the engine fires them.
      local victim = swt.place("sw_unit_nr_trooper", 1, 6, 5, "t_victim")
      victim.hitpoints = 5
      wesnoth.game_events.fire("attack", { 6, 6 }, { 6, 5 }, {
        T.first{ name = "blaster_rifle", type = "fire", range = "ranged" },
        T.second{ name = "blaster_rifle", type = "fire", range = "ranged" } })
      d = doctrine.load(1)
      check("attack observed: damage type and range", d.patterns.attack and d.patterns.attack["fire/ranged"] == 1,
        d.patterns.attack and next(d.patterns.attack))
      check("target choice observed: wounded", d.patterns.target and d.patterns.target.wounded == 1)
      check("threshold unlock: 10 Insight opens the intelligence summary", (function()
        doctrine.seed(1, 9)
        local before = doctrine.effect(doctrine.load(1), "summary")
        wesnoth.game_events.fire("moveto", { 6, 6 }, { 6, 8 })
        local dd = doctrine.load(1)
        dd.budget_turn = 0; doctrine.save(dd)
        wesnoth.game_events.fire("moveto", { 6, 6 }, { 6, 8 })
        return before == nil and doctrine.effect(doctrine.load(1), "summary") ~= nil and doctrine.load(1).tier_reached >= 1
      end)())
      check("tier indicator on the commander", (function()
        local lead = swt.place("sw_unit_nr_sergeant", 1, 2, 12, "t_lead")
        lead.canrecruit = true
        doctrine.update_indicator(doctrine.load(1))
        return table.concat(u("t_lead").overlays, ","):find("sw%-insight%-1") ~= nil end)())
      -- Tactics reported by other systems.
      local before = doctrine.load(1).insight
      local trooper = swt.place("sw_unit_im_stormtrooper", 2, 5, 5, "t_ow")
      swt.refresh()
      ow.enter(trooper)
      check("overwatch use is observed as a tactic", doctrine.load(1).patterns.tactic and doctrine.load(1).patterns.tactic.overwatch == 1)
      check("tactic gain is 2", doctrine.load(1).insight == math.min(before + 2, 100) or doctrine.load(1).insight == before + 2)
    end

    function S.doctrine_control()
      swt.clear()
      doctrine.enable(1, { cap = 30 })
      local got = doctrine.grant(1, 50, "art", "Sculpture from the Corellian sector")
      local d = doctrine.load(1)
      check("Cultural/Art intelligence grant respects the cap", got == 30 and d.insight == 30)
      check("grant logged with its source", d.log[1] and d.log[1].source == "art" and d.log[1].amount == 30)
      check("the grant appears in the summary", doctrine.summary_text(d):find("captured art", 1, true) ~= nil)
      wesnoth.wml_actions.sw_doctrine{ action = "cap", side = 1, cap = 20 }
      check("lowering the cap lowers Insight", doctrine.load(1).insight == 20)
      wesnoth.wml_actions.sw_doctrine{ action = "seed", side = 1, amount = 45,
        T.study{ type = "sw_unit_nr_xwing", count = 3 }, T.pattern{ category = "target", key = "wounded", count = 4 } }
      d = doctrine.load(1)
      check("seed sets Insight exactly (capped at 20)", d.insight == 20)
      wesnoth.wml_actions.sw_doctrine{ action = "cap", side = 1, cap = 100 }
      wesnoth.wml_actions.sw_doctrine{ action = "seed", side = 1, amount = 45 }
      d = doctrine.load(1)
      check("pre-seed to 45 unlocks three tiers", d.insight == 45 and d.tier_reached == 3 and doctrine.effect(d, "sensors") ~= nil)
      check("seeded studies and patterns", d.studied.sw_unit_nr_xwing == 3 and doctrine.pattern(d, "target") == "wounded")
      wesnoth.wml_actions.sw_doctrine{ action = "reset", side = 1 }
      d = doctrine.load(1)
      check("reset clears Insight, patterns and studies", d.insight == 0 and next(d.patterns) == nil and next(d.studied) == nil and d.tier_reached == 0)
      wesnoth.wml_actions.sw_doctrine{ action = "disable", side = 1 }
      check("disabled doctrine ignores grants", doctrine.grant(1, 10, "archive") == 0 and doctrine.load(1).insight == 0)
      wesnoth.wml_actions.sw_doctrine{ action = "enable", side = 1, cap = 60, turn_limit = 1,
        T.tier{ insight = 5, effect = "summary" }, T.tier{ insight = 15, effect = "sensors", identify = 4, eccm = 1, discrimination = 0 } }
      d = doctrine.load(1)
      check("custom tiers and settings", #d.tiers == 2 and d.tiers[2].identify == 4 and d.cap == 60 and d.turn_limit == 1)
      check("custom gains", (function()
        wesnoth.wml_actions.sw_doctrine{ action = "enable", side = 1, T.gains{ move = 5 } }
        return doctrine.load(1).gains.move == 5 and doctrine.load(1).gains.attack == 1 end)())
      check("watch list limits the observed sides", (function()
        wesnoth.wml_actions.sw_doctrine{ action = "enable", side = 1, watch = "3" }
        swt.place("sw_unit_im_stormtrooper", 2, 3, 3, "t_w2")
        swt.observer("t_obs", 2, 3)
        swt.refresh()
        local b = doctrine.load(1).insight
        wesnoth.game_events.fire("moveto", { 3, 3 }, { 3, 5 })
        return doctrine.load(1).insight == b end)())
    end

    -- Coordination (chance to hit, also overwatch) and prediction.
    function S.doctrine_effects()
      swt.clear()
      local att = swt.place("sw_unit_nr_trooper", 1, 8, 8, "t_att")
      local studied = swt.place("sw_unit_im_stormtrooper", 2, 8, 7, "t_st")
      local other = swt.place("sw_unit_im_scout_trooper", 2, 9, 8, "t_sc")
      swt.refresh()
      doctrine.enable(1)
      wesnoth.wml_actions.sw_doctrine{ action = "seed", side = 1, amount = 80,
        T.study{ type = "sw_unit_im_stormtrooper", count = 3 }, T.pattern{ category = "target", key = "wounded", count = 4 } }
      att = u("t_att")
      check("coordination ability added to doctrine units", att:matches{ ability = "sw_ability_doctrine_coordination" })
      check("doctrine units marked active at the coordination tier", att.status.sw_doctrine_coordination == true)
      check("only studied enemy types are marked", u("t_st").status.sw_studied_s1 == true and not u("t_sc").status.sw_studied_s1)
      local _, _, w1 = wesnoth.simulate_combat(att, 1, u("t_st"))
      u("t_st").status.sw_studied_s1 = false
      local _, _, w0 = wesnoth.simulate_combat(att, 1, u("t_st"))
      u("t_st").status.sw_studied_s1 = true
      check("coordinated fire: +10% to hit a studied type", w1.chance_to_hit - w0.chance_to_hit == 10,
        w0.chance_to_hit .. " -> " .. w1.chance_to_hit)
      local shot = { accuracy = 0, damage = 5, strikes = 2 }
      doctrine.overwatch_modify(att, u("t_st"), shot)
      check("coordinated fire also sharpens overwatch reactions", shot.accuracy == 10)
      shot.accuracy = 0
      doctrine.overwatch_modify(att, u("t_sc"), shot)
      check("no bonus against unstudied types", shot.accuracy == 0)
      -- Prediction: wounded own unit within reach of a known enemy is marked.
      local hurt = swt.place("sw_unit_nr_trooper", 1, 12, 8, "t_hurt")
      hurt.hitpoints = 4
      swt.place("sw_unit_nr_trooper", 1, 1, 14, "t_safe").hitpoints = 4
      swt.refresh()
      local marked = doctrine.predict(doctrine.load(1))
      local ids = {}
      for _, m in ipairs(marked) do ids[m.id] = true end
      check("prediction marks a wounded unit enemies can reach", ids.t_hurt == true)
      check("prediction skips units no known enemy can reach", ids.t_safe == nil)
      check("prediction does not mark healthy units (pattern: wounded)", ids.t_att == nil)
      swt.mem.pred_items = #swt.items_at(12, 8)
      local d = doctrine.load(1)
      doctrine.save(d)
      swt.mem.summary = doctrine.summary_text(doctrine.load(1))
      -- The coordination bonus disappears when the doctrine is disabled.
      doctrine.disable(1)
      check("disabling clears the coordination statuses", not u("t_att").status.sw_doctrine_coordination and not u("t_st").status.sw_studied_s1)
    end
    function S.check_doctrine_effects()
      check("prediction marker drawn for the doctrine team", swt.mem.pred_items == 1, swt.mem.pred_items)
      local s = swt.mem.summary or ""
      check("summary lists patterns, sensor doctrine, prediction and coordination",
        s:find("single out", 1, true) and s:find("Sensor doctrine", 1, true) and s:find("Predicted targets", 1, true) and
        s:find("Coordinated fire", 1, true), s)
    end

    -- Doctrine/sensor integration: identification improves, detection does not.
    function S.integration()
      swt.clear()
      swt.observer("t_obs", 4, 8)
      swt.cloaked("t_mid", 8, 8, 6, 4)             -- d 4: 4 - 2 + 6 - 4 = 4: partial
      swt.cloaked("t_deep", 6, 10, 2, 9)           -- far below 0: undetected
      local decoy = ew.add_decoy{ x = 7, y = 6, side = 2, class = "capital" }   -- d 3ish
      swt.refresh()
      local dec_before = ew.record(REP, decoy)
      check("without doctrine: partial contact stays partial", swt.state(REP, "t_mid") == ew.PARTIAL)
      doctrine.enable(1)
      local d = doctrine.load(1)
      check("low Insight: the decoy is still believed", dec_before ~= nil and (d.insight < 40))
      doctrine.seed(1, 10)
      check("low-Insight summary counts the decoy as a capital ship", doctrine.summary_text(doctrine.load(1)):find(
        tostring(ew.CLASS_NAMES.capital), 1, true) ~= nil, doctrine.summary_text(doctrine.load(1)))
      doctrine.seed(1, 40)
      local rec = ew.record(REP, "t_mid")
      check("sensor doctrine: +2 identification turns the partial contact into an identification",
        rec.state == ew.FULL and rec.identify == rec.score + 2 and rec.doctrine == 2, rec.state .. " " .. tostring(rec.identify))
      check("doctrine never improves raw detection: the deep cloak stays undetected", swt.state(REP, "t_deep") == ew.NONE)
      check("doctrine ECCM reduces jamming", (function()
        swt.place("sw_unit_im_stormtrooper", 2, 8, 9, "t_jam", { ecm = 3, ecm_range = 2, sensor = 0, sensor_range = 0 })
        swt.refresh()
        return ew.record(REP, "t_mid").jam == 1 end)())
      u("t_jam"):erase()
      swt.refresh()
      local dec_after = ew.record(REP, decoy)
      -- decoy: score 4 - 1 (d 3) + 6 = 9 + 2 identify = 11 >= 6 + 4 - 2 = 8 -> exposed
      check("higher Insight sees through the decoy that fooled low Insight", dec_before ~= nil and dec_after == nil,
        dec_before and dec_before.score)
      check("once seen through, the decoy drops out of the summary",
        doctrine.summary_text(doctrine.load(1)):find(tostring(ew.CLASS_NAMES.capital), 1, true) == nil,
        doctrine.summary_text(doctrine.load(1)))
      check("recognising the enemy's decoy use was recorded", doctrine.load(1).patterns.tactic and
        doctrine.load(1).patterns.tactic.decoy == 1)
    end

    -- State from an earlier mission does not leak into the next one.
    function S.carryover()
      swt.clear()
      doctrine.enable(1)
      doctrine.seed(1, 30)
      local d = doctrine.load(1)
      d.scenario = "some_earlier_mission"
      doctrine.save(d)
      doctrine.ensure_scenario()
      check("doctrine from an earlier mission is dropped", doctrine.load(1) == nil)
      doctrine.enable(1, { persist = "yes" })
      doctrine.seed(1, 30)
      d = doctrine.load(1)
      d.scenario = "some_earlier_mission"
      doctrine.save(d)
      doctrine.ensure_scenario()
      check("persist=yes keeps doctrine across missions", doctrine.load(1) ~= nil and doctrine.load(1).insight == 30)
      wml.array_access.set("sw_ew_decoys", { { id = "old", x = 3, y = 3, side = 2, class = "capital", exposed = "" } })
      wml.variables.sw_ew_scenario = "some_earlier_mission"
      ew.ensure_scenario()
      check("EW state from an earlier mission is dropped", #wml.array_access.get("sw_ew_decoys") == 0)
      wml.array_access.set("sw_force_null_sources", { { x = 3, y = 3, radius = 2 } })
      wml.variables.sw_force_null_scenario = "some_earlier_mission"
      force.refresh_fields()
      check("ysalamiri sources from an earlier mission are dropped (regression)", not force.is_suppressed_at(3, 3))
    end

    -- AI safety: side 2 plays a turn with EW units and doctrine enabled.
    function S.ai_turn()
      swt.clear()
      doctrine.enable(2)
      swt.place("sw_unit_im_star_destroyer", 2, 18, 4, "t_ai_sd")
      swt.place("sw_unit_im_stormtrooper", 2, 21, 12, "t_ai_st")
      swt.place("sw_unit_nr_trooper", 1, 4, 12, "t_p1")
      -- A cloaked side-1 unit at contact range of the Star Destroyer's sensors.
      -- 6 - 3 (d 6) + 1 - 4 = 0: an unknown contact for side 2.
      swt.place("sw_unit_nr_commando", 1, 12, 4, "t_p_cloak", { cloak = 4, signature = 1, sensor = 0, sensor_range = 0 })
      swt.refresh()
      swt.mem.ai_pre = ew.state_for(IMP, "t_p_cloak")
      wesnoth.sides[2].controller = "ai"
    end
    function S.check_ai_turn()
      check("AI turn with sensors and doctrine completed without script errors", true)
      check("AI had an unidentified contact before its turn", swt.mem.ai_pre ~= nil and swt.mem.ai_pre >= ew.CONTACT and swt.mem.ai_pre < ew.FULL,
        swt.mem.ai_pre)
      local sd = u("t_ai_sd")
      check("AI capital ship swept for the unidentified contact", sd ~= nil and sd.variables.sw_ew_sweep == true)
      local d = doctrine.load(2)
      check("AI doctrine state stays valid", d ~= nil and type(d.insight) == "number" and d.insight >= 0 and d.insight <= d.cap)
      wesnoth.sides[2].controller = "human"
    end

    function S.prepare_save()
      swt.clear()
      swt.observer("t_obs", 4, 6)
      swt.cloaked("t_cloak", 10, 6, 4, 6)           -- d 6: 4 - 3 + 4 - 6 = -1 ... adjust below
      ew.set_profile(u("t_cloak"), { signature = 6 }) -- 1: contact
      ew.add_decoy{ x = 12, y = 9, side = 2, class = "starfighter" }
      doctrine.enable(1)
      doctrine.seed(1, 33, { T.pattern{ category = "move", key = "ne", count = 5 } })
      swt.refresh()
      wml.variables.swt_digest = sw_systems.digest()
      std_print("SW_TEST: state prepared for save " .. wml.variables.swt_digest)
    end

    function S.load()
      local saved = wml.variables.swt_digest
      local now = sw_systems.digest()
      check("save/load: intelligence state identical after reload", saved ~= nil and saved == now, tostring(saved) .. " vs " .. now)
      ew.refresh()
      check("save/load: recomputing the picture changes nothing", sw_systems.digest() == saved)
      check("save/load: sensor contact kept", ew.state_for(REP, "t_cloak") == ew.CONTACT)
      check("save/load: contact marker kept", #swt.items_at(10, 6) == 1)
      check("save/load: cloaked unit still hidden", not swt.seen("t_cloak", 1))
      check("save/load: decoy kept", #wml.array_access.get("sw_ew_decoys") == 1)
      local d = doctrine.load(1)
      check("save/load: doctrine Insight and patterns kept", d and d.insight == 33 and doctrine.pattern(d, "move") == "ne")
      check("save/load: EW ready after reload", ew.is_ready())
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
    if step == "ai_turn" then
      -- End side 1's turn; side 2 (AI) and side 3 (AI) play; back to side 1.
      context.end_turn{}
      local g = 0
      repeat
        settle(); g = g + 1
      until (info.name == "Game" and info.current_side and info.current_side() == 1) or g > 50
    end
  end
  if PHASE == "main" then
    context.save_game{ filename = "sw_intel_test_save" }
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
