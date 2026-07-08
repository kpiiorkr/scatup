"""산출물 전달 (rule §9-2, §10).

담당자 이메일/슬랙 알림 → 대시보드 '검수 대기' 반영 → CMS 초안함 저장.
발행은 절대 자동으로 하지 않는다. 항상 사람이 직접 수행한다.
현재 CMS 대신 data/outputs/ 에 초안·리포트 파일을 저장한다.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..models.schemas import PipelineContext

_OUTPUT_DIR = Path(__file__).resolve().parents[3] / "data" / "outputs"


def deliver(ctx: PipelineContext) -> None:
    """산출물 저장 + 담당자 알림. '검수 대기' 등록까지만 수행한다."""
    out_dir = None
    if ctx.draft and (ctx.draft.title_options or ctx.draft.body):
        out_dir = _save_outputs(ctx)

    if ctx.halted:
        _notify(f"[담당자 판단 필요] {ctx.halt_reason}")
    else:
        _notify("[검수 대기] 신규 블로그 초안이 등록되었습니다.")

    if out_dir:
        print(f"[OUTPUT] 초안·리포트 저장 완료 → {out_dir}")


def _save_outputs(ctx: PipelineContext) -> Path:
    """블로그 초안 + 트렌드 리포트를 검수용 파일로 저장한다 (rule §9-1)."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = _OUTPUT_DIR / f"run_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "draft.md").write_text(_render_draft(ctx), encoding="utf-8")
    (out_dir / "report.md").write_text(_render_report(ctx), encoding="utf-8")
    return out_dir


def _render_draft(ctx: PipelineContext) -> str:
    d = ctx.draft
    status = d.metadata.compliance_status.value if d.metadata.compliance_status else "미검수"
    flags = ", ".join(f.value for f in d.metadata.sensitivity_flags) or "없음"
    titles = "\n".join(f"{i}. {t}" for i, t in enumerate(d.title_options, 1))
    lines = [
        "# 블로그 초안 (검수 대기)",
        "",
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
        f"- 실행 시각: {ctx.created_at:%Y-%m-%d %H:%M}",
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
        lines += ["", f"## ⚠️ 담당자 확인 필요", f"- 사유: {ctx.halt_reason}"]
    return "\n".join(lines)


def _notify(message: str) -> None:
    """TODO(담당): Slack webhook / 이메일 연동 (settings.slack_webhook_url)."""
    print(f"[NOTIFY] {message}")
