#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import {
  decode,
  encode,
  readCfr,
  writeCfr,
  loadCfr,
  summarize,
  diff,
  fidelity,
  setFeatureQuantity,
} from '../src/codec.mjs';
import { generate, specFromCfr } from '../src/generate.mjs';
import { recordSpec, formatRecord } from '../src/spec.mjs';

const USAGE = `econfig - local IBM e-config CFR toolkit

  inspect  <file.cfr>                 systems, products and feature codes
  parse    <file.cfr> [-o out.json]   CFR -> CFRJSON
  build    <file.json> [-o out.cfr]   CFRJSON -> CFR
  gen      <spec.json> [-o out.cfr]   spec + template -> CFR
  spec-of  <file.cfr> [-o spec.json]  turn a configuration into an editable spec
  diff     <a.cfr> <b.cfr>            compare two configurations by feature code
  set      <file.cfr> --code FC --qty N [--product UID] [-o out.cfr]
  roundtrip <file.cfr|dir>            decode/encode fidelity check
  spec     [recordType]               fixed-width record layout
  serve    [--port 4173]              browser UI on 127.0.0.1

Files are read and written as latin1: .cfr column offsets are bytes.`;

function args(argv) {
  const positional = [];
  const flags = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '-o') flags.out = argv[++i];
    else if (a.startsWith('--')) {
      const [k, v] = a.slice(2).split('=');
      flags[k] = v ?? (argv[i + 1]?.startsWith('-') ? true : argv[++i] ?? true);
    } else positional.push(a);
  }
  return { positional, flags };
}

function cmdInspect(file) {
  const s = summarize(loadCfr(file));
  console.log(`${path.basename(file)}`);
  console.log(`  built by   ${s.creating_application}  level ${s.system_level}`);
  console.log(`  created    ${s.created}`);
  console.log(`  locale     ${s.country} / ${s.language}`);
  console.log(`  totals     ${s.systems.length} systems, ${s.productCount} products, ${s.featureCount} features`);
  for (const sys of s.systems) {
    console.log(`\n  [${sys.key}] ${sys.mtm}  ${sys.description}${sys.serial ? `  s/n ${sys.serial}` : ''}`);
    for (const p of s.products.filter((p) => p.uid.startsWith(sys.key))) {
      console.log(`    ${p.mtm.padEnd(10)} x${String(p.quantity).padEnd(3)} ${p.class.padEnd(9)} ${p.description}`);
      for (const f of p.features) {
        console.log(`        ${String(f.code).padEnd(6)} x${String(f.quantity).padEnd(4)} ${f.description}`);
      }
    }
  }
}

function cmdDiff(a, b) {
  const rows = diff(loadCfr(a), loadCfr(b));
  console.log(`- ${path.basename(a)}`);
  console.log(`+ ${path.basename(b)}`);
  if (!rows.length) return console.log('\nidentical feature sets');
  console.log(`\n${rows.length} differing feature codes\n`);
  for (const r of rows) {
    const sign = r.delta > 0 ? '+' : '-';
    console.log(
      `  ${sign} ${r.mtm.padEnd(10)} ${String(r.code).padEnd(6)} ` +
        `${String(r.left).padStart(4)} -> ${String(r.right).padStart(4)}   ${r.description}`,
    );
  }
}

function cmdRoundtrip(target) {
  const files = fs.statSync(target).isDirectory()
    ? fs
        .readdirSync(target)
        .filter((f) => f.toLowerCase().endsWith('.cfr'))
        .map((f) => path.join(target, f))
    : [target];

  console.log('BOM = records 08/19/25/26/38/47/48/49/50/78/96/97 (the bill of materials)\n');

  let intact = 0;
  for (const file of files) {
    let raw, report;
    try {
      raw = readCfr(file);
      report = fidelity(raw, encode(decode(raw)));
    } catch (e) {
      console.log(`FAIL       ${path.basename(file)}  ${e.message}`);
      continue;
    }
    if (report.bomIntact) intact++;
    const notes = Object.entries(report.byType)
      .map(([t, { missing, added }]) => {
        if (missing && !added) return `${t} dropped x${missing}`;
        if (added && !missing) return `${t} added x${added}`;
        return `${t} rewritten x${Math.max(missing, added)}`;
      })
      .sort();
    console.log(
      `${report.bomIntact ? 'BOM OK   ' : 'BOM DIFF '} ${String(report.total).padStart(4)} recs  ` +
        `${notes.join(', ').padEnd(40)} ${path.basename(file)}`,
    );
  }
  console.log(`\n${intact}/${files.length} preserved the bill of materials exactly`);
}

