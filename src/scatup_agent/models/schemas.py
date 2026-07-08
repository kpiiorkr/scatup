"""데이터 모델 정의 (rule: CLAUDE.md §4, §9).

파이프라인 전 구간에서 주고받는 데이터 구조를 한 곳에 모아 정의한다.
표준 라이브러리(dataclasses, enum)만 사용해 별도 설치 없이 동작한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TriggerType(str, Enum):
    """실행 트리거 종류 (rule §2)."""
    SCHEDULED = "scheduled"            # 2~3일 주기 정기 실행
    RISING_KEYWORD = "rising_keyword"  # 급상승 검색어
    YOUTUBE_SPIKE = "youtube_spike"    # 유튜브 조회수 급상승
    ISSUE_NEWS = "issue_news"          # 이슈성 뉴스


class SourceChannel(str, Enum):
    """크롤링 대상 채널 (rule §3)."""
    NAVER_BLOG = "naver_blog"
    NAVER_CAFE = "naver_cafe"
    NAVER_NEWS = "naver_news"
    NAVER_DATALAB = "naver_datalab"
    YOUTUBE = "youtube"


class ComplianceStatus(str, Enum):
    """의료법 준수 판정 상태 (rule §7)."""
    AUTO_SANITIZED = "auto_sanitized"        # 1단계: 명확한 위반 → 자동 순화/삭제 후 진행
    NEEDS_HUMAN_REVIEW = "needs_human_review"  # 2단계: 애매 → 담당자 판단 필요(발행 차단)
    BLOCKED = "blocked"                       # fail-safe/오정보 → 자동 발행 경로 차단


class SensitivityFlag(str, Enum):
    """메타데이터 민감도 플래그 (rule §6, §9)."""
    NONE = "none"
    MEDICAL_SENSITIVE = "medical_sensitive"   # 치료·효과·부작용 등 민감 키워드
    EVIDENCE_MISSING = "evidence_missing"     # RAG 근거 부족
    QUALITY_FAIL = "quality_fail"             # 문장 품질 미달
    PLAGIARISM = "plagiarism"                 # 표절 유사도 초과


@dataclass
class CollectedItem:
    """수집된 개별 자료 한 건 (rule §5 Step 2~3)."""
    channel: SourceChannel
    title: str
    url: str
    text: str = ""
    view_count: int = 0
    like_count: int = 0
    top_comments: list[str] = field(default_factory=list)
    relevance_score: float = 0.0  # Step 4에서 채워짐
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrendInsight:
    """트렌드 인사이트 리포트 (rule §5 Step 5, §9 산출물)."""
    rising_topics: list[str] = field(default_factory=list)
    sentiment_points: list[str] = field(default_factory=list)
    topic_candidates: list[str] = field(default_factory=list)


@dataclass
class Metadata:
    """블로그 초안 메타데이터 (rule §9 산출물)."""
    sensitivity_flags: list[SensitivityFlag] = field(default_factory=list)
    evidence_docs: list[str] = field(default_factory=list)  # 근거 문서
    similarity_score: float = 0.0                            # 저작권 유사도
    compliance_status: ComplianceStatus | None = None


@dataclass
class BlogDraft:
    """블로그 초안 (rule §5 Step 8, §9 산출물)."""
    title_options: list[str] = field(default_factory=list)  # 제목 3안
    body: str = ""
    hashtags: list[str] = field(default_factory=list)
    evidence_links: list[str] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)


@dataclass
class PipelineContext:
    """파이프라인 전 구간에서 공유되는 상태 컨테이너.

    각 Step은 이 컨텍스트를 입력받아 갱신한다. 사람 개입 게이트(§10)에
    걸리면 halted=True 로 표시하고 다음 단계 진행을 중단한다.
    """
    trigger: TriggerType
    seed_keywords: list[str] = field(default_factory=list)
    expanded_keywords: list[str] = field(default_factory=list)
    collected: list[CollectedItem] = field(default_factory=list)
    insight: TrendInsight | None = None
    draft: BlogDraft | None = None

    halted: bool = False           # 사람 개입 게이트에 걸려 중단됨
    halt_reason: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def halt(self, reason: str) -> None:
        """파이프라인을 중단하고 담당자에게 넘긴다 (rule §10)."""
        self.halted = True
        self.halt_reason = reason
