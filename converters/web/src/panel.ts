/**
 * 변환기 탭.
 *
 * HWPX 읽기와 PDF 쪽 편집.
 * PDF/HWPX 처리는 브라우저에서, HWP→PDF는 별도 변환 서버에서 실행한다.
 *
 * 화면에 "안 되는 것"까지 적는 이유는 이 도구의 신뢰가 거기서 갈리기 때문이다.
 * 한글 문서를 100% 그대로 옮겨 준다고 믿고 규격서를 맡겼다가 표 한 줄이 조용히
 * 빠지면, 그 뒤로는 아무것도 믿을 수 없게 된다.
 */
import './converters.css';

import { hwpxToMarkdown, type HwpxResult } from './hwpx';
import { pdfTool } from './pdf-panel';
import { hwpPdfTool } from './hwp-pdf-panel';

const MAX_BYTES = 64 * 1024 * 1024;

export function mountConverters(root: HTMLElement): void {
  root.innerHTML = '';
  root.append(header(), pdfTool(), hwpPdfTool(), hwpxTool());
}

function header(): HTMLElement {
  const section = document.createElement('section');
  section.className = 'conv-intro';
  section.innerHTML = `
    <h1>문서 변환기</h1>
    <p>
      PDF 편집·HWPX 생성·읽기는 <strong>브라우저 안에서</strong> 처리합니다.
      HWP → PDF만 파일을 변환 서버로 전송하며, 전송 전에 확인합니다.
    </p>
  `;
  return section;
}

// --- HWPX → Markdown --------------------------------------------------------

function hwpxTool(): HTMLElement {
  const tool = document.createElement('section');
  tool.className = 'conv-tool';
  tool.innerHTML = `
    <h2>HWPX → Markdown</h2>
    <p class="conv-note">
      글의 순서와 표의 칸 구조(병합 포함)를 그대로 옮깁니다.
      글꼴·색·쪽 배치는 옮기지 않습니다 — 그것은 내용이 아니라 꾸밈입니다.
    </p>
    <label class="conv-drop" for="conv-hwpx-file">
      <input id="conv-hwpx-file" type="file" accept=".hwpx,application/hwp+zip" />
      <span>HWPX 파일을 고르거나 여기에 끌어다 놓으세요</span>
    </label>
    <p class="conv-status" role="status" aria-live="polite"></p>
    <div class="conv-result" hidden>
      <div class="conv-stats"></div>
      <div class="conv-actions">
        <button type="button" class="conv-download">Markdown 내려받기</button>
        <span class="conv-filename"></span>
      </div>
      <pre class="conv-preview"></pre>
    </div>
  `;

  const input = tool.querySelector<HTMLInputElement>('#conv-hwpx-file')!;
  const drop = tool.querySelector<HTMLLabelElement>('.conv-drop')!;
  const status = tool.querySelector<HTMLParagraphElement>('.conv-status')!;
  const result = tool.querySelector<HTMLDivElement>('.conv-result')!;
  const stats = tool.querySelector<HTMLDivElement>('.conv-stats')!;
  const preview = tool.querySelector<HTMLPreElement>('.conv-preview')!;
  const download = tool.querySelector<HTMLButtonElement>('.conv-download')!;
  const filename = tool.querySelector<HTMLSpanElement>('.conv-filename')!;

  let markdown = '';
  let name = 'document.md';

  const fail = (message: string): void => {
    status.textContent = message;
    status.dataset['tone'] = 'error';
    result.hidden = true;
  };

  const run = async (file: File): Promise<void> => {
    status.dataset['tone'] = '';
    // .hwp(5.0 바이너리)는 ZIP 이 아니라 OLE 복합 문서다. 브라우저에서 확실하게
    // 읽을 방법이 없어서 시도하지 않고, 무엇을 하면 되는지 알려 준다.
    if (/\.hwp$/i.test(file.name)) {
      fail('.hwp 는 브라우저에서 열 수 없습니다. 한글이 설치된 PC에서 converters/desktop/hwp-to-hwpx.ps1 로 HWPX 로 바꾼 뒤 올려 주세요.');
      return;
    }
    if (file.size > MAX_BYTES) {
      fail(`파일이 너무 큽니다(${mb(file.size)}). ${mb(MAX_BYTES)}까지 읽습니다.`);
      return;
    }

    status.textContent = `${file.name} 읽는 중…`;
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const converted: HwpxResult = await hwpxToMarkdown(bytes);
      markdown = converted.markdown;
      name = `${file.name.replace(/\.hwpx$/i, '')}.md`;

      stats.textContent = describe(converted);
      preview.textContent = markdown.slice(0, 4000) + (markdown.length > 4000 ? '\n…' : '');
      filename.textContent = name;
      result.hidden = false;
      status.textContent = `${file.name} 변환 완료`;
      status.dataset['tone'] = 'ok';
    } catch (error) {
      fail(`읽지 못했습니다: ${error instanceof Error ? error.message : String(error)}`);
    }
  };

  input.addEventListener('change', () => {
    const file = input.files?.[0];
    if (file) void run(file);
  });

  for (const type of ['dragenter', 'dragover'] as const) {
    drop.addEventListener(type, (event) => {
      event.preventDefault();
      drop.dataset['over'] = 'yes';
    });
  }
  for (const type of ['dragleave', 'drop'] as const) {
    drop.addEventListener(type, () => delete drop.dataset['over']);
  }
  drop.addEventListener('drop', (event) => {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (file) void run(file);
  });

  download.addEventListener('click', () => {
    if (!markdown) return;
    const url = URL.createObjectURL(new Blob([markdown], { type: 'text/markdown;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    link.click();
    // 즉시 거두면 사파리에서 저장이 취소된다. 한 틱 뒤에 놓아 준다.
    setTimeout(() => URL.revokeObjectURL(url), 0);
  });

  return tool;
}

function describe({ stats }: HwpxResult): string {
  const parts = [`구역 ${stats.sections}개`, `표 ${stats.tables}개`];
  if (stats.tables) parts.push(`행 ${stats.rows}개`, `칸 ${stats.cells}개`);
  if (stats.bullets) parts.push(`글머리표 ${stats.bullets}개`);
  return parts.join(' · ');
}

function mb(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}
