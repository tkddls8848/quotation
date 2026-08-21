/**
 * 변환 Web Worker.
 *
 * Pyodide 기동과 XLSX 생성은 수백 ms~수 초의 CPU 를 쓴다. 화면 스레드에서
 * 하면 진행 표시도 취소 버튼도 얼어붙는다. 그래서 여기서 돈다.
 *
 * 규칙은 하나다. **이 파일에는 변환 규칙이 없다.** 파이썬(`entry.py` → `api.py`
 * → `quotation.core`)이 하고, 여기는 심부름만 한다.
 */

import { createEngine } from './engine.js';
import type { Engine } from './engine.js';

/** 자산 위치. 배포에서는 정적 자산으로 같은 출처에서 내려온다. */
const BASE_URL = new URL('/py/', self.location.origin).href;

export type WorkerRequest =
  | { kind: 'warmup' }
  | {
      kind: 'convert';
      id: number;
      filename: string;
      content: Uint8Array;
      contentType: string;
      deploymentVersion: string;
    };

export type WorkerMessage =
  | { kind: 'stage'; stage: string }
  | { kind: 'ready'; templateVersion: string }
  | { kind: 'failed'; id?: number; reason: string }
  | {
      kind: 'done';
      id: number;
      status: number;
      headers: Record<string, string>;
      body: Uint8Array;
    };

const post = (message: WorkerMessage, transfer?: Transferable[]): void => {
  (self as unknown as Worker).postMessage(message, transfer ?? []);
};

let engine: Promise<Engine> | null = null;

/** 엔진은 한 번만 띄우고 계속 쓴다. 두 번째 변환부터는 준비 비용이 없다. */
function boot(): Promise<Engine> {
  engine ??= createEngine({
    baseUrl: BASE_URL,
    onStage: (stage) => post({ kind: 'stage', stage }),
  }).then((ready) => {
    post({ kind: 'ready', templateVersion: ready.templateVersion });
    return ready;
  });
  return engine;
}

self.addEventListener('message', (event: MessageEvent<WorkerRequest>) => {
  const request = event.data;

  if (request.kind === 'warmup') {
    // 사용자가 파일을 고르는 동안 미리 띄워 둔다. 실패해도 화면은 그대로 둔다.
    boot().catch((error: unknown) => {
      post({ kind: 'failed', reason: describe(error) });
    });
    return;
  }

  void (async () => {
    try {
      const ready = await boot();
      const result = ready.convert({
        filename: request.filename,
        content: request.content,
        contentType: request.contentType,
        deploymentVersion: request.deploymentVersion,
      });
      // 본문은 복사하지 않고 넘긴다.
      post(
        {
          kind: 'done',
          id: request.id,
          status: result.status,
          headers: result.headers,
          body: result.body,
        },
        [result.body.buffer],
      );
    } catch (error: unknown) {
      post({ kind: 'failed', id: request.id, reason: describe(error) });
    }
  })();
});

function describe(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}
