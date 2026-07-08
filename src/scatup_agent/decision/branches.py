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
    # TODO(담당): 재확장/재수집 루프 (settings.max_recollect_attempts)
    ctx.halt("데이터 부족: 재수집 후에도 임계치 미달 → 소재 후보 제외")


def is_evidence_missing(evidence: list) -> bool:
    return len(evidence) == 0


def handle_evidence_missing(ctx: PipelineContext) -> None:
    """RAG 근거 미확보 → 초안 생성 보류, '근거 부족' 플래그."""
    ctx.halt("근거 부족: 신뢰 근거 미확보 → 초안 생성 보류")
