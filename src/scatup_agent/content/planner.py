"""Step 6 · 콘텐츠 기획 (rule §5 Step 6).

SEO 키워드, 목차, 톤앤매너를 설계한다. 타겟 고객 기준(§0) 반영.
데이터 신호(급상승 토픽·감성 포인트)에 따라 콘텐츠 앵글을 선택해,
매 주기 같은 글이 반복되지 않도록 한다.
"""
from __future__ import annotations

import random

from config.settings import settings

from ..models.schemas import TrendInsight

# 콘텐츠 앵글 카탈로그 — 각 앵글은 서로 다른 주제·목차를 가진다.
# keywords: 이 앵글을 트리거하는 데이터 신호 / main_topic: 어법에 맞는 제목.
_ANGLES = [
    {
        "id": "gov_support",
        "keywords": ("정부지원", "지원", "보조금", "가격", "비용", "부담"),
        "main_topic": "부모님 보청기 정부지원, 신청 자격부터 절차까지 총정리",
        "outline": [
            "들어가며: 보청기 가격, 부담되시죠",
            "정부지원 대상: 누가 받을 수 있나",
            "지원 내용과 한도, 이렇게 됩니다",
            "신청 절차 한눈에 정리",
            "신청 전 꼭 확인할 점",
        ],
    },
    {
        "id": "self_check",
        "keywords": ("난청", "자가", "검사", "되물", "방치", "신호"),
        "main_topic": "부모님 난청, 이런 신호면 청력 검사받으세요 — 자가 점검 가이드",
        "outline": [
            "들어가며: 부모님, 요즘 자꾸 되물으시나요",
            "이런 신호라면 난청 자가 점검",
            "난청의 원인과 유형 이해하기",
            "방치하면 안 되는 이유",
            "청력 검사, 이렇게 시작하세요",
        ],
    },
    {
        "id": "dementia",
        "keywords": ("치매", "인지", "뇌"),
        "main_topic": "난청을 방치하면 치매 위험이? 부모님 청력이 뇌 건강인 이유",
        "outline": [
            "들어가며: 안 들리는 게 뇌 건강 문제라면",
            "난청과 치매, 무슨 관계일까 (근거 기반)",
            "왜 난청이 인지 저하로 이어질까",
            "보청기와 인지 건강",
            "가족이 지금 할 수 있는 일",
        ],
    },
    {
        "id": "tinnitus",
        "keywords": ("이명", "귀울림", "삐"),
        "main_topic": "부모님 이명(귀울림), 원인부터 일상 관리법까지",
        "outline": [
            "들어가며: 부모님 귀에서 소리가 난다면",
            "이명이란 무엇인가",
            "이명의 주요 원인",
            "일상에서의 관리법",
            "병원을 찾아야 할 때",
        ],
    },
    {
        "id": "hearing_aid_choice",
        "keywords": ("보청기", "종류", "선택", "적응", "가격비교"),
        "main_topic": "부모님 첫 보청기, 후회 없이 고르는 종류·선택 가이드",
        "outline": [
            "들어가며: 첫 보청기, 무엇부터 봐야 할까",
            "보청기의 종류",
            "우리 부모님께 맞는 선택 기준",
            "착용 후 적응 관리",
            "비용과 지원 확인하기",
        ],
    },
]


# 앵글별 핵심 근거 문서 (RAG가 전체 내용을 제공해 정확한 용어·사실로 작성하게 함)
_ANGLE_DOCS = {
    "gov_support": ("03_보청기_정부지원_제도.md",),
    "self_check": ("01_난청의_이해.md",),
    "dementia": ("05_난청과_치매의_연관성.md",),
    "tinnitus": ("04_이명의_원인과_관리.md",),
    "hearing_aid_choice": ("02_보청기의_종류와_선택.md",),
}


def _select_angle(insight: TrendInsight) -> dict:
    """급상승 토픽에 걸리는 앵글 중 하나를 무작위로 고른다.

    감성 포인트는 매 주기 거의 고정(정부지원·가격 상시 언급)이라 제외하고,
    변동성 있는 급상승 토픽만 본다. 키워드 '개수'로 점수화하면 시드에 박힌
    '보청기 정부지원'·'보청기 가격' 때문에 특정 앵글로 쏠리므로, 개수 대신
    '트렌드에 한 번이라도 걸린 앵글'을 후보로 두고 동등 확률로 골라 회전시킨다.
    """
    signal = " ".join(insight.rising_topics)
    matched = [angle for angle in _ANGLES if any(kw in signal for kw in angle["keywords"])]
    return random.choice(matched or _ANGLES)


def plan(insight: TrendInsight | None) -> dict:
    """인사이트를 타겟 고객(40~50대 자녀 세대) 관점의 기획안으로 변환한다."""
    if insight is None:
        insight = TrendInsight()

    angle = _select_angle(insight)
    seo_keywords = insight.rising_topics[:5] or ["난청", "보청기"]

    result = {
        "angle": angle["id"],
        "main_topic": angle["main_topic"],
        "seo_keywords": seo_keywords,
        "primary_docs": list(_ANGLE_DOCS.get(angle["id"], [])),
        "outline": angle["outline"],
        "tone": (
            f"타겟({settings.target_audience})에게 말 걸듯 따뜻하고 차분한 정보 전달. "
            "치료 효과 단정·과장 표현 금지, 근거 중심 서술."
        ),
        "sentiment_points": insight.sentiment_points,
    }
    print(f"[PLAN] 앵글: {angle['id']} / 주제: {angle['main_topic']} / SEO: {seo_keywords}")
    return result
