"""Step 5 · 인사이트 도출 (rule §5 Step 5).

급상승 토픽, 감성 포인트, 소재 후보를 도출한다.
"""
from __future__ import annotations

from collections import Counter

from ..models.schemas import CollectedItem, TrendInsight

_TOPIC_TERMS = (
    "보청기 정부지원", "보청기 가격", "돌발성 난청", "노인성 난청",
    "난청 장애등급", "이명", "치매", "청력 검사", "보청기", "난청",
)

# 감성 신호어 → 리포트 문구
_SENTIMENT_CUES = {
    "가격 부담·비용 문의가 많음 (정부지원 정보 수요 큼)": ("부담", "비싸", "가격", "지원"),
    "가족(자녀 세대)이 부모님을 위해 알아보는 흐름이 뚜렷함": ("부모님", "아버지", "어머니", "가족", "선물"),
    "치료효과 단정형 과장 광고에 대한 불신·불안이 존재함": ("완치", "광고", "믿어도", "걱정"),
    "착용 적응기 경험담에 대한 관심이 높음": ("적응", "후기", "만족"),
}


def derive(items: list[CollectedItem]) -> TrendInsight:
    """정제된 수집 자료에서 급상승 토픽·감성 포인트·소재 후보를 뽑는다."""
    # 급상승 토픽: 주제어별 (등장 건수 × 반응) 가중 집계
    topic_weight: Counter[str] = Counter()
    for it in items:
        content = it.title + " " + it.text + " " + " ".join(it.top_comments)
        for term in _TOPIC_TERMS:
            if term in content:
                topic_weight[term] += 1 + it.view_count // 10_000

    rising = [term for term, _ in topic_weight.most_common(5)]

    # 감성 포인트: 본문·댓글에서 신호어 매칭
    all_text = " ".join(
        it.title + it.text + " ".join(it.top_comments) for it in items
    )
    sentiments = [
        point
        for point, cues in _SENTIMENT_CUES.items()
        if any(cue in all_text for cue in cues)
    ]

    # 소재 후보: 데이터 신호 기반 + 타겟(40~50대 자녀 세대) 관점, 어법에 맞는 제목만.
    # '신청 방법'은 신청 가능한 대상(보청기·정부지원)에만 붙이고 상태어(난청·이명)엔 붙이지 않는다.
    signal = " ".join(rising) + " " + " ".join(sentiments)
    candidates: list[str] = []
    if any(k in signal for k in ("정부지원", "지원", "가격", "부담", "비용", "보조금")):
        candidates.append("부모님 보청기 정부지원, 신청 자격부터 절차까지 총정리")
    if any(k in signal for k in ("치매", "인지")):
        candidates.append("난청을 방치하면 치매 위험이? 부모님 청력이 뇌 건강인 이유")
    if "이명" in signal:
        candidates.append("부모님 이명(귀울림), 원인부터 일상 관리법까지")
    for fallback in (
        "부모님 난청, 이런 신호면 청력 검사받으세요 — 자가 점검 가이드",
        "부모님 첫 보청기, 후회 없이 고르는 종류·선택 가이드",
        "부모님 청력 관리, 지금 시작하는 법",
    ):
        candidates.append(fallback)
    candidates = list(dict.fromkeys(candidates))[:3]

    result = TrendInsight(
        rising_topics=rising,
        sentiment_points=sentiments,
        topic_candidates=candidates,
    )
    print(f"[INSIGHT] 급상승 토픽 {len(rising)}개: {rising}")
    print(f"[INSIGHT] 감성 포인트 {len(sentiments)}개, 소재 후보 {len(candidates)}개")
    return result
