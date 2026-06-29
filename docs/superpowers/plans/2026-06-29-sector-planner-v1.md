# Sector & Town Planner v1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** A single-file offline strategic map editor for WASP towns — drag towns on the Chernarus/Takistan map, retune their supply/value/type, manage size-presets; seeded with live data AND able to paste a `mission.sqm` and download a modified one.

**Architecture:** `tools/extract_towns.py` parses the mission `mission.sqm` files → `assets/data/seed-towns.json`. `index.html` (vanilla JS, WDDM dark theme) renders towns as draggable markers on a map (coordinate-mapped), with an edit panel + a paste/download `mission.sqm` path.

**Tech Stack:** Python 3.12 (stdlib); vanilla JS/SVG/Canvas; Playwright.

**Reuse:** WDDM/Loadout Lab design tokens (gunmetal `#14171B`, steel, olive, orange `#D9763C`, bone; Oswald/Inter/JetBrains Mono) + the `loadClassData` fetch + validation patterns.

## Grounding (from research — verbatim facts)
- Towns = `LocationLogicDepot` entities in `mission.sqm` (one per map). Per depot: `position[]={x, alt, y}` (use [0]=x, [2]=y), and an `init=` string: `[this,"Name","Dubbing",startSV,maxSV,value,typeArg] execVM "Common\Init\Init_Town.sqf";...`. `typeArg` = a string `"TinyTown1"` or array `["SmallTown1","SmallTown2"]`; `.sqm` doubles quotes (`""`=`"`).
- Capture radius = 600 m for ALL towns (hardcoded; not per-town).
- Camps = `LocationLogicCamp` (2/town, synchronized to the depot). Spawns = `LocationLogicStart` (14 in Chernarus; some annotated `wfbe_default <side>`/`wfbe_spawn "<pos>"`). Airfields = `LocationLogicAirport`.
- Size presets: `WF_Logic` `init=` sets `Towns_RemovedXSmall/Small/...` arrays of **CamelCase-no-space** town names (e.g. `"NovySobor"`).
- Coord ranges: Chernarus **15360 m**, Takistan **12800 m**. Map: `px = world_x/SIZE*imgW`, `py = (1 - world_y/SIZE)*imgH` (Y flips).
- Files: Chernarus `C:\Users\Steff\a2waspwarfare\Missions\[55-2hc]warfarev2_073v48co.chernarus\mission.sqm`; Takistan `C:\Users\Steff\a2waspwarfare\Missions_Vanilla\[61-2hc]warfarev2_073v48co.takistan\mission.sqm`.

---

## Task 1: Generator — parse mission.sqm → seed-towns.json

**Files:** Create `tools/extract_towns.py`, `tools/test_extract_towns.py`.

