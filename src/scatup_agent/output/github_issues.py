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


def repo_url(path: str = "") -> str:
    """저장소 웹 URL. 로컬(레포 미설정)에서는 기본 레포로 폴백한다."""
    repo = _repo() or "kpiiorkr/scatup"
    return f"https://github.com/{repo}/{path}".rstrip("/")


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
