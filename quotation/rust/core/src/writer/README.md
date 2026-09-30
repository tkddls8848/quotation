# Excel 작성 모듈

공개 API는 `mod.rs`의 `build_bytes`, `Date`, `WriteError`다. 데스크톱·WASM·Python
호출 경로를 바꿀 필요 없이 아래 책임만 고친다. 셀 좌표의 근거는
[SPEC_CELLMAP](../../../../../doc/spec/SPEC_CELLMAP.md)에 있다.

| 파일 | 책임 |
|---|---|
| `mod.rs` | 템플릿 열기 → TOTAL → 상세 → 저장 → 도형 복원 순서 |
| `total.rs` | TOTAL 시트의 장비군 요약·소계 |
| `detail.rs` | 상세 시트·서브라인 수량·제거 부품·H/W·S/W 합계 |
| `footer.rs` | 총합계·공급가·인쇄 영역 |
| `cells.rs` | 문자열/숫자/수식 쓰기·라벨·글꼴·숫자 서식·병합 범위 |
| `decorate.rs` | Layout에 따른 색·테두리·행 높이 등 꾸미기 |
| `restore.rs` | 템플릿 테두리 색 복원 |
| `drawings.rs` | 저장 후 ZIP의 원본 도형·관계 파일 복원 |

셀을 쓴 뒤 꾸미고 마지막에 병합한다. XML 문자열은 `put_xml_text`로 써서
수식으로 실행되지 않게 한다. 금액·수량 수식은 `detail.rs`와 `total.rs`에 유지한다.
수식·N/C·제거·한글·그림 회귀 검사는 `core/tests/workbook.rs`와 `quotation.rs`에 있다.
