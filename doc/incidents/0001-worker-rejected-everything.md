# 사고 0001 — 배포된 Worker 가 모든 변환을 거절했다

- 날짜: 2026-08-14
- 상태: **고침** (`d954ac6`, `0cbee12`)
- 범위: 서버 변환 경로(`web/src/worker.py`)에만 해당. 무료 계정 배포에는 이
  경로가 없다 — [결정 0002](../decisions/0002-convert-in-browser.md)

## 증상

어떤 XML 을 올려도 화면에 이것만 나왔다.

```text
첨부 화일을 읽지 못했습니다.   (INVALID_REQUEST, 400)
```

## 원인

이름이었다. `workers` SDK(`workers-runtime-sdk`)는 JS 객체를 그대로 넘기지
않고 **파이썬 클래스로 감싸서** 준다. `WorkerEntrypoint.fetch` 가 받는 것은
`js.Request` 가 아니라 `workers.Request` 다. 그런데 `worker.py` 는 JS 이름을
불렀다.

| `worker.py` 가 부른 것 | 실제 SDK API | 결과 |
|---|---|---|
| `await request.formData()` | `await request.form_data()` | `AttributeError` |
| `form.getAll("file")` | `form.get_all("file")` | `AttributeError` |
| `await entry.arrayBuffer()` | `await entry.bytes()` | `AttributeError` |
| `entry.type` | `entry.content_type` | 항상 빈 문자열 |

첫 줄에서 이미 `AttributeError` 가 났고, 그것을 감싸고 있던

```python
except Exception as exc:
    raise errors.invalid_request("첨부 화일을 읽지 못했습니다.") from exc
```

가 원인을 통째로 삼켰다. 사용자에게는 "깨진 multipart" 로 보였고 로그에도
`INVALID_REQUEST` 만 남아, **모든 변환이 실패하는데 단서가 없었다.**

## 왜 배포 전에 못 잡았나

`web/tests/` 는 순수 층(`api`, `conversion_adapter`)만 직접 불렀고, `worker.py`
는 `test_worker_smoke.py` 가 **소스를 정적으로** 보는 것이 전부였다. 런타임
객체를 다루는 그 스무 줄만 어떤 테스트도 실행하지 않았다.

계약 테스트가 아무리 촘촘해도, **런타임과 만나는 층을 한 번도 돌리지 않으면
그 층은 배포에서 처음 돈다.**

## 고친 것

1. `worker.py` 가 SDK 의 파이썬 이름을 쓴다.
2. `web/tests/test_worker_runtime.py` — SDK 와 같은 모양의 가짜 런타임으로
   `fetch()` 를 실제로 돌린다. 변환 성공, 파일 아닌 필드, 깨진 multipart,
   multipart 아닌 POST, `/status`·`/config`, 정적 자산 통과, 교차 출처 거절까지
   본다. 이름을 되돌려 놓으면 이 테스트가 프로덕션과 **똑같은 문구**로 죽는다.
3. 같은 파일의 `test_worker_uses_only_real_sdk_names` 가 `pywrangler sync` 로
   받아 둔 실제 SDK 소스를 파싱해, 가짜가 진짜와 어긋나지 않았는지 대조한다.
   CI 의 `bundle` 잡이 sync 직후 이것을 돌린다.
4. 삼키던 자리에 진단 한 줄을 남긴다 — 예외 **종류만** 남기므로 견적 내용은
   새지 않는다(계획 §13). 이번 사고였다면 로그에 `AttributeError` 가 찍혔다.

## 곁다리로 드러난 것

무료 계정 배포에는 Worker 가 없어 `/api/v1/convert` 가 정적 자산 처리기로
넘어가고 SPA 의 `index.html` 이 200 으로 돌아온다. 그것을 받아 `.xlsx` 로
저장하면 HTML 이 든 견적서가 된다. 대비책 경로(`web/frontend/src/api.ts`)가
응답의 `Content-Type` 을 확인하도록 했다.
