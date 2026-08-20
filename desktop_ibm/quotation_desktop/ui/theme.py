"""데스크톱 화면의 어두운 색."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

BG = "#12141a"        # 창 바탕
SURFACE = "#1b1f27"   # 입력칸·눌린 곳
TEXT = "#e7eaf0"
MUTED = "#99a1b3"     # 설명글
LINE = "#2f3542"      # 테두리
ACCENT = "#7aa2f7"    # 진행 막대·선택 표시
ACCENT_TEXT = "#10131a"


def apply(root: tk.Misc) -> None:
    """창과 ttk 위젯을 어둡게 칠한다.

    윈도우 기본 테마(vista)는 색을 바꿔도 대부분 무시하므로 `clam` 으로
    바꾼 뒤 칠한다. 알림창과 화일 선택창은 운영체제가 그리므로 그대로 둔다.
    """
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    root.tk_setPalette(background=BG, foreground=TEXT,
                       activeBackground=LINE, activeForeground=TEXT)

    style.configure(".", background=BG, foreground=TEXT,
                    fieldbackground=SURFACE, bordercolor=LINE,
                    lightcolor=BG, darkcolor=BG, troughcolor=SURFACE,
                    focuscolor=ACCENT)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)

    style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT,
                    insertcolor=TEXT, bordercolor=LINE, lightcolor=LINE,
                    darkcolor=LINE, selectbackground=ACCENT,
                    selectforeground=ACCENT_TEXT, padding=4)
    style.map("TEntry",
              bordercolor=[("focus", ACCENT)],
              lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)],
              fieldbackground=[("disabled", BG)],
              foreground=[("disabled", MUTED)])

    style.configure("TButton", background=SURFACE, foreground=TEXT,
                    bordercolor=LINE, lightcolor=SURFACE, darkcolor=SURFACE,
                    padding=(10, 4))
    style.map("TButton",
              background=[("disabled", BG), ("pressed", LINE),
                          ("active", LINE)],
              foreground=[("disabled", MUTED)],
              bordercolor=[("active", ACCENT), ("focus", ACCENT)])

    style.configure("TCheckbutton", background=BG, foreground=TEXT,
                    indicatorcolor=SURFACE, indicatorbackground=SURFACE)
    style.map("TCheckbutton",
              background=[("active", BG)],
              indicatorcolor=[("selected", ACCENT), ("pressed", LINE)],
              indicatorbackground=[("selected", ACCENT), ("active", LINE)])

    style.configure("TProgressbar", background=ACCENT, troughcolor=SURFACE,
                    bordercolor=LINE, lightcolor=ACCENT, darkcolor=ACCENT)
