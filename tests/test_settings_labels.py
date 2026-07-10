import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from config.settings import settings  # noqa: E402


def test_label_constants_exact_values():
    assert settings.label_draft == "scatup:draft"
    assert settings.label_trigger_scheduled == "trigger:scheduled"
    assert settings.label_trigger_rising == "trigger:rising"
    assert settings.label_cleared == "승인 대기"
    assert settings.label_attention == "🚨담당자 판단 필요"
