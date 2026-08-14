# 결정 0001 — 템플릿을 R2 에서 번들로 옮긴다

- 날짜: 2026-08-14
- 상태: **적용됨**
- 뒤집은 것: [계획 §8 템플릿 운영 계획](../plan/web-app-plan.md#8-템플릿-운영-계획)

## 계획은 무엇이었나

계획 §8 은 템플릿을 비공개 R2 버킷에 버전별로 두고, Worker 변수
`ACTIVE_TEMPLATE_KEY` 로 활성 버전을 가리키도록 설계했다. 코드 배포 없이
템플릿만 갈아 끼우는 것이 목적이었다.

## 왜 바꿨나

- 템플릿은 중앙 한 개뿐이고, 사용자별 템플릿 요건은 아직 확정되지 않았다
  (계획 §16-5).
- 활성 키를 바꾸는 것도 결국 Worker 재배포가 필요하다. "코드 배포 없이 교체"
  라는 이점이 실제로는 크지 않았다.
- 대신 버킷 생성, 토큰 R2 권한, 업로드 절차, 키 관리, 그리고 요청 경로마다
  R2 가 실패할 가능성(`TEMPLATE_UNAVAILABLE`)이 늘었다. 운영 관문이 하나 더
  생기는 셈이었다.

## 무엇으로 바꿨나

- 원본은 `quotation/resources/견적서_template.xlsx` **하나뿐**이고 데스크톱과
  웹이 같은 파일을 쓴다.
- 배포 직전 `web/scripts/sync_core.py` 가 그 파일을 base64 로 담은
  `web/src/template_data.py` 를 만든다(30 KB → 41 KB. 7.5 MB 번들에 견주면
  무시할 수준이다). 생성물은 추적하지 않는다.
- 브라우저 배포에서는 `web/scripts/build_browser_engine.py` 가 같은 파일을
  `quotation-core.zip` 에 담는다.
- 템플릿 판본은 내용 해시(`sha256-…`)다. `/status` 와 `X-Template-Version`,
  `/py/engine.json` 에 그대로 실리므로 추적성은 유지된다.
- 교체는 `.xlsx` 를 고쳐 커밋하는 것이고, 롤백은 그 커밋을 되돌리는 것이다.

계획 §8.1 의 "공개 정적 자산으로 노출하지 않는다" 는 지켜진다. 템플릿은 정적
자산 폴더가 아니라 Worker 모듈과 코어 zip 으로만 들어가므로 URL 로 받아 갈 수
없다.

## 무엇이 지키는가

| 테스트 | 지키는 것 |
|---|---|
| `web/tests/test_api.py::test_bundled_template_matches_the_repository_original` | Worker 번들의 템플릿이 저장소 원본과 같다 |
| `web/tests/test_browser_engine.py::test_template_travels_as_the_repository_original` | 브라우저 엔진의 템플릿이 저장소 원본과 같다 |

## 되돌리는 조건

회사별·사용자별 템플릿이 필요해지거나, 개발자를 거치지 않고 템플릿을 교체해야
하는 운영 요건이 확정되면 계획 §8 의 R2 설계로 돌아간다. 그때 바꿀 곳은
`web/src/template.py` 의 출처 하나이고 나머지 층은 그대로다.
