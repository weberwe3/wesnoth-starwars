# Wesnoth Star Wars Total Conversion - Project Scope and Feature Set

**Status:** Living project reference  
**Baseline date:** 2026-09-03  
**Repository:** `wesnoth-starwars`  
**Engine target:** Battle for Wesnoth 1.19.27 development generation, with forward compatibility toward 1.20.

## 1. Purpose

This project is an original fan total conversion for Battle for Wesnoth inspired by the broad post-Return of the Jedi setting and high-level plot concepts associated with Timothy Zahn's Thrawn trilogy. It is intended to deliver a complete, serious-toned tactical campaign experience while remaining an original implementation.

The project must not copy copyrighted prose, dialogue, art, music, audio, proprietary game assets, or other expressive content from Star Wars books, films, television, games, or licensed products. Story adaptation is limited to broad characters, settings, relationships, and plot concepts as directed by the project owner; all implementation, dialogue, mission scripting, art direction, UI treatment, rules, and supporting material must be original.

## 2. Product Vision

Create a polished three-campaign total conversion that feels purpose-built for Star Wars tactical combat rather than a cosmetic reskin of Wesnoth. The game should combine ground warfare, heroes, squads, vehicles, special missions, off-map air support, and space-combat scenarios within one coherent ruleset.

The intended tone is serious, military, dark, and painterly. The project should avoid cartoonish presentation and avoid mechanics that make Star Wars combat feel like standard medieval fantasy with renamed units.

## 3. Campaign Scope

The planned campaign set is:

1. **Campaign I - Heir to the Empire**
2. **Campaign II - Dark Force Rising**
3. **Campaign III - The Last Command**

Target total size is approximately **25-30 playable missions** across the trilogy. Mission count may move as pacing and production needs become clearer, but the project is intended to be a full-length trilogy rather than a short demonstration.

Indicative production milestones:

- Proof of concept: 3-5 missions.
- Vertical slice: 6-8 missions demonstrating the core systems and visual language.
- First complete campaign: approximately 10-12 missions.
- Trilogy completion: approximately 25-30 missions, followed by dedicated balance, UX, compatibility, visual, and audio polish.

## 4. Current Implemented Foundation

### 4.1 Repository and agent-development foundation

The repository has a deterministic multi-agent development pipeline with isolated Git worktrees and ticket branches. LLM workers do not directly control `main`.

Implemented infrastructure includes:

- Hardened OpenCode agent definitions.
- Deterministic Python coordinator.
- Bounded ticket runner.
- Provider preflight checks.
- Isolated per-ticket branch and worktree creation.
- Allowed-path enforcement.
- Protected-path enforcement.
- Static file validation.
- Wesnoth add-on static validation profile.
- Independent tester stage.
- Primary reviewer with controlled fallback reviewer.
- Fail-closed behavior.
- Structured task logs and result JSON.
- No automatic commit or merge during ticket execution.
- Retry handling concept for transient malformed provider/tool-generation responses.
- Secure Windows-to-WSL credential forwarding using DPAPI-backed Windows storage.

### 4.2 Initial game foundation - ENGINE-001

The first game-content foundation has been created and merged to `main`.

Canonical add-on root:

`addons/Star_Wars_Thrawn_Trilogy/`

Initial files/directories:

- `_main.cfg`
- `README.md`
- `translations/README.md`
- `scenarios/README.md`
- `units/README.md`
- `utils/README.md`
- `lua/README.md`

The initial `_main.cfg` contains only the add-on textdomain directive and top-level `[textdomain]` registration. It deliberately does not yet register a campaign, scenario, binary path, unit definitions, Lua modules, or utility includes.

The foundation passed:

- deterministic path-scope enforcement;
- static text checks;
- strengthened Wesnoth add-on structure checks;
- tester review;
- independent reviewer approval; and
- preprocessing by the installed Battle for Wesnoth 1.19.27 executable with exit code 0.

## 5. Gameplay Feature Set

### 5.1 Unit scale

The total conversion uses a mixed representational scale appropriate to Star Wars combat:

- Major heroes and named characters: individual units.
- Infantry: squad-level logical units.
- Small and medium vehicles: oversized single-hex units where practical.
- Very large walkers such as AT-ATs: oversized or scripted set-piece representation rather than true multi-hex occupancy.
- Space fighters: squadron-level units in space scenarios.
- Millennium Falcon and similarly distinctive craft: individual units.
- Capital ships: oversized or scenario/set-piece representations where required.

True multi-hex unit occupancy is intentionally avoided unless future engine capability makes it reliable enough for production.

### 5.2 Ground combat

Ground scenarios are expected to support:

- infantry squads;
- heroes and specialists;
- armored and transport vehicles;
- walkers and heavy set-piece units;
- ranged combat with meaningful distance bands;
- terrain and cover interactions;
- faction-specific tactical identities;
- mission objectives beyond simple elimination;
- reinforcements and scripted battlefield events;
- hero survival and narrative state where appropriate.

Wesnoth 1.19/1.20 native `min_range`/`max_range` capabilities may be used, supplemented by custom WML/Lua where native UI or AI behavior is insufficient.

### 5.3 Ground-air integration

Fast fixed-wing/spacecraft support in ground scenarios should generally be represented as **off-map sorties** rather than ordinary map units. Intended examples include X-wing, TIE, and bomber strikes.

On-map atmospheric craft may include slower/tactically persistent units such as speeders or gunships where their presence creates useful map gameplay.

### 5.4 Space combat

Dedicated space scenarios will use a tactical abstraction distinct from ground combat:

