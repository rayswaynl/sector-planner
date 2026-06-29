"""
extract_towns.py — Parse WASP mission.sqm files into seed-towns.json.

Usage:
  python tools/extract_towns.py --mission <dir_or_file> --map <name> [--out <path>]
  python tools/extract_towns.py --both <a2waspwarfare_root> [--out <path>]

Output schema:
  {
    "<map>": {
      "map":     str,
      "size":    int,          # 15360 (chernarus) or 12800 (takistan)
      "towns":   [{name, pos:[x,y], dubbing, startSV, maxSV, value, type:[...],
                   camps:[{pos:[x,y]}], defenses:[{pos:[x,y], kind:[...]}]}],
      "spawns":  [{pos:[x,y], side, spawn_pos}],   # side/spawn_pos may be null
      "airports":[{pos:[x,y]}],
      "presets": {"XSmall":[...], "Small":[...], ...}
    }
  }
"""

import re
import json
import os
import sys
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_MAP_SIZES = {
    "chernarus": 15360,
    "takistan": 12800,
}


def _undouble(s: str) -> str:
    """Un-double .sqm quote escaping: \"\"  ->  \" """
    return s.replace('""', '"')


def _detect_map(path: str) -> str:
    """Derive map name from mission folder/file path."""
    p = Path(path).as_posix().lower()
    if "chernarus" in p:
        return "chernarus"
    if "takistan" in p:
        return "takistan"
    raise ValueError(f"Cannot detect map from path: {path!r}. Pass --map explicitly.")


def _find_sqm(path: str) -> str:
    """Return path to mission.sqm given a dir or file path."""
    p = Path(path)
    if p.is_file():
        return str(p)
    sqm = p / "mission.sqm"
    if sqm.exists():
        return str(sqm)
    raise FileNotFoundError(f"Cannot find mission.sqm under {path!r}")


# ---------------------------------------------------------------------------
# Block extraction helpers
# ---------------------------------------------------------------------------

def _find_class_block(text: str, start: int) -> tuple[int, int]:
    """
    Given that text[start] == '{', scan forward counting braces and return
    (body_start, body_end) where text[body_start:body_end] is the content
    between the outer braces (exclusive).
    Returns (start+1, close) where close is the index of the matching '}'.
    """
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c == '{':
            depth += 1
            if depth == 1:
                body_start = i + 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return body_start, i
        i += 1
    raise ValueError(f"Unmatched brace starting at {start}")


def _extract_item0_block(group_body: str) -> str | None:
    """
    Given the body of a group Vehicles block, return the text of class Item0 { ... }.
    """
    m = re.search(r'class\s+Item0\s*\{', group_body)
    if not m:
        return None
    brace_pos = group_body.index('{', m.start())
    body_s, body_e = _find_class_block(group_body, brace_pos)
    return group_body[body_s:body_e]


# ---------------------------------------------------------------------------
# Position parser
# ---------------------------------------------------------------------------

_POS_RE = re.compile(r'position\[\]\s*=\s*\{([^}]+)\}')


def _parse_pos(block: str) -> list[float] | None:
    """Return [x, y] from position[]={x, alt, y} (index 0 and 2)."""
    m = _POS_RE.search(block)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(',')]
    if len(parts) < 3:
        return None
    return [round(float(parts[0]), 4), round(float(parts[2]), 4)]


# ---------------------------------------------------------------------------
# Init parser for LocationLogicDepot
# ---------------------------------------------------------------------------

# The init line looks like (after un-doubling):
#   nullReturn = [this,"Name","Dub",startSV,maxSV,value,typeArg] execVM "...";
#
# typeArg is either:
#   "TinyTown1"                -> bare string (in .sqm: ""TinyTown1"")
#   ["SmallTown1","SmallTown2"] -> array

_INIT_RE = re.compile(
    r'\[this\s*,\s*'               # [this,
    r'"([^"]+)"\s*,\s*'            # "Name",
    r'"([^"]*)"\s*,\s*'            # "Dub",
    r'(\d+)\s*,\s*'                # startSV,
    r'(\d+)\s*,\s*'                # maxSV,
    r'(\d+)\s*,\s*'                # value,
    r'(\[.*?\]|"[^"]*")'           # typeArg (array or bare string)
    r'\s*\]',
    re.DOTALL,
)


