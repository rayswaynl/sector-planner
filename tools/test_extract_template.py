"""
test_extract_template.py — Unit tests for extract_template.py.

All fixtures are inline strings — no filesystem dependencies.
Run with:
    cd tools && python -m unittest test_extract_template -v
"""

import unittest
from extract_template import (
    extract_template,
    count_items,
    _classify_group,
    _split_addons,
    _strip_town_vars,
    _parse_markers,
    _mean_pos,
    _sub3,
)


# ---------------------------------------------------------------------------
# Fixtures — minimal valid .sqm fragments
# ---------------------------------------------------------------------------

# A player slot group (WEST side, FR_TL vehicle)
SLOT_GROUP_FIXTURE = """
    side="WEST";
    class Vehicles
    {
        items=1;
        class Item0
        {
            position[]={2260.5251,512.80225,15297.613};
            id=231;
            side="WEST";
            vehicle="FR_TL";
            player="PLAY CDG";
            leader=1;
            rank="LIEUTENANT";
            skill=0.60000002;
            init="removeAllWeapons this";
            description="Support (Supply run)";
            synchronizations[]={255};
        };
    };
"""

# A depot (town) group — should be classified as None (dropped)
DEPOT_GROUP_FIXTURE = """
    side="LOGIC";
    class Vehicles
    {
        items=5;
        class Item0
        {
            position[]={1827.0815,8.1068478,2260.6648};
            id=4;
            side="LOGIC";
            vehicle="LocationLogicDepot";
            leader=1;
            skill=0.60000002;
            text="Kamenka";
            init="nullReturn = [this,""Kamenka"",""++"",10,45,300,[""SmallTown1""]] execVM ""Common\\Init\\Init_Town.sqf"";this enableSimulation false;";
            synchronizations[]={5,6,19,18};
        };
        class Item1
        {
            position[]={1742.8921,18.179842,2357.0332};
            id=6;
            side="LOGIC";
            vehicle="LocationLogicCamp";
            skill=0.60000002;
            init="this enableSimulation false;";
            synchronizations[]={4};
        };
    };
"""

# Owner logic group (West)
OWNER_WEST_FIXTURE = """
    side="LOGIC";
    class Vehicles
    {
        items=1;
        class Item0
        {
            position[]={2263.1191,514.90869,15309.809};
            id=255;
            side="LOGIC";
            vehicle="LocationLogicOwnerWest";
            leader=1;
            skill=0.60000002;
            text="WFBE_L_BLU";
            synchronizations[]={229,230,231,232,233};
        };
    };
"""

# LocationLogicStart group — should be dropped
START_GROUP_FIXTURE = """
    side="LOGIC";
    class Vehicles
    {
        items=1;
        class Item0
        {
            position[]={10203.106,61.453606,4053.7334};
            id=0;
            side="LOGIC";
            vehicle="LocationLogicStart";
            leader=1;
            skill=0.60000002;
        };
    };
"""

# WF_Logic group
WF_LOGIC_FIXTURE = """
    side="LOGIC";
    class Vehicles
    {
        items=1;
        class Item0
        {
            position[]={1916.9998,0.12864132,54.746704};
            id=228;
            side="LOGIC";
            vehicle="Logic";
            leader=1;
            skill=0.60000002;
            text="WF_Logic";
            init="this setVariable [""totalTowns"",43];this enableSimulation false;   this setVariable [""Towns_RemovedXSmall"",["" Zelenogorsk""]];   nullReturn = [this] ExecVM ""Common\\Init\\Init_TownMode.sqf"" ";
        };
    };
"""

# Utility (RCoin) group
RCOIN_GROUP_FIXTURE = """
    side="LOGIC";
    class Vehicles
    {
        items=1;
        class Item0
        {
            position[]={1946.9515,0.073881432,54.891724};
            id=1;
            side="LOGIC";
            vehicle="Logic";
            leader=1;
            skill=0.60000002;
            text="RCoin";
            init="this enableSimulation false;";
        };
    };
"""

# CIV slot (headless client)
CIV_SLOT_FIXTURE = """
    side="CIV";
    class Vehicles
    {
        items=1;
        class Item0
        {
            position[]={1927.2078,544.75983,15282.436};
            id=268;
            side="CIV";
            vehicle="Functionary1";
            player="PLAY CDG";
            forceHeadlessClient=1;
            leader=1;
            skill=0.60000002;
            init="this allowdamage false;";
            description="Headless Client";
        };
    };
"""

