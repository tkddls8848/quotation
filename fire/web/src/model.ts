/**
 * FIRE 계산 — 순수 계산부. DOM 도 브라우저 API 도 쓰지 않는다.
 *
 * 이 화면의 값어치는 숫자가 맞다는 것 하나다. 그래서 계산을 화면에서 떼어
 * 내고 `model.test.ts` 가 매번 대조한다. 화면은 이 파일이 돌려준 것을 그리기만
 * 한다.
 *
 * ── 무엇을 셈하는가 ───────────────────────────────────────────────────────
 *
 * "25배를 모으면 끝" 이라는 어림(4% 규칙)은 참고로만 보여 준다. 판정은 **월
 * 단위 모의 실험** 이 한다. 은퇴 시점부터 기대 수명까지 매달 물가가 오른 만큼
 * 더 쓰고, 남은 자산은 세후 수익률로 굴리고, 국민연금이 나오기 시작하면 그만큼
 * 덜 뽑는다. 그렇게 끝까지 자산이 남으면 "가능" 이다.
 *
 * 어림 대신 모의 실험으로 판정하는 이유는 4% 규칙이 미국 주식·채권 60/40 을
 * 30년 굴린 결과라서다. 한국의 예금·적금·채권 위주 자산, 물가, 15.4%
 * 이자소득세, 65세부터 들어오는 국민연금은 그 전제와 다르다.
 *
 * ── 단위 ──────────────────────────────────────────────────────────────────
 *
 * 금액은 전부 **만원** 이다. 한국 사람이 머리로 쓰는 단위이고, 원 단위로 두면
 * 0 이 너무 많아 눈으로 검산할 수 없다. 비율은 연 %(백분율 숫자 그대로).
 *
 * ── 세금 ──────────────────────────────────────────────────────────────────
 *
 * 이자·배당은 15.4%(소득세 14% + 지방소득세 1.4%) 원천징수로 본다. 한 해
 * 금융소득이 2,000만원을 넘으면 초과분이 종합과세 대상이라 세금이 더 붙는다 —
 * FIRE 규모에서는 실제로 걸리는 선이라 선택 항목으로 넣었다.
 *
 * 국내 상장주식의 시세 차익은 소액주주면 양도세가 없어서 성장분에는 세금을
 * 매기지 않는다. **해외 주식·ETF 는 양도세 22% 가 붙으므로** 그 경우에는 주가
 * 상승률을 세후로 낮춰 넣어야 한다. 화면이 그 주의를 함께 띄운다.
 */

/** 만원. */
export type Man = number;

/** 한 해 금융소득이 이 선을 넘으면 초과분이 종합과세 대상이 된다 (만원). */
export const COMPREHENSIVE_TAX_THRESHOLD: Man = 2000;

/**
 * 이만큼은 살아야 은퇴라고 친다 (개월).
 *
 * 이 선이 없으면 계산이 "기대 수명에 은퇴하면 하루도 안 버텨도 되니 가능" 이라는
 * 답을 낸다. 틀린 셈은 아니지만 쓸모가 없다. 은퇴하고 1년도 못 쓸 돈이면
 * 그냥 안 되는 것이다.
 */
export const MIN_RETIREMENT_MONTHS = 12;

export interface AssetInput {
  /** 지금 들어 있는 금액. */
  amount: Man;
  /** 연 수익률 %. 배당주는 배당수익률을 뜻한다. */
  rate: number;
  /** 매달 저축하는 돈 중 이 자산군으로 가는 몫 %. */
  allocation: number;
}

export interface FireInput {
  age: number;
  /** 은퇴하고 싶은 나이. */
  retireAge: number;
  /** 여기까지 돈이 버텨야 한다. */
  lifeAge: number;

  deposit: AssetInput;
  installment: AssetInput;
  bond: AssetInput;
  equity: AssetInput;
  /** 배당주의 주가 상승률 %. 배당과 따로 센다 (국내 주식은 차익이 비과세). */
  equityGrowth: number;

  /** 지금 매달 남겨 저축하는 돈. 은퇴 전까지 넣는다. */
  monthlySaving: Man;
  /** 저축액이 해마다 오르는 비율 % (임금 인상분). */
  savingGrowth: number;

  // 은퇴한 뒤의 월 지출. 지금 물가, 1인 가구 기준으로 적는다.
  living: Man;
  housing: Man;
  medical: Man;
  other: Man;

  married: boolean;
  /** 기혼이면 생활·주거·의료비에 곱하는 계수. 2인 가구는 1인의 1.6배 남짓이다. */
  coupleFactor: number;

