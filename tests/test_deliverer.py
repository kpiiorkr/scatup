import re
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


@pytest.fixture(autouse=True)
def _tmp_outputs(tmp_path, monkeypatch):
    """deliver() 가 실제 data/outputs 를 오염시키지 않도록 임시 폴더로 리다이렉트한다."""
    monkeypatch.setattr(deliverer, "OUTPUTS_DIR", tmp_path / "outputs")


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

    assert re.match(r"\[초안 검수\] \(\d{4}-\d{2}-\d{2}\) 난청 방치 위험$", captured["title"])
    assert captured["labels"] == ["scatup:draft", "trigger:scheduled", "승인 대기"]
    assert "검수 체크리스트" in captured["body"]
    assert "발행 승인" in captured["body"]
    assert "검수 방법" in captured["body"]
    assert "docs/review-guide.md" in captured["body"]
    assert "생성일" in captured["body"]
    assert "(KST)" in captured["body"]


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


def test_deliver_persists_run_files_for_dashboard(monkeypatch):
    """대시보드(build_dashboard.py)가 읽는 run_*/draft.md·report.md 를 남기는지 확인."""
    monkeypatch.setattr(github_issues, "enabled", lambda: False)
    deliverer.deliver(_ctx())

    runs = list(deliverer.OUTPUTS_DIR.glob("run_*"))
    assert len(runs) == 1
    assert re.match(r"run_\d{8}_\d{6}$", runs[0].name)
    draft_md = (runs[0] / "draft.md").read_text(encoding="utf-8")
    report_md = (runs[0] / "report.md").read_text(encoding="utf-8")
    assert "블로그 초안" in draft_md and "제목 3안" in draft_md
    assert "트렌드 인사이트 리포트" in report_md
