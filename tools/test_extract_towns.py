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

def _make_depot_group(pos_x, pos_alt, pos_y, init_str):
    """Build a minimal group block containing one LocationLogicDepot."""
    return f"""
        class ItemN {{
            side="LOGIC";
            class Vehicles {{
                items=1;
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
                }};
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
