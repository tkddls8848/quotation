"""견적 날짜 (계획서 §2.2, §5.1).

Worker 는 UTC 로 돈다. 견적서의 날짜 칸은 한국 영업일 기준이어야 하므로
요청 처리 시작 시점에 Asia/Seoul 날짜를 한 번 정해 모든 시트에 같이 넘긴다.

`zoneinfo` 는 tzdata 패키지가 있어야 하고 Workers 번들을 키운다. 대한민국은
1988년 이후 서머타임이 없어 UTC+9 고정 오프셋으로 충분하다.
"""
from __future__ import annotations

import datetime as dt

KST = dt.timezone(dt.timedelta(hours=9), "KST")


def seoul_now(now: dt.datetime | None = None) -> dt.datetime:
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    return now.astimezone(KST)


def seoul_today(now: dt.datetime | None = None) -> dt.date:
    return seoul_now(now).date()
