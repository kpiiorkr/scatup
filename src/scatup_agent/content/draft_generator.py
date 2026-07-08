"""Step 8 · 초안 생성 (rule §5 Step 8).

Claude + RAG 근거 기반으로 제목 3안 + 본문 + 해시태그를 생성한다.
"""
from __future__ import annotations

from ..models.schemas import BlogDraft, Metadata


def generate(plan: dict, evidence: list[dict]) -> BlogDraft:
    """TODO(담당): Claude API 호출로 초안 생성."""
    return BlogDraft(
        title_options=[],
        body="",
        hashtags=[],
        evidence_links=[e.get("doc", "") for e in evidence],
        metadata=Metadata(evidence_docs=[e.get("doc", "") for e in evidence]),
    )
