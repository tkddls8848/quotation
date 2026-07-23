"""메인 화면 — 원본 Form1 대체.

원본과 달라진 점
  - Excel 을 띄우지 않으므로 "Excel을 모두 종료하십시오" 상황이 없다
  - 변환을 작업 스레드에서 돌려 UI 가 멈추지 않는다
  - 실패해도 잔류 프로세스나 잠긴 파일이 남지 않는다
  - 삼성 SDS 양식 선택(optSDS)은 제거되었다
"""
from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .. import config as config_mod
from ..core import convert
from ..core.pricing import DiscountError
from ..core.xml_reader import QuotationXmlError

log = logging.getLogger(__name__)

TITLE = "견적서 작성기"
SUBTITLE = "IBM eServer and TotalStorage — eConfig Export"
XML_FILETYPES = [("XML 화일", "*.xml"), ("모든 화일", "*.*")]


class MainWindow(ttk.Frame):
    def __init__(self, master: tk.Tk, prefill: str | None = None):
        super().__init__(master, padding=12)
        self.master = master
        self.cfg = config_mod.load()
        self._events: queue.Queue = queue.Queue()
        self._busy = False

        self.xml_path = tk.StringVar()
        self.out_dir = tk.StringVar(value=self.cfg.last_output_dir)
        self.discount = tk.StringVar(value=self.cfg.discount)
        self.include_ma = tk.BooleanVar(value=self.cfg.include_maintenance)
        self.open_folder = tk.BooleanVar(value=self.cfg.open_folder_when_done)
        self.status = tk.StringVar(value="변환할 XML 화일을 선택하십시오.")

        self._build()
        self.grid(sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.after(100, self._drain_events)

        # EXE 에 XML 을 끌어다 놓은 경우
        if prefill and Path(prefill).is_file():
            self.xml_path.set(str(Path(prefill).resolve()))
            self.status.set("<변환> 버튼을 누르면 견적서 변환작업을 시작합니다.")

    # --- 화면 구성 -----------------------------------------------------------

    def _build(self):
        self.columnconfigure(1, weight=1)
        row = 0

        header = ttk.Label(self, text=SUBTITLE, foreground="#555")
        header.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 10))
        row += 1

        ttk.Label(self, text="XML 화일").grid(row=row, column=0, sticky="w")
        entry = ttk.Entry(self, textvariable=self.xml_path)
        entry.grid(row=row, column=1, sticky="ew", padx=6)
        ttk.Button(self, text="찾아보기…", command=self._pick_xml).grid(
            row=row, column=2)
        row += 1

        ttk.Label(self, text="저장 폴더").grid(row=row, column=0, sticky="w",
                                            pady=(6, 0))
        ttk.Entry(self, textvariable=self.out_dir).grid(
            row=row, column=1, sticky="ew", padx=6, pady=(6, 0))
        ttk.Button(self, text="폴더 선택…", command=self._pick_out_dir).grid(
            row=row, column=2, pady=(6, 0))
        row += 1

        ttk.Label(self, text="(비워 두면 XML 과 같은 폴더에 저장합니다)",
                  foreground="#777").grid(row=row, column=1, sticky="w",
                                          padx=6, pady=(2, 8))
        row += 1

        options = ttk.Frame(self)
        options.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 10))
        ttk.Label(options, text="할인율").pack(side="left")
        ttk.Entry(options, textvariable=self.discount, width=7).pack(
            side="left", padx=(6, 2))
        ttk.Label(options, text="%  (0~99, 소수점 1자리)",
                  foreground="#777").pack(side="left", padx=(0, 16))
        ttk.Checkbutton(options, text="유지정비료 포함",
                        variable=self.include_ma).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(options, text="완료 후 폴더 열기",
                        variable=self.open_folder).pack(side="left")
        row += 1

        self.progress = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.progress.grid(row=row, column=0, columnspan=3, sticky="ew")
        row += 1

        ttk.Label(self, textvariable=self.status).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(6, 10))
        row += 1

        buttons = ttk.Frame(self)
        buttons.grid(row=row, column=0, columnspan=3, sticky="e")
        self.convert_btn = ttk.Button(buttons, text="변환", command=self._start,
                                      default="active")
        self.convert_btn.pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="종료", command=self.master.destroy).pack(
            side="left")

        self.master.bind("<Return>", lambda _e: self._start())
        entry.focus_set()

    # --- 입력 ----------------------------------------------------------------

    def _pick_xml(self):
        initial = self.cfg.last_input_dir or str(Path.home())
        chosen = filedialog.askopenfilename(
            title="XML화일 선택", filetypes=XML_FILETYPES,
            initialdir=initial if Path(initial).is_dir() else None)
        if chosen:
            self.xml_path.set(chosen)
            self.status.set("<변환> 버튼을 누르면 견적서 변환작업을 시작합니다.")

    def _pick_out_dir(self):
        initial = self.out_dir.get() or self.cfg.last_output_dir
        chosen = filedialog.askdirectory(
            title="저장 폴더 선택",
            initialdir=initial if initial and Path(initial).is_dir() else None)
        if chosen:
            self.out_dir.set(chosen)

    # --- 변환 ----------------------------------------------------------------

    def _start(self):
        if self._busy:
            return
        raw = self.xml_path.get().strip()
        if not raw:
            messagebox.showinfo(TITLE, "작업할 화일을 선택하세요.")
            return
        xml = Path(raw)
        if not xml.is_file():
            messagebox.showerror(TITLE, f"화일을 찾을 수 없습니다.\n{xml}")
            return

        out_dir = self.out_dir.get().strip() or None
        target = convert.output_path_for(xml, Path(out_dir) if out_dir else None)
        if target.exists() and not messagebox.askyesno(
                TITLE, f"이미 있는 화일을 덮어씁니다.\n\n{target.name}\n\n계속할까요?"):
            return

        self._set_busy(True)
        threading.Thread(target=self._worker,
                         args=(xml, out_dir, self.discount.get(),
                               self.include_ma.get()),
                         daemon=True).start()

    def _worker(self, xml: Path, out_dir, discount: str, include_ma: bool):
        try:
            result = convert.convert(
                xml, out_dir=out_dir, discount=discount,
                include_maintenance=include_ma,
                progress=lambda p, m: self._events.put(("progress", p, m)))
            self._events.put(("done", result))
        except (QuotationXmlError, DiscountError) as exc:
            self._events.put(("error", str(exc)))
        except PermissionError:
            self._events.put((
                "error",
                "저장할 화일이 다른 프로그램에서 열려 있습니다.\n"
                "해당 견적서를 닫고 다시 시도하십시오.",
            ))
        except OSError as exc:
            self._events.put(("error", f"화일을 저장하지 못했습니다.\n{exc}"))
        except Exception as exc:  # noqa: BLE001 - 마지막 방어선
            log.exception("변환 중 예상치 못한 오류")
            self._events.put(("error", f"변환 중 오류가 발생했습니다.\n{exc}"))

    def _drain_events(self):
        try:
            while True:
                event = self._events.get_nowait()
                kind = event[0]
                if kind == "progress":
                    self.progress["value"] = event[1]
                    self.status.set(event[2])
                elif kind == "done":
                    self._on_done(event[1])
                elif kind == "error":
                    self._on_error(event[1])
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _on_done(self, result: convert.Result):
        self._set_busy(False)
        self.progress["value"] = 100
        self.status.set(
            f"견적서작성을 완료하였습니다.  장비군 {result.group_count}개 · "
            f"{result.elapsed:.1f}초")

        self.cfg.remember(Path(self.xml_path.get()), result.output)
        self.cfg.discount = self.discount.get().strip()
        self.cfg.include_maintenance = self.include_ma.get()
        self.cfg.open_folder_when_done = self.open_folder.get()
        config_mod.save(self.cfg)

        if self.open_folder.get():
            _reveal(result.output)
        else:
            messagebox.showinfo(TITLE, f"견적서를 만들었습니다.\n\n{result.output}")

    def _on_error(self, message: str):
        self._set_busy(False)
        self.progress["value"] = 0
        self.status.set("변환에 실패했습니다.")
        messagebox.showerror(TITLE, message)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.convert_btn.state(["disabled"] if busy else ["!disabled"])
        self.master.config(cursor="watch" if busy else "")


def _reveal(path: Path):
    """탐색기에서 결과 파일을 선택된 상태로 연다."""
    try:
        if sys.platform == "win32":
            subprocess.run(["explorer", "/select,", str(path)], check=False)
        else:
            os.startfile(path.parent)  # noqa: S606
    except OSError as exc:
        log.warning("결과 폴더를 열지 못했습니다: %s", exc)


def run(prefill: str | None = None) -> int:
    root = tk.Tk()
    root.title(TITLE)
    root.minsize(620, 300)
    try:
        root.call("tk", "scaling", 1.3)
    except tk.TclError:
        pass
    MainWindow(root, prefill)
    root.mainloop()
    return 0
