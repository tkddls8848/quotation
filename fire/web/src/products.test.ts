/**
 * 공시를 읽는 부분을 대조한다.
 *
 * 여기서 틀리면 상품이 통째로 사라지거나 엉뚱한 금리가 붙는다. 금융감독원
 * 공시가 실제로 주는 모양(상품과 금리가 두 목록에 나뉘어 있고, 숫자가 문자열로
 * 오기도 하고, 빈 칸이 섞여 있다)을 그대로 흉내 낸 자료로 맞춘다.
 */
import { describe, expect, it } from 'vitest';

import { ProductsError, fetchProducts, parseDisclosure } from './products';

/** 공시 응답 한 쪽. 칸 이름은 실제 API 와 같다. */
const page = {
  result: {
    prdt_div: 'D',
    total_count: 2,
    max_page_no: 1,
    now_page_no: 1,
    err_cd: '000',
    err_msg: '정상',
    baseList: [
      {
        dcls_month: '202609',
        fin_co_no: '0010001',
        kor_co_nm: '가나은행',
        fin_prdt_cd: 'AA01',
        fin_prdt_nm: '모으는 정기예금',
        join_way: '인터넷,스마트폰',
        mtrt_int: '만기 후 1개월 이내 기본금리의 1/2',
        spcl_cnd: '첫 거래 0.2%p',
        join_deny: '1',
        join_member: '실명의 개인',
        etc_note: '1인 1계좌',
        max_limit: '50000000',
        dcls_strt_day: '20260901',
      },
      {
        dcls_month: '202609',
        fin_co_no: '0010002',
        kor_co_nm: '다라은행',
        fin_prdt_cd: 'BB01',
        fin_prdt_nm: '금리 줄이 없는 예금',
        join_way: '영업점',
        spcl_cnd: '해당사항 없음',
        join_deny: '3',
        join_member: '실명의 개인',
        max_limit: null,
      },
    ],
    optionList: [
      {
        fin_co_no: '0010001',
        fin_prdt_cd: 'AA01',
        intr_rate_type: 'S',
        intr_rate_type_nm: '단리',
        save_trm: '12',
        intr_rate: 3.1,
        intr_rate2: 3.3,
      },
      {
        fin_co_no: '0010001',
        fin_prdt_cd: 'AA01',
        intr_rate_type: 'M',
        intr_rate_type_nm: '복리',
        save_trm: '6',
        intr_rate: 2.8,
        intr_rate2: 3,
      },
      {
        // 금리가 비어 있는 줄. 0% 로 셈하면 없는 상품을 추천하게 된다.
        fin_co_no: '0010001',
        fin_prdt_cd: 'AA01',
        save_trm: '24',
        intr_rate: null,
        intr_rate2: null,
      },
    ],
  },
};

