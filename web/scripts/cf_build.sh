#!/usr/bin/env bash
# Cloudflare Workers Builds 의 빌드 단계.
#
# 대시보드에는 아래 두 줄만 넣는다. 실제 순서는 저장소가 갖고 있어야 대시보드
# 설정과 코드가 어긋나지 않는다.
#
#   Build command  : bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_build.sh
#   Deploy command : bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_deploy.sh
#
# 이 스크립트는 자기 위치를 보고 web/ 으로 이동한다. 대시보드의 Root directory
# 가 저장소 루트든 web 이든 똑같이 동작한다. (Root directory 가 어긋나면
# wrangler 가 설정을 못 찾아 "Missing entry-point" 로 죽는다.)
#
# 순서가 중요하다.
#   1) 배포 도구: pywrangler 가 Pyodide 의존성을 vendoring 한다. wrangler 만
#      쓰면 lxml·openpyxl 이 빠진 채 올라가 첫 요청에서 죽는다.
#   2) 공용 코어 복사: Worker 는 main 이 있는 폴더 아래 모듈만 번들에 담는다.
#   3) 정적 자산: wrangler.jsonc 의 assets.directory(frontend/dist) 가 있어야 한다.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "=== 작업 폴더: $(pwd)"
test -f wrangler.jsonc || { echo "wrangler.jsonc 를 찾지 못했습니다"; exit 1; }

echo "=== 1/3 배포 도구 설치"
python3 -m pip install --quiet --disable-pip-version-check workers-py "uv>=0.12.3"
python3 -m pywrangler --version

echo "=== 2/3 공용 코어를 Worker 번들로 복사"
python3 scripts/sync_core.py

echo "=== 3/3 정적 자산 빌드"
npm ci --prefix frontend
npm run build --prefix frontend

echo "=== 빌드 완료"
