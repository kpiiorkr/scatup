"""파이프라인 뼈대 스모크 테스트.

각 Step이 stub 상태여도 파이프라인이 예외 없이 끝까지 흐르는지 확인한다.
"""
import sys
from pathlib import Path

# src 경로 등록 (뼈대 단계용; 추후 패키지 설치로 대체 가능)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scatup_agent.models.schemas import TriggerType  # noqa: E402
from scatup_agent.pipeline import run_pipeline        # noqa: E402


def test_pipeline_runs_without_error():
    ctx = run_pipeline(TriggerType.SCHEDULED, ["난청", "보청기"])
    assert ctx is not None
    # 뼈대 상태에서는 데이터 부족으로 halt 되는 것이 정상 흐름
    assert isinstance(ctx.halted, bool)
