#!/usr/bin/env node
// Downloads the e-config Cloud application bundle into vendor/.
// The bundle is IBM's code: it is fetched on demand and never committed.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const VENDOR = path.join(ROOT, 'vendor');
const BUNDLE_URL = 'https://www.ibm.com/services/econfigcloud/main.js';
const UA =
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36';

const target = path.join(VENDOR, 'main.js');

fs.mkdirSync(VENDOR, { recursive: true });

const res = await fetch(BUNDLE_URL, { headers: { 'User-Agent': UA } });
if (!res.ok) {
  console.error(`failed to fetch bundle: HTTP ${res.status}`);
  process.exit(1);
}
const body = await res.text();
fs.writeFileSync(target, body, 'utf8');

const version = body.match(/version:"(\d+\.\d+\.\d+)"/)?.[1] ?? 'unknown';
fs.writeFileSync(
  path.join(VENDOR, 'BUNDLE_INFO.json'),
  JSON.stringify(
    { url: BUNDLE_URL, fetched_at: new Date().toISOString(), bytes: body.length, app_version: version },
    null,
    2,
  ),
);

console.log(`saved ${target}`);
console.log(`  ${body.length} bytes, app version ${version}`);
