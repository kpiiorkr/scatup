"""출력 검증 (rule §9-3).

팩트체크, 브랜드보이스 체크, 저작권 유사도 검사, 주간 소재 적중률 점검.
"""
from __future__ import annotations

from ..models.schemas import PipelineContext, SensitivityFlag
from config.settings import settings

# 브랜드보이스 금칙어: 타겟(40~50대)에게 부적절한 표현 (팀에서 지속 보강)
_BRAND_VOICE_BLOCKLIST = ("싸구려", "노인네", "귀머거리", "장사꾼")


def validate_output(ctx: PipelineContext) -> None:
    """팩트체크·브랜드보이스·저작권 유사도 검증. 미달 시 반려/이관."""
    if ctx.draft is None:
        return

    # 1) 팩트체크: 근거 문서 없이 본문이 작성됐는지 확인 (§6 근거 부족)
    if not ctx.draft.evidence_links:
        ctx.draft.metadata.sensitivity_flags.append(SensitivityFlag.EVIDENCE_MISSING)
        ctx.halt("근거 문서 없는 초안 → 담당자 검토 필요")
        return

    # 2) 브랜드보이스 체크
    bad_words = [w for w in _BRAND_VOICE_BLOCKLIST if w in ctx.draft.body]
    if bad_words:
        ctx.draft.metadata.sensitivity_flags.append(SensitivityFlag.QUALITY_FAIL)
        ctx.halt(f"브랜드보이스 위반 표현 {bad_words} → 재작성 요청")
        return

    # 3) 저작권 유사도: 수집 원문과의 최대 유사도 (문자 2-gram 자카드)
    similarity = max(
        (_jaccard(ctx.draft.body, it.text) for it in ctx.collected),
        default=0.0,
    )
    ctx.draft.metadata.similarity_score = round(similarity, 3)
    if similarity > settings.plagiarism_similarity_threshold:
        ctx.draft.metadata.sensitivity_flags.append(SensitivityFlag.PLAGIARISM)
        ctx.halt("표절 유사도 초과 → 초안 반려 후 재작성 요청")
        return

    print(
        f"[VALIDATE] 팩트체크·브랜드보이스 통과, 유사도 {similarity:.3f} "
        f"≤ {settings.plagiarism_similarity_threshold} 통과"
    )
    # TODO(담당): 주간 소재 적중률 점검 (발행 후 성과와 연계 — §11 2차 과제)


def _ngrams(text: str, n: int = 2) -> set[str]:
    compact = "".join(text.split())
    return {compact[i : i + n] for i in range(len(compact) - n + 1)}


def _jaccard(a: str, b: str) -> float:
    na, nb = _ngrams(a), _ngrams(b)
    if not na or not nb:
        return 0.0
    return len(na & nb) / len(na | nb)
