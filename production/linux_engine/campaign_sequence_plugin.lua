-- Campaign-sequence probe for the Linux Wesnoth GUI harness.
--
-- Drives the real title screen into Campaign I, then for every scenario:
--   1. waits for a playable Game context,
--   2. reports the scenario id, side-1 heroes on the map, and stashed heroes,
--   3. saves the game (save/load evidence),
--   4. runs that scenario's scripted win path through real WML events
--      ([move_unit] with fire_event=yes, [kill] with fire_event=yes, or the
--      scenario's own named win event),
--   5. skips dialogs until the next scenario starts.
--
-- Output lines start with "SW_SEQ:" and are parsed by run_campaign_sequence.py.
-- This is a scripted functional check of event wiring, carryover, and
-- transitions. It does not prove that a human can reach the objectives by
-- legal moves; route probes cover that separately.

-- run_campaign_sequence.py substitutes the campaign id and final scenario.
local CAMPAIGN = "Star_Wars_Thrawn_Trilogy"
local FINAL_SCENARIO = "sw_hte_10_thrawns_gambit"

-- Win scripts run inside the game Lua kernel. Each returns nothing; WML
-- events triggered here end the level.
local function move(id, x, y)
  wesnoth.wml_actions.move_unit{id = id, to_x = x, to_y = y, fire_event = true, check_passability = false}
end
local function fire(name)
  wesnoth.wml_actions.fire_event{name = name}
end
local function kill_id(id)
  wesnoth.wml_actions.kill{id = id, fire_event = true, animate = false}
end

local WIN = {
  sw_hte_01_ysalamiri_harvest = function()
    for _, t in ipairs{{12, 4}, {21, 5}, {17, 13}, {23, 15}} do
      move("sw_hero_pellaeon", t[1], t[2])
      move("sw_hero_pellaeon", 3, 9)
    end
  end,
  sw_hte_02_ambush_at_bpfassh = function() move("sw_hero_leia", 25, 2) end,
  sw_hte_03_adrift = function() fire("sw_hte03_rescue") end,
  sw_hte_04_shadows_of_kashyyyk = function() fire("sw_hte04_win") end,
  sw_hte_05_prisoner_of_myrkr = function()
    move("sw_hero_luke", 6, 5)
    move("sw_hero_luke", 17, 9)
  end,
  sw_hte_06_raid_on_karrdes_base = function()
    local evac = 0
    for _, u in ipairs(wesnoth.units.find_on_map{side = 1, type = "sw_unit_sm_smuggler,sw_hero_karrde"}) do
      move(u.id, 27, 11)
      evac = evac + 1
    end
    move("sw_hero_han", 27, 8)
    move("sw_hero_lando", 27, 14)
  end,
  sw_hte_07_the_forest_crossing = function()
    move("sw_hero_luke", 28, 10)
    move("sw_hero_mara", 29, 10)
  end,
  sw_hte_08_nomad_city = function() kill_id("sw_hte08_harbid") end,
  sw_hte_09_sluis_van_shipyards = function()
    wml.variables.sw_hte09_last_wave = true
    for _, u in ipairs(wesnoth.units.find_on_map{type = "sw_unit_im_mole_miner"}) do
      kill_id(u.id)
    end
  end,
  sw_hte_10_thrawns_gambit = function() kill_id("sw_hte10_judicator") end,
  -- Campaign II
  sw_dfr_01_the_noghri_prisoner = function()
    local k = wesnoth.units.get("sw_hero_khabarakh")
    k.hitpoints = 5
    fire("sw_dfr01_check_capture")
  end,
  sw_dfr_02_honoghr = function() move("sw_hero_leia", 26, 9) end,
  sw_dfr_03_jomark = function() kill_id("sw_dfr03_raid_boss") end,
  sw_dfr_04_the_senators_men = function() move("sw_hero_han", 25, 2) end,
  sw_dfr_05_peregrines_nest = function() kill_id("sw_dfr05_commander") end,
  sw_dfr_06_the_mad_jedi = function()
    wesnoth.wml_actions.unit{side = 1, id = "sw_hero_mara", type = "sw_hero_mara", x = 24, y = 9}
    move("sw_hero_luke", 26, 9)
  end,
  sw_dfr_07_the_dark_force = function()
    local shuttle = wesnoth.units.find_on_map{side = 1, type = "sw_unit_nr_boarding_shuttle"}[1]
    for _, hex in ipairs{{10, 9}, {11, 5}, {11, 14}} do
      move(shuttle.id, hex[1], hex[2])
    end
  end,
  sw_dfr_08_aboard_the_katana = function()
    kill_id("sw_dfr08_clone_officer")
    move("sw_hero_luke", 24, 9)
  end,
  sw_dfr_09_battle_for_the_fleet = function()
    move("sw_dfr09_katana", 29, 11)
    move("sw_dfr09_dread_2", 29, 9)
  end,
  sw_dfr_10_honoghrs_choice = function() kill_id("sw_dfr10_commander") end,
  -- Campaign III
  sw_tlc_01_the_siege_of_coruscant = function()
    kill_id("sw_tlc01_minelayer_n")
    kill_id("sw_tlc01_minelayer_s")
  end,
  sw_tlc_02_the_smugglers_council = function() kill_id("sw_tlc02_commander") end,
  sw_tlc_03_the_palace_infiltrators = function()
    wml.variables.sw_tlc03_last_wave = true
    for _, u in ipairs(wesnoth.units.find_on_map{type = "sw_unit_im_infiltrator"}) do kill_id(u.id) end
  end,
  sw_tlc_04_landfall_on_wayland = function()
    move("sw_hero_luke", 25, 10)
    move("sw_hero_mara", 26, 10)
  end,
  sw_tlc_05_the_natives_of_wayland = function() kill_id("sw_tlc05_commander") end,
  sw_tlc_06_the_gates_of_tantiss = function() kill_id("sw_tlc06_generator") end,
  sw_tlc_07_the_cloning_vats = function()
    for _, u in ipairs(wesnoth.units.find_on_map{type = "sw_unit_ob_cloning_cylinder"}) do kill_id(u.id) end
  end,
  sw_tlc_08_the_throne_room = function()
    kill_id("sw_hero_luuke")
    kill_id("sw_hero_cbaoth")
  end,
  sw_tlc_09_bilbringi = function()
    local platforms = wesnoth.units.find_on_map{type = "sw_unit_ob_shipyard_platform"}
    for i = 1, 3 do kill_id(platforms[i].id) end
  end,
  sw_tlc_10_the_last_command = function() fire("sw_tlc10_the_end") end,
}

-- Legal-route checks: unit id -> target hexes it must be able to reach over
-- legal terrain (ignoring other units) within the scenario's turn limit.
-- Turns are counted with the unit's own movement costs, so terrain mistakes
-- (a forest hex a one-move hero cannot enter, a lake with no crossing) fail.
-- Flat strings because the engine cannot serialize nested tables into the
-- game kernel: "unit_id:x,y;x,y|unit_id:x,y".
local ROUTE_SPECS = {
  sw_hte_01_ysalamiri_harvest = "sw_hero_pellaeon:12,4;21,5;17,13;23,15",
  sw_hte_02_ambush_at_bpfassh = "sw_hero_leia:25,2",
  sw_hte_05_prisoner_of_myrkr = "sw_hero_luke:6,5;17,9",
  sw_hte_06_raid_on_karrdes_base = "sw_hero_han:27,8|sw_hero_karrde:27,11",
  sw_hte_07_the_forest_crossing = "sw_hero_luke:28,10|sw_hero_mara:28,10",
  sw_hte_08_nomad_city = "sw_hero_lando:4,9",
  sw_dfr_02_honoghr = "sw_hero_leia:26,9",
  sw_dfr_03_jomark = "sw_hero_luke:23,4",
  sw_dfr_04_the_senators_men = "sw_hero_han:25,2",
  sw_dfr_06_the_mad_jedi = "sw_hero_luke:26,9",
  sw_dfr_08_aboard_the_katana = "sw_hero_luke:23,9",
  sw_dfr_09_battle_for_the_fleet = "sw_dfr09_katana:29,11",
  sw_tlc_04_landfall_on_wayland = "sw_hero_luke:25,10|sw_hero_mara:26,10",
  sw_tlc_05_the_natives_of_wayland = "sw_hero_luke:21,10",
  sw_tlc_06_the_gates_of_tantiss = "sw_hero_han:23,10",
  sw_tlc_08_the_throne_room = "sw_hero_luke:16,8",
}

-- Turns a unit needs to walk a path, honoring per-turn movement points.
local function turns_for_path(u, path)
  local turns, left = 1, u.max_moves
  for i = 2, #path do
    local cost = wesnoth.units.movement_on(u, wesnoth.current.map[path[i]])
    if cost > u.max_moves then return nil end
    if cost > left then turns, left = turns + 1, u.max_moves end
    left = left - cost
  end
  return turns
end

local function check_routes(route_spec)
  for unit_part in string.gmatch(route_spec, "[^|]+") do
    local unit_id, hex_list = string.match(unit_part, "([^:]+):(.+)")
    local targets = {}
    for x, y in string.gmatch(hex_list, "(%d+),(%d+)") do table.insert(targets, {tonumber(x), tonumber(y)}) end
    local spec = {unit_id, targets}
    local u = wesnoth.units.get(spec[1])
    if not u then
      std_print("SW_SEQ: route " .. spec[1] .. " missing_unit")
    else
      local from = {u.x, u.y}
      for _, target in ipairs(spec[2]) do
        local path = wesnoth.paths.find_path(u, target[1], target[2], {ignore_units = true, ignore_teleport = true})
        local turns = (path and #path > 0) and turns_for_path(u, path) or nil
        std_print("SW_SEQ: route " .. spec[1] .. " " .. from[1] .. "," .. from[2] .. "->" .. target[1] .. "," .. target[2]
          .. " turns=" .. tostring(turns) .. " limit=" .. tostring(wesnoth.scenario.turns))
        if path and #path > 0 then from = target end
      end
    end
  end
end

local HEROES = {
  "sw_hero_luke", "sw_hero_leia", "sw_hero_han", "sw_hero_chewbacca", "sw_hero_lando",
  "sw_hero_mara", "sw_hero_karrde", "sw_hero_wedge", "sw_hero_pellaeon",
  "sw_hero_khabarakh", "sw_hero_cbaoth", "sw_hero_bel_iblis", "sw_hero_luuke",
}

local function plugin(events, context, info)
  local function out(t) std_print("SW_SEQ: " .. t) end
  local guard = 0
  local stuck = 0
  local function pump(want)
    -- Advance slices, skipping dialogs and configure screens.
    events, context, info = wesnoth.plugin.next_slice()
    guard = guard + 1
    if info.name == "Dialog" then context.skip_dialog{} end
    if info.name == "Campaign Configure" then context.launch{} end
    -- Linger mode after a victory: the map stays up with the player unable to
    -- move until "End Scenario" (the end-turn action) is pressed.
    if info.name == "Game" and not info.can_move().can_move then
      stuck = stuck + 1
      if stuck % 50 == 0 then context.end_turn{} end
    else
      stuck = 0
    end
    if guard > 400000 then out("fatal guard exceeded in " .. info.name); context.exit{code = 3} end
  end

  events, context, info = wesnoth.plugin.wait_until("titlescreen")
  local args = info.command_line().args or {}
  local tries = 0
  while info.name == "titlescreen" and tries < 100 do
    context.play_campaign({}); tries = tries + 1
    events, context, info = coroutine.yield()
  end
  events, context, info = wesnoth.plugin.wait_until("Campaign Selection")
  local s = info.find_level{id = CAMPAIGN}
  if s.index < 0 then out("fatal campaign not found"); context.exit{code = 2}; return end
  context.select_level({index = s.index})
  events, context, info = wesnoth.plugin.next_slice()
  context.create{}

  local seen = {}
  local last = nil
  for step = 1, 12 do
    repeat pump() until (info.name == "Game" and info.can_move().can_move) or info.name == "titlescreen"
    if info.name == "titlescreen" then out("campaign ended at titlescreen"); break end
    local scenario
    wesnoth.plugin.execute(context, function()
      wesnoth.interface.skip_messages(true)
      scenario = wesnoth.scenario.id
      local present, recall = {}, {}
      for _, id in ipairs(HEROES) do
        local u = wesnoth.units.get(id)
        if u then table.insert(present, id .. "=" .. u.type .. "@" .. u.x .. "," .. u.y .. ":xp" .. u.experience) end
        local r = wesnoth.units.find_on_recall{id = id}[1]
        if r then table.insert(recall, id) end
      end
      std_print("SW_SEQ: scenario " .. scenario .. " turn " .. wesnoth.current.turn)
      std_print("SW_SEQ: heroes_on_map " .. table.concat(present, ";"))
      std_print("SW_SEQ: heroes_on_recall " .. table.concat(recall, ";"))
      local stash = wml.array_access.get("sw_stashed_heroes")
      local ids = {}
      for _, v in ipairs(stash) do table.insert(ids, v.id) end
      std_print("SW_SEQ: stashed " .. table.concat(ids, ";"))
      std_print("SW_SEQ: units_on_map " .. #wesnoth.units.find_on_map{})
      std_print("SW_SEQ: side1_gold " .. wesnoth.sides[1].gold)
    end)
    pump()
    if scenario == last then out("fatal scenario did not advance from " .. tostring(scenario)); break end
    last = scenario
    context.save_game{filename = "sw_seq_" .. tostring(scenario)}
    pump()
    out("saved " .. tostring(scenario))
    local win = WIN[scenario]
    if not win then out("fatal no win script for " .. tostring(scenario)); break end
    local route_spec = ROUTE_SPECS[scenario] or ""
    local exec_ok, exec_err = wesnoth.plugin.execute(context, function()
      -- Legal-route check first, on the untouched opening position.
      local routes_ok, routes_err = pcall(check_routes, route_spec)
      if not routes_ok then std_print("SW_SEQ: route_error " .. tostring(routes_err)) end
      local ok, err = pcall(win)
      if not ok then std_print("SW_SEQ: win_script_error " .. tostring(err)) end
    end)
    if exec_ok == false then out("win_script_error execute refused: " .. tostring(exec_err)) end
    out("win script ran " .. scenario)
    -- Wait for the game to leave this scenario.
    local waited = 0
    repeat
      pump(); waited = waited + 1
      local still = false
      if info.name == "Game" and info.can_move().can_move then
        wesnoth.plugin.execute(context, function() still = (wesnoth.scenario.id == scenario) end)
      end
    until (not still and info.name ~= "Game") or waited > 20000 or info.name == "titlescreen"
    if waited > 20000 then out("fatal scenario " .. scenario .. " did not end") ; break end
    out("left " .. scenario .. " via " .. info.name)
    if scenario == FINAL_SCENARIO then break end
  end
  out("done")
  while info.name ~= "titlescreen" do
    if info.name == "Dialog" then context.skip_dialog{} else context.quit{} end
    events, context, info = wesnoth.plugin.next_slice()
  end
  context.exit{code = 0}
end
return plugin
