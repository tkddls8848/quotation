"""견적 변환기 메인 화면."""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from quotation.core import convert, modes
from quotation.core.xml_reader import QuotationXmlError

from . import theme
from .. import config as config_mod
from .. import paths

TITLE = "견적서 작성기"
SUBTITLE = "IBM eServer and TotalStorage, Lenovo x86 (ThinkSystem) — 자동 구분"
XML_FILETYPES = [("XML 화일", "*.xml"), ("모든 화일", "*.*")]
#: 템플릿 열기 줄에 보여 줄 이름. `quotation.core.modes.LABELS` 는 진단용이라
#: 화면 문구는 여기서 따로 정한다.
TEMPLATE_ROW_LABELS = {modes.UNIX: "IBM", modes.INTEGRATED: "Lenovo x86"}


class MainWindow(ttk.Frame):
    def __init__(self, master: tk.Tk, prefill: str | None = None):
        theme.apply(master)
        super().__init__(master, padding=16)
        self.master = master
        self.cfg = config_mod.load()
        self._events: queue.Queue = queue.Queue()
        self._busy = False

        self.xml_path = tk.StringVar()
        self.open_result = tk.BooleanVar(value=self.cfg.open_result_when_done)
        self.status = tk.StringVar(value="변환할 XML 화일을 선택하십시오.")
        self.progress_pct = tk.StringVar(value="0%")
        # 어느 XML 을 고를지는 아직 모르므로(IBM/Lenovo 는 파싱 후에 갈린다),
        # 편집용 사본은 두 모드 다 미리 만들어 둔다.
        self.template_paths = {mode: paths.template_path(mode) for mode in modes.MODES}

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
        self.columnconfigure(0, weight=1)

        # --- 안내 --------------------------------------------------------
        ttk.Label(self, text=TITLE, style="Heading.TLabel").grid(
            row=0, column=0, sticky="w")
        ttk.Label(self, text=SUBTITLE, style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(2, 16))

        # --- 화일 선택 -----------------------------------------------------
        ttk.Label(self, text="XML 화일", style="FieldLabel.TLabel").grid(
            row=2, column=0, sticky="w")

        file_row = ttk.Frame(self)
        file_row.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        file_row.columnconfigure(0, weight=1)
        entry = ttk.Entry(file_row, textvariable=self.xml_path,
                           font=(theme.MONO_FONT, 9))
        entry.grid(row=0, column=0, sticky="ew", ipady=3)
        ttk.Button(file_row, text="찾아보기…", command=self._pick_xml).grid(
            row=0, column=1, padx=(6, 0))

        ttk.Label(self, text="견적서는 XML 과 같은 폴더에 저장됩니다.",
                  style="Hint.TLabel").grid(row=4, column=0, sticky="w",
                                            pady=(4, 14))

        # --- 옵션 -----------------------------------------------------------
        ttk.Checkbutton(self, text="완료 후 견적서 열기",
                        variable=self.open_result).grid(
            row=5, column=0, sticky="w", pady=(0, 16))

        # --- 템플릿 빠른 열기 -------------------------------------------------
        # 견적서 번호(NO : Trialinfo-YY-)와 머리말의 '담당 : ...' 은 템플릿에서
        # 직접 고친다. IBM 문서와 Lenovo x86 문서는 템플릿이 서로 달라서 두
        # 벌 다 바로 열 수 있게 해 둔다.
        ttk.Label(self, text="템플릿 열기 · 견적번호·담당자 수정",
                  style="FieldLabel.TLabel").grid(row=6, column=0, sticky="w",
                                                  pady=(0, 4))

        templates = ttk.Frame(self)
        templates.grid(row=7, column=0, sticky="ew", pady=(0, 14))
        templates.columnconfigure(0, weight=1)
        for i, mode in enumerate(modes.MODES):
            card = tk.Frame(templates, background=theme.SURFACE,
                            highlightbackground=theme.LINE,
                            highlightthickness=1)
            card.grid(row=i, column=0, sticky="ew", pady=(0 if i == 0 else 6, 0))
            card.columnconfigure(1, weight=1)
            ttk.Label(card, text=TEMPLATE_ROW_LABELS[mode], style="Chip.TLabel"
                      ).grid(row=0, column=0, padx=(10, 8), pady=8)
            ttk.Label(card, text=str(self.template_paths[mode]),
                      style="CardMuted.TLabel").grid(row=0, column=1, sticky="ew")
            ttk.Button(card, text="열기", style="Small.TButton",
                       command=lambda m=mode: self._open_template(m)
                       ).grid(row=0, column=2, padx=8, pady=6)

        # --- 진행률·상태 판독부 -----------------------------------------------
        readout = tk.Frame(self, background=theme.SURFACE,
                           highlightbackground=theme.LINE, highlightthickness=1)
        readout.grid(row=8, column=0, sticky="ew", pady=(0, 16))
        readout.columnconfigure(0, weight=1)

        readout_top = tk.Frame(readout, background=theme.SURFACE)
        readout_top.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        readout_top.columnconfigure(1, weight=1)

        self.status_dot = tk.Canvas(readout_top, width=8, height=8,
                                    background=theme.SURFACE, highlightthickness=0)
        self._dot_id = self.status_dot.create_oval(0, 0, 8, 8,
                                                    fill=theme.MUTED, outline="")
        self.status_dot.grid(row=0, column=0, padx=(0, 8))
        ttk.Label(readout_top, textvariable=self.status, style="CardText.TLabel"
                  ).grid(row=0, column=1, sticky="w")
        ttk.Label(readout_top, textvariable=self.progress_pct,
                  style="CardMuted.TLabel").grid(row=0, column=2, sticky="e")

        bar_wrap = tk.Frame(readout, background=theme.SURFACE)
        bar_wrap.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        bar_wrap.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(bar_wrap, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew")

        # --- 실행 -----------------------------------------------------------
        actions = ttk.Frame(self)
        actions.grid(row=9, column=0, sticky="ew")
        actions.columnconfigure(0, weight=1)
        ttk.Label(actions, text="Enter 로도 바로 변환합니다.", style="Hint.TLabel"
                  ).grid(row=0, column=0, sticky="w")
        buttons = ttk.Frame(actions)
        buttons.grid(row=0, column=1, sticky="e")
        self.convert_btn = ttk.Button(buttons, text="변환", style="Primary.TButton",
                                      command=self._start, default="active")
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
            self.progress["value"] = 0
            self.progress_pct.set("0%")
            self._set_state(theme.MUTED)

    def _open_template(self, mode: str):
        """템플릿을 기본 프로그램(Excel)으로 연다.

        견적서 번호와 머리말의 담당자 이름은 여기서 고친다.
        """
        _open(self.template_paths[mode])

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
        self._set_state(theme.ACCENT)
        threading.Thread(target=self._worker, args=(xml,), daemon=True).start()

    def _worker(self, xml: Path):
        try:
            # 템플릿은 EXE 옆의 사용자 편집본을 쓴다. 코어는 경로 정책을 모른다.
            # IBM 문서인지 Lenovo x86 문서인지는 코어가 파싱한 뒤에야 알므로,
            # 경로를 미리 고르지 않고 `mode -> 경로` 함수를 그대로 건넨다.
            result = convert.convert(
                xml, template=paths.template_path,
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
                    self.progress_pct.set(f"{event[1]:.0f}%")
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
        self.progress_pct.set("100%")
        self._set_state(theme.OK)
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
        self.progress_pct.set("0%")
        self._set_state(theme.DANGER)
        self.status.set("변환에 실패했습니다.")
        messagebox.showerror(TITLE, message)

    def _set_busy(self, busy: bool):
        self._busy = busy
        self.convert_btn.state(["disabled"] if busy else ["!disabled"])
        self.master.config(cursor="watch" if busy else "")

    def _set_state(self, color: str):
        """대기/진행/완료/실패를 판독부의 작은 점 색으로도 알려 준다."""
        self.status_dot.itemconfig(self._dot_id, fill=color)


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
    root.minsize(640, 460)
    root.call("tk", "scaling", 1.3)
    MainWindow(root, prefill)
    root.mainloop()
    return 0
