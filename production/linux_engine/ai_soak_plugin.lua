-- AI soak probe: enter one campaign (whose first_scenario the runner has
-- pointed at the scenario under test), hand side 1 to the AI, and let the
-- engine play turns until the scenario ends or the turn cap is reached.
-- Every turn-based event, reinforcement wave, hazard, and AI decision runs
-- for real. Output lines start with "SW_SOAK:".
-- run_ai_soak.py substitutes the campaign id and turn cap.
local CAMPAIGN = "Star_Wars_Thrawn_Trilogy"
local TURN_CAP = 30

-- Plugin accessors return a table; take its single value.
local function value_of(v)
  if type(v) ~= "table" then return v end
  for _, inner in pairs(v) do return inner end
end

local function plugin(events, context, info)
  local function out(t) std_print("SW_SOAK: " .. t) end
  local function pump()
    events, context, info = wesnoth.plugin.next_slice()
    if info.name == "Dialog" then context.skip_dialog{} end
    if info.name == "Campaign Configure" then context.launch{} end
  end

  events, context, info = wesnoth.plugin.wait_until("titlescreen")
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

  local guard = 0
  repeat pump(); guard = guard + 1 until (info.name == "Game" and info.can_move().can_move) or guard > 200000
  if info.name ~= "Game" then out("fatal no game context"); context.exit{code = 3}; return end

  local ok, err = wesnoth.plugin.execute(context, function()
    wesnoth.interface.skip_messages(true)
    std_print("SW_SOAK: scenario " .. wesnoth.scenario.id .. " turns " .. tostring(wesnoth.scenario.turns))
    -- With no human side left, the engine's generic victory check would end
    -- the level as soon as only allied sides remain (an enemy side waiting
    -- for event reinforcements counts as defeated). Only the scenario's own
    -- events may end it during a soak.
    for _, side in ipairs(wesnoth.sides) do side.defeat_condition = "never" end
    -- Log every death so an early defeat shows its cause in the evidence.
    wesnoth.game_events.add{
      name = "last breath", first_time_only = false,
      action = function()
        local ec = wesnoth.current.event_context
        local u = wesnoth.units.get(ec.x1, ec.y1)
        if u then
          std_print("SW_SOAK: died " .. tostring(u.id) .. " side " .. u.side .. " type " .. u.type
            .. " turn " .. wesnoth.current.turn)
        end
      end,
    }
    wesnoth.sides[1].controller = "ai"
  end)
  if ok == false then out("fatal execute refused " .. tostring(err)) end
  pump()
  if context.end_turn then context.end_turn{} end

  local last_turn, idle = 0, 0
  while true do
    pump()
    if info.name == "titlescreen" then out("result returned_to_titlescreen turn " .. last_turn); break end
    if info.name == "Game" then
      local okr, result = pcall(info.level_result)
      local okt, turn = pcall(info.turn)
      result, turn = value_of(result), tonumber(value_of(turn))
      if okt and turn and turn ~= last_turn then last_turn = turn; out("turn " .. turn) end
      if okr and result and result ~= "NONE" then out("result " .. result .. " turn " .. last_turn); break end
      if last_turn > TURN_CAP then out("result turn_cap turn " .. last_turn); break end
      -- If control comes back to the human interface (e.g. after an event),
      -- end the turn so the AI-controlled side keeps playing.
      if info.can_move().can_move then
        idle = idle + 1
        if idle % 25 == 0 and context.end_turn then context.end_turn{} end
      else
        idle = 0
      end
    end
  end
  out("done")
  while info.name ~= "titlescreen" do
    if info.name == "Dialog" then context.skip_dialog{} else context.quit{} end
    events, context, info = wesnoth.plugin.next_slice()
  end
  context.exit{code = 0}
end
return plugin
