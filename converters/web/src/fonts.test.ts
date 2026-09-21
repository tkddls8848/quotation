/**
 * 받아 온 글꼴을 **한 종도 빼지 않고** 실제로 심어 본다.
 *
 * 화면 검사는 글꼴 하나를 눌러 볼 뿐이다. 목록의 다른 글꼴이 조용히 깨지면
 * 화면은 멀쩡한데 저장한 파일에서만 글자가 빠진다 — 그 일이 일어나는 자리가
 * 여기다(`@pdf-lib/fontkit` 의 배치 테이블 버그, sfnt.ts 참고).
 *
 * 글꼴은 저장소에 없다(web/scripts/fetch_fonts.py 가 받는다). 받아 두지 않은
 * 곳에서는 건너뛴다 — 없는 것을 두고 붉히면 아무도 검사를 믿지 않는다. CI 는
 * 배포와 같은 방법으로 먼저 받아 두므로 거기서는 반드시 돈다.
 */
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import fontkit from '@pdf-lib/fontkit';
import { PDFDocument, StandardFonts } from 'pdf-lib';
import { describe, expect, it } from 'vitest';

import { readTables, stripLayoutTables } from './sfnt';

const DIR = new URL('../../../web/public/fonts/', import.meta.url);
const at = (name: string): string => fileURLToPath(new URL(name, DIR));
const CATALOG = at('fonts.json');
const SAMPLE = '고친 글자 가나다라 힣 ABC 0123';

interface Entry { id: string; label: string; group: string; file: string; bytes: number; license: string }

const fonts: Entry[] = existsSync(CATALOG) ? JSON.parse(readFileSync(CATALOG, 'utf-8')) : [];

describe.skipIf(!fonts.length)('받아 온 글꼴', () => {
  it('목록이 비어 있지 않다', () => {
    expect(fonts.length).toBeGreaterThan(0);
  });

  it.each(fonts.map(font => [font.label, font] as const))('%s 를 심어 한글을 되읽는다', async (_label, font) => {
    const raw = new Uint8Array(readFileSync(at(font.file)));
    expect(raw.length).toBe(font.bytes);
    expect(() => readTables(raw)).not.toThrow();

    const document = await PDFDocument.create();
    document.registerFontkit(fontkit);
    // 배치 테이블을 떼지 않으면 나눔 계열이 바로 여기서 죽는다.
    const embedded = await document.embedFont(stripLayoutTables(raw), { subset: true });
    document.addPage([400, 200]).drawText(SAMPLE, { x: 20, y: 100, size: 16, font: embedded });
    const bytes = await document.save();

    // 서브셋이 깨지면 5.9MB 글꼴이 통째로 들어간다. 받는 사람이 그것을 떠안는다.
    expect(bytes.length).toBeLessThan(raw.length / 4);
    expect(await extract(bytes)).toBe(SAMPLE);
  }, 60_000);

  it.each(fonts.map(font => [font.label, font] as const))('%s 의 라이선스 고지가 함께 있다', (_label, font) => {
    // OFL 은 고지를 함께 배포할 것을 요구한다. 빠진 채로 나가지 않게 막는다.
    const notice = at(`${font.id}.LICENSE.txt`);
    expect(existsSync(notice), `${font.id}.LICENSE.txt 가 없습니다`).toBe(true);
    expect(readFileSync(notice, 'utf-8')).toMatch(/OFL-1\.1\.txt/);
    expect(existsSync(at('OFL-1.1.txt'))).toBe(true);
  });
});

describe('PDF 기본 글꼴', () => {
  it('한글을 조용히 삼키지 않는다', async () => {
    // 물음표나 빈칸을 찍고 성공이라 말하는 것이 가장 나쁘다.
    const document = await PDFDocument.create();
    const helvetica = await document.embedFont(StandardFonts.Helvetica);
    expect(() => helvetica.widthOfTextAtSize('한글', 12)).toThrow(/encode/i);
  });
});

/** 저장한 PDF 에서 글자를 도로 뽑는다. 그림이 아니라 글자로 들어갔다는 증거다. */
async function extract(bytes: Uint8Array): Promise<string> {
  const pdfjs = await import('pdfjs-dist/legacy/build/pdf.mjs');
  // 닫는 것은 여는 일(task) 쪽이다. 문서(proxy)에는 destroy 가 없다.
  const task = pdfjs.getDocument({ data: new Uint8Array(bytes), useSystemFonts: false });
  try {
    const content = await (await (await task.promise).getPage(1)).getTextContent();
    return content.items.map(item => ('str' in item ? item.str : '')).join('').replace(/\s+/g, ' ').trim();
  } finally { await task.destroy(); }
}
