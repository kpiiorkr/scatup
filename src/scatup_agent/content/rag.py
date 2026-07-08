"""Step 7 · RAG 근거 검색 (rule §5 Step 7).

난청 지식베이스(5종 문서)에서 근거 문서를 검색한다.
근거 미확보 시 초안 생성을 보류하고 '근거 부족' 플래그를 부착한다(§6).
"""
from __future__ import annotations


def search_evidence(plan: dict) -> list[dict]:
    """TODO(담당): 난청 지식베이스 임베딩 검색.

    반환: [{"doc": 문서명, "snippet": ..., "score": ...}, ...]
    """
    return []
