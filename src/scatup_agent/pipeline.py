"""파이프라인 오케스트레이터 (rule: CLAUDE.md §5 Step 1~9, §10 게이트).

Step 1~9를 순서대로 실행한다. 각 단계 사이에서 판단 분기(§6)와
사람 개입 게이트(§10)를 확인하며, 게이트에 걸리면 즉시 중단하고
담당자에게 넘긴다. 발행은 절대 자동으로 하지 않는다 (§1-2).
"""
from __future__ import annotations

from .models.schemas import PipelineContext, TriggerType
from .collectors import keyword_expander, naver_collector, youtube_collector
from .processing import refiner, insight as insight_step
from .content import planner, rag, draft_generator
from .compliance import medical_law
from .output import deliverer, validators
from .decision import branches
from .exceptions.handlers import guard


def run_pipeline(trigger: TriggerType, seed_keywords: list[str]) -> PipelineContext:
    """전체 파이프라인 1회 실행."""
    ctx = PipelineContext(trigger=trigger, seed_keywords=seed_keywords)

    # Step 1 · 키워드 확장
    with guard(ctx, step="Step 1 키워드 확장"):
        ctx.expanded_keywords = keyword_expander.expand(ctx.seed_keywords)

    # Step 2 · 네이버 수집
    with guard(ctx, step="Step 2 네이버 수집"):
        ctx.collected += naver_collector.collect(ctx.expanded_keywords)

    # Step 3 · 유튜브 수집 (쿼터 절약 규칙 준수)
    with guard(ctx, step="Step 3 유튜브 수집"):
        ctx.collected += youtube_collector.collect(ctx.expanded_keywords)

    # 판단 분기: 데이터 부족 (§6)
    if branches.is_data_insufficient(ctx):
        branches.handle_data_insufficient(ctx)
        if ctx.halted:
            return _finish(ctx)

    # Step 4 · 데이터 정제 (관련성 스코어링)
    with guard(ctx, step="Step 4 데이터 정제"):
        ctx.collected = refiner.score_and_refine(ctx.collected)

    # Step 5 · 인사이트 도출
    with guard(ctx, step="Step 5 인사이트 도출"):
        ctx.insight = insight_step.derive(ctx.collected)

    # Step 6 · 콘텐츠 기획 (SEO/목차/톤앤매너)
    with guard(ctx, step="Step 6 콘텐츠 기획"):
        plan = planner.plan(ctx.insight)

    # Step 7 · RAG 근거 검색
    with guard(ctx, step="Step 7 RAG 근거 검색"):
        evidence = rag.search_evidence(plan)
    # 판단 분기: 근거 부족 (§6)
    if branches.is_evidence_missing(evidence):
        branches.handle_evidence_missing(ctx)
        return _finish(ctx)

    # Step 8 · 초안 생성 (제목 3안 + 본문 + 해시태그)
    with guard(ctx, step="Step 8 초안 생성"):
        ctx.draft = draft_generator.generate(plan, evidence)

    # Step 9 · 의료법 준수 필터링 (필수 게이트, 건너뛸 수 없음)
    ctx.draft = medical_law.review(ctx.draft)  # 내부에서 fail-safe 처리
    if medical_law.requires_human(ctx.draft):
        ctx.halt("의료법 2단계(애매)/오정보/fail-safe → 담당자 판단 필요, 자동 발행 차단")
        return _finish(ctx)

    # 출력 검증 (팩트체크·브랜드보이스·저작권 유사도)
    validators.validate_output(ctx)

    return _finish(ctx)


def _finish(ctx: PipelineContext) -> PipelineContext:
    """산출물 전달 (rule §9). 발행이 아니라 '검수 대기' 등록까지만 수행."""
    deliverer.deliver(ctx)
    return ctx
