/**
 * 실제 브라우저에서 변환이 되는지 확인한다.
 *
 * Node 로 도는 동일성 검증(`web/tests/test_browser_parity.py`)은 파이썬이 같은
 * 결과를 내는지까지만 본다. 여기서만 볼 수 있는 것이 따로 있다.
 *
 *   - 운영과 같은 CSP 아래에서 WebAssembly 가 컴파일되는가
 *     (`script-src` 에 'wasm-unsafe-eval' 이 없으면 화면이 통째로 죽는다)
 *   - 모듈 Web Worker 가 뜨고 큰 자산을 받아오는가
 *   - 받은 파일 이름이 한글까지 그대로인가
 *   - **여러 건을 한 번에 골라도** 건마다 한 개씩 제 이름으로 내려오는가
 *
 * 빌드된 dist 를 운영과 같은 헤더로 내려 주는 작은 서버를 띄우고, 파일을 골라
 * 변환 버튼을 눌러 실제로 내려받는다.
 *
 *   node web/frontend/e2e/browser_smoke.mjs <dist> <출력폴더> <xml…>
 *
 * 출력: <출력폴더>/<이름>.xlsx 와 result.json
 * 판정(내용이 CPython 산출물과 같은지)은 `web/tests/test_browser_e2e.py` 가 한다.
 */
import { chromium } from 'playwright';

import { createServer } from 'node:http';
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { basename, extname, join, resolve } from 'node:path';

/** 운영에서 붙는 헤더 (web/frontend/public/_headers 와 같은 값). */
const CSP =
  "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self'; " +
  "style-src 'self'; img-src 'self' data:; connect-src 'self'; form-action 'self'; " +
  "base-uri 'none'; frame-ancestors 'none'";

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.wasm': 'application/wasm',
  '.zip': 'application/zip',
  '.whl': 'application/octet-stream',
  '.map': 'application/json',
};

const [distArg, outArg, ...inputs] = process.argv.slice(2);
if (!distArg || !outArg || inputs.length === 0) {
  console.error('사용법: node browser_smoke.mjs <dist> <출력폴더> <xml…>');
  process.exit(2);
}

const dist = resolve(distArg);
const outDir = resolve(outArg);
mkdirSync(outDir, { recursive: true });

if (!existsSync(join(dist, 'py', 'engine.json'))) {
  console.error(`${dist}/py 에 변환 엔진이 없습니다. `
    + 'python web/scripts/build_browser_engine.py 뒤에 프런트엔드를 빌드하십시오.');
  process.exit(2);
}

const server = createServer((request, response) => {
  const path = decodeURIComponent((request.url ?? '/').split('?')[0]);
  let file = join(dist, path);
  // not_found_handling: single-page-application 과 같은 동작
  if (!existsSync(file) || statSync(file).isDirectory()) file = join(dist, 'index.html');

  response.setHeader('Content-Security-Policy', CSP);
  response.setHeader('X-Content-Type-Options', 'nosniff');
  response.setHeader('Content-Type', TYPES[extname(file)] ?? 'application/octet-stream');
  response.end(readFileSync(file));
});
await new Promise((done) => server.listen(0, '127.0.0.1', done));
const origin = `http://127.0.0.1:${server.address().port}`;

const launch = {};
// 이 환경에는 브라우저가 미리 깔려 있다. 있으면 그것을 쓴다.
if (process.env.CHROMIUM_PATH) launch.executablePath = process.env.CHROMIUM_PATH;

const browser = await chromium.launch(launch);
const page = await browser.newPage();

const problems = [];
page.on('pageerror', (error) => problems.push(`pageerror: ${error.message}`));
page.on('console', (message) => {
  if (message.type() === 'error') problems.push(`console: ${message.text()}`);
});

const results = {};
await page.goto(origin + '/');

// 화일을 **한 번에 모두** 고른다. 여러 건 변환이 한 건씩 변환과 같은 결과를
// 내는지가 이 스모크의 요점이다.
const saved = [];
page.on('download', async (download) => {
  const to = join(outDir, download.suggestedFilename());
  await download.saveAs(to);
  saved.push(download.suggestedFilename());
});

await page.setInputFiles('#file', inputs);
await page.click('#submit');

// CSP 가 eval 을 막아 waitForFunction 을 쓸 수 없다. 상태줄을 폴링한다.
const deadline = Date.now() + 300_000;
for (;;) {
  const text = (await page.textContent('#status')) ?? '';
  if (text.includes('내려받았습니다') || text.includes('실패')) break;
  if (Date.now() > deadline) {
    problems.push(`시간 초과: ${text}`);
    break;
  }
  await page.waitForTimeout(500);
}
await page.waitForTimeout(1500);   // 마지막 내려받기가 끝나기를 기다린다

const statusText = await page.textContent('#status');
for (const input of inputs) {
  const filename = basename(input);
  const stem = filename.slice(0, filename.length - extname(filename).length);
  const target = join(outDir, `${stem}.xlsx`);
  results[filename] = {
    downloaded_as: saved.includes(`${stem}.xlsx`) ? `${stem}.xlsx` : null,
    bytes: existsSync(target) ? statSync(target).size : 0,
    status_text: statusText,
    error_shown: (await page.getAttribute('#error', 'hidden')) === null,
  };
  console.log(`${filename} -> ${results[filename].downloaded_as} (${results[filename].bytes} bytes)`);
}
results['#batch'] = { selected: inputs.length, downloaded: saved.length, status_text: statusText };

results['#page'] = {
  template_version: await page.textContent('#template-version'),
  deployment_version: await page.textContent('#deployment-version'),
  problems,
};
writeFileSync(join(outDir, 'result.json'), JSON.stringify(results, null, 2));

await browser.close();
server.close();

if (problems.length) {
  console.error('브라우저가 오류를 냈습니다:\n' + problems.join('\n'));
  process.exit(1);
}