  children: number;
  /** 자녀 한 명당 월 양육·교육비. */
  childCost: Man;
  /** 막내 나이. */
  childYoungestAge: number;
  /** 자녀를 몇 살까지 지원할 것인가. 그 뒤로 이 지출은 사라진다. */
  childUntilAge: number;

  hasCar: boolean;
  /** 월 유지비 (기름·보험·정비). */
  carMonthly: Man;
  /** 차를 바꿀 때 드는 돈. 주기로 나눠 매달 적립하는 셈으로 친다. */
  carReplaceCost: Man;
  carReplaceYears: number;

  /** 이 나이부터 의료비에 계수를 곱한다. 나이 들수록 늘기 때문이다. */
  medicalOldAge: number;
  medicalOldFactor: number;

  /** 연 물가 상승률 %. */
  inflation: number;
  /** 안전 인출률 % — 참고 지표(FIRE 넘버)를 뽑는 데만 쓴다. */
  swr: number;

  /** 이자·배당 원천징수 세율 %. */
  taxRate: number;
  comprehensiveTax: boolean;
  /** 금융소득 2,000만원 초과분에 물릴 실효세율 %. */
  comprehensiveRate: number;

  /** 국민연금 예상 월 수령액 (지금 물가 기준). 물가에 연동해 오른다. */
  pensionMonthly: Man;
  pensionStartAge: number;
}

export interface Balances {
  deposit: number;
  installment: number;
  bond: number;
  equity: number;
}

export interface PathPoint {
  age: number;
  /** 그 나이 시점의 자산 (명목). */
  assets: Man;
  /** 그 나이에 은퇴한다면 필요한 자산 (명목, 인출률 기준 참고선). */
  target: Man;
}

export type Verdict = 'possible' | 'late' | 'impossible';

export interface FireResult {
  verdict: Verdict;
  /** 모의 실험이 통과하는 가장 이른 은퇴 시점 (개월). 없으면 null. */
  earliestMonths: number | null;
  /** 목표 나이에 은퇴했을 때 자산이 바닥나는 나이. 버티면 null. */
  depletionAge: number | null;

  /** 목표 은퇴 나이 시점의 예상 자산 (명목). */
  assetsAtRetire: Man;
  /** 목표 은퇴 나이 시점에 필요한 자산 (명목, 참고선). */
  targetAtRetire: Man;
  /** 참고선에 모자란 금액. 남으면 0. */
  shortfall: Man;

  /** 지금 물가로 환산한 FIRE 넘버 (연 지출 / 인출률). */
  fireNumberToday: Man;
  /** 은퇴 직후 한 달 지출 (지금 물가). */
  monthlySpendToday: Man;
  /** 목표 나이를 지키려면 매달 저축해야 하는 금액. 불가능하면 null. */
  requiredMonthlySaving: Man | null;

  path: PathPoint[];
  warnings: string[];
}

// --- 도우미 -----------------------------------------------------------------

/** 연 이율을 월 복리로 환산한다. 12 로 나누는 것과 다르다. */
export function monthlyRate(annualPercent: number): number {
  return Math.pow(1 + annualPercent / 100, 1 / 12) - 1;
}

const sum = (b: Balances): number => b.deposit + b.installment + b.bond + b.equity;

const clamp = (value: number, low: number, high: number): number =>
  Number.isFinite(value) ? Math.min(high, Math.max(low, value)) : low;

/**
 * 은퇴한 뒤 그 나이에 드는 한 달 지출 (지금 물가 기준).
 *
 * 자녀 지원과 차량 교체 적립은 기한이 있어서 나이에 따라 달라진다. 그래서
 * 지출을 숫자 하나로 두지 않고 나이의 함수로 둔다.
 */
export function monthlySpendAt(input: FireInput, age: number): Man {
  const factor = input.married ? input.coupleFactor : 1;
  let spend = (input.living + input.housing + input.other) * factor;
  spend += input.medical * factor * (age >= input.medicalOldAge ? input.medicalOldFactor : 1);

  if (input.children > 0) {
    const yearsLeft = Math.max(0, input.childUntilAge - input.childYoungestAge);
    if (age < input.age + yearsLeft) spend += input.children * input.childCost;
  }

  if (input.hasCar) {
    spend += input.carMonthly;
    if (input.carReplaceYears > 0) {
      spend += input.carReplaceCost / (input.carReplaceYears * 12);
    }
  }
  return spend;
}

