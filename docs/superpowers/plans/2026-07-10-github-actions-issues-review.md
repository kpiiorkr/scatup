# GitHub Actions cron + Issues 검수 워크플로우 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 파이프라인을 GitHub Actions cron으로 정기 실행하고, 생성된 초안을 GitHub Issue로 등록해 팀이 공유·검수하도록 만든다.

**Architecture:** 파이썬 코드가 GitHub REST API를 `requests`로 직접 호출한다(B안). GitHub 연동 로직은 신규 `output/github_issues.py`에 격리하고, `deliverer.py`는 이를 호출하는 오케스트레이터로 둔다. 토큰이 없으면(로컬) 콘솔 폴백. `main.py`는 매일 실행하되 급상승 감지/정기 3일 주기 게이트로 초안 생성 여부를 결정한다.

**Tech Stack:** Python 3.12, `requests`, `python-dotenv`, pytest, GitHub Actions.

## Global Constraints

- Python 3.12; 새 서드파티 의존성 금지 — 표준 라이브러리 + 기존 `requests`/`python-dotenv`만 사용.
- 코드/로그/라벨의 한국어 문구는 아래 태스크에 적힌 값 그대로 사용(수정 금지).
- 라벨 정확값: `scatup:draft`, `trigger:scheduled`, `trigger:rising`, `승인 대기`, `🚨담당자 판단 필요`.
- §7 fail-safe: 어떤 경우에도 자동 통과 없음. 애매/실패는 `ctx.halt(...)` → `🚨담당자 판단 필요`.
- §1-2: 자동 발행 금지. 에이전트는 Issue 등록(검수 대기)까지만.
- 실행 진입점은 `python run.py`(루트에서). 테스트는 기존 관례대로 `sys.path`에 `src`·루트를 삽입한다.
- 비밀값은 `GITHUB_TOKEN`/`GITHUB_REPOSITORY` 환경변수로 런타임 주입(코드/문서에 하드코딩 금지).

## File Structure

- Create: `src/scatup_agent/output/github_issues.py` — GitHub REST 연동(생성/조회/정기이력). 유일하게 GitHub에 의존하는 모듈.
- Modify: `config/settings.py` — 라벨 문자열 상수 5개 추가.
- Modify: `src/scatup_agent/output/deliverer.py` — `deliver()`가 Issue 생성/중복체크/폴백. 파일 저장 로직 제거.
- Modify: `src/scatup_agent/main.py` — 트리거 게이트(`_resolve_trigger`) 추가.
- Create: `.github/workflows/pipeline.yml` — 매일 cron + 수동 실행.
- Create: `tests/test_github_issues.py`, `tests/test_deliverer.py`, `tests/test_main_gate.py`.

참고: `build_dashboard.py`와 `data/outputs/`는 파이프라인이 더 이상 사용하지 않지만 파일은 남겨둔다(삭제 태스크 없음).

---

### Task 1: 라벨 상수 추가 (settings)

**Files:**
- Modify: `config/settings.py`
- Test: `tests/test_settings_labels.py`

**Interfaces:**
- Consumes: 없음
- Produces: `settings.label_draft`, `settings.label_trigger_scheduled`, `settings.label_trigger_rising`, `settings.label_cleared`, `settings.label_attention` — 모두 `str`.

- [ ] **Step 1: Write the failing test**

`tests/test_settings_labels.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_settings_labels.py -v`
Expected: FAIL with `AttributeError: ... 'Settings' object has no attribute 'label_draft'`

- [ ] **Step 3: Add the label constants**

`config/settings.py` — `Settings` 데이터클래스 안, `mistral_model` 줄 다음(비밀값 필드 앞)에 추가:
```python
    # --- GitHub Issue 라벨 (rule §9-2 검수 대기, §7 판정 결과) ---
    label_draft: str = "scatup:draft"
    label_trigger_scheduled: str = "trigger:scheduled"
    label_trigger_rising: str = "trigger:rising"
    label_cleared: str = "승인 대기"
    label_attention: str = "🚨담당자 판단 필요"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_settings_labels.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config/settings.py tests/test_settings_labels.py
git commit -m "feat: settings에 GitHub Issue 라벨 상수 추가"
```

