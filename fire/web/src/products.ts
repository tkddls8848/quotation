/**
 * 예적금 상품 공시 — 받아 오고, 읽어서 쓸 수 있는 모양으로 만든다.
 *
 * 자료는 금융감독원 **금융상품 통합 비교공시** 다. 은행과 저축은행이 파는
 * 정기예금·적금이 전부 들어 있고, 한 달에 한 번 갱신된다. 우리가 목록을 손으로
 * 적어 두지 않는 이유가 이것이다 — 손으로 적은 금리는 적는 순간 낡는다.
 *
 * 브라우저는 그 API 를 바로 부를 수 없다 (인증키·CORS). 그래서 셸의 Worker 를
 * 거친다 (`fire/worker/products.ts`). 거기서는 키만 붙여 넘기고, **읽어서 합치는
 * 일은 여기서 한다** — 무료 계정 Worker 의 CPU 한도를 쓰지 않기 위함이다.
 *
 * ── 공시가 주는 모양 ──────────────────────────────────────────────────────
 *
 * 상품 하나는 두 곳에 나뉘어 있다.
 *
 *   baseList    상품 그 자체 — 회사 이름, 상품 이름, 가입 방법, 우대조건, 한도
 *   optionList  같은 상품의 **기간별 금리** — 6개월 2.8%, 12개월 3.1% …
 *
 * 둘을 회사 번호(fin_co_no)와 상품 코드(fin_prdt_cd)로 맞붙여야 비로소 "이 상품을
 * 12개월 넣으면 몇 %" 를 말할 수 있다. 그 이음매가 이 파일의 일이다.
 */

/** 정기예금인가 적금인가. Worker 의 창구 이름과 같은 말을 쓴다. */
export type ProductKind = 'deposit' | 'saving';

/** 어느 금융권인가. 예금자보호가 되는 두 권역만 다룬다. */
export type FinanceGroup = 'bank' | 'savingsbank';

export const GROUP_LABEL: Record<FinanceGroup, string> = {
  bank: '은행',
  savingsbank: '저축은행',
};

export const KIND_LABEL: Record<ProductKind, string> = {
  deposit: '정기예금',
  saving: '적금',
};

/** 단리인가 월복리인가. 같은 금리라도 받는 이자가 달라진다. */
export type RateType = 'simple' | 'compound';

/** 적금의 적립 방식. 정액은 매달 같은 돈을, 자유는 형편대로 넣는다. */
export type ReserveType = 'fixed' | 'free';

/** 한 상품의 기간별 금리 한 줄. */
export interface ProductOption {
  /** 저축 기간 (개월). */
  termMonths: number;
  rateType: RateType;
  /** 기본 금리 %. 아무 조건도 채우지 못했을 때 받는 금리다. */
  rate: number;
  /** 우대조건을 모두 채웠을 때의 최고 금리 %. */
  topRate: number;
  /** 적금만 있다. */
  reserveType?: ReserveType;
}

export interface Product {
  kind: ProductKind;
  group: FinanceGroup;
  /** 공시월 (YYYYMM). 언제 기준의 금리인지 밝히기 위해 들고 다닌다. */
  disclosureMonth: string;
  company: string;
  name: string;
  /** 가입 방법 — "영업점", "인터넷", "스마트폰" 처럼 공시가 준 말 그대로. */
  joinWays: string[];
  /** 우대조건 설명. 공시 문장을 그대로 옮긴다. */
  special: string;
  /** 가입 대상 ("실명의 개인" 등). */
  member: string;
  /** 가입 제한. 1 제한 없음, 2 서민 전용, 3 일부 제한. */
  joinDeny: '1' | '2' | '3';
  /** 최고 한도 (원). 공시가 비워 두면 null — 한도가 없거나 밝히지 않은 것이다. */
  maxLimit: number | null;
  /** 만기 후 금리 안내. */
  afterMaturity: string;
  /** 그 밖의 유의사항. */
  note: string;
  options: ProductOption[];
}

/** 화면이 사람에게 그대로 보여 줄 수 있는 실패. */
export class ProductsError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'ProductsError';
    this.code = code;
  }
}

// --- 공시 읽기 ---------------------------------------------------------------

/** 공시가 돌려주는 것. 우리가 쓰는 칸만 적는다. */
interface Disclosure {
  result?: {
    err_cd?: string;
    err_msg?: string;
    max_page_no?: number | string;
    now_page_no?: number | string;
    total_count?: number | string;
    baseList?: unknown;
    optionList?: unknown;
  };
}

const text = (value: unknown): string =>
  typeof value === 'string' ? value.trim() : typeof value === 'number' ? String(value) : '';

/** 공시는 숫자를 숫자로도 문자열로도 준다. 어느 쪽이든 받는다. */
const number = (value: unknown): number | null => {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value.replace(/,/g, ''));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

const rows = (value: unknown): Record<string, unknown>[] =>
  Array.isArray(value) ? (value.filter((row) => typeof row === 'object' && row !== null) as Record<string, unknown>[]) : [];

/** 같은 상품의 두 줄을 맞붙이는 열쇠. */
const key = (row: Record<string, unknown>): string => `${text(row['fin_co_no'])}:${text(row['fin_prdt_cd'])}`;

export interface Page {
  products: Product[];
  /** 몇 쪽까지 있는가. 뒷장을 더 받을지 여기로 정한다. */
  maxPage: number;
  totalCount: number;
}

/**
 * 공시 한 쪽을 상품 목록으로 바꾼다.
 *
 * 금리 줄(optionList)이 없는 상품은 버린다 — 기간별 금리를 모르면 얼마를 받는지
 * 말할 수 없고, 말할 수 없는 것을 추천할 수는 없다.
 */
