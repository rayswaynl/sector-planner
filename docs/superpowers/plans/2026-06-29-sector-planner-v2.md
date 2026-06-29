# Sector & Town Planner v2 — Expansion Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`. Build tasks B→C→D **sequentially** (all edit `index.html`). Texturing (A) slots in when images are staged.

**Goal:** turn the planner from a town-tweaker into a full **campaign design board**: real map textures, town CRUD + promote-location + design-on-any-map, editable camps/defenses/spawns/airfields, and strategy/analysis overlays.

**Current state (v1, on `main`):** `index.html` (2020 lines) — camera-SVG engine (`translate/scale` cam, `svgY = SIZE − worldY`), all 7 worlds from `maps.json` (size + CfgWorlds locations), editable WASP towns on Chernarus/Takistan from `seed-towns.json` (drag + inspector + presets), mission.sqm paste/download (byte-identical round-trip), change-list. `seedData` frozen vs `townsData` live; edited-flag tracking. **Read `index.html` first.**

**Grounding (verbatim, from v1 research):** Town = `LocationLogicDepot` (pos `[x,y]`, init `[this,"Name","Dub",startSV,maxSV,value,typeArg]`). Camps = `LocationLogicCamp` (2/town, `synchronizations[]` → depot). Defense = `Logic` with `init="this setVariable ['wfbe_defense_kind', ['MGNest']]"`. Spawns = `LocationLogicStart` (some `wfbe_default <side>` + `wfbe_spawn "<pos>"`). Airfields = `LocationLogicAirport`. Capture radius 600 m all towns. Income (overlay) = `town.value × INCOME_COEF` (default 8). Town types: Tiny/Small/Medium/Large/Huge×{1,2}.

---

## Task A: Map texturing  *(do when images are staged in scratchpad `maptex\`)*
**Files:** `assets/maps/<world>.jpg|png` (copied from staging), `index.html`.
- [ ] Copy the alignment-verified images into `assets/maps/`. In the renderer, draw `assets/maps/<world>.<ext>` as an `<image>` under the grid, mapped to the full world extent (0..SIZE, Y-flipped) — degrade to grid-only if the file 404s (keep that fallback). Add a **"Map texture" layer toggle** + an opacity slider. Dim the grid when a texture is shown.
- [ ] Verify (Playwright): Chernarus shows the texture with towns landing on the right coastal spots (Kamenka SW coast etc.); toggle hides it; a textureless world (e.g. Desert) still grid-renders. Screenshot. Commit `feat: map textures + layer toggle`.

## Task B: Campaign designer (CRUD + promote + any-map + export)
**Files:** `index.html`.
- [ ] **Enable WASP-town editing on ALL maps** (not just chernarus/takistan): allow a `townsData[world]` for any world (start empty for non-WASP maps). The WASP layer controls un-dim on every map.
- [ ] **Add town**: an "Add town" mode → click empty map → create a town at that world pos with sane defaults (name `New Town N`, startSV 10, maxSV 45, value 250, type `["SmallTown1"]`, 2 auto camps offset ±150 m). Selects it for editing. Mark as added.
- [ ] **Delete town**: a delete control in the inspector (+ keyboard Del on selected). Confirm.
- [ ] **Promote location → town**: clicking a CfgWorlds reference location in "Add" mode (or a "promote" action on a hovered location) creates a town at that location, inheriting its `name`.
- [ ] **Export for new/any-map towns**: a "Export town set" that emits, for the current map's towns: (1) an **SQF block** — one `[this,"Name","Dub",startSV,maxSV,value,type] execVM "Common\Init\Init_Town.sqf"` line per town with its `position` as a comment, and (2) a **JSON** dump. (For chernarus/takistan the existing mission.sqm paste/download still applies to seeded towns.) Label clearly that designed towns need placing as `LocationLogicDepot` logics at the given positions.
- [ ] Verify (Playwright): on Zargabad (no seed towns) — add 2 towns + promote 1 location → 3 towns editable + draggable; export block lists all 3 with correct args/positions; delete one → 2. On Chernarus, add a town alongside seeded ones. 0 errors. Screenshot. Commit `feat: town CRUD + promote-location + design-on-any-map + town-set export`.

## Task C: Editable camps / defenses / spawns / airfields
**Files:** `index.html`.
- [ ] **Camps**: render each town's camps (from seed) as smaller draggable markers linked to the town; add/remove a camp from the inspector; new towns get 2. 
- [ ] **Defenses**: per town, an editable list of defense logics with a **kind** picker (MGNest + the other `wfbe_defense_kind` values found in the data); placeable/removable.
- [ ] **Spawns** (`LocationLogicStart`): make draggable; add/delete; edit side (`wfbe_default` west/east/resistance) + `wfbe_spawn` annotation. **Airfields**: draggable; add/delete.
- [ ] Include camps/defense/spawn/airfield edits in the change-list/export where applicable (note positions). Verify (Playwright): drag a camp; add a defense (MGNest) to a town; move a spawn + set its side; add an airfield. 0 errors. Screenshot. Commit `feat: editable camps, defenses, spawns, airfields`.

## Task D: Strategy overlays (analysis board)
**Files:** `index.html`.
- [ ] **Ownership painting**: assign each town a side (WEST/EAST/GUER/neutral) via the inspector or a paint mode → color markers by side. A side-totals readout (towns + total value per side).
- [ ] **Income overlay**: toggle showing each town's income `value × COEF` (COEF field, default 8) + per-side income totals (links to the economy model). 
- [ ] **Frontline + distance-to-front**: draw the boundary between WEST- and EAST-owned clusters (e.g. midlines between nearest opposing towns); shade each town by distance-to-front; highlight contested/frontline towns.
- [ ] **Capture-time estimate**: per town, an estimate from `maxSV` and a capture-rate field (overlay label/tooltip).
- [ ] Verify (Playwright): paint 3 towns WEST + 3 EAST → side totals + frontline drawn; income overlay shows value×8 + per-side totals; 0 errors. Screenshot. Commit `feat: strategy overlays — ownership, income, frontline, capture estimates`.

## Task E: Verify + finish + deploy
- [ ] Generator tests still pass; full Playwright smoke (texture, CRUD on a non-WASP map, camps/defenses/spawns, overlays, mission.sqm round-trip still byte-identical); 0 console errors; screenshots.
- [ ] README v2 features; commit. Controller: merge `feat/v2`→main, push (GitHub Pages auto-rebuilds → the hub iframe shows v2 automatically — **no miksuu re-deploy needed**). Verify live.

## Self-Review
- 4 user-picked expansions (campaign designer B, camps/defenses/spawns/airfields C, overlays D) + texturing A; income overlay links to the S&E editor's `INCOME_COEF`. Sequential index.html edits (no parallel agents on one file). mission.sqm round-trip must stay intact. Hub auto-updates via Pages (tile already present).
