import { MAX_PDF_BYTES, MAX_PDF_PAGES, readPdf, savePdf, splitRanges, type PdfPageRef } from './pdf';

export function pdfTool(): HTMLElement {
  const tool = document.createElement('section');
  tool.className = 'conv-tool conv-pdf';
  tool.innerHTML = `
    <h2>PDF 편집기</h2>
    <p class="conv-note">여러 파일을 추가해 병합하거나, 쪽을 회전하고 순서를 바꿔 저장하세요. 합계 64MB · 1,000쪽까지 지원합니다.</p>
    <label class="conv-drop" for="conv-pdf-file">
      <input id="conv-pdf-file" type="file" accept=".pdf,application/pdf" multiple />
      <span>PDF 파일을 고르거나 여기에 끌어다 놓으세요 (여러 개 가능)</span>
    </label>
    <p class="conv-status" role="status" aria-live="polite"></p>
    <fieldset class="pdf-controls" disabled>
      <legend>쪽 편집</legend>
      <div class="conv-actions">
        <button type="button" data-action="all">전체 선택</button>
        <button type="button" data-action="none">선택 해제</button>
        <button type="button" data-action="rotate">선택 쪽 ↻ 90°</button>
        <button type="button" data-action="remove">선택 쪽 삭제</button>
        <button type="button" data-action="reset">초기화</button>
      </div>
      <p class="pdf-summary"></p>
      <ol class="pdf-pages" aria-label="저장할 쪽 순서"></ol>
      <div class="conv-actions">
        <button type="button" class="conv-download" data-action="save">전체 병합·저장</button>
        <button type="button" data-action="extract">선택 쪽만 저장</button>
      </div>
      <label for="pdf-ranges">분할 범위 (현재 목록의 쪽 번호 기준)</label>
      <div class="conv-actions">
        <input id="pdf-ranges" type="text" placeholder="예: 1-3; 4-6; 7,9" />
        <button type="button" data-action="split">범위별 분할</button>
      </div>
      <p class="conv-note">쉼표(,)로 쪽을 묶고 세미콜론(;)으로 파일을 나눕니다. 예: 1-3; 4,6 → PDF 2개.</p>
    </fieldset>
    <div class="pdf-outputs conv-actions" aria-label="저장 결과"></div>
    <p class="conv-note">쪽의 글·그림을 PDF로 복사합니다. 책갈피·양식·전자서명 보존은 지원하지 않습니다. 암호화된 PDF는 보안을 해제한 사본을 사용하세요.</p>
  `;
  const input = tool.querySelector<HTMLInputElement>('#conv-pdf-file')!;
  const drop = tool.querySelector<HTMLElement>('.conv-drop')!;
  const status = tool.querySelector<HTMLElement>('.conv-status')!;
  const controls = tool.querySelector<HTMLFieldSetElement>('.pdf-controls')!;
  const list = tool.querySelector<HTMLOListElement>('.pdf-pages')!;
  const summary = tool.querySelector<HTMLElement>('.pdf-summary')!;
  const ranges = tool.querySelector<HTMLInputElement>('#pdf-ranges')!;
  const outputs = tool.querySelector<HTMLElement>('.pdf-outputs')!;
  let pages: PdfPageRef[] = [];
  const selected = new Set<PdfPageRef>();
  let busy = false;
  let urls: string[] = [];
  const message = (text: string, error = false): void => {
    status.textContent = text;
    status.dataset['tone'] = error ? 'error' : '';
  };
  const clearOutputs = (): void => {
    urls.forEach(url => URL.revokeObjectURL(url));
    urls = [];
    outputs.replaceChildren();
  };
  const render = (): void => {
    controls.disabled = busy || !pages.length;
    input.disabled = busy;
    summary.textContent = `${pages.length}쪽 · ${selected.size}쪽 선택`;
    list.replaceChildren();
    pages.forEach((page, index) => {
      const row = document.createElement('li');
      const label = document.createElement('label');
      const check = document.createElement('input');
      check.type = 'checkbox';
      check.checked = selected.has(page);
      check.addEventListener('change', () => {
        if (check.checked) selected.add(page); else selected.delete(page);
        summary.textContent = `${pages.length}쪽 · ${selected.size}쪽 선택`;
      });
      const angle = ((page.source.document.getPage(page.index).getRotation().angle + page.rotation) % 360 + 360) % 360;
      label.append(check, document.createTextNode(`${index + 1}. ${page.source.name} · 원본 ${page.index + 1}쪽 · ${angle}°`));
      row.append(label);
      for (const [title, delta] of [['위로', -1], ['아래로', 1]] as const) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = title;
        button.setAttribute('aria-label', `${index + 1}쪽 ${title}`);
        button.disabled = index + delta < 0 || index + delta >= pages.length;
        button.addEventListener('click', () => {
          [pages[index], pages[index + delta]] = [pages[index + delta]!, page];
          clearOutputs();
          render();
          list.children[index + delta]?.querySelectorAll('button')[delta === -1 ? 0 : 1]?.focus();
        });
        row.append(button);
      }
      list.append(row);
    });
  };
  const run = async (work: () => Promise<void>): Promise<void> => {
    if (busy) return;
    busy = true;
    controls.disabled = true;
    input.disabled = true;
    try { await work(); }
    catch (error) { message(error instanceof Error ? error.message : String(error), true); }
    finally { busy = false; render(); }
  };
  const add = (files: File[]): void => {
    if (!files.length) return;
    void run(async () => {
      message('PDF 읽는 중…');
      let total = [...new Set(pages.map(page => page.source))].reduce((sum, source) => sum + source.size, 0);
      const added: PdfPageRef[] = [];
      for (const file of files) {
        total += file.size;
        if (total > MAX_PDF_BYTES) throw new Error('PDF는 합계 64MB까지 추가할 수 있습니다.');
        const source = await readPdf(new Uint8Array(await file.arrayBuffer()), file.name);
        if (pages.length + added.length + source.document.getPageCount() > MAX_PDF_PAGES) throw new Error('PDF는 합계 1,000쪽까지 추가할 수 있습니다.');
        source.document.getPageIndices().forEach(index => added.push({ source, index, rotation: 0 }));
      }
      pages.push(...added);
      clearOutputs();
      message(`${files.length}개 파일에서 ${added.length}쪽을 추가했습니다.`);
    });
  };
  input.addEventListener('change', () => { add(Array.from(input.files ?? [])); input.value = ''; });
  for (const type of ['dragenter', 'dragover'] as const) drop.addEventListener(type, event => {
    event.preventDefault();
    if (!busy) drop.dataset['over'] = 'yes';
  });
  drop.addEventListener('dragleave', () => delete drop.dataset['over']);
  drop.addEventListener('drop', event => {
    event.preventDefault();
    delete drop.dataset['over'];
    add(Array.from(event.dataTransfer?.files ?? []));
  });
  const exportGroups = async (groups: PdfPageRef[][], prefix: string): Promise<void> => {
    message('PDF 만드는 중…');
    clearOutputs();
    try {
      for (let i = 0; i < groups.length; i++) {
        const bytes = await savePdf(groups[i]!);
        const url = URL.createObjectURL(new Blob([new Uint8Array(bytes)], { type: 'application/pdf' }));
        urls.push(url);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${prefix}${groups.length > 1 ? `-${i + 1}` : ''}.pdf`;
        link.textContent = `${link.download} 내려받기 (${groups[i]!.length}쪽)`;
        outputs.append(link);
      }
      message(`${groups.length}개 PDF를 만들었습니다. 아래 링크를 눌러 내려받으세요.`);
    } catch (error) { clearOutputs(); throw error; }
  };
  controls.addEventListener('click', event => {
    const action = (event.target as HTMLElement).closest<HTMLButtonElement>('button[data-action]')?.dataset['action'];
    if (!action || busy) return;
    if (action === 'save') { void run(() => exportGroups([pages], 'edited')); return; }
    if (action === 'extract') {
      if (!selected.size) { message('저장할 쪽을 선택하세요.', true); return; }
      void run(() => exportGroups([pages.filter(page => selected.has(page))], 'selected')); return;
    }
    if (action === 'split') {
      void run(async () => {
        const groups = splitRanges(ranges.value, pages.length).map(group => group.map(index => pages[index]!));
        await exportGroups(groups, 'split');
      }); return;
    }
    if (action === 'all') pages.forEach(page => selected.add(page));
    if (action === 'none') selected.clear();
    if (action === 'rotate' || action === 'remove') {
      if (!selected.size) { message('편집할 쪽을 선택하세요.', true); return; }
      clearOutputs();
      if (action === 'rotate') selected.forEach(page => { page.rotation = (page.rotation + 90) % 360; });
      else { pages = pages.filter(page => !selected.has(page)); selected.clear(); }
    }
    if (action === 'reset') { pages = []; selected.clear(); ranges.value = ''; clearOutputs(); }
    message('');
    render();
  });
  render();
  return tool;
}
