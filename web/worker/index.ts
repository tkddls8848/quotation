/**
 * 셸의 Worker — 도구가 쓰는 창구 하나만 맡고, 나머지는 정적 자산 그대로다.
 *
 * 오래도록 이 저장소에는 Worker 스크립트가 없었다 (wrangler.jsonc 의 긴 주석).
 * 견적서 변환을 서버에서 하지 않기로 했기 때문이다 — 무료 계정은 요청당 CPU
 * 10 ms 인데 견적서 한 건에 73 ms 가 든다.
 *
 * 그 결정은 그대로다. 여기 Worker 가 선 이유는 다른 데 있다. FIRE 계산기의
 * 예적금 상품 추천은 금융감독원 공시 API 를 봐야 하는데, 그 API 는 인증키를
 * 요구하고 브라우저에서 바로 부르면 CORS 로 막힌다. 키를 아는 자리가 필요하다.
 *
 * Worker 가 생겨도 앞의 근거는 흔들리지 않는다. Workers Static Assets 는 **자산에
 * 맞는 요청을 Worker 에 들르지 않고** 내보내므로(무료·무제한), 화면을 여는 사람은
 * 예전과 똑같이 Worker 를 깨우지 않는다. 이 스크립트가 깨어나는 것은 상품 목록을
 * 부를 때뿐이고, 그때 하는 일은 키를 붙여 넘기는 것뿐이다 (결정 0013).
 *
 * 도구 논리는 여전히 여기 없다. 공시 API 를 아는 것은 FIRE 기능이고
 * (`fire/worker/products.ts`), 셸은 어느 길이 누구 것인지만 안다. 의존은
 * 셸 → 기능 한 방향이다 (결정 0012).
 */
import { ProductsEnv, handleProducts } from '@fire/worker/products';

/** 정적 자산을 내주는 손잡이. wrangler.jsonc 의 `assets.binding` 이 이 이름이다. */
interface Assets {
  fetch: (request: Request) => Promise<Response>;
}

export interface Env extends ProductsEnv {
  ASSETS: Assets;
}

/** FIRE 계산기의 상품 공시 창구. 다른 길은 만들지 않는다. */
const FIRE_PRODUCTS = '/api/fire/products';

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { pathname } = new URL(request.url);
    if (pathname === FIRE_PRODUCTS) return handleProducts(request, env);

    // 자산에 맞지 않는 요청이다. 정적 자산 쪽의 규칙(SPA 되돌림)에 맡긴다.
    return env.ASSETS.fetch(request);
  },
};
