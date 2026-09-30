# 작업 경로

이 저장소는 견적서 작성기다. 문서 변환기는 분리되었다(결정 0021).
데스크톱은 Rust다(결정 0022). 예전 계획·결정의 삭제된 경로를 현재 구현으로 보지 않는다.

| 작업 | 먼저 열 파일 |
|---|---|
| XML 해석·IBM/Lenovo 판별 | `quotation/rust/core/src/xml_reader.rs`, `modes.rs` |
| Excel 셀·수식·서식 | `quotation/rust/core/src/writer/README.md` |
| 업로드 검증·오류 | `quotation/rust/webapi/src/lib.rs`, `limits.rs`, `errors.rs` |
| 브라우저 화면 | `quotation/web/src/panel.ts`, `panel.html` |
| 브라우저 변환 실행 | `quotation/web/src/converter.ts`, `convert.worker.ts`, `engine.js` |
| Windows 앱 | `quotation/desktop/src/ui.rs`, `convert.rs` |
| 배포·빌드 설정 | `web/vite.config.ts`, `web/wrangler.jsonc`, `web/scripts/` |
| Python 호환 API | `quotation/python/quotation/core/` (변환 규칙은 Rust) |

## 작은 범위부터 읽기

- `rg --files <해당 폴더>` → `rg -n <심볼> <폴더>` → 필요한 파일/범위 순서로 탐색한다.
- `target/`, `node_modules/`, `.cache/`, `web/dist/`, `web/public/engine/`는 생성물이다.
  원인 확인이 필요할 때만 읽고, 일반 검색에 `--no-ignore`를 쓰지 않는다.
- lockfile·고객 샘플·과거 계획서를 기본 컨텍스트로 모두 읽지 않는다.
- 운영 소스는 파일당 500줄 이하로 유지한다. 줄을 압축해 맞추지 말고 책임별로 나눈다.
  테스트·명세·lockfile·생성물에는 이 숫자를 기계적으로 적용하지 않는다.
- 런타임 공통 코드는 기능 안에 둔다. 셸은 `@quotation/panel` 진입점만 참조한다.

## 설정과 검증

- `.env*`는 루트에서 계정·인증 토큰만 다룬다. 실제 값은 출력하거나 커밋하지 않는다.
  허용 키와 일반 설정의 위치는 `doc/guide/CONFIGURATION.md`를 따른다.
- UI/설정 변경: `npm --prefix web test` 및 `npm --prefix web run build`.
- 변환 코어 변경: `cargo test -p quotation-core -p quotation-webapi`.
- Rust 변경: `cargo fmt --all -- --check`, 관련 크레이트 clippy.
- 명세·골든은 `doc/spec/`, 회귀 테스트는 `quotation/rust/core/tests/`에 있다.
- `doc/plan/`은 과거 설계 기록이다. 현재 구조는 루트 README와 기능 README를 우선한다.
