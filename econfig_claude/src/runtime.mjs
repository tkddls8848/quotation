// Minimal webpack-5 runtime.
//
// e-config Cloud ships as a webpack chunk that ends with
//   (self.webpackChunkecfgcloud_app_frontend ||= []).push([[792], {...modules...}, r => r(r.s = 5428)])
// The third element boots Angular. We intercept the push, keep only the module
// table, and never call the boot function - so nothing touches the DOM and the
// pure-JS modules (the CFR codec among them) can be required in plain Node.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
export const BUNDLE_PATH = path.join(ROOT, 'vendor', 'main.js');

let _require = null;

function build() {
  if (!fs.existsSync(BUNDLE_PATH)) {
    throw new Error(`bundle not found at ${BUNDLE_PATH}\nRun:  npm run fetch`);
  }
  const src = fs.readFileSync(BUNDLE_PATH, 'utf8');

  // The bundle only reads `self` and pushes onto the chunk array. Give it both,
  // then drop the globals again so we do not leak them into the host process.
  const prevSelf = globalThis.self;
  let table = null;
  globalThis.self = globalThis;
  globalThis.webpackChunkecfgcloud_app_frontend = {
    push(arg) {
      table = Object.assign(table ?? {}, arg[1]);
    },
    forEach() {},
    slice() {
      return [];
    },
  };
  try {
    (0, eval)(src);
  } finally {
    delete globalThis.webpackChunkecfgcloud_app_frontend;
    if (prevSelf === undefined) delete globalThis.self;
    else globalThis.self = prevSelf;
  }

  if (!table) throw new Error('bundle did not register a module table');

  const cache = Object.create(null);
  const req = (id) => {
    id = String(id);
    const hit = cache[id];
    if (hit) return hit.exports;
    const mod = table[id];
    if (!mod) throw new Error(`webpack module ${id} is not in this chunk`);
    const m = (cache[id] = { id, loaded: false, exports: {} });
    mod.call(m.exports, m, m.exports, req);
    m.loaded = true;
    return m.exports;
  };

  req.o = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
  req.d = (exports, getters) => {
    for (const key in getters) {
      if (req.o(getters, key) && !req.o(exports, key)) {
        Object.defineProperty(exports, key, { enumerable: true, get: getters[key] });
      }
    }
  };
  req.r = (exports) => {
    if (typeof Symbol !== 'undefined' && Symbol.toStringTag) {
      Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
    }
    Object.defineProperty(exports, '__esModule', { value: true });
  };
  req.n = (mod) => {
    const getter = mod && mod.__esModule ? () => mod.default : () => mod;
    req.d(getter, { a: getter });
    return getter;
  };
  req.nmd = (m) => {
    m.paths = [];
    m.children ??= [];
    return m;
  };
  req.m = table;
  req.p = '';

  return req;
}

/** Lazily instantiate the webpack require for the vendored bundle. */
export function webpackRequire() {
  return (_require ??= build());
}

/** Module 3294 is the CFR codec: exports gQ (decode), oD (encode), u4 (MRD tokens). */
export const CFR_CODEC_MODULE_ID = 3294;
