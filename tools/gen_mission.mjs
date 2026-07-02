#!/usr/bin/env node
/**
 * gen_mission.mjs — headless WASP mission.sqm generator (CLI).
 *
 * Runs the SAME generator code the browser tool uses: it extracts the
 * "MISSION ASSEMBLER + EMITTER" section out of index.html and evaluates it
 * in a Node vm sandbox, so CLI output can never drift from the web tool.
 *
 * Zero dependencies. Node >= 16.
 *
 * Usage:
 *   node tools/gen_mission.mjs --map zargabad --west US --east TKA \
 *        --campaign my-campaign.json --out ./build
 *
 * Options:
 *   --map <key>        map key from assets/data/maps.json (required)
 *   --west <faction>   WEST faction key from factions.json   (default: US)
 *   --east <faction>   EAST faction key from factions.json   (default: TKA)
 *   --campaign <file>  campaign JSON: {towns:[],spawns:[],airports:[],presets:{}}
 *                      (same shape as a seed-towns.json map entry).
 *                      Default: the map's entry in seed-towns.json.
 *   --auto-towns       no campaign/seed? promote the map's CfgWorlds named
 *                      locations to capturable towns with type-based defaults.
 *   --out <dir>        directory to write mission.sqm into (default: cwd)
 *   --stdout           print the SQM to stdout instead of writing a file
 *   --no-validate      skip structural validation (default: validate; any
 *                      structural issue exits 1)
 *   --json             print a JSON summary (folder, counts, issues) to stdout
 */

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, '..');

// ---------- arg parsing ----------
function parseArgs(argv) {
  const args = { west: 'US', east: 'TKA', validate: true, out: process.cwd() };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    switch (a) {
      case '--map':      args.map = argv[++i]; break;
      case '--west':     args.west = argv[++i]; break;
      case '--east':     args.east = argv[++i]; break;
      case '--campaign': args.campaign = argv[++i]; break;
      case '--auto-towns': args.autoTowns = true; break;
      case '--out':      args.out = argv[++i]; break;
      case '--stdout':   args.stdout = true; break;
      case '--no-validate': args.validate = false; break;
      case '--json':     args.json = true; break;
      case '--help': case '-h': args.help = true; break;
      default:
        fail(`Unknown argument: ${a} (use --help)`);
    }
  }
  return args;
}

function fail(msg) { console.error('ERROR: ' + msg); process.exit(1); }

