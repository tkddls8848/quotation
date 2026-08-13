import { defineConfig } from 'vite';

/**
 * 빌드 결과는 web/frontend/dist 로 나가고 Workers Static Assets 가 그대로 배포한다
 * (web/wrangler.jsonc 의 assets.directory).
 *
 * 개발 중에는 `wrangler dev` 가 띄운 Worker 로 /api 요청만 넘긴다. 그래야
 * 운영과 같은 동일 출처 구성을 로컬에서도 그대로 쓴다.
 */
export default defineConfig({
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
