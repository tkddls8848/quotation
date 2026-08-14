/**
 * 변환 배선 — 브라우저 엔진을 먼저 쓰고, 못 띄우면 서버 API 로 넘어간다.
 *
 * 왜 브라우저가 먼저인가: Cloudflare Workers Free 는 요청당 CPU 10 ms 이고
 * 견적서 한 건은 가장 작은 입력도 73 ms 가 든다(계획서 §18.3). 무료 계정에서
 * 서버 변환은 애초에 성립하지 않는다. 브라우저에서 도는 파이썬은 서버가 돌리던
 * 것과 같은 파일이므로 결과는 같다(`web/tests/test_browser_parity.py`).
 *
 * 서버로 넘어가는 경우는 하나뿐이다 — **엔진 자체를 못 띄웠을 때.** 변환이
 * 오류로 끝난 것은 넘어갈 이유가 아니다. 서버도 같은 코드라 같은 오류를 낸다.
 */

import { ConvertError, Converted, convertOnServer } from './api';
import { filenameFromDisposition, outputNameFor } from './download';

export type Stage = string;

const DEFAULT_MESSAGE = '변환에 실패했습니다. 잠시 후 다시 시도하십시오.';

type WorkerMessage =
  | { kind: 'stage'; stage: string }
  | { kind: 'ready'; templateVersion: string }
  | { kind: 'failed'; id?: number; reason: string }
  | { kind: 'done'; id: number; status: number; headers: Record<string, string>; body: Uint8Array };

interface Pending {
  resolve: (value: Converted) => void;
  reject: (reason: unknown) => void;
  fallbackName: string;
}

export interface ConvertOptions {
  signal: AbortSignal;
  onStage?: (stage: Stage) => void;
}

/** 브라우저 엔진이 뜬 적이 있는지. 화면이 안내 문구를 고르는 데 쓴다. */
export type EngineState = 'unknown' | 'ready' | 'unavailable';

export class Converter {
  private worker: Worker | null = null;
  private pending = new Map<number, Pending>();
  private nextId = 1;
  private onStage: ((stage: Stage) => void) | null = null;

  state: EngineState = 'unknown';
  templateVersion: string | null = null;

  /** 사용자가 파일을 고르는 동안 엔진을 미리 띄워 둔다. */
  warmup(): void {
    try {
      this.ensureWorker().postMessage({ kind: 'warmup' });
    } catch {
      this.state = 'unavailable';
    }
  }

  async convert(file: File, options: ConvertOptions): Promise<Converted> {
    const deploymentVersion = __DEPLOYMENT_VERSION__;

    if (this.state !== 'unavailable') {
      try {
        return await this.inBrowser(file, options, deploymentVersion);
      } catch (error) {
        // 변환이 판단해 낸 오류는 그대로 알린다. 서버도 같은 답을 낸다.
        if (error instanceof ConvertError) throw error;
        if (options.signal.aborted) throw error;
        this.state = 'unavailable';
      }
    }

    options.onStage?.('서버로 변환하는 중…');
    return convertOnServer(file, options.signal);
  }

  /** 취소. Pyodide 는 도중에 끊을 수 없으므로 일꾼을 통째로 내린다. */
  cancel(): void {
    if (!this.worker) return;
    this.worker.terminate();
    this.worker = null;
    for (const pending of this.pending.values()) {
      pending.reject(new DOMException('취소했습니다.', 'AbortError'));
    }
    this.pending.clear();
    // 엔진은 다음 시도에서 다시 띄운다. 못 띄운 것으로 보지 않는다.
    if (this.state === 'ready') this.state = 'unknown';
  }

  private inBrowser(file: File, options: ConvertOptions,
                    deploymentVersion: string): Promise<Converted> {
    const worker = this.ensureWorker();
    const id = this.nextId++;
    this.onStage = options.onStage ?? null;

    return new Promise<Converted>((resolve, reject) => {
      this.pending.set(id, { resolve, reject, fallbackName: outputNameFor(file.name) });

      options.signal.addEventListener('abort', () => this.cancel(), { once: true });

      void file.arrayBuffer().then(
        (buffer) => {
          const content = new Uint8Array(buffer);
          worker.postMessage(
            {
              kind: 'convert',
              id,
              filename: file.name,
              content,
              contentType: file.type,
              deploymentVersion,
            },
            [content.buffer],
          );
        },
        (error: unknown) => {
          this.pending.delete(id);
          reject(error);
        },
      );
    });
  }

  private ensureWorker(): Worker {
    if (this.worker) return this.worker;

    const worker = new Worker(new URL('./convert.worker.ts', import.meta.url), {
      type: 'module',
    });
    worker.addEventListener('message', (event: MessageEvent<WorkerMessage>) => {
      this.receive(event.data);
    });
    worker.addEventListener('error', () => {
      this.state = 'unavailable';
      for (const pending of this.pending.values()) {
        pending.reject(new Error('변환 엔진을 띄우지 못했습니다.'));
      }
      this.pending.clear();
    });
    this.worker = worker;
    return worker;
  }

  private receive(message: WorkerMessage): void {
    if (message.kind === 'stage') {
      this.onStage?.(message.stage);
      return;
    }
    if (message.kind === 'ready') {
      this.state = 'ready';
      this.templateVersion = message.templateVersion;
      return;
    }
    if (message.kind === 'failed') {
      if (this.state !== 'ready') this.state = 'unavailable';
      const pending = message.id === undefined ? null : this.pending.get(message.id);
      if (pending && message.id !== undefined) {
        this.pending.delete(message.id);
        pending.reject(new Error(message.reason));
      }
      return;
    }

    const pending = this.pending.get(message.id);
    if (!pending) return;
    this.pending.delete(message.id);
    try {
      pending.resolve(toConverted(message, pending.fallbackName));
    } catch (error) {
      pending.reject(error);
    }
  }
}

/** 엔진 응답을 서버 응답과 같은 방식으로 읽는다 (같은 헤더, 같은 오류 본문). */
function toConverted(
  message: { status: number; headers: Record<string, string>; body: Uint8Array },
  fallbackName: string,
): Converted {
  const requestId = message.headers['X-Request-Id'] ?? null;

  if (message.status !== 200) {
    let code = 'UNKNOWN';
    let text = DEFAULT_MESSAGE;
    try {
      const payload = JSON.parse(new TextDecoder().decode(message.body)) as {
        error?: { code?: string; message?: string; request_id?: string };
      };
      code = payload.error?.code ?? code;
      text = payload.error?.message ?? text;
    } catch {
      // 본문을 못 읽어도 상태 코드는 믿는다
    }
    throw new ConvertError(text, code, requestId);
  }

  return {
    blob: new Blob([message.body as BlobPart], {
      type: message.headers['Content-Type'],
    }),
    filename: filenameFromDisposition(
      message.headers['Content-Disposition'] ?? null,
      fallbackName,
    ),
    requestId,
    templateVersion: message.headers['X-Template-Version'] ?? null,
  };
}
