import sys
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scatup_agent.compliance import law_api_client as law  # noqa: E402


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


def test_get_retries_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, params=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.ConnectTimeout("connect timed out")
        return FakeResp({"ok": True})

    monkeypatch.setattr(law.requests, "get", fake_get)
    monkeypatch.setattr(law.time, "sleep", lambda s: None)
    resp = law._get("https://x", {})
    assert resp.json() == {"ok": True}
    assert calls["n"] == 3  # 두 번 실패 후 세 번째 성공


def test_get_raises_after_max_attempts(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        raise requests.ConnectTimeout("connect timed out")

    monkeypatch.setattr(law.requests, "get", fake_get)
    monkeypatch.setattr(law.time, "sleep", lambda s: None)
    with pytest.raises(requests.RequestException):
        law._get("https://x", {})
