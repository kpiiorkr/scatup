"""실행 트리거 (rule §2).

2~3일 주기 정기 실행 + 이벤트 기반(급상승 검색어, 유튜브 급상승, 이슈성 뉴스).
"""
from __future__ import annotations

from datetime import date, timedelta

import requests

from ..models.schemas import TriggerType
from config.settings import settings

# 데이터랩 검색어트렌드 API 제약: keywordGroups 최대 5개
_MAX_KEYWORD_GROUPS = 5
_TIMEOUT_SECONDS = 5


def should_run_scheduled(days_since_last_run: int) -> bool:
    """정기 실행 주기 도래 여부."""
    return days_since_last_run >= settings.run_interval_days


def detect_event_trigger() -> TriggerType | None:
    """급상승 검색어/유튜브 급상승/이슈성 뉴스 감지.

    데이터랩 검색어트렌드로 급상승 검색어를 감지한다.
    (유튜브 조회수 급상승·이슈성 뉴스 감지는 TODO(담당))
    """
    if _is_rising_keyword():
        return TriggerType.RISING_KEYWORD
    return None


def _is_rising_keyword() -> bool:
    """데이터랩 검색어트렌드로 시드 키워드의 급상승 여부를 판단한다.

    최근일 검색 비율이 그 이전 기간 평균의 threshold배를 초과하면 급상승으로 본다.
    키 미설정/조회 실패 시 이 트리거만 skip 한다 (§4-2: 해당 소스만 skip, 전체 중단 금지).
    """
    if not (settings.naver_client_id and settings.naver_client_secret):
        return False

    keywords = list(settings.seed_keywords[:_MAX_KEYWORD_GROUPS])
    end = date.today()
    start = end - timedelta(days=settings.datalab_lookback_days - 1)

    try:
        resp = requests.post(
            f"{settings.naver_openapi_base}/datalab/search",
            headers={
                "X-Naver-Client-Id": settings.naver_client_id,
                "X-Naver-Client-Secret": settings.naver_client_secret,
                "Content-Type": "application/json",
            },
            json={
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "timeUnit": "date",
                "keywordGroups": [{"groupName": kw, "keywords": [kw]} for kw in keywords],
            },
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    except (requests.RequestException, ValueError, KeyError) as err:
        print(f"[TRIGGER] 데이터랩 조회 실패: {err} → 급상승 감지 skip")
        return False

    for result in results:
        if _has_spike(result.get("data", [])):
            print(f"[TRIGGER] 급상승 감지: '{result.get('title')}' 검색량 급증")
            return True
    return False


def _has_spike(data: list[dict]) -> bool:
    """마지막 날 비율이 이전 기간 평균의 threshold배를 초과하는지 확인한다."""
    if len(data) < 2:
        return False
    ratios = [point["ratio"] for point in data]
    latest, history = ratios[-1], ratios[:-1]
    avg_history = sum(history) / len(history)
    if avg_history <= 0:
        return False
    return latest / avg_history > settings.datalab_spike_ratio_threshold
