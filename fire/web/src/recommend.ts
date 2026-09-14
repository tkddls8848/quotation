/**
 * 요건에 맞는 예적금 상품 고르기 — 순수 계산부. DOM 도 네트워크도 쓰지 않는다.
 *
 * `model.ts` 와 같은 이유로 화면에서 떼어 두었다. 이 파일이 하는 말은 "이 상품에
 * 이 돈을 이 기간 넣으면 세금 떼고 얼마를 받는다" 이고, 그 숫자가 틀리면 목록의
 * 차례가 통째로 거짓말이 된다. `recommend.test.ts` 가 손으로 검산한 값과 맞춘다.
 *
 * ── 금리를 어떻게 셈하는가 ────────────────────────────────────────────────
 *
 * 은행이 실제로 쓰는 방식을 그대로 따른다. **월이율은 연이율을 12 로 나눈
 * 값**이다 (`model.ts` 의 `monthlyRate` 는 기하평균으로 환산한다 — 거기는 몇십 년을
 * 굴리는 모의 실험이라 그게 맞고, 여기는 은행이 이자를 적어 주는 방식이라 이게
 * 맞다. 두 파일이 다른 것은 실수가 아니다).
 *
 *   정기예금 단리    이자 = 원금 × 연이율 × 개월/12
 *   정기예금 월복리  이자 = 원금 × ((1 + 월이율)^개월 − 1)
 *   적금 단리        이자 = 월납입 × 월이율 × n(n+1)/2
 *                    — 첫 회차는 n 개월, 마지막 회차는 1 개월치 이자를 받는다
 *   적금 월복리      이자 = 월납입 × Σ((1 + 월이율)^k − 1),  k = 1..n
 *
 * 적금의 이자가 "월납입 × 12개월 × 금리" 가 아니라 그 절반 남짓인 이유가 저
 * n(n+1)/2 다. 적금 금리가 예금보다 높아 보여도 실제로 받는 돈은 그렇지 않다 —
 * 이 목록이 금리가 아니라 **세후 이자** 로 차례를 매기는 까닭이다.
 *
 * ── 세금 ──────────────────────────────────────────────────────────────────
 *
 * 이자소득세 15.4% 를 뗀다. 계산기 본체의 세율 항목을 그대로 받아 쓴다.
 */

import { FinanceGroup, Product, ProductKind, ProductOption, RateType } from './products';

/** 만원. `model.ts` 와 같은 단위다. */
export type Man = number;

/** 공시가 한도를 원 단위로 준다. 우리 단위로 내린다. */
const MAN = 10_000;

export interface Requirement {
  kind: ProductKind;
  /** 예치 기간 (개월). 이 기간의 금리가 없는 상품은 애초에 후보가 아니다. */
  termMonths: number;
  /** 정기예금이면 한 번에 넣는 돈, 적금이면 매달 넣는 돈 (만원). */
  amount: Man;
  /** 이 방법 중 하나로 가입할 수 있어야 한다. 비우면 가리지 않는다. */
  joinWays: string[];
  groups: FinanceGroup[];
  /** 이자소득세율 %. */
  taxRate: number;
}

export interface Offer {
  product: Product;
  option: ProductOption;
  /** 넣는 돈의 합 (적금은 월납입 × 개월). */
  principal: Man;
  /** 기본 금리로 받는 세전 이자. */
  interest: Man;
  /** 세금을 뗀 이자. 차례는 이 값이 매긴다. */
  afterTaxInterest: Man;
  /** 원금과 세후 이자를 더한 만기 수령액. */
  maturity: Man;
  /** 우대조건을 다 채웠을 때의 세후 이자. 기본과 같으면 우대가 없는 상품이다. */
  afterTaxInterestTop: Man;
  /** 세후 이자를 원금·기간으로 되돌린 연 수익률 %. 기간이 다른 상품을 견주는 잣대다. */
  effectiveAnnual: number;
}

export interface Recommendation {
  offers: Offer[];
  /** 요건을 따지기 전의 상품 수. */
  considered: number;
  /** 왜 빠졌는지. 목록이 비었을 때 사람에게 할 말이 된다. */
  skipped: {
    term: number;
    channel: number;
    limit: number;
  };
  /** 목록에 든 상품의 공시월 (여럿이면 가장 최근). */
  disclosureMonth: string | null;
}

// --- 이자 --------------------------------------------------------------------

const monthly = (annualPercent: number): number => annualPercent / 100 / 12;

/** 정기예금 이자 (세전). */
export function depositInterest(
  principal: Man,
  annualPercent: number,
  months: number,
  type: RateType,
): Man {
  if (principal <= 0 || months <= 0 || annualPercent <= 0) return 0;
  if (type === 'compound') {
    return principal * (Math.pow(1 + monthly(annualPercent), months) - 1);
  }
  return principal * (annualPercent / 100) * (months / 12);
}

/**
 * 적금 이자 (세전).
 *
 * 매달 같은 돈을 넣는 정액적립식으로 셈한다. 자유적립식도 같은 금리 표를 쓰므로
 * 매달 이만큼 넣는다고 보면 답이 같다.
 */
