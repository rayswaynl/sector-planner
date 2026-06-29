"""
extract_template.py — Parse the Chernarus WASP mission.sqm into a structured
boilerplate template (mission-template.json) for the V3 mission generator.

Classifies every group under class Groups:
  KEEP:
    player slots       (player="PLAY CDG") — side + vehicleClass + cluster-relative offset
    owner logics       (LocationLogicOwnerWest/East) — side + text + sync side
    WF_Logic shell     — position + non-town-specific init tail
    utility            (FunctionsManager, RCoin, MCoin) — vehicle + text + position
    markers            (class Markers) — all 5

  DROP (injected by the generator):
    town groups        (contain LocationLogicDepot/LocationLogicCamp/defense Logic)
    LocationLogicStart / LocationLogicAirport

Usage:
  python tools/extract_template.py [--mission <path>] [--out <path>]
  python tools/extract_template.py  # uses defaults
"""

import re
import json
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared helpers (mirror extract_towns.py discipline)
# ---------------------------------------------------------------------------

def _undouble(s: str) -> str:
    """Un-double .sqm quote escaping: \"\"  ->  \" """
    return s.replace('""', '"')


def _find_class_block(text: str, start: int) -> tuple[int, int]:
    """
    Given that text[start] == '{', scan forward counting braces and return
    (body_start, body_end) where text[body_start:body_end] is the content
    between the outer braces (exclusive).
    """
    depth = 0
    i = start
    body_start = start + 1
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


_POS3_RE = re.compile(r'position\[\]\s*=\s*\{([^}]+)\}')


def _parse_pos3(block: str) -> list[float] | None:
    """Return [x, y, z] from position[]={x, alt, z}."""
    m = _POS3_RE.search(block)
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(',')]
    if len(parts) < 3:
        return None
    return [round(float(p), 4) for p in parts[:3]]


def _parse_array_field(text: str, field: str) -> list[int]:
    """Parse `field[]={1,2,3}` into a list of ints."""
    pat = re.compile(rf'{re.escape(field)}\[\]\s*=\s*\{{([^}}]*)\}}')
    m = pat.search(text)
    if not m or not m.group(1).strip():
        return []
    return [int(x.strip()) for x in m.group(1).split(',') if x.strip().lstrip('-').isdigit()]


def count_items(text: str) -> int:
    """
    Count the number of class ItemN { ... } blocks at the TOP level of *text*
    (one brace depth only — does not recurse into nested ItemN).

    This is the reusable helper for the emitter to verify items=N correctness.
    """
    count = 0
    i = 0
    item_re = re.compile(r'class\s+Item\d+\s*\{')
    while i < len(text):
        m = item_re.search(text, i)
        if not m:
            break
        brace_idx = m.end() - 1
        try:
            _, end = _find_class_block(text, brace_idx)
        except ValueError:
            i = m.end()
            continue
        count += 1
        i = end + 1
    return count


# ---------------------------------------------------------------------------
# Top-level block extractors
# ---------------------------------------------------------------------------

def _extract_top_class(text: str, class_name: str) -> str | None:
    """Return the body (between braces) of the first `class <name> { ... }` at top level."""
    pat = re.compile(rf'class\s+{re.escape(class_name)}\s*\{{')
    m = pat.search(text)
    if not m:
        return None
    brace_idx = m.end() - 1
    body_s, body_e = _find_class_block(text, brace_idx)
    return text[body_s:body_e]


def _extract_addon_list(text: str, field: str) -> list[str]:
    """Parse addOns[] = { "x", "y" }; or addOnsAuto[] = {...}."""
    pat = re.compile(rf'{re.escape(field)}\[\]\s*=\s*\{{([^}}]*)\}}', re.DOTALL)
    m = pat.search(text)
    if not m:
        return []
    raw = m.group(1)
    return [s.strip().strip('"') for s in raw.split(',') if s.strip().strip('"')]


# ---------------------------------------------------------------------------
# Group classifier
# ---------------------------------------------------------------------------