export function parseDisclosure(kind: ProductKind, group: FinanceGroup, body: unknown): Page {
  const result = (body as Disclosure | null)?.result;
  if (!result) throw new ProductsError('bad_response', '공시 응답을 읽지 못했습니다.');

  const code = text(result.err_cd);
  // 정상은 "000" 이다. 그 밖의 값은 공시가 붙여 준 문구를 그대로 사람에게 보인다.
  if (code !== '' && code !== '000') {
    throw new ProductsError('upstream_error', text(result.err_msg) || `공시가 오류 ${code} 로 답했습니다.`);
  }

  const options = new Map<string, ProductOption[]>();
  for (const row of rows(result.optionList)) {
    const term = number(row['save_trm']);
    const rate = number(row['intr_rate']);
    const top = number(row['intr_rate2']);
    // 금리가 비어 있는 줄이 섞여 나온다. 0% 로 셈하면 없는 상품을 추천하게 된다.
    if (term === null || term <= 0 || rate === null) continue;

    const reserve = text(row['rsrv_type']);
    const option: ProductOption = {
      termMonths: term,
      rateType: text(row['intr_rate_type']) === 'M' ? 'compound' : 'simple',
      rate,
      topRate: top ?? rate,
      ...(reserve === 'S' || reserve === 'F' ? { reserveType: reserve === 'S' ? ('fixed' as const) : ('free' as const) } : {}),
    };
    const list = options.get(key(row));
    if (list) list.push(option);
    else options.set(key(row), [option]);
  }

  const products: Product[] = [];
  for (const row of rows(result.baseList)) {
    const mine = options.get(key(row));
    if (!mine || mine.length === 0) continue;

    const deny = text(row['join_deny']);
    products.push({
      kind,
      group,
      disclosureMonth: text(row['dcls_month']),
      company: text(row['kor_co_nm']),
      name: text(row['fin_prdt_nm']),
      joinWays: text(row['join_way'])
        .split(/[,/]/)
        .map((way) => way.trim())
        .filter((way) => way !== ''),
      special: text(row['spcl_cnd']),
      member: text(row['join_member']),
      joinDeny: deny === '2' || deny === '3' ? deny : '1',
      maxLimit: number(row['max_limit']),
      afterMaturity: text(row['mtrt_int']),
      note: text(row['etc_note']),
      options: mine.sort((a, b) => a.termMonths - b.termMonths),
    });
  }

  return {
    products,
    maxPage: Math.max(1, number(result.max_page_no) ?? 1),
    totalCount: number(result.total_count) ?? products.length,
  };
}

// --- 받아 오기 ---------------------------------------------------------------

/** 셸의 Worker 가 내주는 창구. */
const ENDPOINT = '/api/fire/products';

/** 한 권역이 아무리 많아도 여기까지만 받는다. 끝없이 도는 것을 막는 빗장이다. */
const MAX_PAGES = 20;

export interface FetchOptions {
  kind: ProductKind;
  groups: FinanceGroup[];
  signal?: AbortSignal;
  /** 시험에서 갈아 끼운다. 비우면 브라우저의 fetch 를 쓴다. */
  fetcher?: typeof fetch;
}

async function page(
  options: FetchOptions,
  group: FinanceGroup,
  pageNo: number,
): Promise<Page> {
  const get = options.fetcher ?? fetch;
  const url = `${ENDPOINT}?kind=${options.kind}&group=${group}&page=${pageNo}`;

  let answer: Response;
  try {
    answer = await get(url, options.signal ? { signal: options.signal } : {});
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ProductsError('offline', '상품 공시를 불러오지 못했습니다. 연결을 확인하고 다시 시도하십시오.');
  }

  if (!answer.ok) {
    // 창구가 붙여 준 문구가 있으면 그대로 쓴다 — 인증키가 없다는 안내가 여기로 온다.
    const body = (await answer.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null;
    throw new ProductsError(
      body?.error?.code ?? 'http_error',
      body?.error?.message ?? `상품 공시를 불러오지 못했습니다 (HTTP ${answer.status}).`,
    );
  }
  return parseDisclosure(options.kind, group, await answer.json());
}

/** 어느 권역을 받다 어떻게 실패했는가. 그 권역만 다시 받으면 된다. */
export interface GroupFailure {
  group: FinanceGroup;
  error: ProductsError;
}

export interface Fetched {
  /** 성공한 권역의 상품. 권역별로 나뉘어 온다. */
  byGroup: Map<FinanceGroup, Product[]>;
  failures: GroupFailure[];
}

/**
 * 고른 권역의 상품을 모두 받는다.
 *
 * 권역마다 쪽이 나뉘어 있어 첫 쪽을 받아 보고 남은 쪽을 한꺼번에 부른다. 한
 * 권역이 통째로 실패해도 다른 권역의 상품은 보여 준다 — 저축은행 쪽이 막혔다고
 * 은행 상품까지 감출 이유가 없다.
 */
export async function fetchProducts(options: FetchOptions): Promise<Fetched> {
  const byGroup = new Map<FinanceGroup, Product[]>();
  const failures: GroupFailure[] = [];

  await Promise.all(
    options.groups.map(async (group) => {
      try {
        const first = await page(options, group, 1);
        const products = [...first.products];

        const last = Math.min(first.maxPage, MAX_PAGES);
        const rest = await Promise.all(
          Array.from({ length: Math.max(0, last - 1) }, (_, index) => page(options, group, index + 2)),
        );
        for (const next of rest) products.push(...next.products);
        byGroup.set(group, products);
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') throw error;
        failures.push({
          group,
          error:
            error instanceof ProductsError
              ? error
              : new ProductsError('unknown', `${GROUP_LABEL[group]} 상품을 불러오지 못했습니다.`),
        });
      }
    }),
  );

  return { byGroup, failures };
}
