"""Step 1 · 키워드 확장 (rule §5 Step 1).

시드 키워드 + 데이터랩 연관검색어를 결합해 탐색 키워드를 확장한다.
"""
from __future__ import annotations


def expand(seed_keywords: list[str]) -> list[str]:
    """TODO(담당): 데이터랩 연관검색어 API 연동 후 결합.

    현재는 뼈대만 제공하며 시드를 그대로 반환한다.
    """
    # TODO: DataLab 연관검색어 조회 → 병합 → 중복 제거
    return list(dict.fromkeys(seed_keywords))
