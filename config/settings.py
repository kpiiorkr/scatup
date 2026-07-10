"""전역 설정 (rule: CLAUDE.md 전반).

기획안의 수치·임계치·대상 채널을 한 곳에서 관리한다.
API 키 등 비밀값은 .env 로 분리하며 여기서 os.environ 으로 읽는다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    # --- 실행 트리거 (rule §2) ---
    run_interval_days: int = 3            # 2~3일 주기 정기 실행

    # --- 유튜브 쿼터 (rule §4-2, §5 Step 3, §8) ---
    youtube_quota_warn_ratio: float = 0.8  # 80% 초과 시 검색 횟수 자동 축소
    youtube_search_per_keyword: int = 1    # search.list는 키워드당 1회만 (쿼터 절약)
    youtube_daily_quota_units: int = 10_000  # Google Cloud 프로젝트 기본 일일 쿼터

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

    # --- 시드 키워드 (rule §5 Step 1) : 팀에서 지속 보강 ---
    seed_keywords: tuple[str, ...] = (
        "난청", "보청기", "보청기 정부지원", "보청기 가격비교", "이명", "안들림",
    )

    # --- 키워드 확장 (rule §5 Step 1, §6 데이터 부족 재확장) ---
    related_keywords_per_seed: int = 5   # 키워드당 연관검색어 최대 수
    max_expanded_keywords: int = 50      # 확장 키워드 전체 상한

    # --- 의료 민감 키워드 (rule §6, §7) : 팀에서 지속 보강 ---
    medical_sensitive_keywords: tuple[str, ...] = (
        "치료", "효과", "부작용", "완치", "예방", "부작용 없음",
    )

    # --- 데이터랩 급상승 감지 (rule §2 이벤트 트리거) ---
    datalab_lookback_days: int = 14        # 추세 조회 기간
    datalab_spike_ratio_threshold: float = 1.5  # 최근일 / 이전 평균 비율이 이 값 초과 시 급상승

    # --- 외부 API 엔드포인트 (rule §3, §7) ---
    law_api_base: str = "https://www.law.go.kr/DRF"  # 국가법령정보센터 Open API
    naver_openapi_base: str = "https://openapi.naver.com/v1"
    youtube_api_base: str = "https://www.googleapis.com/youtube/v3"
    mistral_api_base: str = "https://api.mistral.ai/v1"
    mistral_model: str = "mistral-small-latest"  # 초안 생성(Step 8) 기본 모델, 팀에서 조정 가능

    # --- GitHub Issue 라벨 (rule §9-2 검수 대기, §7 판정 결과) ---
    label_draft: str = "scatup:draft"
    label_trigger_scheduled: str = "trigger:scheduled"
    label_trigger_rising: str = "trigger:rising"
    label_cleared: str = "승인 대기"
    label_attention: str = "🚨담당자 판단 필요"

    # --- 비밀값 (.env 에서 로드) ---
    naver_client_id: str = field(default_factory=lambda: os.getenv("NAVER_CLIENT_ID", ""))
    naver_client_secret: str = field(default_factory=lambda: os.getenv("NAVER_CLIENT_SECRET", ""))
    youtube_api_key: str = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY", ""))
    law_api_key: str = field(default_factory=lambda: os.getenv("LAW_API_KEY", ""))
    mistral_api_key: str = field(default_factory=lambda: os.getenv("MISTRAL_API_KEY", ""))
    slack_webhook_url: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", ""))


settings = Settings()
