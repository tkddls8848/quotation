// 관문 2 — WASM 기동 시간 측정.
//
//   node tools/wasm_startup_bench.mjs [반복]
//
// 재는 것은 두 가지다.
//   1. 기동: .wasm 바이트를 컴파일하고 인스턴스를 세우기까지.
//   2. 변환 1건: 템플릿을 열어 XML 을 훑고 다시 저장하기까지.
//
// 지금 Pyodide 는 기동에 2.5 s 를 쓴다 (doc/measurements/runtime.md).
// 판정 기준은 기동 200 ms 이하다.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const wasmPath = join(root, "rust", "wasm", "pkg-node", "quotation_wasm_bg.wasm");
const glueUrl = new URL("../rust/wasm/pkg-node/quotation_wasm.js", import.meta.url);
const templatePath = join(root, "quotation", "resources", "견적서_template_IBM.xlsx");
const xmlPath = join(root, "tests", "fixtures", "public", "new_quote.xml");

const rounds = Number(process.argv[2] ?? 10);
const wasmBytes = readFileSync(wasmPath);

// 1. 기동 — 브라우저가 자산을 받은 뒤에 하는 일과 같다.
//    (내려받는 시간은 크기 측정 쪽에서 따로 본다.)
const startup = [];
for (let i = 0; i < rounds; i += 1) {
  const started = performance.now();
  const module = await WebAssembly.compile(wasmBytes);
  const imports = {};
  for (const { module: name } of WebAssembly.Module.imports(module)) {
    imports[name] ??= new Proxy({}, { get: () => () => {} });
  }
  await WebAssembly.instantiate(module, imports);
  startup.push(performance.now() - started);
}

// 2. 변환 1건 — 같은 인스턴스를 여러 번 부른다. 이제 진짜 견적서를 만든다.
const { convert } = await import(glueUrl.href);
const template = readFileSync(templatePath);
const xml = readFileSync(xmlPath);
const conversions = [];
for (let i = 0; i < rounds; i += 1) {
  const started = performance.now();
  convert(xml, template, 2026, 8, 27);
  conversions.push(performance.now() - started);
}

const report = (label, samples) => {
  const sorted = [...samples].sort((a, b) => a - b);
  const middle = sorted[Math.floor(sorted.length / 2)];
  console.log(
    `${label}: 중앙값 ${middle.toFixed(1)} ms  (최소 ${sorted[0].toFixed(1)} / ` +
      `최대 ${sorted[sorted.length - 1].toFixed(1)}, ${samples.length}회)`,
  );
};

console.log(`wasm ${(wasmBytes.length / 1048576).toFixed(2)} MiB, node ${process.version}`);
report("기동(compile + instantiate)", startup);
report("변환 1건(XML -> 견적서 .xlsx)", conversions);
