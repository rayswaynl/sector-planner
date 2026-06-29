# Sector & Town Planner

A browser-based, offline, single-file **strategic map editor** for the Arma 2 **WASP "Warfare"** mission — part of the [Miksuu's Warfare tools](https://miksuu.com/tools) suite (sibling to [WDDM](https://github.com/rayswaynl/WDDM) and [Loadout Lab](https://github.com/rayswaynl/loadout-lab)).

> Status: **in development**.

## What it does

Edit the whole WASP campaign on a map: every capturable **town** is a draggable marker on the Chernarus (15360 m) or Takistan (12800 m) map. Drag towns to reposition them, click to retune their **supply values** (`startSV`/`maxSV`), **income value**, and **AI town-type**, and manage which towns each **size preset** (XSmall…Huge) includes. Spawn points and airfields are shown as context.

Towns live in the mission's `mission.sqm` as `LocationLogicDepot` entities. The planner:
- **Ships seeded** with the live Chernarus + Takistan town data (instant browsing, no setup), and
- **Accepts a pasted `mission.sqm`** to map your exact file and **download a modified `mission.sqm`** with your edits applied in place.

## Unique core

Where WDDM edits meter-scale footprints and Loadout Lab edits a unit's kit, this tool edits the **entire campaign at strategic zoom** — a draggable map, not a form or a palette.

## License

Unofficial, non-commercial reference tool for mission development. Arma 2 map imagery and config data © **Bohemia Interactive**.
