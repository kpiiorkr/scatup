"""전역 설정 (rule: CLAUDE.md 전반).

기획안의 수치·임계치·대상 채널을 한 곳에서 관리한다.
API 키 등 비밀값은 .env 로 분리하며 여기서 os.environ 으로 읽는다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # --- 실행 트리거 (rule §2) ---
    run_interval_days: int = 3            # 2~3일 주기 정기 실행

    # --- 유튜브 쿼터 (rule §4-2, §5 Step 3, §8) ---
    youtube_quota_warn_ratio: float = 0.8  # 80% 초과 시 검색 횟수 자동 축소
    youtube_search_per_keyword: int = 1    # search.list는 키워드당 1회만 (쿼터 절약)

    # --- 데이터 부족 판단 (rule §6) ---
    min_collection_count: int = 20         # 임계치 미만이면 재확장/재수집 (팀 조정 필요)
    max_recollect_attempts: int = 2

    # --- 콘텐츠 품질/저작권 (rule §6, §8) ---
    plagiarism_similarity_threshold: float = 0.85  # 초과 시 초안 반려

    # --- 크롤링 대상 채널 (rule §3) ---
    naver_channels: tuple[str, ...] = ("blog", "cafe", "news", "datalab")
    youtube_enabled: bool = True

    # --- 타겟 고객 (rule §0) ---
    target_audience: str = "40~50대, 남녀 약 6:4, 효도상품·가족소통 니즈"

    # --- 의료 민감 키워드 (rule §6, §7) : 팀에서 지속 보강 ---
    medical_sensitive_keywords: tuple[str, ...] = (
        "치료", "효과", "부작용", "완치", "예방", "부작용 없음",
    )

    # --- 외부 API 엔드포인트 (rule §3, §7) ---
    law_api_base: str = "https://www.law.go.kr/DRF"  # 국가법령정보센터 Open API
    naver_openapi_base: str = "https://openapi.naver.com/v1"
    youtube_api_base: str = "https://www.googleapis.com/youtube/v3"

    # --- 비밀값 (.env 에서 로드) ---
    naver_client_id: str = field(default_factory=lambda: os.getenv("NAVER_CLIENT_ID", ""))
    naver_client_secret: str = field(default_factory=lambda: os.getenv("NAVER_CLIENT_SECRET", ""))
    youtube_api_key: str = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY", ""))
    law_api_key: str = field(default_factory=lambda: os.getenv("LAW_API_KEY", ""))
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    slack_webhook_url: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", ""))


settings = Settings()
