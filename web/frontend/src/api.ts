/** Worker API 호출 (계약은 doc 계획서 §6). */

import { filenameFromDisposition, outputNameFor } from './download';

export interface AppConfig {
  max_upload_bytes: number;
  max_file_count: number;
  allowed_suffixes: string[];
  output_suffix: string;
}

export interface AppStatus {
  deployment_version: string;
  template_version: string;
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

export const FALLBACK_CONFIG: AppConfig = {
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

export async function fetchConfig(signal?: AbortSignal): Promise<AppConfig> {
  const response = await fetch('/api/v1/config', { signal: signal ?? null });
  if (!response.ok) throw await readError(response);
  return (await response.json()) as AppConfig;
}

export async function fetchStatus(signal?: AbortSignal): Promise<AppStatus> {
  const response = await fetch('/api/v1/status', { signal: signal ?? null });
  if (!response.ok) throw await readError(response);
  return (await response.json()) as AppStatus;
}

export async function convert(file: File, signal: AbortSignal): Promise<Converted> {
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
