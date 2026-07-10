"""국가법령정보센터 Open API 클라이언트 (rule §7-1, §7-2).

의료법 제56조(의료광고의 금지 등)의 최신 조문을 실시간 조회한다.
주의: 이 API는 '조회' 서비스이며 위법 여부를 판정하지 않는다(§7-1).
LAW_API_KEY 미설정/조회 실패 시 LawApiError 를 raise → fail-safe(§7-3)로 전환된다.
"""
from __future__ import annotations

import time

import requests

from config.settings import settings

_TARGET_LAW_NAME = "의료법"
_TARGET_ARTICLE_NO = "56"
# (connect, read) 타임아웃. law.go.kr은 해외(예: GitHub Actions 러너)에서 연결이 느려
# connect 단계에서 자주 타임아웃 나므로 connect 여유를 크게 준다.
_TIMEOUT = (20, 25)
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 2


class LawApiError(Exception):
    """법령 API 응답 실패/타임아웃 (fail-safe 트리거, §7-3)."""


def _get(url: str, params: dict) -> requests.Response:
    """GET을 재시도와 함께 수행한다. 마지막 시도까지 실패하면 예외를 그대로 올린다.

    (일시적 지연·연결 실패를 흡수하려는 것일 뿐, 최종 실패 시에는 fail-safe(§7-3)로 간다.)
    """
    last_err: requests.RequestException | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as err:
            last_err = err
            print(f"[LAW] 조회 실패 재시도 {attempt}/{_MAX_ATTEMPTS}: {err}")
            if attempt < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF_SECONDS)
    assert last_err is not None
    raise last_err


def fetch_prohibition_clauses() -> list[str]:
    """의료법 제56조 금지 조항의 최신 조문을 조회해 항/호/목을 평탄화한 목록으로 반환한다.

    조회·파싱 중 어떤 문제든 발생하면 LawApiError 를 raise 하여 fail-safe 로 전환시킨다
    (§7-3: 자동 통과 절대 금지 — 실패 시 절대 조용히 넘어가지 않는다).
    """
    if not settings.law_api_key:
        raise LawApiError("LAW_API_KEY 미설정 → 실시간 조문 조회 불가")

    try:
        mst = _find_law_mst(_TARGET_LAW_NAME)
        article = _fetch_article(mst, _TARGET_ARTICLE_NO)
        clauses = _flatten_clauses(article)
    except requests.RequestException as err:
        raise LawApiError(f"law.go.kr API 호출 실패: {err}") from err
    except (ValueError, KeyError) as err:
        raise LawApiError(f"law.go.kr 응답 파싱 실패: {err}") from err

    if not clauses:
        raise LawApiError(f"제{_TARGET_ARTICLE_NO}조 조문 내용이 비어 있음")
    return clauses


def _find_law_mst(law_name: str) -> str:
    """법령명으로 법령일련번호(MST)를 조회한다 (lawSearch.do)."""
    resp = _get(
        f"{settings.law_api_base}/lawSearch.do",
        params={
            "OC": settings.law_api_key,
            "target": "law",
            "type": "JSON",
            "query": law_name,
            "search": 1,
        },
    )
    laws = _as_list(resp.json().get("LawSearch", {}).get("law"))
    for law in laws:
        if law.get("법령명한글") == law_name:
            return law["법령일련번호"]
    raise ValueError(f"'{law_name}' 법령을 검색 결과에서 찾을 수 없음")


def _fetch_article(mst: str, article_no: str) -> dict:
    """법령 본문을 조회해 지정한 조문번호의 조문단위를 반환한다 (lawService.do)."""
    resp = _get(
        f"{settings.law_api_base}/lawService.do",
        params={"OC": settings.law_api_key, "target": "law", "MST": mst, "type": "JSON"},
    )
    units = _as_list(resp.json()["법령"]["조문"]["조문단위"])
    for unit in units:
        if unit.get("조문번호") == article_no and unit.get("조문여부") == "조문":
            return unit
    raise ValueError(f"제{article_no}조를 조문 목록에서 찾을 수 없음")


def _flatten_clauses(article: dict) -> list[str]:
    """조문단위의 항/호/목 계층을 문자열 리스트로 평탄화한다."""
    clauses: list[str] = []
    for hang in _as_list(article.get("항")):
        clauses.append(hang["항내용"])
        for ho in _as_list(hang.get("호")):
            clauses.append(ho["호내용"])
            for mok in _as_list(ho.get("목")):
                clauses.append(mok["목내용"])
    return clauses


def _as_list(value: object) -> list:
    """law.go.kr JSON은 항목이 하나면 dict, 여럿이면 list로 내려와 형태를 통일한다."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


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
