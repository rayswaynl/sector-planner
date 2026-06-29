"""
Unit tests for extract_towns.py — no filesystem dependencies.
All fixtures are inline strings.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from extract_towns import extract_towns, _undouble, _parse_init_args, _parse_presets


# ---------------------------------------------------------------------------
# Minimal SQM fixture helpers
# ---------------------------------------------------------------------------

def _make_depot_group(pos_x, pos_alt, pos_y, init_str,
                      camps=None, defenses=None):
    """Build a minimal group block containing one LocationLogicDepot and
    optional sibling LocationLogicCamp + defense Logic entities."""
    sibling_items = ""
    item_idx = 1
    for camp_pos in (camps or []):
        cx, cy = camp_pos
        sibling_items += f"""
                class Item{item_idx} {{
                    position[]={{{cx},5,{cy}}};
                    id={100 + item_idx};
                    side="LOGIC";
                    vehicle="LocationLogicCamp";
                    skill=0.60000002;
                    init="this enableSimulation false;";
                    synchronizations[]={{4}};
                }};"""
        item_idx += 1
    for def_info in (defenses or []):
        dx, dy = def_info["pos"]
        kind_str = ",".join(f"'{k}'" for k in def_info["kind"])
        sibling_items += f"""
                class Item{item_idx} {{
                    position[]={{{dx},10,{dy}}};
                    id={200 + item_idx};
                    side="LOGIC";
                    vehicle="Logic";
                    skill=0.60000002;
                    init="this setVariable ['wfbe_defense_kind', [{kind_str}]];";
                    synchronizations[]={{4}};
                }};"""
        item_idx += 1
    total_items = item_idx  # items= count
    return f"""
        class ItemN {{
            side="LOGIC";
            class Vehicles {{
                items={total_items};
                class Item0 {{
                    position[]={{{pos_x},{pos_alt},{pos_y}}};
                    azimut=160;
                    special="NONE";
                    id=4;
                    side="LOGIC";
                    vehicle="LocationLogicDepot";
                    leader=1;
                    skill=0.60000002;
                    text="TestTown";
                    init="{init_str}";
                    synchronizations[]={{5,6}};
                }};{sibling_items}
            }};
        }};
"""


def _make_spawn_group(pos_x, pos_alt, pos_y, init_str=""):
    """Build a minimal group block containing one LocationLogicStart."""
    init_line = f'init="{init_str}";' if init_str else ""
    return f"""
        class ItemSpawn {{
            side="LOGIC";
            class Vehicles {{
                items=1;
                class Item0 {{
                    position[]={{{pos_x},{pos_alt},{pos_y}}};
                    id=99;
                    side="LOGIC";
                    vehicle="LocationLogicStart";
                    leader=1;
                    skill=0.60000002;
                    {init_line}
                }};
            }};
        }};
"""


def _make_airport_group(pos_x, pos_alt, pos_y):
    return f"""
        class ItemAirport {{
            side="LOGIC";
            class Vehicles {{
                items=1;
                class Item0 {{
                    position[]={{{pos_x},{pos_alt},{pos_y}}};
                    id=200;
                    side="LOGIC";
                    vehicle="LocationLogicAirport";
                    leader=1;
                    skill=0.60000002;
                    init="this enableSimulation false;";
                }};
            }};
        }};
"""


def _make_wflogic_group(preset_str=""):
    init = (
        'this setVariable [""totalTowns"",5];'
        + preset_str
        + ' nullReturn = [this] ExecVM ""Common\\Init\\Init_TownMode.sqf""'
    )
    return f"""
        class ItemWF {{
            side="LOGIC";
            class Vehicles {{
                items=1;
                class Item0 {{
                    position[]={{100,0,100}};
                    id=999;
                    side="LOGIC";
                    vehicle="Logic";
                    leader=1;
                    skill=0.60000002;
                    text="WF_Logic";
                    init="{init}";
                }};
            }};
        }};
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUndouble(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_undouble('say ""hello""'), 'say "hello"')

    def test_no_change(self):
        self.assertEqual(_undouble("plain"), "plain")