describe('parseDisclosure', () => {
  it('상품과 기간별 금리를 회사·상품 코드로 맞붙인다', () => {
    const { products, maxPage, totalCount } = parseDisclosure('deposit', 'bank', page);
    expect(maxPage).toBe(1);
    expect(totalCount).toBe(2);
    expect(products).toHaveLength(1); // 금리 줄이 없는 상품은 뺀다

    const [first] = products;
    expect(first?.company).toBe('가나은행');
    expect(first?.kind).toBe('deposit');
    expect(first?.group).toBe('bank');
    expect(first?.joinWays).toEqual(['인터넷', '스마트폰']);
    expect(first?.maxLimit).toBe(50_000_000);
    expect(first?.options).toEqual([
      { termMonths: 6, rateType: 'compound', rate: 2.8, topRate: 3 },
      { termMonths: 12, rateType: 'simple', rate: 3.1, topRate: 3.3 },
    ]);
  });

  it('적금은 적립 방식까지 읽는다', () => {
    const saving = {
      result: {
        err_cd: '000',
        max_page_no: 1,
        total_count: 1,
        baseList: [
          {
            dcls_month: '202609',
            fin_co_no: '0010001',
            kor_co_nm: '가나은행',
            fin_prdt_cd: 'CC01',
            fin_prdt_nm: '자유 적금',
            join_way: '스마트폰',
            join_deny: '2',
          },
        ],
        optionList: [
          {
            fin_co_no: '0010001',
            fin_prdt_cd: 'CC01',
            intr_rate_type: 'S',
            rsrv_type: 'F',
            rsrv_type_nm: '자유적립식',
            save_trm: 12,
            intr_rate: 3.5,
            intr_rate2: 4.5,
          },
        ],
      },
    };
    const { products } = parseDisclosure('saving', 'savingsbank', saving);
    expect(products[0]?.options[0]?.reserveType).toBe('free');
    expect(products[0]?.joinDeny).toBe('2');
    expect(products[0]?.maxLimit).toBeNull();
  });

  it('최고 금리가 없으면 기본 금리를 그대로 쓴다', () => {
    const body = {
      result: {
        err_cd: '000',
        baseList: [{ fin_co_no: '1', fin_prdt_cd: 'X', kor_co_nm: '가나', fin_prdt_nm: '예금' }],
        optionList: [{ fin_co_no: '1', fin_prdt_cd: 'X', save_trm: '12', intr_rate: 3 }],
      },
    };
    expect(parseDisclosure('deposit', 'bank', body).products[0]?.options[0]?.topRate).toBe(3);
  });

  it('공시가 오류로 답하면 그 문구를 그대로 올린다', () => {
    const body = { result: { err_cd: '020', err_msg: '인증키가 유효하지 않습니다' } };
    expect(() => parseDisclosure('deposit', 'bank', body)).toThrow(ProductsError);
    expect(() => parseDisclosure('deposit', 'bank', body)).toThrow('인증키가 유효하지 않습니다');
  });

  it('응답이 아예 다른 모양이면 읽지 못했다고 한다', () => {
    expect(() => parseDisclosure('deposit', 'bank', null)).toThrow(ProductsError);
    expect(() => parseDisclosure('deposit', 'bank', { nope: 1 })).toThrow('공시 응답을 읽지 못했습니다.');
  });
});

describe('fetchProducts', () => {
  const answer = (body: unknown, status = 200): Response =>
    new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

  it('쪽이 나뉘어 있으면 끝까지 받아 합친다', async () => {
    const asked: string[] = [];
    const two = (pageNo: number) => ({
      result: {
        err_cd: '000',
        max_page_no: 2,
        now_page_no: pageNo,
        total_count: 2,
        baseList: [{ fin_co_no: `${pageNo}`, fin_prdt_cd: 'X', kor_co_nm: `은행${pageNo}`, fin_prdt_nm: '예금' }],
        optionList: [{ fin_co_no: `${pageNo}`, fin_prdt_cd: 'X', save_trm: '12', intr_rate: 3 }],
      },
    });

    const { byGroup, failures } = await fetchProducts({
      kind: 'deposit',
      groups: ['bank'],
      fetcher: (async (url: string) => {
        asked.push(url);
        return answer(two(Number(new URL(url, 'https://x').searchParams.get('page'))));
      }) as unknown as typeof fetch,
    });

    expect(asked).toEqual(['/api/fire/products?kind=deposit&group=bank&page=1', '/api/fire/products?kind=deposit&group=bank&page=2']);
    expect(byGroup.get('bank')?.map((product) => product.company)).toEqual(['은행1', '은행2']);
    expect(failures).toHaveLength(0);
  });

  it('한 권역이 실패해도 다른 권역은 보여 준다', async () => {
    const { byGroup, failures } = await fetchProducts({
      kind: 'deposit',
      groups: ['bank', 'savingsbank'],
      fetcher: (async (url: string) => {
        if (url.includes('savingsbank')) {
          return answer({ error: { code: 'no_api_key', message: '인증키가 설정되지 않았습니다.' } }, 503);
        }
        return answer({
          result: {
            err_cd: '000',
            max_page_no: 1,
            baseList: [{ fin_co_no: '1', fin_prdt_cd: 'X', kor_co_nm: '가나은행', fin_prdt_nm: '예금' }],
            optionList: [{ fin_co_no: '1', fin_prdt_cd: 'X', save_trm: '12', intr_rate: 3 }],
          },
        });
      }) as unknown as typeof fetch,
    });

    expect(byGroup.get('bank')).toHaveLength(1);
    expect(byGroup.has('savingsbank')).toBe(false);
    expect(failures).toHaveLength(1);
    expect(failures[0]?.group).toBe('savingsbank');
    expect(failures[0]?.error.code).toBe('no_api_key');
    expect(failures[0]?.error.message).toBe('인증키가 설정되지 않았습니다.');
  });
});
