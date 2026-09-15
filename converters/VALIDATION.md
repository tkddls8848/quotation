# 변환기 검증 기록

측정일: 2026-09-15.

| 경로 | 상태 |
|---|---|
| PDF → HWPX (이미지·텍스트) | 실제 화면·실제 브라우저에서 통과. **한글에서 열어 본 검증은 남아 있다** |
| HWP(5.0) → PDF | 공개 문서 36건 중 30건 변환, 2건 접수 거절, 4건 변환 실패. 알려진 손실 1종 |

두 경로 모두 실제 업무 문서로는 아직 재 보지 않았다.

## 구현 파일

브라우저:

- `web/src/pdf-hwpx.ts`: PDF.js 렌더링·텍스트 추출, 회전·해상도, 쪽 한도, 취소와 자원 해제.
- `web/src/pdf-text.ts`: 글자 좌표에서 읽는 순서·문단·단순 표를 추정한다.
- `web/src/hwpx-writer.ts`: 쪽마다 구역 하나를 만들어 HWPX 패키지로 묶는다.
- `web/src/pdf-panel.ts`: PDF 편집기의 쪽 선택·순서·회전을 그대로 HWPX 저장에 연결한다.
- `web/src/hwp-pdf-panel.ts`: 전송 동의, 작업 접수·상태·내려받기·취소·삭제.
- `web/probe.html`, `web/src/hwpx-probe.ts`: 한 쪽짜리 최소 HWPX 생성기. 개발 검증 전용이며 배포 빌드에 들어가지 않는다.

변환 서버:

- `server/app.py`: 접수·상태·결과·삭제 API. HWP 5.0 헤더 검사, 작업별 토큰, 격리 컨테이너 실행, 보관 기한.
- `server/Dockerfile`, `server/convert.py`: LibreOffice + H2Orestart 0.7.14 컨테이너와 그 진입점.
- `server/hwptext.py`: HWP 본문 글자만 읽는 최소 판독기. 검증에만 쓰고 변환 경로는 부르지 않는다.
- `server/smoke.py`: 실제 API·엔진으로 변환하고 **본문 글자가 살아남았는지** 대조한다.

검사 스크립트:

- `web/scripts/check-converters.mjs`: 실제 Chromium 으로 공개 화면을 조작한다(이미지·텍스트 저장, 표, 혼합 쪽 크기, 스캔 쪽 처리, 선택·회전, 취소, 모바일 폭).
- `web/scripts/check-hwpx.mjs`: 한 쪽짜리 HWPX 를 만들어 패키지 구조·쪽 크기·PNG 픽셀을 확인한다.
- `desktop/verify-hwpx.ps1`: 한글 자동화로 HWPX 를 열어 본다.

## 재현

저장소 루트에서 실행한다.

```powershell
npm.cmd --prefix web ci
npm.cmd --prefix web run typecheck
npm.cmd --prefix web test
npm.cmd --prefix web run build
npm.cmd --prefix web run dev -- --host 127.0.0.1 --port 18574
```

다른 터미널에서 (Playwright Chromium 이 없으면 `web/` 에서 `npx.cmd playwright install chromium`):

```powershell
node converters/web/scripts/check-converters.mjs
node converters/web/scripts/check-hwpx.mjs
```

HWP → PDF 는 Docker 와 파이썬 의존성이 필요하다.

```powershell
docker build -t quotation-hwp-converter:local converters/server
python -m venv .cache/converter-venv
.cache\converter-venv\Scripts\python.exe -m pip install -r converters/server/requirements.txt
.cache\converter-venv\Scripts\python.exe converters/server/app.py
```

또 다른 터미널에서 (검증용 문서를 직접 지정한다):

```powershell
.cache\converter-venv\Scripts\python.exe converters/server/smoke.py <문서.hwp> ...
$env:HWP_TEST_FILE = "<문서.hwp>"; node converters/web/scripts/check-converters.mjs
```

