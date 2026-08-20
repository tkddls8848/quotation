"""견적 변환기 메인 화면."""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from quotation.core import convert
from quotation.core.xml_reader import QuotationXmlError

from . import theme
from .. import config as config_mod
from .. import paths

TITLE = "견적서 작성기"
SUBTITLE = "IBM eServer and TotalStorage — eConfig Export"
XML_FILETYPES = [("XML 화일", "*.xml"), ("모든 화일", "*.*")]


class MainWindow(ttk.Frame):
    def __init__(self, master: tk.Tk, prefill: str | None = None):
        theme.apply(master)
        super().__init__(master, padding=12)
        self.master = master
        self.cfg = config_mod.load()
        self._events: queue.Queue = queue.Queue()
        self._busy = False

        self.xml_path = tk.StringVar()
        self.open_result = tk.BooleanVar(value=self.cfg.open_result_when_done)
        self.status = tk.StringVar(value="변환할 XML 화일을 선택하십시오.")
        self.template_label = tk.StringVar(value=str(paths.template_path()))

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

        header = ttk.Label(self, text=SUBTITLE, style="Muted.TLabel")
        header.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 10))
        row += 1

        ttk.Label(self, text="XML 화일").grid(row=row, column=0, sticky="w")
        entry = ttk.Entry(self, textvariable=self.xml_path)
        entry.grid(row=row, column=1, sticky="ew", padx=6)
        ttk.Button(self, text="찾아보기…", command=self._pick_xml).grid(
            row=row, column=2)
        row += 1

        ttk.Label(self, text="견적서는 XML 과 같은 폴더에 저장됩니다.",
                  style="Muted.TLabel").grid(row=row, column=1, sticky="w",
                                             padx=6, pady=(4, 8))
        row += 1

        options = ttk.Frame(self)
        options.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(4, 6))
        ttk.Checkbutton(options, text="완료 후 견적서 열기",
                        variable=self.open_result).pack(side="left")
        row += 1

        # 견적서 번호(NO : Trialinfo-YY-)와 머리말의 '담당 : ...' 은 템플릿에서
        # 직접 고친다. 그래서 템플릿을 바로 열 수 있게 해 둔다.
        tmpl = ttk.Frame(self)
        tmpl.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        ttk.Label(tmpl, text="템플릿", style="Muted.TLabel").pack(side="left")
        ttk.Label(tmpl, textvariable=self.template_label,
                  style="Muted.TLabel").pack(side="left", padx=(6, 10))
        ttk.Button(tmpl, text="템플릿 열기(견적번호·담당자 수정)",
                   command=self._open_template).pack(side="left")
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
        chosen = filedialog.askopenfilename(
            title="XML화일 선택", filetypes=XML_FILETYPES,
            initialdir=self.cfg.last_input_dir or str(Path.home()))
        if chosen:
            self.xml_path.set(chosen)
            self.status.set("<변환> 버튼을 누르면 견적서 변환작업을 시작합니다.")

    def _open_template(self):
        """템플릿을 기본 프로그램(Excel)으로 연다.

        견적서 번호와 머리말의 담당자 이름은 여기서 고친다.
        """
        _open(paths.template_path())

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

        target = convert.output_path_for(xml)
        if target.exists() and not messagebox.askyesno(
                TITLE, f"이미 있는 화일을 덮어씁니다.\n\n{target.name}\n\n계속할까요?"):
            return

        self._set_busy(True)
        threading.Thread(target=self._worker, args=(xml,), daemon=True).start()

    def _worker(self, xml: Path):
        try:
            # 템플릿은 EXE 옆의 사용자 편집본을 쓴다. 코어는 경로 정책을 모른다.
            result = convert.convert(
                xml, template=paths.template_path(),
                progress=lambda p, m: self._events.put(("progress", p, m)))
            self._events.put(("done", result))
        except QuotationXmlError as exc:
            self._events.put(("error", str(exc)))
        except PermissionError:
            self._events.put((
                "error",
                "저장할 화일이 다른 프로그램에서 열려 있습니다.\n"
                "해당 견적서를 닫고 다시 시도하십시오.",
            ))
        except OSError as exc:
            self._events.put(("error", f"화일을 저장하지 못했습니다.\n{exc}"))

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

        self.cfg.remember(Path(self.xml_path.get()))
        self.cfg.open_result_when_done = self.open_result.get()
        config_mod.save(self.cfg)

        # 알림창은 띄우지 않는다. 만든 견적서를 바로 연다.
        if self.open_result.get():
            _open(result.output)

    def _on_error(self, message: str):
        self._set_busy(False)
        self.progress["value"] = 0
        self.status.set("변환에 실패했습니다.")
        messagebox.showerror(TITLE, message)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.convert_btn.state(["disabled"] if busy else ["!disabled"])
        self.master.config(cursor="watch" if busy else "")


def _open(path: Path):
    """만든 견적서를 기본 프로그램(Excel)으로 연다."""
    try:
        os.startfile(path)  # noqa: S606
    except OSError as exc:
        messagebox.showerror(TITLE, f"화일을 열지 못했습니다.\n{exc}")


def run(prefill: str | None = None) -> int:
    root = tk.Tk()
    root.title(TITLE)
    root.configure(background=theme.BG)
    root.minsize(620, 300)
    root.call("tk", "scaling", 1.3)
    MainWindow(root, prefill)
    root.mainloop()
    return 0