---

### Task 2: GitHub REST 연동 모듈 (github_issues.py)

**Files:**
- Create: `src/scatup_agent/output/github_issues.py`
- Test: `tests/test_github_issues.py`

**Interfaces:**
- Consumes: `settings.label_draft`, `settings.label_trigger_scheduled` (Task 1).
- Produces:
  - `enabled() -> bool` — 토큰+레포 환경변수가 모두 있으면 True.
  - `draft_issue_title(rep_title: str) -> str` — `"[초안 검수] " + rep_title`.
  - `create_issue(title: str, body: str, labels: list[str]) -> str | None` — 생성된 Issue의 `html_url`, 비활성/실패 시 None.
  - `open_draft_titles() -> set[str]` — 열린 `scatup:draft` Issue 제목의 정규화 집합.
  - `is_duplicate(rep_title: str) -> bool` — 같은 대표 제목의 열린 초안 Issue 존재 여부.
  - `days_since_last_scheduled() -> int | None` — 최근 `trigger:scheduled` Issue로부터 경과 일수, 없으면 None.

- [ ] **Step 1: Write the failing tests**

`tests/test_github_issues.py`:
```python
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
            {"title": "[초안 검수] 난청 방치 위험"},
            {"title": "[초안 검수] 이명 관리법", "pull_request": {"url": "x"}},
        ])

    monkeypatch.setattr(gh.requests, "get", fake_get)
    titles = gh.open_draft_titles()
    assert "난청방치위험" in titles
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_github_issues.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scatup_agent.output.github_issues'`

- [ ] **Step 3: Create the module**

`src/scatup_agent/output/github_issues.py`:
```python
"""GitHub Issue 연동 (rule §9-2 검수 대기 등록).

블로그 초안을 GitHub Issue로 등록하고, 중복 방지·정기 주기 판단을 위해
기존 Issue를 조회한다. GitHub REST API를 requests로 직접 호출한다(새 의존성 없음).

토큰(GITHUB_TOKEN)·레포(GITHUB_REPOSITORY)는 런타임 환경변수로 주입한다.
Actions에서는 자동 주입되며, 로컬 개발에서 없으면 enabled()=False 로 콘솔 폴백한다.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

import requests

from config.settings import settings

_API = "https://api.github.com"
_TITLE_PREFIX = "[초안 검수] "
_TIMEOUT = 10


def _token() -> str:
    return os.getenv("GITHUB_TOKEN", "")


def _repo() -> str:
    return os.getenv("GITHUB_REPOSITORY", "")


def enabled() -> bool:
    """토큰·레포가 모두 설정돼 GitHub 연동이 가능한 상태인지."""
    return bool(_token() and _repo())


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def draft_issue_title(rep_title: str) -> str:
    return _TITLE_PREFIX + rep_title


def _norm_title(title: str) -> str:
    """제목 접두사를 떼고 공백을 제거해 중복 비교용으로 정규화한다."""
    body = title[len(_TITLE_PREFIX):] if title.startswith(_TITLE_PREFIX) else title
    return re.sub(r"\s+", "", body)


def create_issue(title: str, body: str, labels: list[str]) -> str | None:
    """Issue를 생성하고 html_url을 반환한다. 비활성/실패 시 None.

    (존재하지 않는 라벨은 GitHub이 Issue 생성 시 자동 생성한다.)
    """
    if not enabled():
        return None
    try:
        resp = requests.post(
            f"{_API}/repos/{_repo()}/issues",
            headers=_headers(),
            json={"title": title, "body": body, "labels": labels},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("html_url")
    except (requests.RequestException, ValueError) as err:
        print(f"[ISSUE] 생성 실패: {err}")
        return None


def open_draft_titles() -> set[str]:
    """열린 초안 Issue 제목의 정규화 집합 (중복 판단용)."""
    if not enabled():
        return set()
    try:
        resp = requests.get(
            f"{_API}/repos/{_repo()}/issues",
            headers=_headers(),
            params={"labels": settings.label_draft, "state": "open", "per_page": 100},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return {_norm_title(i["title"]) for i in resp.json() if "pull_request" not in i}
    except (requests.RequestException, ValueError, KeyError) as err:
        print(f"[ISSUE] 열린 초안 조회 실패: {err}")
        return set()


def is_duplicate(rep_title: str) -> bool:
    """같은 대표 제목의 열린 초안 Issue가 이미 있는지."""
    return _norm_title(rep_title) in open_draft_titles()


def days_since_last_scheduled() -> int | None:
    """최근 trigger:scheduled Issue로부터 경과 일수. 없거나 조회 실패 시 None."""
    if not enabled():
        return None
    try:
        resp = requests.get(
            f"{_API}/repos/{_repo()}/issues",
            headers=_headers(),
            params={
                "labels": settings.label_trigger_scheduled,
                "state": "all",
                "sort": "created",
                "direction": "desc",
                "per_page": 1,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        items = [i for i in resp.json() if "pull_request" not in i]
        if not items:
            return None
        created = datetime.strptime(items[0]["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        return (datetime.now(timezone.utc) - created).days
    except (requests.RequestException, ValueError, KeyError) as err:
        print(f"[ISSUE] 정기 실행 이력 조회 실패: {err}")
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_github_issues.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add src/scatup_agent/output/github_issues.py tests/test_github_issues.py
git commit -m "feat: GitHub Issue 연동 모듈(생성·중복조회·정기이력) 추가"
```

