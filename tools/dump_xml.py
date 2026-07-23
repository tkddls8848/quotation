"""eConfig XML 구조/데이터 덤프. Phase 0 분석용."""
import sys
from collections import Counter
from lxml import etree

X = {
    "line": "./ProductLineNumber",
    "txn": "./TransactionType",
    "grp": "./ProprietaryGroupIdentifier",
    "qty": "./Quantity",
    "desc": "./ProductIdentification/PartnerProductIdentification/ProductDescription",
    "type": "./ProductIdentification/PartnerProductIdentification/ProductTypeCode",
    "pid": "./ProductIdentification/PartnerProductIdentification/ProprietaryProductIdentifier",
    "cur": "./UnitListPrice/FinancialAmount/GlobalCurrencyCode",
    "amt": "./UnitListPrice/FinancialAmount/MonetaryAmount",
    "term": "./UnitListPrice/PriceTerm",
    "mcur": "./MaintenanceUnitListPrice/FinancialAmount/GlobalCurrencyCode",
    "mamt": "./MaintenanceUnitListPrice/FinancialAmount/MonetaryAmount",
    "mterm": "./MaintenanceUnitListPrice/PriceTerm",
}


def g(el, path):
    n = el.find(path)
    return (n.text or "").strip() if n is not None else None


def main(path):
    p = etree.XMLParser(load_dtd=False, resolve_entities=False, recover=True)
    tree = etree.parse(path, p)
    root = tree.getroot()
    print(f"=== {path}")
    print(f"root=<{root.tag}>")
    for tag in ("thisDocumentGenerationDateTime/DateTimeStamp",
                "thisDocumentIdentifier/ProprietaryDocumentIdentifier"):
        print(f"  {tag} = {g(root, './' + tag)}")

    cf = root.find("./CFData")
    print(f"CFData found: {cf is not None}")

    for pi in cf.findall("./ProprietaryInformation"):
        print(f"  PropInfo: {g(pi, './Name')} = {g(pi, './Value')}")
    psi = cf.find("./ProprietaryShippingInformation")
    if psi is not None:
        print(f"  Shipping: {g(psi,'./Name')} "
              f"{g(psi,'./FinancialAmount/GlobalCurrencyCode')} "
              f"{g(psi,'./FinancialAmount/MonetaryAmount')}")

    items = cf.findall(".//ProductLineItem")
    print(f"\nProductLineItem count (//): {len(items)}")
    print(f"ProductLineItem count (direct child): {len(cf.findall('./ProductLineItem'))}")

    txn = Counter(); typ = Counter(); grp = Counter(); term = Counter(); cur = Counter()
    nsub = 0
    for it in items:
        txn[g(it, X['txn'])] += 1
        typ[g(it, X['type'])] += 1
        grp[g(it, X['grp'])] += 1
        term[g(it, X['term'])] += 1
        cur[g(it, X['cur'])] += 1
        nsub += len(it.findall(".//ProductSubLineItem"))

    for name, c in (("TransactionType", txn), ("ProductTypeCode", typ),
                    ("ProprietaryGroupIdentifier", grp), ("PriceTerm", term),
                    ("GlobalCurrencyCode", cur)):
        print(f"\n{name}: {dict(c)}")
    print(f"\nProductSubLineItem total: {nsub}")

    print("\n--- ALL LINE ITEMS ---")
    hdr = ("line", "txn", "grp", "type", "pid", "qty", "cur", "amt", "term", "mamt", "mterm")
    print(" | ".join(f"{h}" for h in hdr) + " | desc | #sub")
    for it in items:
        row = [str(g(it, X[h]) or "") for h in hdr]
        d = g(it, X['desc']) or ""
        subs = it.findall("./ProductSubLineItem")
        print(" | ".join(row) + f" | {d} | {len(subs)}")
        for s in subs:
            print(f"      SUB: ln={g(s,'./LineNumber')} txn={g(s,'./TransactionType')} "
                  f"qty={g(s,'./Quantity')} "
                  f"pid={g(s,'./ProductIdentification/PartnerProductIdentification/ProprietaryProductIdentifier')} "
                  f"amt={g(s,'./UnitListPrice/FinancialAmount/MonetaryAmount')} "
                  f"mamt={g(s,'./MaintenanceUnitListPrice/FinancialAmount/MonetaryAmount')} "
                  f"desc={g(s,'./ProductIdentification/PartnerProductIdentification/ProductDescription')}")


if __name__ == "__main__":
    for a in sys.argv[1:]:
        main(a)
        print("\n" + "=" * 100 + "\n")
