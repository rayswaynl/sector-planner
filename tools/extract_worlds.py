#!/usr/bin/env python3
"""
extract_worlds.py — Parse CfgWorlds.txt and emit assets/data/maps.json

Usage:
    python tools/extract_worlds.py \
        --src "C:/Users/Steff/arma2-co-config-reference/Config/CfgWorlds.txt" \
        --out "assets/data/maps.json"

Output schema:
    {
        "<worldKey>": {
            "name": "<display name>",
            "worldName": "<wrp path>",
            "size": <int metres>,
            "locations": [
                { "name": "<str>", "pos": [x, y], "type": "<str>" },
                ...
            ]
        },
        ...
    }

worldKey is the lowercased class name with Shapur_BAF → "shapur_baf" etc.
"""

import re
import json
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# The 7 playable worlds we care about (class names as they appear in the file)
# ---------------------------------------------------------------------------
PLAYABLE_WORLDS = [
    "utes",
    "Chernarus",
    "ProvingGrounds_PMC",
    "Shapur_BAF",
    "Takistan",
    "Zargabad",
    "Desert_E",
]

# Hardcoded sizes for worlds whose Grid.offsetY = 0 (stepY positive = no-flip)
HARDCODE_SIZES = {
    "chernarus": 15360,
    "utes":      5120,
}

# Display names
WORLD_DISPLAY_NAMES = {
    "utes":              "Utes",
    "chernarus":         "Chernarus",
    "provinggrounds_pmc":"Proving Grounds",
    "shapur_baf":        "Shapur",
    "takistan":          "Takistan",
    "zargabad":          "Zargabad",
    "desert_e":          "Takistan Desert",
}


# ---------------------------------------------------------------------------
# STEP 1: Extract the raw text span for each top-level world class
# We brace-match from the opening { of "class <World> : CAWorld" to its closing }
# ---------------------------------------------------------------------------
def _find_world_spans(text: str) -> dict[str, str]:
    """
    Returns { class_name: body_text } for each playable world class.
    body_text is the content INSIDE the outer braces (not including them).
    """
    spans = {}
    for world in PLAYABLE_WORLDS:
        # Match: optional leading whitespace + "class <World> : CAWorld"
        pattern = re.compile(
            r'^\s*class\s+' + re.escape(world) + r'\s*:\s*CAWorld\s*\{',
            re.MULTILINE,
        )
        m = pattern.search(text)
        if not m:
            continue

        # Brace-match from the opening { to the matching }
        start = m.end()  # position just after the opening {
        depth = 1
        pos = start
        while pos < len(text) and depth > 0:
            ch = text[pos]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            pos += 1

        body = text[start: pos - 1]  # everything between the outer { }
        spans[world] = body

    return spans


# ---------------------------------------------------------------------------
# STEP 2: Extract size from Grid block inside a world body
# ---------------------------------------------------------------------------
def _extract_size(world_key: str, body: str) -> int:
    """
    Size rules:
    - If world_key is in HARDCODE_SIZES → return that value directly.
    - Otherwise find the first "class Grid : Grid" block within body,
      read offsetY (which IS the terrain size when stepY is negative).
    """
    if world_key in HARDCODE_SIZES:
        return HARDCODE_SIZES[world_key]

    # Find the Grid block
    grid_pat = re.compile(r'class\s+Grid\s*:\s*Grid\s*\{')
    gm = grid_pat.search(body)
    if not gm:
        return 0

    # Extract just the Grid block body (brace-match)
    start = gm.end()
    depth = 1
    pos = start
    while pos < len(body) and depth > 0:
        ch = body[pos]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        pos += 1
    grid_body = body[start: pos - 1]

    # offsetY = <number>
    m = re.search(r'offsetY\s*=\s*(\d+)', grid_body)
    if m:
        return int(m.group(1))
    return 0


# ---------------------------------------------------------------------------
# STEP 3: Extract locations from the Names block inside a world body
# ---------------------------------------------------------------------------
def _extract_locations(body: str) -> list[dict]:
    """
    Finds the FIRST "class Names" block in body (brace-matched),
    then iterates over all sub-entries extracting name/position/type.
    """
    # Find "class Names" within this body
    names_pat = re.compile(r'class\s+Names\s*\{')
    nm = names_pat.search(body)
    if not nm:
        return []

    # Brace-match to get the Names block body
    start = nm.end()
    depth = 1
    pos = start
    while pos < len(body) and depth > 0:
        ch = body[pos]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        pos += 1
    names_body = body[start: pos - 1]

    # Now iterate over each "class <id> {" inside Names
    entry_pat = re.compile(r'class\s+\w+\s*\{')
    locations = []
    for em in entry_pat.finditer(names_body):
        # Brace-match this entry
        estart = em.end()
        edepth = 1
        epos = estart
        while epos < len(names_body) and edepth > 0:
            ch = names_body[epos]
            if ch == '{':
                edepth += 1
            elif ch == '}':
                edepth -= 1
            epos += 1
        entry_body = names_body[estart: epos - 1]

        # Extract fields
        name_m = re.search(r'name\s*=\s*"([^"]*)"', entry_body)
        pos_m  = re.search(r'position\[\]\s*=\s*\{([^}]+)\}', entry_body)
        type_m = re.search(r'type\s*=\s*"([^"]*)"', entry_body)

        if not (pos_m and type_m):
            continue

        loc_name = name_m.group(1).strip() if name_m else ""
        raw_pos  = pos_m.group(1).split(',')
        if len(raw_pos) < 2:
            continue
        try:
            x = float(raw_pos[0].strip())
            y = float(raw_pos[1].strip())
        except ValueError:
            continue

        loc_type = type_m.group(1).strip()

        locations.append({
            "name": loc_name,
            "pos":  [x, y],
            "type": loc_type,
        })

    return locations


# ---------------------------------------------------------------------------
# PUBLIC API: parse a CfgWorlds text string into the maps dict
# ---------------------------------------------------------------------------
def parse_cfg_worlds(text: str) -> dict:
    """
    Returns maps dict: { worldKey: { name, worldName, size, locations } }
    """
    spans = _find_world_spans(text)
    result = {}

    for world_class, body in spans.items():
        world_key = world_class.lower()

        # Display name
        display_name = WORLD_DISPLAY_NAMES.get(world_key, world_class)

        # worldName field
        wn_m = re.search(r'worldName\s*=\s*"([^"]*)"', body)
        world_name_val = wn_m.group(1) if wn_m else ""

        size = _extract_size(world_key, body)
        locations = _extract_locations(body)

        result[world_key] = {
            "name":       display_name,
            "worldName":  world_name_val,
            "size":       size,
            "locations":  locations,
        }

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Extract CfgWorlds → maps.json")
    parser.add_argument(
        "--src",
        default="C:/Users/Steff/arma2-co-config-reference/Config/CfgWorlds.txt",
        help="Path to CfgWorlds.txt",
    )
    parser.add_argument(
        "--out",
        default="assets/data/maps.json",
        help="Output path for maps.json",
    )
    args = parser.parse_args()

    src_path = Path(args.src)
    out_path = Path(args.out)

    print(f"Reading: {src_path}")
    text = src_path.read_text(encoding="utf-8", errors="replace")

    maps = parse_cfg_worlds(text)

    # Sanity output
    print(f"\nExtracted {len(maps)} worlds:")
    for key, data in maps.items():
        print(f"  {key:25s}  size={data['size']:6d}  locs={len(data['locations'])}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(maps, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path} ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
