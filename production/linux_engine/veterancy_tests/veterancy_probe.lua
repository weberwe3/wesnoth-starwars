-- Actual native AMLA probes. Only loaded into the staged test add-on.
-- LuaAPI units.advance drives all progression; no add_modification simulation.
local sw_vet = {}
local SW_WEAPONS = "sw_amla_weapons_drill"
local SW_MOBILITY = "sw_amla_mobility_drill"
local SW_DEFAULT = "amla_default"

function sw_vet.check(label, condition, detail)
    std_print("SW_VET: " .. (condition and "PASS " or "FAIL ") .. label ..
        ((not condition and detail ~= nil) and (" -- " .. tostring(detail)) or ""))
end

function sw_vet.place(type_id, id, x)
    wesnoth.wml_actions.unit{ type = type_id, id = id, x = x or 3, y = 3, side = 1,
        random_traits = false, generate_name = false }
    return wesnoth.units.get(id)
end

function sw_vet.config(u, choice)
    for _, cfg in ipairs(u.advancements) do
        if cfg.id == choice then return cfg end
    end
end

function sw_vet.count(u, choice)
    local mods = wml.get_child(u.__cfg, "modifications") or {}
    local count = 0
    for _, cfg in ipairs(wml.child_array(mods, "advancement")) do
        if cfg.id == choice then count = count + 1 end
    end
    return count
end

