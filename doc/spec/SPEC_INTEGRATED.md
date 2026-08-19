# 통합 모드 명세 — 레노버 x86 구성 파일

- 대상: Lenovo DCSC(Data Center Solution Configurator)가 내려 주는 CFXML
- 적용: 화면의 `변환 모드` 토글에서 **통합** 을 고른 경우에만
- 구현: [`quotation/core/integrated.py`](../../quotation/core/integrated.py),
  [`quotation/core/dcsc_summary.py`](../../quotation/core/dcsc_summary.py),
  [`quotation/core/modes.py`](../../quotation/core/modes.py)
- 검증: [`tests/test_integrated.py`](../../tests/test_integrated.py),
  [`tests/test_dcsc_summary.py`](../../tests/test_dcsc_summary.py),
  [`web/tests/test_modes.py`](../../web/tests/test_modes.py)

## 1. 왜 모드가 필요한가

문서 **형식** 은 IBM eConfig Export 와 같다. `CFXML/CFData/ProductLineItem`
이하 구조도, XPath 도 그대로 쓴다. 다른 것은 **값이 뜻하는 바** 이며 지금까지
확인된 차이는 둘뿐이다. 그 둘 때문에 UNIX 모드로 읽으면 시트 이름이 겹치고
금액이 부풀려진다.

UNIX 모드는 한 줄도 달라지지 않는다. 산출물이 셀 단위로 같은지는
`tests/test_writer.py`(골든)와 `web/tests/test_browser_parity.py` 가 지킨다.

## 2. 장비 이름은 ProductName 에 있다

### 2.1 무엇이 문제인가

한 파일에 같은 기종을 여러 대 담으면 `ProductDescription` 이 전부 같다.

```text
그룹 1000   ThinkSystem SR650 V4-3yr Base Warranty
그룹 7000   ThinkSystem SR650 V4-3yr Base Warranty
…           (열 그룹 모두 같다)
```

UNIX 모드의 종목 키는 이 설명에서 따온다. 그래서 시트 이름이 열 장 모두
`THINKSYSTEM SR650 V4-3YR BASE W` 가 되고, 이름이 겹치자 openpyxl 이 뒤에
숫자를 이어 붙여 `…BASE W1` … `…BASE W9` 를 만든다. **31자 제한을 넘긴
32자 이름** 이라 Excel 이 경고를 낸다. 사람이 볼 이름도 아니다.

### 2.2 무엇으로 삼는가

장비를 구분하는 이름은 구성기에서 **사람이 적어 넣은** `ProductName` 에 있다.

```text
그룹 1000   ProductName = 백업서버_1식
그룹 7000   ProductName = 타시스템 연계서버_1식
그룹 19000  ProductName = 메일/스펨_1식
```

Lenovo 가 내려 주는 요약표(Summary)도 그 이름을 설명 앞에 붙여 적는다
(`백업서버_1식 : ThinkSystem SR650 V4-3yr Base Warranty`). 손으로 만들던
견적서의 종목 칸도 같은 이름을 쓴다.

규칙은 다음과 같다.

| 항목 | 값 |
|---|---|
| 종목 키 (`Group.item_key`) | 본체 라인의 `ProductName`. 없으면 지금까지대로 `ProductDescription` 에서 딴다 |
| 상세 시트 제목 (`Group.title`, C1) | 종목 키를 대문자로. **금칙 문자를 그대로 둔다** — `(메일/스펨_1식)` |
| 시트 이름 (`Group.sheet_name`) | 종목 키를 대문자로 하고 아래 정리를 거친다 |

본체 라인은 `CPUSIUvalue=1` 인 하드웨어 라인이다. 랙·PDU·콘솔처럼 본체 없이
부품만 있는 그룹에는 `ProductName` 이 없으므로 설명에서 딴다.

### 2.3 시트 이름 정리

Excel 이 시트 이름에 걸어 두는 제한을 여기서 먼저 지킨다. openpyxl 에 맡기면
31자를 넘긴 이름이 나온다.

| 규칙 | 처리 |
|---|---|
| 금칙 문자 `: \ / ? * [ ]` | 하이픈으로 바꾼다. `메일/스펨_1식` → `메일-스펨_1식` |
| 앞뒤 공백·작은따옴표 | 없앤다 |
| 31자 초과 | 자른다 |
| 빈 이름, 예약어 `History` | `SHEET` 로 바꾼다 |
| 이름이 겹칠 때 | ` (2)`, ` (3)` … 을 붙인다. 31자를 넘기지 않도록 앞을 줄인다 |

