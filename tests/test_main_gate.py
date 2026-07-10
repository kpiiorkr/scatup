import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scatup_agent import main  # noqa: E402
from scatup_agent.models.schemas import TriggerType  # noqa: E402
from scatup_agent.trigger import scheduler  # noqa: E402
from scatup_agent.output import github_issues  # noqa: E402


def test_rising_event_takes_priority(monkeypatch):
    monkeypatch.setattr(scheduler, "detect_event_trigger", lambda: TriggerType.RISING_KEYWORD)
    assert main._resolve_trigger() == TriggerType.RISING_KEYWORD


def test_scheduled_when_github_disabled(monkeypatch):
    monkeypatch.setattr(scheduler, "detect_event_trigger", lambda: None)
    monkeypatch.setattr(github_issues, "enabled", lambda: False)
    assert main._resolve_trigger() == TriggerType.SCHEDULED


def test_skip_when_within_interval(monkeypatch):
    monkeypatch.setattr(scheduler, "detect_event_trigger", lambda: None)
    monkeypatch.setattr(github_issues, "enabled", lambda: True)
    monkeypatch.setattr(github_issues, "days_since_last_scheduled", lambda: 1)
    assert main._resolve_trigger() is None


def test_scheduled_when_interval_elapsed(monkeypatch):
    monkeypatch.setattr(scheduler, "detect_event_trigger", lambda: None)
    monkeypatch.setattr(github_issues, "enabled", lambda: True)
    monkeypatch.setattr(github_issues, "days_since_last_scheduled", lambda: 5)
    assert main._resolve_trigger() == TriggerType.SCHEDULED


def test_scheduled_when_no_history(monkeypatch):
    monkeypatch.setattr(scheduler, "detect_event_trigger", lambda: None)
    monkeypatch.setattr(github_issues, "enabled", lambda: True)
    monkeypatch.setattr(github_issues, "days_since_last_scheduled", lambda: None)
    assert main._resolve_trigger() == TriggerType.SCHEDULED
