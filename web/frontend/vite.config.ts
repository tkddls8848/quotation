import { defineConfig } from 'vite';

// 설정 파일은 Node 에서 돈다. @types/node 를 끌어오지 않기 위해 여기서만 알린다.
declare const process: { env: Record<string, string | undefined> };

/**
 * 빌드 결과는 web/frontend/dist 로 나가고 Workers Static Assets 가 그대로 배포한다
 * (web/wrangler.jsonc 의 assets.directory).
 *
 * 변환 엔진(Pyodide 런타임 + 파이썬 모듈)은 `public/py/` 에 있고 그대로 복사된다.
 * `python web/scripts/build_browser_engine.py` 가 만든다. 번들러가 손대지 않는
 * 이유는 그것이 실행 파일이 아니라 **런타임이 읽는 자료** 이기 때문이다.
 *
 * 개발 중에는 `wrangler dev` 가 띄운 Worker 로 /api 요청만 넘긴다. 무료 계정
 * 배포에는 Worker 가 없지만, Paid 의 `env.server` 배포를 로컬에서 확인할 때
 * 같은 동일 출처 구성을 그대로 쓴다.
 */
export default defineConfig({
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
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8787',
        changeOrigin: false,
      },
    },
  },
});