def _parse_init_args(init_raw: str) -> dict | None:
    """Parse the depot init= string (already un-doubled). Returns dict or None."""
    m = _INIT_RE.search(init_raw)
    if not m:
        return None
    name, dub, start_sv, max_sv, value, type_raw = m.groups()
    type_raw = type_raw.strip()
    if type_raw.startswith('['):
        # Array: ["SmallTown1","SmallTown2"]
        # Extract all quoted strings inside.
        types = re.findall(r'"([^"]+)"', type_raw)
    else:
        # Bare string: "SmallTown1"
        inner = re.match(r'"([^"]+)"', type_raw)
        types = [inner.group(1)] if inner else []
    return {
        "name":    name,
        "dubbing": dub,
        "startSV": int(start_sv),
        "maxSV":   int(max_sv),
        "value":   int(value),
        "type":    types,
    }


# ---------------------------------------------------------------------------
# Spawn annotation parser (LocationLogicStart)
# ---------------------------------------------------------------------------

_SIDE_RE = re.compile(r'wfbe_default[""]*\s*,\s*(\w+)')
_SPAWN_POS_RE = re.compile(r'wfbe_spawn[""]*\s*,\s*"([^"]+)"')


def _parse_spawn_init(init_raw: str) -> tuple[str | None, str | None]:
    """Return (side, spawn_pos) from wfbe_default/wfbe_spawn annotations."""
    side = None
    spawn_pos = None
    if not init_raw:
        return side, spawn_pos
    m = _SIDE_RE.search(init_raw)
    if m:
        side = m.group(1)
    m = _SPAWN_POS_RE.search(init_raw)
    if m:
        spawn_pos = m.group(1)
    return side, spawn_pos


# ---------------------------------------------------------------------------
# Preset parser (WF_Logic entity)
# ---------------------------------------------------------------------------

_PRESET_NAMES = ["XSmall", "Small", "Medium", "Large", "BigTowns", "CentralLine", "SmallTowns"]

_PRESET_RE = {
    name: re.compile(
        r'Towns_Removed' + re.escape(name) + r'[""]*\s*,\s*\[([^\]]*)\]',
        re.DOTALL,
    )
    for name in _PRESET_NAMES
}

_TOWN_NAME_RE = re.compile(r'"([^"]+)"')


def _parse_presets(wf_logic_init: str) -> dict:
    """Extract Towns_Removed* arrays from WF_Logic init (already un-doubled)."""
    presets = {}
    for name, pat in _PRESET_RE.items():
        m = pat.search(wf_logic_init)
        if m:
            towns = _TOWN_NAME_RE.findall(m.group(1))
            presets[name] = towns
    return presets


# ---------------------------------------------------------------------------
# Camp / defense extraction from a Vehicles block
# ---------------------------------------------------------------------------

_DEFENSE_KIND_RE = re.compile(
    r"wfbe_defense_kind['\"]?\s*,\s*\[([^\]]+)\]"
)