---

### Task 3: deliverer가 Issue를 생성하도록 재작성

**Files:**
- Modify: `src/scatup_agent/output/deliverer.py`
- Test: `tests/test_deliverer.py`

**Interfaces:**
- Consumes: `github_issues.enabled/draft_issue_title/is_duplicate/create_issue` (Task 2), `settings.label_*` (Task 1), `TriggerType` (schemas).
- Produces: `deliver(ctx: PipelineContext) -> None` — 초안이 있으면 Issue 생성(또는 콘솔 폴백/중복 생략), 토큰 있는데 실패하면 `RuntimeError`.

- [ ] **Step 1: Write the failing tests**

`tests/test_deliverer.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_deliverer.py -v`
Expected: FAIL (deliver still writes files / no Issue logic; assertions on labels/body fail or AttributeError)

- [ ] **Step 3: Rewrite deliverer.py**

`src/scatup_agent/output/deliverer.py` 전체를 아래로 교체:
```python
"""산출물 전달 (rule §9-2, §10).

블로그 초안을 GitHub Issue '검수 대기'로 등록한다. 발행은 절대 자동으로 하지 않으며,
항상 사람이 직접 수행한다(§1-2). 토큰이 없는 로컬 실행에서는 콘솔로 폴백한다.
"""
from __future__ import annotations

from datetime import datetime

from ..models.schemas import PipelineContext, TriggerType
from . import github_issues
from config.settings import settings

_CHECKLIST = (
    "## 검수 체크리스트 (rule §10)\n"
    "- [ ] 팩트체크\n"
    "- [ ] 브랜드보이스 체크\n"
    "- [ ] 발행 승인 (승인 후 사람이 직접 발행)\n"
)


def deliver(ctx: PipelineContext) -> None:
    """초안을 검수 대기 Issue로 등록한다. 초안이 없으면 콘솔 알림만 수행한다."""
    if not (ctx.draft and (ctx.draft.title_options or ctx.draft.body)):
        # 초안 생성 전 게이트에 걸린 경우(데이터/근거 부족 등): 콘솔 알림만 (Actions 로그로 확인)
        if ctx.halted:
            _notify(f"[담당자 판단 필요] {ctx.halt_reason}")
        return

    rep_title = ctx.draft.title_options[0] if ctx.draft.title_options else "(제목 없음)"
    title = github_issues.draft_issue_title(rep_title)
    body = _issue_body(ctx)
    labels = _labels(ctx)

    if not github_issues.enabled():
        _notify("[검수 대기] 신규 블로그 초안 (로컬: GitHub 미연동 → 콘솔 출력)")
        print(body)
        return

    if github_issues.is_duplicate(rep_title):
        print("[DEDUP] 동일 제목 초안 Issue가 이미 열려 있어 생성을 생략합니다")
        return

    url = github_issues.create_issue(title, body, labels)
    if url is None:
        print(body)  # 유실 방지: 실패 시 본문을 로그에 남긴다
        raise RuntimeError("GitHub Issue 생성 실패 (토큰은 있으나 API 오류)")
    print(f"[ISSUE] 검수 대기 Issue 생성 → {url}")


def _labels(ctx: PipelineContext) -> list[str]:
    labels = [settings.label_draft]
    labels.append(
        settings.label_trigger_scheduled
        if ctx.trigger == TriggerType.SCHEDULED
        else settings.label_trigger_rising
    )
    labels.append(settings.label_attention if ctx.halted else settings.label_cleared)
    return labels


def _issue_body(ctx: PipelineContext) -> str:
    return "\n\n---\n\n".join([_render_draft(ctx), _render_report(ctx), _CHECKLIST])


def _render_draft(ctx: PipelineContext) -> str:
    d = ctx.draft
    status = d.metadata.compliance_status.value if d.metadata.compliance_status else "미검수"
    flags = ", ".join(f.value for f in d.metadata.sensitivity_flags) or "없음"
    titles = "\n".join(f"{i}. {t}" for i, t in enumerate(d.title_options, 1))
    lines = [
        "# 블로그 초안 (검수 대기)",
        "",
        f"> 상태: **{status}** · 민감도 플래그: {flags} · 저작권 유사도: {d.metadata.similarity_score:.2f}",
        "> ⚠️ 발행은 담당자 승인 후 직접 수행합니다. 자동 발행 금지 (rule §1-2).",
        "",
        "## 제목 3안",
        titles,
        "",
        "## 본문",
        d.body,
        "",
        "## 해시태그",
        " ".join(d.hashtags),
        "",
        "## 근거 문서",
        "\n".join(f"- {link}" for link in d.evidence_links) or "- (없음)",
    ]
    return "\n".join(lines)


def _render_report(ctx: PipelineContext) -> str:
    ins = ctx.insight
    lines = [
        "# 트렌드 인사이트 리포트",
        "",
        f"- 실행 시각: {ctx.created_at:%Y-%m-%d %H:%M}",
        f"- 트리거: {ctx.trigger.value}",
        f"- 시드 키워드: {', '.join(ctx.seed_keywords)}",
        f"- 확장 키워드: {len(ctx.expanded_keywords)}개",
        f"- 수집·정제 자료: {len(ctx.collected)}건",
        "",
        "## 급상승 토픽",
        "\n".join(f"- {t}" for t in (ins.rising_topics if ins else [])) or "- (없음)",
        "",
        "## 감성 포인트",
        "\n".join(f"- {s}" for s in (ins.sentiment_points if ins else [])) or "- (없음)",
        "",
        "## 소재 후보",
        "\n".join(f"- {c}" for c in (ins.topic_candidates if ins else [])) or "- (없음)",
        "",
        "## 상위 수집 자료 (관련성순)",
    ]
    for it in ctx.collected[:10]:
        lines.append(
            f"- [{it.channel.value}] {it.title} (관련성 {it.relevance_score:.2f}, 조회 {it.view_count:,}) — {it.url}"
        )
    if ctx.halted:
        lines += ["", "## ⚠️ 담당자 확인 필요", f"- 사유: {ctx.halt_reason}"]
    return "\n".join(lines)


def _notify(message: str) -> None:
    print(f"[NOTIFY] {message}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_deliverer.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Run the full suite (regression)**

Run: `python -m pytest -v`
Expected: PASS (기존 `test_pipeline.py` 포함 모두 통과)

- [ ] **Step 6: Commit**

```bash
git add src/scatup_agent/output/deliverer.py tests/test_deliverer.py
git commit -m "feat: deliver()가 초안을 GitHub Issue 검수 대기로 등록하도록 재작성"
```

---

### Task 4: main 트리거 게이트 (매일 실행 + 3일 정기)

**Files:**
- Modify: `src/scatup_agent/main.py`
- Test: `tests/test_main_gate.py`

**Interfaces:**
- Consumes: `scheduler.detect_event_trigger()`, `github_issues.enabled/days_since_last_scheduled` (Task 2), `settings.run_interval_days`.
- Produces: `_resolve_trigger() -> TriggerType | None` — 오늘 사용할 트리거, None이면 생성 없이 종료.

- [ ] **Step 1: Write the failing tests**

`tests/test_main_gate.py`:
```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_main_gate.py -v`
Expected: FAIL with `AttributeError: module 'scatup_agent.main' has no attribute '_resolve_trigger'`

- [ ] **Step 3: Rewrite main.py**

`src/scatup_agent/main.py` 전체를 아래로 교체:
```python
"""엔트리 포인트 (rule: CLAUDE.md 전체).

매일 실행하되, 급상승 감지 시 즉시 초안을 만들고, 그 외에는 정기 주기(§2, 3일)가
도래했을 때만 초안을 생성한다. '마지막 정기 실행일'은 최근 trigger:scheduled
Issue 생성일로 역산한다(파일 상태 없이 Issue를 단일 창구로 사용).
"""
from __future__ import annotations

