/**
 * 화면 배선 (계획서 §7).
 *
 * 규칙 몇 가지를 코드로 못박아 둔다.
 *   - 브라우저 1차 검사는 편의일 뿐이고 판단은 파이썬이 다시 한다
 *   - 진짜 진행률을 알 수 없다. 가짜 백분율 대신 단계만 보여 준다
 *   - 처리 중에는 중복 제출을 막고 AbortController 로 취소할 수 있게 한다
 *   - 화면을 여는 것만으로 서버를 깨우지 않는다. 상한도 판본도 배포와 함께
 *     정해지므로 물어볼 필요가 없다 (무료 계정의 요청·CPU 한도를 아낀다)
 */

import './styles.css';

import { APP_CONFIG, AppConfig, ConvertError } from './api';
import { Converter } from './converter';
import { saveBlob } from './download';

const MiB = 1024 * 1024;

const el = <T extends HTMLElement>(id: string): T => {
  const found = document.getElementById(id);
  if (!found) throw new Error(`요소를 찾지 못했습니다: #${id}`);
  return found as T;
};

const form = el<HTMLFormElement>('form');
const dropzone = el<HTMLDivElement>('dropzone');
const fileInput = el<HTMLInputElement>('file');
const selected = el<HTMLParagraphElement>('selected');
const submit = el<HTMLButtonElement>('submit');
const cancel = el<HTMLButtonElement>('cancel');
const status = el<HTMLParagraphElement>('status');
const errorBox = el<HTMLDivElement>('error');
const errorMessage = el<HTMLParagraphElement>('error-message');
const errorId = el<HTMLElement>('error-id');
const maxSize = el<HTMLElement>('max-size');

const config: AppConfig = APP_CONFIG;
const converter = new Converter();
let chosen: File | null = null;
let running: AbortController | null = null;

// --- 화면 상태 ---------------------------------------------------------------

function setStatus(text: string): void {
  status.textContent = text;
}

function showError(message: string, requestId: string | null): void {
  errorMessage.textContent = message;
  errorId.textContent = requestId ?? '(없음)';
  errorBox.hidden = false;
}

function clearError(): void {
  errorBox.hidden = true;
  errorMessage.textContent = '';
  errorId.textContent = '';
}

function setBusy(busy: boolean): void {
  submit.disabled = busy || chosen === null;
  cancel.hidden = !busy;
  dropzone.setAttribute('aria-disabled', String(busy));
  document.body.classList.toggle('is-busy', busy);
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < MiB) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / MiB).toFixed(1)} MiB`;
}

// --- 파일 선택 ---------------------------------------------------------------

function rejectReason(file: File): string | null {
  const name = file.name.toLowerCase();
  const allowed = config.allowed_suffixes.some((suffix) => name.endsWith(suffix));
  if (!allowed) return 'XML 화일만 변환할 수 있습니다.';
  if (file.size === 0) return '빈 화일입니다.';
  if (file.size > config.max_upload_bytes) {
    return `화일이 너무 큽니다. 최대 ${Math.floor(config.max_upload_bytes / MiB)} MiB 까지 올릴 수 있습니다.`;
  }
  return null;
}

function choose(file: File | null): void {
  clearError();
  setStatus('');

  if (!file) {
    chosen = null;
    selected.hidden = true;
    submit.disabled = true;
    return;
  }

  const reason = rejectReason(file);
  if (reason) {
    chosen = null;
    selected.hidden = true;
    submit.disabled = true;
    showError(reason, null);
    return;
  }

  chosen = file;
  selected.textContent = `${file.name} · ${humanSize(file.size)}`;
  selected.hidden = false;
  submit.disabled = false;
  setStatus('<변환 및 다운로드> 를 누르면 변환을 시작합니다.');
  // 고르는 동안 엔진을 미리 띄워 둔다. 누른 뒤 기다리는 시간이 줄어든다.
  converter.warmup();
}

function pickFromInput(): void {
  choose(fileInput.files?.[0] ?? null);
}

// --- 드래그앤드롭 ------------------------------------------------------------

for (const type of ['dragenter', 'dragover']) {
  dropzone.addEventListener(type, (event) => {
    event.preventDefault();
    if (running) return;
    dropzone.classList.add('is-over');
  });
}

for (const type of ['dragleave', 'dragend', 'drop']) {
  dropzone.addEventListener(type, () => dropzone.classList.remove('is-over'));
}

dropzone.addEventListener('drop', (event) => {
  event.preventDefault();
  if (running) return;
  const files = event.dataTransfer?.files;
  if (!files?.length) return;
  if (files.length > config.max_file_count) {
    showError('한 번에 한 개의 XML 화일만 변환합니다.', null);
    return;
  }
  // 드롭한 파일을 입력 요소에도 반영해 두면 폼 상태가 화면과 어긋나지 않는다.
  fileInput.files = files;
  choose(files[0]);
});

// 키보드만으로도 파일을 고를 수 있어야 한다.
dropzone.addEventListener('click', () => {
  if (!running) fileInput.click();
});
dropzone.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    if (!running) fileInput.click();
  }
});
fileInput.addEventListener('change', pickFromInput);

// --- 변환 --------------------------------------------------------------------

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (running || !chosen) return; // 중복 제출 방지

  const controller = new AbortController();
  running = controller;
  setBusy(true);
  clearError();
  setStatus('변환을 준비하는 중…');

  try {
    const result = await converter.convert(chosen, {
      signal: controller.signal,
      onStage: (stage) => setStatus(stage),
    });

    setStatus('다운로드 준비 완료');
    saveBlob(result.blob, result.filename);
    setStatus(`${result.filename} 을 내려받았습니다.`);
    showTemplateVersion(result.templateVersion);
  } catch (error) {
    if (controller.signal.aborted) {
      setStatus('변환을 취소했습니다.');
    } else if (error instanceof ConvertError) {
      setStatus('변환에 실패했습니다.');
      showError(error.message, error.requestId);
    } else {
      setStatus('변환에 실패했습니다.');
      showError('변환 엔진을 불러오지 못했습니다. 새로 고친 뒤 다시 시도하십시오.',
                null);
    }
  } finally {
    running = null;
    setBusy(false);
  }
});

cancel.addEventListener('click', () => {
  converter.cancel();
  running?.abort();
});

// --- 초기화 ------------------------------------------------------------------

function showTemplateVersion(version: string | null): void {
  if (version) el('template-version').textContent = version;
}

/**
 * 화면을 여는 데 필요한 것은 전부 이미 갖고 있다. 남은 것은 표시뿐이며
 * 그것도 정적 자산 한 개(`/py/engine.json`)를 읽는 것으로 끝난다.
 */
async function boot(): Promise<void> {
  maxSize.textContent = String(Math.floor(config.max_upload_bytes / MiB));
  el('deployment-version').textContent = __DEPLOYMENT_VERSION__;

  try {
    const response = await fetch('/py/engine.json');
    if (response.ok) {
      const manifest = (await response.json()) as {
        template?: { template_version?: string };
      };
      showTemplateVersion(manifest.template?.template_version ?? null);
    }
  } catch {
    // 운영 지원용 표시일 뿐이라 실패해도 화면은 그대로 쓴다.
  }
}

void boot();