/** 한 해 금융소득 중 2,000만원을 넘는 몫에 더 물리는 세금. */
function extraTax(input: FireInput, yearlyFinancialIncome: Man): Man {
  if (!input.comprehensiveTax) return 0;
  const over = yearlyFinancialIncome - COMPREHENSIVE_TAX_THRESHOLD;
  if (over <= 0) return 0;
  const gap = Math.max(0, input.comprehensiveRate - input.taxRate) / 100;
  return over * gap;
}

/** 값이 뒤집혀 있거나 비어 있어도 계산이 무너지지 않도록 다듬는다. */
function normalize(raw: FireInput): { input: FireInput; warnings: string[] } {
  const warnings: string[] = [];
  const input: FireInput = { ...raw };

  input.age = clamp(input.age, 0, 100);
  input.retireAge = clamp(input.retireAge, input.age, 100);
  input.lifeAge = clamp(input.lifeAge, input.retireAge + 1, 120);

  const total =
    input.deposit.allocation +
    input.installment.allocation +
    input.bond.allocation +
    input.equity.allocation;

  if (input.monthlySaving > 0 && total <= 0) {
    // 갈 곳을 적지 않았다. 가장 안전한 곳에 둔다.
    input.deposit = { ...input.deposit, allocation: 100 };
    warnings.push('저축 배분이 비어 있어 전액 예금으로 넣고 셈했습니다.');
  } else if (total > 0 && Math.abs(total - 100) > 0.5) {
    const scale = 100 / total;
    input.deposit = { ...input.deposit, allocation: input.deposit.allocation * scale };
    input.installment = { ...input.installment, allocation: input.installment.allocation * scale };
    input.bond = { ...input.bond, allocation: input.bond.allocation * scale };
    input.equity = { ...input.equity, allocation: input.equity.allocation * scale };
    warnings.push(`저축 배분 합이 ${Math.round(total)}% 라서 100% 로 맞춰 셈했습니다.`);
  }
  return { input, warnings };
}

// --- 모으는 동안 -------------------------------------------------------------

/**
 * 은퇴 전까지 매달 자산이 어떻게 불어나는지 따라간다.
 *
 * 이자와 배당은 받은 자리에서 세금을 떼고 그대로 재투자한다고 본다. 은퇴 전에는
 * 쓰지 않는 돈이므로 이게 실제에 가깝다.
 */
function accumulate(input: FireInput, months: number): Balances[] {
  const rates = {
    deposit: monthlyRate(input.deposit.rate),
    installment: monthlyRate(input.installment.rate),
    bond: monthlyRate(input.bond.rate),
    dividend: monthlyRate(input.equity.rate),
    growth: monthlyRate(input.equityGrowth),
  };
  const share = {
    deposit: input.deposit.allocation / 100,
    installment: input.installment.allocation / 100,
    bond: input.bond.allocation / 100,
    equity: input.equity.allocation / 100,
  };
  const afterTax = 1 - input.taxRate / 100;

  let balances: Balances = {
    deposit: Math.max(0, input.deposit.amount),
    installment: Math.max(0, input.installment.amount),
    bond: Math.max(0, input.bond.amount),
    equity: Math.max(0, input.equity.amount),
  };
  const path: Balances[] = [{ ...balances }];
  let yearIncome = 0;

  for (let m = 0; m < months; m += 1) {
    yearIncome +=
      balances.deposit * rates.deposit +
      balances.installment * rates.installment +
      balances.bond * rates.bond +
      balances.equity * rates.dividend;

    balances = {
      deposit: balances.deposit * (1 + rates.deposit * afterTax),
      installment: balances.installment * (1 + rates.installment * afterTax),
      bond: balances.bond * (1 + rates.bond * afterTax),
      equity: balances.equity * (1 + rates.dividend * afterTax + rates.growth),
    };

    if ((m + 1) % 12 === 0) {
      const bill = extraTax(input, yearIncome);
      yearIncome = 0;
      const total = sum(balances);
      if (bill > 0 && total > 0) {
        // 세금은 자산 구성대로 고르게 떼어 간다.
        const keep = Math.max(0, 1 - bill / total);
        balances = {
          deposit: balances.deposit * keep,
          installment: balances.installment * keep,
          bond: balances.bond * keep,
          equity: balances.equity * keep,
        };
      }
    }

    const saving =
      Math.max(0, input.monthlySaving) * Math.pow(1 + input.savingGrowth / 100, m / 12);
    balances = {
      deposit: balances.deposit + saving * share.deposit,
      installment: balances.installment + saving * share.installment,
      bond: balances.bond + saving * share.bond,
      equity: balances.equity + saving * share.equity,
    };
    path.push({ ...balances });
  }
  return path;
}

