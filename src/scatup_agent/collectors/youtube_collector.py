"""Step 3 · 유튜브 수집 (rule §5 Step 3, §4-2, §8).

쿼터 절약 규칙을 반드시 지킨다:
  ① search.list 는 키워드당 1회만 호출
  ② videos.list 로 좋아요·조회수 일괄 조회
  ③ commentThreads.list 로 상위 댓글·댓글별 좋아요 수집
  ④ 댓글 비활성 영상은 통계(조회수·좋아요)만 반영
쿼터 80% 초과 시 검색 횟수를 자동 축소한다 (남은 키워드는 다음 주기로 이월, rule §8).

YOUTUBE_API_KEY 미설정 시 '샘플 데이터 모드'로 동작한다.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import requests

from config.settings import settings

from ..models.schemas import CollectedItem, SourceChannel

# 샘플 모드에서 수집을 시뮬레이션할 키워드 수 (실 연동 시 제거)
_SAMPLE_KEYWORD_LIMIT = 5

# 실 연동 설정
_RESULTS_PER_KEYWORD = 3     # search.list 1회 호출당 가져올 영상 수
_TOP_COMMENTS_LIMIT = 5
_TIMEOUT_SECONDS = 5

# YouTube Data API 쿼터 비용 (단위: quota unit)
_COST_SEARCH = 100
_COST_VIDEOS = 1
_COST_COMMENT_THREADS = 1

# 일일 쿼터 사용량 로컬 추적 파일 (§8: 쿼터 초과 시 다음 주기로 이월 판단용)
_QUOTA_STATE_PATH = Path(__file__).resolve().parents[3] / "data" / ".youtube_quota.json"

_SAMPLE_COMMENTS = [
    "부모님 해드렸는데 대화가 편해져서 저까지 좋네요",
    "가격이 부담돼요… 정부지원 신청 방법 자세히 알려주세요",
    "적응하는 데 한 달 걸렸는데 지금은 만족합니다",
    "어머니가 자꾸 되물으셔서 검사 예약했어요, 영상 감사합니다",
]


def collect(keywords: list[str]) -> list[CollectedItem]:
    """유튜브 수집. 키 미설정 시 샘플 데이터 모드."""
    if not settings.youtube_api_key:
        return _collect_samples(keywords)

    items: list[CollectedItem] = []
    for idx, keyword in enumerate(keywords):
        if _quota_over_warn():
            remaining = len(keywords) - idx
            print(
                f"[YOUTUBE] 쿼터 {settings.youtube_quota_warn_ratio:.0%} 초과 → 검색 횟수 자동 축소, "
                f"남은 키워드 {remaining}개는 다음 주기로 이월 (rule §8)"
            )
            break

        try:
            video_ids = _search_video_ids(keyword)  # ① search.list 키워드당 1회
        except requests.RequestException as err:
            print(f"[YOUTUBE] 검색 실패(키워드={keyword}): {err} → skip")
            continue
        if not video_ids:
            continue

        try:
            videos = _fetch_video_stats(video_ids)  # ② videos.list 일괄 통계
        except requests.RequestException as err:
            print(f"[YOUTUBE] 통계 조회 실패(키워드={keyword}): {err} → skip")
            continue

        items += [_build_item(video) for video in videos]

    print(f"[YOUTUBE] 검색 API 수집 {len(items)}건 (키워드 최대 {len(keywords)}개)")
    return items


def _search_video_ids(keyword: str) -> list[str]:
    resp = requests.get(
        f"{settings.youtube_api_base}/search",
        params={
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "maxResults": _RESULTS_PER_KEYWORD,
            "key": settings.youtube_api_key,
        },
        timeout=_TIMEOUT_SECONDS,
    )
    _record_quota_usage(_COST_SEARCH)
    resp.raise_for_status()
    return [item["id"]["videoId"] for item in resp.json().get("items", [])]


def _fetch_video_stats(video_ids: list[str]) -> list[dict]:
    resp = requests.get(
        f"{settings.youtube_api_base}/videos",
        params={
            "part": "snippet,statistics",
            "id": ",".join(video_ids),
            "key": settings.youtube_api_key,
        },
        timeout=_TIMEOUT_SECONDS,
    )
    _record_quota_usage(_COST_VIDEOS)
    resp.raise_for_status()
    return resp.json().get("items", [])


def _build_item(video: dict) -> CollectedItem:
    video_id = video["id"]
    snippet = video.get("snippet", {})
    stats = video.get("statistics", {})

    # statistics 에 commentCount 가 없으면 댓글 비활성화 영상 → 통계만 반영 (rule §5 Step3-④)
    comments = _fetch_top_comments(video_id) if "commentCount" in stats else []

    return CollectedItem(
        channel=SourceChannel.YOUTUBE,
        title=snippet.get("title", ""),
        url=f"https://www.youtube.com/watch?v={video_id}",
        text=snippet.get("description", ""),
        view_count=int(stats.get("viewCount", 0)),
        like_count=int(stats.get("likeCount", 0)),
        top_comments=comments,
        raw=video,
    )


def _fetch_top_comments(video_id: str) -> list[str]:
    """상위 댓글을 조회한다 (rule §5 Step3-③). 실패(비활성화 등) 시 통계만 반영."""
    try:
        resp = requests.get(
            f"{settings.youtube_api_base}/commentThreads",
            params={
                "part": "snippet",
                "videoId": video_id,
                "order": "relevance",
                "maxResults": _TOP_COMMENTS_LIMIT,
                "key": settings.youtube_api_key,
            },
            timeout=_TIMEOUT_SECONDS,
        )
        _record_quota_usage(_COST_COMMENT_THREADS)
        resp.raise_for_status()
    except requests.RequestException:
        return []  # rule §5 Step3-④: 댓글 조회 불가 → 통계만 반영

    comments = []
    for item in resp.json().get("items", []):
        snippet = item["snippet"]["topLevelComment"]["snippet"]
        text = snippet.get("textDisplay", "").strip()
        if text:
            comments.append(text)
    return comments


def _collect_samples(keywords: list[str]) -> list[CollectedItem]:
    """샘플 데이터 생성. 규칙 ④(댓글 비활성 영상은 통계만)도 모사한다."""
    targets = keywords[:_SAMPLE_KEYWORD_LIMIT]
    print(f"[MOCK] 유튜브 API 키 미설정 → 샘플 데이터 모드 (키워드 {len(targets)}개 × 2영상)")

    items: list[CollectedItem] = []
    for kw in targets:
        seed = int(hashlib.md5(kw.encode("utf-8")).hexdigest()[:6], 16)
        # 댓글이 활성화된 영상
        items.append(
            CollectedItem(
                channel=SourceChannel.YOUTUBE,
                title=f"{kw}, 꼭 알아야 할 5가지 (이비인후과 전문의)",
                url=f"https://sample.youtube.com/watch?v=a{seed}",
                text=f"{kw}에 대해 검사부터 관리까지 단계별로 설명하는 영상",
                view_count=seed % 90000 + 8000,
                like_count=seed % 1200 + 100,
                top_comments=list(_SAMPLE_COMMENTS),
                raw={"mode": "sample", "comments_enabled": True},
            )
        )
        # 댓글 비활성 영상 → 통계만 반영 (rule §5 Step 3-④, §8)
        items.append(
            CollectedItem(
                channel=SourceChannel.YOUTUBE,
                title=f"부모님 {kw} 선물 브이로그",
                url=f"https://sample.youtube.com/watch?v=b{seed}",
                text=f"부모님께 {kw} 상담을 선물한 자녀의 브이로그",
                view_count=seed % 40000 + 3000,
                like_count=seed % 600 + 50,
                top_comments=[],  # 댓글 비활성 → 통계만
                raw={"mode": "sample", "comments_enabled": False},
            )
        )
    return items


def _quota_over_warn() -> bool:
    """당일 유튜브 쿼터 사용량이 경고 비율(80%)을 초과했는지 확인한다 (rule §4-2, §8)."""
    state = _load_quota_state()
    ratio = state["used_units"] / settings.youtube_daily_quota_units
    return ratio >= settings.youtube_quota_warn_ratio


def _record_quota_usage(units: int) -> None:
    state = _load_quota_state()
    state["used_units"] += units
    _save_quota_state(state)


def _load_quota_state() -> dict:
    today = date.today().isoformat()
    try:
        state = json.loads(_QUOTA_STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    if state.get("date") != today:
        state = {"date": today, "used_units": 0}
    return state


def _save_quota_state(state: dict) -> None:
    _QUOTA_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _QUOTA_STATE_PATH.write_text(json.dumps(state), encoding="utf-8")
