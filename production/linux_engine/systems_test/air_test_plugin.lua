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
  "move_sounds", "rank_promotion", "rank_amla", "rank_abilities", "safe_backstab", "air_basics", "air_accuracy", "air_ecm_origin", "air_ecm_ai", "check_air_ecm_ai", "air_strafe", "check_strafe",
  "air_bombing", "land_bombing", "check_bombing", "scripted", "check_scripted", "carryover",
  "ai_avoid", "check_ai_avoid", "ai_air", "check_ai_air", "weapon_ranges", "space_evasion", "kill_xp", "ability_review", "achievements", "bonus_objectives", "command_decisions", "flanking", "ai_ranged_legality", "ai_ranged", "check_ai_ranged",
  "ai_target_priority", "ai_ow_path_rules", "ai_ow_path", "check_ai_ow_path", "ai_withdraw_rules", "ai_withdraw", "check_ai_withdraw",
  "alert_rules", "alert_sneak", "alert_takedown", "alert_ai", "check_alert_ai", "alert_sight", "check_alert_sight", "hero_withdraw", "check_hero_withdraw",
  "myneyrshi_medic_ranks", "myneyrshi_medic_recruit_setup", "myneyrshi_medic_recruit_check",
  "myneyrshi_medic_move_setup", "myneyrshi_medic_move_check", "myneyrshi_medic_heal_setup", "myneyrshi_medic_enemy_turn", "myneyrshi_medic_heal_check",
  "myneyrshi_medic_upgrade_setup", "myneyrshi_medic_upgrade_enemy_turn", "myneyrshi_medic_upgrade_check", "wookiee_ranks", "wookiee_recruit_setup", "wookiee_recruit_check", "wookiee_normal", "wookiee_check_normal",
  "wookiee_aimed", "wookiee_check_hit", "wookiee_target_turn", "wookiee_check_return", "wookiee_expiry",
  "wookiee_miss", "wookiee_check_miss", "muzzle_flashes", "attack_range", "prepare_save",
}
local END_TURN_AFTER = { air_ecm_ai = true, ai_avoid = true, ai_air = true, ai_ranged = true, ai_ow_path = true, ai_withdraw = true, alert_ai = true }

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
    -- Record the sounds an air strike plays (sw_air.lua air.play).
    function swt.record_air_sounds()
      swt.mem.air_sounds, swt.mem.real_air_play = {}, swt.mem.real_air_play or air.play
      air.play = function(sound) table.insert(swt.mem.air_sounds, sound) end
    end
    function swt.stop_air_sounds()
      air.play = swt.mem.real_air_play or air.play
      return swt.mem.air_sounds or {}
    end
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
      local sw_options
      if #u.advances_to == 0 then
        -- Rank checks expect the core +3 HP AMLA. Native advancement opens a
        -- dialog for multiple choices even with animate=false (installed
        -- actions/advancement.cpp); offer its unchanged default config only.
        sw_options = u.advancements
        local sw_default
        for _i, sw_option in ipairs(sw_options) do
          if sw_option.id == "amla_default" then sw_default = sw_option; break end
        end
        assert(sw_default, "rank fixture requires native amla_default for " .. id)
        u.advancements = { sw_default }
      end
      u.experience = u.max_experience
      u:advance(false, true)
      u = assert(wesnoth.units.get(id), "native advancement lost rank-test unit " .. id)
      if sw_options then
        -- Restore terminal choices after rank variations rebuild the unit.
        -- Never restore a pre-promotion list onto the newly promoted type.
        u.advancements = sw_options
        local sw_restored = u.advancements
        local sw_complete = #sw_restored == #sw_options
        for sw_index, sw_option in ipairs(sw_options) do
          sw_complete = sw_complete and sw_restored[sw_index].id == sw_option.id
        end
        swt.check("rank fixture restores every terminal AMLA option (" .. id .. ")", sw_complete)
      end
      return u
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
    -- Engine sounds for moves that start out of view (lua/sw_move_sound.lua).
    function S.move_sounds()
      swt.clear()
      local ms = sw_systems.move_sound
      check("a speeder's take-off sound is read from its type", ms.sound_of("sw_unit_im_scout_trooper") == "sw-move-speeder.wav",
        tostring(ms.sound_of("sw_unit_im_scout_trooper")))
      check("infantry have no engine sound", ms.sound_of("sw_unit_nr_trooper") == nil)
      local played, real_play = {}, ms.play
      ms.play = function(sound) table.insert(played, sound) end
      local sp = swt.place("sw_unit_im_scout_trooper", 2, 3, 3, "t_ms_sp")
      ms.finish(sp)
      ms.step(sp, false, false)
      check("out of view at the start and still unseen: silent", #played == 0)
      ms.step(sp, false, true)
      check("comes into view: the engine sound plays", #played == 1 and played[1] == "sw-move-speeder.wav", table.concat(played, ","))
      ms.step(sp, false, true)
      check("only once per move", #played == 1)
      ms.finish(sp)
      ms.step(sp, true, true)
      check("a move that starts in view is left to the take-off animation", #played == 1)
      ms.finish(sp)
      local own = swt.place("sw_unit_im_scout_trooper", 1, 5, 3, "t_ms_own")
      swt.move_to("t_ms_own", 5, 7)
      check("a real move of a visible speeder adds no second sound", #played == 1, #played)
      ms.play = real_play
      -- Air sorties fly the craft's hidden flyover variation; its take-off is
      -- silent because sw_air.lua plays the engine sound itself.
      local function takeoff_sound(cfg)
        local anim = wml.get_child(cfg, "pre_movement_anim")
        local f = anim and wml.get_child(anim, "frame")
        return f and f.sound
      end
      local xw = wesnoth.unit_types.sw_unit_nr_xwing
      check("an X-wing's own take-off keeps its engine sound", takeoff_sound(xw.__cfg) == "sw-move-fighter.wav",
        tostring(takeoff_sound(xw.__cfg)))
      local fly = xw.variations and xw.variations.sw_flyover
      local quiet = fly and takeoff_sound(fly.__cfg)
      check("the flyover variation takes off silently", fly ~= nil and (quiet == nil or quiet == ""), tostring(quiet))
      swt.clear()
    end

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
      -- Rank designs: at rank II and III a type with redrawn art switches to
      -- variation rank2 / rank3 (lua/sw_rank.lua); a hero disarmed by the
      -- story (variation "unarmed") keeps that look.
      local with_designs = {}
      for ty, entry in pairs(rank.DATA) do
        if entry.designs and #entry.designs > 0 then table.insert(with_designs, ty) end
      end
      table.sort(with_designs)
      local design_type = with_designs[1]
      if design_type then
        local d = swt.place(design_type, 1, 13, 7, "t_design")
        check("below rank II the base design is worn", rank.of(d) >= 2 or d.variation == "")
        for _i = 1, 3 do
          if rank.of(d) >= 2 then break end
          d = swt.level_up("t_design")
        end
        local want = rank.DATA[design_type].designs[1] == 2 and "rank2" or ""
        check("rank II wears its redrawn design (" .. design_type .. ")", d.variation == want, d.variation)
        check("the design keeps the rank insignia", tostring(d.image_mods):find("sw%-rank%-") ~= nil)
      else
        check("rank designs: no type has redrawn rank art yet", true)
      end
      local v = swt.place("sw_unit_wl_vornskr", 3, 11, 5, "t_vor")
      local vhp = v.max_hitpoints
      v = swt.level_up("t_vor")
      check("creatures gain the AMLA but wear no insignia", v.max_hitpoints == vhp + 3 and not tostring(v.image_mods):find("sw%-rank"))
    end

    -- Shipped base backstab: core identity, all directions and negative cases.
    function S.safe_backstab()
      swt.clear()
      local opposite={n="s",s="n",ne="sw",sw="ne",se="nw",nw="se"}
      local directions={"n","ne","se","s","sw","nw"}
      local victim=swt.place("sw_unit_nr_trooper",2,12,8,"t_bs_victim")
      local function loc(dir)
        local p=wesnoth.map.get_direction({12,8},dir)
        return p.x or p[1],p.y or p[2]
      end
      for _,profile in ipairs{{type="sw_unit_im_noghri"},{type="sw_hero_khabarakh"},
        {type="sw_hero_khabarakh",variation="rank2"},{type="sw_hero_khabarakh",variation="rank3"},
        {type="sw_unit_im_infiltrator"}} do
        local label=profile.type.."/"..(profile.variation or "base")
        wesnoth.wml_actions.unit{type=profile.type,variation=profile.variation,side=1,x=12,y=7,
          id="t_bs_attacker",random_traits=false,generate_name=false}
        local actor=u("t_bs_attacker")
        local special,count=nil,0
        for _,sp in ipairs(actor.attacks[1].specials) do
          if sp[1]=="damage" and sp[2].id=="backstab" then special=sp[2];count=count+1 end
        end
        local filter=special and wml.get_child(special,"filter_opponent")
        check(label.." exactly one native offense-only double-damage backstab",
          count==1 and special.multiply==2 and special.active_on=="offense")
        check(label.." absent secondary opponent safely fails filter",filter and not victim:matches(filter))
        for _,dir in ipairs(directions) do
          local ax,ay=loc(opposite[dir]);local bx,by=loc(dir)
          actor:to_map(ax,ay);actor.facing=dir
          local _,_,solo=wesnoth.simulate_combat(actor,1,victim)
          check(label.." empty opposite "..dir.." preserves base damage",solo.damage==actor.attacks[1].damage)
          local f=swt.place("sw_unit_nr_trooper",1,bx,by,"t_bs_flanker")
          local _,_,flank=wesnoth.simulate_combat(actor,1,victim)
          check(label.." hostile opposite "..dir.." doubles knife damage",flank.damage==2*solo.damage)
          check(label.." armed flanker "..dir.." retains independent accuracy",flank.chance_to_hit==solo.chance_to_hit+10)
          f.status.petrified=true
          local _,_,stone=wesnoth.simulate_combat(actor,1,victim)
          check(label.." petrified opposite "..dir.." gives no bonus",
            stone.damage==solo.damage and stone.chance_to_hit==solo.chance_to_hit)
          f.status.petrified=false;f.side=2
          local _,_,friendly=wesnoth.simulate_combat(actor,1,victim)
          check(label.." target ally opposite "..dir.." gives no backstab",friendly.damage==solo.damage)
          f.side=1
          f:add_modification("object",{id="sw_test_backstab_unarmed",T.effect{apply_to="remove_attacks"}})
          check(label.." unarmed fixture "..dir.." has no native attacks",#f.attacks==0)
          local _,_,unarmed=wesnoth.simulate_combat(actor,1,victim)
          check(label.." unarmed hostile opposite "..dir.." retains native damage bonus",
            unarmed.damage==2*solo.damage and unarmed.chance_to_hit==solo.chance_to_hit)
          f:erase()
          local wrong
          for _,d in ipairs(directions) do if d~=dir and d~=opposite[dir] then wrong=d;break end end
          local wx,wy=loc(wrong)
          f=swt.place("sw_unit_nr_trooper",1,wx,wy,"t_bs_wrong")
          local _,_,offaxis=wesnoth.simulate_combat(actor,1,victim)
          check(label.." off-axis hostile "..dir.." does not double damage",offaxis.damage==solo.damage)
          f:erase()
          f=swt.place("sw_unit_nr_trooper",1,bx,by,"t_bs_defense_support")
          local _,_,_,defense=wesnoth.simulate_combat(victim,1,actor,1)
          check(label.." return fire "..dir.." keeps ordinary knife damage",defense.damage==actor.attacks[1].damage)
          f:erase()
        end
        actor:erase()
      end
      swt.clear()
    end

    -- Rank abilities (lua/sw_rank_abilities.lua, production/tools/rank_abilities.py).
    function S.rank_abilities()
      swt.clear()
      local function idx(u, name)
        for i, a in ipairs(u.attacks) do if a.name == name then return i end end
      end
      local function has_special(u, weapon, id)
        local a = u.attacks[idx(u, weapon)]
        for _i, sp in ipairs(a and a.specials or {}) do
          if sp[2] and sp[2].id == id then return true end
        end
        return false
      end
      local function cth(att, name, def)
        local _a, _d, aw = wesnoth.simulate_combat(att, idx(att, name), def)
        return aw.chance_to_hit
      end
      -- Promotion: a sergeant earns its rank I ability with the stripes.
      swt.place("sw_unit_nr_trooper", 1, 3, 3, "t_ra_tr")
      local sgt = swt.level_up("t_ra_tr")
      check("promoted sergeant earns fire discipline (rank I)", sgt:matches{ ability = "sw_rank_hit_aura" }
        and tonumber(sgt.variables.sw_rank_ability) == 1, sgt.variables.sw_rank_ability)
      -- Fire discipline: adjacent allies +10% to hit with ranged attacks, not melee.
      local tr = swt.place("sw_unit_nr_trooper", 1, 5, 8, "t_ra_ally")
      local st = swt.place("sw_unit_im_stormtrooper", 2, 6, 8, "t_ra_enemy")
      local ranged0, melee0 = cth(tr, "blaster_rifle", st), cth(tr, "rifle_butt", st)
      sgt:to_map(4, 8)
      check("fire discipline: adjacent ally +10% ranged", cth(tr, "blaster_rifle", st) == ranged0 + 10,
        ranged0 .. " -> " .. cth(tr, "blaster_rifle", st))
      check("fire discipline does not touch melee", cth(tr, "rifle_butt", st) == melee0)
      -- AMLA ranks: commando I ambush, II backstab on its knife, III saboteur on its carbine.
      local c = swt.place("sw_unit_nr_commando", 1, 3, 12, "t_ra_cmd")
      local attacks0 = #c.attacks
      c = swt.level_up("t_ra_cmd")
      check("commando rank I: jungle fighter (hides in forest)", c:matches{ ability = "sw_rank_hides" })
      c = swt.level_up("t_ra_cmd")
      check("commando rank II: knife work on the vibroknife", has_special(c, "vibroknife", "sw_rank_backstab"))
      c = swt.level_up("t_ra_cmd")
      check("commando rank III: saboteur on the carbine and its aimed shot",
        has_special(c, "blaster_carbine", "sw_rank_bane") and
        (idx(c, "blaster_carbine_aimed") == nil or has_special(c, "blaster_carbine_aimed", "sw_rank_bane")))
      check("rank abilities add no attacks", #c.attacks == attacks0, attacks0 .. " -> " .. #c.attacks)
      -- Knife work doubles knife damage with an ally behind the target.
      local tx, ty = 15, 12
      local above = wesnoth.map.get_direction({ tx, ty }, "n")
      local behind = wesnoth.map.get_direction({ tx, ty }, "s")
      local ax, ay = above.x or above[1], above.y or above[2]
      local bx, by = behind.x or behind[1], behind.y or behind[2]
      local victim = swt.place("sw_unit_im_stormtrooper", 2, tx, ty, "t_ra_victim")
      c:to_map(ax, ay)
      c.facing = "s"
      local _a1, _d1, solo = wesnoth.simulate_combat(c, idx(c, "vibroknife"), victim)
      swt.place("sw_unit_nr_trooper", 1, bx, by, "t_ra_flank")
      local _a2, _d2, flanked = wesnoth.simulate_combat(c, idx(c, "vibroknife"), victim)
      check("knife work: double damage with an ally behind the target", flanked.damage >= 2 * solo.damage - 1,
        solo.damage .. " -> " .. flanked.damage)
      c = swt.level_up("t_ra_cmd")
      sw_systems.rank.update(c)
      check("each rank ability is granted once (no duplicates past rank III or on update)",
        swt.objects(c, "sw_rank_ability_1") == 1 and swt.objects(c, "sw_rank_ability_3") == 1)
      -- Field surgery replaces heals +4 with heals +8.
      swt.place("sw_unit_nr_field_medic", 1, 9, 12, "t_ra_med")
      local med = swt.level_up("t_ra_med")
      local heals = {}
      for _i, h in ipairs(wml.child_array(wml.get_child(med.__cfg, "abilities") or {}, "heals")) do
        table.insert(heals, h.value)
      end
      check("medic rank I: one heals ability, now +8", #heals == 1 and tonumber(heals[1]) == 8, table.concat(heals, ","))
      -- Battle roar: adjacent enemies -10% to hit.
      local w = swt.place("sw_unit_wk_warrior", 1, 11, 8, "t_ra_wk")
      local foe = swt.place("sw_unit_im_stormtrooper", 2, 12, 8, "t_ra_foe")
      local mark = swt.place("sw_unit_nr_trooper", 1, 13, 8, "t_ra_mark")
      local foe0 = cth(foe, "blaster_rifle", mark)
      w = swt.level_up("t_ra_wk")
      check("Wookiee warrior rank I: battle roar, adjacent enemies -10%", cth(foe, "blaster_rifle", mark) == foe0 - 10,
        foe0 .. " -> " .. cth(foe, "blaster_rifle", mark))
      -- Every assigned weapon special exists on that unit type (generator asserts; spot-check the data).
      local ok = true
      for ty, ranks in pairs(sw_systems.rank.ABILITIES) do
        if not wesnoth.unit_types[ty] then ok = false end
        for r = 1, 3 do if not (ranks[r] and ranks[r].effects and #ranks[r].effects > 0) then ok = false end end
      end
      check("every listed type has abilities for ranks I-III", ok)
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


    -- The radius array is sorted for deterministic effects. Its first cell
    -- must never stand in for the selected bombing target.
    function S.air_ecm_origin()
      for _, loc in ipairs{ {8,8}, {9,8}, {8,9}, {9,9} } do
        swt.clear()
        local x,y = loc[1],loc[2]
        local label = "bombing ECM " .. x .. "," .. y
        local obs = swt.place("sw_unit_nr_sergeant",1,x-4,y,"sw_test_ecm_obs")
        local jammer = swt.place("sw_unit_im_stormtrooper",2,x,y,"sw_test_ecm_jam")
        ew.set_profile(obs,{eccm=0})
        ew.set_profile(jammer,{ecm=2,ecm_range=0})
        local area = air.area("bombing",obs,x,y)
        check(label .. ": footprint remains seven sorted cells", #area==7 and area[1].x==x-1)
        check(label .. ": selected target carries separate metadata", area.target and area.target.x==x and area.target.y==y)
        local terms = air.preview(1,"bombing",obs,x,y).terms
        check(label .. ": target-only jammer applies 20", terms.jamming==20 and terms.total==-10,terms.jamming)
        check(label .. ": strafing retains target ECM", air.preview(1,"strafe",obs,x,y).terms.jamming==20)
        local reversed = {target={x=x,y=y}}
        for i=#area,1,-1 do reversed[#reversed+1]=area[i] end
        check(label .. ": array order cannot change ECM", air.accuracy(1,"bombing",obs,reversed).jamming==20)
        ew.set_profile(obs,{eccm=1})
        check(label .. ": observer ECCM offsets one point", air.preview(1,"bombing",obs,x,y).terms.jamming==10)
        ew.set_profile(obs,{eccm=3})
        check(label .. ": stronger ECCM cannot add accuracy", air.preview(1,"bombing",obs,x,y).terms.jamming==0)
        ew.set_profile(obs,{eccm=0})
        jammer.loc={area[1].x,area[1].y}
        check(label .. ": sorted-edge-only jammer is irrelevant", air.preview(1,"bombing",obs,x,y).terms.jamming==0)
        local legacy = {}
        for _,h in ipairs(area) do legacy[#legacy+1]=h end
        check(label .. ": legacy caller retains first-cell fallback", air.accuracy(1,"bombing",obs,legacy).jamming==20)
        jammer.loc={x-2,y}
        ew.set_profile(jammer,{ecm=2,ecm_range=1})
        check(label .. ": radius1 reaching only edge is irrelevant", air.preview(1,"bombing",obs,x,y).terms.jamming==0)
        ew.set_profile(jammer,{ecm=2,ecm_range=2})
        check(label .. ": range boundary at target still applies", air.preview(1,"bombing",obs,x,y).terms.jamming==20)
        jammer.side=1
        check(label .. ": friendly jamming never penalizes", air.preview(1,"bombing",obs,x,y).terms.jamming==0)
        local aa=swt.place("sw_unit_im_at_st",2,x+3,y,"sw_test_ecm_aa")
        local t=air.preview(1,"bombing",obs,x,y).terms
        check(label .. ": AA reaches blast edge beyond target radius", wesnoth.map.distance_between(x,y,aa.x,aa.y)>2
          and t.anti_air==20 and t.jamming==0 and t.total==-10,t.anti_air)
        check(label .. ": scripted no-observer accuracy has no ECM", air.accuracy(1,"bombing",nil,area).jamming==0)
      end
    end

    function S.air_ecm_ai()
      swt.clear()
      swt.mem.strikes={}
      -- Native defense_on is avoidance, the complement of CFG hit chance.
      -- Equal forest cover keeps only ECM across the unchanged AI threshold.
      swt.mem.ecm_ai_terrain={wesnoth.current.map[{8,8}],wesnoth.current.map[{8,10}]}
      wesnoth.wml_actions.terrain{x=8,y=8,terrain="Gg^Fmf"}
      wesnoth.wml_actions.terrain{x=8,y=10,terrain="Gg^Fmf"}
      wesnoth.sides[2].controller="ai"
      local obs=swt.place("sw_unit_im_stormtrooper_sergeant",2,4,8,"sw_test_ecm_ai_obs")
      local defended=swt.place("sw_unit_nr_trooper",1,8,8,"sw_test_ecm_ai_defended")
      local exposed=swt.place("sw_unit_nr_trooper",1,8,10,"sw_test_ecm_ai_exposed")
      obs.moves=0;defended.attacks_left=0;exposed.attacks_left=0
      ew.set_profile(obs,{eccm=0})
      ew.set_profile(defended,{ecm=2,ecm_range=0})
      ew.set_profile(exposed,{ecm=0})
      air.grant(2,"bombing",1,"sw_unit_im_tie_bomber")
      check("AI bomb fixture: both targets have native forest defense50",
        defended:defense_on(wesnoth.current.map[{8,8}])==50
        and exposed:defense_on(wesnoth.current.map[{8,10}])==50)
      local a=air.preview(2,"bombing",obs,8,8)
      local b=air.preview(2,"bombing",obs,8,10)
      check("AI bomb fixture: equal cover, defended target below sortie threshold", a.terms.jamming==20 and b.terms.jamming==0
        and a.enemy_damage<8 and b.enemy_damage>=8,a.enemy_damage .. "/" .. b.enemy_damage)
    end
    function S.check_air_ecm_ai()
      local queued=wml.array_access.get("sw_air_inbound")
      check("ordinary AI turn bombs exposed target instead of jammed target", #queued==1 and tonumber(queued[1].side)==2
        and tonumber(queued[1].x)==8 and tonumber(queued[1].y)==10)
      check("ordinary AI air decision spends one sortie and observer attack", air.charges(2,"bombing")==0
        and u("sw_test_ecm_ai_obs").attacks_left==0)
      wesnoth.wml_actions.terrain{x=8,y=8,terrain=swt.mem.ecm_ai_terrain[1]}
      wesnoth.wml_actions.terrain{x=8,y=10,terrain=swt.mem.ecm_ai_terrain[2]}
      swt.mem.ecm_ai_terrain=nil
      -- Clear only this test's public markers before the next isolated case.
      for _,strike in ipairs(queued) do
        local xs,ys=core.split(strike.xs),core.split(strike.ys)
        for i=1,#xs do wesnoth.interface.remove_item(tonumber(xs[i]),tonumber(ys[i]),"sw_air_inbound|" .. strike.id) end
      end
      wml.array_access.set("sw_air_inbound",{})
      wesnoth.sides[2].controller="human"
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
      swt.record_air_sounds()
      swt.mem.call = air.call(1, "strafe", obs, 8, 8)
    end
    function S.check_strafe()
      local heard = swt.stop_air_sounds()
      check("strafing run: guns, then one engine pass, then a bolt impact every other hex",
        table.concat(heard, ",") == "sw-laser-cannon.wav,sw-move-fighter.wav,sw-laser-hit.wav,sw-laser-hit.wav",
        table.concat(heard, ","))
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
      swt.record_air_sounds()
      air.on_side_turn(1)
    end
    function S.check_bombing()
      local heard = swt.stop_air_sounds()
      local booms = "sw-explosion.wav,sw-torpedo-hit.wav,sw-death-vehicle.wav"
      check("bombing run: one starfighter pass, no torpedo launch",
        heard[1] == "sw-move-fighter.wav" and not table.concat(heard, ","):find("sw%-torpedo%.wav"), table.concat(heard, ","))
      check("bombs: three staggered explosions over seven hexes, not seven at once",
        #heard == 4 and heard[2] == booms and heard[3] == booms and heard[4] == booms, table.concat(heard, " | "))
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

    -- Space combat review 2026-10-16: lore evasion ratings (per-unit
    -- [defense] overrides of sw_starfighter), unguided and anti-ship
    -- ordnance, astromech repairs and the A-wing's pursuit (skirmisher).
    -- defense_on is avoidance; Qsp open space, Qsa asteroids, Qsd deck.
    function S.space_evasion()
      swt.clear()
      local function idx(u, name)
        for i, a in ipairs(u.attacks) do if a.name == name then return i end end
      end
      local function dmg(att, name, def)
        local _a, _d, aw = wesnoth.simulate_combat(att, idx(att, name), def)
        return aw.damage
      end
      local aw = swt.place("sw_unit_nr_awing", 1, 12, 4, "t_aw")
      local xw = swt.place("sw_unit_nr_xwing", 1, 12, 6, "t_xw")
      local yw = swt.place("sw_unit_nr_ywing", 1, 12, 8, "t_yw")
      local tf = swt.place("sw_unit_im_tie_fighter", 2, 14, 4, "t_tf")
      local ti = swt.place("sw_unit_im_tie_interceptor", 2, 14, 6, "t_ti")
      local tb = swt.place("sw_unit_im_tie_bomber", 2, 13, 6, "t_tb")
      local sd = swt.place("sw_unit_im_star_destroyer", 2, 13, 8, "t_sd")
      local function ev(u) return u:defense_on("Qsp") end
      check("evasion in open space: A-wing 65, TIE Interceptor 65, TIE fighter 55, X-wing 50, Y-wing 35, TIE bomber 35, Star Destroyer 10",
        ev(aw) == 65 and ev(ti) == 65 and ev(tf) == 55 and ev(xw) == 50 and ev(yw) == 35 and ev(tb) == 35 and ev(sd) == 10,
        table.concat({ev(aw), ev(ti), ev(tf), ev(xw), ev(yw), ev(tb), ev(sd)}, ","))
      check("asteroids add 10% up to the 70% cap, decks take 10% away",
        aw:defense_on("Qsa") == 70 and yw:defense_on("Qsa") == 45 and aw:defense_on("Qsd") == 55 and xw:defense_on("Qsd") == 40,
        aw:defense_on("Qsa") .. "," .. yw:defense_on("Qsa") .. "," .. aw:defense_on("Qsd") .. "," .. xw:defense_on("Qsd"))
      check("the rating is listed as an ability", aw:matches{ ability = "sw_ability_evasion" } and sd:matches{ ability = "sw_ability_evasion" })
      -- TIE bomber concussion bombs 16: half against craft (X-wing impact 90%: 16*0.5*0.9=7.2 -> 7), +50% against
      -- capital ships (Y-wing torpedoes 16*1.5 vs Star Destroyer impact 70% = 16.8 -> 17).
      tb:to_map(13, 6)
      check("unguided bombs: half damage against a starfighter", dmg(tb, "concussion_bombs", xw) == 7, dmg(tb, "concussion_bombs", xw))
      check("anti-ship torpedoes: +50% against a capital ship", dmg(yw, "proton_torpedoes", sd) == 17, dmg(yw, "proton_torpedoes", sd))
      check("X-wing and Y-wing carry astromech droids; the A-wing and TIEs do not",
        xw:matches{ ability = "sw_ability_astromech" } and yw:matches{ ability = "sw_ability_astromech" }
        and not aw:matches{ ability = "sw_ability_astromech" } and not tf:matches{ ability = "sw_ability_astromech" })
      check("the A-wing slips past escorts (skirmisher) and carries concussion missiles",
        aw:matches{ ability = "skirmisher" } and idx(aw, "concussion_missiles") ~= nil)
      check("hero X-wings cost 40 and dodge 60%",
        wesnoth.unit_types["sw_hero_wedge"].cost == 40 and wesnoth.unit_types["sw_hero_xwing_luke"].cost == 40
        and swt.place("sw_hero_wedge", 1, 10, 10, "t_wedge"):defense_on("Qsp") == 60)
    end

    -- Kill experience scales with the victim's toughness (lua/sw_xp.lua):
    -- engine 8 x level, plus 1 XP per 4 HP above 22 + 14 x level.
    function S.kill_xp()
      swt.clear()
      local xpm = sw_systems.xp
      local st = swt.place("sw_unit_im_stormtrooper", 2, 14, 4, "t_kx_st")
      local sd = swt.place("sw_unit_im_star_destroyer", 2, 13, 8, "t_kx_sd")
      local gen = swt.place("sw_unit_ob_shield_generator", 2, 16, 8, "t_kx_gen")
      check("a stormtrooper gives no bonus; a Star Destroyer +36; an unarmed set piece none",
        xpm.kill_bonus(st) == 0 and xpm.kill_bonus(sd) == 36 and xpm.kill_bonus(gen) == 0,
        xpm.kill_bonus(st) .. "," .. xpm.kill_bonus(sd) .. "," .. xpm.kill_bonus(gen))
      -- A real attack: Wedge (level 3, 150 XP to advance) finishes a 1-HP Star
      -- Destroyer. The kill pays 32 (8 x level 4) + 36.
      local wedge = swt.place("sw_hero_wedge", 1, 12, 7, "t_kx_wedge")
      wedge.experience = 0
      sd.hitpoints = 1
      local killed = false
      for _try = 1, 4 do
        wedge.attacks_left = 1
        wesnoth.wml_actions.do_command{ T.attack{ T.source{ x = 12, y = 7 }, T.destination{ x = 13, y = 8 }, weapon = 0 } }
        if not wesnoth.units.get("t_kx_sd") then killed = true break end
      end
      wedge = wesnoth.units.get("t_kx_wedge")
      check("destroying a Star Destroyer pays 68 XP, not 32", killed and wedge.experience >= 68,
        tostring(killed) .. " xp=" .. (wedge and wedge.experience or -1))
    end

    -- Flanking (units/00_sw_specials.cfg): +10% to hit per armed unit hostile
    -- to the target on its far side as seen from the attacker, max +20%,
    -- offense only. Engine combat simulation with real unit positions.
    -- Ability review 2026-10-10 (docs/balance/MISSION_BALANCE_REVIEW.md 3.7),
    -- checked with the engine's own combat simulation.
    function S.ability_review()
      swt.clear()
      local function idx(u, name)
        for i, a in ipairs(u.attacks) do if a.name == name then return i end end
      end
      local function dmg(att, name, def)
        local _a, _d, aw = wesnoth.simulate_combat(att, idx(att, name), def)
        return aw.damage
      end
      local st = swt.place("sw_unit_im_stormtrooper", 2, 6, 10, "t_ab_st")
      local ch = swt.place("sw_hero_chewbacca", 1, 5, 10, "t_ab_ch")
      local full = dmg(ch, "wookiee_strength", st)
      ch.hitpoints = math.floor(ch.max_hitpoints / 2) - 1
      local hurt = dmg(ch, "wookiee_strength", st)
      check("Wookiee rage: +25% melee below half hit points", math.abs(hurt - full * 1.25) <= 1 and hurt > full,
        full .. " -> " .. hurt)
      ch.hitpoints = math.ceil(ch.max_hitpoints / 2)
      check("no rage at half hit points or more", dmg(ch, "wookiee_strength", st) == full)
      ch:erase()
      local wk = swt.place("sw_unit_wk_warrior", 1, 5, 10, "t_ab_wk")
      local wfull = dmg(wk, "ryyk_blade", st)
      wk.hitpoints = 5
      check("Wookiee warriors rage too", dmg(wk, "ryyk_blade", st) > wfull)
      local han = swt.place("sw_hero_han", 1, 3, 12, "t_ab_han")
      check("Han Solo is a skirmisher", han:matches{ ability = "skirmisher" })
      st:erase(); wk:erase(); han:erase()
      -- Force hunter: vornskrs strike any Force user (Mara, Leia) harder, not only Luke.
      local v = swt.place("sw_unit_wl_vornskr", 2, 6, 10, "t_ab_v")
      local function vs(type, id)
        local d = swt.place(type, 1, 5, 10, id)
        local value = dmg(v, "fangs", d)
        local res = d:resistance_against("blade")
        d:erase()
        return value, 6 * (100 - res) / 100
      end
      local mara, mara_base = vs("sw_hero_mara", "t_ab_mara")
      local leia, leia_base = vs("sw_hero_leia", "t_ab_leia")
      local hn, han_base = vs("sw_hero_han", "t_ab_han2")
      check("Force hunter applies to Mara (+50%)", math.abs(mara - mara_base * 1.5) <= 1, mara .. " vs " .. mara_base)
      check("Force hunter applies to Leia (+50%)", math.abs(leia - leia_base * 1.5) <= 1, leia .. " vs " .. leia_base)
      check("no Force hunter bonus against a non-Force user", math.abs(hn - han_base) <= 1, hn .. " vs " .. han_base)
    end

    -- Achievement rules (lua/sw_achievements.lua; awarded only in campaign missions).
    function S.achievements()
      local ach = sw_systems.achievements
      check("missions map to their campaign's achievement group",
        ach.campaign_of("sw_hte_01_ysalamiri_harvest") == "Star_Wars_Thrawn_Trilogy"
        and ach.campaign_of("sw_dfr_03_jomark") == "Star_Wars_Thrawn_Trilogy_Dark_Force_Rising"
        and ach.campaign_of("sw_tlc_09_bilbringi") == "Star_Wars_Thrawn_Trilogy_The_Last_Command")
      check("test scenarios earn nothing", ach.campaign_of(wesnoth.scenario.id) == nil, wesnoth.scenario.id)
      check("swift: a third of the turns unused", ach.is_swift(10, 15) and not ach.is_swift(11, 15))
      check("hold-out missions have no swift victory", ach.HOLD_OUT.sw_hte_03_adrift and ach.HOLD_OUT.sw_tlc_02_the_smugglers_council)
      check("each campaign has a final mission", ach.FINALS.sw_hte_10_thrawns_gambit and ach.FINALS.sw_dfr_10_honoghrs_choice
        and ach.FINALS.sw_tlc_10_the_last_command)
      local ok = pcall(ach.feat, "sw_feat_gambit")
      check("a mission feat outside the campaigns is ignored without error", ok)
    end

    -- Bonus objectives (lua/sw_bonus.lua).
    function S.bonus_objectives()
      swt.clear()
      local b = sw_systems.bonus
      local side = wesnoth.sides[1]
      wml.variables.sw_bonus_bank = nil
      -- villages
      b.define("villages", "1", 40)
      check("no village held: not met", not b.met(b.config()))
      local vx, vy = 3, 14
      wesnoth.wml_actions.terrain{ x = vx, y = vy, terrain = "Gg^Vh" }
      if vx then
        wesnoth.map.set_owner(vx, vy, 1)
        check("a village held: met", b.met(b.config()))
        b.on_victory()
        check("victory banks the reward", tonumber(wml.variables.sw_bonus_bank) == 40, wml.variables.sw_bonus_bank)
        b.on_victory()
        check("paid once", tonumber(wml.variables.sw_bonus_bank) == 40)
        wesnoth.map.set_owner(vx, vy, 0)
        wesnoth.wml_actions.terrain{ x = vx, y = vy, terrain = "Gg" }
      end
      -- heroes
      b.define("heroes", "t_bo_han", 40)
      check("a named hero absent: not met", not b.met(b.config()))
      swt.place("sw_hero_han", 1, 5, 5, "t_bo_han")
      check("the named hero present: met", b.met(b.config()))
      b.on_withdraw("t_bo_han")
      check("a withdrawal loses it", b.config().failed == true and not b.met(b.config()))
      -- undetected
      b.define("undetected", "-", 50)
      check("no alarm: met", b.met(b.config()))
      b.on_alarm()
      check("an alarm loses it", not b.met(b.config()))
      -- payment needs a side that can recruit
      local gold, recruit = side.gold, side.recruit
      wml.variables.sw_bonus_bank = 40     -- as banked by a won mission
      side.recruit = {}
      b.on_start()
      check("no recruiting: the bank waits", tonumber(wml.variables.sw_bonus_bank) == 40 and side.gold == gold)
      side.recruit = { "sw_unit_nr_trooper" }
      swt.place("sw_unit_nr_sergeant", 1, 7, 5, "t_bo_leader").canrecruit = true
      b.on_start()
      check("recruiting: paid in full", side.gold == gold + 40 and wml.variables.sw_bonus_bank == nil, side.gold - gold)
      side.gold, side.recruit = gold, recruit
      wml.variables.sw_bonus = nil
      -- Mission debrief (lua/sw_debrief.lua): counts and the bonus line.
      local db = sw_systems.debrief
      wml.variables.sw_debrief = nil
      db.on_withdraw("t_bo_han")
      wml.variables.sw_bonus_result = { scenario = wesnoth.scenario.id, state = "complete", gold = 40 }
      local text = db.text()
      check("debrief counts a withdrawal", text:find("Heroes withdrawn: 1") ~= nil, text)
      check("debrief reports the bonus objective", text:find("Bonus objective complete: 40") ~= nil, text)
      check("debrief shows the turn", text:find("Mission complete on turn") ~= nil or (wesnoth.scenario.turns or -1) <= 0)
      wml.variables.sw_bonus_result = { scenario = wesnoth.scenario.id, state = "missed", gold = 40 }
      check("debrief reports a missed bonus", db.text():find("Bonus objective missed") ~= nil)
      -- Campaign totals: each victory adds once.
      wml.variables.sw_campaign_stats = nil
      wml.variables.sw_bonus_result = { scenario = wesnoth.scenario.id, state = "complete", gold = 40 }
      local st = db.record()
      st = db.record()
      check("a mission is added to the campaign totals once", st.missions == 1 and st.bonus == 1 and st.withdrawn == 1,
        st.missions .. "/" .. st.bonus .. "/" .. st.withdrawn)
      local summary = db.campaign_text(db.campaign_stats())
      check("campaign summary lists missions and bonus objectives",
        summary:find("Missions won: 1") ~= nil and summary:find("Bonus objectives earned: 1") ~= nil, summary)
      wml.variables.sw_command = { choice = "counter", scenario = "earlier" }
      summary = db.campaign_text(db.campaign_stats())
      check("campaign summary names the command decision", summary:find("Command decision: Counter%-intelligence") ~= nil, summary)
      wml.variables.sw_command = nil
      wml.variables.sw_bonus_result, wml.variables.sw_debrief, wml.variables.sw_campaign_stats = nil, nil, nil
    end

    -- Command decisions (lua/sw_command.lua).
    function S.command_decisions()
      swt.clear()
      local cmd = sw_systems.command
      local side = wesnoth.sides[1]
      local gold, recruit = side.gold, side.recruit
      wml.variables.sw_command = nil
      side.recruit = { "sw_unit_nr_trooper", "sw_unit_nr_commando" }
      swt.place("sw_unit_nr_sergeant", 1, 7, 5, "t_cd_leader").canrecruit = true
      local best = wesnoth.unit_types.sw_unit_nr_commando.cost >= wesnoth.unit_types.sw_unit_nr_trooper.cost
        and "sw_unit_nr_commando" or "sw_unit_nr_trooper"
      local before = #wesnoth.units.find_on_map{ side = 1, type = best }
      local placed = cmd.decide("cadre")
      local cadre = wesnoth.units.find_on_map{ side = 1, type = best }
      local loyal, half = 0, 0
      for _i, c in ipairs(cadre) do
        if c.upkeep == "loyal" or c.upkeep == 0 then loyal = loyal + 1 end
        if c.experience == math.floor(c.max_experience / 2) then half = half + 1 end
      end
      check("cadre: two units of the best recruit join", placed == 2 and #cadre == before + 2, placed .. " " .. #cadre)
      check("cadre units are loyal and half-way to their next level", loyal >= 2 and half >= 2, loyal .. "/" .. half)
      check("the choice is recorded", cmd.current() == "cadre")
      -- supply: paid at the start of a later mission where the player recruits
      wml.variables.sw_command = { campaign = wml.variables["sw_command.campaign"], choice = "supply", scenario = "earlier" }
      cmd.on_start()
      check("supply convoy: +25 credits at a later start", side.gold == gold + cmd.SUPPLY_GOLD, side.gold - gold)
      side.gold = gold
      side.recruit = {}
      cmd.on_start()
      check("supply convoy: nothing without recruiting", side.gold == gold, side.gold - gold)
      side.recruit = { "sw_unit_nr_trooper" }
      wml.variables["sw_command.scenario"] = wesnoth.scenario.id
      cmd.on_start()
      check("supply convoy: not paid in the mission where it was chosen", side.gold == gold, side.gold - gold)
      -- counter-intelligence: caps every enabled doctrine side
      local doctrine = sw_systems.doctrine
      local d = doctrine.load(2) or doctrine.enable(2)
      local cap = d.cap
      wml.variables.sw_command = nil
      cmd.decide("counter")
      check("counter-intelligence caps Thrawn's insight at 75", doctrine.load(2).cap == cmd.COUNTER_CAP, doctrine.load(2).cap)
      check("the cap is below the top tier", cmd.COUNTER_CAP < 80)
      doctrine.set_cap(2, cap)
      side.gold, side.recruit = gold, recruit
      wml.variables.sw_command = nil
    end

    function S.flanking()
      swt.clear()
      local function idx(u, name)
        for i, a in ipairs(u.attacks) do if a.name == name then return i end end
      end
      local function cth(att, name, def)
        local _a, _d, aw = wesnoth.simulate_combat(att, idx(att, name), def)
        return aw.chance_to_hit
      end
      local function at(dir)
        local h = wesnoth.map.get_direction({ 10, 8 }, dir)
        return h[1] or h.x, h[2] or h.y
      end
      local function ally(dir, id)
        local x, y = at(dir)
        return swt.place("sw_unit_nr_trooper", 1, x, y, id)
      end
      local st = swt.place("sw_unit_im_stormtrooper", 2, 10, 8, "t_fl_target")
      local nx, ny = at("n")
      local tr = swt.place("sw_unit_nr_trooper", 1, nx, ny, "t_fl_att")
      local base = cth(tr, "rifle_butt", st)
      local a1 = ally("s", "t_fl_a1")
      local c1 = cth(tr, "rifle_butt", st)
      check("one ally behind the target: +10% to hit", c1 == base + 10, base .. " -> " .. c1)
      local active = false
      for _i, sp in ipairs(tr.attacks[idx(tr, "rifle_butt")].specials) do
        if sp[2] and sp[2].id == "sw_special_flanking" then active = true end
      end
      check("the flanking special is on the weapon", active)
      local a2 = ally("se", "t_fl_a2")
      local c2 = cth(tr, "rifle_butt", st)
      check("two allies on the far side: +20%", c2 == base + 20, base .. " -> " .. c2)
      ally("sw", "t_fl_a3")
      local c3 = cth(tr, "rifle_butt", st)
      check("three allies: capped at +20%", c3 == base + 20, base .. " -> " .. c3)
      for _i, id in ipairs{ "t_fl_a1", "t_fl_a2", "t_fl_a3" } do wesnoth.units.get(id):erase() end
      ally("ne", "t_fl_side1")
      ally("nw", "t_fl_side2")
      local cs = cth(tr, "rifle_butt", st)
      check("allies beside the attacker do not flank", cs == base, base .. " -> " .. cs)
      wesnoth.units.get("t_fl_side1"):erase()
      wesnoth.units.get("t_fl_side2"):erase()
      local stone = ally("s", "t_fl_stone")
      stone.status.petrified = true
      local cp = cth(tr, "rifle_butt", st)
      check("a petrified unit does not flank", cp == base, base .. " -> " .. cp)
      stone:erase()
      -- Return fire is never flanked: a stormtrooper behind the trooper (on
      -- its far side from the defender) leaves the defender's chance as is.
      local _a0, _d0, _aw0, dw0 = wesnoth.simulate_combat(tr, idx(tr, "rifle_butt"), st)
      local bx, by = wesnoth.map.get_direction({ nx, ny }, "n")[1], wesnoth.map.get_direction({ nx, ny }, "n")[2]
      swt.place("sw_unit_im_stormtrooper", 2, bx, by, "t_fl_behind")
      local _a1, _d1, _aw1, dw1 = wesnoth.simulate_combat(tr, idx(tr, "rifle_butt"), st)
      check("flanking never applies to return fire", dw0 and dw1 and dw1.chance_to_hit == dw0.chance_to_hit,
        dw0 and dw1 and (dw0.chance_to_hit .. " -> " .. dw1.chance_to_hit))
      wesnoth.units.get("t_fl_behind"):erase()
      -- A shot from 2 hexes: the hexes behind the target along the line of fire.
      local fx, fy = wesnoth.map.get_direction({ nx, ny }, "n")[1], wesnoth.map.get_direction({ nx, ny }, "n")[2]
      tr:to_map(fx, fy)
      local r0 = cth(tr, "blaster_rifle", st)
      ally("s", "t_fl_r1")
      local r1 = cth(tr, "blaster_rifle", st)
      check("a 2-hex shot is flanked from the far side: +10%", r1 == r0 + 10, r0 .. " -> " .. r1)
      local ai = wesnoth.dofile("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua")
      check("the AI's ranged model sees the same +10%", ai.flank_bonus(st, fx, fy, tr) == 10)
    end

    function S.ai_ranged_legality()
      local ca = wesnoth.dofile("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua")
      swt.clear()
      swt.place("sw_unit_nr_militia", 1, 10, 8, "t_legal_target")
      local luke = swt.place("sw_hero_luke", 2, 12, 8, "t_legal_luke")
      luke.moves = 0
      check("stand-off AI excludes defensive-only Jedi deflection", ca.best_attack(2, {}) == nil)
      luke:erase()
      local shooter = swt.place("sw_unit_im_stormtrooper", 2, 12, 8, "t_legal_shooter")
      shooter.moves = 0
      shooter.status.petrified = true
      check("stand-off AI excludes a petrified attacker", ca.best_attack(2, {}) == nil)
      shooter.status.petrified = false

      -- Keep the actual native aimed config, including its defense-only
      -- disable. Removing other fixture weapons proves this weapon qualifies.
      local aimed
      for _i, a in ipairs(shooter.attacks) do
        if a.name == "blaster_rifle_aimed" then aimed = a.__cfg end
      end
      assert(aimed, "AI fixture requires the native aimed rifle")
      for i = #shooter.attacks, 1, -1 do shooter.attacks[i] = nil end
      shooter.attacks[1] = aimed
      local choice = ca.best_attack(2, {})
      check("stand-off AI retains the defense-disabled aimed shot", choice and choice.weapon == 1)
      local native_specials = shooter.attacks[1].specials
      local function disable(body)
        local specials = {}
        for _i, sp in ipairs(native_specials) do specials[#specials + 1] = sp end
        specials[#specials + 1] = T.disable(body)
        shooter.attacks[1].specials = specials
      end
      disable{ T.filter_opponent{ id = "t_legal_target" } }
      check("a matching conditional disable defaults to both and prevents offense", ca.best_attack(2, {}) == nil)
      disable{ active_on = "offense", T.filter_opponent{ id = "t_other_target" } }
      check("a nonmatching conditional disable still permits offense", ca.best_attack(2, {}) ~= nil)
      disable{ active_on = "offense", apply_to = "opponent" }
      check("an opponent-only disable does not disable the AI's own weapon", ca.best_attack(2, {}) ~= nil)
      disable{ active_on = "offense", apply_to = "defender" }
      check("a defender-only disable does not disable the attacker", ca.best_attack(2, {}) ~= nil)
      disable{ active_on = "offense", apply_to = "attacker" }
      check("an attacker-only disable prevents offense", ca.best_attack(2, {}) == nil)
      disable{ active_on = "offense", apply_to = "both" }
      check("a both-combatants disable also prevents the attacker's offense", ca.best_attack(2, {}) == nil)
      disable{ active_on = "offense", T.filter_self{ T.filter_weapon{ name = "blaster_rifle_aimed" } } }
      check("conditional disable matches the selected native weapon", ca.best_attack(2, {}) == nil)
      disable{ active_on = "offense", T.filter_attacker{ T.filter_weapon{ name = "other_weapon" } } }
      check("a nonmatching weapon-filtered disable permits the shot", ca.best_attack(2, {}) ~= nil)
      disable{ active_on = "offense", T.filter_defender{ id = "t_legal_target" } }
      check("conditional disable honors the native defender filter", ca.best_attack(2, {}) == nil)
      disable{ active_on = "offense", T.filter_self{ x = 12, y = 8 } }
      shooter.moves = 3
      choice = ca.best_attack(2, {})
      check("conditional self-location is evaluated at the proposed firing hex",
        choice and (choice.x ~= 12 or choice.y ~= 8))

      -- Exercise the real CA execution with native units and a bounded move
      -- callback. Only movement/command delivery is intercepted; each mutation
      -- represents WML or an ambush during movement. No invalid attack may be
      -- submitted. The separate ai_ranged step retains the real AI-turn attack.
      local cases = {
        { "attacker petrified", function(a) a.status.petrified = true end },
        { "attacker lost its attack", function(a) a.attacks_left = 0 end },
        { "attacker changed side", function(a) a.side = 2 end },
        { "attacker disappeared", function(a) a:erase() end },
        { "move did not reach the firing hex", function(a) a:to_map(15, 8) end },
        { "selected weapon replaced", function(a, _t, b) a.attacks[b.weapon].name = "sw_test_replaced_weapon" end },
        { "selected weapon needs more attacks", function(a, _t, b) a.attacks[b.weapon].attacks_used = 2 end },
        { "selected weapon range changed", function(a, _t, b)
          a.attacks[b.weapon].min_range = 3; a.attacks[b.weapon].max_range = 3
        end },
        { "selected weapon became conditionally disabled", function(a, _t, b)
          local sp = a.attacks[b.weapon].specials
          sp[#sp + 1] = T.disable{ active_on = "offense", T.filter_self{ x = b.x, y = b.y } }
          a.attacks[b.weapon].specials = sp
        end },
        { "target became friendly", function(_a, t) t.side = 1 end },
        { "target disappeared", function(_a, t) t:erase() end },
        { "target became petrified", function(_a, t) t.status.petrified = true end },
        { "target moved out of range", function(_a, t) t:to_map(1, 1) end },
        { "target became invisible", function(_a, t)
          local id, x, y = t.id, t.x, t.y
          t:add_modification("object", { id = "sw_test_ai_hidden",
            T.effect{ apply_to = "new_ability", T.abilities{ T.hides{ id = "sw_test_ai_hidden", affect_self = true } } } })
          -- The intercepted move bypasses native movement's status-cache
          -- clearing after best_attack queried visibility. A native clone
          -- starts with an empty invisibility cache (1.19.27 unit copy ctor).
          t:clone():to_map(x, y)
          t = assert(swt.u(id), "hidden-target fixture lost the replacement unit")
          local hidden = not t:matches{ T.filter_vision{ side = 1, visible = true } }
          check("post-move hidden-target fixture proves native invisibility", hidden)
          assert(hidden, "hidden-target fixture must establish native invisibility before testing the guard")
        end },
      }
      for _i, case in ipairs(cases) do
        swt.clear()
        local a = swt.place("sw_unit_nr_trooper", 1, 15, 8, "t_legal_move")
        swt.place("sw_unit_nr_militia", 2, 10, 8, "t_legal_move_target")
        local best = ca.best_attack(1, {})
        local saved_ai, saved_command = ai, wesnoth.wml_actions.do_command
        local moved, commands = false, 0
        ai = { move = function(actor, x, y)
          moved = true
          actor:to_map(x, y)
          case[2](swt.u(actor.id), swt.u("t_legal_move_target"), best)
        end }
        wesnoth.wml_actions.do_command = function() commands = commands + 1 end
        local ok, err = pcall(function()
          assert(best and (best.x ~= a.x or best.y ~= a.y), "fixture requires movement before firing")
          ca:execution({}, { sw_ranged_fire = best, sw_ranged_tried = {} })
        end)
        ai, wesnoth.wml_actions.do_command = saved_ai, saved_command
        check("post-move AI legality rejects " .. case[1], ok and moved and commands == 0, err or commands)
      end
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
      check("the real AI turn used an eligible offensive rifle", shot and
        (shot.w == "blaster_rifle" or shot.w == "blaster_rifle_aimed"), shot and shot.w)
    end

    function S.ai_target_priority()
      swt.clear()
      local ca = wesnoth.dofile("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua")
      local target = swt.place("sw_unit_im_stormtrooper", 1, 10, 8, "t_focus_target")
      local support = swt.place("sw_unit_im_stormtrooper", 1, 9, 8, "t_focus_support")
      local support2 = swt.place("sw_unit_im_stormtrooper", 1, 10, 9, "t_focus_support2")
      check("isolated full-health target preference is four points", ca.target_priority(target, {target}) == 4)
      check("one nearby armed ally halves the isolation preference", ca.target_priority(target, {target, support}) == 2)
      check("two nearby armed allies remove the isolation preference", ca.target_priority(target, {target, support, support2}) == 0)
      target.hitpoints = 1
      local rating = ca.target_priority(target, {target})
      check("wounded and isolated target preferences stay below eight points", rating > 4 and rating < 8, rating)
      target.hitpoints = target.max_hitpoints
      support2.status.petrified = true
      check("petrified troops do not protect a target in the model", ca.target_priority(target, {target, support2}) == 4)

      -- Equal native rifles on flat ground give less than the four-point
      -- baseline after return fire. Preferences must not authorize that duel.
      swt.clear()
      local full = swt.place("sw_unit_im_stormtrooper", 1, 10, 8, "t_a_full")
      local wounded = swt.place("sw_unit_im_stormtrooper", 1, 12, 8, "t_z_wounded")
      wounded.hitpoints = math.floor(wounded.max_hitpoints * 0.7)
      local shooter = swt.place("sw_unit_im_stormtrooper", 2, 11, 10, "t_focus_shooter")
      shooter.moves = 0
      check("native focus fixture has equally distant rifle targets",
        wesnoth.map.distance_between(shooter.x, shooter.y, full.x, full.y) == 2
        and wesnoth.map.distance_between(shooter.x, shooter.y, wounded.x, wounded.y) == 2)
      local best = ca.best_attack(2, {})
      check("target preferences never authorize a below-baseline rifle duel", best == nil)
      -- Change only the fixture defenders' reach to one hex. Both now offer
      -- worthwhile, equivalent shots without return fire; wounded preference
      -- breaks the tie. Their damage, terrain, resistances and HP are unchanged.
      for _i, defender in ipairs{full, wounded} do
        for _j, weapon in ipairs(defender.attacks) do
          if weapon.range == "ranged" then weapon.min_range = 1; weapon.max_range = 1 end
        end
      end
      best = ca.best_attack(2, {})
      check("real ranged selection prefers the wounded equivalent target", best and best.target == wounded.id,
        best and best.target or "no worthwhile attack")

      -- A concealed occupant of the preferred firing hex must not redirect
      -- planning. The native movement order, rather than hidden map lookup,
      -- remains responsible for any subsequent ambush.
      swt.clear()
      swt.place("sw_unit_nr_militia", 1, 10, 8, "t_hidden_target")
      shooter = swt.place("sw_unit_im_stormtrooper", 2, 15, 8, "t_hidden_shooter")
      best = assert(ca.best_attack(2, {}), "hidden-occupant fixture needs a reachable shot")
      local hidden = swt.place("sw_unit_nr_militia", 1, best.x, best.y, "t_hidden_occupant")
      hidden:add_modification("object", { id = "sw_test_tactics_hidden",
        T.effect{ apply_to = "new_ability", T.abilities{ T.hides{ id = "sw_test_tactics_hidden", affect_self = true } } } })
      hidden:clone():to_map(hidden.x, hidden.y)
      hidden = swt.u("t_hidden_occupant")
      check("native firing-hex occupant is actually hidden",
        not hidden:matches{ T.filter_vision{ side = 2, visible = true } })
      local after = ca.best_attack(2, {})
      check("hidden firing-hex occupant does not change target, hex or rating", after
        and after.target == best.target and after.x == best.x and after.y == best.y and after.rating == best.rating)
    end

    local function sw_ow_scene(prefix, shift)
      swt.clear()
      local d = shift or 0
      local mover = swt.place("sw_unit_im_stormtrooper", 2, 6+d, 8, prefix .. "_mover")
      local target = swt.place("sw_unit_sm_smuggler", 1, 12+d, 8, prefix .. "_target")
      local watcher = swt.place("sw_unit_nr_eweb_team", 1, 5+d, 6, prefix .. "_watcher")
      return mover, target, watcher
    end
    function S.ai_ow_path_rules()
      local ca = wesnoth.dofile("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua")
      local ow = sw_systems.overwatch
      local mover, target, watcher = sw_ow_scene("sw_test_ow_rules")
      local off = assert(ca.best_attack(2, {}))
      check("inactive watcher retains native baseline firing position", off.target == target.id and off.x == 10 and off.y == 7)
      check("inactive watcher permits the native baseline path", ca.sw_path_avoids_overwatch(mover, 10, 7))
      assert(ow.enter(watcher, true))
      local sw_rules_shots = watcher.variables.sw_ow_shots
      check("native arm spends the watcher's ordinary attack and movement", watcher.attacks_left == 0 and watcher.moves == 0)
      check("visible active watcher vetoes the path before its otherwise safe endpoint",
        not ca.sw_path_avoids_overwatch(mover, 10, 7) and wesnoth.map.distance_between(5,6,10,7) > 3)
      local best = assert(ca.best_attack(2, {}))
      check("ranged AI selects the safe equal-cost firing position", best.target == target.id and best.x == 10 and best.y == 8)
      local _, old_cost = wesnoth.paths.find_path(mover, 10, 7, {viewing_side=2})
      local _, safe_cost = wesnoth.paths.find_path(mover, best.x, best.y, {viewing_side=2})
      check("both tactical approaches cost four native MP", old_cost == 4 and safe_cost == 4)
      local again = ca.best_attack(2, {})
      check("safe firing selection is deterministic", again and again.x == best.x and again.y == best.y and again.rating == best.rating)
      check("overwatch choice adds no attack damage or accuracy", best.rating == off.rating)
      check("planning preserves ordinary mover and watcher budgets", mover.moves == 5 and mover.attacks_left == 1
        and watcher.variables.sw_ow_shots == sw_rules_shots and sw_rules_shots == ow.config(watcher).reactions
        and sw_rules_shots > 0 and watcher.attacks_left == 0)
      watcher.variables.sw_ow_shots = 0
      check("spent watcher cannot veto the path", ca.sw_path_avoids_overwatch(mover, 10, 7))
      watcher.variables.sw_ow_shots = 1
      watcher.status.petrified = true
      check("petrified watcher cannot veto the path", ca.sw_path_avoids_overwatch(mover, 10, 7))
      watcher.status.petrified = false
      watcher.status.stunned = true
      check("stunned watcher cannot veto the path", ca.sw_path_avoids_overwatch(mover, 10, 7))
      watcher.status.stunned = false
      watcher.variables.sw_dazed_active = true
      check("dazed watcher cannot veto the path", ca.sw_path_avoids_overwatch(mover, 10, 7))
      watcher.variables.sw_dazed_active = nil
      watcher.side = 2
      check("allied watcher cannot veto the path", ca.sw_path_avoids_overwatch(mover, 10, 7))
      watcher.side = 1
      watcher.variables.sw_ow_fired = mover.id .. "#0"
      check("same movement serial prevents a duplicate predicted reaction", ca.sw_path_avoids_overwatch(mover, 10, 7))
      mover.variables.sw_move_serial = 1
      check("the next movement serial restores the reaction risk", not ca.sw_path_avoids_overwatch(mover, 10, 7))
      watcher.variables.sw_ow_fired = nil
      mover.variables.sw_move_serial = nil
      watcher.variables.sw_ow_range = 0
      check("a zero-range watcher does not cover entered path cells", ca.sw_path_avoids_overwatch(mover, 10, 7))
      watcher.variables.sw_ow_range = 3
      watcher.variables.sw_ow_arc = "front"
      local path = wesnoth.paths.find_path(mover, 10, 7, {viewing_side=2})
      for _, facing in ipairs{"n","ne","se","s","sw","nw"} do
        watcher.variables.sw_ow_facing = facing
        local covered = false
        for i=2,#path do
          local x,y=path[i][1] or path[i].x,path[i][2] or path[i].y
          if wesnoth.map.distance_between(watcher.x,watcher.y,x,y)<=3
            and ow.in_arc(watcher,{x=x,y=y}) then covered=true end
        end
        check("native front arc respected for "..facing, ca.sw_path_avoids_overwatch(mover,10,7)==not covered)
      end
      watcher.variables.sw_ow_arc = "all"
      watcher:add_modification("object",{id="sw_test_ow_hiding",
        T.effect{apply_to="new_ability",T.abilities{T.hides{id="sw_test_ow_hiding",affect_self=true}}}})
      watcher:clone():to_map(watcher.x,watcher.y)
      watcher = u("sw_test_ow_rules_watcher")
      check("native watcher is actually concealed from the acting side", not watcher:matches{T.filter_vision{side=2,visible=true}})
      local hidden_on = ca.best_attack(2,{})
      ow.clear(watcher)
      local hidden_off = ca.best_attack(2,{})
      check("arming a hidden watcher changes neither target, position nor rating", hidden_on and hidden_off
        and hidden_on.target==hidden_off.target and hidden_on.x==hidden_off.x and hidden_on.y==hidden_off.y
        and hidden_on.rating==hidden_off.rating)
      check("hidden watcher cannot veto a public planned path", ca.sw_path_avoids_overwatch(mover,10,7))
      for shift=0,1 do
        mover,target,watcher = sw_ow_scene("sw_test_ow_parity"..shift,shift)
        assert(ow.enter(watcher,true))
        local reach = wesnoth.paths.find_reach(mover,{viewing_side=2})
        for _,hex in ipairs(reach) do
          local x,y=hex[1] or hex.x,hex[2] or hex.y
          if not wesnoth.units.get(x,y) or (x==mover.x and y==mover.y) then
            local p,cost = wesnoth.paths.find_path(mover,x,y,{viewing_side=2})
            local covered = false
            for i=2,#p do
              local clone=mover:clone();clone.loc={p[i][1] or p[i].x,p[i][2] or p[i].y}
              if ow.eligible(watcher,clone) then covered=true;break end
            end
            check("public lane agrees with native eligible path at parity"..shift.." "..x..","..y,
              ca.sw_path_avoids_overwatch(mover,x,y)==(cost<=mover.moves and not covered))
          end
        end
      end
      mover,target,watcher = sw_ow_scene("sw_test_ow_stay")
      assert(ow.enter(watcher,true))
      watcher.variables.sw_ow_range = 20 -- isolated all-paths-blocked control
      check("no exposed endpoint is credited when all moving shots are covered", ca.best_attack(2,{})==nil)
      mover.loc={10,8}
      check("remaining on the source hex draws no movement reaction", ca.sw_path_avoids_overwatch(mover,10,8))
      best=ca.best_attack(2,{})
      check("an already positioned rifle can still make a worthwhile stationary shot", best and best.x==10 and best.y==8
        and best.target==target.id)
    end

    function S.ai_ow_path()
      local ca=wesnoth.dofile("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua")
      local mover,target,watcher=sw_ow_scene("sw_test_ow_real")
      assert(sw_systems.overwatch.enter(watcher,true))
      local best=assert(ca.best_attack(2,{}))
      local path,cost=wesnoth.paths.find_path(mover,best.x,best.y,{viewing_side=2})
      local expected={}
      for i=2,#path do expected[#expected+1]=(path[i][1] or path[i].x)..","..(path[i][2] or path[i].y) end
      swt.mem.ow_real={expected=table.concat(expected,";"),trace={},x=best.x,y=best.y,target=best.target,cost=cost,
        hp=mover.hitpoints,attacks=mover.attacks_left,moves=mover.moves,shots=watcher.variables.sw_ow_shots}
      wesnoth.game_events.add{name="enter_hex",id="sw_test_ow_actual_move",first_time_only=false,action=function()
        local ec=wesnoth.current.event_context
        local moving=wesnoth.units.get(ec.x1,ec.y1);local m=swt.mem.ow_real
        if moving and moving.id=="sw_test_ow_real_mover" and not m.attack then
          m.trace[#m.trace+1]=moving.x..","..moving.y
        end
      end}
      -- moveto observes the remaining movement before native combat spends it.
      wesnoth.game_events.add{name="moveto",id="sw_test_ow_actual_arrival",first_time_only=false,action=function()
        local ec=wesnoth.current.event_context
        local moving=wesnoth.units.get(ec.x1,ec.y1);local m=swt.mem.ow_real
        if moving and moving.id=="sw_test_ow_real_mover" and not m.attack then
          local watch=u("sw_test_ow_real_watcher")
          m.arrival={x=moving.x,y=moving.y,hp=moving.hitpoints,moves=moving.moves,
            shots=watch and watch.variables.sw_ow_shots,fired=watch and watch.variables.sw_ow_fired}
        end
      end}
      wesnoth.game_events.add{name="attack",id="sw_test_ow_actual_shot",first_time_only=false,action=function()
        local ec=wesnoth.current.event_context
        local firing=wesnoth.units.get(ec.x1,ec.y1);local victim=wesnoth.units.get(ec.x2,ec.y2)
        local m=swt.mem.ow_real
        if firing and firing.id=="sw_test_ow_real_mover" and not m.attack then
          local watch=u("sw_test_ow_real_watcher")
          m.attack={x=firing.x,y=firing.y,target=victim and victim.id,hp=firing.hitpoints,moves=firing.moves,
            shots=watch and watch.variables.sw_ow_shots,fired=watch and watch.variables.sw_ow_fired,
            weapon=(wml.get_child(ec,"weapon") or {}).name}
        end
      end}
      check("ordinary AI-turn setup uses the verified safe firing position", best.x==10 and best.y==8 and best.target==target.id)
      wesnoth.sides[2].controller="ai"
    end
    function S.check_ai_ow_path()
      wesnoth.game_events.remove("sw_test_ow_actual_move")
      wesnoth.game_events.remove("sw_test_ow_actual_shot")
      wesnoth.game_events.remove("sw_test_ow_actual_arrival")
      wesnoth.sides[2].controller="human"
      local m=swt.mem.ow_real;local a=m.attack
      check("ordinary native AI turn reached the safe hex and attacked", a and a.x==m.x and a.y==m.y and a.target==m.target)
      check("ordinary ai.move followed the planner's complete native path", table.concat(m.trace,";")==m.expected,
        table.concat(m.trace,";").." versus "..m.expected)
      local arrival=m.arrival
      check("safe native approach spent the expected four MP", arrival and arrival.x==m.x and arrival.y==m.y
        and arrival.moves==m.moves-m.cost and m.cost==4, arrival and arrival.moves)
      check("safe approach did not draw the visible overwatch volley", arrival and a and arrival.hp==m.hp
        and arrival.shots==m.shots and arrival.fired==nil and a.hp==m.hp and a.shots==m.shots and a.fired==nil)
      check("the native attack spends remaining movement after arrival", a and a.moves==0, a and a.moves)
      check("actual safe ranged attack used a shipped offensive rifle", a and (a.weapon=="blaster_rifle" or a.weapon=="blaster_rifle_aimed"))
      local mover=u("sw_test_ow_real_mover")
      check("the native safe attack spent the mover's attack", mover and mover.attacks_left==0)
    end

    local function sw_ow_saved_choice(ca,mover)
      local tried={}
      for _,other in ipairs(wesnoth.units.find_on_map{side=2}) do
        if other.id~=mover.id then tried[other.id]=true end
      end
      return ca.best_attack(2,tried)
    end
    local function sw_prepare_ow_save()
      local ca=wesnoth.dofile("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua")
      local mover=swt.place("sw_unit_im_stormtrooper",2,14,3,"sw_test_ow_saved_mover")
      local target=swt.place("sw_unit_sm_smuggler",1,20,3,"sw_test_ow_saved_target")
      local watcher=swt.place("sw_unit_nr_eweb_team",1,13,1,"sw_test_ow_saved_watcher")
      assert(sw_systems.overwatch.enter(watcher,true))
      local best=assert(sw_ow_saved_choice(ca,mover))
      wml.variables.sw_test_ow_saved={x=best.x,y=best.y,target=best.target,weapon=best.weapon_name,rating=best.rating,
        mover_x=mover.x,mover_y=mover.y,moves=mover.moves,attacks=mover.attacks_left,hp=mover.hitpoints,
        watcher_x=watcher.x,watcher_y=watcher.y,shots=watcher.variables.sw_ow_shots,range=watcher.variables.sw_ow_range,
        arc=watcher.variables.sw_ow_arc,facing=watcher.variables.sw_ow_facing}
      check("real save fixture has a safe nonstationary native firing choice", (best.x~=mover.x or best.y~=mover.y)
        and ca.sw_path_avoids_overwatch(mover,best.x,best.y))
    end
    local function sw_check_ow_reload()
      local ca=wesnoth.dofile("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua")
      local e=wml.variables.sw_test_ow_saved
      local mover,watcher=u("sw_test_ow_saved_mover"),u("sw_test_ow_saved_watcher")
      check("real reload retains the native overwatch mover and unspent actions", e and mover and mover.x==e.mover_x
        and mover.y==e.mover_y and mover.moves==e.moves and mover.attacks_left==e.attacks and mover.hitpoints==e.hp)
      check("real reload retains active watcher position and spent actions", e and watcher and watcher.x==e.watcher_x
        and watcher.y==e.watcher_y and watcher.variables.sw_ow_active and watcher.moves==0 and watcher.attacks_left==0)
      check("real reload retains reactions, range, arc and facing", e and watcher and watcher.variables.sw_ow_shots==e.shots
        and watcher.variables.sw_ow_range==e.range and watcher.variables.sw_ow_arc==e.arc and watcher.variables.sw_ow_facing==e.facing)
      local best=mover and sw_ow_saved_choice(ca,mover)
      check("real reload reproduces the same public safe firing choice", e and best and best.x==e.x and best.y==e.y
        and best.target==e.target and best.weapon_name==e.weapon and best.rating==e.rating)
      check("real reload's firing path remains outside the visible lane", best and ca.sw_path_avoids_overwatch(mover,best.x,best.y))
    end

    function S.ai_withdraw_rules()
      swt.clear()
      local ca = wesnoth.dofile("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua")
      local target = swt.place("sw_unit_nr_militia", 1, 10, 8, "t_retreat_threat")
      local soldier = swt.place("sw_unit_im_stormtrooper", 2, 12, 8, "t_retreat_unit")
      soldier.hitpoints = math.floor(soldier.max_hitpoints * 0.4)
      local function choice(avoid, tried) return ca.best_withdrawal(2, tried or {}, avoid or {}) end
      local best = choice()
      check("wounded exposed soldier finds a withdrawal", best and best.unit == soldier.id)
      assert(best, "withdrawal fixture requires a safe reachable hex")
      local reachable = false
      local reach = wesnoth.paths.find_reach(soldier, { viewing_side = 2 })
      for _i, loc in ipairs(reach) do
        if (loc[1] or loc.x) == best.x and (loc[2] or loc.y) == best.y then reachable = true end
      end
      check("withdrawal destination uses native movement reach", reachable)
      check("withdrawal gains two hexes and leaves the visible pistol's reach",
        wesnoth.map.distance_between(best.x, best.y, target.x, target.y)
          >= wesnoth.map.distance_between(soldier.x, soldier.y, target.x, target.y) + 2)
      local again = choice()
      check("withdrawal selection is deterministic", again and again.x == best.x and again.y == best.y)
      check("native AI avoid locations can rule out every withdrawal", choice(reach) == nil)
      check("a tried unit cannot repeat a failed withdrawal", choice({}, {[soldier.id] = true}) == nil)
      soldier.hitpoints = soldier.max_hitpoints
      check("healthy units do not withdraw", choice() == nil)
      soldier.hitpoints = math.floor(soldier.max_hitpoints * 0.4)
      soldier.canrecruit = true
      check("leaders do not withdraw through the new action", choice() == nil)
      soldier.canrecruit = false
      soldier.variables.sw_alert_state = "unaware"
      check("unaware guards keep their posts", choice() == nil)
      soldier.variables.sw_alert_state = nil
      soldier.status.petrified = true
      check("petrified troops cannot withdraw", choice() == nil)
      soldier.status.petrified = false
      soldier.moves = 0
      check("troops without movement cannot withdraw", choice() == nil)
      soldier.moves = soldier.max_moves
      soldier.attacks_left = 0
      check("a spent sensor or attack action still permits ordinary withdrawal", choice() ~= nil)
      target:erase()
      check("withdrawal does not search for hidden or absent threats", choice() == nil)
      local stand_down = wesnoth.custom_synced_commands.sw_ai_withdraw_stand_down
      check("withdrawal's replay command is registered without an AI evaluation", type(stand_down) == "function")
      local own = swt.place("sw_unit_nr_sergeant", wesnoth.current.side, 10, 8, "t_stand_down")
      local cmd = {unit = own.id, side = own.side, x = own.x, y = own.y, turn = wesnoth.current.turn}
      own.moves, own.attacks_left = own.max_moves, own.max_attacks
      local function unspent() return own.moves == own.max_moves and own.attacks_left == own.max_attacks end
      cmd.turn = cmd.turn - 1; stand_down(cmd)
      check("stale withdrawal commands preserve a unit's actions", unspent())
      cmd.turn = wesnoth.current.turn; cmd.x = own.x + 1; stand_down(cmd)
      check("withdrawal commands cannot spend actions at a different hex", unspent())
      cmd.x = own.x; cmd.side = soldier.side; stand_down(cmd)
      check("withdrawal commands cannot spend another side's actions", unspent())
      cmd.side = own.side
      wesnoth.sync.invoke_command("sw_ai_withdraw_stand_down", cmd)
      check("the native synced withdrawal command spends movement and attacks", own.moves == 0 and own.attacks_left == 0)
    end

    function S.ai_withdraw()
      swt.clear()
      local ca = wesnoth.dofile("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_ai_ranged.lua")
      local target = swt.place("sw_unit_nr_militia", 1, 10, 8, "t_real_retreat_threat")
      local soldier = swt.place("sw_unit_im_stormtrooper", 2, 12, 8, "t_real_retreat")
      soldier.hitpoints = math.floor(soldier.max_hitpoints * 0.4)
      swt.mem.retreat_origin = {x = soldier.x, y = soldier.y, hp = soldier.hitpoints, target_hp = target.hitpoints}
      swt.mem.retreat_logs = 0
      swt.mem.retreat_log = core.log
      core.log = function(channel, message)
        if channel == "ai" and message:find("t_real_retreat withdraws", 1, true) then
          swt.mem.retreat_logs = swt.mem.retreat_logs + 1
        end
        return swt.mem.retreat_log(channel, message)
      end
      check("real AI withdrawal setup has a safe destination", ca.best_withdrawal(2, {}, {}) ~= nil)
      wesnoth.sides[2].controller = "ai"
    end

    function S.check_ai_withdraw()
      core.log = swt.mem.retreat_log
      wesnoth.sides[2].controller = "human"
      local soldier, target = u("t_real_retreat"), u("t_real_retreat_threat")
      local origin = swt.mem.retreat_origin
      check("the real AI turn executes the new withdrawal once", swt.mem.retreat_logs == 1, swt.mem.retreat_logs)
      check("the wounded AI soldier moved farther from the visible threat", soldier and target
        and wesnoth.map.distance_between(soldier.x, soldier.y, target.x, target.y)
          >= wesnoth.map.distance_between(origin.x, origin.y, target.x, target.y) + 2)
      check("withdrawal spends remaining movement and attacks", soldier and soldier.moves == 0 and soldier.attacks_left == 0)
      check("withdrawal grants no free healing or follow-up attack", soldier and target
        and soldier.hitpoints == origin.hp and target.hitpoints == origin.target_hp)
      if soldier then swt.mem.retreat_saved = soldier.__cfg end
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

    -- Facing: a guard sees the way it faces, so an intruder can step next to
    -- it from behind with a real move and take it down that turn; at the
    -- start of the guards' turn they look around and notice anyone beside them.
    function S.alert_sneak()
      swt.clear()
      local alert = sw_systems.alert
      swt.place("sw_unit_sm_smuggler", 2, 10, 8, "t_back")
      swt.place("sw_unit_sm_smuggler", 2, 16, 3, "t_front")
      swt.place("sw_unit_nr_commando", 1, 6, 8, "t_spy")
      swt.place("sw_unit_nr_commando", 1, 21, 3, "t_spy2")
      wesnoth.wml_actions.sw_alert{ action = "enable", guard_side = 2, intruder_side = 1 }
      check("guards start facing the nearest intruder", u("t_back").facing == "sw" and u("t_front").facing == "se",
        u("t_back").facing .. " " .. u("t_front").facing)
      wesnoth.wml_actions.sw_alert{ action = "guard", T.filter{ id = "t_back" }, facing = "se" }
      check("a scenario can set a guard's facing", u("t_back").facing == "se")
      local behind, ahead = 0, 0
      for _i, loc in ipairs(wml.array_access.get("sw_alert_drawn")) do
        if wesnoth.map.distance_between(loc.x, loc.y, 10, 8) <= 3 then
          if loc.x < 10 then behind = behind + 1 else ahead = ahead + 1 end
        end
      end
      check("sight hexes cover only the half the guard faces", behind == 0 and ahead > 0, behind .. " behind, " .. ahead .. " ahead")
      -- Real move order up behind the guard.
      u("t_spy").moves = 8
      swt.move_to("t_spy", 9, 8)
      check("stepping next to a guard from behind: not spotted", u("t_spy").x == 9 and alert.is_unaware(u("t_back")),
        u("t_spy").x .. "," .. u("t_spy").y)
      wml.variables.x1, wml.variables.y1 = 9, 8
      local ok, vis = pcall(alert.takedown_menu_visible)
      wml.variables.x1, wml.variables.y1 = nil, nil
      check("so Silent takedown is offered after a real approach", ok and vis == true, tostring(vis))
      alert.takedown(u("t_spy"), u("t_back"))
      check("and the guard is knocked out", u("t_back") == nil)
      -- From the front: spotted.
      u("t_spy2").moves = 8
      swt.move_to("t_spy2", 17, 3)
      check("stepping next to a guard from the front: spotted", not alert.is_unaware(u("t_front")))
      -- The guards' turn: a guard on post turns about and notices an
      -- intruder beside it.
      swt.clear()
      swt.place("sw_unit_sm_smuggler", 2, 10, 8, "t_post")
      swt.place("sw_unit_nr_commando", 1, 16, 8, "t_far")
      wesnoth.wml_actions.sw_alert{ action = "enable", guard_side = 2, intruder_side = 1 }
      check("(the post faces east, toward the far intruder)", u("t_post").facing == "se")
      swt.place("sw_unit_nr_commando", 1, 9, 8, "t_lurk")
      alert.check()
      check("an intruder behind the guard is unseen during its own turn", alert.is_unaware(u("t_post")))
      alert.on_side_turn(2)
      check("guards on post look around at the start of their turn", u("t_post").facing == "sw", u("t_post").facing)
      check("and notice an intruder still beside them", not alert.is_unaware(u("t_post")))
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

    -- Guard sight hexes vanish the moment a guard dies (any cause) or is
    -- alerted, without waiting for another move.
    local function drawn_near(x, y)
      local n = 0
      for _i, loc in ipairs(wml.array_access.get("sw_alert_drawn")) do
        if wesnoth.map.distance_between(loc.x, loc.y, x, y) <= 1 then n = n + 1 end
      end
      return n
    end
    function S.alert_sight()
      swt.clear()
      local alert = sw_systems.alert
      swt.place("sw_unit_sm_smuggler", 2, 10, 4, "t_sg_a")
      swt.place("sw_unit_sm_smuggler", 2, 20, 12, "t_sg_b")
      wesnoth.wml_actions.sw_alert{ action = "enable", guard_side = 2, intruder_side = 1 }
      check("sight hexes are drawn around each unaware guard", drawn_near(10, 4) > 0 and drawn_near(20, 12) > 0,
        drawn_near(10, 4) .. " " .. drawn_near(20, 12))
      -- Not combat: a Force power, air strike or hazard kill.
      wesnoth.wml_actions.harm_unit{ T.filter{ id = "t_sg_b" }, amount = 999, kill = true, fire_event = true,
        animate = false }
      check("a guard killed outside combat: its sight hexes vanish at once", drawn_near(20, 12) == 0
        and #wesnoth.interface.get_items(21, 12) == 0, drawn_near(20, 12))
      check("the other guard's sight hexes stay", drawn_near(10, 4) > 0)
      -- An intruder next to the guard attacks it (no move order, so only the
      -- attack itself can alert it); checked in the next step.
      swt.place("sw_unit_nr_commando", 1, 9, 4, "t_sg_spy")
      check("the guard is still unaware before the attack", alert.is_unaware(wesnoth.units.get("t_sg_a")))
      wesnoth.wml_actions.do_command{ T.attack{ weapon = 0, T.source{ x = 9, y = 4 }, T.destination{ x = 10, y = 4 } } }
    end
    function S.check_alert_sight()
      local g = wesnoth.units.get("t_sg_a")
      check("the attacked guard is alert", g == nil or not sw_systems.alert.is_unaware(g))
      check("an alerted guard's sight hexes vanish when the fight ends", drawn_near(10, 4) == 0
        and #wml.array_access.get("sw_alert_drawn") == 0, drawn_near(10, 4))
    end

    -- Hero withdrawal (utils/hte_macros.cfg SW_HERO_WITHDRAWS): a falling
    -- secondary hero leaves the map healed and is kept in sw_stashed_heroes;
    -- the scenario goes on.
    local function stashed(id)
      for _i, u in ipairs(wml.array_access.get("sw_stashed_heroes")) do
        if u.id == id then return u end
      end
    end
    function S.hero_withdraw()
      swt.clear()
      wml.variables.sw_stashed_heroes = nil
      swt.place("sw_hero_lando", 1, 10, 8, "sw_test_withdrawer")
      -- Outside combat (Force power, hazard): [harm_unit] kill.
      wesnoth.wml_actions.harm_unit{ T.filter{ id = "sw_test_withdrawer" }, amount = 999, kill = true,
        fire_event = true, animate = false }
      local s1 = stashed("sw_test_withdrawer")
      check("a hero killed outside combat withdraws: off the map", wesnoth.units.get("sw_test_withdrawer") == nil)
      check("and is kept, healed, to return after victory", s1 ~= nil and s1.hitpoints == s1.max_hitpoints,
        s1 and (s1.hitpoints .. "/" .. s1.max_hitpoints))
      -- In combat: a 1 HP hero attacks a Noghri whose return strikes always
      -- hit (a test-only 100% special), so the counterattack fells her.
      local h = swt.place("sw_hero_leia", 1, 12, 8, "sw_test_withdrawer2")
      h.hitpoints = 1
      local ng = swt.place("sw_unit_im_noghri", 2, 13, 8, "t_wd_ng")
      ng:add_modification("object", { T.effect{ apply_to = "attack", range = "melee",
        T.set_specials{ mode = "append", T.chance_to_hit{ id = "t_sure", value = 100 } } } })
      wesnoth.wml_actions.do_command{ T.attack{ weapon = 0, T.source{ x = 12, y = 8 }, T.destination{ x = 13, y = 8 } } }
    end
    function S.check_hero_withdraw()
      local gone = wesnoth.units.get("sw_test_withdrawer2") == nil
      local s2 = stashed("sw_test_withdrawer2")
      check("a hero struck down in combat withdraws instead of dying", gone and s2 ~= nil,
        tostring(gone) .. " " .. tostring(s2 ~= nil))
      check("the scenario goes on", wesnoth.current.turn >= 1)
      wml.variables.sw_stashed_heroes = nil
    end

    -- Muzzle flashes match the shot (owner rule 2026-10-04): every ranged
    -- animation's firing-frame flash is the colour of the bolt it fires, and
    -- the composed frame image actually builds in the engine.
    function S.muzzle_flashes()
      local frames, mismatched, broken, painted, painted_ids = 0, {}, {}, 0, {}
      local family = { ["sw-ion"] = "ion", ["sw-force-lightning"] = "lightning", ["sw-torpedo"] = "torpedo",
        ["sw-stun"] = "blue" }
      for _i, id in ipairs(core.sorted_keys(wesnoth.unit_types)) do
        local cfg = wesnoth.unit_types[id].__cfg
        for _j, anim in ipairs(wml.child_array(cfg, "attack_anim")) do
          local missile = wml.get_child(anim, "missile_frame")
          local bolt = missile and missile.image or ""
          for _k, fr in ipairs(wml.child_array(anim, "frame")) do
            local img = fr.image or ""
            local flash = img:match("~BLIT%(projectiles/sw%-flash%-(%a+)%.png")
            if flash then
              frames = frames + 1
              local want = bolt:match("sw%-heavy%-bolt%-(%a+)%-n") or bolt:match("sw%-bolt%-(%a+)%-n")
              for prefix, c in pairs(family) do
                if bolt:find(prefix, 1, true) then want = c end
              end
              if want ~= flash then table.insert(mismatched, id .. ":" .. flash .. "/" .. tostring(want)) end
              local w, h = filesystem.image_size(img)
              if w ~= 72 or h ~= 72 then table.insert(broken, img) end
            elseif img:find("ranged%-2%.png$") and bolt:find("bolt-", 1, true) then
              painted = painted + 1
              table.insert(painted_ids, id)
            end
          end
        end
      end
      -- Firing frames either get a blitted flash or paint their own (owner and
      -- Codex sheets since 2026-10-06); together they cover the roster.
      check("firing frames carry a coloured muzzle flash", frames + painted > 60, frames .. " blitted + " .. painted .. " painted")
      check("every flash is the colour of its shot", #mismatched == 0, table.concat(mismatched, " "))
      check("every flashed frame builds in the engine (72x72)", #broken == 0, table.concat(broken, " "))
      check("hand-painted flashes fire bolts too", painted >= 6, painted .. " " .. table.concat(painted_ids, ","))
    end

    -- Attack range display (lua/sw_range.lua).
    function S.attack_range()
      swt.clear()
      local range = sw_systems.range
      local tr = swt.place("sw_unit_nr_trooper", 1, 8, 8, "t_tr")
      local mil = swt.place("sw_unit_nr_militia", 1, 3, 3, "t_mil")
      local d = range.distances(tr)
      check("a rifleman can attack at 1 and 2 hexes", d[1] and d[2] and not d[3])
      check("a pistol-armed militiaman only at 1 hex", range.distances(mil)[1] and not range.distances(mil)[2])
      local direct, moving = range.zones(tr, false)
      local nd, nm = 0, 0
      for _k in pairs(direct) do nd = nd + 1 end
      for _k in pairs(moving) do nm = nm + 1 end
      check("solid markers cover the 18 hexes within 2", nd == 18, nd)
      check("dotted markers cover hexes reachable by moving first", nm > 0, nm)
      wml.variables.x1, wml.variables.y1 = 8, 8
      local okv, vis = pcall(range.show_menu_visible)
      wml.variables.x1, wml.variables.y1 = nil, nil
      check("Show attack range is offered on a visible unit", okv and vis == true, tostring(vis))
      range.show(tr, 1)
      local mine = 0
      for _i, it in ipairs(wesnoth.interface.get_items(9, 8)) do
        if it.name == "sw_range_direct" and it.team_name == core.team_key(1) then mine = mine + 1 end
      end
      check("the range is drawn for the viewer's team only", mine == 1, mine)
      local st = swt.place("sw_unit_im_stormtrooper", 2, 15, 8, "t_st")
      range.show(st, 1)
      local only_st = true
      for _i, e in ipairs(wml.array_access.get("sw_range_shown")) do if e.unit ~= "t_st" then only_st = false end end
      check("showing another unit replaces the display", range.shown_unit(core.team_key(1)) == "t_st" and only_st)
      u("t_st"):to_map(16, 8)
      wesnoth.game_events.fire("moveto", 16, 8)
      check("the display clears when that unit moves", range.shown_unit(core.team_key(1)) == nil)
      range.show(tr, 1)
      range.hide_menu_command()
      check("Hide attack range clears it", #wml.array_access.get("sw_range_shown") == 0)
    end

    -- Native slow (core WEAPON_SPECIAL_SLOW): on a hit, lasts through the
    -- target's next turn; doubles terrain costs rather than halving max_moves.
    -- Only fixture chance-to-hit specials are replaced to isolate hit/miss.
    -- The shipped slow, range and aimed defense-disable remain intact.
    local function sw_wk_idx(unit, name)
      for i, attack in ipairs(unit.attacks) do if attack.name == name then return i end end
      error("missing Wookiee fixture weapon: " .. name)
    end
    local function sw_wk_certainty(unit, name, value)
      local idx = sw_wk_idx(unit, name)
      local original, specials = unit.attacks[idx].specials, {}
      for _, special in ipairs(original) do
        if special[1] ~= "chance_to_hit" then specials[#specials + 1] = special end
      end
      specials[#specials + 1] = T.chance_to_hit{ id = "sw_test_wookiee_certainty", value = value, cumulative = false }
      unit.attacks[idx].specials = specials
      return idx, original
    end
    local function sw_wk_cost(unit, x, y)
      local _, cost = wesnoth.paths.find_path(unit, x, y, { ignore_units = true })
      return cost
    end
    local function sw_wk_damage(unit, target)
      local _, _, weapon = wesnoth.simulate_combat(unit, sw_wk_idx(unit, "rifle_butt"), target)
      return weapon.damage
    end
    -- Keep a concussive support recruit in the class-rank system without
    -- adding weapons or duplicating its base Slow. Use real native AMLAs.
    -- Wayland support troops use native healing at the start of their side's
    -- turn (AbilitiesWML), not a manual heal action or mission event.
    local function sw_med_heals(unit)
      local values = {}
      for _, cfg in ipairs(wml.child_array(wml.get_child(unit.__cfg, "abilities") or {}, "heals")) do
        values[#values + 1] = tonumber(cfg.value)
      end
      return values
    end
    function S.myneyrshi_medic_ranks()
      swt.clear()
      local med = swt.place("sw_unit_wy_field_medic", 1, 14, 12, "sw_test_native_medic_ranked")
      local old = #med.attacks
      check("Myneyrshi medic is a fragile 20-gold healer", med.max_hitpoints == 28 and med.max_moves == 6
        and med.max_experience == 48 and wesnoth.unit_types.sw_unit_wy_field_medic.cost == 20)
      check("fresh native medic heals4 without hiding or skirmisher", #sw_med_heals(med) == 1
        and sw_med_heals(med)[1] == 4 and not med:matches{ ability = "sw_rank_hides" }
        and not med:matches{ ability = "sw_rank_skirmisher" })
      check("native medic retains Wayland forest mobility and fire vulnerability",
        med:movement_on(wesnoth.current.map[{15,12}]) == 1 and med:resistance_against("fire") == -10)
      local other = swt.place("sw_unit_nr_field_medic", 1, 16, 12, "sw_test_native_medic_compare")
      check("ordinary Republic medic pays2 for the same forest", other:movement_on(wesnoth.current.map[{15,12}]) == 2)
      med = swt.level_up(med.id)
      check("native medic rankI grants forest concealment", rank.of(med) == 1
        and med:matches{ ability = "sw_rank_hides" } and sw_med_heals(med)[1] == 4)
      med = swt.level_up(med.id)
      check("native medic rankII replaces healing4 with exactly one healing8",
        rank.of(med) == 2 and #sw_med_heals(med) == 1 and sw_med_heals(med)[1] == 8)
      med = swt.level_up(med.id)
      check("native medic rankIII grants rapid evacuation", rank.of(med) == 3
        and med:matches{ ability = "sw_rank_skirmisher" } and #med.attacks == old and med.max_moves == 6)
      swt.mem.native_medic_ranked = med.__cfg
      med = swt.level_up(med.id)
      rank.update(med)
      local once = rank.of(med) == 3 and #sw_med_heals(med) == 1
      for r = 1,3 do once = once and swt.objects(med, "sw_rank_ability_" .. r) == 1 end
      check("native medic rank grants stay unique and add no weapons", once and #med.attacks == old)
    end
    function S.myneyrshi_medic_recruit_setup()
      swt.clear()
      swt.mem.med_gold, swt.mem.med_recruit = wesnoth.sides[1].gold, wesnoth.sides[1].recruit
      swt.mem.med_keep, swt.mem.med_castle = wesnoth.current.map[{4,4}], wesnoth.current.map[{5,4}]
      wesnoth.wml_actions.terrain{ x=4, y=4, terrain="Kh" }
      wesnoth.wml_actions.terrain{ x=5, y=4, terrain="Ch" }
      local leader = swt.place("sw_hero_han", 1, 4, 4, "sw_test_native_medic_leader")
      leader.canrecruit = true
      wesnoth.sides[1].gold, wesnoth.sides[1].recruit = 100, {"sw_unit_wy_field_medic"}
    end
    function S.myneyrshi_medic_recruit_check()
      local med = wesnoth.units.get(5,4)
      check("native paid recruitment buys Myneyrshi medic for20 gold", med and med.type == "sw_unit_wy_field_medic"
        and wesnoth.sides[1].gold == 80 and med.side == 1 and not med.canrecruit)
      check("a recruited native medic has spent movement and attack", med and med.moves == 0 and med.attacks_left == 0)
      wesnoth.sides[1].gold, wesnoth.sides[1].recruit = swt.mem.med_gold, swt.mem.med_recruit
      wesnoth.wml_actions.terrain{ x=4, y=4, terrain=swt.mem.med_keep }
      wesnoth.wml_actions.terrain{ x=5, y=4, terrain=swt.mem.med_castle }
    end
    function S.myneyrshi_medic_move_setup()
      swt.clear()
      local med = swt.place("sw_unit_wy_field_medic", 1, 14, 12, "sw_test_native_medic")
      swt.mem.native_medic_move_before = med.moves
      -- Native movement animates and may end this execute slice. Inspect its
      -- result in the next step, after the plugin settles the game.
      swt.move_to(med.id,15,12)
    end
    function S.myneyrshi_medic_move_check()
      local med = u("sw_test_native_medic")
      check("ordinary native forest move costs one MP without refill",
        med.x == 15 and med.y == 12 and med.moves == swt.mem.native_medic_move_before - 1 and med.attacks_left == 1)
    end
    function S.myneyrshi_medic_heal_setup()
      swt.clear()
      local med = swt.place("sw_unit_wy_field_medic", 1, 14, 12, "sw_test_native_medic")
      local ally = swt.place("sw_unit_wy_myneyrshi", 1, 15, 12, "sw_test_native_medic_ally")
      local second = swt.place("sw_unit_nr_field_medic", 1, 16, 12, "sw_test_native_medic_second")
      local poison = swt.place("sw_unit_wy_myneyrshi", 1, 14, 13, "sw_test_native_medic_poison")
      local distant = swt.place("sw_unit_wy_myneyrshi", 1, 18, 12, "sw_test_native_medic_distant")
      local enemy = swt.place("sw_unit_im_stormtrooper", 2, 13, 12, "sw_test_native_medic_enemy")
      for _, unit in ipairs{med,ally,second,poison,distant,enemy} do
        unit.hitpoints, unit.resting, unit.attacks_left = 10, false, 0
      end
      poison.status.poisoned = true
      check("native healing probes have real adjacency and no villages",
        wesnoth.map.distance_between(14,12,15,12) == 1 and wesnoth.map.distance_between(16,12,15,12) == 1
        and wesnoth.map.distance_between(14,12,14,13) == 1
        and not wesnoth.terrain_types[wesnoth.current.map[{15,12}]].village)
    end
    function S.myneyrshi_medic_enemy_turn()
      check("native healing waits for its own turn", wesnoth.current.side == 2
        and u("sw_test_native_medic_ally").hitpoints == 10)
    end
    function S.myneyrshi_medic_heal_check()
      check("two native healing4 sources do not add together", wesnoth.current.side == 1
        and u("sw_test_native_medic_ally").hitpoints == 14, u("sw_test_native_medic_ally").hitpoints)
      check("native healing stops poison damage without curing or healing",
        u("sw_test_native_medic_poison").hitpoints == 10 and u("sw_test_native_medic_poison").status.poisoned)
      check("native healing does not heal itself, distant allies or enemies",
        u("sw_test_native_medic").hitpoints == 10 and u("sw_test_native_medic_distant").hitpoints == 10
        and u("sw_test_native_medic_enemy").hitpoints == 10)
    end
    function S.myneyrshi_medic_upgrade_setup()
      local med = swt.level_up("sw_test_native_medic")
      med = swt.level_up(med.id)
      for _, id in ipairs{"sw_test_native_medic","sw_test_native_medic_ally","sw_test_native_medic_second",
        "sw_test_native_medic_poison","sw_test_native_medic_distant","sw_test_native_medic_enemy"} do
        local unit = u(id)
        unit.hitpoints, unit.resting, unit.attacks_left = 10, false, 0
      end
    end
    function S.myneyrshi_medic_upgrade_enemy_turn()
      check("rankII medic still waits for its own native turn", wesnoth.current.side == 2
        and u("sw_test_native_medic_ally").hitpoints == 10)
    end
    function S.myneyrshi_medic_upgrade_check()
      check("native rankII healing8 replaces4 rather than stacking to12", wesnoth.current.side == 1
        and u("sw_test_native_medic_ally").hitpoints == 18, u("sw_test_native_medic_ally").hitpoints)
      check("field surgery keeps native poison slowed and no self-healing",
        u("sw_test_native_medic_poison").hitpoints == 10 and u("sw_test_native_medic_poison").status.poisoned
        and u("sw_test_native_medic").hitpoints == 10)
    end

    function S.wookiee_ranks()
      swt.clear()
      local function idx(unit, name)
        for i, attack in ipairs(unit.attacks) do if attack.name == name then return i end end
      end
      local function count(unit, name, tag)
        local n = 0
        for _i, special in ipairs(unit.attacks[idx(unit, name)].specials) do
          if special[1] == tag then n = n + 1 end
        end
        return n
      end
      local function cth(att, name, def)
        local _a, _d, weapon = wesnoth.simulate_combat(att, idx(att, name), def)
        return weapon.chance_to_hit
      end
      local unit = swt.place("sw_unit_wk_suppressor", 1, 8, 8, "sw_test_wookiee_ranked")
      local ally = swt.place("sw_unit_nr_trooper", 1, 9, 8, "sw_test_wookiee_rank_ally")
      local foe = swt.place("sw_unit_im_stormtrooper", 2, 10, 8, "sw_test_wookiee_rank_foe")
      local n = #unit.attacks
      local ranged0, melee0 = cth(ally, "blaster_rifle", foe), cth(ally, "rifle_butt", foe)
      local own0 = cth(unit, "bowcaster", foe)
      check("a fresh Suppressor has rank zero and no earned rank object", rank.of(unit) == 0
        and swt.objects(unit, "sw_rank_ability_1") == 0)
      unit = swt.level_up(unit.id)
      check("Suppressor rank I grants thick hide through native advancement", rank.of(unit) == 1
        and unit:matches{ ability = "sw_rank_steadfast" } and tonumber(unit.variables.sw_rank_ability) == 1)
      check("thick hide doubles positive defense resistance", unit:resistance_against("blade", false) == 20
        and unit:resistance_against("cold", false) == 40)
      check("thick hide retains offensive resistance and fire vulnerability", unit:resistance_against("blade", true) == 10
        and unit:resistance_against("cold", true) == 20 and unit:resistance_against("fire", false) == -10)
      unit = swt.level_up(unit.id)
      check("Suppressor rank II gives both bowcaster variants one first strike", rank.of(unit) == 2
        and count(unit, "bowcaster", "firststrike") == 1 and count(unit, "bowcaster_aimed", "firststrike") == 1)
      check("covering fire adds no first strike to the ryyk blade", count(unit, "ryyk_blade", "firststrike") == 0)
      unit = swt.level_up(unit.id)
      check("Suppressor rank III grants fire discipline", rank.of(unit) == 3
        and unit:matches{ ability = "sw_rank_hit_aura" } and tonumber(unit.variables.sw_rank_ability) == 3)
      check("elite Suppressor gives adjacent allies +10 percent ranged accuracy", cth(ally, "blaster_rifle", foe) == ranged0 + 10)
      check("elite Suppressor does not improve allied melee or its own accuracy",
        cth(ally, "rifle_butt", foe) == melee0 and cth(unit, "bowcaster", foe) == own0)
      unit:to_map(8, 6)
      check("Suppressor fire discipline stops beyond adjacency", cth(ally, "blaster_rifle", foe) == ranged0)
      unit:to_map(8, 8)
      check("Suppressor ranks retain exactly one Slow per bowcaster", count(unit, "bowcaster", "slow") == 1
        and count(unit, "bowcaster_aimed", "slow") == 1)
      check("Suppressor ranks add no attacks or movement", #unit.attacks == n and unit.max_moves == 5)
      swt.mem.wk_rank_snapshot = unit.__cfg
      unit = swt.level_up(unit.id)
      rank.update(unit)
      local once = true
      for r = 1, 3 do once = once and swt.objects(unit, "sw_rank_ability_" .. r) == 1 end
      check("Suppressor grants stay capped and unique after another AMLA and update", once and rank.of(unit) == 3
        and count(unit, "bowcaster", "firststrike") == 1 and count(unit, "bowcaster", "slow") == 1)
    end

    function S.wookiee_recruit_setup()
      swt.clear()
      local side = wesnoth.sides[1]
      swt.mem.wk_gold, swt.mem.wk_recruit = side.gold, side.recruit
      swt.mem.wk_keep, swt.mem.wk_castle = wesnoth.current.map[{ 4, 4 }], wesnoth.current.map[{ 5, 4 }]
      wesnoth.wml_actions.terrain{ x = 4, y = 4, terrain = "Kh" }
      wesnoth.wml_actions.terrain{ x = 5, y = 4, terrain = "Ch" }
      local leader = swt.place("sw_hero_leia", 1, 4, 4, "sw_test_wookiee_leader")
      leader.canrecruit = true
      side.gold, side.recruit = 100, { "sw_unit_wk_suppressor" }
    end
    function S.wookiee_recruit_check()
      local unit = wesnoth.units.get(5, 4)
      check("Suppressor recruits through a native paid command for 22 gold", unit and
        unit.type == "sw_unit_wk_suppressor" and unit.side == 1 and not unit.canrecruit and wesnoth.sides[1].gold == 78)
      check("a recruited Suppressor has spent movement and attack", unit and unit.moves == 0 and unit.attacks_left == 0)
      wesnoth.sides[1].gold, wesnoth.sides[1].recruit = swt.mem.wk_gold, swt.mem.wk_recruit
      wesnoth.wml_actions.terrain{ x = 4, y = 4, terrain = swt.mem.wk_keep }
      wesnoth.wml_actions.terrain{ x = 5, y = 4, terrain = swt.mem.wk_castle }
    end
    function S.wookiee_normal()
      swt.clear()
      local shooter = swt.place("sw_unit_wk_suppressor", 1, 8, 8, "sw_test_wookiee_normal")
      local target = swt.place("sw_unit_im_stormtrooper", 2, 10, 8, "sw_test_wookiee_target")
      local victim = swt.place("sw_unit_nr_militia", 1, 10, 7, "sw_test_wookiee_victim")
      check("Suppressor has the bounded generated profile", shooter.max_hitpoints == 34 and shooter.max_moves == 5
        and shooter.max_experience == 48 and wesnoth.unit_types.sw_unit_wk_suppressor.cost == 22)
      check("Suppressor does not replace lookout keen senses", not shooter:matches{ ability = "sw_ability_keen_senses" })
      local normal, aimed = shooter.attacks[sw_wk_idx(shooter, "bowcaster")], shooter.attacks[sw_wk_idx(shooter, "bowcaster_aimed")]
      check("Suppressor normal bowcaster is 4x2 at range 1-2", normal.damage == 4 and normal.number == 2 and normal.min_range == 1 and normal.max_range == 2)
      check("Suppressor aimed bowcaster is 4x1 at range 2", aimed.damage == 4 and aimed.number == 1 and aimed.min_range == 2 and aimed.max_range == 2)
      local _, _, nw = wesnoth.simulate_combat(shooter, sw_wk_idx(shooter, "bowcaster"), target)
      local _, _, aw = wesnoth.simulate_combat(shooter, sw_wk_idx(shooter, "bowcaster_aimed"), target)
      check("unmodified Suppressor aim adds 20 percent accuracy", aw.chance_to_hit == nw.chance_to_hit + 20)
      swt.mem.wk_base_damage = sw_wk_damage(target, victim)
      swt.mem.wk_base_cost = sw_wk_cost(target, 11, 8)
      check("unslowed target has one-hex grass cost 1", swt.mem.wk_base_cost == 1, swt.mem.wk_base_cost)
      swt.mem.wk_target_hp = target.hitpoints
      local idx, original = sw_wk_certainty(shooter, "bowcaster", 100)
      swt.mem.wk_normal_specials = original
      local _, _, sure = wesnoth.simulate_combat(shooter, idx, target)
      check("normal hit fixture establishes native 100 percent chance", sure.chance_to_hit == 100, sure.chance_to_hit)
      wesnoth.wml_actions.do_command{ T.attack{ weapon = idx - 1, T.source{ x = 8, y = 8 }, T.destination{ x = 10, y = 8 } } }
    end
    function S.wookiee_check_normal()
      local shooter, target = u("sw_test_wookiee_normal"), u("sw_test_wookiee_target")
      shooter.attacks[sw_wk_idx(shooter, "bowcaster")].specials = swt.mem.wk_normal_specials
      check("actual two-hex bowcaster hit deals damage and applies Slow", target and target.hitpoints < swt.mem.wk_target_hp and target.status.slowed)
      check("actual Suppressor attack spends its native actions", shooter.attacks_left == 0 and shooter.moves == 0)
      check("Slow halves the target's native attack damage", sw_wk_damage(target, u("sw_test_wookiee_victim")) == math.ceil(swt.mem.wk_base_damage / 2))
      check("Slow doubles native grass path cost", sw_wk_cost(target, 11, 8) == 2)
      swt.mem.wk_saved_shooter, swt.mem.wk_saved_target = shooter.__cfg, target.__cfg
    end
    function S.wookiee_aimed()
      local shooter = swt.place("sw_unit_wk_suppressor", 1, 12, 8, "sw_test_wookiee_aimed")
      local target = swt.place("sw_unit_im_stormtrooper", 2, 14, 8, "sw_test_wookiee_aimed_target")
      swt.mem.wk_aimed_hp = target.hitpoints
      local idx, original = sw_wk_certainty(shooter, "bowcaster_aimed", 100)
      swt.mem.wk_aimed_specials = original
      local _, _, shot = wesnoth.simulate_combat(shooter, idx, target)
      check("aimed hit fixture establishes one certain native strike", shot.chance_to_hit == 100 and shot.num_blows == 1)
      wesnoth.wml_actions.do_command{ T.attack{ weapon = idx - 1, T.source{ x = 12, y = 8 }, T.destination{ x = 14, y = 8 } } }
    end
    function S.wookiee_check_hit()
      local shooter, target = u("sw_test_wookiee_aimed"), u("sw_test_wookiee_aimed_target")
      shooter.attacks[sw_wk_idx(shooter, "bowcaster_aimed")].specials = swt.mem.wk_aimed_specials
      check("actual aimed two-hex hit applies Slow and spends actions", target and target.hitpoints < swt.mem.wk_aimed_hp
        and target.status.slowed and shooter.attacks_left == 0 and shooter.moves == 0)
      -- Leave no spare attack for overwatch before the real side 2 turn.
      u("sw_test_wookiee_victim").attacks_left = 0
      local defender = swt.place("sw_unit_wk_suppressor", 1, 16, 8, "sw_test_wookiee_return")
      defender.attacks_left = 0
      swt.place("sw_unit_im_stormtrooper", 2, 17, 8, "sw_test_wookiee_return_target")
      local _, original = sw_wk_certainty(defender, "bowcaster", 100)
      swt.mem.wk_return_specials = original
    end
    function S.wookiee_target_turn()
      local target = u("sw_test_wookiee_target")
      check("actual target turn retains Slow after native refresh", wesnoth.current.side == 2 and target.status.slowed and target.moves > 0)
      check("actual target turn retains doubled path cost and halved damage", sw_wk_cost(target, 11, 8) == 2
        and sw_wk_damage(target, u("sw_test_wookiee_victim")) == math.ceil(swt.mem.wk_base_damage / 2))
      local attacker = u("sw_test_wookiee_return_target")
      wesnoth.wml_actions.do_command{ T.attack{ weapon = sw_wk_idx(attacker, "blaster_rifle") - 1,
        T.source{ x = 17, y = 8 }, T.destination{ x = 16, y = 8 } } }
    end
    function S.wookiee_check_return()
      local defender = u("sw_test_wookiee_return")
      defender.attacks[sw_wk_idx(defender, "bowcaster")].specials = swt.mem.wk_return_specials
      check("actual normal bowcaster return fire also applies Slow", defender and u("sw_test_wookiee_return_target").status.slowed)
    end
    function S.wookiee_expiry()
      local target = u("sw_test_wookiee_target")
      check("Slow expires after the actual target end turn", wesnoth.current.side == 1 and not target.status.slowed
        and not u("sw_test_wookiee_aimed_target").status.slowed and not u("sw_test_wookiee_return_target").status.slowed)
      check("native damage and grass cost recover after expiry", sw_wk_cost(target, 11, 8) == 1
        and sw_wk_damage(target, u("sw_test_wookiee_victim")) == swt.mem.wk_base_damage)
    end
    function S.wookiee_miss()
      swt.clear()
      local shooter = swt.place("sw_unit_wk_suppressor", 1, 8, 8, "sw_test_wookiee_miss")
      local target = swt.place("sw_unit_im_stormtrooper", 2, 10, 8, "sw_test_wookiee_miss_target")
      swt.mem.wk_miss_hp = target.hitpoints
      local idx, original = sw_wk_certainty(shooter, "bowcaster", 0)
      swt.mem.wk_miss_specials = original
      local _, _, shot = wesnoth.simulate_combat(shooter, idx, target)
      check("miss fixture establishes native zero percent chance", shot.chance_to_hit == 0, shot.chance_to_hit)
      wesnoth.wml_actions.do_command{ T.attack{ weapon = idx - 1, T.source{ x = 8, y = 8 }, T.destination{ x = 10, y = 8 } } }
    end
    function S.wookiee_check_miss()
      local shooter, target = u("sw_test_wookiee_miss"), u("sw_test_wookiee_miss_target")
      shooter.attacks[sw_wk_idx(shooter, "bowcaster")].specials = swt.mem.wk_miss_specials
      check("an actual native miss does no damage and does not slow", target.hitpoints == swt.mem.wk_miss_hp and not target.status.slowed)
      check("an actual native miss still spends the attack", shooter.attacks_left == 0 and shooter.moves == 0)
    end

    function S.prepare_save()
      swt.clear()
      if swt.mem.retreat_saved then
        local soldier = wesnoth.units.create(swt.mem.retreat_saved)
        soldier:to_map()
        wml.variables.swt_retreat_expected = { x = soldier.x, y = soldier.y, hp = soldier.hitpoints,
          moves = soldier.moves, attacks = soldier.attacks_left }
      end
      -- Reconstruct the real combat snapshots, with original weapon specials,
      -- through native [unit] creation. Discard serialized internal identities
      -- so each reconstructed unit receives a fresh one. No manual status.
      if swt.mem.wk_saved_shooter and swt.mem.wk_saved_target then
        swt.mem.wk_saved_shooter.underlying_id = nil
        swt.mem.wk_saved_target.underlying_id = nil
        wesnoth.wml_actions.unit(swt.mem.wk_saved_shooter)
        wesnoth.wml_actions.unit(swt.mem.wk_saved_target)
        local shooter, target = u("sw_test_wookiee_normal"), u("sw_test_wookiee_target")
        wml.variables.swt_wookiee_expected = { hp = shooter.hitpoints, moves = shooter.moves, attacks = shooter.attacks_left,
          target_hp = target.hitpoints, target_slowed = target.status.slowed }
      end
      if swt.mem.wk_rank_snapshot then
        swt.mem.wk_rank_snapshot.underlying_id = nil
        swt.mem.wk_rank_snapshot.x, swt.mem.wk_rank_snapshot.y = 18, 12
        wesnoth.wml_actions.unit(swt.mem.wk_rank_snapshot)
      end
      if swt.mem.native_medic_ranked then
        swt.mem.native_medic_ranked.underlying_id = nil
        swt.mem.native_medic_ranked.x, swt.mem.native_medic_ranked.y = 21,12
        wesnoth.wml_actions.unit(swt.mem.native_medic_ranked)
      end
      local obs = swt.place("sw_unit_nr_commando", 1, 4, 4, "t_obs")
      for _i = 1, 2 do swt.level_up("t_obs") end
      air.grant(1, "strafe", 2, "sw_unit_nr_xwing")
      air.grant(1, "bombing", 1, "sw_unit_nr_ywing")
      local jammer=swt.place("sw_unit_im_stormtrooper",2,8,4,"sw_test_ecm_saved_jammer")
      ew.set_profile(jammer,{ecm=2,ecm_range=0})
      ew.set_profile(u("t_obs"),{eccm=1})
      local chance=math.max(air.MIN_CHANCE,math.min(air.MAX_CHANCE,100-jammer:defense_on({x=8,y=4})))
      wml.variables.sw_test_ecm_saved={x=8,y=4,jamming=10,chance=chance,hp=jammer.hitpoints}
      check("save fixture bombing preview uses selected-target ECM", air.preview(1,"bombing",u("t_obs"),8,4).terms.jamming==10)
      air.call(1, "bombing", u("t_obs"), 8, 4)
      sw_prepare_ow_save()
      wml.variables.swt_digest = sw_systems.digest()
      std_print("SW_TEST: state prepared for save")
    end

    function S.myneyrshi_medic_reload_setup()
      local med=u("sw_test_native_medic_ranked")
      med.hitpoints,med.resting,med.attacks_left=10,false,0
      local ally=swt.place("sw_unit_wy_myneyrshi",1,22,12,"sw_test_native_medic_reloaded_ally")
      ally.hitpoints,ally.resting,ally.attacks_left=10,false,0
    end
    function S.myneyrshi_medic_reload_enemy_turn()
      check("reloaded medic waits for its normal healing turn", wesnoth.current.side==2
        and u("sw_test_native_medic_reloaded_ally").hitpoints==10)
    end
    function S.myneyrshi_medic_reload_check()
      check("actual reload retains functional native healing8 on next turn", wesnoth.current.side==1
        and u("sw_test_native_medic_reloaded_ally").hitpoints==18)
    end
    function S.load()
      sw_check_ow_reload()
      local med=u("sw_test_native_medic_ranked")
      check("actual reload retains native medic type and all three earned abilities", med and med.type=="sw_unit_wy_field_medic"
        and rank.of(med)==3 and med:matches{ability="sw_rank_hides"} and med:matches{ability="sw_rank_skirmisher"}
        and #sw_med_heals(med)==1 and sw_med_heals(med)[1]==8)
      check("actual reload retains exactly one native medic object per rank", med and swt.objects(med,"sw_rank_ability_1")==1
        and swt.objects(med,"sw_rank_ability_2")==1 and swt.objects(med,"sw_rank_ability_3")==1)
      local veteran = u("sw_test_wookiee_ranked")
      check("actual reload keeps all three earned Suppressor rank objects", veteran and rank.of(veteran) == 3
        and swt.objects(veteran, "sw_rank_ability_1") == 1 and swt.objects(veteran, "sw_rank_ability_2") == 1
        and swt.objects(veteran, "sw_rank_ability_3") == 1 and veteran:matches{ ability = "sw_rank_hit_aura" })
      local shooter, target, wk = u("sw_test_wookiee_normal"), u("sw_test_wookiee_target"), wml.variables.swt_wookiee_expected
      check("actual reload retains Suppressor profile and spent actions", shooter and wk and shooter.type == "sw_unit_wk_suppressor"
        and shooter.max_hitpoints == 34 and shooter.max_moves == 5 and shooter.x == 8 and shooter.y == 8
        and shooter.hitpoints == wk.hp and shooter.moves == wk.moves and shooter.attacks_left == wk.attacks)
      check("actual reload retains the native on-hit Slow snapshot", target and wk and wk.target_slowed and target.status.slowed
        and target.x == 10 and target.y == 8 and target.hitpoints == wk.target_hp and sw_wk_cost(target, 11, 8) == 2)
      local specials_ok, slow = true, false
      if shooter then
        for _, special in ipairs(shooter.attacks[sw_wk_idx(shooter, "bowcaster")].specials) do
          if special[1] == "slow" then slow = true end
          if special[2].id == "sw_test_wookiee_certainty" then specials_ok = false end
        end
      end
      check("actual reload restores the shipped Slow weapon without fixture certainty", specials_ok and slow)
      local soldier, saved = u("t_real_retreat"), wml.variables.swt_retreat_expected
      check("real reload registers the withdrawal replay command", type(wesnoth.custom_synced_commands.sw_ai_withdraw_stand_down) == "function")
      check("real reload retains withdrawn troop position, health and spent actions", soldier and saved
        and soldier.x == saved.x and soldier.y == saved.y and soldier.hitpoints == saved.hp
        and soldier.moves == saved.moves and soldier.attacks_left == saved.attacks)
      check("save/load: state identical after reload", wml.variables.swt_digest == sw_systems.digest())
      check("save/load: sorties kept", air.charges(1, "strafe") == 2 and air.charges(1, "bombing") == 0)
      check("save/load: inbound bombing kept", #wml.array_access.get("sw_air_inbound") == 1)
      local marked = 0
      for _j, it in ipairs(wesnoth.interface.get_items(8, 4)) do if it.image == "misc/sw-air-inbound.png" then marked = marked + 1 end end
      check("save/load: inbound marker kept", marked == 1)
      local c = u("t_obs")
      check("save/load: rank insignia kept", c and tostring(c.image_mods):find("sw%-rank%-republic%-2") ~= nil and rank.of(c) == 2)

      local queued=wml.array_access.get("sw_air_inbound")
      local e=wml.variables.sw_test_ecm_saved
      check("actual reload retains previously serialized strike target", #queued==1 and e and tonumber(queued[1].x)==e.x
        and tonumber(queued[1].y)==e.y and queued[1].target==nil)
      check("actual reload bombing preview measures ECM at saved target", e and air.preview(1,"bombing",c,e.x,e.y).terms.jamming==e.jamming)
    end
    function S.air_ecm_reload_check()
      local e=wml.variables.sw_test_ecm_saved
      local strike=swt.mem.strikes and swt.mem.strikes[1]
      local hit
      for _,r in ipairs(strike and strike.results or {}) do if r.id=="sw_test_ecm_saved_jammer" then hit=r end end
      check("actual reloaded bomb lands on ordinary next side turn", wesnoth.current.side==1 and strike
        and tonumber(strike.strike.x)==e.x and tonumber(strike.strike.y)==e.y
        and #wml.array_access.get("sw_air_inbound")==0)
      check("actual reloaded bomb rolls target-centered ECM chance", hit and hit.chance==e.chance,hit and hit.chance)
      check("actual reloaded bomb damage matches native hit rolls", hit and swt.damage_ok(hit.id,e.hp,9,hit.hits,"fire"))
    end

    function swt.step(name)
      local ok, err = pcall(S[name])
      if not ok then std_print("SW_TEST: FAIL " .. name .. " -- error: " .. tostring(err)) end
    end
  end)
  settle()

  local steps = PHASE == "main" and STEPS or { "load", "myneyrshi_medic_reload_setup", "myneyrshi_medic_reload_enemy_turn", "myneyrshi_medic_reload_check", "air_ecm_reload_check" }
  for _, name in ipairs(steps) do
    local step = name
    wesnoth.plugin.execute(context, function() swt.step(step) end)
    settle()
    if step == "myneyrshi_medic_recruit_setup" then
      context.synced_command{{ "recruit", { type="sw_unit_wy_field_medic", x=5, y=4, {"from",{x=4,y=4}} } }}
      settle()
    end
    if step == "myneyrshi_medic_heal_setup" or step == "myneyrshi_medic_upgrade_setup"
      or step == "myneyrshi_medic_enemy_turn" or step == "myneyrshi_medic_upgrade_enemy_turn"
      or step == "myneyrshi_medic_reload_setup" or step == "myneyrshi_medic_reload_enemy_turn" then
      context.end_turn{}
      local expected = (step == "myneyrshi_medic_heal_setup" or step == "myneyrshi_medic_upgrade_setup"
        or step == "myneyrshi_medic_reload_setup") and 2 or 1
      local g=0
      repeat settle(); g=g+1 until (info.name=="Game" and info.current_side and info.current_side()==expected) or g>50
    end
    if step == "wookiee_recruit_setup" then
      context.synced_command{{ "recruit", { type = "sw_unit_wk_suppressor", x = 5, y = 4,
        { "from", { x = 4, y = 4 } } } }}
      settle()
    end
    if step == "wookiee_check_hit" or step == "wookiee_check_return" then
      -- Both active fixture sides are human: explicitly end each native turn.
      context.end_turn{}
      local expected = step == "wookiee_check_hit" and 2 or 1
      local g = 0
      repeat settle(); g = g + 1
      until (info.name == "Game" and info.current_side and info.current_side() == expected) or g > 50
    end
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
  -- Checks and the real save are complete. The runner owns this disposable
  -- process and stops it after observing done; interactive quit is not tested.
  while true do
    events, context, info = wesnoth.plugin.next_slice()
  end
end
return plugin
