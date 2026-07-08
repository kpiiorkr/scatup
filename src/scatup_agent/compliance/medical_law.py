"""Step 9 · 의료법 준수 필터링 (rule §7, 최우선 CRITICAL).

「명백한 위반은 기계가, 애매한 영역은 사람이」 2단계 판정 구조.
안전 우선(fail-safe): 법령 API 실패 시 전부 '담당자 판단 필요'로 전환하며
어떤 경우에도 자동 통과를 허용하지 않는다(§7-3).
"""
from __future__ import annotations

from ..models.schemas import BlogDraft, ComplianceStatus, SensitivityFlag
from . import law_api_client


def review(draft: BlogDraft) -> BlogDraft:
    """초안을 의료법 기준으로 검수한다."""
    try:
        clauses = law_api_client.fetch_prohibition_clauses()
    except (law_api_client.LawApiError, NotImplementedError):
        # fail-safe: API 실패/타임아웃 → 전부 담당자 판단 필요, 자동 통과 금지
        draft.metadata.compliance_status = ComplianceStatus.NEEDS_HUMAN_REVIEW
        return draft

    # 1단계: 명확한 위반 → 자동 순화/삭제 후 진행
    draft.body, sanitized = _stage1_auto_sanitize(draft.body, clauses)

    # 2단계: 애매한 표현 → 담당자 판단 필요 (발행 차단)
    if _stage2_is_ambiguous(draft.body, clauses):
        draft.metadata.compliance_status = ComplianceStatus.NEEDS_HUMAN_REVIEW
        draft.metadata.sensitivity_flags.append(SensitivityFlag.MEDICAL_SENSITIVE)
        return draft

    draft.metadata.compliance_status = (
        ComplianceStatus.AUTO_SANITIZED if sanitized else ComplianceStatus.AUTO_SANITIZED
    )
    return draft


def requires_human(draft: BlogDraft) -> bool:
    """담당자 판단이 필요한 상태인지 (자동 발행 경로 차단 여부)."""
    return draft.metadata.compliance_status in {
        ComplianceStatus.NEEDS_HUMAN_REVIEW,
        ComplianceStatus.BLOCKED,
    }


def _stage1_auto_sanitize(body: str, clauses: list[str]) -> tuple[str, bool]:
    """TODO(담당): 법령에 문언적으로 명백히 해당하는 표현을 순화/삭제.

    예: '완치', '100% 효과', '부작용 전혀 없음', 체험담 효과 보장 서술.
    반환: (수정된 본문, 수정 여부)
    """
    return body, False


def _stage2_is_ambiguous(body: str, clauses: list[str]) -> bool:
    """TODO(담당): 조문만으로 판단이 어려운 애매 표현 탐지.

    맥락상 완곡한 효과 암시, 법령 미열거 표현, 유권해석 필요 등.
    """
    return False
