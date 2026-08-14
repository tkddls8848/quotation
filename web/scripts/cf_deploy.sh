#!/usr/bin/env bash
# Cloudflare Workers Builds 의 배포 단계.
#
#   프로덕션 배포 : bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_deploy.sh deploy
#   프리뷰 업로드 : bash "$(git rev-parse --show-toplevel)"/web/scripts/cf_deploy.sh versions upload
#   스테이징이면  : ... cf_deploy.sh deploy --env staging
#   서버 변환까지 : ... cf_deploy.sh deploy --env server   (Workers Paid 전용)
#
# Workers Builds 는 프로덕션 브랜치와 그 외 브랜치의 배포 명령을 따로 둔다
# (기본값이 각각 `wrangler deploy`, `wrangler versions upload`). 둘 다 이
# 스크립트를 쓰도록 인자를 그대로 받는다. 인자가 없으면 deploy 로 본다.
#
# cf_build.sh 와 마찬가지로 자기 위치를 보고 web/ 으로 이동하므로 대시보드의
# Root directory 값에 영향을 받지 않는다.
#
# 어느 도구를 부를지는 대상에 따라 갈린다.
#
#   기본(무료 계정)   정적 자산만 올린다  -> wrangler 로 충분하다
#   --env server      Python Worker 포함  -> pywrangler 가 필요하다
#
# pywrangler 를 써야 하는 이유: wrangler 는 pyproject.toml 을 읽지 않아
# lxml·openpyxl 이 번들에서 빠지고 첫 요청에서 죽는다. pywrangler 는 그것을
# 먼저 vendoring 한 뒤 wrangler 에 그대로 넘긴다 (web/README.md).
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "=== 작업 폴더: $(pwd)"
test -f wrangler.jsonc || { echo "wrangler.jsonc 를 찾지 못했습니다"; exit 1; }

if [ "$#" -eq 0 ]; then
  set -- deploy
fi

# 대상 환경을 알아 둔다. wrangler 는 환경을 지정하지 않으면 경고를 낸다.
wants_server=false
has_env=false
for arg in "$@"; do
  case "$arg" in
    server) wants_server=true ;;
    --env|--env=*|-e) has_env=true ;;
  esac
  case "$arg" in --env=server) wants_server=true ;; esac
done

if [ "$wants_server" = true ]; then
  echo "=== Workers Paid 대상: Python Worker 를 함께 올립니다"
  python3 -m pywrangler --version >/dev/null 2>&1 || \
    python3 -m pip install --quiet --disable-pip-version-check workers-py "uv>=0.12.3"
  echo "=== 배포: python3 -m pywrangler $*"
  exec python3 -m pywrangler "$@"
fi

# 정적 자산만 올린다. 환경을 안 준 경우 최상위 환경임을 분명히 한다.
if [ "$has_env" = false ]; then
  set -- "$@" --env=""
fi
echo "=== 배포: npx wrangler $*"
exec npx wrangler "$@"
