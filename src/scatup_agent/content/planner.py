"""Step 6 · 콘텐츠 기획 (rule §5 Step 6).

SEO 키워드, 목차, 톤앤매너를 설계한다. 타겟 고객 기준(§0) 반영.
"""
from __future__ import annotations

from config.settings import settings

from ..models.schemas import TrendInsight


def plan(insight: TrendInsight | None) -> dict:
    """인사이트를 타겟 고객(40~50대 자녀 세대) 관점의 기획안으로 변환한다."""
    if insight is None:
        insight = TrendInsight()

    main_topic = (
        insight.topic_candidates[0]
        if insight.topic_candidates
        else "부모님 청력 관리 가이드"
    )
    seo_keywords = insight.rising_topics[:5] or ["난청", "보청기"]

    outline = [
        "들어가며: 부모님과의 대화, 요즘 어떠신가요",
        f"지금 많이 찾는 주제: {', '.join(seo_keywords[:3])}",
        "난청, 왜 방치하면 안 될까 (근거 기반)",
        "보청기 정부지원 제도, 이렇게 활용하세요",
        "마무리: 가장 좋은 효도는 '다시 잘 들리는 일상'",
    ]

    result = {
        "main_topic": main_topic,
        "seo_keywords": seo_keywords,
        "outline": outline,
        "tone": (
            f"타겟({settings.target_audience})에게 말 걸듯 따뜻하고 차분한 정보 전달. "
            "치료 효과 단정·과장 표현 금지, 근거 중심 서술."
        ),
        "sentiment_points": insight.sentiment_points,
    }
    print(f"[PLAN] 주제: {main_topic} / SEO 키워드: {seo_keywords}")
    return result