# Regex patterns reused across groups
_VEHICLE_RE = re.compile(r'vehicle\s*=\s*"([^"]+)"')
_SIDE_RE = re.compile(r'^\s*side\s*=\s*"([^"]+)"', re.MULTILINE)
_TEXT_RE = re.compile(r'text\s*=\s*"([^"]+)"')
_PLAYER_RE = re.compile(r'player\s*=\s*"PLAY CDG"')
_RANK_RE = re.compile(r'rank\s*=\s*"([^"]+)"')
_INIT_RE = re.compile(r'init\s*=\s*"((?:[^"\\]|"")*)"')
_DESC_RE = re.compile(r'description\s*=\s*"([^"]+)"')
_ID_RE = re.compile(r'\bid\s*=\s*(\d+)')
_FHC_RE = re.compile(r'forceHeadlessClient\s*=\s*1')
_LEADER_RE = re.compile(r'leader\s*=\s*1')
_AZIMUT_RE = re.compile(r'azimut\s*=\s*([\d.]+)')


# Town-marker vehicle types — groups containing these are DROPPED
_TOWN_VEHICLES = frozenset([
    'LocationLogicDepot', 'LocationLogicCamp',
])

# Injected-at-generate-time logics — DROPPED
_INJECTED_VEHICLES = frozenset([
    'LocationLogicStart', 'LocationLogicAirport',
])

# Utility logics — KEPT
_UTILITY_TEXT = frozenset(['FunctionsManager', 'RCoin', 'MCoin'])


def _is_town_group(vehicles_body: str) -> bool:
    """True if this group's Vehicles block contains a depot or camp."""
    for m in _VEHICLE_RE.finditer(vehicles_body):
        if m.group(1) in _TOWN_VEHICLES:
            return True
    # Also catch defense Logic groups that sync to a depot (wfbe_defense_kind)
    if "wfbe_defense_kind" in vehicles_body:
        return True
    return False


def _is_injected_group(vehicles_body: str) -> bool:
    """True if this group contains only LocationLogicStart/Airport vehicles."""
    for m in _VEHICLE_RE.finditer(vehicles_body):
        if m.group(1) in _INJECTED_VEHICLES:
            return True
    return False


def _parse_item0_block(vehicles_body: str) -> tuple[str, int, int] | None:
    """
    Extract the class Item0 { ... } body from a Vehicles block body.
    Returns (item0_body, body_start, body_end) or None.
    """
    m = re.search(r'class\s+Item0\s*\{', vehicles_body)
    if not m:
        return None
    brace_idx = vehicles_body.index('{', m.start())
    body_s, body_e = _find_class_block(vehicles_body, brace_idx)
    return vehicles_body[body_s:body_e], body_s, body_e


