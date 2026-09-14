/**
 * 상품 고르기가 맞는지 대조한다.
 *
 * 이 목록은 차례가 전부다 — 이자를 잘못 세면 더 적게 주는 상품을 맨 위에 올려
 * 놓는다. 그래서 손으로 검산할 수 있는 값만 골라 맞춘다. 연 12% 를 쓰는 경우가
 * 많은 것은 월이율이 정확히 1% 가 되어 암산이 서기 때문이다.
 */
import { describe, expect, it } from 'vitest';

import { Product, ProductOption } from './products';
import {
  Requirement,
  availableTerms,
  depositInterest,
  interestOf,
  principalOf,
  recommend,
  savingInterest,
} from './recommend';

function product(overrides: Partial<Product> = {}): Product {
  return {
    kind: 'deposit',
    group: 'bank',
    disclosureMonth: '202609',
    company: '가나은행',
    name: '보통 정기예금',
    joinWays: ['영업점', '인터넷', '스마트폰'],
    special: '해당사항 없음',
    member: '실명의 개인',
    joinDeny: '1',
    maxLimit: null,
    afterMaturity: '만기 후 1년 이내 기본금리의 절반',
    note: '',
    options: [option()],
    ...overrides,
  };
}

function option(overrides: Partial<ProductOption> = {}): ProductOption {
  return { termMonths: 12, rateType: 'simple', rate: 3, topRate: 3, ...overrides };
}

function requirement(overrides: Partial<Requirement> = {}): Requirement {
  return {
    kind: 'deposit',
    termMonths: 12,
    amount: 1000,
    joinWays: [],
    groups: ['bank', 'savingsbank'],
    taxRate: 15.4,
    ...overrides,
  };
}

describe('정기예금 이자', () => {
  it('단리는 원금 × 연이율 × 기간이다', () => {
    expect(depositInterest(1000, 3, 12, 'simple')).toBeCloseTo(30, 10);
    expect(depositInterest(1000, 3, 6, 'simple')).toBeCloseTo(15, 10);
    expect(depositInterest(1000, 3, 24, 'simple')).toBeCloseTo(60, 10);
  });

  it('월복리는 연이율을 12 로 나눈 월이율로 굴린다', () => {
    // 연 12% → 월 1%. 1.01^12 − 1 = 0.126825…
    expect(depositInterest(1000, 12, 12, 'compound')).toBeCloseTo(126.8250301, 6);
  });

  it('월복리가 같은 금리의 단리보다 많다', () => {
    expect(depositInterest(1000, 3, 24, 'compound')).toBeGreaterThan(
      depositInterest(1000, 3, 24, 'simple'),
    );
  });

  it('금액이나 기간이 없으면 이자도 없다', () => {
    expect(depositInterest(0, 3, 12, 'simple')).toBe(0);
    expect(depositInterest(1000, 3, 0, 'simple')).toBe(0);
    expect(depositInterest(1000, 0, 12, 'simple')).toBe(0);
  });
});

describe('적금 이자', () => {
  it('단리는 월납입 × 월이율 × n(n+1)/2 다', () => {
    // 월 100만원, 연 12%(월 1%), 12개월 → 100 × 0.01 × 78 = 78
    expect(savingInterest(100, 12, 12, 'simple')).toBeCloseTo(78, 10);
  });

  it('같은 금리라도 예금에 한꺼번에 넣은 것의 절반 남짓이다', () => {
    // 적금으로 1년에 1200만원을 넣는 것과, 1200만원을 1년 예치하는 것.
    const saving = savingInterest(100, 12, 12, 'simple');
    const deposit = depositInterest(1200, 12, 12, 'simple');
    expect(saving / deposit).toBeCloseTo(0.541666, 5); // 78 / 144
  });

  it('월복리는 회차마다 남은 개월만큼 굴린 것을 더한 값이다', () => {
    const rate = 0.12 / 12;
    let byHand = 0;
    for (let k = 1; k <= 12; k += 1) byHand += 100 * (Math.pow(1 + rate, k) - 1);
    expect(savingInterest(100, 12, 12, 'compound')).toBeCloseTo(byHand, 8);
    expect(savingInterest(100, 12, 12, 'compound')).toBeGreaterThan(savingInterest(100, 12, 12, 'simple'));
  });
});

describe('원금과 종류별 셈', () => {
  it('적금의 원금은 매달 넣은 것이 쌓인 값이다', () => {
    expect(principalOf('deposit', 1000, 12)).toBe(1000);
    expect(principalOf('saving', 100, 12)).toBe(1200);
  });

  it('종류에 맞는 셈을 고른다', () => {
    expect(interestOf('deposit', 1000, 3, 12, 'simple')).toBeCloseTo(30, 10);
    expect(interestOf('saving', 1000, 3, 12, 'simple')).toBeCloseTo(
      savingInterest(1000, 3, 12, 'simple'),
      10,
    );
  });
});

