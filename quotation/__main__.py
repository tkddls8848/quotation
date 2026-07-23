r"""진입점. 인자가 없으면 GUI, 있으면 CLI 로 동작한다.

    QuotationTool.exe                       -> GUI
    QuotationTool.exe a.xml b.xml -o out\   -> 일괄 변환
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__, logging_setup
from .core import convert
from .core.pricing import DiscountError
from .core.xml_reader import QuotationXmlError


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="QuotationTool", description="eConfig XML 을 견적서로 변환합니다.")
    parser.add_argument("xml", nargs="+", type=Path, help="입력 XML 화일")
    parser.add_argument("-o", "--out-dir", type=Path,
                        help="저장 폴더 (기본: XML 과 같은 폴더)")
    parser.add_argument("-d", "--discount", default="",
                        help="할인율 %% (0~99, 소수점 1자리)")
    parser.add_argument("--no-maintenance", action="store_true",
                        help="유지정비료(H열)를 채우지 않습니다")
    parser.add_argument("-v", "--version", action="version",
                        version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    failed = 0
    for xml in args.xml:
        try:
            result = convert.convert(
                xml, out_dir=args.out_dir, discount=args.discount,
                include_maintenance=not args.no_maintenance)
            print(f"OK   {xml.name} -> {result.output}  "
                  f"(장비군 {result.group_count}개, {result.elapsed:.2f}초)")
        except (QuotationXmlError, DiscountError, OSError) as exc:
            print(f"실패 {xml.name}: {exc}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    logging_setup.setup(console=bool(argv))
    if argv:
        return _cli(argv)

    from .ui.main_window import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
