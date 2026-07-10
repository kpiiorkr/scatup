import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from config import settings as settings_module  # noqa: E402


def test_env_strips_trailing_newline(monkeypatch):
    monkeypatch.setenv("SCATUP_TEST_SECRET", "sk-abc123\n")
    assert settings_module._env("SCATUP_TEST_SECRET") == "sk-abc123"


def test_env_strips_surrounding_whitespace_and_cr(monkeypatch):
    monkeypatch.setenv("SCATUP_TEST_SECRET", "  tok\r\n ")
    assert settings_module._env("SCATUP_TEST_SECRET") == "tok"


def test_env_missing_returns_empty(monkeypatch):
    monkeypatch.delenv("SCATUP_TEST_SECRET", raising=False)
    assert settings_module._env("SCATUP_TEST_SECRET") == ""
