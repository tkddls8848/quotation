#!/usr/bin/env bash
# Cloudflare Workers Builds 의 빌드 단계.
#
# 대시보드에는 이 스크립트 한 줄만 넣는다. 실제 순서를 저장소에서 관리해야
# 대시보드 설정과 코드가 어긋나지 않는다.
#
#   Root directory : web
#   Build command  : bash scripts/cf_build.sh
#   Deploy command : pywrangler deploy            (Worker 이름이 quotation-web)
#                    pywrangler deploy --env staging  (quotation-web-staging)
#
# 순서가 중요하다.
#   1) 배포 도구: pywrangler 가 Pyodide 의존성을 vendoring 한다. wrangler 만
#      쓰면 lxml·openpyxl 이 빠진 채 올라가 첫 요청에서 죽는다.
#   2) 공용 코어 복사: Worker 는 main 이 있는 폴더 아래 모듈만 번들에 담는다.
#   3) 정적 자산: wrangler.jsonc 의 assets.directory(frontend/dist) 가 있어야 한다.
set -euo pipefail

echo "=== 1/3 배포 도구 설치"
python3 -m pip install --quiet --disable-pip-version-check workers-py "uv>=0.12.3"
python3 -m pip show workers-py | sed -n '1,2p'

echo "=== 2/3 공용 코어를 Worker 번들로 복사"
python3 scripts/sync_core.py

echo "=== 3/3 정적 자산 빌드"
npm ci --prefix frontend
npm run build --prefix frontend

echo "=== 빌드 완료"
