"""산출물 전달 (rule §9-2, §10).

블로그 초안을 GitHub Issue '검수 대기'로 등록한다. 발행은 절대 자동으로 하지 않으며,
항상 사람이 직접 수행한다(§1-2). 토큰이 없는 로컬 실행에서는 콘솔로 폴백한다.
"""
from __future__ import annotations

from datetime import timezone, timedelta

from ..models.schemas import PipelineContext, TriggerType
from . import github_issues
from config.settings import settings

_KST = timezone(timedelta(hours=9))


def _kst(ctx: PipelineContext):
    """생성 시각을 KST(aware)로 변환한다. created_at은 실행 환경(Actions=UTC) 기준
    naive이므로 UTC로 간주해 KST로 바꾼다."""
    return ctx.created_at.replace(tzinfo=timezone.utc).astimezone(_KST)

_CHECKLIST = (
    "## 검수 체크리스트 (rule §10)\n"
    "- [ ] 사실 확인 — 본문의 수치·근거가 정확한지 확인\n"
    "- [ ] 표현 점검 — 40~50대 타깃에 맞는 말투·브랜드 톤인지 확인\n"
    "- [ ] 발행 승인 — 담당자가 확인한 뒤 직접 발행\n"
)

_REVIEW_HOWTO = (
    "## 검수 방법\n"
    "- **승인:** 오른쪽 `Labels`에 `승인` 추가 → `Close as completed` → 담당자가 직접 발행\n"
    "- **반려:** 사유를 댓글로 남기고 `Labels`에 `반려` 추가 → `Close as not planned`\n"
    "- 자세한 절차는 [검수 가이드]({guide})를 참고하세요.\n"
)


def deliver(ctx: PipelineContext) -> None:
    """초안을 검수 대기 Issue로 등록한다. 초안이 없으면 콘솔 알림만 수행한다."""
    if not (ctx.draft and (ctx.draft.title_options or ctx.draft.body)):
        # 초안 생성 전 게이트에 걸린 경우(데이터/근거 부족 등): 콘솔 알림만 (Actions 로그로 확인)
        if ctx.halted:
            _notify(f"[담당자 판단 필요] {ctx.halt_reason}")
        return

    rep_title = ctx.draft.title_options[0] if ctx.draft.title_options else "(제목 없음)"
    title = github_issues.draft_issue_title(rep_title, _kst(ctx).strftime("%Y-%m-%d"))
    body = _issue_body(ctx)
    labels = _labels(ctx)

    if not github_issues.enabled():
        _notify("[검수 대기] 신규 블로그 초안 (로컬: GitHub 미연동 → 콘솔 출력)")
        print(body)
        return

    if github_issues.is_duplicate(rep_title):
        print("[DEDUP] 동일 제목 초안 Issue가 이미 열려 있어 생성을 생략합니다")
        return

    url = github_issues.create_issue(title, body, labels)
    if url is None:
        print(body)  # 유실 방지: 실패 시 본문을 로그에 남긴다
        raise RuntimeError("GitHub Issue 생성 실패 (토큰은 있으나 API 오류)")
    print(f"[ISSUE] 검수 대기 Issue 생성 → {url}")


def _labels(ctx: PipelineContext) -> list[str]:
    labels = [settings.label_draft]
    labels.append(
        settings.label_trigger_scheduled
        if ctx.trigger == TriggerType.SCHEDULED
        else settings.label_trigger_rising
    )
    labels.append(settings.label_attention if ctx.halted else settings.label_cleared)
    return labels


def _issue_body(ctx: PipelineContext) -> str:
    howto = _REVIEW_HOWTO.format(guide=github_issues.repo_url("blob/main/docs/review-guide.md"))
    return "\n\n---\n\n".join([_render_draft(ctx), _render_report(ctx), _CHECKLIST, howto])


def _render_draft(ctx: PipelineContext) -> str:
    d = ctx.draft
    status = d.metadata.compliance_status.value if d.metadata.compliance_status else "미검수"
    flags = ", ".join(f.value for f in d.metadata.sensitivity_flags) or "없음"
    titles = "\n".join(f"{i}. {t}" for i, t in enumerate(d.title_options, 1))
    lines = [
        "# 블로그 초안 (검수 대기)",
        "",
        f"> 📅 생성일: {_kst(ctx):%Y-%m-%d %H:%M} (KST) · 트리거: {ctx.trigger.value}",
        f"> 상태: **{status}** · 민감도 플래그: {flags} · 저작권 유사도: {d.metadata.similarity_score:.2f}",
        "> ⚠️ 발행은 담당자 승인 후 직접 수행합니다. 자동 발행 금지 (rule §1-2).",
        "",
        "## 제목 3안",
        titles,
        "",
        "## 본문",
        d.body,
        "",
        "## 해시태그",
        " ".join(d.hashtags),
        "",
        "## 근거 문서",
        "\n".join(f"- {link}" for link in d.evidence_links) or "- (없음)",
    ]
    return "\n".join(lines)


def _render_report(ctx: PipelineContext) -> str:
    ins = ctx.insight
    lines = [
        "# 트렌드 인사이트 리포트",
        "",
        f"- 실행 시각: {_kst(ctx):%Y-%m-%d %H:%M} (KST)",
        f"- 트리거: {ctx.trigger.value}",
        f"- 시드 키워드: {', '.join(ctx.seed_keywords)}",
        f"- 확장 키워드: {len(ctx.expanded_keywords)}개",
        f"- 수집·정제 자료: {len(ctx.collected)}건",
        "",
        "## 급상승 토픽",
        "\n".join(f"- {t}" for t in (ins.rising_topics if ins else [])) or "- (없음)",
        "",
        "## 감성 포인트",
        "\n".join(f"- {s}" for s in (ins.sentiment_points if ins else [])) or "- (없음)",
        "",
        "## 소재 후보",
        "\n".join(f"- {c}" for c in (ins.topic_candidates if ins else [])) or "- (없음)",
        "",
        "## 상위 수집 자료 (관련성순)",
    ]
    for it in ctx.collected[:10]:
        lines.append(
            f"- [{it.channel.value}] {it.title} (관련성 {it.relevance_score:.2f}, 조회 {it.view_count:,}) — {it.url}"
        )
    if ctx.halted:
        lines += ["", "## ⚠️ 담당자 확인 필요", f"- 사유: {ctx.halt_reason}"]
    return "\n".join(lines)


def _notify(message: str) -> None:
    print(f"[NOTIFY] {message}")
