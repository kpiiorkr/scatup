"""신규 키워드 발굴 (rule §5 Step 1 보강, §3 도메인 범위 유지).

수집한 네이버·유튜브 원문(제목·본문·댓글)에서 시드에 없던 도메인 관련
빈출어를 뽑아 '다음 주기 시드'로 편입한다. 커뮤니티가 실제로 말하는 소주제를
자동으로 발견하되, §3 도메인(난청·보청기·치매) 밖으로 새지 않도록 도메인
어근을 포함한 후보만 남긴다. 별도 형태소 분석기 없이 표준 라이브러리로 동작한다.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from ..models.schemas import CollectedItem

# 발굴 키워드 저장소 (런타임 상태, .gitignore 대상)
_STORE_PATH = Path(__file__).resolve().parents[3] / "data" / "discovered_keywords.json"
_STORE_CAP = 20  # 최근 발굴어 보관 상한

# 도메인 어근 — 이 어근을 포함하는 더 구체적인 말만 후보로 (범위 밖 이탈 방지)
_DOMAIN_STEMS = (
    "난청", "보청기", "이명", "청력", "청각", "보장구", "인공와우",
    "돌발성", "소음성", "노인성", "귀울림", "난청등급",
)

# 어근 자체(너무 일반적)는 신규 후보에서 제외
_TOO_GENERIC = set(_DOMAIN_STEMS) | {"난청이", "보청기가"}

# 흔한 조사 — 토큰 끝에서 떼어내 후보 품질을 높인다 (휴리스틱)
_JOSA = (
    "으로써", "으로", "에서", "까지", "부터", "에게", "이나", "라도", "처럼",
    "보다", "마저", "조차", "이라", "은", "는", "이", "가", "을", "를",
    "의", "에", "도", "만", "과", "와", "로", "나", "랑", "께", "요",
)


def mine(items: list[CollectedItem], known: list[str], top_n: int = 5, min_count: int = 3) -> list[str]:
    """수집 원문에서 시드에 없는 도메인 관련 빈출어를 발굴한다."""
    known_norm = {k.replace(" ", "") for k in known}
    counter: Counter[str] = Counter()

    for item in items:
        text = " ".join([item.title, item.text, " ".join(item.top_comments)])
        for raw in re.findall(r"[가-힣]{2,12}", text):
            token = _strip_josa(raw)
            if not (2 <= len(token) <= 10):
                continue
            if token in _TOO_GENERIC or token.replace(" ", "") in known_norm:
                continue
            if any(stem in token and token != stem for stem in _DOMAIN_STEMS):
                counter[token] += 1

    discovered: list[str] = []
    for term, count in counter.most_common():
        if count < min_count:
            break
        discovered.append(term)
        if len(discovered) >= top_n:
            break
    return discovered


def _strip_josa(token: str) -> str:
    for josa in sorted(_JOSA, key=len, reverse=True):
        if token.endswith(josa) and len(token) - len(josa) >= 2:
            return token[: -len(josa)]
    return token


def recall() -> list[str]:
    """이전 주기에 발굴해 저장해둔 키워드를 불러온다."""
    try:
        data = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        return list(data) if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def remember(terms: list[str]) -> None:
    """발굴 키워드를 기존 목록과 합쳐 최근 것 위주로 저장한다."""
    merged = list(dict.fromkeys(terms + recall()))[:_STORE_CAP]
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
