"""Step 4 · 데이터 정제 (rule §5 Step 4).

수집 데이터의 관련성 스코어링 및 정제. Claude 프롬프트로 전처리·스코어링.
"""
from __future__ import annotations

from ..models.schemas import CollectedItem


def score_and_refine(items: list[CollectedItem]) -> list[CollectedItem]:
    """TODO(담당): Claude 기반 관련성 스코어링 후 정렬/필터."""
    for it in items:
        it.relevance_score = 0.0  # TODO: 실제 스코어 계산
    return items
