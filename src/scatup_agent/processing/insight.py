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

    # 소재 후보: 상위 토픽 × 타겟 고객(40~50대 자녀 세대) 관점
    candidates = [
        f"부모님 {rising[0]} 신청 방법 총정리" if rising else "부모님 청력 관리 가이드",
        "부모님이 자꾸 되물으신다면? 난청 자가 점검 신호 5가지",
        "보청기 가격, 부담 줄이는 정부지원 제도 활용법",
    ]

    result = TrendInsight(
        rising_topics=rising,
        sentiment_points=sentiments,
        topic_candidates=candidates,
    )
    print(f"[INSIGHT] 급상승 토픽 {len(rising)}개: {rising}")
    print(f"[INSIGHT] 감성 포인트 {len(sentiments)}개, 소재 후보 {len(candidates)}개")
    return result
