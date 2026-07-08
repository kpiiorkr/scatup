"""산출물 전달 (rule §9-2, §10).

담당자 이메일/슬랙 알림 → 대시보드 '검수 대기' 반영 → CMS 초안함 저장.
발행은 절대 자동으로 하지 않는다. 항상 사람이 직접 수행한다.
"""
from __future__ import annotations

from ..models.schemas import PipelineContext


def deliver(ctx: PipelineContext) -> None:
    """TODO(담당): 슬랙/이메일 알림 + 대시보드 + CMS 초안함 저장."""
    if ctx.halted:
        _notify(f"[담당자 판단 필요] {ctx.halt_reason}")
        return
    # TODO: CMS 초안함 저장 + '검수 대기' 등록
    _notify("[검수 대기] 신규 블로그 초안이 등록되었습니다.")


def _notify(message: str) -> None:
    """TODO(담당): Slack webhook / 이메일 연동."""
    print(f"[NOTIFY] {message}")
