// Recovers the fixed-width record layout that .cfr files are written in.
//
// The layout lives as a module-private constant inside the codec chunk, so it
// cannot simply be required - it is lifted out of the source text instead.
// Shape: { "00": { name, map: [ [startCol, endCol, FIELD_NAME, {type,...}], ... ] }, ... }

import fs from 'node:fs';
import { BUNDLE_PATH } from './runtime.mjs';

const ANCHOR = '{"00":{name:"Header",map:[[';

function sliceObjectLiteral(src, start) {
  let depth = 0;
  let inStr = null;
  for (let i = start; i < src.length; i++) {
    const c = src[i];
    if (inStr) {
      if (c === '\\') i++;
      else if (c === inStr) inStr = null;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') inStr = c;
    else if (c === '{') depth++;
    else if (c === '}' && --depth === 0) return src.slice(start, i + 1);
  }
  throw new Error('unbalanced object literal');
}

export function recordSpec() {
  const src = fs.readFileSync(BUNDLE_PATH, 'utf8');
  const at = src.indexOf(ANCHOR);
  if (at === -1) throw new Error('record layout not found - bundle layout changed');

  let literal = sliceObjectLiteral(src, at);
  // Field types are enum members from a sibling module; inline them as strings.
  literal = literal.replace(/[A-Za-z_$][\w$]*\.vk\.([A-Z_0-9]+)/g, '"$1"');

  const leftover = literal.match(/[^"'\w](?:[A-Za-z_$][\w$]*)\.[A-Za-z_$]/g);
  if (leftover) throw new Error(`unresolved references in layout: ${[...new Set(leftover)].join(', ')}`);

  return (0, eval)('(' + literal + ')');
}

/** Render one record type as an aligned column map. */
export function formatRecord(code, record) {
  const lines = [`${code}  ${record.name ?? ''}`];
  for (const [from, to, name, opts] of record.map ?? []) {
    const span = `${String(from).padStart(4)}-${String(to).padEnd(4)}`;
    const width = String(to - from + 1).padStart(3);
    const extra = opts && Object.keys(opts).length ? '  ' + JSON.stringify(opts) : '';
    lines.push(`     ${span} (${width})  ${name}${extra}`);
  }
  return lines.join('\n');
}
