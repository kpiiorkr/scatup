"""엔트리 포인트 (rule: CLAUDE.md 전체).

정기/이벤트 트리거를 확인해 파이프라인을 실행한다.
뼈대 상태에서도 `python -m scatup_agent.main` 으로 흐름을 확인할 수 있다.
"""
from __future__ import annotations

from .models.schemas import TriggerType
from .trigger import scheduler
from .pipeline import run_pipeline


def main() -> None:
    trigger = scheduler.detect_event_trigger() or TriggerType.SCHEDULED
    seed_keywords = ["난청", "보청기", "치매"]  # TODO: 시드 키워드 소스 연동

    print(f"[START] trigger={trigger.value}, seeds={seed_keywords}")
    ctx = run_pipeline(trigger, seed_keywords)

    if ctx.halted:
        print(f"[HALTED] 담당자 판단 필요 → {ctx.halt_reason}")
    else:
        print("[DONE] 초안 생성 완료 → 검수 대기 등록 (발행은 사람이 직접 수행)")


if __name__ == "__main__":
    main()
