"""Step 4 · 데이터 정제 (rule §5 Step 4).

수집 데이터의 관련성 스코어링 및 정제.
현재는 규칙 기반 스코어링이며, 추후 Mistral 프롬프트 스코어링으로 교체 가능.
"""
from __future__ import annotations

from ..models.schemas import CollectedItem

# 타겟 주제(난청·보청기·치매) 관련 용어 — 포함 시 가점
_TOPIC_TERMS = (
    "난청", "보청기", "이명", "청력", "귀", "치매", "인지",
    "정부지원", "보조금", "장애등급", "이비인후과",
)
# 무관 소재(기기 고장·동명이인 등) — 포함 시 감점
_NOISE_TERMS = ("에어팟", "버즈", "이어폰", "블루투스", "헤드셋", "이명학")

_MIN_RELEVANCE = 0.3  # 이 점수 미만은 소재 후보에서 제외


def score_and_refine(items: list[CollectedItem]) -> list[CollectedItem]:
    """관련성 스코어링 후 임계 미달 자료를 걸러내고 점수순 정렬한다."""
    for it in items:
        it.relevance_score = _score(it)

    refined = sorted(
        (it for it in items if it.relevance_score >= _MIN_RELEVANCE),
        key=lambda it: it.relevance_score,
        reverse=True,
    )
    print(f"[REFINE] 수집 {len(items)}건 → 관련성 필터 후 {len(refined)}건 (임계 {_MIN_RELEVANCE})")
    return refined


def _score(item: CollectedItem) -> float:
    """제목·본문의 주제어 매칭 + 반응 지표로 0~1 점수를 계산한다."""
    score = 0.0
    for term in _TOPIC_TERMS:
        if term in item.title:
            score += 0.25
        if term in item.text:
            score += 0.10
    for term in _NOISE_TERMS:
        if term in item.title or term in item.text:
            score -= 0.5

    # 반응(조회수·좋아요) 가점: 최대 0.2
    engagement = min(0.2, item.view_count / 500_000 + item.like_count / 10_000)
    score += engagement
    return max(0.0, min(1.0, score))
