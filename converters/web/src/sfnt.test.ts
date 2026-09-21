import { describe, expect, it } from 'vitest';

import { readTables, stripLayoutTables } from './sfnt';

/** 시험용 sfnt 한 벌. 테이블 이름과 내용만 맞으면 된다 — 글리프는 보지 않는다. */
function buildFont(tables: [string, Uint8Array][]): Uint8Array {
  const pad = (n: number): number => (n + 3) & ~3;
  const directory = 12 + tables.length * 16;
  const out = new Uint8Array(directory + tables.reduce((sum, [, body]) => sum + pad(body.length), 0));
  const view = new DataView(out.buffer);
  view.setUint32(0, 0x00010000);
  view.setUint16(4, tables.length);
  let at = directory;
  tables.forEach(([tag, body], index) => {
    const record = 12 + index * 16;
    for (let c = 0; c < 4; c++) out[record + c] = tag.charCodeAt(c);
    view.setUint32(record + 4, 0);
    view.setUint32(record + 8, at);
    view.setUint32(record + 12, body.length);
    out.set(body, at);
    at += pad(body.length);
  });
  return out;
}

const body = (text: string): Uint8Array => new TextEncoder().encode(text);
/** head 는 54바이트다. checkSumAdjustment 가 8번째 바이트에 있다. */
const head = (): Uint8Array => new Uint8Array(54);

describe('sfnt 테이블 손질', () => {
  it('배치 테이블을 떼고 나머지는 그대로 둔다', () => {
    const font = buildFont([['GPOS', body('xx')], ['cmap', body('cmap-내용')], ['glyf', body('glyf-내용')], ['head', head()]]);
    const stripped = stripLayoutTables(font);

    const tags = readTables(stripped).map(table => table.tag);
    expect(tags).not.toContain('GPOS');
    expect(tags.sort()).toEqual(['cmap', 'glyf', 'head']);
  });

  it('뗀 뒤에도 남은 테이블의 내용이 바뀌지 않는다', () => {
    const font = buildFont([['GSUB', body('버릴 것')], ['cmap', body('지킬 내용')], ['head', head()]]);
    const stripped = stripLayoutTables(font);

    const cmap = readTables(stripped).find(table => table.tag === 'cmap')!;
    expect(new TextDecoder().decode(stripped.subarray(cmap.offset, cmap.offset + cmap.length))).toBe('지킬 내용');
  });

  it('뗄 것이 없으면 받은 바이트를 그대로 돌려준다', () => {
    // 멀쩡한 글꼴을 괜히 다시 짜지 않는다 — 다시 짜는 것 자체가 위험이다.
    const font = buildFont([['cmap', body('가')], ['glyf', body('나')], ['head', head()]]);
    expect(stripLayoutTables(font)).toBe(font);
  });

  it('GPOS·GSUB·GDEF·kern·DSIG 를 모두 뗀다', () => {
    const font = buildFont([
      ['GPOS', body('1')], ['GSUB', body('2')], ['GDEF', body('3')],
      ['kern', body('4')], ['DSIG', body('5')], ['BASE', body('6')],
      ['cmap', body('7')], ['head', head()],
    ]);
    expect(readTables(stripLayoutTables(font)).map(table => table.tag).sort()).toEqual(['cmap', 'head']);
  });

  it('head 의 checkSumAdjustment 를 다시 센다', () => {
    // 테이블을 옮겼으니 예전 값은 맞지 않는다. 그대로 두면 깨진 글꼴로 읽힌다.
    const font = buildFont([['GPOS', body('xx')], ['cmap', body('가')], ['head', head()]]);
    const stripped = stripLayoutTables(font);
    const record = readTables(stripped).find(table => table.tag === 'head')!;
    const view = new DataView(stripped.buffer, stripped.byteOffset, stripped.byteLength);
    const stored = view.getUint32(record.offset + 8);

    view.setUint32(record.offset + 8, 0);
    let sum = 0;
    for (let at = 0; at + 4 <= view.byteLength; at += 4) sum = (sum + view.getUint32(at)) >>> 0;
    expect(stored).toBe((0xb1b0afba - sum) >>> 0);
  });

  it('WOFF·글꼴 묶음·엉뚱한 파일은 이름을 대고 멈춘다', () => {
    const woff = new Uint8Array(16);
    woff.set(new TextEncoder().encode('wOFF'));
    expect(() => stripLayoutTables(woff)).toThrow(/WOFF/);

    const collection = new Uint8Array(16);
    collection.set(new TextEncoder().encode('ttcf'));
    expect(() => stripLayoutTables(collection)).toThrow(/묶음/);

    expect(() => stripLayoutTables(new TextEncoder().encode('이건 글꼴이 아니다'))).toThrow(/TrueType/);
    expect(() => stripLayoutTables(new Uint8Array(4))).toThrow(/짧습니다/);
  });

  it('목록이 파일 밖을 가리키면 심기 전에 멈춘다', () => {
    // 그대로 fontkit 에 넘기면 "Trying to access beyond buffer length" 로 죽는다.
    const font = buildFont([['cmap', body('가')], ['head', head()]]);
    new DataView(font.buffer).setUint32(12 + 12, 9999);
    expect(() => readTables(font)).toThrow(/파일 끝/);
  });
});
