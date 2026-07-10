import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scatup_agent.models.schemas import (  # noqa: E402
    BlogDraft, Metadata, PipelineContext, TrendInsight, TriggerType,
)
from scatup_agent.output import deliverer  # noqa: E402
from scatup_agent.output import github_issues  # noqa: E402


def _ctx(halted=False, trigger=TriggerType.SCHEDULED):
    ctx = PipelineContext(trigger=trigger, seed_keywords=["난청"])
    ctx.insight = TrendInsight(rising_topics=["난청"], sentiment_points=[], topic_candidates=[])
    ctx.draft = BlogDraft(
        title_options=["난청 방치 위험", "제목2", "제목3"],
        body="본문입니다.",
        hashtags=["#난청"],
        evidence_links=["01_난청의_이해.md"],
        metadata=Metadata(),
    )
    ctx.halted = halted
    return ctx


def test_deliver_creates_issue_with_cleared_labels(monkeypatch):
    captured = {}
    monkeypatch.setattr(github_issues, "enabled", lambda: True)
    monkeypatch.setattr(github_issues, "is_duplicate", lambda rep: False)

    def fake_create(title, body, labels):
        captured.update(title=title, body=body, labels=labels)
        return "https://github.com/kpiiorkr/scatup/issues/7"

    monkeypatch.setattr(github_issues, "create_issue", fake_create)
    deliverer.deliver(_ctx(halted=False, trigger=TriggerType.SCHEDULED))

    assert captured["title"] == "[초안 검수] 난청 방치 위험"
    assert captured["labels"] == ["scatup:draft", "trigger:scheduled", "승인 대기"]
    assert "검수 체크리스트" in captured["body"]
    assert "발행 승인" in captured["body"]


def test_deliver_attention_and_rising_labels(monkeypatch):
    captured = {}
    monkeypatch.setattr(github_issues, "enabled", lambda: True)
    monkeypatch.setattr(github_issues, "is_duplicate", lambda rep: False)
    monkeypatch.setattr(github_issues, "create_issue",
                        lambda title, body, labels: captured.update(labels=labels) or "url")
    deliverer.deliver(_ctx(halted=True, trigger=TriggerType.RISING_KEYWORD))
    assert captured["labels"] == ["scatup:draft", "trigger:rising", "🚨담당자 판단 필요"]


def test_deliver_dedup_skips_creation(monkeypatch):
    calls = []
    monkeypatch.setattr(github_issues, "enabled", lambda: True)
    monkeypatch.setattr(github_issues, "is_duplicate", lambda rep: True)
    monkeypatch.setattr(github_issues, "create_issue",
                        lambda *a, **k: calls.append(1) or "url")
    deliverer.deliver(_ctx())
    assert calls == []  # 생성 호출 안 됨


def test_deliver_console_fallback_when_disabled(monkeypatch):
    calls = []
    monkeypatch.setattr(github_issues, "enabled", lambda: False)
    monkeypatch.setattr(github_issues, "create_issue",
                        lambda *a, **k: calls.append(1) or "url")
    deliverer.deliver(_ctx())  # 예외 없이 통과
    assert calls == []


def test_deliver_raises_on_api_failure(monkeypatch):
    monkeypatch.setattr(github_issues, "enabled", lambda: True)
    monkeypatch.setattr(github_issues, "is_duplicate", lambda rep: False)
    monkeypatch.setattr(github_issues, "create_issue", lambda *a, **k: None)
    with pytest.raises(RuntimeError):
        deliverer.deliver(_ctx())
