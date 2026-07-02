#!/usr/bin/env node
/**
 * test_gen_mission.mjs — regression tests for the headless CLI generator.
 * Run: node tools/test_gen_mission.mjs
 */

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { extractGenerator, makeGenerator, autoTownsFromLocations } from './gen_mission.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');
const CLI = path.join(__dirname, 'gen_mission.mjs');

let passed = 0, failed = 0;
function assert(cond, label) {
  if (cond) { passed++; console.log('  ok  ' + label); }
  else { failed++; console.error('  FAIL ' + label); }
}

function loadJson(rel) {
  return JSON.parse(fs.readFileSync(path.join(ROOT, 'assets', 'data', rel), 'utf8'));
}

const maps = loadJson('maps.json');
const factionsData = loadJson('factions.json');
const missionTemplate = loadJson('mission-template.json');
const seeds = loadJson('seed-towns.json');

// ---------- 1. extraction ----------
console.log('extraction:');
const indexHtml = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const code = extractGenerator(indexHtml);
assert(code.includes('function buildMissionSqm'), 'extracted code contains buildMissionSqm');
assert(code.includes('function validateSqmStructure'), 'extracted code contains validateSqmStructure');
assert(code.includes('function buildFolderName'), 'extracted code contains buildFolderName');
assert(!code.includes('addEventListener'), 'extracted code has no DOM wiring');

// ---------- 2. library generation for every seeded map ----------
const gen = makeGenerator({ factionsData, missionTemplate });
for (const mapKey of Object.keys(seeds)) {
  console.log(`library generation: ${mapKey}`);
  const data = seeds[mapKey];
  const sqm = gen.buildMissionSqm({
    world: mapKey, size: maps[mapKey].size,
    westFaction: 'US', eastFaction: 'TKA', data,
  });
  const rep = gen.validateSqmStructure(sqm);
  assert(rep.uniqueIds, 'all entity IDs unique');
  assert(rep.groupsItemsDeclared === rep.groupsItemsActual,
    `Groups items= matches actual (${rep.groupsItemsDeclared})`);
  assert(rep.depotCount === data.towns.length,
    `depot count == towns (${data.towns.length})`);
  assert(rep.totalTowns === data.towns.length, 'WF_Logic totalTowns matches');
  assert(rep.vehiclesCounts.every(vc => vc.declared === vc.actual), 'all Vehicles items= match');
  assert(rep.ownerWestSync.length > 0 && rep.ownerEastSync.length > 0, 'owner logics synced to slots');
  assert(sqm.includes('name="DEADSPAWNS"') && sqm.includes('name="DEADSPAWNS_1"'),
    'DEADSPAWNS markers present');
  assert(sqm.includes('name="WestTempRespawnMarker"') && sqm.includes('name="EastTempRespawnMarker"'),
    'temp respawn markers present');
}

// ---------- 3. marker scaling: markers land near top-right corner of target map ----------
console.log('marker scaling (zargabad 8192):');
{
  const data = { towns: [], spawns: [], airports: [], presets: {} };
  const sqm = gen.buildMissionSqm({
    world: 'zargabad', size: maps.zargabad.size,
    westFaction: 'US', eastFaction: 'TKA', data,
  });
  const m = sqm.match(/position\[\]=\{([\d.]+),[\d.]+,([\d.]+)\};\n\t\t\tname="DEADSPAWNS"/);
  assert(!!m, 'DEADSPAWNS marker has position');
  if (m) {
    const [x, y] = [parseFloat(m[1]), parseFloat(m[2])];
    const k = 8192 / 15360;
    assert(Math.abs(x - 15440.639 * k) < 0.5, `DEADSPAWNS x scaled (${x.toFixed(1)})`);
    assert(Math.abs(y - 15237.345 * k) < 0.5, `DEADSPAWNS y scaled (${y.toFixed(1)})`);
  }
}

// ---------- 4. auto-towns promotion ----------
console.log('auto-towns:');
{
  const towns = autoTownsFromLocations(maps.zargabad.locations);
  assert(towns.length > 0, `zargabad locations promoted (${towns.length})`);
  assert(towns.every(t => t.type.length > 0 && t.maxSV > 0 && t.pos.length === 2),
    'promoted towns have type/maxSV/pos');
  const cap = towns.find(t => t.name === 'Zargabad');
  assert(cap && cap.type.includes('LargeTown1'), 'capital promoted to LargeTown tier');
}

