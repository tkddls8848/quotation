import { describe, expect, it } from 'vitest';

import { filenameFromDisposition, outputNameFor } from './download';

describe('filenameFromDisposition', () => {
  it('RFC 5987 로 온 한글 이름을 되살린다', () => {
    const header =
      "attachment; filename=\"____.xlsx\"; filename*=UTF-8''%EA%B2%AC%EC%A0%81%EC%84%9C.xlsx";
    expect(filenameFromDisposition(header, 'fallback.xlsx')).toBe('견적서.xlsx');
  });

  it('공백·괄호·# 가 섞인 이름을 그대로 받는다', () => {
    const encoded = encodeURIComponent('견적 (수정본)#2.xlsx');
    const header = `attachment; filename="___2.xlsx"; filename*=UTF-8''${encoded}`;
    expect(filenameFromDisposition(header, 'fallback.xlsx')).toBe(
      '견적 (수정본)#2.xlsx',
    );
  });

  it('별표 없는 형식도 읽는다', () => {
    expect(
      filenameFromDisposition('attachment; filename="quote.xlsx"', 'fallback.xlsx'),
    ).toBe('quote.xlsx');
  });

  it('헤더가 없거나 깨졌으면 대비책 이름을 쓴다', () => {
    expect(filenameFromDisposition(null, 'fallback.xlsx')).toBe('fallback.xlsx');
    expect(filenameFromDisposition('attachment', 'fallback.xlsx')).toBe(
      'fallback.xlsx',
    );
    expect(
      filenameFromDisposition("attachment; filename*=UTF-8''%E0%A4%A", 'f.xlsx'),
    ).toBe('f.xlsx');
  });
});

describe('outputNameFor', () => {
  it('확장자만 바꾼다', () => {
    expect(outputNameFor('FS5045_260722.xml')).toBe('FS5045_260722.xlsx');
    expect(outputNameFor('점.이.여럿.xml')).toBe('점.이.여럿.xlsx');
  });

  it('경로를 떼어 낸다', () => {
    expect(outputNameFor('C:\\input\\견적.xml')).toBe('견적.xlsx');
    expect(outputNameFor('/tmp/a.xml')).toBe('a.xlsx');
  });

  it('이름이 없으면 기본값을 쓴다', () => {
    expect(outputNameFor('.xml')).toBe('quotation.xlsx');
  });
});
