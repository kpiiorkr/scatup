# GitHub Actions 정기 실행 + Issues 검수 워크플로우 — 설계

- 작성일: 2026-07-10
- 대상 저장소: https://github.com/kpiiorkr/scatup
- 관련 규칙: CLAUDE.md §1(핵심 원칙), §2(트리거), §7(의료법), §9(출력·전달), §10(사람 개입 게이트)

## 1. 목표

블로그 콘텐츠 AX 에이전트를 **GitHub Actions cron으로 정기 실행**하고, 생성된 초안을
**GitHub Issue로 등록**해 여러 팀원이 나눠서 검수·승인할 수 있게 한다. 내 PC가 꺼져 있어도
GitHub 서버가 대신 실행하며, 검수 상태(승인/반려)는 GitHub 계정 기반으로 팀 전원이 공유한다.

해결하는 문제:
- 기존 정적 대시보드는 승인/반려를 브라우저 `localStorage`에만 저장 → 다른 기기·사람과 공유 불가.
- 파이프라인을 수동(`python run.py`)으로만 실행 → 정기 자동화 없음.

## 2. 범위

### 포함
- `.github/workflows/pipeline.yml` — 매일 cron + 수동 실행(workflow_dispatch)
- 실행 게이트: 급상승 감지 시 즉시 / 정기는 3일 주기 / 둘 다 아니면 종료
- 모든 초안을 GitHub Issue로 생성 (cleared / attention 모두)
- 열린 Issue 제목 기반 중복 방지
- GitHub 기본 알림 사용 (팀 repo watch)

### 제외 (범위 밖)
- 별도 이메일/Slack 발송 (GitHub 기본 알림으로 대체)
- 담당자 자동 배정(assignee) — 팀 자율 검수
- `data/outputs/run_*` 파일 저장 및 `build_dashboard.py` 대시보드 (파이프라인에서 미사용)
- 회차 간 키워드 누적(`discovered_keywords.json` 되커밋) — 매 실행 기본 시드로 시작.
  §5 Step1 "보강"은 이후 독립 기능으로 추가 가능.

## 3. 전체 흐름

```
매일 00:00 UTC(=09:00 KST)  GitHub Actions cron  (+ 수동 실행 버튼)
   │
   ├─ checkout → setup-python → pip install -r requirements.txt
   ├─ python run.py
   │    ├─ [트리거 게이트] 오늘 초안을 만들까? (4장)
   │    │      급상승 O → RISING_KEYWORD 즉시 진행
   │    │      급상승 X + 최근 정기 Issue 3일 경과 → SCHEDULED 진행
   │    │      그 외 → 조용히 종료 (no-op)
   │    ├─ 파이프라인 Step 1~9 (기존 로직 그대로)
   │    └─ deliver(ctx) → 중복 아니면 GitHub Issue 생성
   │
   └─ 팀원: repo watch → 알림 → Issue에서 검수 → 라벨로 승인/반려 → 사람이 직접 발행
```

## 4. 트리거 게이트 (매일 실행 + 3일 정기)

GitHub Actions는 정해진 시각(cron)에만 실행 가능하고 "급상승 발생 순간 실행"은 불가능하므로,
**매일 실행하며 그 안에서 급상승을 감지**하는 방식으로 §2를 근사한다.

`main.py` 시작부에 초안 생성 여부 판단을 추가:

1. `scheduler.detect_event_trigger()`로 데이터랩 급상승 확인.
2. **급상승 O** → `TriggerType.RISING_KEYWORD`로 즉시 진행.
3. **급상승 X** → 최근 `trigger:scheduled` 라벨 Issue의 생성일을 GitHub API로 조회:
   - `settings.run_interval_days`(=3)일 경과 → `TriggerType.SCHEDULED`로 진행.
   - 미경과 → 초안 생성 없이 종료 (오늘은 감지만 한 no-op 날).
