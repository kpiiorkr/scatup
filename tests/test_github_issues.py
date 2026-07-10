import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scatup_agent.output import github_issues as gh  # noqa: E402


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"status {self.status_code}")


def _enable(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "tok")
    monkeypatch.setenv("GITHUB_REPOSITORY", "kpiiorkr/scatup")


def test_enabled_reflects_env(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert gh.enabled() is False
    _enable(monkeypatch)
    assert gh.enabled() is True


def test_draft_issue_title_prefix():
    assert gh.draft_issue_title("난청과 치매") == "[초안 검수] 난청과 치매"
    assert gh.draft_issue_title("난청과 치매", "2026-07-10") == "[초안 검수] (2026-07-10) 난청과 치매"


def test_norm_title_strips_prefix_and_date():
    assert gh._norm_title("[초안 검수] (2026-07-10) 난청 방치 위험") == "난청방치위험"
    assert gh._norm_title("[초안 검수] 난청 방치 위험") == "난청방치위험"


def test_create_issue_disabled_returns_none(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert gh.create_issue("t", "b", ["l"]) is None


def test_create_issue_posts_payload(monkeypatch):
    _enable(monkeypatch)
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return FakeResp({"html_url": "https://github.com/kpiiorkr/scatup/issues/1"})

    monkeypatch.setattr(gh.requests, "post", fake_post)
    url = gh.create_issue("[초안 검수] 제목", "본문", ["scatup:draft", "승인 대기"])
    assert url == "https://github.com/kpiiorkr/scatup/issues/1"
    assert captured["url"].endswith("/repos/kpiiorkr/scatup/issues")
    assert captured["json"] == {"title": "[초안 검수] 제목", "body": "본문",
                                "labels": ["scatup:draft", "승인 대기"]}
    assert captured["headers"]["Authorization"] == "Bearer tok"


def test_create_issue_api_error_returns_none(monkeypatch):
    _enable(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResp({}, status=422)

    monkeypatch.setattr(gh.requests, "post", fake_post)
    assert gh.create_issue("t", "b", ["l"]) is None


def test_open_draft_titles_normalizes_and_filters_pr(monkeypatch):
    _enable(monkeypatch)

    def fake_get(url, headers=None, params=None, timeout=None):
        return FakeResp([
            {"title": "[초안 검수] (2026-07-10) 난청 방치 위험"},
            {"title": "[초안 검수] 이명 관리법", "pull_request": {"url": "x"}},
        ])

    monkeypatch.setattr(gh.requests, "get", fake_get)
    titles = gh.open_draft_titles()
    assert "난청방치위험" in titles  # 날짜 접두가 있어도 주제로 정규화
    assert all("이명" not in t for t in titles)  # PR 제외


def test_is_duplicate_uses_normalized_titles(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(gh, "open_draft_titles", lambda: {"난청방치위험"})
    assert gh.is_duplicate("난청 방치 위험") is True
    assert gh.is_duplicate("완전히 다른 제목") is False


def test_days_since_last_scheduled(monkeypatch):
    _enable(monkeypatch)
    created = (datetime.now(timezone.utc) - timedelta(days=5, hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def fake_get(url, headers=None, params=None, timeout=None):
        return FakeResp([{"created_at": created}])

    monkeypatch.setattr(gh.requests, "get", fake_get)
    assert gh.days_since_last_scheduled() == 5


def test_days_since_last_scheduled_none_when_empty(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(gh.requests, "get", lambda *a, **k: FakeResp([]))
    assert gh.days_since_last_scheduled() is None
