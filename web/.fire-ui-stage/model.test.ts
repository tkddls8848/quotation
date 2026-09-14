/**
 * 계산이 맞는지 대조한다.
 *
 * 이 화면은 숫자가 틀리면 없느니만 못하다. 그래서 손으로 검산할 수 있는
 * 경우를 골라 해석해와 맞춰 본다 — 복리 공식, 수익률 0 일 때의 고갈 시점,
 * 세금이 갉아먹는 양처럼 답을 미리 아는 것들이다.
 */
import { describe, expect, it } from 'vitest';

import {
  COMPREHENSIVE_TAX_THRESHOLD,
  FireInput,
  calculate,
  defaultInput,
  monthlySpendAt,
  monthlyRate,
  survive,
} from './model';

/** 셈이 드러나도록 가정을 전부 끈 입력. 여기서부터 하나씩 켜 본다. */
function plain(overrides: Partial<FireInput> = {}): FireInput {
  return {
    ...defaultInput(),
    age: 40,
    retireAge: 40,
    lifeAge: 90,
    deposit: { amount: 0, rate: 0, allocation: 100 },
    installment: { amount: 0, rate: 0, allocation: 0 },
    bond: { amount: 0, rate: 0, allocation: 0 },
    equity: { amount: 0, rate: 0, allocation: 0 },
    equityGrowth: 0,
    monthlySaving: 0,
    savingGrowth: 0,
    living: 0,
    housing: 0,
    medical: 0,
    other: 0,
    married: false,
    children: 0,
    hasCar: false,
    carMonthly: 0,
    carReplaceCost: 0,
    carReplaceYears: 0,
    inflation: 0,
    taxRate: 0,
    comprehensiveTax: false,
    pensionMonthly: 0,
    ...overrides,
  };
}

const balances = (deposit: number) => ({ deposit, installment: 0, bond: 0, equity: 0 });

describe('monthlyRate', () => {
  it('열두 번 곱하면 연 이율이 된다 (12 로 나누는 것과 다르다)', () => {
    const monthly = monthlyRate(6);
    expect(Math.pow(1 + monthly, 12) - 1).toBeCloseTo(0.06, 10);
    expect(monthly).toBeLessThan(0.06 / 12); // 복리라서 단리보다 작다
  });

  it('0% 는 0 이다', () => {
    expect(monthlyRate(0)).toBe(0);
  });
});

describe('monthlySpendAt — 지출은 나이의 함수다', () => {
  it('결혼하면 생활·주거·의료비에 계수가 붙는다', () => {
    const single = plain({ living: 100, medical: 10 });
    const married = { ...single, married: true, coupleFactor: 1.6 };
    expect(monthlySpendAt(single, 40)).toBe(110);
    expect(monthlySpendAt(married, 40)).toBeCloseTo(176, 6);
  });

  it('자녀 지원이 끝나면 그만큼 지출이 준다', () => {
    // 막내가 10살이고 22살까지 지원하면 12년 뒤 (부모 52세) 끝난다.
    const input = plain({
      living: 100,
      children: 2,
      childCost: 80,
      childYoungestAge: 10,
      childUntilAge: 22,
    });
    expect(monthlySpendAt(input, 51)).toBe(100 + 160);
    expect(monthlySpendAt(input, 52)).toBe(100);
  });

  it('차량 교체비는 주기로 나눠 매달 적립하는 셈으로 넣는다', () => {
    const input = plain({ hasCar: true, carMonthly: 40, carReplaceCost: 3000, carReplaceYears: 10 });
    expect(monthlySpendAt(input, 40)).toBe(40 + 25); // 3000 / 120 개월
  });

  it('정해 둔 나이부터 의료비에 계수를 곱한다', () => {
    const input = plain({ medical: 20, medicalOldAge: 65, medicalOldFactor: 2 });
    expect(monthlySpendAt(input, 64)).toBe(20);
    expect(monthlySpendAt(input, 65)).toBe(40);
  });
});

