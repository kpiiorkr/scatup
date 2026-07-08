"""Step 2 · 네이버 수집 (rule §5 Step 2, §3).

블로그·카페·뉴스 대상 관련 자료를 수집한다.
"""
from __future__ import annotations

from ..models.schemas import CollectedItem


def collect(keywords: list[str]) -> list[CollectedItem]:
    """TODO(담당): 네이버 검색 API(blog/cafe/news) 연동.

    입력 검증 규칙(§4-2): API 응답 오류 시 해당 소스만 skip.
    """
    items: list[CollectedItem] = []
    # TODO: 각 채널별 검색 → CollectedItem 매핑
    return items
