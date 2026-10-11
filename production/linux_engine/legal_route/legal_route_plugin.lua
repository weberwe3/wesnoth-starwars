-- Native, ordinary-command proof for Campaign I mission one. No game content,
-- unit properties, mission variables, or enemy controllers are modified here.
-- Default NORMAL difficulty uses ordinary campaign/combat RNG, not a human balance claim.
-- Installed seed_rng.cpp uses boost::random_device independently of CLI srand.
local FIRST = "sw_hte_01_ysalamiri_harvest"
local NEXT = "sw_hte_02_ambush_at_bpfassh"

local function plugin(events, context, info)
  local function idle()
    -- The runner owns shutdown. Interactive quit has separate, unproved behavior.
    while true do events, context, info = wesnoth.plugin.next_slice() end
  end
  local function pump()
    events, context, info = wesnoth.plugin.next_slice()
    if info.name == "Dialog" then context.skip_dialog{} end
    if info.name == "Campaign Configure" then context.launch{} end
    for _, e in ipairs(events or {}) do
      if e.name == "synced_command_error" then
        std_print('SW_ROUTE: {"event":"failure","reason":"native synced command error"}')
      end
    end
  end
  events, context, info = wesnoth.plugin.wait_until("titlescreen")
  context.play_campaign{}
  events, context, info = wesnoth.plugin.wait_until("Campaign Selection")
  local level = info.find_level{id = "Star_Wars_Thrawn_Trilogy"}
  if level.index < 0 then
    std_print('SW_ROUTE: {"event":"failure","reason":"campaign unavailable"}')
    std_print('SW_ROUTE: {"event":"done","success":false}')
    idle()
  end
  context.select_level{index = level.index}
  pump()
  context.create{}
  local initialized, ended = false, false
  while not ended do
    pump()
    if info.name == "Game" and info.can_move().can_move
        and info.current_side().current_side == 1 then
      local scenario
      wesnoth.plugin.execute(context, function()
        wesnoth.interface.skip_messages(true)
        scenario = wesnoth.scenario.id
      end)
      pump() -- execute queues work; the next slice returns updated upvalues.
      if scenario == NEXT then
        std_print('SW_ROUTE: {"event":"next_scenario","scenario":"' .. NEXT .. '"}')
        std_print('SW_ROUTE: {"event":"done","success":true}')
        ended = true
      elseif scenario ~= FIRST then
        std_print('SW_ROUTE: {"event":"failure","reason":"unexpected scenario"}')
        std_print('SW_ROUTE: {"event":"done","success":false}')
        ended = true
      else
        if not initialized then
          wesnoth.plugin.execute(context, function()
            sw_route = {jobs = {}, recruited = 0, negative = false, serial = 0,
              harvests = {}, deliveries = {}, completed = false, failed = false,
              trees = {{12,4}, {21,5}, {17,13}, {23,15}}, order = {4,2,3,1}}
            local r = sw_route
            local function json(v)
              if type(v) == "string" then
                return '"' .. v:gsub('[%z\1-\31\\"]', function(c)
                  return string.format('\\u%04x', string.byte(c))
                end) .. '"'
              elseif type(v) == "number" or type(v) == "boolean" then return tostring(v)
              elseif type(v) ~= "table" then return "null" end
              local out = {}
              if #v > 0 then
                for _, x in ipairs(v) do out[#out+1] = json(x) end
                return "[" .. table.concat(out, ",") .. "]"
              end
              local keys = {}; for k in pairs(v) do keys[#keys+1] = k end
              table.sort(keys)
              for _, k in ipairs(keys) do out[#out+1] = json(k) .. ":" .. json(v[k]) end
              return "{" .. table.concat(out, ",") .. "}"
            end
            function r.emit(event, fields)
              fields = fields or {}; fields.event = event
              fields.turn = wesnoth.current.turn
              std_print("SW_ROUTE: " .. json(fields))
            end
            function r.fail(reason)
              if not r.failed then r.emit("failure", {reason = reason}) end
              r.failed = true
            end
            function r.check(name, ok, fields)
              fields = fields or {}; fields.name = name; fields.ok = not not ok
              r.emit("check", fields)
              if not ok then r.fail(name) end
              return ok
            end
            function r.state(u)
              return {id = u.id, type = u.type, x = u.x, y = u.y, moves = u.moves,
                side = u.side, max_moves = u.max_moves, attacks_left = u.attacks_left,
                hitpoints = u.hitpoints, experience = u.experience,
                frame = not not u.variables.sw_frame, frame_tree = tonumber(u.variables.sw_frame_tree)}
            end
            function r.delivered() return tonumber(wml.variables.sw_hte01_delivered) or 0 end
            function r.xy(loc) return {loc.x or loc[1], loc.y or loc[2]} end
            function r.map_setup()
              local map = wesnoth.current.map
              r.width, r.height = map.playable_width, map.playable_height
              r.shuttle, r.component, r.shuttle_set = {}, {}, {}
              for y=1,r.height do for x=1,r.width do
                local code = map[{x,y}]
                if code == "Qkp" or code == "Qcp" then
                  local goal = {xy={x,y}, code=code}
                  r.shuttle[#r.shuttle+1] = goal; r.shuttle_set[x .. "," .. y] = true
                end
              end end
              table.sort(r.shuttle,function(a,b) return a.xy[1] == b.xy[1]
                and a.xy[2] < b.xy[2] or a.xy[1] < b.xy[1] end)
              local leader = wesnoth.units.get("sw_hero_pellaeon")
              if not leader or map[{leader.x,leader.y}] ~= "Qkp" then
                r.fail("actual keep is not the leader's native Qkp hex"); return
              end
              r.keep = {leader.x,leader.y}
              local seen, queue = {}, {{leader.x,leader.y}}
              seen[leader.x .. "," .. leader.y] = true
              local cursor=1
              while cursor <= #queue do
                local p=queue[cursor]; cursor=cursor+1
                local code=map[{p[1],p[2]}]; local terrain=wesnoth.terrain_types[code]
                r.component[#r.component+1]={xy=p,code=code,castle=terrain.castle or terrain.keep or false}
                if terrain.castle or terrain.keep then
                  for ny=1,r.height do for nx=1,r.width do
                    local key=nx .. "," .. ny; local other=wesnoth.terrain_types[map[{nx,ny}]]
                    if not seen[key] and (other.castle or other.keep)
                        and wesnoth.map.distance_between({p[1],p[2]},{nx,ny}) == 1 then
                      seen[key]=true; queue[#queue+1]={nx,ny}
                    end
                  end end
                end
              end
              table.sort(r.component,function(a,b) return a.xy[1] == b.xy[1]
                and a.xy[2] < b.xy[2] or a.xy[1] < b.xy[1] end)
              r.emit("route_map",{width=r.width,height=r.height,keep=r.keep,
                shuttle_goals=r.shuttle,recruit_component=r.component,
                recruit_requests={"sw_unit_im_scout_trooper","sw_unit_im_scout_trooper","sw_unit_im_scout_trooper"}})
              r.check("native shuttle and connected recruit component are valid",
                #r.shuttle > 0 and #r.component > 0 and seen[leader.x .. "," .. leader.y])
            end
            function r.terrain(u, actor_id)
              local points, added = {}, {}
              local function add(xy)
                local key=xy[1] .. "," .. xy[2]
                if not added[key] then added[key]=true; points[#points+1]=xy end
              end
              for _,xy in ipairs(r.trees) do add(xy) end
              for _,g in ipairs(r.shuttle) do add(g.xy) end
              for _,g in ipairs(r.component) do add(g.xy) end
              table.sort(points,function(a,b) return a[1] == b[1] and a[2] < b[2] or a[1] < b[1] end)
              for _, p in ipairs(points) do
                local code = wesnoth.current.map[{p[1],p[2]}]
                local t = wesnoth.terrain_types[code]
                r.emit("terrain", {actor = actor_id or u.id, type = u.type, x = p[1], y = p[2],
                  code = code, id = t.id, movement_alias = t.mvt_alias,
                  movement_cost = u:movement_on(code), max_moves = u.max_moves})
              end
            end
            function r.assign(u)
              local n = 0; for _ in pairs(r.jobs) do n = n+1 end
              if n < 4 then
                local index = r.order[n+1]
                r.jobs[u.id] = {index = index, done = false}
                r.emit("carrier", {actor = r.state(u), tree = index})
                r.terrain(u, u.id)
              end
            end
            function r.adjacent(a,b)
              return wesnoth.map.distance_between(a,b) == 1
            end
            function r.move_result(p)
              local u = wesnoth.units.get(p.actor)
              if not r.check("move actor survives immediate command", u ~= nil, {command = p.serial}) then return end
              local after = r.state(u)
              local prefix, cost = nil, 0
              for i, loc in ipairs(p.path) do
                if i > 1 then cost = cost + p.costs[i] end
                if u.x == loc[1] and u.y == loc[2] then prefix = i; break end
              end
              local spent = p.before.moves - after.moves
              local ok = prefix ~= nil and prefix > 1 and spent >= cost
                and spent <= p.before.moves and after.moves >= 0
              r.emit("move_result", {command = p.serial, before = p.before, after = after,
                path = p.path, step_costs = p.costs, reached_prefix = prefix or 0,
                native_path_cost = p.native_cost, terrain_cost_spent = cost,
                movement_spent = spent, legal_budget = ok})
              r.check("native move used contiguous affordable path", ok, {command = p.serial})
            end
            -- Read-only observers bracket the production objective handlers.
            wesnoth.game_events.add{id = "sw_route_before_move", name = "moveto",
              first_time_only = false, priority = 100, action = function()
                r.before_event = nil
                local ec = wesnoth.current.event_context
                local u = wesnoth.units.get(ec.x1,ec.y1)
                if u and u.side == 1 then
                  r.before_event = {actor = u.id, frame = not not u.variables.sw_frame,
                    index = tonumber(u.variables.sw_frame_tree), count = r.delivered(),
                    x = u.x, y = u.y}
                end
              end}
            wesnoth.game_events.add{id = "sw_route_after_move", name = "moveto",
              first_time_only = false, priority = -100, action = function()
                local b = r.before_event
                r.before_event = nil
                local u = b and wesnoth.units.get(b.actor)
                if not u then return end
                if not b.frame and u.variables.sw_frame then
                  local index = tonumber(u.variables.sw_frame_tree) + 1
                  local tree = r.trees[index]
                  r.check("natural harvest is on assigned tree", tree and u.x == tree[1]
                    and u.y == tree[2] and r.jobs[u.id] and r.jobs[u.id].index == index,
                    {actor = u.id, tree = index})
                  r.check("tree harvested once", not r.harvests[index], {tree = index})
                  r.harvests[index] = u.id
                  r.emit("harvest", {actor = u.id, tree = index, x = u.x, y = u.y,
                    frame = true, count = r.delivered()})
                elseif b.frame and not u.variables.sw_frame then
                  r.record_delivery(b, u)
                end
              end}
            function r.record_delivery(b,u)
              -- Endlevel can observe this same moveto before its late observer.
              -- Suppress only a repeated observation of this exact snapshot;
              -- a fresh event delivering the same tree still fails below.
              if b.delivery_recorded then return end
              b.delivery_recorded = true
              local index = b.index + 1
              local code = wesnoth.current.map[{b.x,b.y}]
              local count = r.delivered()
              r.check("natural delivery increases counter on shuttle terrain",
                (code == "Qkp" or code == "Qcp") and count == b.count + 1
                  and r.harvests[index] == b.actor and not r.deliveries[index],
                {actor = b.actor, tree = index, before_count = b.count, count = count, code = code})
              r.deliveries[index] = b.actor
              if r.jobs[b.actor] then r.jobs[b.actor].done = true end
              r.emit("delivery", {actor = b.actor, tree = index, x = b.x, y = b.y,
                code = code, count = count, frame = u and not not u.variables.sw_frame or false})
            end
            wesnoth.game_events.add{id = "sw_route_all_delivered", name = "sw_hte01_all_delivered",
              first_time_only = false, priority = 100, action = function()
                -- Fourth delivery enters endlevel before the late moveto observer.
                local b = r.before_event
                if b and b.frame and not r.deliveries[b.index+1] then
                  r.record_delivery(b, wesnoth.units.get(b.actor))
                end
                if r.pending and r.pending.kind == "move" then
                  r.move_result(r.pending)
                  r.pending = nil
                end
                local states, all = {}, true
                local trees = wml.array_access.get("sw_hte01_trees")
                for i=1,4 do
                  states[i] = trees[i] and trees[i].state or "missing"
                  all = all and states[i] == "delivered" and r.harvests[i] ~= nil
                    and r.deliveries[i] ~= nil
                end
                r.check("normal all-delivered event observes four real deliveries", all
                  and r.delivered() == 4 and r.negative and not r.failed, {states = states})
                r.completed = all and not r.failed
                r.emit("all_delivered", {count = r.delivered(), states = states})
              end}
            wesnoth.game_events.add{id = "sw_route_victory", name = "victory",
              first_time_only = false, priority = 100, action = function()
                r.check("normal victory follows all-delivered event", r.completed)
                r.emit("victory", {count = r.delivered(), scenario = wesnoth.scenario.id})
              end}
            wesnoth.game_events.add{id = "sw_route_defeat", name = "defeat",
              first_time_only = false, priority = 100, action = function()
                r.fail("ordinary campaign defeat; this bounded policy did not prove a route")
              end}
            wesnoth.game_events.add{id = "sw_route_death", name = "die",
              first_time_only = false, priority = 100, action = function()
                local ec = wesnoth.current.event_context
                local u = wesnoth.units.get(ec.x1,ec.y1)
                if u then r.emit("unit_death", {actor=r.state(u), carrier=r.jobs[u.id] ~= nil}) end
              end}
            local function plain(value, depth)
              depth = depth or 0
              if depth > 64 then error("negative snapshot nesting limit exceeded") end
              local kind = type(value)
              if kind == "nil" or kind == "boolean" or kind == "number" or kind == "string" then return value end
              if kind ~= "table" then return tostring(value) end
              local out = {}
              for k,v in pairs(value) do
                if type(k) == "string" or type(k) == "number" then
                  out[#out+1] = {key_type=type(k),key=k,value=plain(v,depth+1)}
                end
              end
              table.sort(out,function(a,b) return a.key_type == b.key_type and a.key < b.key
                or a.key_type < b.key_type end)
              return out
            end
            function r.snapshot(actor)
              local units = wesnoth.units.find_on_map{}
              table.sort(units,function(a,b) return a.id == b.id and a.side < b.side or a.id < b.id end)
              local states={}; for _,u in ipairs(units) do
                local state=r.state(u); state.side=u.side
                local cfg=u.__cfg
                state.variables=plain(wml.get_child(cfg,"variables") or {})
                state.status=plain(wml.get_child(cfg,"status") or {})
                states[#states+1]=state
              end
              local trees=plain(wml.array_access.get("sw_hte01_trees") or {})
              return {actor=actor and r.state(actor),units=states,gold=wesnoth.sides[1].gold,
                delivered=r.delivered(),trees=trees,objectives=plain(wml.variables.objectives or ""),
                frame_tree=plain(wml.variables.sw_frame_tree)}
            end
            function r.finish_pending()
              local p = r.pending; r.pending = nil
              if not p then return end
              if p.kind == "illegal" then
                local a=wesnoth.units.get(p.actor)
                local after=r.snapshot(a)
                local ok=p.before and json(p.before)==json(after)
                r.emit("illegal_result",{before=p.before,after=after,unchanged=not not ok})
                r.negative=r.check("identical-coordinate native command preserves complete opening state",ok)
              elseif p.kind == "move" then r.move_result(p)
              elseif p.kind == "recruit" then
                local u = wesnoth.units.get(p.x,p.y)
                local ok = u and u.side == 1 and u.type == "sw_unit_im_scout_trooper"
                  and not p.before_ids[u.id] and u.moves == 0 and u.attacks_left == 0
                  and wesnoth.sides[1].gold == p.gold - p.cost
                r.check("native paid scout recruitment", ok, {before_gold = p.gold,
                  after_gold = wesnoth.sides[1].gold, cost = p.cost,
                  side=u and u.side,type=u and u.type,x=u and u.x,y=u and u.y,
                  id=u and u.id,moves=u and u.moves,attacks_left=u and u.attacks_left,
                   max_moves=u and u.max_moves})
                if ok then r.recruited = r.recruited + 1; r.assign(u) end
              elseif p.kind == "attack" then
                local u, enemy = wesnoth.units.get(p.actor), wesnoth.units.get(p.enemy)
                r.emit("attack_result", {before = p.before, enemy_before = p.enemy_before,
                  after = u and r.state(u), enemy_after = enemy and r.state(enemy), weapon = p.weapon})
                r.check("native combat consumes ordinary attack", not u or u.attacks_left < p.before.attacks_left)
              end
            end
            function r.plan()
              r.finish_pending()
              if r.failed then return {kind = "stop"} end
              if wesnoth.current.turn > wesnoth.scenario.turns then
                r.fail("native turn cap exceeded"); return {kind = "stop"}
              end
              local units = wesnoth.units.find_on_map{side = 1}
              table.sort(units, function(a,b) return a.id < b.id end)
              if not r.negative then
                local a=units[1]
                if not a then r.fail("no opening side-one actor"); return {kind="stop"} end
                r.pending={kind="illegal",actor=a.id,before=r.snapshot(a)}
                r.emit("illegal_request",{actor=r.state(a),coordinates={a.x,a.y,a.x,a.y}})
                return {kind="move",xs=a.x .. "," .. a.x,ys=a.y .. "," .. a.y}
              end
              local leader = wesnoth.units.get("sw_hero_pellaeon")
              if not leader then r.fail("leader lost"); return {kind = "stop"} end
              if r.recruited < 3 then
                local cost = wesnoth.unit_types.sw_unit_im_scout_trooper.cost
                if wesnoth.current.map[{leader.x,leader.y}] ~= "Qkp" then
                  r.fail("opening leader is not on native shuttle keep"); return {kind = "stop"}
                end
                for _, goal in ipairs(r.component) do
                  local hex=goal.xy
                  if (goal.castle or goal.code == "Qkp" or goal.code == "Qcp")
                      and not wesnoth.units.get(hex[1],hex[2]) and wesnoth.sides[1].gold >= cost then
                    local before_ids={}
                    for _,existing in ipairs(wesnoth.units.find_on_map{}) do before_ids[existing.id]=true end
                    r.pending = {kind = "recruit", x = hex[1], y = hex[2],
                      gold = wesnoth.sides[1].gold, cost = cost, before_ids=before_ids}
                    r.emit("recruit_request", {x = hex[1], y = hex[2], leader = r.state(leader),
                      gold = wesnoth.sides[1].gold, cost = cost,
                      type="sw_unit_im_scout_trooper"})
                    return {kind = "recruit", x = hex[1], y = hex[2], fx = leader.x, fy = leader.y}
                  end
                end
              end
              local enemies = {}
              for _, e in ipairs(wesnoth.units.find_on_map{side = 2}) do
                if e:matches{wml.tag.filter_vision{side = 1, visible = true}} then
                  enemies[#enemies+1] = e
                end
              end
              table.sort(enemies,function(a,b) return a.id < b.id end)
              -- Reconsider legal fire after each command, before spending more
              -- movement near wildlife. Ordinary attacks and retaliation remain real.
              for _, u in ipairs(units) do
                if u.attacks_left > 0 then
                  for _, e in ipairs(enemies) do
                    local distance = wesnoth.map.distance_between(u,e)
                    for index, attack in ipairs(u.attacks) do
                      if attack.range == "ranged" and distance >= attack.min_range
                          and distance <= attack.max_range then
                        r.pending = {kind = "attack", actor = u.id, enemy = e.id,
                          before = r.state(u), enemy_before = r.state(e), weapon = index-1}
                        r.emit("attack_request", {actor = r.state(u), enemy = r.state(e),
                          weapon = index-1, distance = distance})
                        return {kind = "attack", x = u.x, y = u.y, tx = e.x, ty = e.y, weapon = index-1}
                      end
                    end
                  end
                end
              end
              -- Each carrier follows an ordinary native reachable path. Visible
              -- wildlife risk only chooses among legal endpoints; AI turns stay real.
              for _, u in ipairs(units) do
                local job = r.jobs[u.id]
                local code = wesnoth.current.map[{u.x,u.y}]
                local parking = job and job.done and (code == "Qkp" or code == "Qcp")
                local escort = not job and not u.canrecruit
                if (job and (not job.done or parking) or escort) and u.moves > 0 then
                  -- Delivered carriers clear the limited apron through ordinary
                  -- moves so the remaining carriers can reach shuttle terrain.
                  local goals = {}
                  if escort then
                    for _, e in ipairs(enemies) do goals[#goals+1] = {xy={e.x,e.y}} end
                    if #goals == 0 then
                      for _, carrier in ipairs(units) do
                        local assigned = r.jobs[carrier.id]
                        if assigned and not assigned.done then
                          goals[#goals+1] = {xy={carrier.x,carrier.y}}
                        end
                      end
                    end
                  elseif not parking then
                    goals = u.variables.sw_frame and r.shuttle or {{xy=r.trees[job.index]}}
                  end
                  local function endpoint_score(x,y)
                    local distance = 999
                    if parking then distance=0
                    else for _, goal in ipairs(goals) do
                      local d = wesnoth.map.distance_between({x,y},goal.xy or goal)
                      -- Escorts close to ordinary blaster range, then fire on
                      -- the next plan call rather than standing at the shuttle.
                      if escort and #enemies > 0 then d = math.max(0,d-2) end
                      distance = math.min(distance,d)
                    end end
                    local risk = 0
                    for _, e in ipairs(enemies) do
                      local d = wesnoth.map.distance_between({x,y},e)
                      if d <= 1 then risk=risk+12 elseif d <= 2 then risk=risk+4 end
                    end
                    return distance*4+risk
                  end
                  local current_score = endpoint_score(u.x,u.y)
                  local best
                  for _, loc in ipairs(wesnoth.paths.find_reach(u, {ignore_teleport = true})) do
                    local x,y = loc[1],loc[2]
                    if (x ~= u.x or y ~= u.y) and not wesnoth.units.get(x,y) then
                      local path,cost = wesnoth.paths.find_path(u,x,y,{ignore_teleport = true})
                      local target_code=wesnoth.current.map[{x,y}]
                      local native_cost=u:movement_on(target_code)
                      local playable=x >= 1 and x <= r.width and y >= 1 and y <= r.height
                      local parking_legal = not parking or (playable and target_code ~= "Qkp"
                        and target_code ~= "Qcp" and native_cost > 0 and native_cost <= u.moves)
                      if parking_legal and path and #path > 1 and cost <= u.moves then
                        local score = parking and (cost*100 + wesnoth.map.distance_between({x,y},r.keep)) or endpoint_score(x,y)
                        -- A non-improving move used to cycle between equally
                        -- scored hexes until the carrier exhausted its budget.
                        if (parking or score < current_score) and (not best or score < best.score or (score == best.score and cost < best.cost)
                            or (score == best.score and cost == best.cost and (x < best.x
                              or x == best.x and y < best.y))) then
                          best = {x = x, y = y, path = path, cost = cost, score = score}
                        end
                      end
                    end
                  end
                  if best then
                    r.serial = r.serial+1
                    local path, costs, xs, ys = {}, {0}, {}, {}
                    for i, loc in ipairs(best.path) do
                      path[i] = {loc[1],loc[2]}; xs[i] = tostring(loc[1]); ys[i] = tostring(loc[2])
                      if i > 1 then costs[i] = u:movement_on(wesnoth.current.map[{loc[1],loc[2]}]) end
                    end
                    r.pending = {kind = "move", actor = u.id, before = r.state(u),
                      path = path, costs = costs, native_cost = best.cost, serial = r.serial,
                      purpose = parking and "parking" or escort and "escort" or "objective", endpoint = {best.x,best.y}}
                    r.emit("move_request", {command = r.serial, actor = r.state(u), path = path,
                      step_costs = costs, native_path_cost = best.cost, tree = job and job.index,
                      purpose = parking and "parking" or escort and "escort" or "objective", endpoint = {best.x,best.y},
                      before_score = current_score, endpoint_score = best.score})
                    return {kind = "move", xs = table.concat(xs,","), ys = table.concat(ys,",")}
                  end
                end
              end
              for id, job in pairs(r.jobs) do
                if not job.done and not wesnoth.units.get(id) then
                  r.fail("carrier lost during ordinary enemy turns"); return {kind = "stop"}
                end
              end
              r.emit("end_turn", {difficulty = wesnoth.scenario.difficulty, cap = wesnoth.scenario.turns,
                count = r.delivered(), enemies = #enemies, units = #units,
                snapshot = r.snapshot()})
              return {kind = "end_turn"}
            end
            r.emit("entered", {scenario = wesnoth.scenario.id, difficulty = wesnoth.scenario.difficulty,
              cap = wesnoth.scenario.turns, gold = wesnoth.sides[1].gold})
            r.check("untouched normal opening and objective state", wesnoth.current.turn == 1
              and wesnoth.scenario.difficulty == "NORMAL" and wesnoth.scenario.turns == 16
              and r.delivered() == 0)
            r.map_setup()
            local units = wesnoth.units.find_on_map{side = 1}
            table.sort(units,function(a,b) return a.id < b.id end)
            for _, u in ipairs(units) do
              r.emit("opening_unit", r.state(u)); r.terrain(u)
              if u.type == "sw_unit_im_scout_trooper" then r.assign(u) end
            end
          end)
          pump()
          initialized = true
        end
        -- This engine's execute copyback mishandles nil scalar upvalues.
        -- Keep the transported upvalue a non-nil config table; optional keys
        -- remain absent and commands retain their ordinary native semantics.
        local sw_command = {}
        wesnoth.plugin.execute(context, function()
          sw_command = sw_route.plan()
        end)
        pump()
        local kind, xs, ys = sw_command.kind, sw_command.xs, sw_command.ys
        local x,y,fx,fy,tx,ty,weapon = sw_command.x,sw_command.y,sw_command.fx,
          sw_command.fy,sw_command.tx,sw_command.ty,sw_command.weapon
        if kind == "move" then
          if xs and ys and xs:find(",",1,true) and xs:match("^([^,]+),([^,]+)$")
              and ys:match("^([^,]+),([^,]+)$") then
            local sx,dx=xs:match("^([^,]+),([^,]+)$"); local sy,dy=ys:match("^([^,]+),([^,]+)$")
            if sx==dx and sy==dy then
              context.synced_command{{"move",{x=sx,y=sy}}}
            else context.synced_command{{"move",{x=xs,y=ys}}} end
          else context.synced_command{{"move",{x=xs,y=ys}}} end
        elseif kind == "recruit" then
          context.synced_command{{"recruit",{type="sw_unit_im_scout_trooper",x=x,y=y,{"from",{x=fx,y=fy}}}}}
        elseif kind == "attack" then
          context.synced_command{{"attack",{weapon=weapon,{"source",{x=x,y=y}},{"destination",{x=tx,y=ty}}}}}
        elseif kind == "end_turn" then context.end_turn{}
        elseif kind == "stop" then
          std_print('SW_ROUTE: {"event":"done","success":false}')
          ended = true
        end
      end
    elseif initialized and info.name == "titlescreen" then
      std_print('SW_ROUTE: {"event":"failure","reason":"campaign left before required transition"}')
      std_print('SW_ROUTE: {"event":"done","success":false}')
      ended = true
    end
  end
  idle()
end
return plugin
