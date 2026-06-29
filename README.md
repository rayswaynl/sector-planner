# Sector & Town Planner

A browser-based, offline, single-file **strategic map editor** for Arma 2 **WASP "Warfare"** — part of the [Miksuu's Warfare tools](https://miksuu.com/tools) suite (sibling to [WDDM](https://github.com/rayswaynl/WDDM) and [Loadout Lab](https://github.com/rayswaynl/loadout-lab)).

**▶ Live: https://rayswaynl.github.io/sector-planner/**

## What it does

Edit the whole WASP campaign on a map. Every capturable **town** is a draggable marker on a pan/zoom map of the chosen world:

- **All 7 stock Arma 2 / expansion maps preloaded** — Chernarus (15360 m), Takistan (12800 m), Zargabad (8192 m), Utes (5120 m), Shapur, Proving Grounds, Desert — each with its real **named locations** (cities/villages from `CfgWorlds`) as reference markers.
- **WASP towns** on Chernarus + Takistan are **editable**: drag to reposition, and click to retune **supply** (`startSV`/`maxSV`), **income value**, and **AI town-type** in the inspector. 600 m capture rings, spawn points and airfields shown.
- **Size presets** — toggle which towns each `Towns_Removed*` preset (XSmall…Huge) includes.

## Mission I/O

- **Ships seeded** with the live Chernarus + Takistan town data — browse + edit instantly.
- **Paste your `mission.sqm`** → the planner maps your exact towns → edit on the map → **download a modified `mission.sqm`** with your changes applied **in place** (a no-op edit returns the file byte-for-byte identical — only the towns you actually changed are touched).
- Or, in seeded mode, **export a change-list** (the new `position[]` / `init=` lines per edited town) to paste yourself.

## Unique core

Where WDDM edits meter-scale footprints and Loadout Lab edits a unit's kit, this tool edits the **entire campaign at strategic zoom** — a draggable map, not a form or a palette.

## Build

`tools/extract_towns.py` parses the mission `mission.sqm` (`LocationLogicDepot` towns + spawns + airfields + presets) → `assets/data/seed-towns.json`. `tools/extract_worlds.py` parses `CfgWorlds.txt` (all 7 worlds: size + named locations) → `assets/data/maps.json`. `index.html` is the single-file app. Tests: `python tools/test_extract_towns.py && python tools/test_extract_worlds.py`.

## Roadmap (v2 ideas)

- **Design campaigns on any map** — promote a CfgWorlds location to a WASP town / place towns from scratch on Zargabad, Utes, etc. (export new-mission town blocks).
- Real topographic map images under the grid.

## License

Unofficial, non-commercial reference tool for mission development. Arma 2 map data © **Bohemia Interactive**.