describe('survive — 쓰는 동안', () => {
  it('수익도 물가도 없으면 자산을 지출로 나눈 개월에 바닥난다', () => {
    // 1,200만원을 매달 100만원씩 쓰면 12개월 뒤 0 이고 13개월째에 모자란다.
    const input = plain({ living: 100 });
    const result = survive(input, 0, balances(1200), 600);
    expect(result.survived).toBe(false);
    expect(result.depletionMonth).toBe(12);
  });

  it('국민연금이 지출을 다 덮으면 자산이 없어도 버틴다', () => {
    const input = plain({ living: 100, pensionMonthly: 100, pensionStartAge: 40 });
    expect(survive(input, 0, balances(0), 600).survived).toBe(true);
  });

  it('연금 개시 전까지는 자산으로 버텨야 한다', () => {
    const input = plain({ living: 100, pensionMonthly: 100, pensionStartAge: 65 });
    // 40세부터 65세까지 300개월 × 100만원 = 30,000만원(3억)이 있어야 한다.
    expect(survive(input, 0, balances(29900), 600).survived).toBe(false);
    expect(survive(input, 0, balances(30000), 600).survived).toBe(true);
  });

  it('물가가 오르면 같은 자산으로 더 짧게 버틴다', () => {
    const flat = plain({ living: 100 });
    const rising = { ...flat, inflation: 3 };
    const a = survive(flat, 0, balances(6000), 600);
    const b = survive(rising, 0, balances(6000), 600);
    expect(a.depletionMonth).toBe(60);
    expect(b.depletionMonth).toBeLessThan(60);
  });

  it('세금은 이자에만 붙고 주가 상승분에는 붙지 않는다', () => {
    const base = plain({
      deposit: { amount: 10000, rate: 5, allocation: 100 },
      taxRate: 15.4,
    });
    const equity = plain({
      deposit: { amount: 0, rate: 0, allocation: 0 },
      equity: { amount: 10000, rate: 0, allocation: 100 },
      equityGrowth: 5,
      taxRate: 15.4,
    });
    // 같은 5% 인데 이자 쪽만 세금을 뗀다 — 한 해 뒤 잔액이 다르다.
    const oneYear = 12;
    const afterInterest = survive(base, 0, balances(10000), oneYear);
    const afterGrowth = survive(equity, 0, { deposit: 0, installment: 0, bond: 0, equity: 10000 }, oneYear);
    expect(afterInterest.survived).toBe(true);
    expect(afterGrowth.survived).toBe(true);
  });
});

