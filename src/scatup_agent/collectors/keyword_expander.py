"""Step 1 · 키워드 확장 (rule §5 Step 1).

시드 키워드 + 네이버 연관검색어(자동완성 API)를 결합해 탐색 키워드를 확장한다.
연관검색어 조회는 API 키 없이 동작하며, 실패 시 해당 키워드만 건너뛴다
(rule §4-2: API 응답 오류 → 해당 소스만 skip, 전체 중단 금지).
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from config.settings import settings

_AC_ENDPOINT = "https://ac.search.naver.com/nx/ac"


def fetch_related(keyword: str, limit: int | None = None) -> list[str]:
    """네이버 자동완성 API로 키워드 1개의 연관검색어를 조회한다."""
    if limit is None:
        limit = settings.related_keywords_per_seed
    query = urllib.parse.urlencode({
        "q": keyword,
        "con": "1",
        "frm": "nv",
        "ans": "2",
        "r_format": "json",
        "r_enc": "UTF-8",
        "q_enc": "UTF-8",
        "st": "100",
        "t_koreng": "1",
    })
    req = urllib.request.Request(
        f"{_AC_ENDPOINT}?{query}",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.naver.com/",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []  # rule §4-2: 해당 소스만 skip

    related: list[str] = []
    for group in data.get("items", []):
        for entry in group:
            if entry and isinstance(entry, (list, tuple)):
                term = str(entry[0]).strip()
                if term and term != keyword:
                    related.append(term)
    return related[:limit]


def expand(seed_keywords: list[str], per_keyword: int | None = None) -> list[str]:
    """시드 키워드 + 연관검색어를 결합·중복 제거해 확장 키워드를 만든다."""
    expanded: list[str] = list(seed_keywords)
    for seed in seed_keywords:
        expanded += fetch_related(seed, per_keyword)
    deduped = list(dict.fromkeys(k.strip() for k in expanded if k.strip()))
    return deduped[: settings.max_expanded_keywords]
