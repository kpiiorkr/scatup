"""국가법령정보센터 Open API 클라이언트 (rule §7-1, §7-2).

의료법 제56조·시행령·관련 고시의 최신 조문을 실시간 조회한다.
주의: 이 API는 '조회' 서비스이며 위법 여부를 판정하지 않는다(§7-1).
LAW_API_KEY 미설정/실패 시 LawApiError 를 raise → fail-safe(§7-3)로 전환된다.
"""
from __future__ import annotations

from config.settings import settings


class LawApiError(Exception):
    """법령 API 응답 실패/타임아웃 (fail-safe 트리거, §7-3)."""


def fetch_prohibition_clauses() -> list[str]:
    """의료법 금지 조항 최신 조문 조회.

    실패/타임아웃 시 LawApiError 를 raise 하여 fail-safe 로 전환시킨다.
    """
    if not settings.law_api_key:
        raise LawApiError("LAW_API_KEY 미설정 → 실시간 조문 조회 불가")
    # TODO(담당): law.go.kr Open API 호출 (OC=키, target=law, MST=의료법)
    raise LawApiError("law.go.kr API 실연동 전")


def local_snapshot_clauses() -> list[str]:
    """의료법 제56조 요지 로컬 스냅샷 (fail-safe 시 1단계 순화의 최소 기준).

    실시간 조문을 대체하지 않으며(§7-1), 스냅샷 사용 시 반드시
    '담당자 판단 필요' 상태를 유지해야 한다(§7-3: 자동 통과 절대 금지).
    """
    return [
        "치료효과를 보장하는 등 소비자를 현혹할 우려가 있는 내용의 광고 금지",
        "특정 의료인·이용자의 치료 경험담을 통해 효과를 오인하게 하는 광고 금지",
        "객관적 근거 없이 효과를 단정하거나 부작용이 없다고 표현하는 광고 금지",
        "다른 의료기관·의료인과 비교하여 우수함을 표방하는 광고 금지",
    ]
