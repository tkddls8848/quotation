# 0012 — 기능마다 최상위 폴더 하나

*2026-09-13*

## 무엇을 바꿨나

폴더를 **역할별**(rust / quotation / desktop_ibm / web)에서 **기능별**로 다시
묶었다.

```text
이전                          지금
rust/                         quotation/rust/
quotation/                    quotation/python/quotation/
desktop_ibm/                  quotation/desktop/
tests/                        quotation/tests/
web/tests/                    quotation/web/tests/
web/scripts/build_*.py        quotation/web/scripts/
web/frontend/src/api.ts …     quotation/web/src/
web/frontend/src/fire/        fire/web/src/
web/frontend/{index,vite,…}   web/            (셸)
                              converters/     (자리만)
```

파이썬 패키지는 `quotation/python/` 아래로 한 칸 내렸다. 그래야 기능 폴더
이름(`quotation/`)과 패키지 이름(`quotation`)이 부딪히지 않으면서
`from quotation.core import convert` 는 그대로 선다. 임포트 뿌리는 저장소 루트
`conftest.py` 가 잡는다.

## 왜

도구가 하나일 때는 역할별 묶음이 맞았다. 견적기뿐이었으므로 `rust/` 가 곧
견적기의 규칙이었고 `web/` 이 곧 견적기의 화면이었다.

도구가 둘이 되고(FIRE 계산기) 셋이 될 예정이 되자(PDF↔HWP 변환기) 그 묶음이
거짓말이 됐다. `web/frontend/src/` 안에 견적서 배선과 FIRE 계산이 나란히 있는
동안에는 **한 도구를 고치면서 다른 도구의 파일을 건드리게 된다.** 스타일 한
장(`styles.css`)을 셋이 나눠 쓰고 있었고, 화면 뼈대(`index.html`)도 하나였다.

경계가 파일 단위로만 있으면 시간이 지나며 반드시 샌다. 폴더로 갈라 두면 샐 수
없다.

## 규칙

의존은 한 방향뿐이다.

```text
셸(web/) ──별명(@quotation, @fire)──▶ 기능
기능 ──▶ 기능                          금지
```

- 별명은 셸의 `vite.config.ts` 에만 있다. 기능 폴더끼리는 서로를 import 하지
  않는다.
- 기능은 화면 뼈대·스타일·논리·테스트를 제 폴더에 다 갖는다. 셸이 내주는 것은
  빈 칸 하나(`<main id="…-root">`)와 탭 단추뿐이다.
- 기능은 제 탭이 처음 열릴 때 받아 온다. 빌드 산출물도 기능마다 따로 나간다.

### 기능 바깥에 공유 코드를 두지 않는다

**여러 기능이 쓸 법한 코드라도 각 기능이 제 것을 안에 둔다. 공유는 기능
안에서만 한다.**

같은 코드가 두 기능에 각각 있는 것을 중복이라 부르며 밖으로 빼내고 싶어지는데,
그 순간 **한 군데의 변경이 여러 기능의 장애로 번지는 길**이 생긴다. 기능이
서넛인 저장소에서 그 길은 이득보다 비싸다. 중복은 눈에 보이고 국소적이지만,
새는 결합은 보이지 않고 전파된다.

그래서 개발 도구도 기능 안에 둔다. 견적서 산출물을 비교하는 `compare.py`,
`xlsx_content.py`, 엔진 기동을 재는 `wasm_startup_bench.mjs`, 골든을 변환하는
`xls2xlsx.ps1` 은 전부 견적기에만 쓰이므로 최상위 `tools/` 가 아니라
`quotation/tools/` 에 있다.

정말로 여러 기능이 같은 것을 써야 한다면, 그때는 **판본을 갖는 별도 꾸러미**로
꺼낸다 — 아무나 고칠 수 있는 최상위 폴더로 두지 않는다. 그 판단은 그때 다시
기록한다.

최상위에 남는 것은 기능이 아닌 것뿐이다.

| 폴더 | 무엇인가 |
|---|---|
| `web/` | 셸. 탭과 공통 틀. 도구 논리는 없다 |
| `doc/` | 저장소 전체의 기록 (결정·사고·실측·명세) |

## 무엇으로 지키나

- **빌드가 증거다.** `npm --prefix web run build` 가 기능마다 따로 덩어리를
  낸다 (셸 1.8 kB, 견적서 5.6 kB, FIRE 8.2 kB — 전부 gzip). 한 기능이 다른
  기능을 부르기 시작하면 그 덩어리가 합쳐지므로 바로 드러난다.
- 기능 폴더의 `README` 가 그 경계를 적어 둔다.

## 대가

- 경로를 쓰는 곳을 한 번에 다 고쳐야 했다 — CI, Cloudflare 빌드, PyInstaller
  spec, pytest, Cargo 작업공간, wrangler.
- 프런트엔드 소스가 셸 폴더 밖에 있어서 `vite.config.ts` 에 `server.fs.allow`
  와 별명이, `tsconfig.json` 에 `paths` 가 필요하다. 도구가 셸에 깔리므로
  `vitest` 의 자리도 알려 준다.
- `web/frontend/` 를 `web/` 으로 폈다. node 프로젝트가 둘에서 하나가 되면서
  `npm ci` 도 한 번이면 된다.

## 되돌리는 조건

기능이 다시 하나로 줄거나, 기능 사이에 공유해야 할 코드가 많아져서 별명
한 방향으로 감당이 안 될 때. 그때는 공유 부분을 `tools/` 나 별도 패키지로
끌어내는 것이 먼저이고, 폴더를 도로 합치는 것은 그다음이다.
