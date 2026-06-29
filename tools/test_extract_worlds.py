#!/usr/bin/env python3
"""
test_extract_worlds.py — Unit tests for extract_worlds.py (stdlib unittest, no deps)

Run: python tools/test_extract_worlds.py
"""

import sys
import unittest
from pathlib import Path

# Allow importing from the same tools/ directory
sys.path.insert(0, str(Path(__file__).parent))

from extract_worlds import (
    _extract_size,
    _extract_locations,
    _find_world_spans,
    parse_cfg_worlds,
    HARDCODE_SIZES,
)


# ---------------------------------------------------------------------------
# Inline fixtures
# ---------------------------------------------------------------------------

FIXTURE_GRID_NEGATIVE_STEP = """
    class Grid : Grid
    {
        offsetX = 0;
        offsetY = 12800;
        class Zoom1
        {
            zoomMax = 0.15;
            format = "XY";
            stepX = 100;
            stepY = -100;
        };
    };
"""

FIXTURE_GRID_POSITIVE_STEP = """
    class Grid : Grid
    {
        offsetX = 0;
        offsetY = 0;
        class Zoom1
        {
            zoomMax = 0.15;
            format = "XY";
            stepX = 100;
            stepY = 100;
        };
    };
"""

FIXTURE_NAMES_BLOCK = """
    class Names
    {
        class city_Chernogorsk
        {
            name = "Chernogorsk";
            position[] = {
                6731.21,
                2554.13
            };
            type = "NameCityCapital";
            radiusA = 300;
            radiusB = 300;
            angle = 0;
        };
        class vill_Stary
        {
            name = "Stary Sobor";
            position[] = {
                6169.01,
                7793.67
            };
            type = "NameCity";
            radiusA = 100;
            radiusB = 100;
            angle = 0;
        };
        class flat_area
        {
            name = "";
            position[] = {
                100.0,
                200.0
            };
            type = "FlatArea";
            radiusA = 50;
            radiusB = 50;
            angle = 0;
        };
    };
"""

FIXTURE_EMPTY_NAMES = """
    class Names
    {
    };
"""