## 3. 본체 라인 LP 가 그 서버의 전체 금액이다

### 3.1 근거

Lenovo DCSC 가 같은 구성으로 내려 주는 요약표와 대조했다. 그룹 1000
(`백업서버_1식`)은 요약표에서 여섯 줄로 갈라진다.

| 부품 번호 | 설명 | 요약표 가격 |
|---|---|---|
| 7DGDCTO1WW | ThinkSystem SR650 V4 | 27,360,001.8 |
| 7S0FCTOBWW | Red Hat RHEL | 5,440,001 |
| 7S0XCTO8WW | XClarity Controller Prem-FOD | 840,001 |
| 5WS7C20241 | 3Yr Premier 24x7 4Hr Resp | 5,691,000 |
| 5PS7C20483 | 3Yr KYD Add-On | 841,000 |
| 5374CM1 | Configuration Instruction | 1 |

그런데 **XML 의 본체 라인 `UnitListPrice` 는 40,172,001.8** 이다. 위 여섯 줄의
합(40,172,004.8)에서 자리표 1 원 세 개를 뺀 값이며, 곧 **그 서버 한 대의 전체
LP** 다. XML 의 소프트웨어 라인은 실제 금액이 아니라 자리표 `1` 만 담는다.

즉 UNIX 모드로 읽으면 이렇게 된다.

```text
40,172,001.8  본체 (이미 SW·서비스를 포함한 값)
         + 1  Red Hat RHEL      (자리표)
         + 1  XClarity          (자리표)
         + 1  Configuration     (자리표)
   + 841,000  KYD               ← 두 번째 계상
 + 5,691,000  Premier 24x7      ← 두 번째 계상
------------
46,704,004.8  ← 서비스 6,532,000 원과 자리표 3 원이 더 붙었다
```

### 3.2 품목별 실금액은 요약표에 있다

본체 LP 를 그대로 쓰면 이중 계상은 막지만 S/W 구간이 0 이 되어, 무엇이 얼마인지
견적서에 남지 않는다. 그 내역이 **문서 안에** 있다.
`CFXML/SectionData/GroupData` 가 DCSC 화면의 요약표를 그대로 담고 있으며,
base64 로 적은 gzip XML 이다.

```xml
<Group_-Product>
  <id>KR__…2610</id>            <- 구성(서버 한 대) 식별자
  <code>7DGDCTO1WW</code>  <type>hardware</type>
  <unitPrice>7.58000014E7</unitPrice>              <- 하드웨어만의 금액
  <prices><SimplePrice><price>8.31720014E7</price></SimplePrice></prices>
</Group_-Product>                                   <- 이 값이 본체 라인 LP 다
<Group_-Product>
  <code>7S0XCTO8WW</code>  <type>hipo</type>        <- 소프트웨어
  <unitPrice>840001.0</unitPrice>                   <- 실금액 840,000 + 자리표 1
</Group_-Product>
<Group_-Product>
  <code>5WS7C20241</code>  <type>service</type>
  <unitPrice>5691000.0</unitPrice>                  <- XML 라인 값과 같다
</Group_-Product>
```

실파일 27 건 73 개 장비군을 검산해 확인한 것은 넷이다.

1. 하드웨어 항목의 `prices/SimplePrice/price` 가 **XML 본체 라인의
   UnitListPrice** 와 같다. 장비군과 구성은 이것으로 짝짓는다.
2. 다음 항등식이 성립한다.

       본체 LP = 하드웨어 + Σ소프트웨어 + Σ서비스 - (소프트웨어 항목 수)

   빼는 값은 소프트웨어마다 하나씩 붙은 자리표 1 원이다. 65 개 장비군이
   짝지어졌고 56 개는 원 단위까지 맞았다. 나머지 9 개는 1~5 원 차이였다
   (자리표 개수와 소수 넷째 자리 반올림). 짝짓기가 어긋난 것은 없었다.
   남은 8 개는 DCSC 쪽에 금액이 아예 없는 장비군이다.
3. 서비스 금액은 XML 라인에도 실금액으로 들어 있고, 요약표와 한 건도 다르지
   않았다. 요약표가 새로 알려 주는 것은 **소프트웨어 실금액** 뿐이다.
4. 한 장비군 안의 라인 수량은 모두 같다. 그래서 단가끼리 더하고 빼면 된다.