// ---------- 5. CLI end-to-end ----------
console.log('CLI end-to-end:');
{
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'genmission-'));
  const out = execFileSync(process.execPath,
    [CLI, '--map', 'chernarus', '--west', 'US', '--east', 'RU', '--out', tmp, '--json'],
    { encoding: 'utf8' });
  const summary = JSON.parse(out);
  assert(summary.issues.length === 0, 'chernarus seed generation has no structural issues');
  assert(summary.towns === seeds.chernarus.towns.length, `CLI used chernarus seeds (${summary.towns} towns)`);
  const sqmPath = path.join(tmp, 'mission.sqm');
  assert(fs.existsSync(sqmPath), 'mission.sqm written');
  const sqmTxt = fs.readFileSync(sqmPath, 'utf8');
  assert(sqmTxt.startsWith('version=11;'), 'sqm starts with version=11;');
  assert(/class Mission[\s\S]*class Intro[\s\S]*class OutroWin[\s\S]*class OutroLoose/.test(sqmTxt),
    'all four top-level blocks present');
  fs.rmSync(tmp, { recursive: true, force: true });
}

// ---------- 6. CLI with a campaign file ----------
console.log('CLI with campaign file:');
{
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'genmission-'));
  const campaign = {
    towns: [
      { name: 'Alpha', dubbing: '+', startSV: 10, maxSV: 40, value: 400,
        type: ['SmallTown1'], pos: [1000, 1000],
        camps: [{ pos: [1100, 1050] }],
        defenses: [{ pos: [950, 980], kind: ['MGNest'] }] },
      { name: 'Bravo', dubbing: '+', startSV: 20, maxSV: 80, value: 800,
        type: ['LargeTown1', 'LargeTown2'], pos: [4000, 4000], camps: [], defenses: [] },
    ],
    spawns: [
      { pos: [500, 500], side: 'west', spawn_pos: 'south' },
      { pos: [7500, 7500], side: 'east', spawn_pos: 'north' },
      { pos: [4000, 2000], side: null, spawn_pos: null },
    ],
    airports: [{ pos: [3300, 4100] }],
    presets: {},
  };
  const campFile = path.join(tmp, 'campaign.json');
  fs.writeFileSync(campFile, JSON.stringify(campaign));
  const out = execFileSync(process.execPath,
    [CLI, '--map', 'zargabad', '--campaign', campFile, '--out', tmp, '--json'],
    { encoding: 'utf8' });
  const summary = JSON.parse(out);
  assert(summary.issues.length === 0, 'campaign generation has no structural issues');
  assert(summary.folder === '[2-2hc]warfarev2_073v48co.zargabad', `folder name (${summary.folder})`);
  const sqmTxt = fs.readFileSync(path.join(tmp, 'mission.sqm'), 'utf8');
  assert(sqmTxt.includes('LocationLogicAirport'), 'airport logic emitted');
  assert(sqmTxt.includes('wfbe_spawn'), 'sided spawn init emitted');
  assert(sqmTxt.includes('wfbe_defense_kind'), 'defense logic emitted');
  assert((sqmTxt.match(/LocationLogicCamp/g) || []).length === 1, 'camp emitted once');
  fs.rmSync(tmp, { recursive: true, force: true });
}

// ---------- 7. auto-towns CLI path for a map with no seeds ----------
console.log('CLI --auto-towns (zargabad):');
{
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'genmission-'));
  const out = execFileSync(process.execPath,
    [CLI, '--map', 'zargabad', '--auto-towns', '--out', tmp, '--json'],
    { encoding: 'utf8' });
  const summary = JSON.parse(out);
  assert(summary.issues.length === 0, 'auto-towns generation has no structural issues');
  assert(summary.towns > 0, `auto-towns promoted ${summary.towns} towns`);
  fs.rmSync(tmp, { recursive: true, force: true });
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed ? 1 : 0);