4. **로컬(GITHUB_TOKEN 없음)** → 게이트를 건너뛰고 항상 실행 (개발·테스트 편의).

"마지막 정기 실행일"은 파일 없이 **Issue 생성일로 역산** → Issue 단일 창구 원칙 유지.

## 5. Issue 형식

- **제목:** `[초안 검수] {대표 제목}`
  - 대표 제목 = `draft.title_options[0]`
- **본문 (마크다운):** 기존 `deliverer._render_draft` + `_render_report` 결과를 재활용
  - 상태 / 민감도 플래그 / 저작권 유사도
  - 제목 3안, 본문, 해시태그, 근거 링크
  - 트렌드 인사이트 리포트(급상승 토픽·감성 포인트·소재 후보·상위 수집자료)
  - 하단 **사람 개입 체크리스트 (§10)**:
    ```
    - [ ] 팩트체크
    - [ ] 브랜드보이스 체크
    - [ ] 발행 승인 (승인 후 사람이 직접 발행)
    ```
- **라벨:**

  | 라벨 | 의미 | 부착 조건 |
  |---|---|---|
  | `scatup:draft` | 모든 초안 (조회·중복판단용) | 항상 |
  | `trigger:scheduled` | 정기 트리거 | trigger=SCHEDULED |
  | `trigger:rising` | 급상승 트리거 | trigger=RISING_KEYWORD |
  | `승인 대기` | AI 자동검수 통과(cleared) | ctx.halted=False |
  | `🚨담당자 판단 필요` | attention(의료법 2단계/fail-safe/근거부족 등) | ctx.halted=True |

- **assignee:** 없음 (팀 자율 검수).

## 6. 중복 방지

기존 `_is_duplicate`(로컬 `run_*/draft.md` glob) → **열린 `scatup:draft` Issue 제목 조회**로 대체.
- `github_issues.open_draft_titles()`가 정규화된 제목 집합 반환.
- 신규 초안의 정규화 대표 제목이 집합에 있으면 생성 생략(로그 남김).
- 정규화 규칙은 기존 `_norm`(공백 제거)을 재사용.

## 7. 모듈 설계 (파이썬이 직접 API 호출 + 모듈 분리)

### 신규: `src/scatup_agent/output/github_issues.py`
GitHub REST API를 `requests`로 호출 (새 의존성 없음).

- `create_issue(title: str, body: str, labels: list[str]) -> str | None`
  - 생성된 Issue URL 반환, 실패/토큰없음 시 `None`.
- `open_draft_titles() -> set[str]`
  - 열린 `scatup:draft` Issue 제목을 정규화해 반환 (중복 판단용).
- `days_since_last_scheduled() -> int | None`
  - 최근 `trigger:scheduled` Issue 생성일로부터 경과 일수. 없거나 토큰없음 시 `None`.
- 내부: `_token()`(env `GITHUB_TOKEN`), `_repo()`(env `GITHUB_REPOSITORY`, 없으면 settings), `_request()`.
- **토큰/레포 정보 없으면 모든 함수가 안전하게 `None`/빈값 반환** → 호출부가 콘솔 폴백.

### 수정: `src/scatup_agent/output/deliverer.py`
- `deliver(ctx)`:
  - 초안이 있으면 제목/본문/라벨 구성 → `github_issues.open_draft_titles()`로 중복 체크 →
    중복 아니면 `github_issues.create_issue(...)`.
  - **토큰 없음(로컬 개발)** → 정상 폴백: `_notify()` + 본문 콘솔 출력 (실패 아님).
  - **토큰 있는데 생성 실패(Actions 실제 오류)** → 9장대로 로그 + 본문 출력 후 실패 종료.
- `_render_draft` / `_render_report`는 **그대로 유지**하고 Issue 본문 조립에 재사용.
- 제거: `_save_outputs`(파일 저장), 파일 기반 `_is_duplicate`.