산출물은 `.cache/hwpx-validation/`, `.cache/hwp-validation/` 에 생성되며 저장소에는 커밋하지 않는다.
`smoke.py` 는 콘솔 코드 페이지와 무관하게 `report.txt` 를 UTF-8 로 남긴다.

## PDF → HWPX

`check-converters.mjs` 가 실제 화면에서 확인한 것:

| 산출물 | 결과 |
|---|---|
| `multi-image.hwpx` | 87,539바이트 · 구역 3 · 그림 3 (쪽 크기 400×500, 500×300, 300×400pt 혼합) |
| `multi-text.hwpx` | 29,000바이트 · 구역 3 · 그림 1 (텍스트 2쪽 + 글자 없는 쪽을 이미지로) |
| `skip-text.hwpx` | 8,982바이트 · 구역 2 (글자 없는 쪽 제외 선택) |
| `selected-image.hwpx` | 36,477바이트 · 구역 1 · 쪽 크기 30000×50000 (선택 쪽 + 90° 회전 반영) |

함께 확인한 것: 표 추정(`rowCnt="2" colCnt="2"`), XML 특수문자(`Title < & >`) 이스케이프,
글자 없는 쪽의 세 가지 처리(중단·이미지·제외)와 그때의 안내문, 변환 취소,
`secCnt` 와 구역 수의 일치, 375px 폭에서 가로 스크롤 없음, 브라우저 미처리 오류 없음.

`check-hwpx.mjs` 의 한 쪽 생성 기록:

| 합성 입력 | DPI | HWPX 크기 | 생성부터 다운로드 검사까지 |
|---|---|---|---|
| 300×400pt, 추가 회전 0° | 150 | 25,067바이트 | 약 1.0초 |
| 500×200pt, 원본 90° + 추가 90° | 200 | 31,599바이트 | 약 0.9초 |
| 300×400pt, 추가 회전 90° | 300 | 59,898바이트 | 약 0.9초 |

첫 ZIP 항목이 압축하지 않은 `mimetype` 인지, 쪽 크기와 PNG 픽셀 수가 회전·해상도와 맞는지,
잘못된 쪽 번호·취소·PDF 아닌 입력을 어떻게 알리는지까지 같은 스크립트가 본다.

합성 문서 한 번의 기록이므로 실제 업무 문서의 성능이나 모바일 메모리 한도를 보장하지 않는다.
검증 입력은 기본 글꼴의 영문과 색 도형이다. 한글 글꼴·CMap·JPEG2000 같은 추가 렌더링 자산이
필요한 문서는 아직 재 보지 않았다.

### 남은 관문 — 한글에서 열기

**이 검증은 아직 통과하지 못했다.** 이 PC 의 한글 자동화 버전은 `8, 0, 0, 466` 이고 HWPX 를
지원하지 않는다. 별도 빈 문서의 HWPX 저장 호출이 응답하지 않아 검증용 프로세스를 종료했다.
사용자 문서를 열거나 바꾸지 않았고, 검증 스크립트는 이 환경에서 명시적으로 실패하도록 두었다.

