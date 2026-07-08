"""예외 처리 (rule §8).

각 Step을 감싸 API 쿼터 초과/키 만료/파서 오류 등을 표준 방식으로 처리한다.
"""
from __future__ import annotations

from contextlib import contextmanager

from ..models.schemas import PipelineContext


@contextmanager
def guard(ctx: PipelineContext, step: str):
    """Step 실행을 감싸는 컨텍스트 매니저.

    예외 발생 시 해당 소스 skip + 담당자 알림 방식으로 처리한다(§8).
    치명적 예외는 파이프라인을 중단(halt)시킨다.
    """
    try:
        yield
    except NotImplementedError:
        # 아직 구현 전인 stub → 뼈대 실행 시엔 통과
        pass
    except Exception as exc:  # noqa: BLE001 - 팀에서 세분화 예정
        # TODO(담당): 예외 유형별 세분화 (쿼터 초과/키 만료/파서 오류 등)
        ctx.halt(f"{step} 예외: {exc!r} → 해당 소스 skip + 담당자 알림")