# Minimal full mission.sqm for extract_template()
MINIMAL_SQM = """version=11;
class Mission
{
    addOns[]=
    {
        "cacharacters2",
        "chernarus",
        "ca_modules_functions",
        "warfare2vehicles"
    };
    addOnsAuto[]=
    {
        "ca_modules_functions",
        "cacharacters2",
        "chernarus"
    };
    randomSeed=10034581;
    class Intel
    {
        briefingName="Test Mission";
        year=2016;
        month=12;
        day=28;
        hour=8;
        minute=0;
    };
    class Groups
    {
        items=6;
        class Item0
        {
            side="LOGIC";
            class Vehicles
            {
                items=1;
                class Item0
                {
                    position[]={10203.106,61.453606,4053.7334};
                    id=0;
                    side="LOGIC";
                    vehicle="LocationLogicStart";
                    leader=1;
                    skill=0.60000002;
                };
            };
        };
        class Item1
        {
            side="LOGIC";
            class Vehicles
            {
                items=1;
                class Item0
                {
                    position[]={1946.9515,0.073881432,54.891724};
                    id=1;
                    side="LOGIC";
                    vehicle="Logic";
                    leader=1;
                    skill=0.60000002;
                    text="RCoin";
                    init="this enableSimulation false;";
                };
            };
        };
        class Item2
        {
            side="LOGIC";
            class Vehicles
            {
                items=5;
                class Item0
                {
                    position[]={1827.0815,8.1068478,2260.6648};
                    id=4;
                    side="LOGIC";
                    vehicle="LocationLogicDepot";
                    leader=1;
                    skill=0.60000002;
                    text="Kamenka";
                    init="nullReturn = [this,""Kamenka"",""++"",10,45,300,[""SmallTown1""]] execVM ""Common\\Init\\Init_Town.sqf"";this enableSimulation false;";
                    synchronizations[]={5,6,19,18};
                };
                class Item1
                {
                    position[]={1742.8921,18.179842,2357.0332};
                    id=6;
                    side="LOGIC";
                    vehicle="LocationLogicCamp";
                    skill=0.60000002;
                    init="this enableSimulation false;";
                    synchronizations[]={4};
                };
            };
        };
        class Item3
        {
            side="WEST";
            class Vehicles
            {
                items=1;
                class Item0
                {
                    position[]={100.0,500.0,200.0};
                    id=10;
                    side="WEST";
                    vehicle="FR_TL";
                    player="PLAY CDG";
                    leader=1;
                    rank="LIEUTENANT";
                    skill=0.60000002;
                    init="removeAllWeapons this";
                    description="Support";
                    synchronizations[]={50};
                };
            };
        };
        class Item4
        {
            side="LOGIC";
            class Vehicles
            {
                items=1;
                class Item0
                {
                    position[]={100.0,500.0,200.0};
                    id=50;
                    side="LOGIC";
                    vehicle="LocationLogicOwnerWest";
                    leader=1;
                    skill=0.60000002;
                    text="WFBE_L_BLU";
                    synchronizations[]={10};
                };
            };
        };
        class Item5
        {
            side="LOGIC";
            class Vehicles
            {
                items=1;
                class Item0
                {
                    position[]={200.0,0.0,100.0};
                    id=99;
                    side="LOGIC";
                    vehicle="Logic";
                    leader=1;
                    skill=0.60000002;
                    text="WF_Logic";
                    init="this setVariable [""totalTowns"",1];this enableSimulation false;this setVariable [""Towns_RemovedXSmall"",[]]; nullReturn = [this] ExecVM ""Common\\Init\\Init_TownMode.sqf"" ";
                };
            };
        };
    };
    class Markers
    {
        items=2;
        class Item0
        {
            position[]={15491.06,276.31659,15198.396};
            name="WestTempRespawnMarker";
            type="Empty";
        };
        class Item1
        {
            position[]={15404.811,268.35049,15293.424};
            name="EastTempRespawnMarker";
            type="Empty";
        };
    };
};
class Intro
{
    addOns[]={"chernarus"};
    addOnsAuto[]={"chernarus"};
    randomSeed=13267190;
    class Intel
    {
        startWeather=0.25;
        year=2008;
    };
};
class OutroWin
{
    addOns[]={"chernarus"};
    addOnsAuto[]={"chernarus"};
    randomSeed=10462969;
    class Intel {};
};
class OutroLoose
{
    addOns[]={"chernarus"};
    addOnsAuto[]={"chernarus"};
    randomSeed=12603217;
    class Intel {};
};
"""

