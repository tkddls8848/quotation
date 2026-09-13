"""데스크톱(로컬) 견적서 작성기.

변환 로직은 공용 코어 패키지 ``quotation.core`` 에 있다. 이 패키지에는
Windows 데스크톱에서만 쓰는 것들 — Tkinter 화면, 사용자 설정, 파일 경로,
PyInstaller 진입점 — 만 둔다. 웹(Worker)은 이 패키지를 import 하지 않는다.
"""

__version__ = "3.1.0"
