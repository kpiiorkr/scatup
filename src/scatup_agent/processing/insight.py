"""Step 5 · 인사이트 도출 (rule §5 Step 5).

급상승 토픽, 감성 포인트, 소재 후보를 도출한다.
"""
from __future__ import annotations

from ..models.schemas import CollectedItem, TrendInsight


def derive(items: list[CollectedItem]) -> TrendInsight:
    """TODO(담당): 급상승 토픽/감성/소재 후보 도출."""
    return TrendInsight()
