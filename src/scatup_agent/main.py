"""엔트리 포인트 (rule: CLAUDE.md 전체).

매일 실행하되, 급상승 감지 시 즉시 초안을 만들고, 그 외에는 정기 주기(§2, 3일)가
도래했을 때만 초안을 생성한다. '마지막 정기 실행일'은 최근 trigger:scheduled
Issue 생성일로 역산한다(파일 상태 없이 Issue를 단일 창구로 사용).
"""
from __future__ import annotations

import os

from config.settings import settings

from .models.schemas import TriggerType
from .trigger import scheduler
from .pipeline import run_pipeline
from .processing import keyword_miner
from .output import github_issues


def _resolve_trigger() -> TriggerType | None:
    """오늘 사용할 트리거를 결정한다. None이면 오늘은 초안 생성 없이 종료.

    - 급상승 감지 → 즉시 실행(RISING_KEYWORD).
    - FORCE_RUN=true (수동 강제 실행) → 게이트 무시하고 SCHEDULED.
    - 급상승 없음 → 최근 정기 Issue가 run_interval_days 경과했을 때만 SCHEDULED.
    - 로컬(GitHub 미연동) → 게이트 건너뛰고 항상 SCHEDULED (개발 편의).
    """
    event = scheduler.detect_event_trigger()
    if event is not None:
        return event
    if os.getenv("FORCE_RUN", "").lower() == "true":
        print("[FORCE] 강제 실행 요청 → 정기 주기 게이트 무시")
        return TriggerType.SCHEDULED
    if github_issues.enabled():
        days = github_issues.days_since_last_scheduled()
        if days is not None and days < settings.run_interval_days:
            return None
    return TriggerType.SCHEDULED


def main() -> None:
    trigger = _resolve_trigger()
    if trigger is None:
        print(
            f"[SKIP] 급상승 없음 & 마지막 정기 실행 {settings.run_interval_days}일 미경과 "
            "→ 오늘은 초안 생성 안 함"
        )
        return

    # 기본 시드 + 이전 주기에 수집 원문에서 발굴한 신규 키워드 (§5 Step 1 보강)
    seed_keywords = list(dict.fromkeys(list(settings.seed_keywords) + keyword_miner.recall()))

    print(f"[START] trigger={trigger.value}, seeds={seed_keywords}")
    ctx = run_pipeline(trigger, seed_keywords)

    if ctx.halted and ctx.draft:
        print(f"[HALTED] 초안은 생성 완료, 담당자 검수 대기 → {ctx.halt_reason}")
    elif ctx.halted:
        print(f"[HALTED] 담당자 판단 필요 → {ctx.halt_reason}")
    else:
        print("[DONE] 초안 생성 완료 → 검수 대기 등록 (발행은 사람이 직접 수행)")


if __name__ == "__main__":
    main()