FIXTURE_FULL_WORLD_TAKISTAN = """
class FakeWorld : CAWorld
{
    worldName = "\\ca\\takistan\\takistan.wrp";
    class Grid : Grid
    {
        offsetX = 0;
        offsetY = 12800;
        class Zoom1
        {
            stepX = 100;
            stepY = -100;
        };
    };
    class Names
    {
        class city_Capital
        {
            name = "Takmyr";
            position[] = {
                5000.0,
                8000.0
            };
            type = "NameCityCapital";
            radiusA = 200;
            radiusB = 200;
            angle = 0;
        };
        class vill_One
        {
            name = "Al Rayak";
            position[] = {
                3000.0,
                4000.0
            };
            type = "NameVillage";
            radiusA = 100;
            radiusB = 100;
            angle = 0;
        };
    };
};
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGridSizeExtraction(unittest.TestCase):
    """Grid offsetY → size."""

    def test_negative_step_returns_offsetY(self):
        """When stepY is negative, offsetY IS the terrain size."""
        size = _extract_size("takistan", FIXTURE_GRID_NEGATIVE_STEP)
        self.assertEqual(size, 12800)

    def test_positive_step_offsetY_zero(self):
        """Chernarus/utes have offsetY=0 + positive stepY → we DON'T hardcode in _extract_size
        (the HARDCODE check happens in _extract_size first)."""
        # Without the hardcode key, offsetY=0 is returned as-is
        size = _extract_size("someworldnotinhardcode", FIXTURE_GRID_POSITIVE_STEP)
        self.assertEqual(size, 0)

    def test_chernarus_hardcode_overrides(self):
        """Chernarus key → hardcoded 15360 regardless of Grid content."""
        size = _extract_size("chernarus", FIXTURE_GRID_POSITIVE_STEP)
        self.assertEqual(size, 15360)

    def test_utes_hardcode_overrides(self):
        """Utes key → hardcoded 5120."""
        size = _extract_size("utes", FIXTURE_GRID_POSITIVE_STEP)
        self.assertEqual(size, 5120)

    def test_all_hardcodes_present(self):
        """Both hardcoded worlds are in HARDCODE_SIZES."""
        self.assertIn("chernarus", HARDCODE_SIZES)
        self.assertIn("utes", HARDCODE_SIZES)
        self.assertEqual(HARDCODE_SIZES["chernarus"], 15360)
        self.assertEqual(HARDCODE_SIZES["utes"], 5120)

    def test_zargabad_size_8192(self):
        body = """
        class Grid : Grid
        {
            offsetX = 0;
            offsetY = 8192;
            class Zoom1 { stepY = -100; };
        };
        """
        self.assertEqual(_extract_size("zargabad", body), 8192)


class TestNamesExtraction(unittest.TestCase):
    """Names block → locations list."""

    def test_names_count(self):
        locs = _extract_locations(FIXTURE_NAMES_BLOCK)
        self.assertEqual(len(locs), 3)

    def test_first_location_name_and_type(self):
        locs = _extract_locations(FIXTURE_NAMES_BLOCK)
        chernogorsk = next(l for l in locs if "Chernogorsk" in l["name"])
        self.assertEqual(chernogorsk["type"], "NameCityCapital")

    def test_position_values(self):
        locs = _extract_locations(FIXTURE_NAMES_BLOCK)
        chernogorsk = next(l for l in locs if "Chernogorsk" in l["name"])
        self.assertAlmostEqual(chernogorsk["pos"][0], 6731.21, places=1)
        self.assertAlmostEqual(chernogorsk["pos"][1], 2554.13, places=1)

    def test_empty_names_block_returns_empty_list(self):
        locs = _extract_locations(FIXTURE_EMPTY_NAMES)
        self.assertEqual(locs, [])

    def test_empty_name_string_included(self):
        """Entries with name="" should still be included (FlatArea etc.)."""
        locs = _extract_locations(FIXTURE_NAMES_BLOCK)
        flat = next((l for l in locs if l["type"] == "FlatArea"), None)
        self.assertIsNotNone(flat)
        self.assertEqual(flat["name"], "")

    def test_no_names_block_returns_empty(self):
        locs = _extract_locations("class Grid : Grid { offsetY = 1000; };")
        self.assertEqual(locs, [])


class TestWorldSpanExtraction(unittest.TestCase):
    """_find_world_spans correctly isolates world bodies."""

    def test_full_world_fixture_found(self):
        spans = _find_world_spans(FIXTURE_FULL_WORLD_TAKISTAN.replace("FakeWorld", "Takistan"))
        self.assertIn("Takistan", spans)

    def test_body_contains_worldname(self):
        text = FIXTURE_FULL_WORLD_TAKISTAN.replace("FakeWorld", "Takistan")
        spans = _find_world_spans(text)
        self.assertIn("takistan.wrp", spans["Takistan"])


class TestParseCfgWorldsIntegration(unittest.TestCase):
    """parse_cfg_worlds on a synthetic multi-world snippet."""

    MULTI_FIXTURE = """
class CfgWorlds
{
    class utes : CAWorld
    {
        worldName = "\\ca\\utes\\utes.wrp";
        class Grid : Grid
        {
            offsetX = 0;
            offsetY = 0;
            class Zoom1 { stepX = 100; stepY = 100; };
        };
        class Names
        {
            class vill_Test
            {
                name = "TestVillage";
                position[] = { 1000.0, 2000.0 };
                type = "NameVillage";
                radiusA = 100;
                radiusB = 100;
                angle = 0;
            };
        };
    };
    class Takistan : CAWorld
    {
        worldName = "\\ca\\takistan\\takistan.wrp";
        class Grid : Grid
        {
            offsetX = 0;
            offsetY = 12800;
            class Zoom1 { stepX = 100; stepY = -100; };
        };
        class Names
        {
        };
    };
}
"""

    def setUp(self):
        self.maps = parse_cfg_worlds(self.MULTI_FIXTURE)

    def test_utes_uses_hardcode_size(self):
        self.assertIn("utes", self.maps)
        self.assertEqual(self.maps["utes"]["size"], 5120)

    def test_takistan_uses_offsetY(self):
        self.assertIn("takistan", self.maps)
        self.assertEqual(self.maps["takistan"]["size"], 12800)

    def test_utes_has_locations(self):
        self.assertEqual(len(self.maps["utes"]["locations"]), 1)
        self.assertEqual(self.maps["utes"]["locations"][0]["name"], "TestVillage")
        self.assertEqual(self.maps["utes"]["locations"][0]["type"], "NameVillage")

    def test_takistan_has_empty_locations(self):
        self.assertEqual(self.maps["takistan"]["locations"], [])

    def test_world_key_is_lowercase(self):
        """World keys must be lowercased class names."""
        for key in self.maps:
            self.assertEqual(key, key.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