// ---------- load data files ----------
function loadJson(rel) {
  const p = path.join(ROOT, 'assets', 'data', rel);
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

// ---------- extract the generator out of index.html ----------
const START_MARK = 'let _idCounter = 0;';
// Note: single-line marker (index.html may be CRLF). The dangling banner line
// left above the cut is a comment and harmless to the vm evaluation.
const END_MARK = '// GENERATE MISSION: UI + wiring';

export function extractGenerator(indexHtmlText) {
  const start = indexHtmlText.indexOf(START_MARK);
  if (start === -1) throw new Error(`extraction start marker not found: ${START_MARK}`);
  const end = indexHtmlText.indexOf(END_MARK, start);
  if (end === -1) throw new Error('extraction end marker not found (GENERATE MISSION: UI + wiring banner)');
  return indexHtmlText.slice(start, end);
}

export function makeGenerator({ factionsData, missionTemplate }) {
  const indexHtml = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
  const code = extractGenerator(indexHtml);
  const sandbox = {
    factionsData,
    window: { _missionTemplate: missionTemplate },
    console,
  };
  const ctx = vm.createContext(sandbox);
  vm.runInContext(code, ctx, { filename: 'index.html#generator' });
  const api = vm.runInContext(
    '({ buildMissionSqm, buildFolderName, validateSqmStructure })',
    ctx
  );
  return api;
}

// ---------- auto-town promotion (CfgWorlds locations -> towns) ----------
// Defaults are modelled on the Takistan seed campaign's tiers.
const AUTO_TOWN_DEFAULTS = {
  NameCityCapital: { startSV: 20, maxSV: 80, value: 800, type: ['LargeTown1', 'LargeTown2'] },
  NameCity:        { startSV: 10, maxSV: 50, value: 600, type: ['MediumTown1', 'MediumTown2'] },
  NameVillage:     { startSV: 10, maxSV: 40, value: 400, type: ['SmallTown1'] },
  NameLocal:       { startSV: 5,  maxSV: 30, value: 300, type: ['TinyTown1'] },
};

export function autoTownsFromLocations(locations) {
  return locations
    .filter(loc => AUTO_TOWN_DEFAULTS[loc.type])
    .map(loc => {
      const d = AUTO_TOWN_DEFAULTS[loc.type];
      return {
        name: loc.name,
        dubbing: '+',
        startSV: d.startSV,
        maxSV: d.maxSV,
        value: d.value,
        type: d.type.slice(),
        pos: [loc.pos[0], loc.pos[1]],
        camps: [],
        defenses: [],
      };
    });
}

// ---------- main ----------
function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.map) {
    console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8').split('*/')[0] + '*/');
    process.exit(args.help ? 0 : 1);
  }

  const maps = loadJson('maps.json');
  const factionsData = loadJson('factions.json');
  const missionTemplate = loadJson('mission-template.json');
  const seeds = loadJson('seed-towns.json');

  const mapDef = maps[args.map];
  if (!mapDef) fail(`Unknown map "${args.map}". Known: ${Object.keys(maps).join(', ')}`);
  if (!factionsData.factions[args.west]) fail(`Unknown west faction "${args.west}"`);
  if (!factionsData.factions[args.east]) fail(`Unknown east faction "${args.east}"`);

  // Campaign data: --campaign file > seed-towns entry > --auto-towns from CfgWorlds locations
  let data;
  if (args.campaign) {
    data = JSON.parse(fs.readFileSync(args.campaign, 'utf8'));
  } else if (seeds[args.map]) {
    data = seeds[args.map];
  } else if (args.autoTowns) {
    data = {
      towns: autoTownsFromLocations(mapDef.locations || []),
      spawns: [],
      airports: [],
      presets: {},
    };
  } else {
    fail(`No campaign for "${args.map}": pass --campaign <file> or --auto-towns`);
  }
  data.towns    = data.towns    || [];
  data.spawns   = data.spawns   || [];
  data.airports = data.airports || [];
  data.presets  = data.presets  || {};

  const gen = makeGenerator({ factionsData, missionTemplate });

  const sqm = gen.buildMissionSqm({
    world: args.map,
    size: mapDef.size,
    westFaction: args.west,
    eastFaction: args.east,
    data,
  });

  const folder = gen.buildFolderName(args.map, data.towns.length);

  // ---- structural validation (same checks as the browser button) ----
  const report = gen.validateSqmStructure(sqm);
  const issues = [];
  if (!report.uniqueIds) issues.push('DUPLICATE IDs detected');
  if (report.groupsItemsDeclared !== report.groupsItemsActual) {
    issues.push(`Groups items= mismatch: declared ${report.groupsItemsDeclared}, actual ${report.groupsItemsActual}`);
  }
  for (const vc of report.vehiclesCounts) {
    if (vc.declared !== vc.actual) issues.push(`Vehicles items= mismatch: declared ${vc.declared}, actual ${vc.actual}`);
  }
  if (report.addOns4Blocks.length < 4) issues.push(`Expected 4 addOns[] blocks, found ${report.addOns4Blocks.length}`);
  report.addOns4Blocks.forEach((blk, bi) => {
    if (!blk.includes(args.map)) issues.push(`addOns block ${bi + 1} missing world "${args.map}"`);
  });
  const expectedTotalTowns = data.towns.filter(t => !t.airfield).length;
  if (report.totalTowns !== expectedTotalTowns) issues.push(`totalTowns=${report.totalTowns} but ${expectedTotalTowns} non-airfield towns`);
  if (report.depotCount !== data.towns.length) issues.push(`Depot count ${report.depotCount} != town count ${data.towns.length}`);

  // ---- output ----
  if (args.stdout) {
    process.stdout.write(sqm);
  } else {
    fs.mkdirSync(args.out, { recursive: true });
    const outFile = path.join(args.out, 'mission.sqm');
    fs.writeFileSync(outFile, sqm, 'utf8');
    if (!args.json) console.error(`wrote ${outFile}`);
  }

  const summary = {
    map: args.map,
    size: mapDef.size,
    west: args.west,
    east: args.east,
    folder,
    towns: data.towns.length,
    spawns: data.spawns.length,
    airports: data.airports.length,
    entities: report.allIds.length,
    uniqueIds: report.uniqueIds,
    issues,
  };
  if (args.json) {
    console.log(JSON.stringify(summary, null, 2));
  } else {
    console.error(`folder: ${folder}`);
    console.error(`towns=${summary.towns} spawns=${summary.spawns} airports=${summary.airports} entities=${summary.entities}`);
    if (issues.length) console.error('ISSUES:\n  ' + issues.join('\n  '));
  }

  if (args.validate && issues.length > 0) process.exit(1);
}

const isCliInvocation = process.argv[1] &&
  path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isCliInvocation) main();
