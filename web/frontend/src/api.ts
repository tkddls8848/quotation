/**
 * 서버 API 호출 (계약은 doc 계획서 §6).
 *
 * 무료 계정 배포에서는 **이 경로를 쓰지 않는다.** 변환은 브라우저가 하고
 * (`converter.ts`), Cloudflare 는 정적 자산만 내려 준다. 여기 남겨 둔 것은
 * 브라우저 엔진을 못 띄웠을 때의 대비책이며, Workers Paid 에 Python Worker 를
 * 함께 올린 배포(`wrangler.jsonc` 의 `env.server`)에서만 실제로 응답한다.
 */

import { filenameFromDisposition, outputNameFor } from './download';

export interface AppConfig {
  max_upload_bytes: number;
  max_file_count: number;
  allowed_suffixes: string[];
  output_suffix: string;
}

export interface Converted {
  blob: Blob;
  filename: string;
  requestId: string | null;
  templateVersion: string | null;
}

/** 서버가 돌려준 오류. 요청 ID 를 그대로 화면에 보여 준다. */
export class ConvertError extends Error {
  readonly code: string;
  readonly requestId: string | null;

  constructor(message: string, code: string, requestId: string | null) {
    super(message);
    this.name = 'ConvertError';
    this.code = code;
    this.requestId = requestId;
  }
}

const DEFAULT_MESSAGE = '변환에 실패했습니다. 잠시 후 다시 시도하십시오.';

/**
 * 브라우저 1차 검사에 쓰는 상한. `web/src/limits.py` 와 같은 값이며
 * 어긋나면 `web/tests/test_api.py` 가 잡는다.
 *
 * 예전에는 `GET /api/v1/config` 로 받아 왔지만, 그러면 화면을 여는 것만으로
 * Worker 가 깨어나 무료 계정의 CPU·요청 한도를 쓴다. 값은 배포와 함께
 * 고정되므로 물어볼 이유가 없다. 판단은 어차피 파이썬이 다시 한다.
 */
export const APP_CONFIG: AppConfig = {
  max_upload_bytes: 10 * 1024 * 1024,
  max_file_count: 1,
  allowed_suffixes: ['.xml'],
  output_suffix: '.xlsx',
};

async function readError(response: Response): Promise<ConvertError> {
  const requestId = response.headers.get('X-Request-Id');
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string; request_id?: string };
    };
    return new ConvertError(
      body.error?.message ?? DEFAULT_MESSAGE,
      body.error?.code ?? 'UNKNOWN',
      body.error?.request_id ?? requestId,
    );
  } catch {
    return new ConvertError(DEFAULT_MESSAGE, 'UNKNOWN', requestId);
  }
}

/** 대비책 경로. 브라우저 엔진을 못 띄웠을 때만 부른다. */
export async function convertOnServer(file: File, signal: AbortSignal): Promise<Converted> {
  const form = new FormData();
  form.append('file', file, file.name);

  const response = await fetch('/api/v1/convert', {
    method: 'POST',
    body: form,
    signal,
    // 같은 출처로만 보낸다. CORS 는 열려 있지 않다.
    credentials: 'same-origin',
  });

  if (!response.ok) throw await readError(response);

  return {
    blob: await response.blob(),
    filename: filenameFromDisposition(
      response.headers.get('Content-Disposition'),
      outputNameFor(file.name),
    ),
    requestId: response.headers.get('X-Request-Id'),
    templateVersion: response.headers.get('X-Template-Version'),
  };
}
