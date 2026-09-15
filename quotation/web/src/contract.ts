/**
 * 변환 계약 — 화면과 엔진이 주고받는 모양, 그리고 상한.
 *
 * 이름이 `api.ts` 였다. 서버 호출이 없어진 파일에 API 라는 이름을 두면
 * 다음 사람이 여기서 네트워크 코드를 찾는다.
 *
 * 예전에는 여기에 서버 호출(`POST /api/v1/convert`)이 있었다. 변환이 브라우저로
 * 들어오면서(결정 0002) 그것은 엔진을 못 띄웠을 때의 대비책으로만 남았고, 서버
 * 경로 자체가 없어지면서(결정 0010) 함께 지웠다. 이 파일에는 이제 네트워크를
 * 타는 코드가 없다.
 */

export interface AppConfig {
  /** 파일 한 개의 최대 크기. */
  max_upload_bytes: number;
  /** 한 번에 골라 변환할 수 있는 파일 수. 브라우저가 그만큼 되풀이한다. */
  max_batch_files: number;
  allowed_suffixes: string[];
}

export interface Converted {
  blob: Blob;
  filename: string;
  requestId: string | null;
  templateVersion: string | null;
}

/** 엔진이 돌려준 오류. 요청 ID 를 그대로 화면에 보여 준다. */
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

/**
 * 파일을 고를 때 화면이 하는 1차 검사 값. 진짜 판단은 엔진이 다시 한다 —
 * 같은 상한이 `quotation/rust/webapi/src/limits.rs` 에 있고 그쪽이 기준이다.
 *
 * 예전에는 `GET /api/v1/config` 로 받아 왔다. 그 요청은 서버 경로와 함께
 * 없어졌고(결정 0010), 값은 배포와 함께 고정되므로 물어볼 이유도 없다.
 */
export const APP_CONFIG: AppConfig = {
  max_upload_bytes: 10 * 1024 * 1024,
  max_batch_files: 50,
  allowed_suffixes: ['.xml'],
};