def _classify_group(group_body: str) -> dict | None:
    """
    Classify a single group (Item body text). Returns a classification dict or None
    if the group should be dropped.

    Returns one of:
      {kind: "slot",    ...}
      {kind: "owner",   ...}
      {kind: "wf_logic",...}
      {kind: "utility", ...}
    or None (drop).
    """
    # Get the group-level side
    side_m = _SIDE_RE.search(group_body)
    group_side = side_m.group(1) if side_m else "LOGIC"

    # Find class Vehicles { ... } body
    veh_pat = re.compile(r'class\s+Vehicles\s*\{')
    vm = veh_pat.search(group_body)
    if not vm:
        return None
    veh_brace = vm.end() - 1
    veh_bs, veh_be = _find_class_block(group_body, veh_brace)
    vehicles_body = group_body[veh_bs:veh_be]

    # --- DROP: town groups
    if _is_town_group(vehicles_body):
        return None

    # --- DROP: injected groups (Start/Airport)
    if _is_injected_group(vehicles_body):
        return None

    # Parse Item0
    result = _parse_item0_block(vehicles_body)
    if not result:
        return None
    item0_body = result[0]

    veh_m = _VEHICLE_RE.search(item0_body)
    if not veh_m:
        return None
    vehicle = veh_m.group(1)

    text_m = _TEXT_RE.search(item0_body)
    text_val = text_m.group(1) if text_m else ""

    pos3 = _parse_pos3(item0_body)
    id_m = _ID_RE.search(item0_body)
    entity_id = int(id_m.group(1)) if id_m else None

    # --- KEEP: player slots
    if _PLAYER_RE.search(item0_body):
        side_item_m = _SIDE_RE.search(item0_body)
        side = side_item_m.group(1) if side_item_m else group_side
        rank_m = _RANK_RE.search(item0_body)
        init_m = _INIT_RE.search(item0_body)
        init_raw = _undouble(init_m.group(1)) if init_m else ""
        desc_m = _DESC_RE.search(item0_body)
        fhc = bool(_FHC_RE.search(item0_body))
        syncs = _parse_array_field(item0_body, "synchronizations")
        return {
            "kind": "slot",
            "side": side,
            "vehicleClass": vehicle,
            "position": pos3,
            "id": entity_id,
            "leader": bool(_LEADER_RE.search(item0_body)),
            "rank": rank_m.group(1) if rank_m else None,
            "init": init_raw or None,
            "description": desc_m.group(1) if desc_m else None,
            "forceHeadlessClient": fhc,
            "synchronizations": syncs,
        }

    # --- KEEP: owner logics
    if vehicle in ("LocationLogicOwnerWest", "LocationLogicOwnerEast"):
        syncs = _parse_array_field(item0_body, "synchronizations")
        owner_side = "WEST" if vehicle == "LocationLogicOwnerWest" else "EAST"
        return {
            "kind": "owner",
            "side": owner_side,
            "vehicle": vehicle,
            "text": text_val,
            "position": pos3,
            "id": entity_id,
            "synchronizations": syncs,
        }

    # --- KEEP: WF_Logic shell
    if vehicle == "Logic" and text_val == "WF_Logic":
        init_m = _INIT_RE.search(item0_body)
        init_raw = _undouble(init_m.group(1)) if init_m else ""
        # Strip town-specific variables: totalTowns, Towns_Removed*
        tail = _strip_town_vars(init_raw)
        return {
            "kind": "wf_logic",
            "position": pos3,
            "id": entity_id,
            "init_tail": tail,
        }

    # --- KEEP: utility (FunctionsManager, RCoin, MCoin)
    # FunctionsManager has no text field; identify by vehicle name
    is_utility = (
        vehicle == "FunctionsManager"
        or (vehicle == "Logic" and text_val in _UTILITY_TEXT)
    )
    if is_utility:
        label = text_val if text_val else vehicle
        return {
            "kind": "utility",
            "vehicle": vehicle,
            "text": label,
            "position": pos3,
            "id": entity_id,
        }

    # Anything else (unknown Logic etc.) — drop
    return None


_TOWN_VAR_RE = re.compile(
    # Matches after _undouble() has been applied — single " delimiters
    r'this\s+setVariable\s*\["(totalTowns|Towns_Removed[^"]*)"'
    r'\s*,\s*(?:\d+|\[[^\]]*\])\s*\]\s*;?',
    re.DOTALL,
)


def _strip_town_vars(init: str) -> str:
    """Remove totalTowns / Towns_Removed* setVariable calls from WF_Logic init."""
    cleaned = _TOWN_VAR_RE.sub('', init)
    # Collapse multiple whitespace runs
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    return cleaned


# ---------------------------------------------------------------------------
# Markers extractor
# ---------------------------------------------------------------------------

