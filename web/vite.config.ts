// vitest 의 defineConfig 는 vite 의 것을 그대로 넓힌 것이다. test 항목까지 타입이 선다.
import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';

// 설정 파일은 Node 에서 돈다. @types/node 를 끌어오지 않기 위해 여기서만 알린다.
declare const process: { env: Record<string, string | undefined> };

const at = (path: string) => fileURLToPath(new URL(path, import.meta.url));

/**
 * 셸의 빌드 설정.
 *
 * 도구는 저장소 최상위에 기능별로 나뉘어 있고 (`quotation/`, `fire/`, `converters/`), 셸은
 * 별명으로만 그것들을 부른다. 도구끼리는 서로를 부르지 않는다 — 별명이
 * 셸에서 도구로 가는 한 방향만 있기 때문에 그 규칙이 설정으로 지켜진다.
 *
 * 빌드 결과는 web/dist 로 나가고 Workers Static Assets 가 그대로 배포한다
 * (web/wrangler.jsonc 의 assets.directory).
 *
 * 변환 엔진(Rust→WASM)은 `web/public/engine/` 에 있고 그대로 복사된다.
 * `python quotation/web/scripts/build_browser_engine.py` 가 만든다. 번들러가
 * 손대지 않는 이유는 그것이 실행 파일이 아니라 **런타임이 읽는 자료** 이기
 * 때문이다.
 */
export default defineConfig({
  resolve: {
    alias: {
      '@quotation': at('../quotation/web/src'),
      '@fire': at('../fire/web/src'),
      '@converters': at('../converters/web/src'),
      'pdf-lib': at('./node_modules/pdf-lib/es/index.js'),
    },
  },
  define: {
    __DEPLOYMENT_VERSION__: JSON.stringify(process.env.DEPLOYMENT_VERSION ?? 'dev'),
  },
  worker: {
    // 변환 일꾼은 모듈 워커다. `import.meta.url` 로 만든 URL 을 그대로 쓴다.
    format: 'es',
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
  },
  server: {
    port: 5173,
    fs: {
      // 도구가 셸 폴더 밖에 있다. 개발 서버가 그것을 읽을 수 있어야 한다.
      allow: [at('..')],
    },
  },
  test: {
    // 각 도구의 테스트는 그 도구 폴더에 있다.
    include: [
      'src/**/*.test.ts',
      '../quotation/web/src/**/*.test.ts',
      '../fire/web/src/**/*.test.ts',
      // 기능이 가진 Worker 도 그 폴더에서 검사한다 (결정 0013).
      '../fire/worker/**/*.test.ts',
      '../converters/web/src/**/*.test.ts',
    ],
  },
});
