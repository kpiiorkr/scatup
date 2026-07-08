"""Step 7 · RAG 근거 검색 (rule §5 Step 7).

난청 지식베이스(data/knowledge_base/ 5종 문서)에서 근거 문서를 검색한다.
근거 미확보 시 초안 생성을 보류하고 '근거 부족' 플래그를 부착한다(§6).
현재는 키워드 매칭 검색이며, 추후 임베딩 검색으로 교체 가능.
"""
from __future__ import annotations

from pathlib import Path

_KB_DIR = Path(__file__).resolve().parents[3] / "data" / "knowledge_base"
_TOP_K = 3


def search_evidence(plan: dict) -> list[dict]:
    """기획안의 주제·SEO 키워드와 겹치는 지식베이스 문서를 찾는다.

    반환: [{"doc": 문서명, "snippet": 발췌, "score": 매칭 점수}, ...]
    """
    if not _KB_DIR.exists():
        return []  # 근거 부족 → §6 분기에서 처리

    query_terms = _query_terms(plan)
    scored: list[dict] = []
    for doc_path in sorted(_KB_DIR.glob("*.md")):
        text = doc_path.read_text(encoding="utf-8")
        score = sum(text.count(term) for term in query_terms)
        if score <= 0:
            continue
        scored.append(
            {
                "doc": doc_path.name,
                "snippet": _best_snippet(text, query_terms),
                "score": score,
            }
        )

    top = sorted(scored, key=lambda e: e["score"], reverse=True)[:_TOP_K]
    print(f"[RAG] 지식베이스 {len(list(_KB_DIR.glob('*.md')))}종 중 근거 문서 {len(top)}건 확보")
    return top


def _query_terms(plan: dict) -> list[str]:
    terms = list(plan.get("seo_keywords", []))
    # 복합 키워드는 공백 단위로도 쪼개 매칭율을 높인다 (예: "보청기 정부지원")
    for kw in list(terms):
        terms += kw.split()
    return list(dict.fromkeys(t for t in terms if len(t) >= 2))


def _best_snippet(text: str, terms: list[str], max_len: int = 300) -> str:
    """검색어가 가장 많이 포함된 문단을 문장 단위로 발췌한다."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    best = max(paragraphs, key=lambda p: sum(p.count(t) for t in terms))
    if len(best) <= max_len:
        return best
    cut = best[:max_len]
    # 문장이 중간에 잘리지 않도록 마지막 마침표까지만 사용
    last_period = cut.rfind("다.")
    return cut[: last_period + 2] if last_period > 0 else cut
