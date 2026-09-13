#!/usr/bin/env bash
# 브라우저 변환 엔진(Rust→WASM)을 지을 도구를 갖춘다.
#
# Cloudflare Workers Builds 의 빌드 이미지에는 Node·Python·Go·Ruby 는 있어도
# **Rust 가 없다.** 그래서 cf_build.sh 가 곧바로 build_browser_engine.py 를
# 부르면 이렇게 죽는다.
#
#   === 2/3 브라우저 변환 엔진 생성
#   === wasm-pack build (rust/wasm)
#   wasm-pack 이 없습니다. cargo install wasm-pack 으로 설치하십시오.
#   Failed: error occurred while running build command
#
# 이 스크립트는 **없는 것만** 채운다. 이미 갖춰진 곳(개발 기계, GitHub
# Actions)에서는 판본만 찍고 끝난다.
#
#   cargo                   없으면 rustup 으로 설치한다 (minimal 프로파일)
#   wasm32-unknown-unknown  없으면 붙인다
#   wasm-pack               없으면 공식 릴리스 이진을 내려받는다
#
# 설치 자리는 `${CARGO_HOME:-$HOME/.cargo}/bin` 이다. **부르는 쪽이 그 경로를
# PATH 에 넣어야 한다** — 자식 프로세스가 바꾼 PATH 는 부모로 올라가지 않는다.
#
#   export PATH="${CARGO_HOME:-$HOME/.cargo}/bin:$PATH"
#   bash web/scripts/ensure_wasm_toolchain.sh
#
# wasm-pack 을 `cargo install` 로 짓지 않는 이유는 시간이다. 원본 빌드는 CF
# 빌더에서 몇 분을 먹는데 빌드 한도가 20 분이고, 그 뒤에 엔진 본체를 또 지어야
# 한다. 공식 릴리스의 정적 이진(musl)은 내려받아 sha256 으로 대조하면 몇 초다.
# 그 길이 막히면 `cargo install` 로 되돌아간다.
set -euo pipefail

# 판본을 여기 한 곳에 둔다. CI 와 Cloudflare 가 같은 도구로 짓게 하기 위함이다.
RUST_VERSION="${RUST_VERSION:-stable}"
WASM_PACK_VERSION="${WASM_PACK_VERSION:-0.15.0}"

# 공식 릴리스 이진의 sha256 (github.com/wasm-bindgen/wasm-pack).
# 판본을 올릴 때 이 값도 같이 올린다. 어긋나면 설치하지 않고 멈춘다.
WASM_PACK_SHA256_X86_64="c09f971ecaed9a2efc80fdcea7a00ef6b53c7fadc8c57d1f61b53a6aa66b668a"
WASM_PACK_SHA256_AARCH64="e17ef0806381c3a0acb9c9ddad643a49facaa5a2ecf657a421d4d8f3357a24b7"

# 빌더의 네트워크는 가끔 한 번씩 걸린다. 붙는 데 20 초, 받는 데 3 분이 넘으면
# 끊고 세 번까지 다시 해 본다. 그래도 안 되면 원본 빌드로 되돌아간다.
CURL_RETRY=(--retry 3 --retry-connrefused --connect-timeout 20 --max-time 180)

TARGET="wasm32-unknown-unknown"
CARGO_BIN="${CARGO_HOME:-$HOME/.cargo}/bin"
export PATH="$CARGO_BIN:$PATH"

# 내려받는 자리. 어떻게 끝나든 지운다. (함수 안에서 trap ... RETURN 을 걸면
# 그 뒤의 모든 함수 반환마다 다시 돌아 set -u 에 걸린다.)
WORK=""
trap 'if [ -n "$WORK" ]; then rm -rf "$WORK"; fi' EXIT

have() { command -v "$1" >/dev/null 2>&1; }

sha256_of() {
  if have sha256sum; then sha256sum "$1" | cut -d' ' -f1
  elif have shasum; then shasum -a 256 "$1" | cut -d' ' -f1
  else echo "sha256 을 계산할 도구가 없습니다 (sha256sum 또는 shasum)" >&2; return 1
  fi
}

