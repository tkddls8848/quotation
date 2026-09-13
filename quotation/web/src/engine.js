/**
 * 브라우저 변환 엔진 (결정 decisions/0002).
 *
 * Cloudflare Workers Free 는 요청당 CPU 10 ms 다. 견적서 한 건은 가장 작은
 * 입력도 73 ms 가 든다(실측 measurements/runtime.md). 그래서 무료 계정에서는 변환을
 * 브라우저가 하고 Cloudflare 는 정적 자산만 내려 준다.
 *
 * 여기서 돌리는 것은 데스크톱이 쓰는 것과 **같은 코어** 다. 변환 규칙도,
 * 파일 검증과 오류 문구도 Rust 한 벌에서 온다 (`rust/core`, `rust/webapi`).
 * 이 파일이 하는 일은 wasm 을 세우고 `convert` 를 부르는 것뿐이며, 규칙은 한
 * 줄도 여기 없다.
 *
 * TypeScript 가 아니라 JavaScript 인 이유: 브라우저의 Web Worker 와 Node 로
 * 도는 동일성 검증(`web/tests/test_browser_parity.py`)이 **같은 파일** 을 쓴다.
 * 검증한 것과 배포되는 것이 갈라지지 않게 한다.
 */

/** 화면에 보여 줄 준비 단계. 예전 Pyodide 는 세 단계였고 지금은 한 단계다. */
export const STAGES = {
  runtime: '변환 엔진을 내려받는 중… (최초 1회만)',
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

/** 요청 ID. 오류 화면과 로그가 같은 건을 가리키게 하는 값이다. */
function newRequestId() {
  const source = globalThis.crypto;
  if (source?.randomUUID) return source.randomUUID();
  const bytes = new Uint8Array(16);
  source.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-`
    + `${hex.slice(16, 20)}-${hex.slice(20)}`;
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
  const wasm = await importModule(baseUrl + manifest.module.file);
  // 바이트를 직접 넘긴다. 글루가 스스로 fetch 하지 않으므로 브라우저와 Node
  // 에서 같은 경로로 선다.
  await wasm.default({ module_or_path: await loadBinary(baseUrl + manifest.wasm.file) });

  onStage(STAGES.ready);

  return {
    manifest,

    /** 이번 변환이 쓸 견적 날짜 (Asia/Seoul). 동일성 검증이 읽는다. */
    today() {
      return wasm.today(Date.now());
    },

    /**
     * XML 한 건을 견적서로 바꾼다. 서버의 `POST /api/v1/convert` 와 같은 응답을
     * 돌려준다 — 같은 상태 코드, 같은 헤더, 같은 본문, 같은 오류 메시지.
     *
     * IBM 문서인지 레노버 x86 문서인지는 고를 필요가 없다. XML 내용으로
     * 코어가 알아낸다.
     *
     * @param {{filename: string, content: Uint8Array, contentType?: string,
     *          deploymentVersion?: string}} upload
     */
    convert(upload) {
      return wasm.convert(
        upload.filename,
        upload.content,
        upload.contentType ?? '',
        upload.deploymentVersion ?? 'browser',
        newRequestId(),
        Date.now(),
      );
    },
  };
}
