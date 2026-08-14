# 사고 0002 — Pyodide 의 libxml2 는 EUC-KR 을 모른다

- 날짜: 2026-08-14
- 상태: **고침** (`quotation/core/xml_reader.py`)
- 드러난 경위: [결정 0002](../decisions/0002-convert-in-browser.md) 를 적용하고
  실제로 돌려 보는 중

## 증상

EUC-KR 견적 XML 이 통째로 변환되지 않았다.

```text
XMLSyntaxError: Unsupported encoding EUC-KR, line 1, column 38
```

## 원인

Pyodide 의 lxml 이 iconv 없이 빌드되어 있다. 2005년 형식 견적 XML 은 EUC-KR
이 흔하므로, 그대로 두면 그 견적서들은 웹에서 만들 수 없었다.

**계획 §4 의 Python Worker 로 갔어도 같은 결과였다.** 그쪽도 Pyodide 다.

## 왜 미리 못 잡았나

계획 §11 Phase 0 의 게이트가 `pywrangler sync` 성공까지만 보고 **실제 변환을
돌리지 않았다.** 의존성이 설치된다는 것과 그 의존성이 우리 입력을 처리한다는
것은 다른 이야기다.

## 고친 것

`quotation/core/xml_reader.py` 에 좁은 대비책을 두었다. 파싱이 **아예 실패한
경우에 한해**, 선언된 인코딩을 파이썬 표준 코덱(Pyodide 에도 EUC-KR·CP949·
Shift_JIS 등이 모두 있다)으로 디코딩해 UTF-8 로 다시 적고 **한 번만** 더
읽는다.

- 문자는 하나도 바뀌지 않으므로 파서가 보는 문서는 iconv 가 있는 데스크톱이
  보는 것과 같다.
- 이미 읽히는 문서에는 이 경로가 닿지 않는다.
- 다시 읽어도 실패하면 **처음 오류 문구를 그대로** 알린다(원본 프로그램과 같은
  문구를 지킨다).

## 무엇이 지키는가

`tests/fixtures/public/euckr_quote.xml` 이 코어 테스트와 브라우저 동일성
검증(`web/tests/test_browser_parity.py`, `test_browser_e2e.py`) 양쪽에 들어
있다. 브라우저에서 이 fixture 가 깨지면 CI 의 `browser` 잡이 잡는다.
