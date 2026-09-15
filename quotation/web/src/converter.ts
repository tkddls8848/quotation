/**
 * 변환 배선 — 변환은 브라우저 안에서만 한다.
 *
 * Cloudflare Workers Free 는 요청당 CPU 10 ms 이고 견적서 한 건은 가장 작은
 * 입력도 73 ms 가 든다(실측 measurements/runtime.md). 무료 계정에서 서버 변환은
 * 애초에 성립하지 않아 그 경로를 없앴다(결정 0010). 엔진을 못 띄우면 **그 사실을
 * 그대로 알린다** — 받아 줄 곳도 없는데 파일을 내보내지 않는다.
 *
 * 여기서 도는 것은 데스크톱이 쓰는 것과 같은 Rust 코어이고, 결과가 같은지는
 * `quotation/web/tests/test_browser_parity.py` 가 매번 대조한다.
 */

import { ConvertError, Converted } from './contract';
import { filenameFromDisposition, outputNameFor } from './download';

export type Stage = string;

const DEFAULT_MESSAGE = '변환에 실패했습니다. 잠시 후 다시 시도하십시오.';
const ENGINE_UNAVAILABLE = '이 브라우저에서는 변환 엔진을 띄우지 못했습니다.';

type WorkerMessage =
  | { kind: 'stage'; stage: string }
  | { kind: 'ready' }
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

  /** 사용자가 파일을 고르는 동안 엔진을 미리 띄워 둔다. */
  warmup(): void {
    try {
      this.ensureWorker().postMessage({ kind: 'warmup' });
    } catch {
      this.state = 'unavailable';
    }
  }

  async convert(file: File, options: ConvertOptions): Promise<Converted> {
    if (this.state === 'unavailable') throw new Error(ENGINE_UNAVAILABLE);
    try {
      return await this.inBrowser(file, options, __DEPLOYMENT_VERSION__);
    } catch (error) {
      // 변환이 판단해 낸 오류는 엔진 고장이 아니다. 상태를 내리지 않는다.
      if (error instanceof ConvertError || options.signal.aborted) throw error;
      this.state = 'unavailable';
      throw error;
    }
  }

  /** 취소. wasm 변환은 도중에 끊을 수 없으므로 일꾼을 통째로 내린다. */
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

/** 엔진 응답을 읽는다. 헤더와 오류 본문의 모양은 `rust/webapi` 가 정한다. */
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
