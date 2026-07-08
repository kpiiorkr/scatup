# scatup 블로그 콘텐츠 AX 에이전트

난청·보청기·치매 관련 트렌드를 주기적으로 추적하고, 근거 기반 블로그 초안을
생성해 담당자의 **검수·승인 중심 워크플로우**를 지원하는 에이전트의 기본 틀입니다.

> 운영 규칙 전문은 [`CLAUDE.md`](./CLAUDE.md) 를 참고하세요. 코드의 각 모듈은
> 이 규칙 문서의 섹션(§)과 1:1로 대응됩니다.

## 핵심 원칙

- 규칙·패턴이 명확한 일은 자동화, 판단이 필요한 일은 사람이 최종 결정
- **발행은 절대 자동으로 하지 않음** — 에이전트는 초안·검수 대기 등록까지만
- 의료법 준수가 최우선 (fail-safe: 자동 통과 절대 금지)

## 프로젝트 구조

```
scatup-blog-ax-agent/
├── CLAUDE.md                  # 운영 규칙 (팀 기획 = rule 파일)
├── config/
│   └── settings.py            # 임계치·쿼터·대상 채널·API 설정
├── src/scatup_agent/
│   ├── main.py                # 엔트리 포인트
│   ├── pipeline.py            # Step 1~9 오케스트레이터 + 사람 개입 게이트
│   ├── trigger/scheduler.py   # §2 정기/이벤트 트리거
│   ├── input/validator.py     # §4 입력 검증
│   ├── collectors/            # Step 1~3 (키워드 확장·네이버·유튜브)
│   ├── processing/            # Step 4~5 (정제·인사이트)
│   ├── content/               # Step 6~8 (기획·RAG·초안)
│   ├── compliance/            # Step 9 의료법 준수 (핵심)
│   ├── decision/branches.py   # §6 판단 분기
│   ├── exceptions/handlers.py # §8 예외 처리
│   ├── output/                # §9 산출물 전달·검증
│   └── models/schemas.py      # 데이터 모델
├── data/knowledge_base/       # RAG 난청 5종 문서 위치
└── tests/
```

## 실행 방법

뼈대 상태에서도 표준 라이브러리만으로 전체 흐름을 확인할 수 있습니다.

```bash
git clone <이 저장소 URL>
cd scatup-blog-ax-agent

# 흐름 확인 (stub 실행) — 프로젝트 루트에서
python run.py

# 테스트
python -m pytest -q
```

실제 구현 시:

```bash
cp .env.example .env      # API 키 입력
pip install -r requirements.txt   # 필요한 라이브러리 주석 해제 후
```

## 팀 작업 분담 가이드

각 모듈은 독립적으로 구현 가능하도록 분리되어 있습니다. `# TODO(담당)` 주석이
채워 넣을 지점입니다.

| 영역 | 파일 | 대응 규칙 |
|---|---|---|
| 트리거 | `trigger/scheduler.py` | §2 |
| 키워드 확장 | `collectors/keyword_expander.py` | Step 1 |
| 네이버 수집 | `collectors/naver_collector.py` | Step 2 |
| 유튜브 수집 | `collectors/youtube_collector.py` | Step 3 |
| 정제·인사이트 | `processing/` | Step 4~5 |
| 기획·RAG·초안 | `content/` | Step 6~8 |
| **의료법 준수** | `compliance/` | **Step 9 / §7 (최우선)** |
| 출력·전달 | `output/` | §9 |

## 주의

- `.env` 는 절대 커밋하지 않습니다 (`.gitignore` 에 포함됨).
- `compliance/` 는 서비스 리스크와 직결되므로 리뷰 없이 병합하지 않습니다.