HWPX 를 지원하는 한글에서 다음을 실행하고 결과를 눈으로 비교해야 한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File converters/desktop/verify-hwpx.ps1 -InputPath .cache/hwpx-validation/page-1-rotate-0-150dpi.hwpx
```

확인할 것: 복구 경고 없음, 쪽 수·쪽 크기 일치, 그림 잘림과 빈 쪽 없음, 텍스트 방식의 문단·표를
실제로 고쳐 다시 저장할 수 있는지.

## HWP(5.0) → PDF

엔진은 Debian trixie 의 LibreOffice Writer 에 H2Orestart 0.7.14(GPLv3) 를 얹은 컨테이너다.
작업마다 새 컨테이너를 만들고 `--network none --read-only --cap-drop=ALL`,
메모리 1G, CPU 1, 프로세스 128, 출력 64MB, `/tmp` 256MB 로 묶는다. 원본은 읽기 전용으로 붙인다.

검증 문서는 pyhwp 시험 자료의 공개 HWP 5.0 문서 36건이다(표·병합·캡션, 머리말·꼬리말, 다단,
각주·미주, 그림, 글상자, 수식, 글꼴, 글머리표, 탭, 정렬, 쪽 나눔, 암호 문서, 배포용 문서).
사용자 문서는 쓰지 않았다.

```text
30/36 converted, 6 refused, 2 body text lines dropped.
```

건당 2.1~5.1초, 산출물 6,630~92,007바이트, 1~16쪽.

### 살아남은 것

30건에서 본문 글자가 모두 살아남았다. `smoke.py` 가 원본 HWP 의 문단 글자를 직접 읽어
PDF 에서 추출한 글자와 순서까지 대조한다. 표·머리말·꼬리말·다단·글머리표·탭·정렬·쪽 나눔
문서가 여기 든다. 표 캡션과 쪽 번호는 자동 번호가 붙은 채로(`표  위 캡션` → `표 1 위 캡션`)
나오므로 대조는 글자가 순서대로 살아 있는지만 본다 — **배치가 같은지는 보지 않는다.**

### 알려진 손실 — 그림·글상자 캡션

`textbox.hwp` 의 `그림  캡션`, `multicolumns-in-common-controls.hwp` 의 `그림  ` 이
PDF 에 나오지 않는다. 표 캡션은 나오고 그림 캡션만 빠진다. 조용히 빠지는 손실이므로
화면에 적었고, `smoke.py` 는 이 때문에 실패(종료 코드 1)로 끝난다.

### 알려진 실패 — 변환 자체가 안 되는 문서

`footnote-endnote.hwp`, `sample-5017.hwp`, `sample-5017-pics.hwp`, `shapepict-scaled.hwp`.
UNO 로 직접 열어 보면 LibreOffice 프로세스가 문서를 읽다가 죽는다(`DisposedException:
Binary URP bridge disposed during call`). 컨테이너가 0 아닌 코드로 끝나므로 API 는 실패로
알리고, 절반만 만들어진 PDF 를 성공으로 내주지 않는다.

`--infilter=Hwp2002_Reader` 로 필터를 강제하면 **모든** 문서가 같은 오류로 실패한다.
H2Orestart 의 탐지 서비스를 거치지 않기 때문이다. 유형 탐지에 맡겨야 한다
(`server/convert.py` 에 적어 두었다).

### 접수 거절

`password-12345.hwp`(암호), `viewtext.hwp`(배포용)는 컨테이너에 닿기 전에 거절한다.
LibreOffice 는 배포용 문서를 열 수 있지만, 작성자가 걸어 둔 제한을 우회하는 셈이라 받지 않는다.

### 이 검증이 잡아낸 결함

- 필터 강제 지정 때문에 모든 변환이 실패하고 있었다. 유형 탐지로 바꿨다.
- 끝난 작업이 15분 동안 서버의 작업 자리를 물고 있었다. 16건을 처리하면 그 뒤 모든 접수가
  "서버가 처리 중입니다" 로 거절됐다. 결과를 내려받고 삭제하면 자리를 바로 돌려주도록 고쳤다.

### 아직 하지 않은 검증

- **한글이 내보낸 기준 PDF 와의 배치 비교.** 글꼴이 다르면 줄바꿈 위치가 달라진다.
  컨테이너에는 함초롬체가 없고 Noto CJK 로 대체된다. 이 검증 없이는 "보이는 그대로" 를
  약속할 수 없다.
- 실제 업무 문서(제안요청서·과업내용서 같은 긴 문서, 수십 MB, 복잡한 병합 표).
- 동시 작업 부하와 시간 초과 종료. 코드에는 있으나 실측하지 않았다.
- 공개 서버 운영(TLS, 접근키, 보관 기한, 비용). 지금 구성은 로컬 루프백 전용이다.
