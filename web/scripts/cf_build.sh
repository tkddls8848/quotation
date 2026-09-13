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
# 무료 계정 기준 배포에는 서버 코드가 없다. 변환은 브라우저에서 돌고
# Cloudflare 는 정적 자산만 내려 준다(결정 decisions/0002).
#
# web/ 은 **셸** 이다 — 탭과 공통 틀만 갖는다. 도구는 최상위 기능 폴더에 있고
# (quotation/, fire/) 셸이 별명으로 부른다. 그래서 빌드 순서가 이렇다.
#
#   1) 변환 엔진: 견적기의 Rust 코어를 wasm 으로 지어 web/public/engine 으로.
#      빌드 이미지에 Rust 가 없으므로 도구부터 갖춘다 (ensure_wasm_toolchain.sh).
#   2) 데스크톱 앱: 릴리스의 EXE 를 web/public/download 로. 저장소에 담아 두지
#      않고 배포할 때 받아 온다 (fetch_desktop_app.sh).
#   3) 정적 자산: wrangler.jsonc 의 assets.directory(dist) 가 있어야 한다.
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

echo "=== 1/3 브라우저 변환 엔진 생성"
# Cloudflare 빌드 이미지에는 Node·Python·Go·Ruby 만 있고 Rust 가 없다. 없는 것만
# 갖춘다 — 이미 있는 곳(개발 기계, GitHub Actions)에서는 판본만 찍고 지나간다.
export PATH="${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"
bash scripts/ensure_wasm_toolchain.sh
python3 ../quotation/web/scripts/build_browser_engine.py

echo "=== 2/3 데스크톱 앱 가져오기"
# 화면에서 바로 받아지게 릴리스의 EXE 를 정적 자산에 담는다. 못 받아도 빌드는
# 계속한다 (화면이 GitHub 쪽으로 물러난다).
bash scripts/fetch_desktop_app.sh

echo "=== 3/3 정적 자산 빌드"
npm ci
npm run build

echo "=== 빌드 완료"