### 수정: `src/scatup_agent/main.py`
- 4장 트리거 게이트 로직 추가. no-op 날은 파이프라인을 돌리지 않고 로그 후 종료.

### 수정: `config/settings.py`
- `github_token`(env `GITHUB_TOKEN`), `github_repo`(env `GITHUB_REPOSITORY`) 추가.
- 라벨 문자열 상수 추가(`label_draft`, `label_trigger_*`, `label_cleared`, `label_attention`).

## 8. 워크플로우 & 시크릿

### `.github/workflows/pipeline.yml`
```yaml
name: scatup content pipeline
on:
  schedule:
    - cron: '0 0 * * *'      # 매일 00:00 UTC (= 09:00 KST)
  workflow_dispatch: {}       # 수동 실행 버튼
permissions:
  issues: write               # Issue 생성/조회
jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt
      - run: python run.py
        env:
          NAVER_CLIENT_ID:     ${{ secrets.NAVER_CLIENT_ID }}
          NAVER_CLIENT_SECRET: ${{ secrets.NAVER_CLIENT_SECRET }}
          YOUTUBE_API_KEY:     ${{ secrets.YOUTUBE_API_KEY }}
          LAW_API_KEY:         ${{ secrets.LAW_API_KEY }}
          MISTRAL_API_KEY:     ${{ secrets.MISTRAL_API_KEY }}
          GITHUB_TOKEN:        ${{ secrets.GITHUB_TOKEN }}   # 자동 발급
```

### Secrets 등록 (Settings > Secrets and variables > Actions)
- `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `YOUTUBE_API_KEY`, `LAW_API_KEY`, `MISTRAL_API_KEY`
- `GITHUB_TOKEN`은 GitHub이 실행마다 자동 발급 → 등록 불필요.

### 필요한 라벨
저장소에 라벨 사전 생성(또는 워크플로우/코드에서 없으면 생성):
`scatup:draft`, `trigger:scheduled`, `trigger:rising`, `승인 대기`, `🚨담당자 판단 필요`.

## 9. 에러 처리 / Fail-safe

- **§7 fail-safe 유지:** 법령 조회 실패·타임아웃·의료법 2단계(애매)는 기존대로 `ctx.halt(...)` →
  `🚨담당자 판단 필요` 라벨. 자동 통과 절대 없음.
- **Issue 생성 실패 (토큰 있음, API 오류):** 예외를 잡아 로그 + 초안 본문을 콘솔에 출력(유실 방지)
  후 파이프라인은 비정상 종료 코드로 마감(워크플로우가 실패로 표시되어 담당자가 인지).
  토큰 자체가 없는 로컬 실행은 오류가 아니라 콘솔 폴백(7장).
- **API 키 없는 소스:** 기존 §4-2대로 해당 소스만 skip, 전체 중단 없음.
- **중복 조회 실패:** 조회 실패 시 중복 아님으로 간주하고 생성(누락보다 중복이 안전).

## 10. 테스트

- `github_issues`: `requests` 모킹으로 생성 페이로드/라벨/헤더, `open_draft_titles` 정규화,
  `days_since_last_scheduled` 계산 검증.
- `deliver()`: 토큰 있음(Issue 생성 호출) / 없음(콘솔 폴백) 분기 검증.
- 트리거 게이트: 급상승 / 3일 경과 / 미경과(no-op) 세 갈래 검증.
- 기존 `tests/test_pipeline.py`가 깨지지 않도록 유지.

## 11. 미해결/후속 과제

- 회차 간 키워드 누적(§5 Step1 보강) — 필요 시 상태 저장 방식(예: 저장소 되커밋 또는 외부 저장)으로 별도 추가.
- 유튜브 조회수 급상승·이슈성 뉴스 이벤트 감지(§2) — 현재 데이터랩 급상승만 구현됨(기존 한계 그대로).
- 로컬 폴더(상위 `에이전트/`)와 원격 연결 정리 — scatup 하위 폴더는 이미 origin 연결됨.
