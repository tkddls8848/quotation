// CFR <-> CFRJSON codec, lifted straight out of the e-config Cloud bundle.
//
// Nothing here reimplements the format: `decode`/`encode` are the very functions
// the web app itself uses, so the fixed-width record layout, the code pages and
// the section/product model stay authoritative even when IBM changes them.

import fs from 'node:fs';
import { webpackRequire, CFR_CODEC_MODULE_ID } from './runtime.mjs';

// .cfr is a byte-oriented fixed-width format - column offsets are bytes, not
// code points - so it must round-trip through a single-byte encoding.
export const CFR_ENCODING = 'latin1';

let _codec = null;
function codec() {
  if (_codec) return _codec;
  const mod = webpackRequire()(CFR_CODEC_MODULE_ID);
  if (!mod?.gQ?.fromCFRSync || !mod?.oD?.fromCFRJSON) {
    throw new Error('CFR codec not found in bundle - IBM may have reshuffled the chunks');
  }
  return (_codec = mod);
}

/** CFR text -> CFRJSON object. Throws if the text is not a parsable CFR. */
export function decode(text) {
  const json = codec().gQ.fromCFRSync(text);
  if (!json) throw new Error('not a parsable CFR (decoder returned undefined)');
  return json;
}

/** CFRJSON object -> CFR text. See README for the trailer caveat. */
export function encode(json) {
  return codec().oD.fromCFRJSON(json);
}

/** Build a CFRJSON from a flat backend-shaped product list. */
export function fromProducts(products, brand, country, language, region) {
  return codec().gQ.fromProducts(products, brand, country, language, region);
}

/** Splice a product list into an existing CFRJSON (the template workflow). */
export function fromProductsList(cfrjson, products, section, brand, country) {
  return codec().gQ.fromProductsList(cfrjson, products, section, brand, country);
}

export function readCfr(file) {
  return fs.readFileSync(file, CFR_ENCODING);
}

export function writeCfr(file, text) {
  fs.writeFileSync(file, text, CFR_ENCODING);
}

export function loadCfr(file) {
  return decode(readCfr(file));
}

// ---------------------------------------------------------------------------
// Views over a decoded configuration
// ---------------------------------------------------------------------------

/** Flatten a CFRJSON into one row per product, each carrying its feature codes. */
export function listProducts(json) {
  return Object.entries(json.products ?? {}).map(([uid, p]) => ({
    uid,
    mtm: [p.type, p.model].filter(Boolean).join('-'),
    class: p.class ?? '',
    description: p.description ?? '',
    quantity: p.quantity ?? 0,
    features: (p.features ?? []).map((f) => ({
      code: f.num,
      description: f.description ?? '',
      quantity: f.quantity ?? 0,
    })),
  }));
}

export function summarize(json) {
  const products = listProducts(json);
  return {
    creating_application: json.document_info?.creating_applic_name ?? '',
    system_level: json.document_info?.system_level ?? '',
    created: json.document_info?.config_creation_date ?? '',
    country: json.document_info?.config_country_code ?? '',
    language: json.document_info?.selected_language ?? '',
    systems: Object.entries(json.systems ?? {}).map(([key, s]) => ({
      key,
      mtm: [s.machine_type, s.model].filter(Boolean).join('-'),
      description: s.system_description ?? '',
      serial: s.serial ?? '',
    })),
    productCount: products.length,
    featureCount: products.reduce((n, p) => n + p.features.length, 0),
    products,
  };
}

/**
 * Feature-code multiset for the whole configuration, keyed `MTM/CODE`.
 * This is the representation that makes two configurations comparable.
 */
export function featureIndex(json) {
  const index = new Map();
  for (const p of listProducts(json)) {
    for (const f of p.features) {
      const key = `${p.mtm}/${f.code}`;
      const hit = index.get(key);
      if (hit) hit.quantity += f.quantity * (p.quantity || 1);
      else
        index.set(key, {
          mtm: p.mtm,
          code: f.code,
          description: f.description,
          quantity: f.quantity * (p.quantity || 1),
        });
    }
  }
  return index;
}

/** Compare two configurations by feature code. */
export function diff(aJson, bJson) {
  const a = featureIndex(aJson);
  const b = featureIndex(bJson);
  const rows = [];
  for (const key of new Set([...a.keys(), ...b.keys()])) {
    const left = a.get(key);
    const right = b.get(key);
    const lq = left?.quantity ?? 0;
    const rq = right?.quantity ?? 0;
    if (lq === rq) continue;
    rows.push({
      mtm: (left ?? right).mtm,
      code: (left ?? right).code,
      description: (left ?? right).description,
      left: lq,
      right: rq,
      delta: rq - lq,
    });
  }
  rows.sort((x, y) => x.mtm.localeCompare(y.mtm) || x.code.localeCompare(y.code));
  return rows;
}

// ---------------------------------------------------------------------------
// Round-trip fidelity
// ---------------------------------------------------------------------------

/** Record types that carry the bill of materials - these must survive intact. */
export const BOM_RECORDS = new Set(['08', '19', '25', '26', '38', '47', '48', '49', '50', '78', '96', '97']);

const records = (text) =>
  text
    .split(/\r?\n/)
    .map((l) => l.replace(/\s+$/, ''))
    .filter(Boolean);

/**
 * Compare original CFR text against a re-encode of it.
 *
 * The encoder does not reproduce a file byte for byte: it reorders records,
 * repacks the engine-state blob in record 06, rewrites the description field in
 * record 95 and omits the checksum trailer 99. So fidelity is measured as a
 * multiset over records, per record type, rather than positionally.
 */
export function fidelity(originalText, encodedText) {
  const bag = (arr) => {
    const m = new Map();
    for (const l of arr) m.set(l, (m.get(l) ?? 0) + 1);
    return m;
  };
  const a = bag(records(originalText));
  const b = bag(records(encodedText));

  const byType = {};
  const bump = (line, key) => {
    const t = line.slice(0, 2);
    byType[t] ??= { missing: 0, added: 0 };
    byType[t][key]++;
  };
  for (const [line, n] of a) for (let i = 0; i < n - (b.get(line) ?? 0); i++) bump(line, 'missing');
  for (const [line, n] of b) for (let i = 0; i < n - (a.get(line) ?? 0); i++) bump(line, 'added');

  const bomChanged = Object.entries(byType).filter(([t]) => BOM_RECORDS.has(t));
  return {
    total: records(originalText).length,
    byType,
    bomIntact: bomChanged.length === 0,
    bomChanged: Object.fromEntries(bomChanged),
  };
}

/**
 * Set the quantity of a feature code in place.
 * `productUid` narrows the edit to one product; omit it to hit every product
 * carrying the code. Returns the edits that were applied.
 */
export function setFeatureQuantity(json, code, quantity, productUid = null) {
  const applied = [];
  for (const [uid, p] of Object.entries(json.products ?? {})) {
    if (productUid && uid !== productUid) continue;
    for (const f of p.features ?? []) {
      if (f.num !== code) continue;
      applied.push({ uid, code, from: f.quantity, to: quantity });
      f.quantity = quantity;
    }
  }
  return applied;
}
