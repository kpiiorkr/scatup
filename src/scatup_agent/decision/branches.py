"""판단 분기 규칙 (rule §6).

데이터 부족 / 근거 부족 등 조건에 따른 처리를 모은다.
"""
from __future__ import annotations

from ..models.schemas import PipelineContext
from config.settings import settings


def is_data_insufficient(ctx: PipelineContext) -> bool:
    return len(ctx.collected) < settings.min_collection_count


def handle_data_insufficient(ctx: PipelineContext) -> None:
    """키워드 재확장 후 재수집, 부족 지속 시 소재 후보 제외."""
    from ..collectors import keyword_expander, naver_collector, youtube_collector

    for attempt in range(1, settings.max_recollect_attempts + 1):
        print(
            f"[RETRY] 데이터 부족({len(ctx.collected)}건 < {settings.min_collection_count}건)"
            f" → 연관검색어 재확장 후 재수집 ({attempt}/{settings.max_recollect_attempts})"
        )
        wider = keyword_expander.expand(ctx.expanded_keywords)
        new_keywords = [k for k in wider if k not in ctx.expanded_keywords]
        if not new_keywords:
            print("[RETRY] 새로 확장된 키워드 없음 → 재수집 중단")
            break

        print(f"[EXPAND] 연관검색어 {len(new_keywords)}개 추가: {new_keywords}")
        ctx.expanded_keywords += new_keywords
        ctx.collected += naver_collector.collect(new_keywords)
        ctx.collected += youtube_collector.collect(new_keywords)
        _dedupe_collected(ctx)

        if not is_data_insufficient(ctx):
            print(f"[RETRY] 재수집 성공: 총 {len(ctx.collected)}건 확보 → 파이프라인 계속")
            return

    ctx.halt("데이터 부족: 재수집 후에도 임계치 미달 → 소재 후보 제외")


def _dedupe_collected(ctx: PipelineContext) -> None:
    """재수집 시 같은 URL 자료가 중복 집계되지 않도록 제거한다."""
    seen: set[str] = set()
    unique = []
    for item in ctx.collected:
        if item.url in seen:
            continue
        seen.add(item.url)
        unique.append(item)
    ctx.collected = unique


def is_evidence_missing(evidence: list) -> bool:
    return len(evidence) == 0


def handle_evidence_missing(ctx: PipelineContext) -> None:
    """RAG 근거 미확보 → 초안 생성 보류, '근거 부족' 플래그."""
    ctx.halt("근거 부족: 신뢰 근거 미확보 → 초안 생성 보류")