describe('추천 — 요건에 맞지 않는 것을 뺀다', () => {
  it('그 기간의 금리가 없는 상품은 후보가 아니다', () => {
    const only6 = product({ name: '6개월짜리', options: [option({ termMonths: 6 })] });
    const result = recommend([product(), only6], requirement({ termMonths: 12 }));
    expect(result.offers).toHaveLength(1);
    expect(result.skipped.term).toBe(1);
  });

  it('고른 방법으로 가입할 수 없는 상품은 뺀다', () => {
    const branchOnly = product({ name: '영업점만', joinWays: ['영업점'] });
    const result = recommend([product(), branchOnly], requirement({ joinWays: ['스마트폰'] }));
    expect(result.offers.map((offer) => offer.product.name)).toEqual(['보통 정기예금']);
    expect(result.skipped.channel).toBe(1);
  });

  it('한도보다 많이 넣으려는 상품은 뺀다 (공시 한도는 원 단위다)', () => {
    const capped = product({ name: '500만원 한도', maxLimit: 5_000_000 });
    const result = recommend([capped], requirement({ amount: 1000 }));
    expect(result.offers).toHaveLength(0);
    expect(result.skipped.limit).toBe(1);

    const fits = recommend([capped], requirement({ amount: 400 }));
    expect(fits.offers).toHaveLength(1);
  });

  it('고르지 않은 금융권과 다른 종류는 아예 세지 않는다', () => {
    const savingsBank = product({ group: 'savingsbank', name: '저축은행 예금' });
    const saving = product({ kind: 'saving', name: '적금' });
    const result = recommend([product(), savingsBank, saving], requirement({ groups: ['bank'] }));
    expect(result.considered).toBe(1);
    expect(result.offers).toHaveLength(1);
  });
});

describe('추천 — 차례는 세후 이자가 매긴다', () => {
  it('금리가 높아도 적게 주면 아래로 간다', () => {
    // 단리 3.5% 는 35만원, 월복리 3.4% 는 34.5만원 남짓이다.
    const simple = product({ name: '단리 3.5', options: [option({ rate: 3.5, topRate: 3.5 })] });
    const compound = product({
      name: '복리 3.4',
      options: [option({ rate: 3.4, topRate: 3.4, rateType: 'compound' })],
    });
    const result = recommend([compound, simple], requirement());
    expect(result.offers.map((offer) => offer.product.name)).toEqual(['단리 3.5', '복리 3.4']);
  });

  it('한 상품에 단리·복리 줄이 같이 있으면 많이 주는 쪽으로 셈한다', () => {
    const both = product({
      options: [
        option({ rate: 3.5, topRate: 3.5, rateType: 'simple' }),
        option({ rate: 3.4, topRate: 3.4, rateType: 'compound' }),
      ],
    });
    const [offer] = recommend([both], requirement()).offers;
    expect(offer?.option.rateType).toBe('simple');
    expect(offer?.interest).toBeCloseTo(35, 6);
  });

  it('세금을 뗀 값과 만기 수령액을 함께 준다', () => {
    const [offer] = recommend([product()], requirement()).offers;
    expect(offer?.interest).toBeCloseTo(30, 10);
    expect(offer?.afterTaxInterest).toBeCloseTo(30 * (1 - 0.154), 10);
    expect(offer?.maturity).toBeCloseTo(1000 + 30 * 0.846, 10);
  });

  it('적금의 실효 연수익률은 표시 금리보다 훨씬 낮다', () => {
    const saving = product({ kind: 'saving', options: [option({ rate: 12, topRate: 12 })] });
    const [offer] = recommend([saving], requirement({ kind: 'saving', amount: 100, taxRate: 0 })).offers;
    // 78 / 1200 = 6.5%. 표시 금리 12% 의 절반 남짓이다.
    expect(offer?.effectiveAnnual).toBeCloseTo(6.5, 6);
  });

  it('우대조건까지 채웠을 때의 이자도 따로 알려 준다', () => {
    const withBonus = product({ options: [option({ rate: 3, topRate: 4 })] });
    const [offer] = recommend([withBonus], requirement()).offers;
    expect(offer?.afterTaxInterest).toBeCloseTo(30 * 0.846, 10);
    expect(offer?.afterTaxInterestTop).toBeCloseTo(40 * 0.846, 10);
  });

  it('공시월은 목록에 든 것 중 가장 최근을 쓴다', () => {
    const old = product({ name: '지난달', disclosureMonth: '202608' });
    const result = recommend([old, product()], requirement());
    expect(result.disclosureMonth).toBe('202609');
  });
});

describe('availableTerms', () => {
  it('자료에 실제로 있는 기간만 차례대로 준다', () => {
    const a = product({ options: [option({ termMonths: 12 }), option({ termMonths: 6 })] });
    const b = product({ options: [option({ termMonths: 24 }), option({ termMonths: 6 })] });
    const other = product({ kind: 'saving', options: [option({ termMonths: 36 })] });
    expect(availableTerms([a, b, other], 'deposit')).toEqual([6, 12, 24]);
    expect(availableTerms([a, b, other], 'saving')).toEqual([36]);
  });
});
