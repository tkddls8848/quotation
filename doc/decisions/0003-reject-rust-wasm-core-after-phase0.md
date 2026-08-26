# 결정 0003 — Rust→WASM 변환 코어 전환을 하지 않는다

- 날짜: 2026-08-26
- 상태: **적용됨**
- 폐기한 계획: [Rust→WASM 코어 전환 착수안](../plan/rust-wasm-core-plan.md)

## 결론

Rust→WASM 코어 전환을 **진행하지 않는다.** 현재 Python 코어와 브라우저 Pyodide
엔진을 유지한다. 서버 변환이나 별도 Rust 구현도 이 결정의 결과로 새로 만들지
않는다.

## Phase 0 관문 1 결과

계획의 첫 관문은 템플릿을 열어 셀 하나만 바꿔 저장했을 때 기존 산출물과
`xlsx_parity.py` 기준으로 같은지를 묻는다. 2026-08-26에 다음을 실행했다.

1. `umya-spreadsheet` 3.1.0으로 IBM 템플릿을 읽었다.
2. `TOTAL!C3`만 `2099-01-01`로 바꾸고 저장했다.
3. openpyxl 3.1.5으로 같은 템플릿과 같은 셀 변경을 저장했다.
4. 두 결과를 `web/tests/xlsx_parity.py::differences`로 비교했다.

비교는 실패했다. Rust 산출물에는 openpyxl 산출물에 없는 다음 부품이 **추가로**
들어 있었다.

- `xl/drawings/_rels/drawing1.xml.rels`, `drawing2.xml.rels`
- `xl/drawings/drawing1.xml`, `drawing2.xml`
- `xl/media/image1.png`
- `xl/printerSettings/printerSettings1.bin`, `printerSettings2.bin`
- `xl/sharedStrings.xml`
- `xl/worksheets/_rels/sheet1.xml.rels`, `sheet2.xml.rels`

openpyxl 산출물은 10개 부품·11,925 bytes, Rust 산출물은 20개 부품·24,444 bytes였다.
공통인 10개 부품도 모두 달랐다. 즉 `xlsx_parity.py`는 추가 부품 10개와 내용이
다른 공통 부품 10개, 총 20개 차이를 보고했다. 내용이 다른 부품은
`[Content_Types].xml`, `_rels/.rels`, `docProps/app.xml`,
`docProps/core.xml`, `xl/_rels/workbook.xml.rels`, `xl/styles.xml`,
`xl/theme/theme1.xml`, `xl/workbook.xml`, `xl/worksheets/sheet1.xml`,
`xl/worksheets/sheet2.xml`가 달랐다. 현재 판정기는 생성 시각과 병합 영역
나열 순서만 무시하므로, 이 차이는 허용할 수 없다.

## 이유와 후속 조치

이 계획은 Phase 0의 세 관문 중 하나라도 실패하면 나머지 단계를 폐기하도록
정했다. 첫 관문이 실패했으므로 "zip + quick-xml으로 직접 구현"으로 우회하거나
정규화 규칙을 늘리지 않는다. 그것은 검증 범위와 단일 구현이라는 전제를 새로
결정해야 하는 다른 계획이다.

Phase 0에서 만든 Rust 프로토타입과 빌드 산출물은 폐기했다. 현행 Python 구현,
테스트, 템플릿, 브라우저 배포 경로에는 변경이 없다.
