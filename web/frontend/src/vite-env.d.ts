/// <reference types="vite/client" />

/**
 * 배포 판본. 예전에는 `GET /api/v1/status` 로 물어봤지만, 그러면 화면을 여는
 * 것만으로 Worker 가 깨어난다. 빌드 시점에 박아 넣는다 (`vite.config.ts`).
 */
declare const __DEPLOYMENT_VERSION__: string;
