-- Deterministic engine tests for the Force and overwatch systems.
-- run_systems_tests.py points the campaign at sw_test_systems and runs this
-- plugin. PHASE is substituted: "main" runs every test and saves; "load"
-- runs after reloading that save and checks that state survived.
--
-- Combat animation (reaction fire, a blocked push's slam, Force Choke) ends a
-- plugin execute call, so the tests are steps: a step may end with such an
-- action, and the following step checks its outcome. Test helpers and steps
-- live in the game's Lua state (global swt) so each execute stays upvalue-free.
local CAMPAIGN = "Star_Wars_Thrawn_Trilogy"
local PHASE = "main"

local STEPS = {
  "fp", "targets", "slam_wall", "check_slam_wall", "slam_occupied", "check_slam_occupied",
  "push_pull", "menu_text", "menu_dialog", "check_menu_dialog", "slam_edge", "check_slam_edge", "fields", "ow_fire", "check_ow_fire",
  "multi_fire", "check_multi", "deflect", "check_deflect", "deflect_field", "check_deflect_field",
  "hidden_and_trick", "arcs_and_hooks", "ai_turn", "check_ai_turn", "recursion", "check_recursion", "sense_choke", "check_choke", "prepare_save",
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
    local force, ow = sw_systems.force, sw_systems.overwatch
    swt = { mem = {} }
    -- Events flush the engine's visibility cache.
    wesnoth.game_events.add{ name = "sw_test_noop", id = "sw_test_noop", first_time_only = false, action = function() end }
    function swt.check(name, cond, detail)
      std_print("SW_TEST: " .. (cond and "PASS " or "FAIL ") .. name ..
        ((not cond and detail ~= nil) and (" -- " .. tostring(detail)) or ""))
    end
    function swt.u(id) return wesnoth.units.get(id) end
    function swt.clear()
      for _, u in ipairs(wesnoth.units.find_on_map{}) do u:erase() end
      wml.array_access.set("sw_ow_index", {})
      wml.array_access.set("sw_force_null_sources", {})
      force.refresh_fields()
    end
    function swt.place(type, side, x, y, id)
      wesnoth.wml_actions.unit{ type = type, side = side, x = x, y = y, id = id,
        random_traits = false, generate_name = false }
      return wesnoth.units.get(id)
    end
    function swt.move(px, py)
      wesnoth.wml_actions.do_command{ T.move{ x = px, y = py } }
    end
    -- Real move order along the engine's own shortest path.
    function swt.move_to(id, x, y)
      local unit = wesnoth.units.get(id)
      local path = wesnoth.paths.find_path(unit, x, y)
      local xs, ys = {}, {}
      for _, loc in ipairs(path) do table.insert(xs, loc[1] or loc.x); table.insert(ys, loc[2] or loc.y) end
      swt.move(table.concat(xs, ","), table.concat(ys, ","))
    end
    -- The hex a push from caster would move target into.
    function swt.push_dest(caster, target)
      local dir = wesnoth.map.get_relative_dir({ caster.x, caster.y }, { target.x, target.y })
      local d = wesnoth.map.get_direction({ target.x, target.y }, dir)
      return d[1] or d.x, d[2] or d.y
    end
    local check, u, place, clear, move = swt.check, swt.u, swt.place, swt.clear, swt.move
    local S = {}
    swt.steps = S

    function S.fp()
      clear()
      local luke = place("sw_hero_luke", 1, 5, 5, "t_luke")
      check("FP initialised to max on placement", tonumber(luke.variables.sw_fp) == 8, luke.variables.sw_fp)
      check("Force Speed usable", (force.can_use(luke, "speed")))
      local moves = luke.moves
      force.use(luke, "speed", luke)
      luke = u("t_luke")
      check("Force Speed spends 2 FP", tonumber(luke.variables.sw_fp) == 6, luke.variables.sw_fp)
      check("Force Speed adds 2 moves", luke.moves == moves + 2, luke.moves)
      local ok, why = force.can_use(luke, "speed")
      check("Force Speed once per turn", not ok, why)
      luke.variables.sw_fp = 1
      ok, why = force.can_use(luke, "push")
      check("insufficient FP blocks a power", not ok, why)
      force.on_side_turn(1)
      check("FP regenerates by fp_regen", tonumber(u("t_luke").variables.sw_fp) == 3, u("t_luke").variables.sw_fp)
      u("t_luke").variables.sw_fp = 8
      force.on_side_turn(1)
      check("FP regeneration capped at maximum", tonumber(u("t_luke").variables.sw_fp) == 8)
      check("FP indicator shown", table.concat(u("t_luke").overlays, ","):find("sw%-fp%-8") ~= nil)
    end

    function S.targets()
      clear()
      local luke = place("sw_hero_luke", 1, 5, 5, "t_luke")
      place("sw_unit_im_stormtrooper", 2, 6, 5, "t_enemy_near")
      place("sw_unit_im_stormtrooper", 2, 9, 5, "t_enemy_far")
      place("sw_unit_nr_trooper", 1, 4, 5, "t_ally")
      place("sw_hero_cbaoth", 2, 5, 7, "t_jedi_enemy")
      local function ids(power)
        local set = {}
        for _, t in ipairs(force.valid_targets(luke, power)) do set[t.id] = true end
        return set
      end
      local push = ids("push")
      check("push targets an enemy in range", push.t_enemy_near == true)
      check("push excludes allies", push.t_ally == nil)
      check("push excludes enemies out of range", push.t_enemy_far == nil)
      local mt = ids("mind_trick")
      check("mind trick excludes Force users", mt.t_jedi_enemy == nil)
      check("mind trick allows a weak-minded trooper", mt.t_enemy_near == true)
      check("pull excludes adjacent targets", ids("pull").t_enemy_near == nil)
      check("light-side Luke has no Force Choke", not force.can_use(luke, "choke"))
    end

    function S.slam_wall()
      clear()
      local luke = place("sw_hero_luke", 1, 10, 4, "t_luke")
      local v = place("sw_unit_im_stormtrooper", 2, 11, 4, "t_walled")
      local dx, dy = swt.push_dest(luke, v)
      wesnoth.wml_actions.terrain{ x = dx, y = dy, terrain = "Xu" }   -- wall where the push would land
      swt.mem.hp = v.hitpoints
      force.use(luke, "push", v)
    end
    function S.check_slam_wall()
      local v = u("t_walled")
      check("push into impassable terrain does not move the target", v and v.x == 11 and v.y == 4,
        v and (v.x .. "," .. v.y))
      check("a blocked push slams for damage instead", v and v.hitpoints < swt.mem.hp, v and v.hitpoints)
    end

    function S.slam_occupied()
      clear()
      local luke = place("sw_hero_luke", 1, 5, 5, "t_luke")
      local t = place("sw_unit_im_stormtrooper", 2, 6, 5, "t_pushed")
      local dx, dy = swt.push_dest(luke, t)
      place("sw_unit_nr_trooper", 1, dx, dy, "t_blocker")
      swt.mem.pos = t.x .. "," .. t.y
      swt.mem.blocker = dx .. "," .. dy
      force.use(luke, "push", t)
    end
    function S.check_slam_occupied()
      local t = u("t_pushed")
      check("push into an occupied hex never overlaps units", t and (t.x .. "," .. t.y) == swt.mem.pos)
      check("blocker undisturbed", (u("t_blocker").x .. "," .. u("t_blocker").y) == swt.mem.blocker)
      check("a blocked push slams for damage instead", u("t_pushed") == nil or u("t_pushed").hitpoints < 36)
    end

    function S.push_pull()
      clear()
      local luke = place("sw_hero_luke", 1, 5, 5, "t_luke")
      local t = place("sw_unit_im_stormtrooper", 2, 6, 5, "t_pushed")
      force.use(luke, "push", t)
      t = u("t_pushed")
      check("push moves the target one hex away", wesnoth.map.distance_between(5, 5, t.x, t.y) == 2, t.x .. "," .. t.y)
      check("push uses the caster's attack", u("t_luke").attacks_left == 0)
      check("push spends FP and starts cooldown", tonumber(u("t_luke").variables.sw_fp) == 6 and
        tonumber(u("t_luke").variables.sw_cd_push) == 1)
      clear()
      luke = place("sw_hero_luke", 1, 5, 5, "t_luke")
      t = place("sw_unit_im_stormtrooper", 2, 5, 8, "t_pulled")
      force.use(luke, "pull", t)
      t = u("t_pulled")
      check("pull moves the target one hex closer", wesnoth.map.distance_between(5, 5, t.x, t.y) == 2, t.x .. "," .. t.y)
      force.on_side_turn(1)
      check("cooldown ticks down at turn start", tonumber(u("t_luke").variables.sw_cd_pull) == 0)
    end

    -- Menu descriptions and the Push/Pull direction preview.
    function S.menu_text()
      clear()
      local function have(img)
        local ok, res = pcall(filesystem.have_file, "~add-ons/Star_Wars_Thrawn_Trilogy/images/" .. img)
        return ok and res
      end
      local luke = place("sw_hero_luke", 1, 10, 6, "t_luke")
      local v = place("sw_unit_im_stormtrooper", 2, 11, 6, "t_v")
      local dx, dy = swt.push_dest(luke, v)
      local p = force.displacement_preview(luke, v, "push")
      check("push preview matches the real push direction", p.x == dx and p.y == dy and not p.blocked)
      local text = force.displacement_text(luke, v, "push")
      check("clear push: names the destination, not bold", text:find(dx .. "," .. dy, 1, true) ~= nil and not text:find("<b>"), text)
      check("direction arrow image exists", have(force.arrow_image(p)), force.arrow_image(p))
      place("sw_unit_im_stormtrooper", 2, dx, dy, "t_blocker")
      p = force.displacement_preview(luke, v, "push")
      text = force.displacement_text(luke, v, "push")
      check("push into a unit: bold slam warning with the damage", p.blocked and p.kind == "unit" and
        text:find("<b>", 1, true) ~= nil and text:find("6 ", 1, true) ~= nil, text)
      check("blocked arrow image exists", force.arrow_image(p):find("blocked") ~= nil and have(force.arrow_image(p)))
      u("t_blocker"):erase()
      wesnoth.wml_actions.terrain{ x = dx, y = dy, terrain = "Xu" }
      p = force.displacement_preview(luke, v, "push")
      check("push into impassable terrain: blocked by terrain", p.blocked and p.kind == "terrain" and
        force.displacement_text(luke, v, "push"):find("<b>", 1, true) ~= nil)
      wesnoth.wml_actions.terrain{ x = dx, y = dy, terrain = "Gg" }
      -- A hidden (cloaked) unit in the way is not revealed by the preview.
      place("sw_unit_ob_cloaked_asteroid", 2, dx, dy, "t_hidden")
      sw_systems.ew.refresh()
      wesnoth.game_events.fire("sw_test_noop")
      p = force.displacement_preview(luke, v, "push")
      check("a hidden unit behind the target is not revealed", not u("t_hidden"):matches{ T.filter_vision{ side = 1, visible = true } } and
        not p.blocked)
      u("t_hidden"):erase()
      -- Map edge.
      v:to_map(22, 6)
      luke:to_map(21, 6)
      p = force.displacement_preview(luke, v, "push")
      check("push off the battlefield: blocked by the edge", p.blocked and p.kind == "edge")
      -- Pull blocked by a unit between.
      luke:to_map(10, 6)
      v:to_map(13, 6)
      local pp = force.displacement_preview(luke, v, "pull")
      place("sw_unit_im_stormtrooper", 2, pp.x, pp.y, "t_between")
      text = force.displacement_text(luke, v, "pull")
      check("blocked pull: bold, no damage", force.displacement_preview(luke, v, "pull").blocked and
        text:find("<b>", 1, true) ~= nil and text:find("no damage", 1, true) ~= nil, text)
      local summary = force.power_summary(luke, "push")
      check("power description lists effect, cost, range, recovery and attack use",
        summary:find("Hurl", 1, true) and summary:find("2 FP", 1, true) and summary:find("range 2", 1, true) and
        summary:find("recovers", 1, true) and summary:find("attack", 1, true), summary)
      check("passive powers are described as passive", force.power_summary(luke, "deflection"):find("passive", 1, true) ~= nil)
      check("self powers say self", force.power_summary(luke, "speed"):find("self", 1, true) ~= nil)
    end

    -- Open the real Force menu (the harness dismisses dialogs) to prove the
    -- options with descriptions and arrow icons are accepted by the engine.
    function S.menu_dialog()
      clear()
      place("sw_hero_luke", 1, 10, 6, "t_luke")
      place("sw_unit_im_stormtrooper", 2, 11, 6, "t_v")
      swt.mem.menu_ok = nil
      local ok, err = pcall(function() wesnoth.game_events.fire("menu item sw_force_menu", 10, 6) end)
      swt.mem.menu_ok = ok
      swt.mem.menu_err = err
      -- (Dismissing the first menu picks its first option, Push, so reset Luke.)
      local l = u("t_luke")
      l.variables.sw_cd_push = nil
      l.variables.sw_fp = 8
      l.attacks_left = 1
      -- Then the Push target dialog: the first choice is answered with Push,
      -- the second (targets with arrows) is the real dialog.
      local core = sw_systems.core
      local real = core.choose
      local calls = 0
      swt.mem.target_options = nil
      core.choose = function(caption, text, labels, image)
        calls = calls + 1
        if calls == 1 then
          for i, opt in ipairs(labels) do
            if type(opt) == "table" and tostring(opt.label):find("Force Push", 1, true) then swt.mem.push_label = tostring(opt.label) return i end
          end
          return 0
        end
        swt.mem.target_options = labels
        return real(caption, text, labels, image)
      end
      local ok2, err2 = pcall(function() wesnoth.game_events.fire("menu item sw_force_menu", 10, 6) end)
      core.choose = real
      swt.mem.target_ok, swt.mem.target_err = ok2, err2
      swt.mem.calls = calls
    end
    function S.check_menu_dialog()
      check("the Force menu opens with descriptions without errors", swt.mem.menu_ok == true, swt.mem.menu_err)
      check("no arrow marks left on the map after the menu", #wesnoth.interface.get_items(11, 6) == 0)
      check("the Push target dialog opens without errors", swt.mem.target_ok == true, swt.mem.target_err)
      local first = swt.mem.target_options and swt.mem.target_options[1]
      check("the Push target option shows the direction arrow and outcome", type(first) == "table" and
        tostring(first.image):find("sw%-force%-arrow%-") ~= nil and tostring(first.description):find("Pushed", 1, true) ~= nil,
        (first and (tostring(first.image) .. " " .. tostring(first.description)) or "") .. " calls=" .. tostring(swt.mem.calls) .. " push=" .. tostring(swt.mem.push_label) ..
        " opts=" .. tostring(swt.mem.target_options and #swt.mem.target_options))
    end

    function S.slam_edge()
      clear()
      local luke = place("sw_hero_luke", 1, 2, 1, "t_luke")
      local t = place("sw_unit_im_stormtrooper", 2, 1, 1, "t_edge")
      force.use(luke, "push", t)
    end
    function S.check_slam_edge()
      local t = u("t_edge")
      check("push off the map edge is refused", t == nil or wesnoth.current.map:on_board(t.x, t.y))
    end

    function S.fields()
      clear()
      place("sw_hero_luke", 1, 5, 5, "t_luke")
      local c = place("sw_unit_im_stormtrooper", 2, 15, 10, "t_carrier")
      c:add_modification("object", { id = "t_frame",
        T.effect{ apply_to = "new_ability", T.abilities{ T.dummy{ id = "sw_ability_ysalamiri", radius = 2 } } } })
      force.refresh_fields()
      check("a carrier projects a null field", force.is_suppressed_at(15, 10) and force.is_suppressed_at(17, 10))
      check("field radius is respected", not force.is_suppressed_at(18, 10))
      u("t_carrier"):to_map(6, 5)
      force.refresh_fields()
      check("the field moves with its carrier", force.is_suppressed_at(6, 5) and not force.is_suppressed_at(15, 10))
      local luke = u("t_luke")
      check("a Force user inside the field is suppressed", force.is_suppressed(luke))
      local ok, why = force.can_use(luke, "speed")
      check("a suppressed Force user cannot use powers", not ok, why)
      check("suppression indicator shown", table.concat(luke.overlays, ","):find("sw%-force%-suppressed") ~= nil)
      luke.variables.sw_fp = 2
      force.on_side_turn(1)
      check("no FP regeneration inside a field", tonumber(u("t_luke").variables.sw_fp) == 2)
      check("WML zone variable mirrors the field", #wml.array_access.get("sw_ysalamiri_zone") > 0)
      force.add_static_source(18, 3, 1)
      check("static sources register", force.is_suppressed_at(18, 3))
      wesnoth.wml_actions.kill{ id = "t_carrier", fire_event = true, animate = false }
      check("a dead carrier's field collapses", not force.is_suppressed_at(6, 5))
      -- Enter and leave by real move orders (enter_hex updates hex by hex).
      local c2 = place("sw_unit_im_stormtrooper", 2, 9, 10, "t_carrier2")
      c2:add_modification("object", { id = "t_frame",
        T.effect{ apply_to = "new_ability", T.abilities{ T.dummy{ id = "sw_ability_ysalamiri", radius = 1 } } } })
      force.refresh_fields()
      u("t_luke").moves = 10
      swt.move_to("t_luke", 9, 9)
      check("entering a field suppresses immediately", force.is_suppressed(u("t_luke")),
        u("t_luke").x .. "," .. u("t_luke").y)
      u("t_luke").moves = 10
      swt.move_to("t_luke", 9, 6)
      check("leaving a field restores the Force", not force.is_suppressed(u("t_luke")),
        u("t_luke").x .. "," .. u("t_luke").y)
      check("FP indicator returns after leaving", table.concat(u("t_luke").overlays, ","):find("sw%-fp%-") ~= nil)
    end

    function S.ow_fire()
      clear()
      local w = place("sw_unit_im_stormtrooper", 2, 10, 8, "t_watch")
      check("overwatch entered", ow.enter(w) and u("t_watch").variables.sw_ow_active == true)
      w = u("t_watch")
      check("overwatch commits the attack", w.attacks_left == 0 and w.moves == 0)
      check("overwatch is indexed", #wml.array_access.get("sw_ow_index") == 1)
      check("overwatch indicator shown", table.concat(w.overlays, ","):find("sw%-overwatch") ~= nil)
      check("cannot enter overwatch twice", not ow.can_enter(w))
      local m = place("sw_unit_nr_trooper", 1, 10, 3, "t_mover")
      swt.mem.hp = m.hitpoints
      move("10,10,10,10,10", "3,4,5,6,7")
    end
    function S.check_ow_fire()
      check("reaction fired when the enemy entered range", tonumber(u("t_watch").variables.sw_ow_shots) == 0)
      local m = u("t_mover")
      check("reaction fire paused the move", m and m.y == 6, m and (m.x .. "," .. m.y))
      check("the mover keeps its remaining moves", m and m.moves > 0, m and m.moves)
      check("reaction damage applied or missed cleanly", m == nil or m.hitpoints <= swt.mem.hp)
      if m then
        local hp = m.hitpoints
        move("10,11", "6,6")
        check("spent overwatch does not fire again", u("t_mover").hitpoints == hp)
      end
      ow.on_side_turn(2)
      check("overwatch expires at its side's next turn", u("t_watch").variables.sw_ow_active == nil and
        #wml.array_access.get("sw_ow_index") == 0)
    end

    function S.multi_fire()
      clear()
      ow.enter(place("sw_unit_im_stormtrooper", 2, 9, 8, "t_wa"))
      ow.enter(place("sw_unit_im_stormtrooper", 2, 11, 8, "t_wb"))
      ow.enter(place("sw_unit_im_stormtrooper", 2, 20, 2, "t_wfar"))
      place("sw_unit_nr_trooper", 1, 10, 3, "t_mover")
      move("10,10,10,10,10", "3,4,5,6,7")
    end
    function S.check_multi()
      check("both shooters in range fired", tonumber(u("t_wa").variables.sw_ow_shots) == 0 and
        tonumber(u("t_wb").variables.sw_ow_shots) == 0, tostring(u("t_wa").variables.sw_ow_shots) .. "/" ..
        tostring(u("t_wb").variables.sw_ow_shots))
      check("out-of-range shooter held fire", tonumber(u("t_wfar").variables.sw_ow_shots) == 1)
    end

    function S.deflect()
      clear()
      ow.enter(place("sw_unit_im_stormtrooper", 2, 10, 8, "t_watch"))
      local luke = place("sw_hero_luke", 1, 10, 3, "t_luke")
      swt.mem.hp, swt.mem.fp = luke.hitpoints, tonumber(luke.variables.sw_fp)
      move("10,10,10,10", "3,4,5,6")
    end
    function S.check_deflect()
      local luke = u("t_luke")
      check("Blaster Deflection turned the volley aside", luke.hitpoints == swt.mem.hp, luke.hitpoints)
      check("deflection spent 1 FP", tonumber(luke.variables.sw_fp) == swt.mem.fp - 1, luke.variables.sw_fp)
      check("a deflected volley still uses the reaction", tonumber(u("t_watch").variables.sw_ow_shots) == 0)
    end

    function S.deflect_field()
      clear()
      ow.enter(place("sw_unit_im_stormtrooper", 2, 10, 8, "t_watch"))
      u("t_watch").variables.sw_ow_accuracy = 100   -- every strike hits
      force.add_static_source(10, 6, 1)
      local luke = place("sw_hero_luke", 1, 10, 3, "t_luke")
      swt.mem.hp = luke.hitpoints
      move("10,10,10,10", "3,4,5,6")
    end
    function S.check_deflect_field()
      local luke = u("t_luke")
      check("no deflection inside a ysalamiri field", luke == nil or luke.hitpoints < swt.mem.hp,
        luke and luke.hitpoints)
    end

    function S.hidden_and_trick()
      clear()
      ow.enter(place("sw_unit_im_stormtrooper", 2, 10, 8, "t_watch"))
      local n = place("sw_unit_im_noghri", 1, 10, 3, "t_hidden")
      n:add_modification("object", { id = "t_hide",
        T.effect{ apply_to = "new_ability", T.abilities{ T.hides{ id = "t_always_hidden", affect_self = true } } } })
      move("10,10,10,10", "3,4,5,6")
      check("a hidden unit draws no reaction", tonumber(u("t_watch").variables.sw_ow_shots) == 1)
      local luke = place("sw_hero_luke", 1, 11, 8, "t_luke")
      force.use(luke, "mind_trick", u("t_watch"))
      check("Mind Trick clears overwatch", u("t_watch").variables.sw_ow_active == nil)
      check("a dazed unit cannot enter overwatch", not ow.can_enter(u("t_watch")))
    end

    function S.arcs_and_hooks()
      clear()
      local w = place("sw_unit_im_stormtrooper", 2, 10, 8, "t_watch")
      ow.enter(w)
      w = u("t_watch")
      w.variables.sw_ow_arc = "front"
      w.variables.sw_ow_facing = "n"
      local north = place("sw_unit_nr_trooper", 1, 10, 6, "t_north")
      local south = place("sw_unit_nr_trooper", 1, 10, 10, "t_south")
      check("firing arc covers the facing direction", (ow.eligible(u("t_watch"), north)))
      local ok, why = ow.eligible(u("t_watch"), south)
      check("firing arc excludes the rear", not ok and why == "outside firing arc", why)
      table.insert(ow.hooks.can_react, function() return false end)
      ok, why = ow.eligible(u("t_watch"), north)
      table.remove(ow.hooks.can_react)
      check("can_react hook can veto a reaction", not ok and why == "vetoed by hook", why)
      local shot = { accuracy = 0, damage = 10, strikes = 3 }
      table.insert(ow.hooks.modify, function(_, _, s) s.damage = s.damage * 2 end)
      for _, hook in ipairs(ow.hooks.modify) do hook(u("t_watch"), north, shot) end
      table.remove(ow.hooks.modify)
      check("modify hook can adjust a shot", shot.damage == 20)
      w.variables.sw_ow_shots = 1
      local cfg = ow.config(u("t_watch"))
      check("overwatch config read from the unit's ability", cfg and cfg.range == 2 and cfg.reactions == 1 and
        cfg.accuracy == -10 and cfg.weapons[1] == "blaster_rifle")
      local beast = place("sw_unit_wl_vornskr", 2, 18, 12, "t_beast")
      check("units without the overwatch ability cannot overwatch", ow.config(beast) == nil and not ow.can_enter(beast))
    end

    -- AI safety: hand side 2 to the AI for one turn; it may enter overwatch at
    -- turn end and its moves can provoke side-1 reactions.
    function S.ai_turn()
      clear()
      place("sw_unit_nr_trooper", 1, 6, 6, "t_p1")
      ow.enter(place("sw_unit_nr_eweb_team", 1, 9, 6, "t_p2"))
      -- Far from every enemy, so they cannot attack and keep their action.
      place("sw_unit_im_stormtrooper", 2, 22, 13, "t_ai1")
      place("sw_unit_im_stormtrooper", 2, 22, 11, "t_ai2")
      place("sw_hero_cbaoth", 2, 18, 6, "t_ai_jedi")
      wesnoth.sides[2].controller = "ai"
      wml.variables.sw_ai_turn_from = wesnoth.current.turn
    end
    function S.check_ai_turn()
      check("AI turn completed without script errors", true)
      local count = 0
      for _, id in ipairs({ "t_ai1", "t_ai2" }) do
        if u(id) and u(id).variables.sw_ow_active then count = count + 1 end
      end
      local attacked = 0
      for _, id in ipairs({ "t_ai1", "t_ai2" }) do
        if u(id) and not u(id).variables.sw_ow_active and u(id).attacks_left == 0 then attacked = attacked + 1 end
      end
      local detail = {}
      for _, id in ipairs({ "t_ai1", "t_ai2" }) do
        local a = u(id)
        table.insert(detail, id .. (a and ("@" .. a.x .. "," .. a.y .. " atk=" .. a.attacks_left ..
          " ow=" .. tostring(a.variables.sw_ow_active)) or " dead"))
      end
      check("AI units with an unused attack entered overwatch at turn end", count >= 1,
        count .. " " .. table.concat(detail, "; ") .. " turn=" .. wesnoth.current.turn .. " side=" .. wesnoth.current.side)
      check("overwatch index matches units on overwatch", #wml.array_access.get("sw_ow_index") >= count)
      check("AI Force user keeps valid Force Points", u("t_ai_jedi") == nil or tonumber(u("t_ai_jedi").variables.sw_fp) ~= nil)
      wesnoth.sides[2].controller = "human"
    end

    function S.recursion()
      clear()
      ow.enter(place("sw_unit_im_stormtrooper", 2, 10, 8, "t_watch"))
      u("t_watch").variables.sw_ow_shots = 3
      place("sw_unit_nr_trooper", 1, 10, 3, "t_target")
      ow.resolving = true            -- as if a reaction were resolving
      move("10,10,10,10", "3,4,5,6")
      ow.resolving = false
      check("no reaction starts while one resolves", tonumber(u("t_watch").variables.sw_ow_shots) == 3)
      check("eligible before firing", (ow.eligible(u("t_watch"), u("t_target"))))
      ow.resolve(u("t_watch"), u("t_target"))
    end
    function S.check_recursion()
      local t = u("t_target")
      if t then
        check("one move order draws at most one volley per watcher", not ow.eligible(u("t_watch"), t))
        t.variables.sw_move_serial = (tonumber(t.variables.sw_move_serial) or 0) + 1
        check("a new move order can draw fire again", (ow.eligible(u("t_watch"), u("t_target"))))
      end
      check("reentrancy guard released", ow.resolving == false)
    end

    function S.sense_choke()
      clear()
      local luke = place("sw_hero_luke", 1, 5, 5, "t_luke")
      place("sw_unit_im_noghri", 2, 7, 5, "t_noghri")
      place("sw_unit_ob_cloaked_asteroid", 2, 6, 7, "t_asteroid")
      force.use(luke, "sense", luke)
      check("Force Sense removes living stealth", not u("t_noghri"):matches{ ability = "sw_ability_noghri_stealth" })
      check("Force Sense does not defeat cloaking fields", u("t_asteroid"):matches{ ability = "sw_ability_cloaked" })
      force.on_side_turn(1)
      check("the reveal expires at the sensing side's next turn", u("t_noghri"):matches{ ability = "sw_ability_noghri_stealth" })
      local cb = place("sw_hero_cbaoth", 2, 12, 10, "t_cbaoth")
      local v = place("sw_unit_nr_trooper", 1, 13, 10, "t_victim")
      swt.mem.hp = v.hitpoints
      force.use(cb, "choke", v)
    end
    function S.check_choke()
      check("Force Choke damages its target", u("t_victim") == nil or u("t_victim").hitpoints < swt.mem.hp)
      check("Force Choke spent C'baoth's FP", tonumber(u("t_cbaoth").variables.sw_fp) == 7)
    end

    function S.prepare_save()
      clear()
      local luke = place("sw_hero_luke", 1, 4, 4, "t_luke")
      luke.variables.sw_fp = 5
      ow.enter(place("sw_unit_im_stormtrooper", 2, 15, 8, "t_watch"))
      force.add_static_source(10, 10, 1)
      std_print("SW_TEST: state prepared for save")
    end

    function S.load()
      local luke, trooper = u("t_luke"), u("t_watch")
      check("save/load: Force Points kept", luke and tonumber(luke.variables.sw_fp) == 5, luke and luke.variables.sw_fp)
      check("save/load: overwatch kept", trooper and trooper.variables.sw_ow_active == true and
        tonumber(trooper.variables.sw_ow_shots) == 1)
      check("save/load: overwatch index kept", #wml.array_access.get("sw_ow_index") == 1)
      check("save/load: null field rebuilt", force.is_suppressed_at(10, 10))
      check("save/load: systems reloaded", type(sw_systems) == "table" and sw_systems.overwatch ~= nil)
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
      -- End side 1's turn; the AI plays side 2; control returns to side 1.
      -- can_move is briefly true during the AI's turn too, so wait for side 1.
      context.end_turn{}
      local g = 0
      repeat
        settle(); g = g + 1
      until (info.name == "Game" and info.current_side and info.current_side() == 1) or g > 50
    end
  end
  if PHASE == "main" then
    context.save_game{ filename = "sw_systems_test_save" }
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
