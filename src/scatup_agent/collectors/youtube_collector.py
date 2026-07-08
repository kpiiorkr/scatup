"""Step 3 · 유튜브 수집 (rule §5 Step 3, §4-2, §8).

쿼터 절약 규칙을 반드시 지킨다:
  ① search.list 는 키워드당 1회만 호출
  ② videos.list 로 좋아요·조회수 일괄 조회
  ③ commentThreads.list 로 상위 댓글·댓글별 좋아요 수집
  ④ 댓글 비활성 영상은 통계(조회수·좋아요)만 반영
쿼터 80% 초과 시 검색 횟수를 자동 축소한다.

YOUTUBE_API_KEY 미설정 시 '샘플 데이터 모드'로 동작한다.
"""
from __future__ import annotations

import hashlib

from config.settings import settings

from ..models.schemas import CollectedItem, SourceChannel

# 샘플 모드에서 수집을 시뮬레이션할 키워드 수 (실 연동 시 제거)
_SAMPLE_KEYWORD_LIMIT = 5

_SAMPLE_COMMENTS = [
    "부모님 해드렸는데 대화가 편해져서 저까지 좋네요",
    "가격이 부담돼요… 정부지원 신청 방법 자세히 알려주세요",
    "적응하는 데 한 달 걸렸는데 지금은 만족합니다",
    "어머니가 자꾸 되물으셔서 검사 예약했어요, 영상 감사합니다",
]


def collect(keywords: list[str]) -> list[CollectedItem]:
    """유튜브 수집. 키 미설정 시 샘플 데이터 모드."""
    if not settings.youtube_api_key:
        return _collect_samples(keywords)

    items: list[CollectedItem] = []
    for _kw in keywords:
        if _quota_over_warn():
            # TODO(담당): 검색 횟수 자동 축소 (rule §8: 다음 주기로 이월)
            break
        # TODO(담당): ① search.list (키워드당 settings.youtube_search_per_keyword 회)
        # ② videos.list 일괄 통계 ③ commentThreads.list 상위 댓글
        # ④ 댓글 비활성 → 통계만
    return items


def _collect_samples(keywords: list[str]) -> list[CollectedItem]:
    """샘플 데이터 생성. 규칙 ④(댓글 비활성 영상은 통계만)도 모사한다."""
    targets = keywords[:_SAMPLE_KEYWORD_LIMIT]
    print(f"[MOCK] 유튜브 API 키 미설정 → 샘플 데이터 모드 (키워드 {len(targets)}개 × 2영상)")

    items: list[CollectedItem] = []
    for kw in targets:
        seed = int(hashlib.md5(kw.encode("utf-8")).hexdigest()[:6], 16)
        # 댓글이 활성화된 영상
        items.append(
            CollectedItem(
                channel=SourceChannel.YOUTUBE,
                title=f"{kw}, 꼭 알아야 할 5가지 (이비인후과 전문의)",
                url=f"https://sample.youtube.com/watch?v=a{seed}",
                text=f"{kw}에 대해 검사부터 관리까지 단계별로 설명하는 영상",
                view_count=seed % 90000 + 8000,
                like_count=seed % 1200 + 100,
                top_comments=list(_SAMPLE_COMMENTS),
                raw={"mode": "sample", "comments_enabled": True},
            )
        )
        # 댓글 비활성 영상 → 통계만 반영 (rule §5 Step 3-④, §8)
        items.append(
            CollectedItem(
                channel=SourceChannel.YOUTUBE,
                title=f"부모님 {kw} 선물 브이로그",
                url=f"https://sample.youtube.com/watch?v=b{seed}",
                text=f"부모님께 {kw} 상담을 선물한 자녀의 브이로그",
                view_count=seed % 40000 + 3000,
                like_count=seed % 600 + 50,
                top_comments=[],  # 댓글 비활성 → 통계만
                raw={"mode": "sample", "comments_enabled": False},
            )
        )
    return items


def _quota_over_warn() -> bool:
    """TODO(담당): 실제 쿼터 사용량 조회 후 80% 초과 여부 반환."""
    return False  # placeholder
