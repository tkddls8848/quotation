/**
 * 브라우저 변환 엔진을 Node 에서 그대로 돌린다 — 동일성 검증 전용.
 *
 * 화면이 쓰는 `web/frontend/src/engine.js` 를 **같은 파일** 그대로 부른다.
 * 그래서 여기서 나온 바이트는 브라우저가 만드는 바이트다.
 * `web/tests/test_browser_parity.py` 가 이것을 CPython 산출물과 대조한다.
 *
 *   node web/scripts/browser_convert.mjs <엔진폴더> <출력폴더> <xml…>
 *
 * 출력: <출력폴더>/<이름>.xlsx 와 <이름>.json (상태·헤더·로그)
 */
import { createEngine } from '../frontend/src/engine.js';

import { mkdirSync, readFileSync, readdirSync, writeFileSync, linkSync } from 'node:fs';
import { basename, extname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { mkdtempSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

/**
 * Node 는 확장자 없는 폴더의 `.js` 를 ESM 으로 볼지 CJS 로 볼지 정하지 못해
 * `pyodide.asm.js` 로드에 실패한다. 브라우저에는 없는 문제라 여기서만 푼다.
 * 자산을 하드링크한 임시 폴더에 `package.json` 한 줄을 얹는다.
 */
function commonjsShim(engineDir) {
  const shim = mkdtempSync(join(tmpdir(), 'quotation-engine-'));
  for (const name of readdirSync(engineDir)) {
    linkSync(join(engineDir, name), join(shim, name));
  }
  writeFileSync(join(shim, 'package.json'), '{"type":"commonjs"}\n');
  return shim;
}

const [engineArg, outArg, ...inputs] = process.argv.slice(2);
if (!engineArg || !outArg || inputs.length === 0) {
  console.error('사용법: node browser_convert.mjs <엔진폴더> <출력폴더> <xml…>');
  process.exit(2);
}

const engineDir = resolve(engineArg);
const outDir = resolve(outArg);
mkdirSync(outDir, { recursive: true });

const baseUrl = commonjsShim(engineDir) + '/';
const engine = await createEngine({
  baseUrl,
  loadBinary: async (url) => new Uint8Array(readFileSync(url)),
  loadJson: async (url) => JSON.parse(readFileSync(url, 'utf8')),
  importModule: (url) => import(pathToFileURL(url).href),
});

for (const input of inputs) {
  const filename = basename(input);
  const result = engine.convert({
    filename,
    content: new Uint8Array(readFileSync(input)),
    contentType: 'text/xml',
    deploymentVersion: 'parity',
  });

  const stem = filename.slice(0, filename.length - extname(filename).length);
  if (result.status === 200) {
    writeFileSync(join(outDir, `${stem}.xlsx`), Buffer.from(result.body));
  }
  writeFileSync(
    join(outDir, `${stem}.json`),
    JSON.stringify(
      {
        status: result.status,
        headers: result.headers,
        log: result.log,
        // 견적 날짜는 브라우저가 정한다. 대조하는 쪽이 같은 날짜를 쓰도록 남긴다.
        today: engine.today(),
        body_length: result.body.length,
        body_utf8: result.status === 200 ? null : Buffer.from(result.body).toString('utf8'),
      },
      null,
      2,
    ),
  );
  console.log(`${filename} -> ${result.status} (${result.body.length} bytes)`);
}
