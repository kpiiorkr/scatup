"""입력 검증 규칙 (rule §4-2).

API 응답 오류→해당 소스 skip / 키워드 형식 오류→기본값 대체 /
크롤링 0건→재수집 / 유튜브 쿼터 80% 초과→검색 횟수 축소.
"""
from __future__ import annotations


def normalize_keywords(keywords: list[str]) -> list[str]:
    """키워드 형식 오류 시 기본값으로 대체."""
    cleaned = [k.strip() for k in keywords if isinstance(k, str) and k.strip()]
    return cleaned or ["난청", "보청기", "치매"]  # 기본값