function cmdSet(file, flags) {
  if (!flags.code) throw new Error('--code is required');
  if (flags.qty === undefined) throw new Error('--qty is required');
  const json = loadCfr(file);
  const applied = setFeatureQuantity(json, String(flags.code), Number(flags.qty), flags.product ?? null);
  if (!applied.length) throw new Error(`feature code ${flags.code} not present in ${path.basename(file)}`);
  for (const a of applied) console.log(`  ${a.uid}  ${a.code}  ${a.from} -> ${a.to}`);
  const out = flags.out ?? file.replace(/\.cfr$/i, `.${flags.code}x${flags.qty}.cfr`);
  writeCfr(out, encode(json));
  console.log(`\nwrote ${out}`);
  console.log('NOTE: unvalidated and without the trailer record - reconcile in e-config before use.');
}

const [cmd, ...rest] = process.argv.slice(2);
const { positional, flags } = args(rest);

try {
  switch (cmd) {
    case 'inspect':
      cmdInspect(positional[0]);
      break;
    case 'parse': {
      const json = loadCfr(positional[0]);
      const text = JSON.stringify(json, null, 2);
      if (flags.out) {
        fs.writeFileSync(flags.out, text);
        console.log(`wrote ${flags.out}`);
      } else console.log(text);
      break;
    }
    case 'build': {
      const cfr = encode(JSON.parse(fs.readFileSync(positional[0], 'utf8')));
      const out = flags.out ?? positional[0].replace(/\.json$/i, '.cfr');
      writeCfr(out, cfr);
      console.log(`wrote ${out}  (${cfr.length} bytes)`);
      break;
    }
    case 'gen': {
      const specPath = positional[0];
      const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
      const tpl = flags.template ?? spec.template;
      if (!tpl) throw new Error('spec needs a "template" path (or pass --template)');
      // A template named in the spec is resolved next to the spec itself.
      const tplPath = path.isAbsolute(tpl) ? tpl : path.resolve(path.dirname(specPath), tpl);
      const { cfr, report } = generate(spec, readCfr(tplPath));

      console.log(`template ${path.basename(tplPath)}`);
      for (const p of report.products) {
        console.log(`\n  ${p.mtm}  [${p.mode}]  ${p.uid}`);
        if (!p.applied.length) console.log('    (no change)');
        for (const a of p.applied) {
          const verb = a.from === 0 ? 'add' : a.to === 0 ? 'drop' : 'set';
          console.log(`    ${verb.padEnd(5)} ${a.code.padEnd(10)} ${a.from} -> ${a.to}`);
        }
      }
      for (const w of report.warnings) console.log(`\n  warning: ${w}`);

      const out = flags.out ?? specPath.replace(/\.json$/i, '.cfr');
      writeCfr(out, cfr);
      console.log(`\nwrote ${out}  (${cfr.length} bytes)`);
      console.log('NOTE: unvalidated, no checksum, stale engine-state blob - reconcile in e-config.');
      break;
    }
    case 'spec-of': {
      const text = JSON.stringify(
        specFromCfr(readCfr(positional[0]), { templateName: path.basename(positional[0]) }),
        null,
        2,
      );
      if (flags.out) {
        fs.writeFileSync(flags.out, text);
        console.log(`wrote ${flags.out}`);
      } else console.log(text);
      break;
    }
    case 'diff':
      cmdDiff(positional[0], positional[1]);
      break;
    case 'set':
      cmdSet(positional[0], flags);
      break;
    case 'roundtrip':
      cmdRoundtrip(positional[0]);
      break;
    case 'serve': {
      const { serve } = await import('../src/server.mjs');
      serve({ port: Number(flags.port ?? 4173) });
      break;
    }
    case 'spec': {
      const spec = recordSpec();
      if (positional[0]) {
        const rec = spec[positional[0]];
        if (!rec) throw new Error(`no record type ${positional[0]}`);
        console.log(formatRecord(positional[0], rec));
      } else {
        for (const [code, rec] of Object.entries(spec)) {
          console.log(`${code}  ${String(rec.name ?? '').padEnd(34)} ${(rec.map ?? []).length} fields`);
        }
      }
      break;
    }
    default:
      console.log(USAGE);
      process.exit(cmd ? 1 : 0);
  }
} catch (e) {
  console.error(`error: ${e.message}`);
  process.exit(1);
}