export function savingInterest(
  monthlyAmount: Man,
  annualPercent: number,
  months: number,
  type: RateType,
): Man {
  if (monthlyAmount <= 0 || months <= 0 || annualPercent <= 0) return 0;
  const rate = monthly(annualPercent);
  if (type === 'compound') {
    // Σ((1+i)^k − 1), k = 1..n 을 닫힌 꼴로 적은 것이다.
    const grown = Math.pow(1 + rate, months);
    return monthlyAmount * (((1 + rate) * (grown - 1)) / rate - months);
  }
  return monthlyAmount * rate * ((months * (months + 1)) / 2);
}

/** 종류에 맞는 이자 셈을 고른다. */
export function interestOf(
  kind: ProductKind,
  amount: Man,
  annualPercent: number,
  months: number,
  type: RateType,
): Man {
  return kind === 'deposit'
    ? depositInterest(amount, annualPercent, months, type)
    : savingInterest(amount, annualPercent, months, type);
}

/** 넣는 돈의 합. 적금은 매달 넣은 것이 쌓인다. */
export function principalOf(kind: ProductKind, amount: Man, months: number): Man {
  return kind === 'deposit' ? amount : amount * months;
}

// --- 고르기 ------------------------------------------------------------------

/** 가입 방법은 공시가 "인터넷,스마트폰" 처럼 붙여 준다. 한 쪽이라도 겹치면 된다. */
function reachable(product: Product, wanted: string[]): boolean {
  if (wanted.length === 0) return true;
  return product.joinWays.some((way) => wanted.some((pick) => way.includes(pick) || pick.includes(way)));
}

/**
 * 한도는 원 단위로 공시된다. 적금이면 **월 납입 한도** 이고 예금이면 예치 한도다.
 * 한도가 비어 있으면 밝히지 않은 것이니 막지 않는다.
 */
function withinLimit(product: Product, requirement: Requirement): boolean {
  if (product.maxLimit === null || product.maxLimit <= 0) return true;
  return requirement.amount <= product.maxLimit / MAN;
}

/**
 * 요건에 맞는 상품을 세후 이자가 많은 차례로 줄 세운다.
 *
 * 금리가 아니라 세후 이자로 줄 세우는 이유는 두 가지다. 단리와 월복리가 섞여
 * 있고, 적금은 같은 금리라도 예금의 절반쯤만 받기 때문이다. 사람이 알고 싶은
 * 것은 "어느 쪽이 더 주는가" 이지 "어느 쪽 숫자가 큰가" 가 아니다.
 */
export function recommend(products: Product[], requirement: Requirement): Recommendation {
  const skipped = { term: 0, channel: 0, limit: 0 };
  const offers: Offer[] = [];
  const groups = new Set(requirement.groups);
  const tax = 1 - Math.max(0, Math.min(100, requirement.taxRate)) / 100;

  const candidates = products.filter((product) => product.kind === requirement.kind && groups.has(product.group));

  for (const product of candidates) {
    // 같은 기간이라도 단리·복리 줄이 따로 있다. 그중 기본 금리가 가장 높은 것을 고른다.
    const matching = product.options.filter((option) => option.termMonths === requirement.termMonths);
    if (matching.length === 0) {
      skipped.term += 1;
      continue;
    }
    if (!reachable(product, requirement.joinWays)) {
      skipped.channel += 1;
      continue;
    }
    if (!withinLimit(product, requirement)) {
      skipped.limit += 1;
      continue;
    }

    let best: Offer | null = null;
    for (const option of matching) {
      const interest = interestOf(
        requirement.kind,
        requirement.amount,
        option.rate,
        option.termMonths,
        option.rateType,
      );
      const top = interestOf(
        requirement.kind,
        requirement.amount,
        option.topRate,
        option.termMonths,
        option.rateType,
      );
      const principal = principalOf(requirement.kind, requirement.amount, option.termMonths);
      const afterTaxInterest = interest * tax;
      const offer: Offer = {
        product,
        option,
        principal,
        interest,
        afterTaxInterest,
        maturity: principal + afterTaxInterest,
        afterTaxInterestTop: top * tax,
        effectiveAnnual:
          principal > 0 && option.termMonths > 0
            ? (afterTaxInterest / principal) * (12 / option.termMonths) * 100
            : 0,
      };
      if (!best || offer.afterTaxInterest > best.afterTaxInterest) best = offer;
    }
    if (best) offers.push(best);
  }

  offers.sort(
    (a, b) =>
      b.afterTaxInterest - a.afterTaxInterest ||
      b.afterTaxInterestTop - a.afterTaxInterestTop ||
      a.product.company.localeCompare(b.product.company, 'ko') ||
      a.product.name.localeCompare(b.product.name, 'ko'),
  );

  const months = offers
    .map((offer) => offer.product.disclosureMonth)
    .filter((month) => month !== '')
    .sort();

  return {
    offers,
    considered: candidates.length,
    skipped,
    disclosureMonth: months.length > 0 ? months[months.length - 1]! : null,
  };
}

/** 화면이 고를 수 있게, 자료에 실제로 있는 기간만 추려 준다. */
export function availableTerms(products: Product[], kind: ProductKind): number[] {
  const terms = new Set<number>();
  for (const product of products) {
    if (product.kind !== kind) continue;
    for (const option of product.options) terms.add(option.termMonths);
  }
  return [...terms].sort((a, b) => a - b);
}