- fighter and interceptor squadrons;
- bomber squadrons;
- named individual craft where narratively important;
- capital ships as large units or scenario structures/set pieces;
- objectives involving screening, interception, escort, assault, survival, positioning, and timed events;
- faction-specific maneuver and firepower identities.

### 5.5 Heroes and named characters

Named characters should feel mechanically distinct without becoming mandatory instant-win units. Character design should emphasize role, battlefield identity, survivability expectations, unique abilities, command influence, and narrative consequences.

### 5.6 Ranged combat model

The project targets Wesnoth's development-generation range functionality, including native `min_range` and `max_range` where useful. Native engine support is treated as enforcement infrastructure, not necessarily a complete player experience. Custom WML/Lua may provide:

- clearer range visualization;
- targeting assistance;
- AI decision support;
- specialized weapon behaviors;
- range-dependent combat modifiers;
- scenario-specific firing rules.

### 5.7 Abilities and defensive systems

The 1.19/1.20 generation's WML/Lua capabilities, including `[defense]` ability support where appropriate, may underpin systems such as cover, shields, special defensive profiles, suppression-like effects, command effects, or faction-specific mechanics. Mechanics must be evaluated for clarity, AI compatibility, and balance before becoming global systems.

## 6. Faction and Content Direction

The project is expected to include major New Republic, Imperial, independent, criminal, local, and special-purpose forces required by the campaign narrative. Each faction should have recognizable tactical identity rather than relying only on visual differences.

Faction implementation should consider:

- unit roles and counters;
- weapon families;
- movement profiles;
- armor/defense behavior;
- morale/leadership analogues where useful;
- hero interaction;
- vehicles and support assets;
- progression and scenario availability.

Exact rosters remain subject to staged design tickets and balance testing.

## 7. Mission Design Requirements

Campaign missions should vary substantially in objective and structure. The design toolkit should support:

- conventional battles;
- defensive holds;
- assaults;
- escorts;
- extractions;
- infiltrations;
- ambushes;
- timed objectives;
- survival missions;
- vehicle-heavy engagements;
- air-support missions;
- space battles;
- scripted set pieces;
- branching or state-dependent outcomes where production cost is justified.

Narrative exposition should be concise and original. Mission scripting should prioritize playable decisions over passive exposition.

## 8. User Interface and Presentation

The project may use full add-on GUI2 themes and custom interface elements where useful. UI work should prioritize:

- range clarity;
- weapon identity;
- unit-role readability;
- scenario objectives;
- special ability state;
- faction distinction;
- space-versus-ground mode clarity;
- minimal friction for players unfamiliar with custom mechanics.

Any custom interface must remain maintainable across the targeted Wesnoth engine generation.

## 9. Art and Audio Direction

Visual direction:

- serious;
- dark/painterly;
- military science-fiction atmosphere;
- readable at Wesnoth tactical scale;
- original assets only;
- no extraction or reuse of copyrighted franchise art or game assets.

Audio direction follows the same original-content rule. No copyrighted score, dialogue, effects, or proprietary audio assets may be copied into the project.

## 10. Technical Target

Primary development target:

- Battle for Wesnoth 1.19.27 development build currently installed on KillDozer.
- Forward target: Wesnoth 1.20 generation.
- WML and Lua are the primary game scripting technologies.
- Python is used for deterministic development orchestration, not runtime gameplay.

The project should prefer engine-native behavior when it is reliable and comprehensible, while using custom WML/Lua to fill UI, AI, or rules gaps.

## 11. Quality Gates

No feature is considered complete merely because an LLM reports success. Relevant work must pass deterministic and/or engine-backed checks appropriate to its risk.

Expected gates include:

- file scope enforcement;
- protected path enforcement;
- static text and encoding checks;
- WML structure checks;
- Python tests for orchestration code;
- independent tester evaluation;
- independent reviewer evaluation;
- Wesnoth preprocessing/parse checks;
- scenario launch checks once scenarios exist;
- `--validate-addon` or equivalent engine validation when meaningful;
- functional playtesting for gameplay changes;
- GitHub CI checks after GitHub integration;
- pull-request review before protected `main` is updated.

## 12. GitHub Integration Scope

GitHub becomes the remote collaboration and audit layer, not a replacement for the local coordinator.

Planned repository workflow:

1. `main` is the protected source of truth.
2. Every ticket runs locally in an isolated `agent/<ticket>-<timestamp>` branch/worktree.
3. Local deterministic and model-review gates run first.
4. A successful ticket is committed to its ticket branch.
5. The branch is pushed to GitHub.
6. A pull request is created with ticket metadata, validation evidence, and change summary.
7. GitHub Actions runs repository-safe checks.
8. Required GitHub checks and review policy must pass.
9. Only then is the pull request merged to protected `main`.
10. Local `main` is synchronized and the completed worktree/branch is cleaned up.

Direct routine pushes to `main` should be eliminated once branch protection is enabled.

## 13. Development Priorities

Near-term priorities:

1. Complete GitHub integration and branch-protection workflow.
2. Make the project references mandatory for all LLM agents.
3. Add automatic local Wesnoth preprocessing as a deterministic engine gate.
4. Create `ENGINE-002`: minimal campaign and first launchable scenario registration.
5. Establish scenario launch validation.
6. Build the first vertical slice systems incrementally rather than attempting the entire trilogy at once.

## 14. Definition of Project Success

The project succeeds when it delivers a stable, coherent, original three-campaign Star Wars tactical experience that:

- runs reliably on the targeted Wesnoth generation;
- feels mechanically distinct from stock medieval Wesnoth;
- communicates its custom systems clearly;
- remains maintainable by the agent-assisted development workflow;
- preserves secure and deterministic development controls;
- can be audited through Git and GitHub history; and
- avoids copying protected expressive franchise assets or prose.
