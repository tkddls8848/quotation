/**
 * 브라우저 변환 엔진 (계획서 §18.5).
 *
 * Cloudflare Workers Free 는 요청당 CPU 10 ms 다. 견적서 한 건은 가장 작은
 * 입력도 73 ms 가 든다(계획서 §18.3). 그래서 무료 계정에서는 변환을 브라우저가
 * 하고 Cloudflare 는 정적 자산만 내려 준다.
 *
 * 여기서 돌리는 파이썬은 Worker 가 돌리던 것과 **같은 파일** 이다
 * (`web/scripts/build_browser_engine.py` 가 `web/src` 에서 zip 으로 묶는다).
 * 이 파일이 하는 일은 Pyodide 를 띄우고 `entry.convert` 를 부르는 것뿐이며,
 * 변환 규칙은 한 줄도 여기 없다.
 *
 * TypeScript 가 아니라 JavaScript 인 이유: 브라우저의 Web Worker 와 Node 로
 * 도는 동일성 검증(`web/tests/test_browser_parity.py`)이 **같은 파일** 을 쓴다.
 * 검증한 것과 배포되는 것이 갈라지지 않게 한다.
 */

/** 파이썬 모듈을 풀어 둘 자리. sys.path 맨 앞에 넣는다. */
const EXTRACT_DIR = '/quotation-engine';

/** 화면에 보여 줄 준비 단계. 실제 진행률은 알 수 없으므로 단계만 알린다. */
export const STAGES = {
  runtime: '변환 엔진을 내려받는 중… (최초 1회만)',
  packages: '변환 라이브러리를 준비하는 중…',
  core: '견적서 양식을 불러오는 중…',
  ready: '변환 준비 완료',
};

async function fetchBinary(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} 을 받지 못했습니다 (${response.status})`);
  return new Uint8Array(await response.arrayBuffer());
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} 을 받지 못했습니다 (${response.status})`);
  return response.json();
}

/**
 * 엔진을 띄운다. 무거운 준비는 여기서 한 번만 한다.
 *
 * @param {object} options
 * @param {string} options.baseUrl        자산 폴더 URL (끝에 `/`)
 * @param {(stage: string) => void} [options.onStage]  준비 단계 알림
 * @param {(url: string) => Promise<Uint8Array>} [options.loadBinary]
 * @param {(url: string) => Promise<object>} [options.loadJson]
 * @param {(url: string) => Promise<object>} [options.importModule]
 */
export async function createEngine(options) {
  const {
    baseUrl,
    onStage = () => {},
    loadBinary = fetchBinary,
    loadJson = fetchJson,
    importModule = (url) => import(/* @vite-ignore */ url),
  } = options;

  onStage(STAGES.runtime);
  const manifest = await loadJson(baseUrl + 'engine.json');
  const { loadPyodide } = await importModule(baseUrl + 'pyodide.mjs');
  const pyodide = await loadPyodide({ indexURL: baseUrl });

  onStage(STAGES.packages);
  // lxml 은 C 확장이라 Pyodide 배포판의 wasm32 wheel 을 그대로 쓴다. 파일을
  // 직접 가리키므로 실행 중 외부 인덱스를 찾아가지 않는다.
  await pyodide.loadPackage(baseUrl + manifest.packages.lxml.file);

  onStage(STAGES.core);
  // 순수 파이썬 의존성(openpyxl·et_xmlfile)과 우리 모듈을 같은 자리에 편다.
  for (const file of [manifest.packages.python_deps.file, manifest.core.file]) {
    pyodide.unpackArchive(await loadBinary(baseUrl + file), 'zip', {
      extractDir: EXTRACT_DIR,
    });
  }
  pyodide.runPython(
    `import sys\npath = ${JSON.stringify(EXTRACT_DIR)}\n` +
      'if path not in sys.path:\n    sys.path.insert(0, path)\n',
  );

  const entry = pyodide.pyimport('entry');
  onStage(STAGES.ready);

  return {
    manifest,
    templateVersion: manifest.template.template_version,

    /** 이번 변환이 쓸 견적 날짜 (Asia/Seoul). 동일성 검증이 읽는다. */
    today() {
      return entry.today();
    },

    /**
     * XML 한 건을 견적서로 바꾼다. 서버의 `POST /api/v1/convert` 와 같은 응답을
     * 돌려준다 — 같은 상태 코드, 같은 헤더, 같은 본문, 같은 오류 메시지.
     *
     * @param {{filename: string, content: Uint8Array, contentType?: string,
     *          deploymentVersion?: string}} upload
     */
    convert(upload) {
      const result = entry.convert(
        upload.filename,
        pyodide.toPy(upload.content),
        upload.contentType ?? '',
        upload.deploymentVersion ?? 'browser',
      );
      try {
        return {
          status: result.get('status'),
          headers: takeMap(result, 'headers'),
          body: takeBytes(result, 'body'),
          log: takeMap(result, 'log'),
        };
      } finally {
        // PyProxy 는 직접 놓아 주어야 WASM 힙이 쌓이지 않는다.
        result.destroy();
      }
    },
  };
}

function takeMap(result, key) {
  const proxy = result.get(key);
  try {
    return Object.fromEntries(proxy.toJs());
  } finally {
    proxy.destroy();
  }
}

function takeBytes(result, key) {
  const proxy = result.get(key);
  try {
    return proxy.toJs();
  } finally {
    proxy.destroy();
  }
}
