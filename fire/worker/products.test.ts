/**
 * 창구가 제 할 일만 하는지 대조한다.
 *
 * 여기서 틀리면 두 가지가 난다. 인증키가 새거나, 이 창구가 아무 데나 대신
 * 찔러 주는 통로가 된다. 둘 다 화면이 조금 이상해지는 정도가 아니라 사고다.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

import { handleProducts } from './products';

const KEY = 'test-key-0000';

const ask = (query: string, method = 'GET'): Request =>
  new Request(`https://example.com/api/fire/products?${query}`, { method });

const upstream = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

/** 공시가 답한 셈 치고, 어디로 물어봤는지 적어 둔다. */
function stub(answer: () => Response | Promise<Response>): string[] {
  const asked: string[] = [];
  vi.stubGlobal('fetch', async (url: string) => {
    asked.push(String(url));
    return answer();
  });
  return asked;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('handleProducts — 들어온 요청 가리기', () => {
  it('표에 없는 종류·금융권은 받지 않는다', async () => {
    const cases = ['kind=loan&group=bank', 'kind=deposit&group=stock', 'group=bank', 'kind=deposit'];
    for (const query of cases) {
      const answer = await handleProducts(ask(query), { FSS_API_KEY: KEY });
      expect(answer.status, query).toBe(400);
    }
  });

  it('쪽 번호가 수가 아니거나 범위 밖이면 받지 않는다', async () => {
    for (const page of ['0', '-1', '999', 'abc', '1.5']) {
      const answer = await handleProducts(ask(`kind=deposit&group=bank&page=${page}`), { FSS_API_KEY: KEY });
      expect(answer.status, page).toBe(400);
    }
  });

  it('GET 이 아니면 받지 않는다', async () => {
    const answer = await handleProducts(ask('kind=deposit&group=bank', 'POST'), { FSS_API_KEY: KEY });
    expect(answer.status).toBe(405);
  });

  it('키가 없으면 어떻게 받는지 알려 준다', async () => {
    const answer = await handleProducts(ask('kind=deposit&group=bank'), {});
    expect(answer.status).toBe(503);
    const body = (await answer.json()) as { error: { code: string; message: string } };
    expect(body.error.code).toBe('no_api_key');
    expect(body.error.message).toContain('FSS_API_KEY');
  });
});

describe('handleProducts — 넘기고 돌려주기', () => {
  it('주소는 표에서 고르고 키와 쪽만 붙인다', async () => {
    const asked = stub(() => upstream({ result: { err_cd: '000' } }));
    await handleProducts(ask('kind=saving&group=savingsbank&page=3'), { FSS_API_KEY: KEY });

    expect(asked).toHaveLength(1);
    const url = new URL(asked[0]!);
    expect(url.origin + url.pathname).toBe('https://finlife.fss.or.kr/finlifeapi/savingProductsSearch.json');
    expect(url.searchParams.get('auth')).toBe(KEY);
    expect(url.searchParams.get('topFinGrpNo')).toBe('030300'); // 저축은행
    expect(url.searchParams.get('pageNo')).toBe('3');
  });

  it('정기예금과 은행도 제 주소로 간다', async () => {
    const asked = stub(() => upstream({ result: { err_cd: '000' } }));
    await handleProducts(ask('kind=deposit&group=bank'), { FSS_API_KEY: KEY });
    const url = new URL(asked[0]!);
    expect(url.pathname).toBe('/finlifeapi/depositProductsSearch.json');
    expect(url.searchParams.get('topFinGrpNo')).toBe('020000');
    expect(url.searchParams.get('pageNo')).toBe('1'); // 쪽을 안 주면 첫 쪽
  });

  it('받은 몸통을 고치지 않고 그대로 돌려준다', async () => {
    const body = { result: { err_cd: '000', baseList: [{ fin_prdt_nm: '예금' }] } };
    stub(() => upstream(body));
    const answer = await handleProducts(ask('kind=deposit&group=bank'), { FSS_API_KEY: KEY });

    expect(answer.status).toBe(200);
    expect(await answer.json()).toEqual(body);
    expect(answer.headers.get('cache-control')).toContain('max-age=86400');
    // 정적 자산과 같은 방어 머리말을 쓴다 (web/public/_headers).
    expect(answer.headers.get('x-content-type-options')).toBe('nosniff');
  });

  it('공시가 답하지 않으면 502 로 알리되 주소를 담지 않는다 (키가 붙어 있다)', async () => {
    vi.stubGlobal('fetch', async () => {
      throw new Error('getaddrinfo ENOTFOUND finlife.fss.or.kr');
    });
    const answer = await handleProducts(ask('kind=deposit&group=bank'), { FSS_API_KEY: KEY });
    expect(answer.status).toBe(502);
    const text = await answer.text();
    expect(text).not.toContain(KEY);
    expect(text).not.toContain('finlife');
  });

  it('공시가 오류 상태로 답해도 키를 흘리지 않는다', async () => {
    stub(() => upstream({ nope: true }, 500));
    const answer = await handleProducts(ask('kind=deposit&group=bank'), { FSS_API_KEY: KEY });
    expect(answer.status).toBe(502);
    expect(await answer.text()).not.toContain(KEY);
  });
});