from config.settings import settings

from .models.schemas import TriggerType
from .trigger import scheduler
from .pipeline import run_pipeline
from .processing import keyword_miner
from .output import github_issues


def _resolve_trigger() -> TriggerType | None:
    """오늘 사용할 트리거를 결정한다. None이면 오늘은 초안 생성 없이 종료.

    - 급상승 감지 → 즉시 실행(RISING_KEYWORD).
    - 급상승 없음 → 최근 정기 Issue가 run_interval_days 경과했을 때만 SCHEDULED.
    - 로컬(GitHub 미연동) → 게이트 건너뛰고 항상 SCHEDULED (개발 편의).
    """
    event = scheduler.detect_event_trigger()
    if event is not None:
        return event
    if github_issues.enabled():
        days = github_issues.days_since_last_scheduled()
        if days is not None and days < settings.run_interval_days:
            return None
    return TriggerType.SCHEDULED


def main() -> None:
    trigger = _resolve_trigger()
    if trigger is None:
        print(
            f"[SKIP] 급상승 없음 & 마지막 정기 실행 {settings.run_interval_days}일 미경과 "
            "→ 오늘은 초안 생성 안 함"
        )
        return

    # 기본 시드 + 이전 주기에 수집 원문에서 발굴한 신규 키워드 (§5 Step 1 보강)
    seed_keywords = list(dict.fromkeys(list(settings.seed_keywords) + keyword_miner.recall()))

    print(f"[START] trigger={trigger.value}, seeds={seed_keywords}")
    ctx = run_pipeline(trigger, seed_keywords)

    if ctx.halted and ctx.draft:
        print(f"[HALTED] 초안은 생성 완료, 담당자 검수 대기 → {ctx.halt_reason}")
    elif ctx.halted:
        print(f"[HALTED] 담당자 판단 필요 → {ctx.halt_reason}")
    else:
        print("[DONE] 초안 생성 완료 → 검수 대기 등록 (발행은 사람이 직접 수행)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_main_gate.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/scatup_agent/main.py tests/test_main_gate.py
git commit -m "feat: main에 매일 실행+3일 정기 트리거 게이트 추가"
```

---

### Task 5: GitHub Actions 워크플로우

**Files:**
- Create: `.github/workflows/pipeline.yml`

**Interfaces:**
- Consumes: `run.py`(엔트리), `requirements.txt`, Secrets(NAVER/YOUTUBE/LAW/MISTRAL), 자동 `GITHUB_TOKEN`/`GITHUB_REPOSITORY`.
- Produces: 없음(CI 설정).

- [ ] **Step 1: Create the workflow file**

`.github/workflows/pipeline.yml`:
```yaml
name: scatup content pipeline

on:
  schedule:
    - cron: '0 0 * * *'        # 매일 00:00 UTC (= 09:00 KST). 급상승 감지 + 3일마다 정기 초안
  workflow_dispatch: {}         # 수동 실행 버튼

permissions:
  contents: read                # checkout
  issues: write                 # Issue 생성/조회

concurrency:
  group: scatup-pipeline
  cancel-in-progress: false

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run pipeline
        run: python run.py
        env:
          NAVER_CLIENT_ID:     ${{ secrets.NAVER_CLIENT_ID }}
          NAVER_CLIENT_SECRET: ${{ secrets.NAVER_CLIENT_SECRET }}
          YOUTUBE_API_KEY:     ${{ secrets.YOUTUBE_API_KEY }}
          LAW_API_KEY:         ${{ secrets.LAW_API_KEY }}
          MISTRAL_API_KEY:     ${{ secrets.MISTRAL_API_KEY }}
          GITHUB_TOKEN:        ${{ secrets.GITHUB_TOKEN }}
```

- [ ] **Step 2: Validate YAML structure**

Run: `python -c "import ast,sys; open('.github/workflows/pipeline.yml',encoding='utf-8').read(); print('file readable')"`
Expected: `file readable` (PyYAML은 의존성에 없으므로 들여쓰기를 육안 확인: `on.schedule.cron`, `workflow_dispatch`, `permissions.issues: write`, run 스텝의 env 6개가 있는지 확인)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pipeline.yml
git commit -m "ci: 매일 cron + 수동 실행 파이프라인 워크플로우 추가"
```

---

## 수동 설정 (구현 후 사용자 안내)

코드로 자동화할 수 없는 GitHub UI 작업 — 실행 담당자에게 전달:

1. **Secrets 등록** (repo Settings > Secrets and variables > Actions > New repository secret):
   `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `YOUTUBE_API_KEY`, `LAW_API_KEY`, `MISTRAL_API_KEY`.
   (`GITHUB_TOKEN`은 자동 발급 — 등록 불필요.)
2. **팀원 초대**: repo Settings > Collaborators에 검수 팀원 추가.
3. **알림 구독**: 각 팀원이 repo를 **Watch**(또는 Custom > Issues)로 설정.
4. **첫 실행 확인**: Actions 탭 > "scatup content pipeline" > **Run workflow**(수동)로 1회 실행 → Issues 탭에 초안 Issue 생성 확인.
5. 라벨은 첫 Issue 생성 시 GitHub이 자동 생성하므로 사전 등록 불필요.

---

## Self-Review

**Spec coverage:**
- §3 흐름/§4 게이트 → Task 4. §5 Issue 형식 → Task 3(제목/본문/라벨/체크리스트). §6 중복 → Task 2(`is_duplicate`/`open_draft_titles`) + Task 3. §7 모듈 → Task 1(settings)+Task 2(github_issues)+Task 3(deliverer)+Task 4(main). §8 워크플로우/시크릿 → Task 5 + 수동 설정. §9 에러/fail-safe → Task 3(폴백/RuntimeError), 기존 파이프라인 halt 유지. §10 테스트 → 각 태스크 TDD. 누락 없음.
- 제거 항목(§ spec 8): `_save_outputs`/파일 `_is_duplicate` → Task 3에서 삭제(교체본에 없음). `_notify` 콘솔은 폴백 용도로만 잔존(의도됨).

**알려진 한계(후속):** 초안 생성 전 게이트(데이터/근거 부족)로 halt된 경우 Issue를 만들지 않고 콘솔 알림만 한다(스펙 §5는 초안 대상). 팀이 이 신호도 Issue로 받길 원하면 별도 태스크로 확장.

**Placeholder scan:** TBD/TODO 없음. 모든 코드 스텝에 실제 코드 포함.

**Type consistency:** `enabled/draft_issue_title/is_duplicate/create_issue/open_draft_titles/days_since_last_scheduled` 시그니처가 Task 2 정의와 Task 3·4 사용처에서 일치. 라벨 상수명(`label_draft` 등)이 Task 1 정의와 Task 3 사용처에서 일치. `_resolve_trigger` 반환 타입(`TriggerType | None`)이 Task 4 테스트/사용과 일치.
