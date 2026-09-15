const local = ['localhost', '127.0.0.1'].includes(location.hostname);
const API = (import.meta.env.VITE_HWP_API_URL as string | undefined)?.replace(/\/$/, '') ?? (local ? 'http://127.0.0.1:8788' : '');

export function hwpPdfTool(): HTMLElement {
  const tool = document.createElement('section');
  tool.className = 'conv-tool conv-hwp-pdf';
  tool.innerHTML = `
    <h2>HWP(5.0) → PDF</h2>
    <p class="conv-note">한글 프로그램 없이 변환합니다. 이 기능은 파일을 변환 서버로 전송합니다.
      글꼴·표·수식·쪽 배치가 원본과 달라질 수 있고, <strong>그림·글상자의 캡션 글자는 빠집니다.</strong>
      변환하지 못하는 문서는 실패로 알립니다 — 결과를 원본과 비교하세요.</p>
    <label class="conv-drop">HWP 파일 (최대 32MB)<input type="file" accept=".hwp,application/x-hwp" /></label>
    <label class="hwp-consent"><input type="checkbox" /> 이 파일을 변환 서버로 전송합니다. 원본은 처리 후 삭제되고 결과는 접수 후 최대 15분 보관됩니다.</label>
    <label class="hwp-key" hidden>서버 접근키 <input type="password" autocomplete="off" /></label>
    <div class="conv-actions"><button type="button" class="conv-download hwp-convert" disabled>PDF로 변환</button><button type="button" class="hwp-cancel" hidden>작업 취소·삭제</button><button type="button" class="hwp-retry">서버 연결 확인</button></div>
    <p class="conv-status" role="status" aria-live="polite"></p>
    <a class="hwp-result" hidden download="converted.pdf">PDF 내려받기</a>
  `;
  const file = tool.querySelector<HTMLInputElement>('input[type=file]')!;
  const consent = tool.querySelector<HTMLInputElement>('input[type=checkbox]')!;
  const keyLabel = tool.querySelector<HTMLElement>('.hwp-key')!;
  const key = tool.querySelector<HTMLInputElement>('input[type=password]')!;
  const convert = tool.querySelector<HTMLButtonElement>('.hwp-convert')!;
  const cancel = tool.querySelector<HTMLButtonElement>('.hwp-cancel')!;
  const retry = tool.querySelector<HTMLButtonElement>('.hwp-retry')!;
  const status = tool.querySelector<HTMLElement>('.conv-status')!;
  const result = tool.querySelector<HTMLAnchorElement>('.hwp-result')!;
  let ready = false, busy = false, url: string | undefined;
  let controller: AbortController | undefined;
  let job: { id: string; token: string } | undefined;
  let jobKey = '';
  const message = (text: string, error = false): void => { status.textContent = text; status.dataset['tone'] = error ? 'error' : ''; };
  const sync = (): void => { convert.disabled = !ready || busy || !consent.checked || !file.files?.length; file.disabled = busy; consent.disabled = busy; key.disabled = busy; retry.disabled = busy; };
  const clear = (): void => { result.hidden = true; if (url) URL.revokeObjectURL(url); url = undefined; };
  const auth = (): Record<string, string> => ({ 'X-Service-Key': jobKey, ...(job ? { Authorization: `Bearer ${job.token}` } : {}) });
  const request = async (path: string, init: RequestInit = {}): Promise<Response> => {
    const response = await fetch(API + path, { ...init, headers: { ...auth(), ...init.headers } });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { error?: string };
      throw new Error(payload.error ?? `서버 오류 (${response.status})`);
    }
    return response;
  };
  const check = async (): Promise<void> => {
    ready = false; sync();
    if (!API) { message('변환 서버가 연결되지 않았습니다. 서버 연결 설정 후 사용할 수 있습니다.'); return; }
    message('변환 서버 확인 중…');
    try {
      const response = await fetch(`${API}/health`, { signal: AbortSignal.timeout(10000) });
      if (!response.ok) throw new Error('서버 확인 실패');
      const health = await response.json() as { ready: boolean; requiresKey: boolean };
      ready = health.ready; keyLabel.hidden = !health.requiresKey;
      message(ready ? '변환 서버가 준비되었습니다.' : '서버의 변환 엔진이 준비되지 않았습니다.');
    } catch { message('변환 서버에 연결하지 못했습니다. 잠시 후 연결을 다시 확인하세요.', true); }
    sync();
  };
  file.addEventListener('change', () => { clear(); sync(); });
  consent.addEventListener('change', sync);
  retry.addEventListener('click', () => { void check(); });
  cancel.addEventListener('click', () => { controller?.abort(); });
  convert.addEventListener('click', () => {
    void (async () => {
      const input = file.files?.[0];
      if (!input || !consent.checked || busy || !ready) return;
      if (!/\.hwp$/i.test(input.name) || input.size > 32 * 1024 * 1024) { message('32MB 이하의 .hwp 파일을 선택하세요.', true); return; }
      busy = true; sync(); clear(); controller = new AbortController(); cancel.hidden = false; jobKey = key.value;
      try {
        if (job) { await request(`/jobs/${job.id}`, { method: 'DELETE', signal: AbortSignal.timeout(10000) }).catch(() => {}); job = undefined; }
        message('HWP 파일 전송 중…');
        // Keep the upload request alive to receive its job token even if cancel is clicked.
        // The newly created job can then be deleted reliably rather than left orphaned.
        const response = await request('/jobs', { method: 'POST', body: input, headers: { 'Content-Type': 'application/octet-stream' }, signal: AbortSignal.timeout(45000) });
        job = await response.json() as { id: string; token: string };
        const deadline = Date.now() + 300000;
        while (Date.now() < deadline) {
          controller.signal.throwIfAborted();
          const info = await (await request(`/jobs/${job.id}`, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(10000)]) })).json() as { state: string; message: string };
          if (info.state === 'done') {
            const pdf = await (await request(`/jobs/${job.id}/result`, { signal: AbortSignal.any([controller.signal, AbortSignal.timeout(30000)]) })).blob();
            controller.signal.throwIfAborted();
            url = URL.createObjectURL(pdf); result.href = url; result.download = input.name.replace(/\.hwp$/i, '') + '.pdf'; result.hidden = false;
            message('PDF 변환 완료. 내려받은 뒤 원본과 배치를 비교해 주세요.');
            // We now have the result locally, so delete the server copy early.
            await request(`/jobs/${job.id}`, { method: 'DELETE', signal: AbortSignal.timeout(10000) }).catch(() => {});
            job = undefined; return;
          }
          if (info.state === 'failed' || info.state === 'cancelled') throw new Error(info.message || '작업이 취소되었습니다.');
          message(info.state === 'queued' ? '변환 대기 중…' : 'PDF 변환 중…');
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
        throw new Error('대기 시간이 초과되었습니다. 다시 시도하세요.');
      } catch (error) {
        message(controller.signal.aborted ? '작업을 취소했습니다.' : (error instanceof Error ? error.message : String(error)), !controller.signal.aborted);
        if (job) await request(`/jobs/${job.id}`, { method: 'DELETE', signal: AbortSignal.timeout(10000) }).catch(() => {});
        job = undefined;
      } finally { busy = false; cancel.hidden = true; controller = undefined; sync(); }
    })();
  });
  void check();
  return tool;
}
