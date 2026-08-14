#!/usr/bin/env bash
# Cloudflare Workers Builds 의 빌드 단계.
#
# 대시보드에는 아래 두 줄만 넣는다. 실제 순서는 저장소가 갖고 있어야 대시보드
# 설정과 코드가 어긋나지 않는다.
#
#   Build command  : bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_build.sh
#   Deploy command : bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_deploy.sh deploy
#
# 이 스크립트는 자기 위치를 보고 web/ 으로 이동한다. 대시보드의 Root directory
# 가 저장소 루트든 web 이든 똑같이 동작한다. (Root directory 가 어긋나면
# wrangler 가 설정을 못 찾아 "Missing entry-point" 로 죽는다.)
#
# 무료 계정 기준 배포에는 Python Worker 가 없다. 변환은 브라우저에서 돌고
# Cloudflare 는 정적 자산만 내려 준다(결정 decisions/0002). 그래서 여기서 pywrangler
# 나 Pyodide vendoring 을 하지 않는다 — 빌드가 짧아지고 실패 지점이 줄어든다.
# Workers Paid 에 서버 변환 API 까지 올릴 때만 cf_deploy.sh 가 그것을 챙긴다.
#
# 순서가 중요하다.
#   1) 공용 코어·템플릿 생성: 브라우저 엔진이 이것을 담아 간다.
#   2) 브라우저 변환 엔진: Pyodide 런타임과 파이썬 모듈을 frontend/public/py 로.
#   3) 정적 자산: wrangler.jsonc 의 assets.directory(frontend/dist) 가 있어야 한다.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "=== 작업 폴더: $(pwd)"
test -f wrangler.jsonc || { echo "wrangler.jsonc 를 찾지 못했습니다"; exit 1; }

# Cloudflare 빌드 환경은 pyproject.toml 을 보고 `pip install .` 을 먼저 돌린다.
# 그 부산물(*.egg-info)이 web/ 에 남으면 배포에 딸려 올라간다.
rm -rf ./*.egg-info

# 화면 아래에 찍힐 배포 판본. 대시보드가 주는 커밋 해시를 그대로 쓴다.
export DEPLOYMENT_VERSION="${DEPLOYMENT_VERSION:-${WORKERS_CI_COMMIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo dev)}}"
echo "=== 배포 판본: ${DEPLOYMENT_VERSION}"

echo "=== 1/3 공용 코어와 템플릿 생성"
python3 scripts/sync_core.py

echo "=== 2/3 브라우저 변환 엔진 생성"
python3 scripts/build_browser_engine.py

echo "=== 3/3 정적 자산 빌드"
npm ci --prefix frontend
npm run build --prefix frontend

echo "=== 빌드 완료"
