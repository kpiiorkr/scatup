"""Step 8 · 초안 생성 (rule §5 Step 8).

RAG 근거 기반으로 제목 3안 + 본문 + 해시태그를 생성한다.
ANTHROPIC_API_KEY 설정 시 Claude API 생성으로 교체 예정이며,
현재는 기획안·근거를 조립하는 템플릿 방식으로 동작한다.
"""
from __future__ import annotations

from ..models.schemas import BlogDraft, Metadata


def generate(plan: dict, evidence: list[dict]) -> BlogDraft:
    """기획안(plan) + 근거(evidence)로 블로그 초안을 조립한다."""
    # TODO(담당): ANTHROPIC_API_KEY 설정 시 Claude API 호출로 교체
    main_topic = plan.get("main_topic", "부모님 청력 관리 가이드")
    seo = plan.get("seo_keywords", [])

    titles = [
        main_topic,
        f"{seo[0]}, 부모님을 위해 알아봤습니다" if seo else "부모님 청력, 지금 점검해야 하는 이유",
        "부모님이 자꾸 되물으신다면 — 자녀가 먼저 챙기는 청력 관리",
    ]

    body = _build_body(plan, evidence)

    hashtags = ["#" + kw.replace(" ", "") for kw in seo[:5]] + ["#효도", "#부모님건강"]

    draft = BlogDraft(
        title_options=titles,
        body=body,
        hashtags=hashtags,
        evidence_links=[e["doc"] for e in evidence],
        metadata=Metadata(evidence_docs=[e["doc"] for e in evidence]),
    )
    print(f"[DRAFT] 제목 {len(titles)}안 + 본문 {len(body)}자 + 해시태그 {len(hashtags)}개 생성")
    return draft


def _build_body(plan: dict, evidence: list[dict]) -> str:
    outline = plan.get("outline", [])
    sentiments = plan.get("sentiment_points", [])
    sections: list[str] = []

    sections.append(
        "부모님과 통화할 때 같은 말을 두세 번 반복하게 되진 않으신가요? "
        "TV 볼륨이 예전보다 훌쩍 커졌다면, 그냥 지나칠 일이 아닐 수 있습니다. "
        "최근 커뮤니티와 영상에서도 부모님의 청력을 자녀가 먼저 챙기는 흐름이 뚜렷합니다."
    )

    if sentiments:
        bullet = "\n".join(f"- {s}" for s in sentiments)
        sections.append(f"### 요즘 사람들이 가장 궁금해하는 것\n{bullet}")

    for ev in evidence:
        doc_title = ev["doc"].rsplit(".", 1)[0].split("_", 1)[-1].replace("_", " ")
        sections.append(f"### {doc_title}\n{ev['snippet']}")

    sections.append(
        "커뮤니티에는 '보청기만 하면 완치된다'는 광고성 글도 보이지만, "
        "보청기는 치료 기기가 아니라 듣기를 돕는 재활 도구이며 효과는 개인차가 있습니다. "
        "정확한 검사와 전문가 상담이 항상 먼저입니다."
    )
    sections.append(
        "가격이 부담된다면 청각장애 등록 시 국민건강보험의 보청기 급여(5년 1회)를 "
        "활용할 수 있습니다. 기준은 바뀔 수 있으니 국민건강보험공단(1577-1000)에서 "
        "최신 조건을 꼭 확인하세요. 가장 좋은 효도는 '다시 잘 들리는 일상'을 선물하는 일입니다."
    )

    outline_block = "\n".join(f"{i}. {sec}" for i, sec in enumerate(outline, 1))
    return f"## 목차\n{outline_block}\n\n" + "\n\n".join(sections)