def _extract_camps_and_defenses(vehicles_body: str) -> tuple[list, list]:
    """
    Given the body text of a 'class Vehicles { ... }' block (already found to
    contain a LocationLogicDepot), collect all sibling:
      - LocationLogicCamp  → camps: [{pos:[x,y]}]
      - Logic with wfbe_defense_kind annotation → defenses: [{pos:[x,y], kind:[...]}]

    Returns (camps, defenses).
    """
    camps: list[dict] = []
    defenses: list[dict] = []

    # Find all ItemN sub-blocks within this Vehicles body
    item_re = re.compile(r'class\s+Item\d+\s*\{')
    for item_m in item_re.finditer(vehicles_body):
        brace_idx = item_m.end() - 1  # index of '{'
        try:
            body_s, body_e = _find_class_block(vehicles_body, brace_idx)
        except ValueError:
            continue
        item_body = vehicles_body[body_s:body_e]

        # Determine vehicle type for this item
        veh_m = re.search(r'vehicle\s*=\s*"([^"]+)"', item_body)
        if not veh_m:
            continue
        vtype = veh_m.group(1)

        pos_xy = _parse_pos(item_body)
        if pos_xy is None:
            continue

        if vtype == 'LocationLogicCamp':
            camps.append({'pos': pos_xy})

        elif vtype == 'Logic':
            # Check for defense annotation
            init_m = re.search(r'init\s*=\s*"([^"]*(?:""[^"]*)*)"', item_body)
            if not init_m:
                continue
            init_raw = _undouble(init_m.group(1))
            kind_m = _DEFENSE_KIND_RE.search(init_raw)
            if kind_m:
                kinds = re.findall(r"'([^']+)'|\"([^\"]+)\"", kind_m.group(1))
                kind_list = [k for pair in kinds for k in pair if k]
                defenses.append({'pos': pos_xy, 'kind': kind_list})

    return camps, defenses


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def extract_towns(sqm_text: str) -> dict:
    """
    Parse a mission.sqm text and return:
      {
        "towns":   [{ name, pos, dubbing, startSV, maxSV, value, type }],
        "spawns":  [{ pos, side, spawn_pos }],
        "airports":[{ pos }],
        "presets": { "XSmall": [...], ... },
      }
    """
    towns = []
    spawns = []
    airports = []
    presets = {}

    # We process the file as a flat text with regex anchoring on vehicle= lines.
    # For each interesting vehicle type we then extract the enclosing class Item0 block.

    # The SQM structure is:
    #   class ItemN {  <- group
    #     side="LOGIC";
    #     class Vehicles {
    #       items=N;
    #       class Item0 {    <- the primary entity (depot, spawn, airport)
    #         position[]={...};
    #         vehicle="...";
    #         init="...";
    #       };
    #       ...
    #     };
    #   };

    # We search for vehicle="X" and then walk backwards to find the enclosing
    # class Item0 { block, which contains the position[].

    vehicle_re = re.compile(r'vehicle\s*=\s*"(LocationLogicDepot|LocationLogicStart|LocationLogicAirport|Logic)"')

    # WF_Logic is a Logic vehicle with text="WF_Logic"
    wf_logic_re = re.compile(r'text\s*=\s*"WF_Logic"')

    # Pattern to find "class Vehicles {" — used to get the enclosing Vehicles block
    vehicles_class_re = re.compile(r'class\s+Vehicles\s*\{')

    for m in vehicle_re.finditer(sqm_text):
        vtype = m.group(1)
        pos_in_text = m.start()

        # Walk backwards to find the start of the enclosing class Item0 {
        # We look for "class Item0" + its opening brace before pos_in_text.
        # We search for the pattern "class Item0 {" (with optional whitespace)
        # and use the position of the trailing "{" as the brace to match.
        preceding = sqm_text[:pos_in_text]
        item0_re = re.compile(r'class\s+Item0\s*\{')
        item0_matches = list(item0_re.finditer(preceding))
        if not item0_matches:
            continue
        last_item0 = item0_matches[-1]
        # The opening brace is the last char of the match
        brace_idx = last_item0.end() - 1

        # Now find the matching closing brace starting from brace_idx in the full text
        try:
            body_s, body_e = _find_class_block(sqm_text, brace_idx)
        except ValueError:
            continue

        item0_body = sqm_text[body_s:body_e]

        # Sanity: the vehicle= match must be inside this block
        if not (body_s <= pos_in_text <= body_e):
            continue

        pos_xy = _parse_pos(item0_body)
        if pos_xy is None:
            continue

        if vtype == "LocationLogicDepot":
            init_m = re.search(r'init\s*=\s*"([^"]*(?:""[^"]*)*)"', item0_body)
            if not init_m:
                continue
            init_raw = _undouble(init_m.group(1))
            parsed = _parse_init_args(init_raw)
            if parsed is None:
                continue
            parsed["pos"] = pos_xy

            # Find the enclosing Vehicles block to extract sibling camps + defenses.
            # The Item0 block starts at brace_idx in sqm_text; walk back to Vehicles {.
            preceding_to_item0 = sqm_text[:brace_idx]
            veh_matches = list(vehicles_class_re.finditer(preceding_to_item0))
            if veh_matches:
                veh_brace_idx = veh_matches[-1].end() - 1
                try:
                    veh_bs, veh_be = _find_class_block(sqm_text, veh_brace_idx)
                    vehicles_body = sqm_text[veh_bs:veh_be]
                    camps, defenses = _extract_camps_and_defenses(vehicles_body)
                    parsed["camps"] = camps
                    parsed["defenses"] = defenses
                except ValueError:
                    parsed["camps"] = []
                    parsed["defenses"] = []
            else:
                parsed["camps"] = []
                parsed["defenses"] = []

            towns.append(parsed)

        elif vtype == "LocationLogicStart":
            init_m = re.search(r'init\s*=\s*"([^"]*(?:""[^"]*)*)"', item0_body)
            init_raw = _undouble(init_m.group(1)) if init_m else ""
            side, spawn_pos = _parse_spawn_init(init_raw)
            spawns.append({"pos": pos_xy, "side": side, "spawn_pos": spawn_pos})

        elif vtype == "LocationLogicAirport":
            airports.append({"pos": pos_xy})

        elif vtype == "Logic":
            # Check if this is WF_Logic
            if wf_logic_re.search(item0_body):
                init_m = re.search(r'init\s*=\s*"([^"]*(?:""[^"]*)*)"', item0_body)
                if init_m:
                    init_raw = _undouble(init_m.group(1))
                    presets = _parse_presets(init_raw)

    return {
        "towns": towns,
        "spawns": spawns,
        "airports": airports,
        "presets": presets,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_one(sqm_path: str, map_name: str) -> dict:
    text = Path(sqm_path).read_text(encoding="utf-8", errors="replace")
    result = extract_towns(text)
    result["map"] = map_name
    result["size"] = _MAP_SIZES.get(map_name, 15360)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Parse WASP mission.sqm → seed-towns.json")
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--mission", help="Path to mission dir or mission.sqm file")
    grp.add_argument("--both", help="Path to a2waspwarfare root (finds both missions)")
    parser.add_argument("--map", help="Map name (chernarus/takistan); auto-detected if omitted")
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent.parent / "assets" / "data" / "seed-towns.json"),
        help="Output JSON path (default: assets/data/seed-towns.json)",
    )
    args = parser.parse_args(argv)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing output if it exists (to merge both maps)
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
    else:
        existing = {}

    if args.both:
        root = Path(args.both)
        chern_dir = root / "Missions" / "[55-2hc]warfarev2_073v48co.chernarus"
        tak_dir = root / "Missions_Vanilla" / "[61-2hc]warfarev2_073v48co.takistan"
        missions = [
            (_find_sqm(str(chern_dir)), "chernarus"),
            (_find_sqm(str(tak_dir)), "takistan"),
        ]
        output = {}
        for sqm_path, map_name in missions:
            print(f"Parsing {map_name}: {sqm_path}")
            data = _parse_one(sqm_path, map_name)
            output[map_name] = data
            _print_summary(map_name, data)
    else:
        sqm_path = _find_sqm(args.mission)
        map_name = args.map or _detect_map(args.mission)
        print(f"Parsing {map_name}: {sqm_path}")
        data = _parse_one(sqm_path, map_name)
        existing[map_name] = data
        output = existing
        _print_summary(map_name, data)

    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {out_path}")


def _print_summary(map_name: str, data: dict) -> None:
    total_camps = sum(len(t.get("camps", [])) for t in data["towns"])
    total_defs = sum(len(t.get("defenses", [])) for t in data["towns"])
    print(f"  towns={len(data['towns'])}  spawns={len(data['spawns'])}  "
          f"airports={len(data['airports'])}  presets={list(data['presets'].keys())}  "
          f"camps={total_camps}  defenses={total_defs}")
    # Sanity: show Kamenka if present
    for t in data["towns"]:
        if t["name"].lower() == "kamenka":
            print(f"  Kamenka pos={t['pos']}  value={t['value']}  "
                  f"camps={t.get('camps',[])}  defenses={len(t.get('defenses',[]))}")
            break


if __name__ == "__main__":
    main()
