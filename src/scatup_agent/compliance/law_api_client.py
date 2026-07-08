"""국가법령정보센터 Open API 클라이언트 (rule §7-1, §7-2).

의료법 제56조·시행령·관련 고시의 최신 조문을 실시간 조회한다.
주의: 이 API는 '조회' 서비스이며 위법 여부를 판정하지 않는다(§7-1).
"""
from __future__ import annotations


class LawApiError(Exception):
    """법령 API 응답 실패/타임아웃 (fail-safe 트리거, §7-3)."""


def fetch_prohibition_clauses() -> list[str]:
    """TODO(담당): 의료법 금지 조항 최신 조문 조회.

    실패/타임아웃 시 LawApiError 를 raise 하여 fail-safe 로 전환시킨다.
    """
    # TODO: law.go.kr Open API 호출
    raise NotImplementedError("law.go.kr API 연동 필요")
