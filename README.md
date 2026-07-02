# Sector & Town Planner

A browser-based, offline, single-file **strategic map editor** for Arma 2 **WASP "Warfare"** — part of the [Miksuu's Warfare tools](https://miksuu.com/tools) suite (sibling to [WDDM](https://github.com/rayswaynl/WDDM) and [Loadout Lab](https://github.com/rayswaynl/loadout-lab)).

**▶ Live: https://rayswaynl.github.io/sector-planner/**

## What it does

Edit the whole WASP campaign on a map. Every capturable **town** is a draggable marker on a pan/zoom map of the chosen world, over a **real topographic texture**:

- **All 7 stock Arma 2 / expansion maps preloaded** — Chernarus (15360 m), Takistan (12800 m), Zargabad (8192 m), Utes (5120 m), Shapur, Proving Grounds, Desert — each with a **topographic map image** (alignment-verified; toggle + opacity) and its real **named locations** from `CfgWorlds` as reference markers.
- **Town editing on every map**: drag to reposition; click to retune **supply** (`startSV`/`maxSV`), **income value**, **AI town-type**; 600 m capture rings.
- **Campaign designer** — add/delete towns, **promote a CfgWorlds location → capturable town**, and design a campaign **from scratch on any map** (Zargabad, Utes…).
- **Generate a playable mission** — pick a WEST + EAST faction and hit Generate to download a **complete, runnable WASP `mission.sqm`** for the current map (towns + camps + spawns + airfields + WF_Logic + player slots + side plumbing, all assembled with valid IDs/syncs/counts) plus the folder name to drop it in. Design on *any* of the 7 maps → play it.
- **Tactical layer** — editable **camps**, **defenses** (MGNest etc.), **spawn points** (per-side), and **airfields**.
- **Strategy overlays** — paint town **ownership** (side totals), **income** per town (`value × COEF`), an approximate **frontline** with contested/distance-to-front shading, and **capture-time** estimates.
- **Size presets** — toggle which towns each `Towns_Removed*` preset (XSmall…Huge) includes.

## Mission I/O

- **Ships seeded** with the live Chernarus + Takistan town data — browse + edit instantly.
- **Paste your `mission.sqm`** → the planner maps your exact towns → edit on the map → **download a modified `mission.sqm`** with your changes applied **in place** (a no-op edit returns the file byte-for-byte identical — only the towns you actually changed are touched).
- Or, in seeded mode, **export a change-list** (the new `position[]` / `init=` lines per edited town) to paste yourself.

## Headless CLI (build missions by prompting)

`tools/gen_mission.mjs` (Node ≥ 16, zero deps) runs the **same** generator as the browser Generate button — it extracts the assembler section out of `index.html` and evaluates it in a vm sandbox, so CLI and web output can never drift.

```
node tools/gen_mission.mjs --map zargabad --west US --east TKA --campaign my-campaign.json --out ./build
node tools/gen_mission.mjs --map zargabad --auto-towns --json     # promote CfgWorlds locations to towns
node tools/gen_mission.mjs --map chernarus --out ./build          # use the shipped seed campaign
```

`--campaign` takes a JSON file shaped like a `seed-towns.json` map entry (`{towns, spawns, airports, presets}`); `--json` prints a machine-readable summary (folder name, counts, structural issues); structural validation runs by default and any issue exits 1. Tests: `node tools/test_gen_mission.mjs`.

## Unique core

Where WDDM edits meter-scale footprints and Loadout Lab edits a unit's kit, this tool edits the **entire campaign at strategic zoom** — a draggable map, not a form or a palette.

## Build

`tools/extract_towns.py` parses the mission `mission.sqm` (`LocationLogicDepot` towns + spawns + airfields + presets) → `assets/data/seed-towns.json`. `tools/extract_worlds.py` parses `CfgWorlds.txt` (all 7 worlds: size + named locations) → `assets/data/maps.json`. `index.html` is the single-file app. Tests: `python tools/test_extract_towns.py && python tools/test_extract_worlds.py`.

## License

Unofficial, non-commercial reference tool for mission development. Arma 2 map data + topographic map renders © **Bohemia Interactive** (map images via the Armed Assault wiki, reference use only).
