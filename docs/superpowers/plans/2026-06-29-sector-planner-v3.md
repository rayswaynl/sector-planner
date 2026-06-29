# Sector & Town Planner V3 — Plan (playable mission.sqm generator → polish)

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development. `- [ ]` steps. Build tasks edit `index.html` SEQUENTIALLY.

**Goal (both-sequenced):** (Phase A) design a campaign on any of the 7 maps → download a **complete, playable `mission.sqm`** + its folder name. (Phase B) polish: per-axis hi-res textures, supply-route graph, campaign sim.

**Approach:** **template-and-inject, structured.** Parse the Chernarus `mission.sqm` into a structured boilerplate template (everything EXCEPT towns). At generate time, build a structured mission model = template boilerplate + the user's designed campaign (towns/camps/defenses/spawns/airfields, already in `townsData`/`getWaspData()`) + the chosen factions + the target world, then **emit** a valid `mission.sqm` with a single ID counter, complete `synchronizations[]`, and recomputed `items=` counts. A structured emitter (not text-surgery) is what makes the `items=`/ID/sync gotchas tractable.

## Grounding (verbatim, from research)
- Root = `class Mission { addOns[]; addOnsAuto[]; randomSeed; class Intel{}; class Groups{ items=N; Item0.. }; class Markers{ items=5; } };` + siblings `class Intro/OutroWin/OutroLoose` (each just `addOns[]/addOnsAuto[]/randomSeed/Intel`). **No top-level `class Vehicles` or `Sensors`.**
- **World key** = the terrain PBO name in `addOns[]` AND `addOnsAuto[]`, in **all 4 blocks** (Mission, Intro, OutroWin, OutroLoose). Terrain is ALSO set by the folder suffix `.<world>` (authoritative). No `world=` field.
- **Town** = `LocationLogicDepot` (own `position[]`, `init="nullReturn=[this,\"Name\",\"Alias\",income,pop,radius,sizeArr] execVM \"Common\\Init\\Init_Town.sqf\";this enableSimulation false;"`) + 2 `LocationLogicCamp` (`synchronizations[]={depotId}`) + N defense `Logic` (`init="this setVariable['wfbe_defense_kind',['MGNest']]"`, `sync={depotId}`). Depot `synchronizations[]={camp,camp,def,def}`. `text=` = the depot's internal name (must match WF_Logic `Towns_Removed*`).
- **WF_Logic** (`vehicle="Logic"`, `text="WF_Logic"`): `init` sets `totalTowns`=depot count + `Towns_RemovedXSmall/Small/Medium/Large[/BigTowns/CentralLine/SmallTowns]` (arrays of depot `text=` names) + `nullReturn=[this] ExecVM "Common\Init\Init_TownMode.sqf"`.
- **Spawns** = `LocationLogicStart` (some `init` set `wfbe_default west|east|resistance` + `wfbe_spawn "north|south|central"`). **Airfields** = `LocationLogicAirport`.
- **Player slots**: solo groups, `side="WEST|EAST|CIV"`, `vehicle="<soldierClass>"`, `player="PLAY CDG"`, `synchronizations[]={ownerId}`. ~27/side + 1 CIV headless (`forceHeadlessClient=1`). **Slot soldier class + position are swappable per faction/map.**
- **Owner logics** `LocationLogicOwnerWest`(`text=WFBE_L_BLU`)/`East`(`WFBE_L_OPF`): `synchronizations[]` must list **every** player-slot id of that side.
- **Markers** (5, names fixed): `WestTempRespawnMarker`, `EastTempRespawnMarker`, `GuerTempRespawnMarker`, `DEADSPAWNS`, `DEADSPAWNS_1`. Positions map-specific (staging).
- **Constants (arbitrary pos)**: `FunctionsManager`, `RCoin`/`MCoin` logics.
- **GOTCHAS**: every `class Groups{items=N}` + inner `class Vehicles{items=M}` must equal child counts (recursive). IDs unique ints, sequential counter. Owner sync must enumerate ALL side slots. addOns must include world + every used soldier class's PBO. `Towns_Removed*` names == depot `text=`.
- **Staging**: put slots/owners/markers in an off-play dead-zone scaled to the target world SIZE (e.g. WEST cluster near one off-map corner, EAST another), so they don't sit on contested terrain. Keep relative offsets within a cluster.

## Phase A — the generator