# Small Groups block for count_items helper test
ITEMS_BLOCK = """
    class Item0
    {
        position[]={1,2,3};
        id=0;
        vehicle="Logic";
    };
    class Item1
    {
        position[]={4,5,6};
        id=1;
        vehicle="Logic";
    };
"""


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestCountItems(unittest.TestCase):
    def test_two_items(self):
        self.assertEqual(count_items(ITEMS_BLOCK), 2)

    def test_zero_items(self):
        self.assertEqual(count_items("no items here"), 0)

    def test_nested_items_not_counted_twice(self):
        # A group containing an inner ItemN should count as 1, not 2
        block = """
        class Item0
        {
            class Vehicles
            {
                items=1;
                class Item0
                {
                    id=0;
                };
            };
        };
        """
        # count_items counts at the TOP level of *block*, which has 1 Item
        self.assertEqual(count_items(block), 1)

    def test_wrapped_groups(self):
        wrapped = "class Groups\n{\n    items=2;\n" + ITEMS_BLOCK + "\n};\n"
        # count_items on the Groups body (sans wrapper) should give 2
        import re
        m = re.search(r'\{', wrapped)
        from extract_template import _find_class_block
        bs, be = _find_class_block(wrapped, m.start())
        inner = wrapped[bs:be]
        self.assertEqual(count_items(inner), 2)


class TestClassifyGroup(unittest.TestCase):
    def test_slot_classified(self):
        result = _classify_group(SLOT_GROUP_FIXTURE)
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "slot")
        self.assertEqual(result["side"], "WEST")
        self.assertEqual(result["vehicleClass"], "FR_TL")
        self.assertEqual(result["rank"], "LIEUTENANT")
        self.assertIsNotNone(result["position"])
        self.assertAlmostEqual(result["position"][0], 2260.5251, places=2)

    def test_depot_group_dropped(self):
        result = _classify_group(DEPOT_GROUP_FIXTURE)
        self.assertIsNone(result, "Town/depot group must be dropped (classified as None)")

    def test_start_group_dropped(self):
        result = _classify_group(START_GROUP_FIXTURE)
        self.assertIsNone(result, "LocationLogicStart group must be dropped")

    def test_owner_classified(self):
        result = _classify_group(OWNER_WEST_FIXTURE)
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "owner")
        self.assertEqual(result["side"], "WEST")
        self.assertEqual(result["text"], "WFBE_L_BLU")
        self.assertEqual(result["synchronizations"], [229, 230, 231, 232, 233])

    def test_wf_logic_classified(self):
        result = _classify_group(WF_LOGIC_FIXTURE)
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "wf_logic")
        # init_tail should NOT contain totalTowns or Towns_Removed*
        tail = result["init_tail"]
        self.assertNotIn("totalTowns", tail)
        self.assertNotIn("Towns_Removed", tail)
        # Should retain the ExecVM tail
        self.assertIn("ExecVM", tail)

    def test_utility_rcoin(self):
        result = _classify_group(RCOIN_GROUP_FIXTURE)
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "utility")
        self.assertEqual(result["text"], "RCoin")

    def test_civ_slot_classified(self):
        result = _classify_group(CIV_SLOT_FIXTURE)
        self.assertIsNotNone(result)
        self.assertEqual(result["kind"], "slot")
        self.assertEqual(result["side"], "CIV")
        self.assertTrue(result["forceHeadlessClient"])


class TestAddOnSplit(unittest.TestCase):
    def test_world_identified(self):
        split = _split_addons(["cacharacters2", "chernarus", "ca_modules_functions", "warfare2vehicles"])
        self.assertEqual(split["world"], ["chernarus"])
        self.assertIn("ca_modules_functions", split["base"])
        self.assertIn("warfare2vehicles", split["base"])
        self.assertIn("cacharacters2", split["faction"])

    def test_empty(self):
        split = _split_addons([])
        self.assertEqual(split["world"], [])
        self.assertEqual(split["base"], [])
        self.assertEqual(split["faction"], [])


