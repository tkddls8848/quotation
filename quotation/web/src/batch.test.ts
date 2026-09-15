import { describe, expect, it } from 'vitest';

import { APP_CONFIG } from './contract';
import { progressLabel, rejectReason, selectFiles, summarize } from './batch';

const file = (name: string, size = 1024): File =>
  new File([new Uint8Array(size)], name, { type: 'text/xml' });

describe('selectFiles', () => {
  it('XML 만 받아들이고 나머지는 이유와 함께 거른다', () => {
    const { accepted, rejected } = selectFiles(
      [file('a.xml'), file('메모.txt'), file('b.XML')],
      APP_CONFIG,
    );
    expect(accepted.map((f) => f.name)).toEqual(['a.xml', 'b.XML']);
    expect(rejected).toEqual([
      { name: '메모.txt', reason: 'XML 화일만 변환할 수 있습니다.' },
    ]);
  });

  it('빈 화일과 너무 큰 화일을 거른다', () => {
    const { accepted, rejected } = selectFiles(
      [file('빈.xml', 0), file('큰.xml', APP_CONFIG.max_upload_bytes + 1), file('ok.xml')],
      APP_CONFIG,
    );
    expect(accepted.map((f) => f.name)).toEqual(['ok.xml']);
    expect(rejected.map((r) => r.name)).toEqual(['빈.xml', '큰.xml']);
    expect(rejected[1].reason).toContain('10 MiB');
  });

  it('같은 이름을 두 번 고르면 앞의 것만 남긴다', () => {
    // 결과 화일 이름이 같아 서로를 덮어쓰기 때문이다.
    const { accepted, rejected } = selectFiles([file('견적.xml'), file('견적.xml')], APP_CONFIG);
    expect(accepted).toHaveLength(1);
    expect(rejected[0].reason).toContain('두 번');
  });

  it('한 번에 받는 개수를 넘으면 넘친 것만 거른다', () => {
    const many = Array.from({ length: 4 }, (_, i) => file(`q${i}.xml`));
    const { accepted, rejected } = selectFiles(many, { ...APP_CONFIG, max_batch_files: 2 });
    expect(accepted.map((f) => f.name)).toEqual(['q0.xml', 'q1.xml']);
    expect(rejected).toHaveLength(2);
    expect(rejected[0].reason).toContain('2개');
  });

  it('한 개도 못 받아들이면 빈 목록을 돌려준다', () => {
    const { accepted, rejected } = selectFiles([file('a.pdf')], APP_CONFIG);
    expect(accepted).toEqual([]);
    expect(rejected).toHaveLength(1);
  });

  it('이미 대기 중인 화일과 이름이 겹치면 거른다', () => {
    const { accepted, rejected } = selectFiles(
      [file('견적.xml'), file('새.xml')],
      APP_CONFIG,
      [file('견적.xml')],
    );
    expect(accepted.map((f) => f.name)).toEqual(['새.xml']);
    expect(rejected[0].reason).toContain('두 번');
  });

  it('대기 중인 개수까지 합쳐서 한 번에 받는 개수를 셈한다', () => {
    const existing = Array.from({ length: 2 }, (_, i) => file(`e${i}.xml`));
    const incoming = Array.from({ length: 2 }, (_, i) => file(`q${i}.xml`));
    const { accepted, rejected } = selectFiles(incoming, { ...APP_CONFIG, max_batch_files: 3 }, existing);
    expect(accepted.map((f) => f.name)).toEqual(['q0.xml']);
    expect(rejected).toHaveLength(1);
    expect(rejected[0].reason).toContain('3개');
  });
});

describe('rejectReason', () => {
  it('받아들일 수 있으면 null', () => {
    expect(rejectReason(file('견적.xml'), APP_CONFIG)).toBeNull();
  });
});

describe('summarize', () => {
  it('한 개만 성공했을 때', () => {
    expect(summarize({ done: 1, failed: 0, total: 1, cancelled: false })).toBe(
      '견적서를 내려받았습니다.',
    );
  });

  it('여러 개 모두 성공했을 때', () => {
    expect(summarize({ done: 5, failed: 0, total: 5, cancelled: false })).toContain('5개를 모두');
  });

  it('일부 실패는 성공·실패 수를 함께 알린다', () => {
    const text = summarize({ done: 3, failed: 2, total: 5, cancelled: false });
    expect(text).toContain('3개');
    expect(text).toContain('2개');
  });

  it('모두 실패했을 때', () => {
    expect(summarize({ done: 0, failed: 4, total: 4, cancelled: false })).toContain('모두 실패');
  });

  it('취소하면 어디까지 받았는지 알린다', () => {
    expect(summarize({ done: 2, failed: 0, total: 5, cancelled: true })).toContain('2개까지');
    expect(summarize({ done: 0, failed: 0, total: 5, cancelled: true })).toBe(
      '변환을 취소했습니다.',
    );
  });
});

describe('progressLabel', () => {
  it('한 개일 때는 번호를 붙이지 않는다', () => {
    expect(progressLabel(0, 1, 'a.xml')).toBe('a.xml 변환 중…');
  });

  it('여러 개일 때는 몇 번째인지 알린다', () => {
    expect(progressLabel(2, 7, 'c.xml')).toBe('(3/7) c.xml 변환 중…');
  });
});
