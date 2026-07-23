# 2005년 원본 프로그램

새 프로그램은 이 화일들을 쓰지 않는다. **역공학의 근거**로 보관한다.

| 파일 | 내용 |
|---|---|
| `setup.exe`, `SETUP.LST` | VB6 Package & Deployment Wizard 배포본 |
| `pConvertXMLtoExcel-2005-05-13.CAB` | 본체(`pConvertXMLtoExcel-2005-05-13.exe`)와 런타임·OCX·템플릿 |

## 꺼내는 법

```powershell
expand.exe .\legacy\pConvertXMLtoExcel-2005-05-13.CAB -F:* .\out\legacy
```

## 왜 남겨 두는가

- `SPEC_CELLMAP.md` 의 XPath·셀 범위·라벨 문구는 이 EXE 의 문자열에서 뽑았다.
  사양에 의문이 생기면 여기로 돌아와 확인할 수 있다.
- **할인율 적용 동작이 아직 미검증**이다 (`SPEC_CELLMAP.md` §7). 할인이 들어간
  골든이 없어서, 필요하면 원본을 호환 환경에서 돌려 결과를 얻어야 한다.

지워도 새 프로그램 동작에는 영향이 없다. 다만 위 두 가지 근거를 잃는다.