- [ ] **Step 1: Failing tests** — fixture a minimal `LocationLogicDepot` group string; assert the parser extracts `{name, pos:[x,y], startSV, maxSV, value, type}` and that an array `typeArg` parses to a list, a bare string to `[string]`.
- [ ] **Step 2-3: Implement** `extract_towns(sqm_text)`:
  - Find every `vehicle="LocationLogicDepot"` block; within it grab the enclosing `position[]={...}` (the depot's own) and the `init=` string.
  - Parse the `init=` args: regex the `[this,"Name","Dub",sv,maxsv,val, <type>]` — `type` is the 7th element (a `"..."` or `[...]`). Un-double the `.sqm` quotes (`""`→`"`).
  - Also extract `LocationLogicStart` (pos + any `wfbe_default`/`wfbe_spawn` annotation), `LocationLogicAirport` (pos), and the `Towns_Removed*` arrays from the `WF_Logic` init.
  - `faction_map(filename)` → 'chernarus'/'takistan' (by folder or a --map arg).
  - `main(--mission <dir>, --map <name>, --out)`: parse → `{map, size, towns:[...], spawns:[...], airports:[...], presets:{XSmall:[...],...}}`. Run for BOTH maps → `assets/data/seed-towns.json` = `{chernarus:{...}, takistan:{...}}`.
- [ ] **Step 4-5: Run** for both missions → `seed-towns.json`. Sanity: chernarus has ~40 towns incl. `Kamenka` at ~`[1827,2261]` with value 300; takistan ~31 towns. **Step 6: Commit** `feat(tools): extract mission.sqm towns/spawns/airports -> seed-towns.json`.

---

## Task 2: Map shell + town render

**Files:** Create `index.html`.

- [ ] **Step 1: Shell** — lift WDDM `<head>`/tokens/brand bar (retitle "SECTOR PLANNER" / "WASP CAMPAIGN MAP"); a left controls panel + a large map stage + a right inspector. Fetch `seed-towns.json`.
- [ ] **Step 2: Map surface** — an SVG (or canvas) sized to the stage; a **map switcher** (Chernarus/Takistan). World→pixel mapping per the formulas (Y flips). For v1 the backdrop is a **styled coordinate grid** (1 km gridlines labelled in metres) on `--gunmetal` — a real map image is a later polish (`assets/maps/<map>.jpg` drawn under the grid if present; degrade to grid-only if absent). Pan/zoom (scroll = zoom, drag-empty = pan).
- [ ] **Step 3: Town markers** — render each town as a marker at its mapped pixel, **radius scaled by `value`** (or `maxSV`), labelled with the name; draw a faint **600 m capture ring** (in map scale). Render spawns (distinct icon + side colour west/east/guer from the WDDM `west`/`east` palette) and airfields (icon) as context. Color towns neutral for now.
- [ ] **Step 4: Verify (Playwright)** — serve `python -m http.server 8091`; 0 console errors; `() => document.querySelectorAll('.town-marker').length` ≈ 40 (chernarus); switching to takistan re-renders ~31; a known town (Kamenka) maps to a plausible pixel. Screenshot. **Commit** `feat: map surface + town/spawn/airfield markers`.

---

## Task 3: Edit interactions

**Files:** Modify `index.html`.

- [ ] **Step 1: Drag** — towns are draggable; dragging updates the town's world `pos` (pixel→world inverse mapping); snap optional. Show live coords.
- [ ] **Step 2: Inspector** — click a town → right panel edits `startSV`, `maxSV`, `value`, `type` (a multi-select of the known town-type templates). Live-update the marker (size).
- [ ] **Step 3: Size presets** — a panel listing the 6 presets (XSmall…Huge); for the selected preset, toggle which towns are included (checkboxes / map highlight). Edits the in-memory `presets`.
- [ ] **Step 4: Verify (Playwright)** — drag a town → its `pos` changed; edit value → marker resized; toggle a preset membership → reflected. 0 errors. Screenshot. **Commit** `feat: drag, attribute inspector, size-preset editor`.

---

## Task 4: Mission I/O (paste + download + change-list)

**Files:** Modify `index.html`.

- [ ] **Step 1: Paste-and-map** — a "Load mission.sqm" textarea/file-input; parse it (a JS port of the Task-1 extraction) → replace the seeded towns with the pasted file's, AND retain the full pasted text for in-place editing.
- [ ] **Step 2: Download modified .sqm** — when a `mission.sqm` was pasted, produce a modified copy: for each edited town, replace its depot `position[]={...}` and/or regenerate its `init=` string in place (regex-locate by the town name in the init); rewrite the `Towns_Removed*` arrays in the WF_Logic init. Offer a **download** of the modified `mission.sqm`. Keep all non-town content byte-identical.
- [ ] **Step 3: Change-list export** (seeded mode, no paste) — export a per-edited-town block: the new `position[]` line + `init=` line to apply.
- [ ] **Step 4: Round-trip gate (Playwright)** — paste a known `mission.sqm` (or a fixture with a few depots), make NO edits, download → the output is byte-identical to the input (no-op safety). Then edit one town's value + download → only that town's `init=` differs. 0 errors. **Commit** `feat: paste mission.sqm, download modified, change-list export`.

---

## Task 5: Verify + finish + deploy + tile

- [ ] **Step 1:** generator tests pass; full Playwright smoke (both maps, drag, edit, preset, paste round-trip); 0 console errors; screenshot.
- [ ] **Step 2:** README usage; commit.
- [ ] **Step 3:** controller: merge `feat/v1`→`main`, push, enable GitHub Pages; verify live.
- [ ] **Step 4:** controller: add a tile to the miksuu hub (`web/src/app/tools/tools.ts` — one entry `{slug:"sector-planner", name:"Sector & Town Planner", description:"...", url:"https://rayswaynl.github.io/sector-planner/"}`) on a branch; **user approves the miksuu deploy**.

---

## Self-Review
- Map editor (unique core) → Tasks 2–3; ingest/emit BOTH (seed + paste/download) → Tasks 1 (seed) + 4 (paste/download/change-list); deploy + tile → Task 5.
- Names: `extract_towns`, `seed-towns.json`, world↔pixel mapping, town/spawn/airfield markers, presets — consistent.
- Map image deferred to a grid-first render (Task 2) so the tool is functional without an asset-sourcing dependency; real image is additive.