class TestParseInitArgs(unittest.TestCase):
    def _init(self, raw):
        return _parse_init_args(_undouble(raw))

    def test_array_type(self):
        raw = '[this,""Kamenka"",""++"",10,45,300,[""SmallTown1"",""SmallTown2""]] execVM ""x.sqf"";'
        result = self._init(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Kamenka")
        self.assertEqual(result["dubbing"], "++")
        self.assertEqual(result["startSV"], 10)
        self.assertEqual(result["maxSV"], 45)
        self.assertEqual(result["value"], 300)
        self.assertEqual(result["type"], ["SmallTown1", "SmallTown2"])

    def test_bare_string_type(self):
        raw = '[this,""Landay"",""++"",10,40,400,""SmallTown1""] execVM ""x.sqf"";'
        result = self._init(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Landay")
        self.assertEqual(result["type"], ["SmallTown1"])

    def test_single_element_array(self):
        raw = '[this,""Solo"",""++"",5,20,100,[""TinyTown1""]] execVM ""x.sqf"";'
        result = self._init(raw)
        self.assertEqual(result["type"], ["TinyTown1"])

    def test_name_with_space(self):
        # "Chak Chak" — name can contain spaces
        raw = '[this,""Chak Chak"",""++"",20,80,800,[""LargeTown1"",""LargeTown2""]] execVM ""x.sqf"";'
        result = self._init(raw)
        self.assertEqual(result["name"], "Chak Chak")

    def test_null_return_prefix(self):
        # Real SQM has "nullReturn = [this,..." prefix
        raw = 'nullReturn = [this,""Pavlovo"",""++"",10,45,250,[""SmallTown1"",""SmallTown2""]] execVM ""Common\\Init\\Init_Town.sqf"";this enableSimulation false;'
        result = self._init(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Pavlovo")


class TestExtractTownsDepot(unittest.TestCase):
    """Test extract_towns with depot-only fixtures."""

    def _make_sqm(self, depot_init, pos_x=1827.0815, pos_alt=8.1, pos_y=2260.6648):
        return _make_depot_group(pos_x, pos_alt, pos_y, depot_init)

    def test_array_type_depot(self):
        init = r'nullReturn = [this,""Kamenka"",""++"",10,45,300,[""SmallTown1"",""SmallTown2""]] execVM ""Common\Init\Init_Town.sqf"";this enableSimulation false;'
        sqm = self._make_sqm(init)
        result = extract_towns(sqm)
        self.assertEqual(len(result["towns"]), 1)
        town = result["towns"][0]
        self.assertEqual(town["name"], "Kamenka")
        self.assertAlmostEqual(town["pos"][0], 1827.0815, places=2)
        self.assertAlmostEqual(town["pos"][1], 2260.6648, places=2)
        self.assertEqual(town["startSV"], 10)
        self.assertEqual(town["maxSV"], 45)
        self.assertEqual(town["value"], 300)
        self.assertIsInstance(town["type"], list)
        self.assertEqual(town["type"], ["SmallTown1", "SmallTown2"])

    def test_bare_string_type_depot(self):
        init = r'nullReturn = [this,""Landay"",""++"",10,40,400,""SmallTown1""] execVM ""Common\Init\Init_Town.sqf"";this enableSimulation false;'
        sqm = self._make_sqm(init, pos_x=2100.0, pos_alt=365.0, pos_y=479.0)
        result = extract_towns(sqm)
        self.assertEqual(len(result["towns"]), 1)
        town = result["towns"][0]
        self.assertEqual(town["name"], "Landay")
        self.assertIsInstance(town["type"], list)
        self.assertEqual(town["type"], ["SmallTown1"])

    def test_pos_x_y_ordering(self):
        """position[]={x, alt, y} — we want index 0 (x) and index 2 (y)."""
        init = r'nullReturn = [this,""PosTest"",""++"",5,20,100,[""TinyTown1""]] execVM ""x.sqf"";'
        sqm = self._make_sqm(init, pos_x=111.1, pos_alt=999.9, pos_y=222.2)
        town = extract_towns(sqm)["towns"][0]
        self.assertAlmostEqual(town["pos"][0], 111.1, places=1)
        self.assertAlmostEqual(town["pos"][1], 222.2, places=1)

    def test_dubbing_extracted(self):
        init = r'nullReturn = [this,""Town"",""NW"",5,10,50,[""TinyTown1""]] execVM ""x.sqf"";'
        sqm = self._make_sqm(init)
        town = extract_towns(sqm)["towns"][0]
        self.assertEqual(town["dubbing"], "NW")


class TestExtractTownsSpawns(unittest.TestCase):
    def test_spawn_no_annotation(self):
        sqm = _make_spawn_group(100, 10, 200)
        result = extract_towns(sqm)
        self.assertEqual(len(result["spawns"]), 1)
        s = result["spawns"][0]
        self.assertAlmostEqual(s["pos"][0], 100.0, places=1)
        self.assertAlmostEqual(s["pos"][1], 200.0, places=1)
        self.assertIsNone(s["side"])
        self.assertIsNone(s["spawn_pos"])

    def test_spawn_with_wfbe_annotations(self):
        init = r'this setVariable [""wfbe_default"", west]; this setVariable [""wfbe_spawn"", ""north""];'
        sqm = _make_spawn_group(500, 50, 600, init)
        result = extract_towns(sqm)
        s = result["spawns"][0]
        self.assertEqual(s["side"], "west")
        self.assertEqual(s["spawn_pos"], "north")


class TestExtractTownsAirports(unittest.TestCase):
    def test_airport_extracted(self):
        sqm = _make_airport_group(4824.0, 8.9, 2500.5)
        result = extract_towns(sqm)
        self.assertEqual(len(result["airports"]), 1)
        a = result["airports"][0]
        self.assertAlmostEqual(a["pos"][0], 4824.0, places=0)
        self.assertAlmostEqual(a["pos"][1], 2500.5, places=0)


class TestExtractTownsPresets(unittest.TestCase):
    def test_preset_extraction(self):
        preset_str = (
            'this setVariable [""Towns_RemovedXSmall"",[""Alpha"",""Beta"",""Gamma""]];'
            'this setVariable [""Towns_RemovedSmall"",[""Alpha"",""Gamma""]];'
        )
        sqm = _make_wflogic_group(preset_str)
        result = extract_towns(sqm)
        self.assertIn("XSmall", result["presets"])
        self.assertEqual(result["presets"]["XSmall"], ["Alpha", "Beta", "Gamma"])
        self.assertEqual(result["presets"]["Small"], ["Alpha", "Gamma"])

    def test_no_presets_when_no_wflogic(self):
        sqm = _make_depot_group(0, 0, 0, 'nullReturn = [this,""A"",""++"",1,2,3,""T""] execVM ""x"";')
        result = extract_towns(sqm)
        self.assertEqual(result["presets"], {})


class TestExtractTownsCampsAndDefenses(unittest.TestCase):
    """Test extraction of camps and defense logics from a depot group."""

    _DEPOT_INIT = (
        r'nullReturn = [this,""Kamenka"",""++"",10,45,300,'
        r'[""SmallTown1"",""SmallTown2""]] execVM ""Common\Init\Init_Town.sqf"";'
        r'this enableSimulation false;'
    )

    def _make_sqm(self, camps=None, defenses=None):
        return _make_depot_group(
            1827.0, 8.1, 2260.6, self._DEPOT_INIT,
            camps=camps, defenses=defenses
        )

    def test_no_camps_or_defenses(self):
        result = extract_towns(self._make_sqm())
        town = result["towns"][0]
        self.assertEqual(town["camps"], [])
        self.assertEqual(town["defenses"], [])

    def test_two_camps(self):
        result = extract_towns(self._make_sqm(
            camps=[(1742.0, 2357.0), (1994.0, 2270.0)]
        ))
        town = result["towns"][0]
        self.assertEqual(len(town["camps"]), 2)
        self.assertAlmostEqual(town["camps"][0]["pos"][0], 1742.0, places=0)
        self.assertAlmostEqual(town["camps"][0]["pos"][1], 2357.0, places=0)
        self.assertAlmostEqual(town["camps"][1]["pos"][0], 1994.0, places=0)

    def test_defense_mgnest_kind(self):
        result = extract_towns(self._make_sqm(
            defenses=[{"pos": (1770.0, 2372.0), "kind": ["MGNest"]}]
        ))
        town = result["towns"][0]
        self.assertEqual(len(town["defenses"]), 1)
        self.assertAlmostEqual(town["defenses"][0]["pos"][0], 1770.0, places=0)
        self.assertEqual(town["defenses"][0]["kind"], ["MGNest"])

    def test_multiple_defense_kinds(self):
        result = extract_towns(self._make_sqm(
            defenses=[
                {"pos": (100.0, 200.0), "kind": ["AA", "AT"]},
                {"pos": (300.0, 400.0), "kind": ["MG"]},
            ]
        ))
        town = result["towns"][0]
        self.assertEqual(len(town["defenses"]), 2)
        self.assertIn("AA", town["defenses"][0]["kind"])
        self.assertIn("AT", town["defenses"][0]["kind"])
        self.assertEqual(town["defenses"][1]["kind"], ["MG"])

    def test_camps_and_defenses_together(self):
        result = extract_towns(self._make_sqm(
            camps=[(1742.0, 2357.0), (1994.0, 2270.0)],
            defenses=[{"pos": (1770.0, 2372.0), "kind": ["MGNest"]}],
        ))
        town = result["towns"][0]
        self.assertEqual(len(town["camps"]), 2)
        self.assertEqual(len(town["defenses"]), 1)
        # Depot's own position must not be included in camps/defenses
        self.assertAlmostEqual(town["pos"][0], 1827.0, places=0)

    def test_kamenka_real_counts(self):
        """Sanity check via the real Chernarus mission if available."""
        import os
        sqm_path = (
            r'C:\Users\Steff\a2waspwarfare\Missions'
            r'\[55-2hc]warfarev2_073v48co.chernarus\mission.sqm'
        )
        if not os.path.exists(sqm_path):
            self.skipTest("Real mission.sqm not available")
        text = open(sqm_path, encoding='utf-8', errors='replace').read()
        result = extract_towns(text)
        kamenka = next((t for t in result["towns"] if t["name"] == "Kamenka"), None)
        self.assertIsNotNone(kamenka)
        # Kamenka has exactly 2 camps per mission.sqm inspection
        self.assertEqual(len(kamenka["camps"]), 2)
        # At least 1 defense
        self.assertGreater(len(kamenka["defenses"]), 0)
        # All defenses should have kind list
        for d in kamenka["defenses"]:
            self.assertIsInstance(d["kind"], list)
            self.assertTrue(len(d["kind"]) > 0)


class TestExtractTownsCombined(unittest.TestCase):
    """Test a combined fixture with depot + spawn + airport + WF_Logic."""

    def test_combined(self):
        depot_init = r'nullReturn = [this,""Kamenka"",""++"",10,45,300,[""SmallTown1"",""SmallTown2""]] execVM ""Common\Init\Init_Town.sqf"";this enableSimulation false;'
        spawn_init = r'this setVariable [""wfbe_default"", west]; this setVariable [""wfbe_spawn"", ""north""];'
        preset_str = 'this setVariable [""Towns_RemovedXSmall"",[""Kamenka"",""Pavlovo""]];'

        sqm = (
            _make_depot_group(1827.0, 8.1, 2260.6, depot_init)
            + _make_spawn_group(2448.0, 367.0, 6811.0, spawn_init)
            + _make_airport_group(4824.0, 8.9, 2500.5)
            + _make_wflogic_group(preset_str)
        )
        result = extract_towns(sqm)
        self.assertEqual(len(result["towns"]), 1)
        self.assertEqual(len(result["spawns"]), 1)
        self.assertEqual(len(result["airports"]), 1)
        self.assertIn("XSmall", result["presets"])
        self.assertIn("Kamenka", result["presets"]["XSmall"])

        town = result["towns"][0]
        self.assertEqual(town["name"], "Kamenka")
        self.assertEqual(town["type"], ["SmallTown1", "SmallTown2"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
