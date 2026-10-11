-- Drives the isolated native progression probe and its saved-game reload.
local SW_CAMPAIGN = "Star_Wars_Thrawn_Trilogy"
local SW_PHASE = "main"

local function plugin(events, context, info)
    local function pump()
        events, context, info = wesnoth.plugin.next_slice()
        if info.name == "Dialog" then context.skip_dialog{} end
        if info.name == "Campaign Configure" then context.launch{} end
    end
    local function settle()
        for _ = 1, 30 do pump() end
        local slices = 0
        repeat
            pump()
            slices = slices + 1
        until (info.name == "Game" and info.can_move().can_move) or slices > 200000
    end
    if SW_PHASE == "main" then
        events, context, info = wesnoth.plugin.wait_until("titlescreen")
        while info.name == "titlescreen" do
            context.play_campaign({})
            events, context, info = coroutine.yield()
        end
        events, context, info = wesnoth.plugin.wait_until("Campaign Selection")
        local selection = info.find_level{ id = SW_CAMPAIGN }
        context.select_level{ index = selection.index }
        events, context, info = wesnoth.plugin.next_slice()
        context.create{}
    end
    settle()
    if info.name ~= "Game" then
        std_print("SW_VET: FAIL setup missing game context")
        context.exit{ code = 3 }
        return
    end
    wesnoth.plugin.execute(context, function()
        wesnoth.interface.skip_messages(true)
        sw_vet = wesnoth.require("~add-ons/Star_Wars_Thrawn_Trilogy/lua/sw_veterancy_probe.lua")
    end)
    settle()
    local steps = SW_PHASE == "main" and {"eligibility", "training"} or {"load"}
    for _, name in ipairs(steps) do
        local step = name
        wesnoth.plugin.execute(context, function()
            local ok, err = pcall(sw_vet[step])
            if not ok then std_print("SW_VET: FAIL " .. step .. " -- " .. tostring(err)) end
        end)
        settle()
    end
    if SW_PHASE == "main" then
        context.save_game{ filename = "sw_veterancy_test_save" }
        settle()
        std_print("SW_VET: saved")
    end
    std_print("SW_VET: done " .. SW_PHASE)
    -- The runner owns this disposable process. Once checks/save are complete,
    -- keep the game idle until it terminates us; no UI shutdown is under test.
    while true do
        events, context, info = wesnoth.plugin.next_slice()
    end
end

return plugin
