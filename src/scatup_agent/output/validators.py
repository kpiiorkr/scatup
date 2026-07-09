"""출력 검증 (rule §9-3).

팩트체크, 브랜드보이스 체크, 저작권 유사도 검사, 주간 소재 적중률 점검.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..models.schemas import PipelineContext, SensitivityFlag
from config.settings import settings

# 브랜드보이스 금칙어: 타겟(40~50대)에게 부적절한 표현 (팀에서 지속 보강)
_BRAND_VOICE_BLOCKLIST = ("싸구려", "노인네", "귀머거리", "장사꾼")

# 팩트체크: 근거 문서(RAG 지식베이스)에 대조할 고위험 수치 유형 (rule §9-3)
# 지원 비율(%)·금액(만원/원)·배수(배)·청력 수치(dB) — LLM 초안에서 지어내기 쉬운 값들.
# 연도·나이·시간 등 저위험·오탐 잦은 유형은 MVP 범위에서 제외한다.
_FACT_RE = re.compile(r"(\d[\d.~\-]*)(억원|만원|원|%|배|dB|데시벨)")
_KB_DIR = Path(__file__).resolve().parents[3] / "data" / "knowledge_base"


def validate_output(ctx: PipelineContext) -> None:
    """팩트체크·브랜드보이스·저작권 유사도 검증. 미달 시 반려/이관."""
    if ctx.draft is None:
        return

    # 1) 팩트체크 (a): 근거 문서 없이 본문이 작성됐는지 확인 (§6 근거 부족)
    if not ctx.draft.evidence_links:
        ctx.draft.metadata.sensitivity_flags.append(SensitivityFlag.EVIDENCE_MISSING)
        ctx.halt("근거 문서 없는 초안 → 담당자 검토 필요")
        return

    # 1) 팩트체크 (b): 근거 문서에 없는 수치·통계 탐지 (LLM 할루시네이션 가드, §9-3)
    #    fail-safe(§7-3 정신): 미검증 수치는 자동 통과시키지 않고 담당자 사실 확인으로 보낸다.
    unverified = _find_unverified_facts(ctx.draft.body)
    if unverified:
        ctx.draft.metadata.sensitivity_flags.append(SensitivityFlag.UNVERIFIED_FACT)
        preview = ", ".join(unverified[:8])
        ctx.halt(f"근거 문서에 없는 수치 {len(unverified)}건(할루시네이션 의심): {preview} → 담당자 사실 확인 필요")
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


def _find_unverified_facts(body: str) -> list[str]:
    """본문의 수치 표현 중 근거 문서(RAG 지식베이스)에 없는 것을 찾는다.

    지원 비율·금액·배수·청력 수치처럼 지어내기 쉬운 값을 추출해, 큐레이션된
    지식베이스 전체와 대조한다. 어느 문서에도 없으면 할루시네이션으로 의심한다.
    (수집한 네이버·유튜브 원문은 그 자체가 미검증이므로 대조 기준에서 제외한다.)
    """
    corpus = _normalize(_load_kb_corpus())
    if not corpus:
        return []  # 근거 코퍼스가 없으면 대조 불가 → 여기서 판단하지 않음

    seen: list[str] = []
    for number, unit in _FACT_RE.findall(body):
        token = _normalize(number + unit)
        if token not in corpus and token not in seen:
            seen.append(token)
    return seen


def _load_kb_corpus() -> str:
    if not _KB_DIR.exists():
        return ""
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(_KB_DIR.glob("*.md")))


def _normalize(text: str) -> str:
    """공백·쉼표를 제거해 '200~300 만원'과 '200~300만원'을 동일 비교한다."""
    return re.sub(r"[\s,]", "", text)


def _ngrams(text: str, n: int = 2) -> set[str]:
    compact = "".join(text.split())
    return {compact[i : i + n] for i in range(len(compact) - n + 1)}


def _jaccard(a: str, b: str) -> float:
    na, nb = _ngrams(a), _ngrams(b)
    if not na or not nb:
        return 0.0
    return len(na & nb) / len(na | nb)