function sw_vet.snapshot(u)
    local attacks = {}
    for _, a in ipairs(u.attacks) do
        attacks[#attacks + 1] = table.concat({a.name, a.damage, a.number, a.range}, ":")
    end
    return table.concat({u.type, u.variation or "", u.max_hitpoints, u.hitpoints,
        u.max_moves, u.vision, u.max_experience, u.experience,
        tostring(u.status.poisoned), tostring(u.status.slowed),
        sw_vet.count(u, SW_WEAPONS), sw_vet.count(u, SW_MOBILITY),
        sw_vet.count(u, SW_DEFAULT), table.concat(attacks, ",")}, "|")
end

function sw_vet.choose(id, choice, label)
    local u = wesnoth.units.get(id)
    local full = u.advancements
    local config = assert(sw_vet.config(u, choice), "missing native choice " .. choice)
    local old_xp, old_count = u.max_experience, sw_vet.count(u, choice)
    -- Offer one unchanged config. The native engine, not this helper, checks
    -- strict_amla, max_times and XP before accepting it. Restore the menu later.
    u.advancements = {config}
    u.experience = old_xp + 4
    u.hitpoints = 1
    u.status.poisoned, u.status.slowed = true, true
    u:advance(false, true)
    u = assert(wesnoth.units.get(id), "native advancement lost unit")
    u.advancements = full
    sw_vet.check(label .. ": native choice recorded", sw_vet.count(u, choice) == old_count + 1)
    sw_vet.check(label .. ": native XP spent with carryover", u.experience == 4, u.experience)
    -- Installed unit::add_modification uses integer percent scaling; these
    -- positive values round +20% to the nearest integer, with halves upward.
    local expected_xp = math.floor(old_xp * 1.2 + 0.5)
    sw_vet.check(label .. ": XP requirement +20%", u.max_experience == expected_xp,
        tostring(u.max_experience) .. " expected " .. expected_xp)
    sw_vet.check(label .. ": full heal and poison/slow cure",
        u.hitpoints == u.max_hitpoints and not u.status.poisoned and not u.status.slowed)
    return u
end

function sw_vet.reject_capped(id, choice, label)
    local u = wesnoth.units.get(id)
    local full, old_experience = u.advancements, u.experience
    local config = assert(sw_vet.config(u, choice), "missing capped raw config")
    u.advancements = {config}
    u.experience = u.max_experience + 4
    local before = sw_vet.snapshot(u)
    -- A capped choice is not available: with no type promotion and no other
    -- AMLA offered, native advance must return without spending XP or effects.
    u:advance(false, true)
    u = wesnoth.units.get(id)
    sw_vet.check(label .. ": native cap rejects advance", sw_vet.snapshot(u) == before)
    u.advancements, u.experience = full, old_experience
end

function sw_vet.menu(u, label, expected)
    local weapons, mobility, default = sw_vet.config(u, SW_WEAPONS),
        sw_vet.config(u, SW_MOBILITY), sw_vet.config(u, SW_DEFAULT)
    if expected then
        sw_vet.check(label .. ": native definitions include both capped drills and default",
            weapons and mobility and default and tonumber(weapons.max_times) == 2
            and tonumber(mobility.max_times) == 1 and weapons.strict_amla and mobility.strict_amla)
    else
        sw_vet.check(label .. ": no military drills", not weapons and not mobility)
    end
end

function sw_vet.eligibility()
    local examples = {
        {"sw_unit_nr_sergeant", true}, {"sw_unit_im_tie_fighter", true},
        {"sw_unit_im_decon_droid", true}, {"sw_unit_wy_psadan", true},
        {"sw_unit_wy_myneyrshi", true}, {"sw_hero_luke", false},
        {"sw_unit_wl_vornskr", false}, {"sw_unit_ob_dreadnaught", false},
        {"sw_unit_ob_shield_generator", false}, {"sw_unit_nr_docked_warship", false},
        {"sw_unit_nr_trooper", false}, {"sw_unit_nr_militia", false},
    }
    for _, item in ipairs(examples) do
        local u = sw_vet.place(item[1], "sw_vet_eligibility")
        sw_vet.menu(u, item[1], item[2])
        u:erase()
    end
    -- New units keep exact base stats: drill effects require a real advance.
    local s = sw_vet.place("sw_unit_nr_sergeant", "sw_vet_base")
    sw_vet.check("fresh base stats unchanged", s.max_hitpoints == 50 and s.max_moves == 5
        and s.max_experience == 90 and s.attacks.rifle_butt.damage == 7
        and s.attacks.blaster_rifle.damage == 9 and s.attacks.blaster_rifle_aimed.damage == 9)
    local config = assert(sw_vet.config(s, SW_WEAPONS))
    s:erase()
    local trooper = sw_vet.place("sw_unit_nr_trooper", "sw_vet_promotion")
    trooper.advancements = {config}
    trooper.experience = trooper.max_experience
    trooper:advance(false, true)
    local promoted = wesnoth.units.get("sw_vet_promotion")
    sw_vet.check("native strict AMLA permits promotion instead of drill",
        promoted.type == "sw_unit_nr_sergeant" and sw_vet.count(promoted, SW_WEAPONS) == 0)
    sw_vet.menu(promoted, "promoted sergeant", true)
    promoted:erase()
end

function sw_vet.damage(u, bonus, label)
    local expected = {rifle_butt = 7 + bonus, blaster_rifle = 9 + bonus,
        blaster_rifle_aimed = 9 + bonus}
    local good = #u.attacks == 3
    for _, a in ipairs(u.attacks) do
        good = good and expected[a.name] == a.damage
    end
    sw_vet.check(label .. ": every offensive/aimed weapon exact damage", good)
    sw_vet.check(label .. ": strikes unchanged", u.attacks.rifle_butt.number == 2
        and u.attacks.blaster_rifle.number == 3 and u.attacks.blaster_rifle_aimed.number == 2)
end

function sw_vet.training()
    sw_vet.place("sw_unit_nr_sergeant", "sw_vet_trained")
    local u = sw_vet.choose("sw_vet_trained", SW_WEAPONS, "weapons I")
    sw_vet.damage(u, 1, "weapons I")
    sw_vet.check("weapons I: native post advance changes to rank II", u.variation == "rank2"
        and sw_systems.rank.amla_count(u) == 1 and sw_systems.rank.of(u) == 2, u.variation)
    sw_vet.menu(u, "rank II", true)
    sw_vet.check("weapons I: HP, movement and vision unchanged", u.max_hitpoints == 50
        and u.max_moves == 5 and u.vision == 5)
    u = sw_vet.choose("sw_vet_trained", SW_MOBILITY, "mobility")
    sw_vet.damage(u, 1, "mobility")
    sw_vet.check("mobility: +1 movement with vision unchanged", u.max_moves == 6 and u.vision == 5)
    sw_vet.check("mobility: native post advance changes to rank III", u.variation == "rank3"
        and sw_systems.rank.amla_count(u) == 2 and sw_systems.rank.of(u) == 3, u.variation)
    sw_vet.menu(u, "rank III", true)
    sw_vet.reject_capped("sw_vet_trained", SW_MOBILITY, "mobility cap")
    u = sw_vet.choose("sw_vet_trained", SW_WEAPONS, "weapons II")
    sw_vet.damage(u, 2, "weapons II")
    sw_vet.reject_capped("sw_vet_trained", SW_WEAPONS, "weapons cap")
    u = sw_vet.choose("sw_vet_trained", SW_DEFAULT, "default after drill caps")
    sw_vet.damage(u, 2, "default after drill caps")
    sw_vet.check("default after caps: only HP increases", u.max_hitpoints == 53
        and u.max_moves == 6 and u.vision == 5 and sw_systems.rank.amla_count(u) == 4)
    -- Rebuild applies the native modification list again: bonuses must not
    -- disappear or accumulate. Existing rank Lua uses native transform.
    u:transform(u.type, "rank2")
    sw_systems.rank.update(u)
    u = wesnoth.units.get("sw_vet_trained")
    sw_vet.damage(u, 2, "rank reapplication")
    sw_vet.check("rank reapplication: trained movement, vision, HP and counts retained",
        u.variation == "rank3" and u.max_hitpoints == 53 and u.max_moves == 6
        and u.vision == 5 and sw_vet.count(u, SW_WEAPONS) == 2
        and sw_vet.count(u, SW_MOBILITY) == 1 and sw_vet.count(u, SW_DEFAULT) == 1)
    -- Native rebuild must preserve transient injuries, rather than reheal
    -- whenever a persistent AMLA's heal effect is reapplied.
    u.hitpoints, u.experience = 17, 11
    u.status.poisoned, u.status.slowed = true, true
    u:rebuild()
    sw_vet.check("rebuild retains transient injury and XP", u.hitpoints == 17 and u.experience == 11)
    sw_vet.damage(u, 2, "rebuild")
    wml.variables.sw_vet_saved_digest = sw_vet.snapshot(u)
    -- Also save a unit below its drill caps; after load the remaining native
    -- choice must still advance and raise the correct rank/stat totals.
    sw_vet.place("sw_unit_nr_sergeant", "sw_vet_partial", 5)
    local partial = sw_vet.choose("sw_vet_partial", SW_WEAPONS, "partial before save")
    wml.variables.sw_vet_partial_digest = sw_vet.snapshot(partial)
end

function sw_vet.load()
    local u = assert(wesnoth.units.get("sw_vet_trained"), "save lost trained veteran")
    sw_vet.check("save/load: exact trained native state", sw_vet.snapshot(u) == wml.variables.sw_vet_saved_digest)
    sw_vet.menu(u, "save/load full menu", true)
    sw_vet.reject_capped(u.id, SW_WEAPONS, "save/load weapons cap")
    sw_vet.reject_capped(u.id, SW_MOBILITY, "save/load mobility cap")
    local partial = assert(wesnoth.units.get("sw_vet_partial"), "save lost partial veteran")
    sw_vet.check("save/load: exact partial native state", sw_vet.snapshot(partial) == wml.variables.sw_vet_partial_digest)
    partial = sw_vet.choose(partial.id, SW_WEAPONS, "remaining drill after load")
    sw_vet.damage(partial, 2, "remaining drill after load")
    sw_vet.check("save/load: remaining choice keeps native rank behavior",
        partial.variation == "rank3" and sw_systems.rank.amla_count(partial) == 2)
end

return sw_vet
