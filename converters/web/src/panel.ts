/**
 * 변환기 탭.
 *
 * PDF 쪽 편집, 이미지 ↔ PDF, HWPX 짓기와 읽기, 인코딩 변환, ZIP.
 * **전부 브라우저 안에서 끝난다** — 고른 파일은 이 컴퓨터를 벗어나지 않는다
 * (결정 0018).
 *
 * 여섯을 한 화면에 늘어놓지 않는다. 먼저 **무엇을 변환할지 고르게 하고**, 고른
 * 것 하나만 아래에 세운다. 이유는 둘이다.
 *
 *   - 쓰는 사람은 한 번에 한 가지를 한다. 나머지 다섯의 한도·주의사항까지
 *     읽어 가며 제 자리를 찾을 이유가 없다
 *   - 도구마다 고정된 id(`#conv-pdf-file`, `#pdf-ranges` …)를 쓴다. 한 번에
 *     하나만 붙어 있으면 그 id 가 화면에서 언제나 하나다
 *
 * 고른 도구는 **처음 고를 때 한 번** 만들고 그대로 들고 있는다. 다른 것을
 * 보다 돌아와도 올려 둔 파일과 고쳐 둔 설정이 그대로다 — 떼었다 붙일 뿐
 * 다시 만들지 않기 때문이다.
 *
 * 화면에 "안 되는 것"까지 적는 이유는 이 도구의 신뢰가 거기서 갈리기 때문이다.
 * 한글 문서를 100% 그대로 옮겨 준다고 믿고 규격서를 맡겼다가 표 한 줄이 조용히
 * 빠지면, 그 뒤로는 아무것도 믿을 수 없게 된다.
 */
import './converters.css';

import { reason } from './errors';
import { encodingTool } from './encoding-panel';
import { hwpxToMarkdown, type HwpxResult } from './hwpx';
import { imagesPdfTool } from './images-pdf-panel';
import { pdfEditTool } from './pdf-edit-panel';
import { pdfTool } from './pdf-panel';
import { textHwpxTool } from './text-hwpx-panel';
import { zipTool } from './zip-panel';
import { documentTool, spreadsheetTool } from './format-panel';

const MAX_BYTES = 64 * 1024 * 1024;

/** 고를 수 있는 변환. `id` 는 화면에서 그 단추를 찾는 이름이라 바뀌면 안 된다. */
interface Choice {
  id: string;
  title: string;
  /** 한 줄로 "이걸 고르면 무엇을 하는가". 한도와 주의는 고른 뒤 도구가 적는다. */
  summary: string;
  build: () => HTMLElement;
}

// 이름은 고른 뒤 열리는 도구의 제목과 **같은 글자**다. 고르고 나서 "내가 이걸
// 골랐나" 를 되짚게 만들지 않기 위함이다.
const CHOICES: Choice[] = [
  { id: 'document', title: '문서·전자책 변환', summary: 'DOCX·ODT·PDF·EPUB 등의 본문을 10가지 형식으로', build: documentTool },
  { id: 'spreadsheet', title: '스프레드시트 변환', summary: 'Excel·ODS·CSV·JSON 등, 여러 시트도 한 번에', build: spreadsheetTool },
  { id: 'pdf', title: 'PDF 편집기', summary: '병합·쪽 삭제·회전·분할, HWPX·이미지로 저장', build: pdfTool },
  { id: 'pdf-edit', title: 'PDF 글자 고치기', summary: '쪽 위의 글자를 눌러 원하는 글꼴·크기로 바꾼다', build: pdfEditTool },
  { id: 'images-pdf', title: '이미지 → PDF', summary: '사진·스캔 여러 장을 고른 순서대로 한 PDF 로', build: imagesPdfTool },
  { id: 'text-hwpx', title: '텍스트·Markdown → HWPX', summary: '붙여 넣은 글과 표를 한글에서 열리는 문서로', build: textHwpxTool },
  { id: 'hwpx-markdown', title: 'HWPX → Markdown', summary: '한글 문서의 글 순서와 표 구조를 그대로 옮긴다', build: hwpxTool },
  { id: 'encoding', title: '인코딩 변환 (CSV·텍스트)', summary: 'CP949 ↔ UTF-8, BOM 과 줄바꿈까지 맞춘다', build: encodingTool },
  { id: 'zip', title: 'ZIP 묶기·풀기', summary: '윈도우가 만든 ZIP 의 한글 이름도 그대로 읽는다', build: zipTool },
];

export function mountConverters(root: HTMLElement): void {
  root.innerHTML = '';

  const stage = document.createElement('div');
  stage.className = 'conv-stage';
  stage.id = 'conv-stage';
  stage.append(placeholder());

  // 만든 도구는 버리지 않고 들고 있는다. 떼었다 붙여도 안에 든 것이 남는다.
  const built = new Map<string, HTMLElement>();
  const buttons = new Map<string, HTMLButtonElement>();

  const chooser = document.createElement('nav');
  chooser.className = 'conv-choices';
  chooser.setAttribute('aria-label', '변환 고르기');

  const select = (choice: Choice): void => {
    for (const [id, button] of buttons) button.setAttribute('aria-pressed', String(id === choice.id));
    let tool = built.get(choice.id);
    if (!tool) {
      tool = choice.build();
      built.set(choice.id, tool);
    }
    stage.replaceChildren(tool);
  };

  for (const choice of CHOICES) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'conv-choice';
    button.dataset['choice'] = choice.id;
    button.setAttribute('aria-pressed', 'false');
    button.setAttribute('aria-controls', stage.id);

    const title = document.createElement('span');
    title.className = 'conv-choice__title';
    title.textContent = choice.title;
    const summary = document.createElement('span');
    summary.className = 'conv-choice__summary';
    summary.textContent = choice.summary;
    button.append(title, summary);

    button.addEventListener('click', () => select(choice));
    buttons.set(choice.id, button);
    chooser.append(button);
  }

  root.append(header(), chooser, stage);
}

/** 아직 아무것도 고르지 않았을 때. 빈 칸만 두면 고장으로 보인다. */
function placeholder(): HTMLElement {
  const empty = document.createElement('p');
  empty.className = 'conv-empty';
  empty.textContent = '위에서 하려는 변환을 고르세요. 고른 것만 여기에 열립니다.';
  return empty;
}

function header(): HTMLElement {
  const section = document.createElement('section');
  section.className = 'conv-intro';
  section.innerHTML = `
    <h1>문서 변환기</h1>
    <p>
      <strong>고른 파일은 이 컴퓨터를 벗어나지 않습니다.</strong>
      모든 변환이 브라우저 안에서 끝나며, 어디로도 올려 보내지 않습니다.
    </p>
    <p>
      <code>.hwp</code>(한글 5.0 바이너리)는 ZIP 이 아니라 OLE 복합 문서라 브라우저에서 열지 못합니다.
      한글이 설치된 PC 에서 <code>converters/desktop/hwp-to-hwpx.ps1</code> 로 HWPX 로 바꾼 뒤 올려 주세요.
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
      fail(`읽지 못했습니다: ${reason(error)}`);
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