class TestStripTownVars(unittest.TestCase):
    def test_strips_total_towns(self):
        init = 'this setVariable ["totalTowns",43];this enableSimulation false;'
        result = _strip_town_vars(init)
        self.assertNotIn("totalTowns", result)
        self.assertIn("enableSimulation", result)

    def test_strips_towns_removed(self):
        init = 'this setVariable ["Towns_RemovedXSmall",["Kamenka"]]; nullReturn = [this] ExecVM "Init_TownMode.sqf"'
        result = _strip_town_vars(init)
        self.assertNotIn("Towns_RemovedXSmall", result)
        self.assertIn("ExecVM", result)


class TestStagingClusters(unittest.TestCase):
    def test_mean_pos(self):
        positions = [[0.0, 0.0, 0.0], [2.0, 0.0, 4.0]]
        result = _mean_pos(positions)
        self.assertAlmostEqual(result[0], 1.0)
        self.assertAlmostEqual(result[2], 2.0)

    def test_offset(self):
        slot_pos = [100.0, 500.0, 200.0]
        anchor = [99.0, 500.0, 199.0]
        offset = _sub3(slot_pos, anchor)
        self.assertAlmostEqual(offset[0], 1.0)
        self.assertAlmostEqual(offset[2], 1.0)


class TestExtractTemplateMinimal(unittest.TestCase):
    def setUp(self):
        self.template = extract_template(MINIMAL_SQM)

    def test_version(self):
        self.assertEqual(self.template["header"]["version"], 11)

    def test_addons_split(self):
        ao = self.template["header"]["addOns"]
        self.assertIn("chernarus", ao["world"])
        self.assertIn("ca_modules_functions", ao["base"])
        self.assertIn("cacharacters2", ao["faction"])

    def test_slot_captured(self):
        west = self.template["slots"]["west"]
        self.assertEqual(len(west), 1)
        slot = west[0]
        self.assertEqual(slot["vehicleClass"], "FR_TL")
        self.assertEqual(slot["id"], 10)
        # Offset should be [0,0,0] when only one slot (anchor == position)
        self.assertIn("offset", slot)

    def test_owner_captured(self):
        owners = self.template["owners"]
        self.assertIn("west", owners)
        self.assertEqual(owners["west"]["text"], "WFBE_L_BLU")
        self.assertEqual(owners["west"]["synchronizations"], [10])

    def test_depot_dropped(self):
        # No slot, owner, wfLogic, or utility should reference a depot vehicle
        for side, slots in self.template["slots"].items():
            for s in slots:
                self.assertNotIn("LocationLogicDepot", s.get("vehicleClass", ""))

    def test_start_dropped(self):
        # LocationLogicStart should not appear in any utility/wfLogic
        for u in self.template["utility"]:
            self.assertNotEqual(u["vehicle"], "LocationLogicStart")

    def test_wf_logic_captured(self):
        wfl = self.template["wfLogic"]
        self.assertIsNotNone(wfl)
        self.assertEqual(wfl["id"], 99)
        self.assertNotIn("totalTowns", wfl["init_tail"])
        self.assertIn("ExecVM", wfl["init_tail"])

    def test_utility_rcoin(self):
        texts = [u["text"] for u in self.template["utility"]]
        self.assertIn("RCoin", texts)

    def test_markers_captured(self):
        markers = self.template["markers"]
        self.assertEqual(len(markers), 2)
        names = {mk["name"] for mk in markers}
        self.assertIn("WestTempRespawnMarker", names)
        self.assertIn("EastTempRespawnMarker", names)

    def test_staging_cluster_west(self):
        clusters = self.template["stagingClusters"]
        self.assertIn("west", clusters)
        anchor = clusters["west"]["anchor"]
        self.assertEqual(len(anchor), 3)
        # One slot at [100,500,200] → anchor = [100,500,200]
        self.assertAlmostEqual(anchor[0], 100.0, places=1)

    def test_intro_parsed(self):
        intro = self.template["header"]["intro"]
        self.assertEqual(intro["randomSeed"], 13267190)
        self.assertIn("chernarus", intro["addOns"]["world"])

    def test_random_seed(self):
        self.assertEqual(self.template["header"]["randomSeed"], 10034581)

    def test_intel_fields(self):
        intel = self.template["header"]["intel"]
        self.assertEqual(intel.get("briefingName"), "Test Mission")
        self.assertEqual(intel.get("hour"), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
