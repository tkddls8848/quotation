/**
 * 예적금 상품 공시 중계 — 금융감독원 금융상품 통합 비교공시 API 앞에 서는 얇은 창구.
 *
 * ── 왜 서버를 거치는가 ────────────────────────────────────────────────────
 *
 * 이 도구의 다른 셈은 전부 브라우저 안에서 돈다. 상품 목록만은 그럴 수 없다.
 * 공시 API 는 (1) 인증키를 요구하고 (2) 브라우저에서 바로 부르면 CORS 로 막힌다.
 * 키를 화면에 박으면 누구나 가져다 쓰므로, 키를 아는 자리는 여기 한 곳뿐이어야
 * 한다.
 *
 * ── 무엇을 하지 않는가 ────────────────────────────────────────────────────
 *
 * **읽어서 고치지 않는다.** 받은 JSON 을 그대로 흘려보낸다. 무료 계정의 Worker
 * 는 요청당 CPU 10 ms 인데(wrangler.jsonc 의 근거), 전 은행·저축은행 상품을 여기서
 * 파싱해 합치면 그 한도가 위태롭다. 페이지를 넘기고 상품과 옵션을 맞붙이는 일은
 * 브라우저가 한다 (`fire/web/src/products.ts`). 여기서 하는 일은 세 가지다.
 *
 *   1. 들어온 요청이 미리 정한 네 조합 중 하나인지 확인한다
 *   2. 인증키를 붙여 공시 API 에 넘긴다
 *   3. 받은 것을 캐시 지시와 함께 그대로 돌려준다
 *
 * 주소를 요청에서 조립하지 않고 **표에서 고른다.** 그래야 이 창구가 아무 데나
 * 대신 찔러 주는 통로(SSRF)가 되지 않는다.
 *
 * ── 캐시 ──────────────────────────────────────────────────────────────────
 *
 * 공시는 한 달에 한 번 바뀐다. 그래서 하루를 캐시한다. Cloudflare 의 가장자리
 * 캐시에 맡기므로(`cf.cacheEverything`) 캐시가 맞는 요청은 파싱도 복사도 없이
 * 나간다 — CPU 를 쓰지 않는다.
 */

/** Worker 에 넣어 두는 값. 키는 시크릿이다 (`wrangler secret put FSS_API_KEY`). */
export interface ProductsEnv {
  /** 금융감독원 오픈API 인증키. 없으면 이 창구는 503 으로 답한다. */
  FSS_API_KEY?: string;
}

/** 공시가 바뀌는 주기는 한 달이다. 하루면 충분히 짧다 (초). */
const CACHE_SECONDS = 86_400;

/** 공시 API 가 오래 답하지 않으면 화면을 붙들지 않고 포기한다 (밀리초). */
const UPSTREAM_TIMEOUT_MS = 8_000;

/**
 * 부를 수 있는 곳은 이 넷뿐이다.
 *
 * 요청에서 받은 값으로 주소를 짓지 않는다 — `kind` 와 `group` 은 이 표의 열쇠일
 * 뿐이고, 표에 없으면 400 이다.
 */
const ENDPOINTS = {
  deposit: 'https://finlife.fss.or.kr/finlifeapi/depositProductsSearch.json',
  saving: 'https://finlife.fss.or.kr/finlifeapi/savingProductsSearch.json',
} as const;

/** 금융권 코드. 예적금을 파는 곳 중 예금자보호가 되는 두 권역만 받는다. */
const GROUPS = {
  bank: '020000',
  savingsbank: '030300',
} as const;

export type ProductKind = keyof typeof ENDPOINTS;
export type FinanceGroup = keyof typeof GROUPS;

const MAX_PAGE = 20;

const isKind = (value: string | null): value is ProductKind =>
  value !== null && Object.hasOwn(ENDPOINTS, value);

const isGroup = (value: string | null): value is FinanceGroup =>
  value !== null && Object.hasOwn(GROUPS, value);