// --- 쓰는 동안 ---------------------------------------------------------------

export interface SurvivalResult {
  survived: boolean;
  /** 자산이 0 밑으로 내려간 시점 (개월). 버티면 null. */
  depletionMonth: number | null;
}

/**
 * `startMonth` 에 은퇴한다고 보고 기대 수명까지 버티는지 본다.
 *
 * 은퇴한 뒤로는 자산 구성이 그대로 유지된다고 본다 — 그래서 이자·배당이 붙는
 * 몫(과세)과 주가가 오르는 몫(비과세)의 비율을 은퇴 시점 잔액으로 한 번 구해
 * 끝까지 쓴다. 실제로는 인출하면서 구성이 조금씩 흔들리지만, 그 차이는 물가와
 * 수익률 가정의 오차보다 훨씬 작다.
 */
export function survive(
  input: FireInput,
  startMonth: number,
  balances: Balances,
  totalMonths: number,
): SurvivalResult {
  let assets = sum(balances);
  const base = assets;

  const taxableAnnual =
    base <= 0
      ? 0
      : (balances.deposit * input.deposit.rate +
          balances.installment * input.installment.rate +
          balances.bond * input.bond.rate +
          balances.equity * input.equity.rate) /
        base;
  const growthAnnual = base <= 0 ? 0 : (balances.equity * input.equityGrowth) / base;

  const taxable = monthlyRate(taxableAnnual);
  const growth = monthlyRate(growthAnnual);
  const afterTax = 1 - input.taxRate / 100;
  let yearIncome = 0;

  for (let m = startMonth; m < totalMonths; m += 1) {
    const age = input.age + m / 12;
    const inflated = Math.pow(1 + input.inflation / 100, m / 12);

    const interest = assets * taxable;
    yearIncome += interest;
    assets += interest * afterTax + assets * growth;

    if ((m + 1) % 12 === 0) {
      assets -= extraTax(input, yearIncome);
      yearIncome = 0;
    }

    const spend = monthlySpendAt(input, age) * inflated;
    const pension = age >= input.pensionStartAge ? input.pensionMonthly * inflated : 0;
    assets -= Math.max(0, spend - pension);

    if (assets < 0) return { survived: false, depletionMonth: m };
  }
  return { survived: true, depletionMonth: null };
}

// --- 판정 --------------------------------------------------------------------

export function calculate(raw: FireInput): FireResult {
  const { input, warnings } = normalize(raw);
  const months = Math.round((input.lifeAge - input.age) * 12);
  const retireMonth = Math.min(Math.round((input.retireAge - input.age) * 12), months);
  const path = accumulate(input, months);

  // 가장 이른 은퇴 시점. 늦게 은퇴할수록 자산은 늘고 버틸 기간은 줄어드니
  // 한 번 통과하면 그 뒤로도 통과한다 — 처음 통과하는 달이 답이다.
  let earliestMonths: number | null = null;
  for (let m = 0; m <= months - MIN_RETIREMENT_MONTHS; m += 1) {
    const point = path[m];
    if (point && survive(input, m, point, months).survived) {
      earliestMonths = m;
      break;
    }
  }

  const atRetire = path[retireMonth] ?? path[path.length - 1]!;
  const assetsAtRetire = sum(atRetire);
  const retireCheck = survive(input, retireMonth, atRetire, months);

  const monthlySpendToday = monthlySpendAt(input, input.retireAge);
  const withdrawal = input.swr > 0 ? input.swr / 100 : 1;
  const fireNumberToday = (monthlySpendToday * 12) / withdrawal;
  const targetAtRetire = fireNumberToday * Math.pow(1 + input.inflation / 100, retireMonth / 12);

  const verdict: Verdict =
    earliestMonths === null ? 'impossible' : earliestMonths <= retireMonth ? 'possible' : 'late';

  const pathPoints: PathPoint[] = [];
  for (let m = 0; m <= months; m += 12) {
    const point = path[m];
    if (!point) continue;
    const age = input.age + m / 12;
    pathPoints.push({
      age,
      assets: sum(point),
      target:
        ((monthlySpendAt(input, age) * 12) / withdrawal) *
        Math.pow(1 + input.inflation / 100, m / 12),
    });
  }

  return {
    verdict,
    earliestMonths,
    depletionAge:
      retireCheck.depletionMonth === null ? null : input.age + retireCheck.depletionMonth / 12,
    assetsAtRetire,
    targetAtRetire,
    shortfall: Math.max(0, targetAtRetire - assetsAtRetire),
    fireNumberToday,
    monthlySpendToday,
    requiredMonthlySaving: requiredMonthlySaving(input, months, retireMonth),
    path: pathPoints,
    warnings: [...warnings, ...notices(input, monthlySpendToday)],
  };
}