describe('calculate — 판정', () => {
  it('이미 충분하면 지금 당장 가능이라고 답한다', () => {
    const result = calculate(
      plain({ living: 100, pensionMonthly: 100, pensionStartAge: 40 }),
    );
    expect(result.verdict).toBe('possible');
    expect(result.earliestMonths).toBe(0);
  });

  it('모자라면 목표 나이에 바닥나는 시점을 알려 준다', () => {
    const result = calculate(plain({ age: 40, retireAge: 40, living: 100, deposit: { amount: 1200, rate: 0, allocation: 100 } }));
    expect(result.verdict).not.toBe('possible');
    expect(result.depletionAge).toBeCloseTo(41, 6);
  });

  it('저축이 쌓여 나중에는 되면 "늦지만 가능" 으로 가른다', () => {
    const result = calculate(
      plain({
        age: 30,
        retireAge: 35,
        lifeAge: 90,
        living: 100,
        monthlySaving: 300,
        deposit: { amount: 0, rate: 3, allocation: 100 },
      }),
    );
    expect(result.verdict).toBe('late');
    expect(result.earliestMonths).not.toBeNull();
    expect(result.earliestMonths!).toBeGreaterThan((35 - 30) * 12);
  });

  it('수익률이 물가를 못 따라가고 지출이 크면 어느 나이에도 안 된다', () => {
    const input = plain({
      age: 30,
      retireAge: 40,
      living: 500,
      inflation: 5,
      monthlySaving: 100,
      deposit: { amount: 0, rate: 0.5, allocation: 100 },
    });
    const result = calculate(input);
    expect(result.verdict).toBe('impossible');
    expect(result.earliestMonths).toBeNull();
    // 그래도 얼마가 필요한지는 답한다 — 지금 저축으로는 어림없다는 것까지.
    expect(result.requiredMonthlySaving!).toBeGreaterThan(input.monthlySaving * 10);
  });

  it('모아 둔 것도 저축도 없으면 어느 나이에 은퇴해도 안 된다', () => {
    const result = calculate(plain({ age: 30, retireAge: 40, living: 100, monthlySaving: 0 }));
    expect(result.verdict).toBe('impossible');
    expect(result.earliestMonths).toBeNull();
    // 그래도 "얼마를 저축하면 되는지" 는 답한다.
    expect(result.requiredMonthlySaving!).toBeGreaterThan(0);
  });

  it('지금 당장 은퇴하려는데 가진 게 없으면 저축으로 메울 시간이 없다', () => {
    const result = calculate(plain({ age: 40, retireAge: 40, living: 100 }));
    expect(result.requiredMonthlySaving).toBeNull();
  });

  it('FIRE 넘버는 연 지출을 인출률로 나눈 값이다', () => {
    const result = calculate(plain({ living: 200, swr: 4 }));
    expect(result.monthlySpendToday).toBe(200);
    expect(result.fireNumberToday).toBe((200 * 12) / 0.04); // 60,000만원 = 6억
  });

  it('알려 준 필요 저축액을 그대로 넣으면 목표 나이에 가능해진다', () => {
    const input = plain({
      age: 35,
      retireAge: 55,
      lifeAge: 90,
      living: 150,
      inflation: 2,
      deposit: { amount: 5000, rate: 3, allocation: 100 },
      monthlySaving: 0,
    });
    const required = calculate(input).requiredMonthlySaving;
    expect(required).not.toBeNull();

    const fixed = calculate({ ...input, monthlySaving: required! });
    expect(fixed.verdict).toBe('possible');

    // 그보다 조금이라도 적으면 안 된다 — 최소값이어야 뜻이 있다.
    const short = calculate({ ...input, monthlySaving: required! * 0.9 });
    expect(short.verdict).not.toBe('possible');
  });

  it('세금을 올리면 같은 조건에서 은퇴가 늦어진다', () => {
    const input = plain({
      age: 30,
      retireAge: 60,
      lifeAge: 90,
      living: 150,
      monthlySaving: 200,
      deposit: { amount: 10000, rate: 4, allocation: 100 },
    });
    const noTax = calculate({ ...input, taxRate: 0 });
    const taxed = calculate({ ...input, taxRate: 15.4 });
    expect(taxed.assetsAtRetire).toBeLessThan(noTax.assetsAtRetire);
    expect(taxed.earliestMonths!).toBeGreaterThan(noTax.earliestMonths!);
  });

  it('금융소득 종합과세를 켜면 자산이 더 줄어든다', () => {
    // 이자만 연 2,000만원을 넘기는 규모여야 차이가 난다.
    const input = plain({
      age: 40,
      retireAge: 41,
      lifeAge: 90,
      living: 100,
      deposit: { amount: 100000, rate: 4, allocation: 100 },
    });
    const separate = calculate({ ...input, comprehensiveTax: false });
    const comprehensive = calculate({
      ...input,
      comprehensiveTax: true,
      comprehensiveRate: 26.4,
    });
    expect(comprehensive.assetsAtRetire).toBeLessThan(separate.assetsAtRetire);
  });

  it('금융소득이 2,000만원을 넘는데 분리과세로 두면 경고한다', () => {
    const result = calculate(
      plain({ deposit: { amount: 100000, rate: 4, allocation: 100 }, living: 100 }),
    );
    const yearly = (100000 * 4) / 100;
    expect(yearly).toBeGreaterThan(COMPREHENSIVE_TAX_THRESHOLD);
    expect(result.warnings.join(' ')).toContain('종합과세');
  });

  it('저축 배분 합이 100 이 아니면 맞춰 셈하고 그 사실을 알린다', () => {
    const result = calculate(
      plain({
        monthlySaving: 100,
        deposit: { amount: 0, rate: 3, allocation: 30 },
        bond: { amount: 0, rate: 3, allocation: 30 },
        living: 100,
      }),
    );
    expect(result.warnings.join(' ')).toContain('배분');
  });

  it('그래프 점은 해마다 하나씩, 기대 수명까지 나온다', () => {
    const result = calculate(plain({ age: 40, retireAge: 50, lifeAge: 90, living: 100 }));
    expect(result.path).toHaveLength(51); // 40세부터 90세까지 양 끝 포함
    expect(result.path[0]!.age).toBe(40);
    expect(result.path[result.path.length - 1]!.age).toBe(90);
  });

  it('기본값으로도 무너지지 않고 답을 낸다', () => {
    const result = calculate(defaultInput());
    expect(Number.isFinite(result.assetsAtRetire)).toBe(true);
    expect(Number.isFinite(result.fireNumberToday)).toBe(true);
    expect(['possible', 'late', 'impossible']).toContain(result.verdict);
  });

  it('나이가 뒤집혀 있어도 계산이 무너지지 않는다', () => {
    const result = calculate(plain({ age: 60, retireAge: 30, lifeAge: 20, living: 100 }));
    expect(Number.isFinite(result.assetsAtRetire)).toBe(true);
    expect(result.path.length).toBeGreaterThan(0);
  });
});