def _parse_markers(markers_body: str) -> list[dict]:
    """Extract all class ItemN marker blocks from the Markers body."""
    markers = []
    item_re = re.compile(r'class\s+Item\d+\s*\{')
    for m in item_re.finditer(markers_body):
        brace_idx = m.end() - 1
        try:
            body_s, body_e = _find_class_block(markers_body, brace_idx)
        except ValueError:
            continue
        item_body = markers_body[body_s:body_e]

        pos3 = _parse_pos3(item_body)
        name_m = re.search(r'name\s*=\s*"([^"]+)"', item_body)
        type_m = re.search(r'type\s*=\s*"([^"]+)"', item_body)
        text_m = re.search(r'text\s*=\s*"([^"]+)"', item_body)
        color_m = re.search(r'colorName\s*=\s*"([^"]+)"', item_body)
        mtype_m = re.search(r'markerType\s*=\s*"([^"]+)"', item_body)
        a_m = re.search(r'\ba\s*=\s*([\d.]+)', item_body)
        b_m = re.search(r'\bb\s*=\s*([\d.]+)', item_body)

        marker = {"position": pos3, "name": name_m.group(1) if name_m else ""}
        if type_m:
            marker["type"] = type_m.group(1)
        if text_m:
            marker["text"] = text_m.group(1)
        if color_m:
            marker["colorName"] = color_m.group(1)
        if mtype_m:
            marker["markerType"] = mtype_m.group(1)
        if a_m:
            marker["a"] = float(a_m.group(1))
        if b_m:
            marker["b"] = float(b_m.group(1))
        markers.append(marker)
    return markers


# ---------------------------------------------------------------------------
# Intel block extractor
# ---------------------------------------------------------------------------

def _parse_intel(intel_body: str) -> dict:
    out = {}
    for field in ("briefingName", "briefingDescription"):
        m = re.search(rf'{field}\s*=\s*"([^"]*)"', intel_body)
        if m:
            out[field] = m.group(1)
    for field in ("resistanceWest", "startWeather", "forecastWeather",
                  "year", "month", "day", "hour", "minute"):
        m = re.search(rf'{field}\s*=\s*([\d.]+)', intel_body)
        if m:
            val = m.group(1)
            out[field] = float(val) if '.' in val else int(val)
    return out


# ---------------------------------------------------------------------------
# Staging cluster helpers
# ---------------------------------------------------------------------------

def _mean_pos(positions: list[list[float]]) -> list[float]:
    """Return the centroid of a list of [x, y, z] positions."""
    if not positions:
        return [0.0, 0.0, 0.0]
    n = len(positions)
    return [
        round(sum(p[i] for p in positions) / n, 4)
        for i in range(3)
    ]


def _sub3(a: list[float], b: list[float]) -> list[float]:
    return [round(a[i] - b[i], 4) for i in range(3)]


# ---------------------------------------------------------------------------
# AddOns classifier
# ---------------------------------------------------------------------------

_WORLD_ADDONS = frozenset([
    "chernarus", "takistan", "zargabad", "utes", "shapur_baf",
    "intro", "desert2", "stratis", "altis",
])

_BASE_ADDONS = frozenset([
    "ca_modules_functions", "warfare2vehicles", "ca_highcommand",
    "ca_modules_functions_e", "ca_modules_functions_acr",
])


