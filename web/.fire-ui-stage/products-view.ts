/**
 * 예적금 상품 추천 화면.
 *
 * 계산기가 "얼마를 모아야 하는가" 를 말해 주면, 이 칸은 "그 돈을 지금 어디에
 * 넣을 수 있는가" 를 말한다. 금리를 우리가 적어 두지 않고 금융감독원 공시를
 * 그때그때 받아 온다 (`products.ts`).
 *
 * ── 왜 단추를 눌러야 불러오는가 ──────────────────────────────────────────
 *
 * 계산기 탭을 여는 것만으로 공시를 받지 않는다. 은퇴 시점만 보러 온 사람에게
 * 수백 개의 상품을 내려받게 할 이유가 없고, 셸의 Worker 도 그때는 깨어나지
 * 않는 편이 낫기 때문이다 (wrangler.jsonc 의 근거). 한 번 받은 것은 이 탭이
 * 열려 있는 동안 들고 있어서, 기간이나 금액을 바꿔 볼 때는 다시 받지 않는다.
 *
 * ── 이 칸은 계산기의 값을 바꾸지 않는다 ──────────────────────────────────
 *
 * 세율 하나만 계산기에서 받아 쓴다 (같은 세금을 두 군데에 적게 할 수 없다).
 * 반대 방향으로는 아무것도 흐르지 않는다 — 상품을 골랐다고 계산기의 이율이
 * 바뀌지는 않는다. 공시 금리는 지금 가입할 수 있는 금리이고 계산기의 이율은
 * 앞으로 수십 년의 가정이라, 둘은 같은 숫자가 아니다.
 */

import {
  FinanceGroup,
  GROUP_LABEL,
  KIND_LABEL,
  Product,
  ProductKind,
  ProductsError,
  fetchProducts,
} from './products';
import { Offer, Requirement, availableTerms, recommend } from './recommend';

const STORAGE_KEY = 'fire-products-v1';

/** 자료를 받기 전에도 기간을 고를 수 있어야 한다. 흔한 기간을 미리 둔다. */
const FALLBACK_TERMS = [3, 6, 12, 24, 36];

/** 공시가 쓰는 가입 방법 이름. 여기 적은 말이 상품의 join_way 와 맞붙는다. */
const CHANNELS = ['영업점', '인터넷', '스마트폰'];

const GROUPS: FinanceGroup[] = ['bank', 'savingsbank'];

/** 한 번에 보여 주는 상품 수. 더 내려가 봐야 금리 차가 의미를 잃는다. */
const SHOWN = 20;

interface Choice {
  kind: ProductKind;
  termMonths: number;
  /**
   * 넣을 돈. 종류마다 따로 들고 있는다 — 정기예금의 "한 번에 넣을 돈" 과 적금의
   * "매달 넣을 돈" 은 자릿수가 다르다. 하나로 두면 종류를 바꾸는 순간 1,000만원이
   * 말없이 월 납입액이 되어, 사람이 넣은 적 없는 조건으로 줄을 세우게 된다.
   */
  amounts: Record<ProductKind, number>;
  channels: string[];
  groups: FinanceGroup[];
}

const create = <K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

/** 만원 단위 금액. 이자는 몇만원 단위라 소수 첫째 자리까지 적는다. */
function amount(man: number): string {
  if (Math.abs(man) >= 10_000) {
    const eok = Math.floor(man / 10_000);
    const rest = Math.round(man % 10_000);
    return rest > 0 ? `${eok.toLocaleString()}억 ${rest.toLocaleString()}만원` : `${eok.toLocaleString()}억원`;
  }
  if (Math.abs(man) >= 100) return `${Math.round(man).toLocaleString()}만원`;
  return `${man.toFixed(1)}만원`;
}

/** 공시월 202609 → 2026년 9월. */
function month(value: string | null): string {
  if (!value || value.length < 6) return '';
  return `${value.slice(0, 4)}년 ${Number(value.slice(4, 6))}월`;
}

const defaults = (): Choice => ({
  kind: 'deposit',
  termMonths: 12,
  amounts: { deposit: 1000, saving: 50 },
  channels: [],
  groups: ['bank'],
});

function load(): Choice {
  const fallback = defaults();
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return fallback;
    const parsed = JSON.parse(saved) as Partial<Choice>;
    // 항목이 바뀐 뒤에도 예전 저장본이 열리도록 기본값 위에 덮는다.
    return { ...fallback, ...parsed, amounts: { ...fallback.amounts, ...parsed.amounts } };
  } catch {
    return fallback;
  }
}

