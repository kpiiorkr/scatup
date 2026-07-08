"""출력 검증 (rule §9-3).

팩트체크, 브랜드보이스 체크, 저작권 유사도 검사, 주간 소재 적중률 점검.
"""
from __future__ import annotations

from ..models.schemas import PipelineContext, SensitivityFlag
from config.settings import settings


def validate_output(ctx: PipelineContext) -> None:
    """TODO(담당): 각 검증 항목 구현."""
    if ctx.draft is None:
        return
    # 저작권 유사도 초과 시 초안 반려 (§6, §8)
    if ctx.draft.metadata.similarity_score > settings.plagiarism_similarity_threshold:
        ctx.draft.metadata.sensitivity_flags.append(SensitivityFlag.PLAGIARISM)
        ctx.halt("표절 유사도 초과 → 초안 반려 후 재작성 요청")
