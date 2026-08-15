// Local-only HTTP wrapper around the CFR codec.
//
// Configuration files carry customer names and list pricing, so this binds to
// the loopback interface and keeps every uploaded file in memory: nothing is
// written to disk and nothing leaves the machine.

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import {
  decode,
  encode,
  summarize,
  diff,
  fidelity,
  setFeatureQuantity,
  CFR_ENCODING,
} from './codec.mjs';
import { generate, specFromCfr } from './generate.mjs';
import { recordSpec } from './spec.mjs';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const WEB = path.join(ROOT, 'web');
const MAX_BODY = 32 * 1024 * 1024;

/** id -> { id, name, text } . Decoding happens per request so edits never
 *  mutate the stored baseline. */
const store = new Map();

const readBody = (req) =>
  new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (c) => {
      size += c.length;
      if (size > MAX_BODY) {
        reject(new Error('upload too large'));
        req.destroy();
      } else chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });

const json = (res, code, body) => {
  const text = JSON.stringify(body);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(text),
  });
  res.end(text);
};

function fileEntry(rec) {
  const parsed = decode(rec.text);
  const s = summarize(parsed);
  return {
    id: rec.id,
    name: rec.name,
    bytes: Buffer.byteLength(rec.text, CFR_ENCODING),
    systems: s.systems,
    productCount: s.productCount,
    featureCount: s.featureCount,
    created: s.created,
    country: s.country,
    language: s.language,
    application: s.creating_application,
  };
}

const need = (id) => {
  const rec = store.get(id);
  if (!rec) throw Object.assign(new Error('unknown file id'), { status: 404 });
  return rec;
};

async function api(req, res, url) {
  const seg = url.pathname.split('/').filter(Boolean); // ['api', ...]

  if (req.method === 'POST' && seg.length === 2 && seg[1] === 'files') {
    const buf = await readBody(req);
    const name = decodeURIComponent(req.headers['x-filename'] ?? 'upload.cfr');
    const text = buf.toString(CFR_ENCODING);
    // Reject non-CFR input before it enters the store; a bad upload is the
    // caller's mistake, so report it as 400 rather than letting it read as 500.
    try {
      decode(text);
    } catch (e) {
      throw Object.assign(new Error(`${name}: ${e.message}`), { status: 400 });
    }
    const rec = { id: randomUUID(), name, text };
    store.set(rec.id, rec);
    return json(res, 200, fileEntry(rec));
  }

  if (req.method === 'GET' && seg.length === 2 && seg[1] === 'files') {
    return json(res, 200, [...store.values()].map(fileEntry));
  }

  if (req.method === 'DELETE' && seg.length === 3 && seg[1] === 'files') {
    store.delete(seg[2]);
    return json(res, 200, { ok: true });
  }

  if (req.method === 'GET' && seg.length === 4 && seg[1] === 'files' && seg[3] === 'inspect') {
    return json(res, 200, summarize(decode(need(seg[2]).text)));
  }

  if (req.method === 'GET' && seg.length === 4 && seg[1] === 'files' && seg[3] === 'fidelity') {
    const rec = need(seg[2]);
    return json(res, 200, fidelity(rec.text, encode(decode(rec.text))));
  }

  if (req.method === 'GET' && seg.length === 2 && seg[1] === 'diff') {
    const a = need(url.searchParams.get('a'));
    const b = need(url.searchParams.get('b'));
    return json(res, 200, {
      a: a.name,
      b: b.name,
      rows: diff(decode(a.text), decode(b.text)),
    });
  }

  if (req.method === 'POST' && seg.length === 4 && seg[1] === 'files' && seg[3] === 'set') {
    const rec = need(seg[2]);
    const body = JSON.parse((await readBody(req)).toString('utf8'));
    const parsed = decode(rec.text);
    const applied = setFeatureQuantity(
      parsed,
      String(body.code),
      Number(body.quantity),
      body.product || null,
    );
    if (!applied.length) {
      return json(res, 400, { error: `feature code ${body.code} not present in this configuration` });
    }
    const cfr = encode(parsed);
    return json(res, 200, {
      applied,
      name: rec.name.replace(/\.cfr$/i, `.${body.code}x${body.quantity}.cfr`),
      // latin1 -> base64 keeps the byte stream intact across JSON
      cfr: Buffer.from(cfr, CFR_ENCODING).toString('base64'),
    });
  }

  if (req.method === 'GET' && seg.length === 4 && seg[1] === 'files' && seg[3] === 'spec') {
    const rec = need(seg[2]);
    return json(res, 200, specFromCfr(rec.text, { templateName: rec.name }));
  }

  if (req.method === 'POST' && seg.length === 2 && seg[1] === 'generate') {
    const body = JSON.parse((await readBody(req)).toString('utf8'));
    const tpl = need(body.templateId);
    let built;
    try {
      built = generate(body.spec, tpl.text);
    } catch (e) {
      throw Object.assign(e, { status: 400 });
    }
    return json(res, 200, {
      report: built.report,
      name: (body.name || tpl.name.replace(/\.cfr$/i, '') + '.generated') + '.cfr',
      cfr: Buffer.from(built.cfr, CFR_ENCODING).toString('base64'),
    });
  }

  if (req.method === 'GET' && seg.length === 2 && seg[1] === 'spec') {
    return json(res, 200, recordSpec());
  }

  return json(res, 404, { error: 'no such endpoint' });
}

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css' };

export function serve({ port = 4173, host = '127.0.0.1' } = {}) {
  const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    try {
      if (url.pathname.startsWith('/api/')) return await api(req, res, url);

      const rel = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
      const file = path.join(WEB, rel);
      if (!file.startsWith(WEB) || !fs.existsSync(file)) {
        res.writeHead(404).end('not found');
        return;
      }
      res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] ?? 'application/octet-stream' });
      fs.createReadStream(file).pipe(res);
    } catch (e) {
      json(res, e.status ?? 500, { error: e.message });
    }
  });

  server.listen(port, host, () => {
    console.log(`econfig web UI  ->  http://${host}:${port}`);
    console.log('loopback only; uploads stay in memory. Ctrl+C to stop.');
  });
  return server;
}
