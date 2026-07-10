import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scatup_agent.content import draft_generator as dg  # noqa: E402


def test_strip_english_removes_capitalized_words():
    out = dg._strip_english("안전 위험 증가: Emergency 상황(예: Consensus) 시 경보음")
    assert "Emergency" not in out
    assert "Consensus" not in out
    assert "안전 위험 증가" in out


def test_strip_english_removes_lowercase_words():
    out = dg._strip_english("소리 치료(sound therapy)를 병행한다")
    assert "sound" not in out and "therapy" not in out
    assert "소리 치료" in out


def test_strip_english_preserves_abbreviations_and_units():
    out = dg._strip_english("귀걸이형 BTE, 오픈형 RIC, 귓속형 CIC, TV 볼륨, 순음 30 dB")
    for keep in ("BTE", "RIC", "CIC", "TV", "dB"):
        assert keep in out