/**
 * 정적 자산에 붙는 것과 같은 방어 머리말 (`web/public/_headers`).
 *
 * 그쪽 규칙은 자산에만 걸린다. 이 창구의 응답에는 우리가 직접 붙여야 같은
 * 정책 아래 놓인다.
 */
const GUARD = {
  'x-content-type-options': 'nosniff',
  'referrer-policy': 'no-referrer',
} as const;

/** 화면이 그대로 사람에게 보여 줄 수 있는 문구로 답한다. */
function fail(status: number, code: string, message: string): Response {
  return new Response(JSON.stringify({ error: { code, message } }), {
    status,
    headers: {
      ...GUARD,
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
    },
  });
}

/**
 * `GET /api/fire/products?kind=deposit|saving&group=bank|savingsbank&page=1`
 *
 * 공시 API 가 돌려준 몸통을 그대로 돌려준다. 형태는
 * `{ result: { total_count, max_page_no, now_page_no, err_cd, baseList, optionList } }` 이고,
 * 읽어 합치는 쪽은 `fire/web/src/products.ts` 다.
 */
export async function handleProducts(request: Request, env: ProductsEnv): Promise<Response> {
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    return fail(405, 'method_not_allowed', 'GET 으로만 부를 수 있습니다.');
  }

  const url = new URL(request.url);
  const kind = url.searchParams.get('kind');
  const group = url.searchParams.get('group');
  const page = Number(url.searchParams.get('page') ?? '1');

  if (!isKind(kind) || !isGroup(group)) {
    return fail(400, 'bad_request', '상품 종류(kind)와 금융권(group)이 올바르지 않습니다.');
  }
  if (!Number.isInteger(page) || page < 1 || page > MAX_PAGE) {
    return fail(400, 'bad_request', `쪽 번호는 1 에서 ${MAX_PAGE} 사이여야 합니다.`);
  }

  const auth = env.FSS_API_KEY;
  if (!auth) {
    // 키가 없으면 어떤 상품도 보여 줄 수 없다. 화면이 이 문구를 그대로 띄운다.
    return fail(
      503,
      'no_api_key',
      '상품 공시 인증키가 설정되지 않았습니다. 금융감독원 금융상품 통합 비교공시(finlife.fss.or.kr)에서 ' +
        '오픈API 인증키를 받아 Worker 시크릿 FSS_API_KEY 로 넣어야 상품을 불러올 수 있습니다.',
    );
  }

  const upstream = new URL(ENDPOINTS[kind]);
  upstream.searchParams.set('auth', auth);
  upstream.searchParams.set('topFinGrpNo', GROUPS[group]);
  upstream.searchParams.set('pageNo', String(page));

  let answer: Response;
  try {
    answer = await fetch(upstream.toString(), {
      // 가장자리 캐시에 맡긴다. 캐시가 맞으면 이 Worker 는 사실상 아무 일도 하지 않는다.
      cf: { cacheEverything: true, cacheTtl: CACHE_SECONDS },
      signal: AbortSignal.timeout(UPSTREAM_TIMEOUT_MS),
      headers: { accept: 'application/json' },
    } as RequestInit);
  } catch {
    // 실패 문구에 주소를 담지 않는다 — 물음표 뒤에 인증키가 붙어 있다.
    return fail(502, 'upstream_unreachable', '금융감독원 공시 서버에 닿지 못했습니다. 잠시 뒤에 다시 시도하십시오.');
  }

  if (!answer.ok) {
    return fail(502, 'upstream_error', `금융감독원 공시 서버가 ${answer.status} 로 답했습니다.`);
  }

  // 몸통은 읽지 않고 그대로 흘려보낸다. 머리말만 우리 것으로 새로 쓴다.
  return new Response(answer.body, {
    status: 200,
    headers: {
      ...GUARD,
      'content-type': 'application/json; charset=utf-8',
      'cache-control': `public, max-age=${CACHE_SECONDS}`,
    },
  });
}