`GroupData` 는 eConfig 규격이 아니라 DCSC 가 제 상태를 담아 두는 자리다.
문서화된 적이 없고 구성기 판올림에 형태가 바뀔 수 있다. 그래서 **읽지 못하면
조용히 포기** 하고, 요소 이름이 아니라 자식 노드의 생김새로 항목을 고른다.

### 3.3 규칙

그룹에 **금액이 붙은 본체 라인** 이 있을 때만 손댄다.

- 요약표에서 이 장비군의 구성을 찾으면(본체 품번이 같고 `SimplePrice` 가 본체
  LP 와 10 원 안쪽이면) 하드웨어가 아닌 라인에 **요약표의 실금액** 을 적고,
  본체 라인은 **남는 값** 으로 잡는다. 자리표와 반올림이 남는 값에 모이므로
  장비군 합계는 본체 LP 와 한 푼도 어긋나지 않는다.
- 요약표가 없거나 구성을 찾지 못하면 지금까지대로 하드웨어가 아닌 라인
  (`ProductTypeCode` 가 `Hardware` 가 아닌 것 — `Software`, `Services`,
  `ServiceCTO` 등)의 단가를 **비운다**.
- 한 구성은 장비군 하나에만 쓴다. 같은 기종을 여러 대 담으면 구성도 그만큼
  들어 있다.
- 요약표에 없는 라인, 실금액이 0 인 라인(Configuration Instruction)은 칸을
  비운다. 같은 품번이 한 장비군에 두 번 나오면 앞선 라인이 금액을 가져간다.
- **라인은 지우지 않는다.** 무엇이 들어 있는지는 TOTAL 시트와 상세 시트에
  그대로 남는다.
- 본체 없이 부품만 있는 그룹(랙, PDU, 콘솔, 케이블)은 손대지 않는다. 저마다
  제 금액을 갖고 요약표에도 없다.
- 서브라인은 손대지 않는다. 레노버 문서의 서브라인 `MonetaryAmount` 는 모두
  `0` 이라 합계에 영향이 없다.

그 결과 견적서의 금액은 이렇게 맞는다.

| 칸 | 요약표를 읽었을 때 | 못 읽었을 때 |
|---|---|---|
| H/W 구간 합계 | (본체 LP - SW - 서비스) × 수량 | 본체 LP × 수량 |
| S/W 구간 합계 | (SW + 서비스) × 수량 | 0 (서식상 `-` 로 보인다) |
| 총합계 | 본체 LP × 수량 | 본체 LP × 수량 |

## 4. 화면과 배선

화면의 `변환 모드` 토글이 모드를 정하고, 그 값이 파이썬까지 그대로 간다.
판단(모르는 값 거절)은 언제나 파이썬이 한다.

```text
index.html  <input name="mode" value="unix|integrated">
  main.ts       currentMode()
    converter.ts    ConvertOptions.mode
      convert.worker.ts  WorkerRequest.mode
        engine.js          entry.convert(…, mode)
          entry.py           api.convert_response(…, mode=…)
            api.py             conversion_adapter.normalize_mode()
              conversion_adapter.py  xml_reader.parse_bytes(…, mode=…)
                xml_reader.py          dcsc_summary.parse
                                       integrated.group_key / fold_prices
```

서버 경로(`web/src/worker.py`, Workers Paid 전용)는 multipart 의 `mode` 필드를
`form.get_all("mode")` 로 읽는다. `get_all` 은 SDK 대응이 확인된 이름이다
([사고 0001](../incidents/0001-worker-rejected-everything.md)).

- 모드 필드가 없거나 비어 있으면 **UNIX** 다. 모드를 모르는 예전 클라이언트도
  지금까지와 같이 돈다.
- 모르는 값은 `INVALID_REQUEST`(400)로 거절한다.
- 모드는 견적 내용이 아니라 설정이므로 구조화 로그에 `mode` 로 남긴다
  (계획 §13).

## 5. 아직 하지 않은 것

- **데스크톱 앱에는 토글이 없다.** 코어는 `mode=` 를 받으므로 화면만 붙이면
  된다.
- 여러 XML 을 한 견적서로 합치지 않는다. 지금처럼 XML 하나에 `.xlsx` 하나다.
- 요약표에 금액이 없는 구성(구형 파일, 가격 미제공)은 갈라 적지 못한다. 본체
  LP 한 줄로만 센다.
