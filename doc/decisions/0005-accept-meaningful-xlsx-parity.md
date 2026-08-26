# 결정 0005 — 견적서 동등성은 내용과 첫 페이지 도형으로 판정한다

- 날짜: 2026-08-26
- 상태: **적용됨**
- 보완하는 계획: [Rust→WASM 코어 전환 착수안](../plan/rust-wasm-core-plan.md)

## 결론

Rust 전환의 1차 승인 기준은 ZIP 직렬화 바이트가 아니라 다음이다.

1. 같은 구성 XML에서 제품 정보, 수량, 단가, 금액, 수식, 시트 순서, 병합이
   Python 기준 산출물과 같다.
2. 첫 페이지(`TOTAL`)의 로고·머리글 도형은 template에서 drawing XML, 관계,
   media, worksheet drawing 관계를 그대로 이식해 보존한다.

OOXML 라이브러리가 만드는 패키지 메타데이터·스타일 직렬화·부품 순서 차이는
진단 대상으로 남기되, 위 두 조건이 성립하는 경우만으로 전환을 중단하지 않는다.

## 근거

`1180_64c_1024_800 4ea_10G 4ea_32G 2ea.xml`을 Python으로 변환한 뒤 umya가
워크북을 읽고 저장한 결과를 대조했다. `TOTAL`, `SERVER 1`, `HMC 1`, `template`
시트의 모든 셀 값·수식은 0건 차이였고, 각 시트의 행·열 크기와 병합 수도 같았다.

umya의 OOXML 재직렬화 뒤 첫 페이지 drawing XML이 달라질 수 있으므로, Rust
경로는 원본 drawing/media 부품과 sheet1 관계를 다시 이식한다. 이 보강 뒤
`xl/drawings/drawing1.xml`, 그 관계 파일, `xl/media/image1.png`,
`xl/worksheets/_rels/sheet1.xml.rels`는 Python 기준 파일과 바이트까지 같았다.

## 유지할 검사

- 기존 골든 회귀와 셀 단위 비교는 계속 수행한다.
- `xlsx_parity.py`의 ZIP 부품 차이는 계속 출력해 조사한다.
- 제품·금액·수식 또는 첫 페이지 drawing 계약이 달라지면 전환을 중단한다.