/**
 * 목표 나이를 지키려면 매달 얼마를 저축해야 하는가.
 *
 * 저축을 늘릴수록 은퇴 시점 자산이 커지므로 통과 여부는 한 방향으로만 바뀐다.
 * 그래서 이분법으로 찾는다. 아무리 넣어도 안 되면 null — 지출이 수익을 넘어서
 * 자산이 얼마든 버티지 못하는 경우다.
 */
function requiredMonthlySaving(
  input: FireInput,
  months: number,
  retireMonth: number,
): Man | null {
  const ok = (saving: Man): boolean => {
    const trial: FireInput = { ...input, monthlySaving: saving };
    const point = accumulate(trial, months)[retireMonth];
    return point ? survive(trial, retireMonth, point, months).survived : false;
  };

  if (ok(0)) return 0;

  let high = Math.max(100, input.monthlySaving * 2);
  for (let i = 0; i < 14 && !ok(high); i += 1) high *= 2;
  if (!ok(high)) return null;

  let low = 0;
  for (let i = 0; i < 32; i += 1) {
    const mid = (low + high) / 2;
    if (ok(mid)) high = mid;
    else low = mid;
  }
  return high;
}

/** 숫자만으로는 드러나지 않는 함정을 말로 알려 준다. */
function notices(input: FireInput, monthlySpendToday: Man): string[] {
  const out: string[] = [];
  const yearlyFinancial =
    (input.deposit.amount * input.deposit.rate +
      input.installment.amount * input.installment.rate +
      input.bond.amount * input.bond.rate +
      input.equity.amount * input.equity.rate) /
    100;

  if (!input.comprehensiveTax && yearlyFinancial > COMPREHENSIVE_TAX_THRESHOLD) {
    out.push(
      `지금 자산에서 나오는 이자·배당만 연 ${Math.round(yearlyFinancial)}만원입니다. ` +
        '2,000만원을 넘으면 금융소득 종합과세 대상이라 세금이 더 붙습니다 — 세금 항목을 켜고 다시 보십시오.',
    );
  }
  if (input.equityGrowth > 0) {
    out.push(
      '배당주의 주가 상승분은 국내 상장주식·소액주주 기준으로 비과세로 셈했습니다. ' +
        '해외 주식이나 해외 ETF 라면 양도세 22% 가 붙으므로 상승률을 그만큼 낮춰 넣으십시오.',
    );
  }
  if (input.swr >= 4) {
    out.push(
      '인출률 4% 는 미국 주식·채권 60/40 을 30년 굴린 연구에서 나온 값입니다. ' +
        '예금·채권 위주이거나 은퇴 기간이 30년보다 길면 3~3.5% 가 안전합니다.',
    );
  }
  if (input.inflation <= 0) {
    out.push('물가 상승률을 0 으로 두면 결과가 실제보다 훨씬 낙관적으로 나옵니다.');
  }
  if (monthlySpendToday <= 0) {
    out.push('은퇴 후 지출이 0 입니다. 지출을 채워야 뜻이 있는 결과가 나옵니다.');
  }
  return out;
}

/** 화면이 처음 띄우는 값. 한국 기준의 무난한 가정이다. */
export function defaultInput(): FireInput {
  return {
    age: 35,
    retireAge: 50,
    lifeAge: 95,

    deposit: { amount: 3000, rate: 3.0, allocation: 20 },
    installment: { amount: 1000, rate: 3.5, allocation: 20 },
    bond: { amount: 2000, rate: 4.0, allocation: 20 },
    equity: { amount: 4000, rate: 3.0, allocation: 40 },
    equityGrowth: 4.0,

    monthlySaving: 200,
    savingGrowth: 2.0,

    living: 120,
    housing: 50,
    medical: 15,
    other: 30,

    married: false,
    coupleFactor: 1.6,

    children: 0,
    childCost: 80,
    childYoungestAge: 0,
    childUntilAge: 22,

    hasCar: true,
    carMonthly: 40,
    carReplaceCost: 3000,
    carReplaceYears: 10,

    medicalOldAge: 65,
    medicalOldFactor: 2.0,

    inflation: 2.3,
    swr: 4.0,

    taxRate: 15.4,
    comprehensiveTax: false,
    comprehensiveRate: 16.5,

    pensionMonthly: 0,
    pensionStartAge: 65,
  };
}