### Task 1: Template extractor (Python) → structured boilerplate
**Files:** `tools/extract_template.py`, `tools/test_extract_template.py`.
- [ ] Parse the Chernarus `mission.sqm` (`C:\Users\Steff\a2waspwarfare\Missions\[55-2hc]warfarev2_073v48co.chernarus\mission.sqm`). Classify every group: town-depot-group (drop — injected later), player-slot (keep: side + a class SLOT + the within-cluster offset), owner-logic (keep: side + which slot-ids it syncs — but record by side, ids reassigned at emit), marker (keep: name + cluster), utility (FunctionsManager/RCoin/MCoin — keep), WF_Logic (keep shell, drop town-specific vars), LocationLogicStart/Airport (drop — injected). 
- [ ] Emit `assets/data/mission-template.json`: `{ header:{version, addOnsBase:[...non-world,non-faction], addOnsFactionPlaceholder, randomSeed}, slots:{west:[{classRole, offset}], east:[...], civ:{...}}, owners:{west:{...}, east:{...}}, markers:[{name, side}], utility:[{vehicle,text}], wfLogic:{...}, stagingClusters:{west:{anchor}, east:{...}, guer:{...}} }`. (Positions stored as cluster-relative offsets so the emitter can drop a cluster at a dead-zone anchor for any SIZE.)
- [ ] Tests on inline fixtures (a slot group → side+class+offset; a depot group is classified as town/dropped; items= counting helper). Run → mission-template.json. **Commit** `feat(tools): extract mission.sqm boilerplate template`.

### Task 2: Faction data → factions.json
**Files:** `tools/build_factions.py` (or hand-curate from the grounding) → `assets/data/factions.json`.
- [ ] From the faction-classes grounding: `{ <faction>: { side:"WEST|EAST|GUER", slotClass, civClass, addOns:[...] } }` for the WASP-playable factions. Always-present base addOns recorded separately. **Commit** `feat(data): faction slot-classes + addOns`.

### Task 3: Mission assembler + emitter (JS, in index.html)
**Files:** `index.html`.
- [ ] A JS module `buildMissionSqm({world, size, westFaction, eastFaction, towns, spawns, airports})`: assign IDs via one counter; build town groups (depot+camps+defenses, sync), spawn/airport logics, the boilerplate (slots with the faction slotClass at staging-cluster positions for `size`, owner logics syncing ALL slot ids, markers, utility, WF_Logic with `totalTowns` + `Towns_Removed*` from the towns), set `addOns[]/addOnsAuto[]` = base + world + the two factions' addOns, in all 4 blocks; recompute every `items=`. Emit valid `.sqm` text.
- [ ] Folder name helper → `[NN-2hc]warfarev2_073v48co.<world>`.

### Task 4: Faction-picker UI + Generate + verify
**Files:** `index.html`.
- [ ] UI: a "Generate mission" panel — WEST faction + EAST faction `<select>` (from factions.json, filtered by side), current map shown, a **Generate** button → download `mission.sqm` + show the folder name + a short "drop this folder in your Missions" note. Validate (≥1 town, ≥1 spawn/side ideally).
- [ ] Verify (Playwright): generate a mission for Zargabad (with a few designed towns) → parse the output back: every `class Groups{items=N}` matches child count; all IDs unique; each owner-logic sync lists all its side's slot ids; `addOns[]` contains the world + both factions' addOns in all 4 blocks; `totalTowns` == town count; `Towns_Removed*` names ⊆ depot text=. Also regenerate Chernarus's own seeded towns and assert structural validity. 0 console errors. Screenshot the generate panel. **Commit** `feat: playable mission.sqm generator + faction picker`.

## Phase B — polish (after Phase A ships)
- [ ] **Per-axis textures**: support `scaleX`/`scaleY` (or a bounds box) per map so the hi-res iZurvive stitches (chernarus 6400×5376 @14900m, takistan 8192² @12800m) can be used accurately; let texture entries carry explicit extents.
- [ ] **Supply-route graph**: define/auto town adjacency; draw the campaign connectivity graph; use it for frontline + AI-path hints.
- [ ] **Campaign sim**: run the economy/AI forward N ticks from the painted ownership + income to preview balance (towns flipping, income curves).

## Task F: deploy
- [ ] Tests pass; full smoke; merge `feat/v3`→main, push (Pages auto → hub tile auto-updates). README v3.

## Self-Review
- Playable generator = Tasks 1–4 (structured template+inject, faction picker, items=/ID/sync discipline). Polish = Phase B. Sequential index.html edits. Round-trip/structural-validity gate on the emitted .sqm.
