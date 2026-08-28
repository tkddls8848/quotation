"""데스크톱 화면의 어두운 색."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

BG = "#12141a"        # 창 바탕
SURFACE = "#1b1f27"   # 입력칸·눌린 곳·카드
SURFACE_2 = "#242b38"  # 카드 위에 얹는 진행 막대 홈처럼, 카드 바탕보다 한 단 밝게
TEXT = "#e7eaf0"
MUTED = "#99a1b3"     # 설명글
MUTED_2 = "#6b7284"   # 더 옅은 설명글(도움말·힌트)
LINE = "#2f3542"      # 테두리
ACCENT = "#7aa2f7"    # 진행 막대·선택 표시
ACCENT_HOVER = "#8fb1f9"
ACCENT_SOFT = "#242c42"  # 강조색을 옅게 섞은 칩 바탕
ACCENT_TEXT = "#10131a"
OK = "#6fcf97"         # 완료
DANGER = "#ff8f85"     # 실패

MONO_FONT = "Consolas"  # 화일 경로·판(mode) 이름처럼 값을 그대로 보여 줄 때


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
    style.configure("Card.TFrame", background=SURFACE)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED)
    style.configure("Hint.TLabel", background=BG, foreground=MUTED_2,
                    font=("Segoe UI", 8))
    style.configure("Heading.TLabel", background=BG, foreground=TEXT,
                    font=("Segoe UI", 14, "bold"))
    style.configure("FieldLabel.TLabel", background=BG, foreground=MUTED,
                    font=("Segoe UI", 8, "bold"))
    style.configure("Mono.TLabel", background=SURFACE, foreground=MUTED,
                    font=(MONO_FONT, 9))
    style.configure("Chip.TLabel", background=ACCENT_SOFT, foreground=ACCENT,
                    font=("Segoe UI", 8, "bold"), padding=(6, 2))
    # 카드(SURFACE 바탕) 위에 얹는 글자는 배경을 따로 맞춰 줘야 한다 — ttk 라벨은
    # 부모의 배경을 이어받지 않고 스타일에 적힌 배경을 그대로 칠한다.
    style.configure("CardText.TLabel", background=SURFACE, foreground=TEXT)
    style.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED,
                    font=(MONO_FONT, 9))

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

    # 이 화면에서 가장 중요한 동작(변환)만 강조색으로 채운다. 나머지 버튼은
    # 위 TButton(테두리만 있는 "고스트" 모양)을 그대로 쓴다.
    style.configure("Primary.TButton", background=ACCENT, foreground=ACCENT_TEXT,
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
                    padding=(14, 6), font=("Segoe UI", 9, "bold"))
    style.map("Primary.TButton",
              background=[("disabled", LINE), ("pressed", ACCENT),
                          ("active", ACCENT_HOVER)],
              bordercolor=[("disabled", LINE), ("active", ACCENT_HOVER)],
              foreground=[("disabled", MUTED)])

    style.configure("Small.TButton", padding=(8, 2), font=("Segoe UI", 8))

    style.configure("TCheckbutton", background=BG, foreground=TEXT,
                    indicatorcolor=SURFACE, indicatorbackground=SURFACE)
    style.map("TCheckbutton",
              background=[("active", BG)],
              indicatorcolor=[("selected", ACCENT), ("pressed", LINE)],
              indicatorbackground=[("selected", ACCENT), ("active", LINE)])

    style.configure("TProgressbar", background=ACCENT, troughcolor=SURFACE_2,
                    bordercolor=LINE, lightcolor=ACCENT, darkcolor=ACCENT)
