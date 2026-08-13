"""애플리케이션 자체 제한 (계획서 §5.3).

Cloudflare 계정 한도보다 작게 잡는다. 실제 샘플 분포를 재고 나면 줄인다.
"""
from __future__ import annotations

MiB = 1024 * 1024

#: 업로드 XML 한 개의 최대 크기
MAX_UPLOAD_BYTES = 10 * MiB

#: 한 요청에 담을 수 있는 파일 수. 다중 변환은 후속 기능이다.
MAX_FILE_COUNT = 1

#: 파싱 전 싸게 걸러 낼 ProductLineItem 등장 횟수 상한.
#: DOM 을 만들기 전에 비정상 문서를 떨어뜨려 메모리 폭주를 막는다.
MAX_LINE_ITEMS = 5_000

#: 장비군(=상세 시트) 수. Excel 시트 폭증을 막는다.
MAX_GROUPS = 200

#: 생성 결과 크기
MAX_OUTPUT_BYTES = 20 * MiB

#: 받아들일 확장자. 확장자만 믿지 않고 내용도 파싱해서 확인한다.
ALLOWED_SUFFIXES = (".xml",)


def public_config() -> dict:
    """클라이언트에 알려 줄 공개 설정 (`GET /api/v1/config`)."""
    return {
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "max_file_count": MAX_FILE_COUNT,
        "allowed_suffixes": list(ALLOWED_SUFFIXES),
        "output_suffix": ".xlsx",
    }