def _split_addons(addon_list: list[str]) -> dict:
    """
    Split a flat addOns[] list into:
      world:   terrain PBO entries
      base:    always-present infrastructure
      faction: everything else (soldier classes, vehicles)
    """
    world = [a for a in addon_list if a.lower() in _WORLD_ADDONS]
    base = [a for a in addon_list if a.lower() in _BASE_ADDONS]
    faction = [a for a in addon_list if a.lower() not in _WORLD_ADDONS and a.lower() not in _BASE_ADDONS]
    return {"world": world, "base": base, "faction": faction}


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_template(sqm_text: str) -> dict:
    """
    Parse a mission.sqm text and return the structured template dict.

    Schema (abbreviated):
    {
      "header": {
        "version": int,
        "addOns": {world, base, faction},
        "addOnsAuto": {world, base, faction},
        "randomSeed": int,
        "intel": {...},
        "intro":   {addOns, addOnsAuto, randomSeed, intel},
        "outroWin":{...},
        "outroLoose":{...},
      },
      "slots": {
        "west":  [{vehicleClass, position, offset, id, leader, rank, init, description, synchronizations}],
        "east":  [...],
        "civ":   [...],
      },
      "stagingClusters": {
        "west": {"anchor": [x,y,z]},
        "east": {"anchor": [x,y,z]},
        "civ":  {"anchor": [x,y,z]},
      },
      "owners": {
        "west": {vehicle, text, position, id, synchronizations},
        "east": {...},
      },
      "wfLogic": {position, id, init_tail},
      "utility": [{vehicle, text, position, id}],
      "markers": [{name, type, position, ...attrs}],
    }
    """
    # --- Header ---
    version_m = re.match(r'version\s*=\s*(\d+)', sqm_text)
    version = int(version_m.group(1)) if version_m else 11

    mission_body = _extract_top_class(sqm_text, "Mission")
    if mission_body is None:
        raise ValueError("class Mission { ... } not found in sqm_text")

    raw_addons = _extract_addon_list(mission_body, "addOns")
    raw_addons_auto = _extract_addon_list(mission_body, "addOnsAuto")
    seed_m = re.search(r'randomSeed\s*=\s*(\d+)', mission_body)
    random_seed = int(seed_m.group(1)) if seed_m else 0

    intel_body = _extract_top_class(mission_body, "Intel")
    intel = _parse_intel(intel_body) if intel_body else {}

    # Outro / Intro blocks (siblings of Mission at root level)
    def _parse_sibling(name: str) -> dict:
        body = _extract_top_class(sqm_text, name)
        if body is None:
            return {}
        ib = _extract_top_class(body, "Intel")
        return {
            "addOns": _split_addons(_extract_addon_list(body, "addOns")),
            "addOnsAuto": _split_addons(_extract_addon_list(body, "addOnsAuto")),
            "randomSeed": int(m.group(1)) if (m := re.search(r'randomSeed\s*=\s*(\d+)', body)) else 0,
            "intel": _parse_intel(ib) if ib else {},
        }

    header = {
        "version": version,
        "addOns": _split_addons(raw_addons),
        "addOnsAuto": _split_addons(raw_addons_auto),
        "randomSeed": random_seed,
        "intel": intel,
        "intro": _parse_sibling("Intro"),
        "outroWin": _parse_sibling("OutroWin"),
        "outroLoose": _parse_sibling("OutroLoose"),
    }

    # --- Groups ---
    groups_body = _extract_top_class(mission_body, "Groups")
    if groups_body is None:
        raise ValueError("class Groups { ... } not found inside class Mission")

    slots: dict[str, list] = {"west": [], "east": [], "civ": []}
    owners: dict[str, dict] = {}
    wf_logic: dict | None = None
    utility: list[dict] = []

    # Iterate over all ItemN groups
    item_re = re.compile(r'class\s+Item\d+\s*\{')
    i = 0
    while i < len(groups_body):
        m = item_re.search(groups_body, i)
        if not m:
            break
        brace_idx = m.end() - 1
        try:
            body_s, body_e = _find_class_block(groups_body, brace_idx)
        except ValueError:
            i = m.end()
            continue
        group_body = groups_body[body_s:body_e]
        i = body_e + 1

        result = _classify_group(group_body)
        if result is None:
            continue

        kind = result["kind"]
        if kind == "slot":
            side = result["side"].lower()
            if side in slots:
                slots[side].append(result)
            # else: unknown side, skip
        elif kind == "owner":
            owners[result["side"].lower()] = result
        elif kind == "wf_logic":
            wf_logic = result
        elif kind == "utility":
            utility.append(result)

    # --- Compute staging clusters (per-side mean position, then offsets) ---
    staging_clusters: dict[str, dict] = {}
    for side, slot_list in slots.items():
        positions = [s["position"] for s in slot_list if s["position"]]
        if positions:
            anchor = _mean_pos(positions)
            staging_clusters[side] = {"anchor": anchor}
            # Store offset in each slot
            for s in slot_list:
                if s["position"]:
                    s["offset"] = _sub3(s["position"], anchor)
                else:
                    s["offset"] = [0.0, 0.0, 0.0]
        else:
            staging_clusters[side] = {"anchor": [0.0, 0.0, 0.0]}

    # --- Markers ---
    markers_body = _extract_top_class(mission_body, "Markers")
    markers = _parse_markers(markers_body) if markers_body else []

    return {
        "header": header,
        "slots": slots,
        "stagingClusters": staging_clusters,
        "owners": owners,
        "wfLogic": wf_logic,
        "utility": utility,
        "markers": markers,
    }


