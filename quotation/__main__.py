"""진입점. 인자가 없으면 GUI, 있으면 CLI 로 동작한다.

    QuotationTool.exe                  -> GUI
    QuotationTool-cli.exe a.xml b.xml  -> 일괄 변환

견적서는 언제나 XML 과 같은 폴더에 저장된다.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__, logging_setup
from .core import convert
from .core.xml_reader import QuotationXmlError


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="QuotationTool", description="eConfig XML 을 견적서로 변환합니다.")
    parser.add_argument("xml", nargs="+", type=Path, help="입력 XML 화일")
    parser.add_argument("-t", "--template", type=Path,
                        help="견적서 템플릿 (기본: EXE 옆의 견적서_template.xlsx)")
    parser.add_argument("-v", "--version", action="version",
                        version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    failed = 0
    for xml in args.xml:
        try:
            result = convert.convert(xml, template=args.template)
            print(f"OK   {xml.name} -> {result.output}  "
                  f"(장비군 {result.group_count}개, {result.elapsed:.2f}초)")
        except (QuotationXmlError, OSError) as exc:
            print(f"실패 {xml.name}: {exc}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


def has_console() -> bool:
    """콘솔이 붙어 있는가. GUI 전용 빌드(QuotationTool.exe)는 False 다."""
    return sys.stdout is not None


def _prepare_console() -> None:
    """Python 기본 UTF-8 출력이 cp949 콘솔에서 깨지지 않도록 맞춘다."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        encoding = f"cp{ctypes.windll.kernel32.GetConsoleOutputCP()}"
        sys.stdout.reconfigure(encoding=encoding, errors="replace")
        sys.stderr.reconfigure(encoding=encoding, errors="replace")
    except (AttributeError, ImportError, OSError, ValueError):
        pass


def main(argv: list[str] | None = None) -> int:
    """인자가 있고 콘솔도 있으면 CLI, 아니면 GUI.

    GUI 전용 빌드(QuotationTool.exe)에 XML 을 끌어다 놓으면 콘솔이 없으므로
    그 화일을 미리 채운 상태로 창을 띄운다. 일괄 변환은 QuotationTool-cli.exe 다.
    windowed EXE 로 CLI 를 흉내내면 파이프에 물렸을 때 호출 측이 멈춘다.
    """
    argv = sys.argv[1:] if argv is None else argv
    cli_mode = bool(argv) and has_console()

    if cli_mode:
        _prepare_console()
    logging_setup.setup(console=cli_mode)

    if cli_mode:
        return _cli(argv)

    from .ui.main_window import run
    prefill = next((a for a in argv if not a.startswith("-")), None)
    return run(prefill)


if __name__ == "__main__":
    sys.exit(main())
