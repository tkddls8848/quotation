#!/usr/bin/env bash
# 데스크톱 EXE 를 정적 자산으로 함께 내보낸다.
#
# 화면의 <EXE 내려받기> 가 github.com 으로 빠지지 않고 이 사이트에서 바로
# 받아지게 하려는 것이다. 그렇다고 EXE 를 저장소에 커밋하지는 않는다 — 판본을
# 올릴 때마다 12 MiB 짜리 사본이 git 이력에 영구히 쌓이고, 바이너리는 델타
# 압축이 먹지 않아 되돌릴 방법이 없다. 이 저장소는 생성물을 추적하지 않는다.
#
# 그래서 **배포할 때 받아서 함께 내보낸다.** EXE 를 만드는 것은 Windows 러너다
# (.github/workflows/desktop-release.yml). 여기서는 그 결과물을 가져오기만 한다.
#
# 받지 못해도 빌드를 세우지 않는다. 아직 릴리스가 없거나 GitHub 가 막혔을 때
# 웹 배포까지 같이 죽을 이유가 없다 — 그때는 화면이 GitHub 릴리스 쪽으로
# 물러난다 (quotation/web/src/panel.ts).
set -euo pipefail

REPO="${DESKTOP_REPO:-tkddls8848/quotation}"
WEB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$WEB/public/download"

# Cloudflare 정적 자산은 파일 하나가 25 MiB 를 넘을 수 없다. 넘는 것을 담으면
# 배포가 통째로 거절되므로, 그 전에 여기서 걸러 낸다.
MAX_BYTES=$((25 * 1024 * 1024))

python3 - "$REPO" "$OUT" "$MAX_BYTES" <<'PY'
import json, sys, urllib.error, urllib.request
from pathlib import Path

repo, out_dir, max_bytes = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
api = f"https://api.github.com/repos/{repo}/releases/latest"


def fetch(url, timeout=120):
    request = urllib.request.Request(url, headers={"User-Agent": "cf-build"})
    return urllib.request.urlopen(request, timeout=timeout)


try:
    with fetch(api, timeout=30) as response:
        release = json.load(response)
except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
    print(f"    데스크톱 앱 릴리스를 찾지 못했습니다 ({exc}). 화면은 GitHub 쪽으로 물러납니다.")
    sys.exit(0)

asset = next((a for a in release.get("assets", [])
              if a["name"].lower().endswith(".exe")), None)
if asset is None:
    print("    릴리스에 EXE 가 없습니다. 화면은 GitHub 쪽으로 물러납니다.")
    sys.exit(0)

size = asset["size"]
if size > max_bytes:
    print(f"    EXE 가 {size / 1048576:.1f} MiB 라 정적 자산 한도(25 MiB)를 넘습니다. "
          "함께 내보내지 않고 GitHub 쪽으로 물러납니다.")
    sys.exit(0)

out_dir.mkdir(parents=True, exist_ok=True)
target = out_dir / asset["name"]
with fetch(asset["browser_download_url"]) as response:
    target.write_bytes(response.read())

got = target.stat().st_size
if got != size:
    # 반쯤 받은 파일을 배포하면 사용자가 깨진 EXE 를 받는다.
    target.unlink()
    print(f"    내려받은 크기가 다릅니다 ({got} != {size}). 버리고 GitHub 쪽으로 물러납니다.")
    sys.exit(0)

(out_dir / "desktop.json").write_text(json.dumps({
    "file": asset["name"],
    "url": f"/download/{asset['name']}",
    "size": size,
    "version": release.get("tag_name", ""),
    "published": release.get("published_at", ""),
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"    {asset['name']} {size / 1048576:.1f} MiB ({release.get('tag_name', '')})")
PY