# ---------------------------------------------------------------------------
# Sanity printer
# ---------------------------------------------------------------------------

def print_summary(template: dict) -> None:
    h = template["header"]
    addon_split = h["addOns"]
    print(f"version={h['version']}  randomSeed={h['randomSeed']}")
    print(f"addOns world={addon_split['world']}  base={addon_split['base']}  faction={addon_split['faction']}")

    slots = template["slots"]
    print(f"slots: west={len(slots['west'])}  east={len(slots['east'])}  civ={len(slots['civ'])}")
    for side, anchor_data in template["stagingClusters"].items():
        a = anchor_data["anchor"]
        print(f"  cluster {side}: anchor=[{a[0]:.1f}, {a[1]:.1f}, {a[2]:.1f}]")

    owners = template["owners"]
    print(f"owners: {list(owners.keys())}  ({len(owners)} total)")
    for side, o in owners.items():
        print(f"  {side}: text={o['text']}  syncs={len(o['synchronizations'])} ids")

    wfl = template["wfLogic"]
    if wfl:
        print(f"wfLogic: id={wfl['id']}  pos={wfl['position']}  init_tail len={len(wfl['init_tail'])}")

    print(f"utility: {[u['text'] for u in template['utility']]}")
    print(f"markers: {[mk['name'] for mk in template['markers']]}")

    # Sanity checks
    west_count = len(slots["west"])
    east_count = len(slots["east"])
    civ_count = len(slots["civ"])
    assert west_count >= 20, f"Expected ≥20 WEST slots, got {west_count}"
    assert east_count >= 20, f"Expected ≥20 EAST slots, got {east_count}"
    assert len(owners) == 2, f"Expected 2 owners, got {len(owners)}"
    assert len(template["markers"]) == 5, f"Expected 5 markers, got {len(template['markers'])}"
    assert len(template["utility"]) == 3, f"Expected 3 utility, got {len(template['utility'])}"
    assert wfl is not None, "WF_Logic missing"
    assert addon_split["world"] == ["chernarus"] or "chernarus" in addon_split["world"], \
        f"World entry not chernarus: {addon_split['world']}"
    print("Sanity OK.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

_DEFAULT_SQM = (
    r"C:\Users\Steff\a2waspwarfare\Missions"
    r"\[55-2hc]warfarev2_073v48co.chernarus\mission.sqm"
)
_DEFAULT_OUT = str(
    Path(__file__).parent.parent / "assets" / "data" / "mission-template.json"
)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Parse WASP mission.sqm → mission-template.json"
    )
    parser.add_argument("--mission", default=_DEFAULT_SQM,
                        help="Path to mission.sqm (default: Chernarus)")
    parser.add_argument("--out", default=_DEFAULT_OUT,
                        help="Output JSON path (default: assets/data/mission-template.json)")
    args = parser.parse_args(argv)

    sqm_path = Path(args.mission)
    if not sqm_path.exists():
        print(f"ERROR: mission.sqm not found at {sqm_path}", flush=True)
        raise SystemExit(1)

    print(f"Parsing: {sqm_path}")
    text = sqm_path.read_text(encoding="utf-8", errors="replace")
    template = extract_template(text)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(template, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    size_kb = out_path.stat().st_size // 1024
    print(f"Wrote {out_path}  ({size_kb} KB)")
    print()
    print_summary(template)


if __name__ == "__main__":
    main()
