"""Step 2 · 네이버 수집 (rule §5 Step 2, §3).

블로그·카페·뉴스 대상 관련 자료를 수집한다.
NAVER_CLIENT_ID/SECRET 미설정 시 '샘플 데이터 모드'로 동작해
API 키 없이도 전체 파이프라인 흐름을 확인할 수 있다.
"""
from __future__ import annotations

import hashlib
import re

import requests

from config.settings import settings

from ..models.schemas import CollectedItem, SourceChannel

# 샘플 모드에서 수집을 시뮬레이션할 키워드 수 (실 연동 시 제거)
_SAMPLE_KEYWORD_LIMIT = 10

# 실 연동 시 쿼터/응답시간 관리를 위한 키워드 상한 및 채널별 조회 건수
_REAL_KEYWORD_LIMIT = 10
_ITEMS_PER_QUERY = 5
_TIMEOUT_SECONDS = 5

_SEARCH_ENDPOINT_BY_CHANNEL = {
    SourceChannel.NAVER_BLOG: "blog",
    SourceChannel.NAVER_CAFE: "cafearticle",
    SourceChannel.NAVER_NEWS: "news",
}

_TAG_RE = re.compile(r"<[^>]+>")

# (채널, 제목 템플릿, 본문 템플릿) — 실제 커뮤니티에서 자주 보이는 글 유형을 모사
_SAMPLE_TEMPLATES = [
    (
        SourceChannel.NAVER_BLOG,
        "{kw} 3개월 후기 — 부모님 대화가 다시 늘었어요",
        "아버지가 {kw} 문제로 고민이 많으셨는데, 전문 센터에서 검사받고 관리 시작한 뒤 "
        "가족 대화가 눈에 띄게 늘었습니다. 다만 적응 기간은 사람마다 다른 것 같아요. "
        "가격이 부담됐는데 정부지원 제도를 알고 나서 큰 도움이 됐습니다.",
    ),
    (
        SourceChannel.NAVER_CAFE,
        "{kw} 알아보는 중인데 조언 부탁드려요",
        "{kw} 관련해서 알아보고 있는데 가격이 천차만별이네요. 정부지원이 되는지, "
        "어느 센터가 괜찮은지 경험자분들 조언 부탁드립니다. "
        "'완치된다'는 광고도 봤는데 믿어도 되는 건가요? 걱정이 앞서네요.",
    ),
    (
        SourceChannel.NAVER_NEWS,
        "40~60대 {kw} 관심 급증… 조기 관리 중요성 커져",
        "최근 중장년층에서 {kw} 관련 검색과 상담이 크게 늘었다. 전문가들은 난청을 "
        "방치하면 인지 기능 저하로 이어질 수 있어 조기 검사와 관리가 중요하다고 조언했다. "
        "특히 부모님 명절 선물로 청력 검사를 문의하는 자녀 세대가 늘고 있다.",
    ),
]


def collect(keywords: list[str]) -> list[CollectedItem]:
    """네이버 블로그·카페·뉴스 수집. 키 미설정 시 샘플 데이터 모드."""
    if not (settings.naver_client_id and settings.naver_client_secret):
        return _collect_samples(keywords)

    items: list[CollectedItem] = []
    targets = keywords[:_REAL_KEYWORD_LIMIT]
    for keyword in targets:
        for channel, endpoint in _SEARCH_ENDPOINT_BY_CHANNEL.items():
            try:
                items += _search(channel, endpoint, keyword)
            except (requests.RequestException, ValueError, KeyError) as err:
                # §4-2: API 응답 오류 시 해당 소스만 skip (전체 중단 금지)
                print(f"[NAVER] {channel.value} 검색 실패(키워드={keyword}): {err} → skip")
    print(f"[NAVER] 검색 API 수집 {len(items)}건 (키워드 {len(targets)}개 × 3채널)")
    return items


def _search(channel: SourceChannel, endpoint: str, keyword: str) -> list[CollectedItem]:
    """네이버 검색 API(blog/cafearticle/news) 1회 호출."""
    resp = requests.get(
        f"{settings.naver_openapi_base}/search/{endpoint}.json",
        headers={
            "X-Naver-Client-Id": settings.naver_client_id,
            "X-Naver-Client-Secret": settings.naver_client_secret,
        },
        params={"query": keyword, "display": _ITEMS_PER_QUERY, "sort": "sim"},
        timeout=_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return [
        CollectedItem(
            channel=channel,
            title=_strip_tags(entry.get("title", "")),
            url=entry.get("link", ""),
            text=_strip_tags(entry.get("description", "")),
            raw=entry,
        )
        for entry in resp.json().get("items", [])
    ]


def _strip_tags(text: str) -> str:
    """검색 API 응답의 <b> 강조 태그 등을 제거한다."""
    return _TAG_RE.sub("", text).strip()


def _collect_samples(keywords: list[str]) -> list[CollectedItem]:
    """샘플 데이터 생성 (키워드별 결정적 — 같은 키워드는 항상 같은 결과)."""
    targets = keywords[:_SAMPLE_KEYWORD_LIMIT]
    print(f"[MOCK] 네이버 API 키 미설정 → 샘플 데이터 모드 (키워드 {len(targets)}개 × 3채널)")

    items: list[CollectedItem] = []
    for kw in targets:
        seed = int(hashlib.md5(kw.encode("utf-8")).hexdigest()[:6], 16)
        for idx, (channel, title_tpl, text_tpl) in enumerate(_SAMPLE_TEMPLATES):
            items.append(
                CollectedItem(
                    channel=channel,
                    title=title_tpl.format(kw=kw),
                    url=f"https://sample.naver.com/{channel.value}/{seed}{idx}",
                    text=text_tpl.format(kw=kw),
                    view_count=(seed + idx * 137) % 4800 + 200,
                    like_count=(seed + idx * 31) % 90 + 5,
                    raw={"mode": "sample"},
                )
            )
    return items
