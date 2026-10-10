# 설정과 인증정보

현재 애플리케이션은 `.env`를 필요로 하지 않는다. 검토 시 실제 `.env*`와
`.dev.vars*` 파일은 발견되지 않았다. 기존 값을 옮기거나 삭제한 것은 없다.

`.env`를 사용하는 배포 도구를 추가할 때는 **저장소 루트의 인증정보 전용 파일**로
한정한다. 허용 키는 `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_WORKER_AI_API_TOKEN`,
`GITHUB_TOKEN`, `GH_TOKEN`이다. 값은 로컬 자격증명이나 CI secret에서 관리하고
Git에 넣지 않는다. 현재 코드가 `.env`를 자동 로드하는 것은 아니다.
새 인증 키가 필요하면 `web/scripts/env-policy.ts`의 허용 목록과 이 문서를 함께 고친다.

| 일반 설정 | 위치 |
|---|---|
| 개발 포트, 번들·별칭 | `web/vite.config.ts` |
| Worker 이름, 배포 환경, 정적 자산 경로 | `web/wrangler.jsonc` |
| 업로드·출력 크기, 품목 수 한도 | `quotation/rust/webapi/src/limits.rs` |
| 데스크톱 동작 기본값 | `quotation/desktop/src/config.rs` |
| 배포 판본 | CI의 `DEPLOYMENT_VERSION` → 공개 빌드 상수 |
| 릴리스 저장소 지정 | 빌드 프로세스의 `DESKTOP_REPO` 옵션 |
| 브라우저 테스트 실행 경로 | 프로세스의 `CHROMIUM_PATH`, `PLAYWRIGHT_BROWSERS_PATH` |

운영체제의 `PATH`, `LOCALAPPDATA`, CI가 주는 커밋 정보 같은 **프로세스 환경변수**는
그대로 사용한다. 인증정보 전용이라는 규칙은 `.env` 파일의 용도를 제한하며,
운영체제·CI 변수 전체를 인증정보로만 제한하지 않는다.

Vite는 `envDir: false`, `envPrefix: []`로 dotenv 자동 로딩과 `VITE_*` 브라우저
주입을 모두 차단한다. `DEPLOYMENT_VERSION`은 공개 판본이라 CI 프로세스에서만
읽어 명시적으로 노출한다. 여기에 비밀값을 넣으면 안 된다.
Vite 설정을 읽는 개발·빌드·테스트 단계에서 실제 환경 파일의 위치·키를 검사한다.
오류에는 파일 경로와 줄 번호만 표시하며 값이나 잘못된 원문은 출력하지 않는다.

생성물·의존성·캐시 내부는 환경 파일 검사에서 제외한다. 이 검사는 비밀값이
소스에 하드코딩되었는지 판별하는 범용 secret scanner를 대체하지 않는다.