function save(choice: Choice): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(choice));
  } catch {
    // 사생활 보호 모드처럼 저장이 막힌 곳이다. 고르는 데에는 지장이 없다.
  }
}

/**
 * 추천 칸을 세운다.
 *
 * @param taxRate 계산기가 쓰는 이자소득세율을 그때그때 물어보는 함수.
 */
export function mountProducts(root: HTMLElement, taxRate: () => number): void {
  const choice = load();

  // 받아 둔 상품. 종류·금융권마다 한 번만 받는다.
  const held = new Map<string, Product[]>();
  let loading = false;
  let failures: ProductsError[] = [];

  const section = create('section', 'products');
  const head = create('div', 'products__head');
  head.append(create('h2', 'products__title', '지금 가입할 수 있는 예적금'));
  head.append(
    create(
      'p',
      'products__note',
      '금융감독원 금융상품 통합 비교공시에서 은행·저축은행의 정기예금과 적금을 받아, 넣을 돈과 기간으로 세금을 뗀 이자를 셈해 많이 주는 차례로 보여 줍니다. 금리는 공시 기준이라 실제 가입 조건은 해당 금융회사에서 확인해야 합니다.',
    ),
  );
  section.append(head);

  const form = create('form', 'products__form');
  form.noValidate = true;
  form.addEventListener('submit', (event) => event.preventDefault());

  const list = create('div', 'products__list');
  list.setAttribute('aria-live', 'polite');

  // --- 고르는 칸 -------------------------------------------------------------

  const kindGroup = create('div', 'products__field');
  kindGroup.append(create('span', 'products__label', '종류'));
  const kindRow = create('div', 'products__choices');
  const kindInputs: HTMLInputElement[] = [];
  for (const kind of ['deposit', 'saving'] as ProductKind[]) {
    const id = `fire-kind-${kind}`;
    const box = create('input');
    box.type = 'radio';
    box.name = 'fire-product-kind';
    box.id = id;
    box.value = kind;
    box.checked = choice.kind === kind;
    box.addEventListener('change', () => {
      if (!box.checked) return;
      choice.kind = kind;
      changed();
    });
    const label = create('label', 'products__choice', KIND_LABEL[kind]);
    label.htmlFor = id;
    kindInputs.push(box);
    kindRow.append(box, label);
  }
  kindGroup.append(kindRow);

  const amountField = create('div', 'products__field');
  const amountLabel = create('label', 'products__label');
  amountLabel.htmlFor = 'fire-product-amount';
  const amountBox = create('input');
  amountBox.type = 'number';
  amountBox.id = 'fire-product-amount';
  amountBox.min = '0';
  amountBox.step = '100';
  amountBox.inputMode = 'decimal';
  amountBox.addEventListener('input', () => {
    choice.amounts[choice.kind] = Math.max(0, Number(amountBox.value) || 0);
    changed();
  });
  const amountControl = create('div', 'products__control');
  amountControl.append(amountBox, create('span', 'products__unit', '만원'));
  amountField.append(amountLabel, amountControl);

  const termField = create('div', 'products__field');
  const termLabel = create('label', 'products__label', '기간');
  termLabel.htmlFor = 'fire-product-term';
  const termBox = create('select');
  termBox.id = 'fire-product-term';
  termBox.addEventListener('change', () => {
    choice.termMonths = Number(termBox.value) || 12;
    changed();
  });
  const termControl = create('div', 'products__control');
  termControl.append(termBox);
  termField.append(termLabel, termControl);

  const fillTerms = (): void => {
    const products = gathered();
    const terms = products.length > 0 ? availableTerms(products, choice.kind) : FALLBACK_TERMS;
    const usable = terms.length > 0 ? terms : FALLBACK_TERMS;
    if (!usable.includes(choice.termMonths)) {
      choice.termMonths = usable.includes(12) ? 12 : usable[0]!;
    }
    termBox.replaceChildren(
      ...usable.map((term) => {
        const item = create('option', undefined, `${term}개월`);
        item.value = String(term);
        item.selected = term === choice.termMonths;
        return item;
      }),
    );
  };

  const checkRow = (
    title: string,
    items: { value: string; label: string }[],
    picked: () => string[],
    toggle: (value: string, on: boolean) => void,
    note?: string,
  ): HTMLElement => {
    const field = create('div', 'products__field');
    field.append(create('span', 'products__label', title));
    const row = create('div', 'products__choices');
    for (const item of items) {
      const id = `fire-pick-${title}-${item.value}`;
      const box = create('input');
      box.type = 'checkbox';
      box.id = id;
      box.checked = picked().includes(item.value);
      box.addEventListener('change', () => {
        toggle(item.value, box.checked);
        changed();
      });
      const label = create('label', 'products__choice', item.label);
      label.htmlFor = id;
      row.append(box, label);
    }
    field.append(row);
    if (note) field.append(create('p', 'products__hint', note));
    return field;
  };

  const channelField = checkRow(
    '가입 방법',
    CHANNELS.map((channel) => ({ value: channel, label: channel })),
    () => choice.channels,
    (value, on) => {
      choice.channels = on ? [...choice.channels, value] : choice.channels.filter((item) => item !== value);
    },
    '고르지 않으면 가리지 않습니다.',
  );

  const groupField = checkRow(
    '금융권',
    GROUPS.map((group) => ({ value: group, label: GROUP_LABEL[group] })),
    () => choice.groups,
    (value, on) => {
      const group = value as FinanceGroup;
      choice.groups = on ? [...choice.groups, group] : choice.groups.filter((item) => item !== group);
    },
    '저축은행은 금리가 높은 대신 예금자보호 한도를 금융회사마다 따로 봅니다.',
  );

  const load_ = create('button', 'products__load', '상품 불러오기');
  load_.type = 'button';
  load_.addEventListener('click', () => void pull());

  form.append(kindGroup, amountField, termField, channelField, groupField, load_);
  section.append(form, list);
  root.replaceChildren(section);

  // --- 받아 오기 -------------------------------------------------------------

  const gathered = (): Product[] => {
    const out: Product[] = [];
    for (const group of choice.groups) {
      out.push(...(held.get(`${choice.kind}:${group}`) ?? []));
    }
    return out;
  };

  /** 아직 받지 않은 조합만 받는다. */
  const missing = (): FinanceGroup[] => choice.groups.filter((group) => !held.has(`${choice.kind}:${group}`));

  async function pull(): Promise<void> {
    const wanted = missing();
    if (loading || wanted.length === 0) {
      draw();
      return;
    }
    loading = true;
    failures = [];
    draw();

    const answer = await fetchProducts({ kind: choice.kind, groups: wanted });
    // 성공한 권역만 담는다. 실패한 쪽은 비워 두어 다시 누르면 다시 받게 한다.
    for (const [group, products] of answer.byGroup) held.set(`${choice.kind}:${group}`, products);
    failures = answer.failures.map((failure) => failure.error);
    loading = false;
    fillTerms();
    draw();
  }

  function changed(): void {
    save(choice);
    for (const box of kindInputs) box.checked = box.value === choice.kind;
    amountLabel.textContent = choice.kind === 'deposit' ? '한 번에 넣을 돈' : '매달 넣을 돈';
    // 고른 종류의 금액을 칸에 되돌려 놓는다. 사람이 적고 있는 중이면 건드리지 않는다.
    const shownAmount = String(choice.amounts[choice.kind]);
    if (document.activeElement !== amountBox && amountBox.value !== shownAmount) {
      amountBox.value = shownAmount;
    }
    load_.hidden = missing().length === 0;
    fillTerms();
    draw();
  }

  // --- 그리기 ---------------------------------------------------------------

  function draw(): void {
    const parts: HTMLElement[] = [];

    if (failures.length > 0) {
      for (const failure of failures) {
        parts.push(create('p', 'products__message products__message--bad', failure.message));
      }
    }

    if (loading) {
      parts.push(create('p', 'products__message', '상품 공시를 불러오는 중입니다…'));
      list.replaceChildren(...parts);
      return;
    }

    const products = gathered();
    if (products.length === 0) {
      if (choice.groups.length === 0) {
        parts.push(create('p', 'products__message', '금융권을 하나 이상 고르십시오.'));
      } else if (failures.length === 0) {
        parts.push(
          create(
            'p',
            'products__message',
            '<상품 불러오기> 를 누르면 그때 공시를 받아 옵니다. 계산기만 쓰러 온 사람에게 상품 목록까지 내려받게 하지 않으려는 것입니다.',
          ),
        );
      }
      list.replaceChildren(...parts);
      return;
    }

    const requirement: Requirement = {
      kind: choice.kind,
      termMonths: choice.termMonths,
      amount: choice.amounts[choice.kind],
      joinWays: choice.channels,
      groups: choice.groups,
      taxRate: taxRate(),
    };
    const result = recommend(products, requirement);

    const summary = create('p', 'products__summary');
    if (result.offers.length === 0) {
      summary.textContent =
        `요건에 맞는 상품이 없습니다. ${KIND_LABEL[choice.kind]} ${result.considered}개 중 ` +
        `${result.skipped.term}개는 ${choice.termMonths}개월 금리가 없고, ` +
        `${result.skipped.channel}개는 고른 방법으로 가입할 수 없으며, ` +
        `${result.skipped.limit}개는 한도를 넘습니다.`;
      list.replaceChildren(...parts, summary);
      return;
    }

    const shown = result.offers.slice(0, SHOWN);
    summary.textContent =
      `${KIND_LABEL[choice.kind]} ${result.considered}개 중 요건에 맞는 ${result.offers.length}개를 ` +
      `세후 이자가 많은 차례로 ${shown.length}개 보여 줍니다` +
      (result.disclosureMonth ? ` (${month(result.disclosureMonth)} 공시).` : '.');
    parts.push(summary);
    parts.push(table(shown, requirement));

    const tail = create(
      'p',
      'products__message products__message--muted',
      choice.kind === 'deposit'
        ? '세후 이자는 이자소득세 ' + taxRate().toFixed(1) + '% 를 뗀 값입니다. 만기까지 넣어 둔다고 봅니다.'
        : '적금 이자는 회차마다 남은 개월만큼만 붙습니다 — 같은 금리라도 예금에 한꺼번에 넣은 것의 절반 남짓입니다. ' +
          '세후 이자는 이자소득세 ' + taxRate().toFixed(1) + '% 를 뗀 값입니다.',
    );
    parts.push(tail);
    list.replaceChildren(...parts);
  }

  function table(offers: Offer[], requirement: Requirement): HTMLElement {
    const wrap = create('div', 'products__table-wrap');
    const table_ = create('table', 'products__table');
    const head_ = create('thead');
    const headRow = create('tr');
    for (const [title, className] of [
      ['금융회사·상품', ''],
      ['금리', 'products__num'],
      ['세후 이자', 'products__num'],
      ['만기 수령액', 'products__num'],
    ] as const) {
      const cell = create('th', className, title);
      cell.scope = 'col';
      headRow.append(cell);
    }
    head_.append(headRow);

    const body = create('tbody');
    for (const offer of offers) {
      const row = create('tr');

      const first = create('td');
      first.append(create('strong', 'products__company', `${offer.product.company} ${offer.product.name}`));
      const marks = create('p', 'products__marks');
      marks.append(create('span', 'products__mark', GROUP_LABEL[offer.product.group]));
      marks.append(
        create('span', 'products__mark', offer.option.rateType === 'compound' ? '월복리' : '단리'),
      );
      if (offer.option.reserveType) {
        marks.append(
          create('span', 'products__mark', offer.option.reserveType === 'free' ? '자유적립' : '정액적립'),
        );
      }
      if (offer.product.joinDeny !== '1') {
        marks.append(
          create('span', 'products__mark', offer.product.joinDeny === '2' ? '서민 전용' : '가입 제한'),
        );
      }
      if (offer.product.joinWays.length > 0) {
        marks.append(create('span', 'products__mark products__mark--plain', offer.product.joinWays.join('·')));
      }
      first.append(marks);
      if (offer.product.special && offer.product.special !== '해당사항 없음') {
        first.append(create('p', 'products__special', `우대: ${offer.product.special}`));
      }

      const rate = create('td', 'products__num');
      rate.append(create('strong', '', `${offer.option.rate.toFixed(2)}%`));
      if (offer.option.topRate > offer.option.rate) {
        rate.append(create('span', 'products__sub', `우대 시 ${offer.option.topRate.toFixed(2)}%`));
      }

      const interest = create('td', 'products__num');
      interest.append(create('strong', '', amount(offer.afterTaxInterest)));
      interest.append(create('span', 'products__sub', `연 ${offer.effectiveAnnual.toFixed(2)}% 꼴`));
      if (offer.afterTaxInterestTop > offer.afterTaxInterest) {
        interest.append(create('span', 'products__sub', `우대 시 ${amount(offer.afterTaxInterestTop)}`));
      }

      const maturity = create('td', 'products__num');
      maturity.append(create('strong', '', amount(offer.maturity)));
      maturity.append(create('span', 'products__sub', `원금 ${amount(offer.principal)}`));

      row.append(first, rate, interest, maturity);
      body.append(row);
    }

    table_.append(head_, body);
    const caption = create(
      'caption',
      'products__caption',
      `${KIND_LABEL[requirement.kind]} ${requirement.termMonths}개월, ` +
        (requirement.kind === 'deposit'
          ? `${amount(requirement.amount)} 예치 기준`
          : `매달 ${amount(requirement.amount)} 납입 기준`),
    );
    table_.prepend(caption);
    wrap.append(table_);
    return wrap;
  }

  changed();
}
