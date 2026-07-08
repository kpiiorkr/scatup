"""실행 트리거 (rule §2).

2~3일 주기 정기 실행 + 이벤트 기반(급상승 검색어, 유튜브 급상승, 이슈성 뉴스).
"""
from __future__ import annotations

from ..models.schemas import TriggerType
from config.settings import settings


def should_run_scheduled(days_since_last_run: int) -> bool:
    """정기 실행 주기 도래 여부."""
    return days_since_last_run >= settings.run_interval_days


def detect_event_trigger() -> TriggerType | None:
    """TODO(담당): 급상승 검색어/유튜브 급상승/이슈성 뉴스 감지."""
    # TODO: 데이터랩 급상승·이슈성 뉴스 모니터링
    return None
