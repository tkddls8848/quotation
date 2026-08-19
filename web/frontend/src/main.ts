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
import { Tally, progressLabel, selectFiles, summarize } from './batch';
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
const maxBatch = el<HTMLElement>('max-batch');
const queue = el<HTMLUListElement>('queue');
const modeInputs = Array.from(
  form.querySelectorAll<HTMLInputElement>('input[name="mode"]'),
);

const config: AppConfig = APP_CONFIG;
const converter = new Converter();
let chosen: File[] = [];
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
  submit.disabled = busy || chosen.length === 0;
  cancel.hidden = !busy;
  dropzone.setAttribute('aria-disabled', String(busy));
  // 변환 도중에 모드를 바꾸면 같은 묶음의 결과가 갈린다.
  for (const input of modeInputs) input.disabled = busy;
  document.body.classList.toggle('is-busy', busy);
}

/** 고른 변환 모드. 아무것도 안 잡히면 파이썬 기본값(UNIX)에 맡긴다. */
function currentMode(): string {
  return modeInputs.find((input) => input.checked)?.value ?? '';
}

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < MiB) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / MiB).toFixed(1)} MiB`;
}

// --- 파일 선택 ---------------------------------------------------------------

/** 대기 목록 한 줄. 변환이 진행되면 이 줄의 상태만 바꾼다. */
function queueRow(index: number): HTMLElement {
  return queue.children[index] as HTMLElement;
}

function setRowState(index: number, state: string, text: string): void {
  const row = queueRow(index);
  if (!row) return;
  row.dataset.state = state;
  (row.querySelector('.queue__state') as HTMLElement).textContent = text;
}

function drawQueue(files: readonly File[]): void {
  queue.replaceChildren();
  for (const file of files) {
    const row = document.createElement('li');
    row.className = 'queue__item';
    row.dataset.state = 'waiting';

    const name = document.createElement('span');
    name.className = 'queue__name';
    name.textContent = file.name;

    const size = document.createElement('span');
    size.className = 'queue__size';
    size.textContent = humanSize(file.size);

    const state = document.createElement('span');
    state.className = 'queue__state';
    state.textContent = '대기';

    row.append(name, size, state);
    queue.append(row);
  }
  queue.hidden = files.length === 0;
}

function choose(files: readonly File[]): void {
  clearError();
  setStatus('');

  const { accepted, rejected } = selectFiles(files, config);
  chosen = accepted;
  drawQueue(accepted);

  selected.hidden = accepted.length === 0;
  selected.textContent =
    accepted.length === 1
      ? '화일 1개'
      : `화일 ${accepted.length}개 · 합계 ${humanSize(
          accepted.reduce((sum, f) => sum + f.size, 0),
        )}`;
  submit.disabled = accepted.length === 0;

  if (rejected.length) {
    showError(
      rejected.map((r) => `${r.name} — ${r.reason}`).join('\n'),
      null,
    );
  }
  if (accepted.length) {
    setStatus('<변환 및 다운로드> 를 누르면 변환을 시작합니다.');
    // 고르는 동안 엔진을 미리 띄워 둔다. 누른 뒤 기다리는 시간이 줄어든다.
    converter.warmup();
  }
}

function pickFromInput(): void {
  choose(Array.from(fileInput.files ?? []));
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
  // 드롭한 화일을 입력 요소에도 반영해 두면 폼 상태가 화면과 어긋나지 않는다.
  fileInput.files = files;
  choose(Array.from(files));
});

// 키보드만으로도 화일을 고를 수 있어야 한다.
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

/** 한 건 변환하고 바로 내려 준다. 실패는 던지지 않고 이유를 돌려준다. */
async function convertOne(file: File, index: number, controller: AbortController,
                          mode: string): Promise<string | null> {
  setRowState(index, 'working', '변환 중');
  try {
    const result = await converter.convert(file, {
      signal: controller.signal,
      mode,
      onStage: (stage) =>
        setStatus(chosen.length === 1 ? stage : `(${index + 1}/${chosen.length}) ${stage}`),
    });
    saveBlob(result.blob, result.filename);
    showTemplateVersion(result.templateVersion);
    setRowState(index, 'done', '내려받음');
    return null;
  } catch (error) {
    if (controller.signal.aborted) throw error;
    const reason =
      error instanceof ConvertError
        ? error.message
        : '변환 엔진을 불러오지 못했습니다. 새로 고친 뒤 다시 시도하십시오.';
    setRowState(index, 'failed', '실패');
    return reason;
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (running || chosen.length === 0) return; // 중복 제출 방지

  const controller = new AbortController();
  const files = chosen;
  // 묶음 전체가 같은 모드로 돈다. 도중에 바뀌어도 흔들리지 않는다.
  const mode = currentMode();
  running = controller;
  setBusy(true);
  clearError();
  setStatus('변환을 준비하는 중…');

  const failures: string[] = [];
  const tally: Tally = { done: 0, failed: 0, total: files.length, cancelled: false };

  try {
    for (const [index, file] of files.entries()) {
      if (controller.signal.aborted) break;
      setStatus(progressLabel(index, files.length, file.name));

      const reason = await convertOne(file, index, controller, mode);
      if (reason === null) {
        tally.done += 1;
      } else {
        tally.failed += 1;
        failures.push(`${file.name} — ${reason}`);
      }
      // 브라우저가 연달아 내려받기를 삼키지 않도록 사이를 조금 둔다.
      if (index < files.length - 1) {
        await new Promise((done) => setTimeout(done, 150));
      }
    }
  } catch {
    // 취소로 빠져나온 경우다. 아래에서 함께 정리한다.
  } finally {
    tally.cancelled = controller.signal.aborted;
    for (let i = tally.done + tally.failed; i < files.length; i += 1) {
      setRowState(i, 'skipped', tally.cancelled ? '취소' : '건너뜀');
    }
    setStatus(summarize(tally));
    if (failures.length) showError(failures.join('\n'), null);
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
  maxBatch.textContent = String(config.max_batch_files);
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
