/** `engine.js` 의 타입. 구현이 JavaScript 인 이유는 그 파일 머리말에 있다. */

export interface EngineManifest {
  pyodide_version: string;
  packages: Record<string, { file: string; sha256: string }>;
  core: { file: string; sha256: string; modules: string[] };
  /** 모드별(IBM/통합) 템플릿 판본. 실제로 쓰인 것은 변환 응답의 X-Template-Version 이 알려 준다. */
  template: Record<string, { name: string; sha256: string; version: string; size: number }>;
}

export interface EngineUpload {
  filename: string;
  content: Uint8Array;
  contentType?: string;
  deploymentVersion?: string;
}

/** 서버의 `POST /api/v1/convert` 응답과 같은 모양. */
export interface EngineResult {
  status: number;
  headers: Record<string, string>;
  body: Uint8Array;
  log: Record<string, string | number>;
}

export interface Engine {
  manifest: EngineManifest;
  today(): string;
  convert(upload: EngineUpload): EngineResult;
}

export interface EngineOptions {
  baseUrl: string;
  onStage?: (stage: string) => void;
  loadBinary?: (url: string) => Promise<Uint8Array>;
  loadJson?: (url: string) => Promise<unknown>;
  importModule?: (url: string) => Promise<{ loadPyodide: (o: unknown) => Promise<unknown> }>;
}

export declare const STAGES: Record<'runtime' | 'packages' | 'core' | 'ready', string>;
export declare function createEngine(options: EngineOptions): Promise<Engine>;
