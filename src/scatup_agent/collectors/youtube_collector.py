"""Step 3 · 유튜브 수집 (rule §5 Step 3, §4-2, §8).

쿼터 절약 규칙을 반드시 지킨다:
  ① search.list 는 키워드당 1회만 호출
  ② videos.list 로 좋아요·조회수 일괄 조회
  ③ commentThreads.list 로 상위 댓글·댓글별 좋아요 수집
  ④ 댓글 비활성 영상은 통계(조회수·좋아요)만 반영
쿼터 80% 초과 시 검색 횟수를 자동 축소한다.
"""
from __future__ import annotations

from ..models.schemas import CollectedItem
from config.settings import settings


def collect(keywords: list[str]) -> list[CollectedItem]:
    """TODO(담당): YouTube Data API 연동."""
    items: list[CollectedItem] = []
    for _kw in keywords:
        if _quota_over_warn():
            # TODO: 검색 횟수 자동 축소 (rule §8: 다음 주기로 이월)
            break
        # ① search.list (키워드당 settings.youtube_search_per_keyword 회)
        # ② videos.list 일괄 통계
        # ③ commentThreads.list 상위 댓글
        # ④ 댓글 비활성 → 통계만
    return items


def _quota_over_warn() -> bool:
    """TODO(담당): 실제 쿼터 사용량 조회 후 80% 초과 여부 반환."""
    return False  # placeholder
