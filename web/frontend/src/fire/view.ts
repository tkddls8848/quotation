/**
 * FIRE 계산기 화면.
 *
 * 입력이 서른 개 남짓이라 HTML 에 손으로 적지 않고 **항목 정의에서 만들어
 * 낸다.** 그래야 모델(`model.ts`)에 항목이 하나 늘 때 고칠 자리가 한 군데로
 * 끝난다. 대신 각 항목은 문자열 경로가 아니라 get/set 함수로 모델에 닿는다 —
 * 오타가 나면 타입 검사에서 걸린다.
 *
 * 값이 바뀔 때마다 다시 셈한다. 한 번 셈하는 데 수십 밀리초라 <계산> 단추가
 * 필요 없다. 입력은 브라우저에 남겨 두어 새로 고쳐도 지워지지 않는다.
 */
import './fire.css';

import { FireInput, FireResult, Man, calculate, defaultInput } from './model';

const STORAGE_KEY = 'fire-input-v1';

// --- 서식 -------------------------------------------------------------------

/** 만원 단위 숫자를 한국 사람이 읽는 대로 적는다. */
export function formatMan(man: Man): string {
  const value = Math.round(Math.max(0, man));
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}경원`;
  if (value >= 10_000) {
    const eok = Math.floor(value / 10_000);
    const rest = value % 10_000;
    const head = eok >= 10_000 ? `${(eok / 10_000).toFixed(1)}조` : `${eok.toLocaleString()}억`;
    return rest > 0 && eok < 10_000 ? `${head} ${rest.toLocaleString()}만원` : `${head}원`;
  }
  return `${value.toLocaleString()}만원`;
}

/** 축 눈금처럼 자리가 좁은 곳에 쓰는 짧은 표기. */
function formatShort(man: Man): string {
  const value = Math.max(0, man);
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(1)}경`;
  if (value >= 1_000_000) return `${(value / 100_000_000 * 10_000).toFixed(0)}조`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(value >= 100_000 ? 0 : 1)}억`;
  return `${Math.round(value).toLocaleString()}만`;
}

/** 개월 수를 나이로 적는다. */
function formatAge(baseAge: number, months: number): string {
  const total = baseAge * 12 + months;
  const years = Math.floor(total / 12);
  const rest = Math.round(total % 12);
  return rest === 0 ? `${years}세` : `${years}세 ${rest}개월`;
}

// --- 입력 항목 ---------------------------------------------------------------

interface BaseField {
  id: string;
  label: string;
  /** 이 항목이 뜻이 있을 때만 보인다. */
  shownWhen?: (input: FireInput) => boolean;
  help?: string;
}

interface NumberField extends BaseField {
  kind: 'number';
  unit: string;
  step: number;
  min: number;
  get: (input: FireInput) => number;
  set: (input: FireInput, value: number) => void;
}

interface BoolField extends BaseField {
  kind: 'bool';
  get: (input: FireInput) => boolean;
  set: (input: FireInput, value: boolean) => void;
}

type Field = NumberField | BoolField;

interface Section {
  title: string;
  note?: string;
  fields: Field[];
  /** 자주 건드리지 않는 항목. 접어 둔다. */
  advanced?: Field[];
}

const num = (
  id: string,
  label: string,
  unit: string,
  step: number,
  get: NumberField['get'],
  set: NumberField['set'],
  extra: Partial<NumberField> = {},
): NumberField => ({ kind: 'number', id, label, unit, step, min: 0, get, set, ...extra });

const bool = (
  id: string,
  label: string,
  get: BoolField['get'],
  set: BoolField['set'],
): BoolField => ({ kind: 'bool', id, label, get, set });

/** 자산군 한 줄. 금액·이율·저축 배분이 나란히 선다. */
const ASSET_ROWS = [
  { id: 'deposit', label: '예금', rateLabel: '연 이자율', pick: (i: FireInput) => i.deposit },
  { id: 'installment', label: '적금', rateLabel: '연 이자율', pick: (i: FireInput) => i.installment },
  { id: 'bond', label: '채권', rateLabel: '연 수익률', pick: (i: FireInput) => i.bond },
  { id: 'equity', label: '배당주', rateLabel: '배당수익률', pick: (i: FireInput) => i.equity },
] as const;

const SECTIONS: Section[] = [
  {
    title: '나',
    fields: [
      num('age', '지금 나이', '세', 1, (i) => i.age, (i, v) => (i.age = v)),
      num('retireAge', '은퇴하고 싶은 나이', '세', 1, (i) => i.retireAge, (i, v) => (i.retireAge = v)),
      num('lifeAge', '돈이 버텨야 하는 나이', '세', 1, (i) => i.lifeAge, (i, v) => (i.lifeAge = v), {
        help: '기대 수명. 길게 잡을수록 보수적인 답이 나옵니다.',
      }),
    ],
  },
  {
    title: '매달 저축',
    note: '지금 실제로 남겨서 넣는 돈입니다. 은퇴 전까지 넣습니다.',
    fields: [
      num('monthlySaving', '월 저축액', '만원', 10, (i) => i.monthlySaving, (i, v) => (i.monthlySaving = v)),
    ],
    advanced: [
      num('savingGrowth', '저축액 연 증가율', '%', 0.5, (i) => i.savingGrowth, (i, v) => (i.savingGrowth = v), {
        help: '임금이 오르는 만큼 저축도 는다고 볼 때.',
      }),
    ],
  },
  {
    title: '은퇴 후 한 달 지출',
    note: '지금 물가, 1인 기준으로 적으십시오. 결혼·자녀·차는 아래에서 더합니다.',
    fields: [
      num('living', '생활비 (먹고 입고 쓰는 돈)', '만원', 10, (i) => i.living, (i, v) => (i.living = v)),
      num('housing', '주거비 (월세·관리비·재산세)', '만원', 5, (i) => i.housing, (i, v) => (i.housing = v)),
      num('medical', '의료비', '만원', 5, (i) => i.medical, (i, v) => (i.medical = v)),
      num('other', '그 밖 (여행·경조사·취미)', '만원', 5, (i) => i.other, (i, v) => (i.other = v)),
    ],
    advanced: [
      num('medicalOldAge', '의료비가 늘기 시작하는 나이', '세', 1, (i) => i.medicalOldAge, (i, v) => (i.medicalOldAge = v)),
      num('medicalOldFactor', '그 뒤 의료비 배수', '배', 0.1, (i) => i.medicalOldFactor, (i, v) => (i.medicalOldFactor = v)),
    ],
  },
  {
    title: '가족과 차',
    fields: [
      bool('married', '결혼했다 (또는 할 것이다)', (i) => i.married, (i, v) => (i.married = v)),
      num('children', '자녀 수', '명', 1, (i) => i.children, (i, v) => (i.children = v)),
      num('childCost', '자녀 한 명당 월 양육·교육비', '만원', 10, (i) => i.childCost, (i, v) => (i.childCost = v), {
        shownWhen: (i) => i.children > 0,
      }),
      num('childYoungestAge', '막내 나이', '세', 1, (i) => i.childYoungestAge, (i, v) => (i.childYoungestAge = v), {
        shownWhen: (i) => i.children > 0,
      }),
      bool('hasCar', '차를 유지한다', (i) => i.hasCar, (i, v) => (i.hasCar = v)),
      num('carMonthly', '차량 월 유지비 (기름·보험·정비)', '만원', 5, (i) => i.carMonthly, (i, v) => (i.carMonthly = v), {
        shownWhen: (i) => i.hasCar,
      }),
    ],
    advanced: [
      num('coupleFactor', '2인 가구 지출 배수', '배', 0.1, (i) => i.coupleFactor, (i, v) => (i.coupleFactor = v), {
        shownWhen: (i) => i.married,
        help: '둘이 살면 1인의 1.6배 남짓 듭니다. 방과 차를 같이 쓰기 때문입니다.',
      }),
      num('childUntilAge', '자녀를 몇 살까지 지원하나', '세', 1, (i) => i.childUntilAge, (i, v) => (i.childUntilAge = v), {
        shownWhen: (i) => i.children > 0,
      }),
      num('carReplaceCost', '차를 바꿀 때 드는 돈', '만원', 100, (i) => i.carReplaceCost, (i, v) => (i.carReplaceCost = v), {
        shownWhen: (i) => i.hasCar,
      }),
      num('carReplaceYears', '차 교체 주기', '년', 1, (i) => i.carReplaceYears, (i, v) => (i.carReplaceYears = v), {
        shownWhen: (i) => i.hasCar,
        help: '교체비를 주기로 나눠 매달 적립하는 셈으로 넣습니다.',
      }),
    ],
  },
  {
    title: '가정과 세금',
    fields: [
      num('inflation', '물가 상승률', '%', 0.1, (i) => i.inflation, (i, v) => (i.inflation = v)),
      num('swr', '안전 인출률', '%', 0.1, (i) => i.swr, (i, v) => (i.swr = v), {
        help: '참고선(FIRE 넘버)을 뽑는 데만 씁니다. 가능·불가 판정은 모의 실험이 합니다.',
      }),
      num('pensionMonthly', '국민연금 예상 월 수령액', '만원', 5, (i) => i.pensionMonthly, (i, v) => (i.pensionMonthly = v), {
        help: '지금 물가 기준. 국민연금은 물가에 연동해 오르므로 그렇게 셈합니다.',
      }),
      num('pensionStartAge', '연금 개시 나이', '세', 1, (i) => i.pensionStartAge, (i, v) => (i.pensionStartAge = v), {
        shownWhen: (i) => i.pensionMonthly > 0,
      }),
    ],
    advanced: [
      num('taxRate', '이자·배당 세율', '%', 0.1, (i) => i.taxRate, (i, v) => (i.taxRate = v), {
        help: '원천징수 15.4% = 소득세 14% + 지방소득세 1.4%.',
      }),
      bool('comprehensiveTax', '금융소득 종합과세를 반영한다', (i) => i.comprehensiveTax, (i, v) => (i.comprehensiveTax = v)),
      num('comprehensiveRate', '2,000만원 초과분 실효세율', '%', 0.1, (i) => i.comprehensiveRate, (i, v) => (i.comprehensiveRate = v), {
        shownWhen: (i) => i.comprehensiveTax,
      }),
    ],
  },
];

// --- 조립 -------------------------------------------------------------------

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

function numberInput(id: string, value: number, step: number, min: number): HTMLInputElement {
  const input = create('input');
  input.type = 'number';
  input.id = id;
  input.step = String(step);
  input.min = String(min);
  input.value = String(Number(value.toFixed(4)));
  input.inputMode = 'decimal';
  return input;
}

export function mountFire(root: HTMLElement): void {
  const input = load();
  const rows: Array<{ field: Field; row: HTMLElement }> = [];
  let redraw = (): void => {};

  const changed = (): void => {
    save(input);
    for (const { field, row } of rows) {
      row.hidden = field.shownWhen ? !field.shownWhen(input) : false;
    }
    redraw();
  };

  const form = create('form', 'fire__form');
  form.noValidate = true;
  form.addEventListener('submit', (event) => event.preventDefault());

  const fieldRow = (field: Field): HTMLElement => {
    const row = create('div', 'field');
    const label = create('label', 'field__label', field.label);
    label.htmlFor = `fire-${field.id}`;

    if (field.kind === 'bool') {
      row.classList.add('field--bool');
      const box = create('input');
      box.type = 'checkbox';
      box.id = `fire-${field.id}`;
      box.checked = field.get(input);
      box.addEventListener('change', () => {
        field.set(input, box.checked);
        changed();
      });
      row.append(box, label);
    } else {
      const control = create('div', 'field__control');
      const box = numberInput(`fire-${field.id}`, field.get(input), field.step, field.min);
      box.addEventListener('input', () => {
        const value = Number(box.value);
        field.set(input, Number.isFinite(value) ? value : 0);
        changed();
      });
      control.append(box, create('span', 'field__unit', field.unit));
      row.append(label, control);
    }

    if (field.help) row.append(create('p', 'field__help', field.help));
    rows.push({ field, row });
    return row;
  };

  // 자산은 표로 세운다 — 네 자산군을 같은 잣대로 견주어 보는 게 요점이다.
  const assetCard = create('fieldset', 'card');
  assetCard.append(create('legend', 'card__title', '모은 돈'));
  assetCard.append(
    create('p', 'card__note', '자산군마다 금액과 이율을 따로 적습니다. 마지막 칸은 매달 저축하는 돈을 어디에 넣을지의 비율이고, 합이 100% 가 되어야 합니다.'),
  );
  const table = create('div', 'assets');
  table.append(
    create('span', 'assets__head', ''),
    create('span', 'assets__head', '지금 금액 (만원)'),
    create('span', 'assets__head', '연 이율 (%)'),
    create('span', 'assets__head', '저축 배분 (%)'),
  );
  for (const asset of ASSET_ROWS) {
    table.append(create('span', 'assets__label', asset.label));
    const amount = numberInput(`fire-${asset.id}-amount`, asset.pick(input).amount, 100, 0);
    const rate = numberInput(`fire-${asset.id}-rate`, asset.pick(input).rate, 0.1, 0);
    const alloc = numberInput(`fire-${asset.id}-alloc`, asset.pick(input).allocation, 5, 0);
    amount.setAttribute('aria-label', `${asset.label} 금액`);
    rate.setAttribute('aria-label', `${asset.label} ${asset.rateLabel}`);
    alloc.setAttribute('aria-label', `${asset.label} 저축 배분`);
    amount.addEventListener('input', () => {
      asset.pick(input).amount = Number(amount.value) || 0;
      changed();
    });
    rate.addEventListener('input', () => {
      asset.pick(input).rate = Number(rate.value) || 0;
      changed();
    });
    alloc.addEventListener('input', () => {
      asset.pick(input).allocation = Number(alloc.value) || 0;
      changed();
    });
    table.append(amount, rate, alloc);
  }
  assetCard.append(table);
  assetCard.append(
    fieldRow(
      num('equityGrowth', '배당주 주가 상승률', '%', 0.5, (i) => i.equityGrowth, (i, v) => (i.equityGrowth = v), {
        help: '배당과 따로 셉니다. 국내 상장주식은 소액주주면 차익이 비과세라 세금을 매기지 않습니다 — 해외 주식·ETF 라면 양도세 22% 만큼 낮춰 넣으십시오.',
      }),
    ),
  );

  for (const [index, section] of SECTIONS.entries()) {
    const card = create('fieldset', 'card');
    card.append(create('legend', 'card__title', section.title));
    if (section.note) card.append(create('p', 'card__note', section.note));
    for (const field of section.fields) card.append(fieldRow(field));
    if (section.advanced?.length) {
      const more = create('details', 'more');
      more.append(create('summary', 'more__summary', '세부 조정'));
      for (const field of section.advanced) more.append(fieldRow(field));
      card.append(more);
    }
    form.append(card);
    // 자산 표는 "나" 다음에 놓는다.
    if (index === 0) form.append(assetCard);
  }

  const reset = create('button', 'fire__reset', '기본값으로 되돌리기');
  reset.type = 'button';
  reset.addEventListener('click', () => {
    Object.assign(input, defaultInput());
    root.replaceChildren();
    clear();
    mountFire(root);
  });
  form.append(reset);

  const result = create('aside', 'fire__result');
  result.setAttribute('aria-live', 'polite');

  const body = create('div', 'fire__body');
  body.append(form, result);
  root.replaceChildren(body);

  redraw = () => drawResult(result, input, calculate(input));
  changed();
}

// --- 결과 -------------------------------------------------------------------

const VERDICT: Record<FireResult['verdict'], { badge: string; tone: string }> = {
  possible: { badge: 'FIRE 가능', tone: 'ok' },
  late: { badge: '목표보다 늦습니다', tone: 'warn' },
  impossible: { badge: '지금 조건으로는 어렵습니다', tone: 'bad' },
};

function headline(input: FireInput, result: FireResult): string {
  if (result.earliestMonths === null) {
    return '어느 나이에 은퇴해도 기대 수명까지 돈이 버티지 못합니다. 지출을 줄이거나 저축을 늘려야 합니다.';
  }
  const when = formatAge(input.age, result.earliestMonths);
  if (result.verdict === 'possible') {
    return result.earliestMonths === 0
      ? '지금 가진 것만으로 은퇴해도 기대 수명까지 버팁니다.'
      : `${when}부터 은퇴할 수 있습니다. 목표는 ${Math.round(input.retireAge)}세입니다.`;
  }
  return `가장 이른 은퇴 시점은 ${when}입니다. 목표한 ${Math.round(input.retireAge)}세보다 늦습니다.`;
}

function statTile(label: string, value: string, note?: string): HTMLElement {
  const tile = create('div', 'stat');
  tile.append(create('span', 'stat__label', label));
  tile.append(create('strong', 'stat__value', value));
  if (note) tile.append(create('span', 'stat__note', note));
  return tile;
}

function drawResult(root: HTMLElement, input: FireInput, result: FireResult): void {
  const verdict = VERDICT[result.verdict];
  const box = create('div', 'verdict');
  box.dataset.tone = verdict.tone;
  box.append(create('strong', 'verdict__badge', verdict.badge));
  box.append(create('p', 'verdict__line', headline(input, result)));

  const stats = create('div', 'stats');
  stats.append(
    statTile(
      `${Math.round(input.retireAge)}세 예상 자산`,
      formatMan(result.assetsAtRetire),
      '지금 저축을 그대로 이어갈 때',
    ),
  );
  stats.append(
    statTile(
      `${Math.round(input.retireAge)}세에 필요한 돈`,
      formatMan(result.targetAtRetire),
      `인출률 ${input.swr}% 기준 참고선`,
    ),
  );
  stats.append(
    statTile('은퇴 후 한 달 지출', formatMan(result.monthlySpendToday), '지금 물가 기준'),
  );
  stats.append(
    statTile(
      '목표를 지키려면 월 저축',
      result.requiredMonthlySaving === null
        ? '불가능'
        : formatMan(result.requiredMonthlySaving),
      result.requiredMonthlySaving === null
        ? '은퇴까지 남은 기간이 너무 짧습니다'
        : `지금은 ${formatMan(input.monthlySaving)}`,
    ),
  );

  const parts: HTMLElement[] = [box, stats, chart(input, result)];

  if (result.depletionAge !== null) {
    const note = create(
      'p',
      'note note--bad',
      `목표한 ${Math.round(input.retireAge)}세에 은퇴하면 ${Math.round(result.depletionAge)}세에 자산이 바닥납니다.`,
    );
    parts.push(note);
  }

  if (result.shortfall > 0) {
    parts.push(
      create(
        'p',
        'note',
        `참고선까지 ${formatMan(result.shortfall)} 모자랍니다. 지금 물가로 치면 FIRE 넘버는 ${formatMan(result.fireNumberToday)}입니다.`,
      ),
    );
  }

  if (result.warnings.length) {
    const list = create('ul', 'warnings');
    for (const warning of result.warnings) list.append(create('li', '', warning));
    const wrap = create('details', 'more');
    wrap.append(create('summary', 'more__summary', `짚어 둘 것 ${result.warnings.length}가지`));
    wrap.append(list);
    parts.push(wrap);
  }

  parts.push(
    create(
      'p',
      'note note--muted',
      '판정은 은퇴 시점부터 기대 수명까지 매달 물가만큼 더 쓰고 남은 자산을 세후 수익률로 굴리는 모의 실험으로 합니다. 4% 규칙은 참고선으로만 보여 줍니다.',
    ),
  );

  root.replaceChildren(...parts);
}

// --- 그래프 -----------------------------------------------------------------

const CHART = { width: 620, height: 260, left: 64, right: 64, top: 18, bottom: 30 };
const SERIES = {
  assets: { color: 'var(--accent)', label: '내 자산' },
  target: { color: 'var(--danger)', label: '필요한 돈' },
};

/**
 * 자산 궤적과 필요액을 한 그림에 둔다.
 *
 * 두 선의 단위가 같으므로 축은 하나다. 색만으로 구분하지 않도록 필요액은 점선에
 * 직접 이름을 달았다 — 회색 기준선은 파랑과 구분이 안 돼서(정상 시력에서도
 * 색 거리가 모자란다) 쓰지 않는다.
 */
function chart(input: FireInput, result: FireResult): HTMLElement {
  const { width, height, left, right, top, bottom } = CHART;
  const points = result.path;
  const figure = create('figure', 'chart');

  if (points.length < 2) return figure;

  const maxY = Math.max(...points.map((p) => Math.max(p.assets, p.target)), 1);
  const minAge = points[0]!.age;
  const maxAge = points[points.length - 1]!.age;
  const x = (age: number) => left + ((age - minAge) / (maxAge - minAge)) * (width - left - right);
  const y = (value: number) => height - bottom - (value / maxY) * (height - top - bottom);

  const line = (pick: (p: (typeof points)[number]) => number): string =>
    points.map((p, i) => `${i === 0 ? 'M' : 'L'}${x(p.age).toFixed(1)} ${y(pick(p)).toFixed(1)}`).join(' ');

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('class', 'chart__svg');
  svg.setAttribute('role', 'img');
  svg.setAttribute(
    'aria-label',
    `${minAge}세부터 ${maxAge}세까지 자산과 필요액. ${Math.round(input.retireAge)}세 자산 ${formatMan(result.assetsAtRetire)}, 필요액 ${formatMan(result.targetAtRetire)}.`,
  );

  const add = (tag: string, attrs: Record<string, string>, text?: string): SVGElement => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    if (text !== undefined) node.textContent = text;
    svg.append(node);
    return node;
  };

  // 눈금은 뒤로 물러나 있어야 한다.
  for (const fraction of [0, 0.5, 1]) {
    const value = maxY * fraction;
    add('line', {
      x1: String(left),
      x2: String(width - right),
      y1: y(value).toFixed(1),
      y2: y(value).toFixed(1),
      class: 'chart__grid',
    });
    add(
      'text',
      { x: String(left - 8), y: (y(value) + 4).toFixed(1), class: 'chart__tick', 'text-anchor': 'end' },
      fraction === 0 ? '0' : formatShort(value),
    );
  }

  const step = maxAge - minAge > 40 ? 10 : 5;
  for (let age = Math.ceil(minAge / step) * step; age <= maxAge; age += step) {
    add(
      'text',
      { x: x(age).toFixed(1), y: String(height - 8), class: 'chart__tick', 'text-anchor': 'middle' },
      String(age),
    );
  }

  // 목표 은퇴 나이.
  if (input.retireAge > minAge && input.retireAge < maxAge) {
    add('line', {
      x1: x(input.retireAge).toFixed(1),
      x2: x(input.retireAge).toFixed(1),
      y1: String(top),
      y2: String(height - bottom),
      class: 'chart__marker',
    });
    add(
      'text',
      { x: (x(input.retireAge) + 5).toFixed(1), y: String(top + 10), class: 'chart__tick' },
      `목표 ${Math.round(input.retireAge)}세`,
    );
  }

  add('path', { d: line((p) => p.target), class: 'chart__line chart__line--target' });
  add('path', { d: line((p) => p.assets), class: 'chart__line chart__line--assets' });

  // 선 끝에 이름을 직접 단다. 색만으로 구분하지 않기 위함이다.
  const last = points[points.length - 1]!;
  add(
    'text',
    { x: String(width - right + 6), y: (y(last.assets) + 4).toFixed(1), class: 'chart__label chart__label--assets' },
    SERIES.assets.label,
  );
  add(
    'text',
    { x: String(width - right + 6), y: (y(last.target) + 4).toFixed(1), class: 'chart__label chart__label--target' },
    SERIES.target.label,
  );

  // 은퇴 가능 시점.
  if (result.earliestMonths !== null) {
    const age = input.age + result.earliestMonths / 12;
    const point = points.find((p) => p.age >= age) ?? last;
    add('circle', {
      cx: x(age).toFixed(1),
      cy: y(point.assets).toFixed(1),
      r: '5',
      class: 'chart__dot',
    });
  }

  figure.append(svg);
  figure.append(
    create(
      'figcaption',
      'chart__caption',
      result.earliestMonths === null
        ? '자산(파랑)이 필요액(살구 점선)을 끝내 넘지 못합니다.'
        : `자산(파랑)이 필요액(살구 점선)을 넘어서는 시점이 ${formatAge(input.age, result.earliestMonths)}입니다.`,
    ),
  );

  // 그림을 못 보는 경우를 위해 같은 내용을 표로도 둔다.
  const table = create('details', 'more');
  table.append(create('summary', 'more__summary', '숫자로 보기'));
  const grid = create('div', 'chart__table');
  grid.append(
    create('span', 'chart__th', '나이'),
    create('span', 'chart__th', '자산'),
    create('span', 'chart__th', '필요액'),
  );
  for (const point of points.filter((_, index) => index % 5 === 0)) {
    grid.append(
      create('span', '', `${Math.round(point.age)}세`),
      create('span', '', formatMan(point.assets)),
      create('span', '', formatMan(point.target)),
    );
  }
  table.append(grid);
  figure.append(table);
  return figure;
}

// --- 저장 -------------------------------------------------------------------

function load(): FireInput {
  const fallback = defaultInput();
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return fallback;
    const parsed = JSON.parse(saved) as Partial<FireInput>;
    // 항목이 늘어난 뒤에도 예전 저장본이 열리도록 기본값 위에 덮는다.
    return { ...fallback, ...parsed };
  } catch {
    return fallback;
  }
}

function save(input: FireInput): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(input));
  } catch {
    // 사생활 보호 모드처럼 저장이 막힌 곳이다. 계산에는 지장이 없다.
  }
}

function clear(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // 위와 같다.
  }
}
