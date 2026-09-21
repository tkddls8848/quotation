/**
 * sfnt(TrueType·OpenType) 테이블 손질.
 *
 * `@pdf-lib/fontkit` 은 GPOS 가 12바이트짜리 빈 껍데기인 글꼴에서 버퍼 끝을
 * 넘어 읽고 죽는다 — "Trying to access beyond buffer length". 나눔고딕·나눔명조·
 * 나눔손글씨·도현·주아·개구가 모두 그렇다. 한글 글꼴에서 드문 일이 아니라서
 * 그 글꼴들을 목록에서 빼는 것으로는 해결되지 않는다. 쓰는 사람이 제 컴퓨터의
 * 글꼴을 올릴 때 같은 일이 그대로 일어난다.
 *
 * 우리가 하는 일은 **글자를 그려 넣는 것** 뿐이다. 합자·커닝 같은 배치 테이블은
 * 쓰지 않는다. 그래서 심기 전에 떼어 낸다 — 고치는 것이 아니라 안 쓰는 것을
 * 버리는 것이라 글자 모양은 그대로다.
 */

/** 그리기에 쓰지 않는 배치·서명 테이블. 이것만 뗀다. */
const LAYOUT_TABLES = new Set(['GPOS', 'GSUB', 'GDEF', 'BASE', 'JSTF', 'MATH', 'DSIG', 'kern']);

/** OpenType 명세가 정한 마법수. head.checkSumAdjustment 를 다시 셀 때 쓴다. */
const CHECKSUM_MAGIC = 0xb1b0afba;

interface TableRecord { tag: string; checksum: number; offset: number; length: number }

/**
 * 배치 테이블을 떼고 sfnt 를 다시 짠다.
 *
 * 뗄 것이 없으면 받은 바이트를 그대로 돌려준다 — 멀쩡한 글꼴을 괜히 다시
 * 짜서 새 버그를 들일 이유가 없다.
 */
export function stripLayoutTables(bytes: Uint8Array): Uint8Array {
  const tables = readTables(bytes);
  const keep = tables.filter((table) => !LAYOUT_TABLES.has(table.tag.trim()));
  if (keep.length === tables.length) return bytes;
  if (!keep.length) throw new Error('글꼴에 남는 테이블이 없습니다.');
  return rebuild(bytes, keep);
}

/** 글꼴 갈래 확인 — 못 쓰는 것은 심기 전에 이름을 대고 멈춘다. */
export function readTables(bytes: Uint8Array): TableRecord[] {
  if (bytes.length < 12) throw new Error('글꼴 파일이 너무 짧습니다.');
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const tag = String.fromCharCode(...bytes.subarray(0, 4));
  // WOFF 는 압축 포장이고 ttcf 는 글꼴 여럿을 담은 묶음이다. 둘 다 그대로는 못 심는다.
  if (tag === 'wOFF' || tag === 'wOF2') throw new Error('WOFF 글꼴은 심을 수 없습니다. TTF 또는 OTF 파일을 올려 주세요.');
  if (tag === 'ttcf') throw new Error('글꼴 묶음(.ttc)은 심을 수 없습니다. 낱개 TTF 또는 OTF 를 올려 주세요.');
  const version = view.getUint32(0);
  if (version !== 0x00010000 && tag !== 'OTTO' && tag !== 'true' && tag !== 'typ1') {
    throw new Error('TrueType·OpenType 글꼴이 아닙니다.');
  }

  const count = view.getUint16(4);
  if (!count || 12 + count * 16 > bytes.length) throw new Error('글꼴의 테이블 목록이 깨졌습니다.');
  const tables: TableRecord[] = [];
  for (let i = 0; i < count; i++) {
    const at = 12 + i * 16;
    const offset = view.getUint32(at + 8);
    const length = view.getUint32(at + 12);
    // 목록이 파일 밖을 가리키면 여기서 멈춘다. 그대로 심으면 fontkit 이 죽는다.
    if (offset + length > bytes.length) throw new Error('글꼴의 테이블이 파일 끝을 넘어갑니다.');
    tables.push({ tag: String.fromCharCode(...bytes.subarray(at, at + 4)), checksum: view.getUint32(at + 4), offset, length });
  }
  return tables;
}

function rebuild(source: Uint8Array, keep: TableRecord[]): Uint8Array {
  const pad = (n: number): number => (n + 3) & ~3;
  const directory = 12 + keep.length * 16;
  const out = new Uint8Array(directory + keep.reduce((sum, table) => sum + pad(table.length), 0));
  const view = new DataView(out.buffer);

  out.set(source.subarray(0, 4));
  view.setUint16(4, keep.length);
  // searchRange·entrySelector·rangeShift. 읽는 쪽은 대개 무시하지만 명세는 값을 정해 두었다.
  const selector = Math.floor(Math.log2(keep.length));
  const range = 2 ** selector * 16;
  view.setUint16(6, range);
  view.setUint16(8, selector);
  view.setUint16(10, keep.length * 16 - range);

  let at = directory;
  let head = -1;
  keep.forEach((table, index) => {
    const record = 12 + index * 16;
    for (let c = 0; c < 4; c++) out[record + c] = table.tag.charCodeAt(c);
    view.setUint32(record + 4, table.checksum);
    view.setUint32(record + 8, at);
    view.setUint32(record + 12, table.length);
    out.set(source.subarray(table.offset, table.offset + table.length), at);
    if (table.tag === 'head') head = at;
    at += pad(table.length);
  });

  // head.checkSumAdjustment 는 **파일 전체**의 합에서 나온다. 테이블을 옮겼으니
  // 예전 값은 더 이상 맞지 않는다. 그대로 두면 검사하는 도구가 깨진 글꼴로 본다.
  if (head >= 0 && head + 12 <= out.length) {
    view.setUint32(head + 8, 0);
    view.setUint32(head + 8, (CHECKSUM_MAGIC - sum32(view)) >>> 0);
  }
  return out;
}

/** sfnt 검사합 — 4바이트씩 더해 32비트로 감는다. */
function sum32(view: DataView): number {
  let total = 0;
  for (let at = 0; at + 4 <= view.byteLength; at += 4) total = (total + view.getUint32(at)) >>> 0;
  return total;
}
