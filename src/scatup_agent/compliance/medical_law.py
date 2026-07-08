"""Step 9 · 의료법 준수 필터링 (rule §7, 최우선 CRITICAL).

「명백한 위반은 기계가, 애매한 영역은 사람이」 2단계 판정 구조.
안전 우선(fail-safe): 법령 API 실패 시 전부 '담당자 판단 필요'로 전환하며
어떤 경우에도 자동 통과를 허용하지 않는다(§7-3).
"""
from __future__ import annotations

from ..models.schemas import BlogDraft, ComplianceStatus, SensitivityFlag
from . import law_api_client

# 1단계: 법령에 문언적으로 명백히 해당하는 표현 → 자동 순화 (rule §7-2)
_STAGE1_SANITIZE = {
    "완치된다": "호전을 기대할 수 있다",
    "완치": "호전",
    "100% 효과": "효과(개인차 있음)",
    "부작용 전혀 없음": "부작용 여부는 개인마다 다를 수 있음",
    "부작용이 전혀 없": "부작용 여부는 개인마다 다를 수 있",
    "즉시 회복": "점진적 개선",
}

# 2단계: 조문만으로 판단이 어려운 애매 표현 → 담당자 판단 (rule §7-2)
_STAGE2_AMBIGUOUS = (
    "효과 보장", "확실한 효과", "무조건 좋아", "치매 예방 효과",
    "청력 회복", "치료 효과", "최고의", "유일한",
)


def review(draft: BlogDraft) -> BlogDraft:
    """초안을 의료법 기준으로 검수한다."""
    failsafe = False
    try:
        clauses = law_api_client.fetch_prohibition_clauses()
    except (law_api_client.LawApiError, NotImplementedError) as err:
        # fail-safe(§7-3): 실시간 조문 조회 불가 → 로컬 스냅샷으로 1단계 순화는
        # 최선을 다해 수행하되, 자동 통과는 절대 금지 (담당자 판단 필요 강제)
        print(f"[COMPLIANCE] 법령 API 조회 실패({err}) → fail-safe 발동")
        clauses = law_api_client.local_snapshot_clauses()
        failsafe = True

    # 1단계: 명확한 위반 → 자동 순화/삭제 후 진행
    draft.body, sanitized_terms = _stage1_auto_sanitize(draft.body, clauses)
    if sanitized_terms:
        print(f"[COMPLIANCE] 1단계 자동 순화 {len(sanitized_terms)}건: {sanitized_terms}")

    if failsafe:
        draft.metadata.compliance_status = ComplianceStatus.NEEDS_HUMAN_REVIEW
        print("[COMPLIANCE] fail-safe: 전건 '담당자 판단 필요' 처리 (자동 통과 금지)")
        return draft

    # 2단계: 애매한 표현 → 담당자 판단 필요 (발행 차단)
    ambiguous = _stage2_find_ambiguous(draft.body, clauses)
    if ambiguous:
        draft.metadata.compliance_status = ComplianceStatus.NEEDS_HUMAN_REVIEW
        draft.metadata.sensitivity_flags.append(SensitivityFlag.MEDICAL_SENSITIVE)
        print(f"[COMPLIANCE] 2단계 애매 표현 {len(ambiguous)}건 → 담당자 판단 필요: {ambiguous}")
        return draft

    draft.metadata.compliance_status = ComplianceStatus.AUTO_SANITIZED
    print("[COMPLIANCE] 1·2단계 통과 (자동 순화 후 진행)")
    return draft


def requires_human(draft: BlogDraft) -> bool:
    """담당자 판단이 필요한 상태인지 (자동 발행 경로 차단 여부)."""
    return draft.metadata.compliance_status in {
        ComplianceStatus.NEEDS_HUMAN_REVIEW,
        ComplianceStatus.BLOCKED,
    }


def _stage1_auto_sanitize(body: str, clauses: list[str]) -> tuple[str, list[str]]:
    """법령에 문언적으로 명백히 해당하는 표현을 순화하고, 순화 목록을 반환한다."""
    sanitized: list[str] = []
    for banned, replacement in _STAGE1_SANITIZE.items():
        if banned in body:
            body = body.replace(banned, replacement)
            sanitized.append(banned)
    return body, sanitized


def _stage2_find_ambiguous(body: str, clauses: list[str]) -> list[str]:
    """맥락 해석이 필요한 애매 표현을 찾는다 (발견 시 담당자 이관).

    TODO(담당): 담당자 판단 사례 DB(§7-2 3단계 학습 루프)와 연동해 정확도 향상.
    """
    return [term for term in _STAGE2_AMBIGUOUS if term in body]
