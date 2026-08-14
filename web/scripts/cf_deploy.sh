#!/usr/bin/env bash
# Cloudflare Workers Builds 의 배포 단계.
#
#   프로덕션 배포 : bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_deploy.sh deploy
#   프리뷰 업로드 : bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_deploy.sh versions upload
#   스테이징이면  : ... cf_deploy.sh deploy --env staging
#
# Workers Builds 는 프로덕션 브랜치와 그 외 브랜치의 배포 명령을 따로 둔다
# (기본값이 각각 `wrangler deploy`, `wrangler versions upload`). 둘 다 이
# 스크립트를 쓰도록 인자를 그대로 받는다. 인자가 없으면 deploy 로 본다.
#
# cf_build.sh 와 마찬가지로 자기 위치를 보고 web/ 으로 이동하므로 대시보드의
# Root directory 값에 영향을 받지 않는다.
#
# wrangler 가 아니라 pywrangler 를 부르는 이유: wrangler 는 pyproject.toml 을
# 읽지 않아 lxml·openpyxl 이 번들에서 빠진다. pywrangler 는 그것을 먼저
# vendoring 한 뒤 wrangler 에 그대로 넘긴다. 인자도 그대로 전달된다.
#
# `python3 -m` 으로 부르는 이유: pip 이 설치한 실행 파일이 빌드 환경의 PATH 에
# 없을 수 있다.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "=== 작업 폴더: $(pwd)"
test -f wrangler.jsonc || { echo "wrangler.jsonc 를 찾지 못했습니다"; exit 1; }

# 빌드 단계를 건너뛰고 배포만 도는 경우에도 도구가 있어야 한다.
python3 -m pywrangler --version >/dev/null 2>&1 || \
  python3 -m pip install --quiet --disable-pip-version-check workers-py "uv>=0.12.3"

if [ "$#" -eq 0 ]; then
  set -- deploy
fi

echo "=== 배포: python3 -m pywrangler $*"
exec python3 -m pywrangler "$@"
