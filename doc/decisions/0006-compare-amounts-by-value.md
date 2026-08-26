# 결정 0006 — 금액 동등성은 `Decimal` 표기가 아니라 값으로 판정한다

- 날짜: 2026-08-26
- 상태: **적용됨**
- 보완하는 계획: [Rust→WASM 코어 전환 착수안](../plan/rust-wasm-core-plan.md) §Phase 1
- 잇는 결정: [결정 0005](0005-accept-meaningful-xlsx-parity.md)

## 결론

파이썬 코어와 Rust 이식본의 금액을 대조할 때, `str(Decimal)` 이 아니라
**지수 없는 자릿수 표기(`format(x, "f")`)** 로 비교한다. 소수 자릿수는 그대로
보존해야 하지만 지수 형태는 계약이 아니다.

## 왜 이 문제가 생겼는가

레노버 DCSC 구성 파일은 큰 금액을 지수 표기로 적는다. 지어낸 사례가 아니라
저장소의 골든 fixture 에 그대로 들어 있다.

```text
tests/fixtures/public/integrated_quote.xml
tests/fixtures/public/integrated_summary_quote.xml
    <MonetaryAmount>4.0172E7</MonetaryAmount>
    <MonetaryAmount>4.2812E7</MonetaryAmount>
```

파이썬 `Decimal("4.0172E7")` 은 이 지수 형태를 그대로 들고 다니며
`str()` 도 `4.0172E+7` 로 돌려준다. 그러나 **셀에 실제로 적히는 값은 그것이
아니다.** openpyxl 은 수치 셀을 `%.16g` 로 직렬화하므로 시트 XML 에는

```xml
<c r="A1" t="n"><v>40172000</v></c>
```

가 들어간다. 즉 지수 형태는 견적서에 도달하지 않는다.

`Decimal` 의 소수 자릿수도 같은 자리에서 사라진다 — `Decimal("88971.50")`
이든 `Decimal("88971.5")` 든 셀에는 `88971.5` 로 적힌다. 그래도 자릿수는
계속 보존한다. 값을 만드는 도중에 반올림이 끼어들지 않는다는 성질이고,
파이썬 구현이 지키는 것을 이식본이 버릴 이유가 없다.

## 무엇을 바꿨나

- Rust `quotation-core::money` 는 지수 표기를 받는다. 값이 같은 자릿수
  표기(`40172000`)로 들고 있고, 지수 형태는 남기지 않는다.
- 대조 하네스 `tools/rust_parity_pure_rules.py` 는 양쪽 금액을
  `format(x, "f")` 로 맞춰 비교한다.
- 유효자릿수 28 자리를 넘겨 Rust 가 담지 못하는 값은 **오류로 거절한다.**
  조용히 반올림해 다른 숫자를 만드는 것보다 멈추는 편이 낫다. eConfig 금액이
  그 자리에 닿은 적은 없다.

## 이 판정이 무엇을 놓치는가

지수 형태 차이를 값 비교로 덮으므로, 만약 앞으로 금액을 **문자열 그대로**
셀에 넣는 경로가 생기면 이 판정은 그 차이를 잡지 못한다. 지금은 그런 경로가
없다 (`writer/ibm_writer.py` 는 수치나 수식으로만 넣는다). 생기면 이 결정을
다시 본다.