ensure_rust() {
  if have cargo; then
    echo "=== rust: $(cargo --version)"
    return
  fi
  have curl || { echo "curl 이 없어 rustup 을 받지 못합니다"; exit 1; }
  echo "=== rust 설치: rustup (${RUST_VERSION}, minimal)"
  # --no-modify-path: 빌더의 셸 프로파일을 건드리지 않는다. PATH 는 위에서 쥔다.
  curl --proto '=https' --tlsv1.2 -sSf "${CURL_RETRY[@]}" https://sh.rustup.rs \
    | sh -s -- -y --profile minimal --default-toolchain "$RUST_VERSION" --no-modify-path
  have cargo || { echo "rustup 을 깔았는데도 cargo 가 보이지 않습니다: $CARGO_BIN"; exit 1; }
  echo "=== rust: $(cargo --version)"
}

ensure_target() {
  if ! have rustup; then
    # 배포판이 깔아 준 Rust 다. 표준 라이브러리가 이미 있다고 보고 넘어간다.
    echo "=== target: rustup 이 없어 ${TARGET} 확인을 건너뜁니다"
    return
  fi
  if rustup target list --installed | grep -qx "$TARGET"; then
    echo "=== target: ${TARGET} 있음"
  else
    echo "=== target 추가: ${TARGET}"
    rustup target add "$TARGET"
  fi
}

# 공식 릴리스 이진을 받는다. 받지 못하면 1 을 돌려 호출 쪽이 되돌아가게 한다.
fetch_wasm_pack() {
  local arch sha name url got
  case "$(uname -s)/$(uname -m)" in
    Linux/x86_64)        arch="x86_64";  sha="$WASM_PACK_SHA256_X86_64" ;;
    Linux/aarch64|Linux/arm64) arch="aarch64"; sha="$WASM_PACK_SHA256_AARCH64" ;;
    *) echo "=== wasm-pack: 릴리스 이진을 고정해 둔 조합이 아닙니다 ($(uname -s)/$(uname -m))"
       return 1 ;;
  esac
  have curl || return 1

  name="wasm-pack-v${WASM_PACK_VERSION}-${arch}-unknown-linux-musl"
  url="https://github.com/wasm-bindgen/wasm-pack/releases/download/v${WASM_PACK_VERSION}/${name}.tar.gz"
  WORK="$(mktemp -d)"

  echo "=== wasm-pack 내려받기: v${WASM_PACK_VERSION} (${arch})"
  curl -sSfL "${CURL_RETRY[@]}" -o "$WORK/wasm-pack.tar.gz" "$url" || return 1

  got="$(sha256_of "$WORK/wasm-pack.tar.gz")"
  if [ "$got" != "$sha" ]; then
    # 고정해 둔 판본의 바이트가 달라졌다는 뜻이다. 여기서는 되돌아가지 않고 멈춘다.
    echo "내려받은 wasm-pack 의 sha256 이 다릅니다."
    echo "  기대: $sha"
    echo "  실제: $got"
    echo "  ${url}"
    exit 1
  fi

  tar -xzf "$WORK/wasm-pack.tar.gz" -C "$WORK"
  mkdir -p "$CARGO_BIN"
  cp "$WORK/$name/wasm-pack" "$CARGO_BIN/wasm-pack"
  chmod +x "$CARGO_BIN/wasm-pack"
}

ensure_wasm_pack() {
  if have wasm-pack; then
    echo "=== wasm-pack: $(wasm-pack --version)"
    return
  fi
  if ! fetch_wasm_pack; then
    echo "=== wasm-pack: 원본에서 짓습니다 (몇 분 걸립니다)"
    cargo install wasm-pack --locked --version "$WASM_PACK_VERSION"
  fi
  have wasm-pack || { echo "wasm-pack 을 갖추지 못했습니다"; exit 1; }
  echo "=== wasm-pack: $(wasm-pack --version)"
}

ensure_rust
ensure_target
ensure_wasm_pack
