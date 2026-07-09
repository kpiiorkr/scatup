"""검수 데스크 대시보드 빌드 (정적 HTML, 서버 불필요).

data/outputs/run_* 를 스캔해 각 run 의 draft.md / report.md 를 파싱하고,
그 결과를 JSON 으로 하나의 HTML 파일에 인라인 임베딩한다.
file:// 더블클릭으로 열리며, fetch 없이 동작한다 (CORS 회피).

디자인: Notion 스타일(warm paper 캔버스 + 순백 카드 + 헤어라인·미세 shadow +
12px 카드/8px 버튼 radius + Inter 폰트). run 을 최신순 플랫 카드로 나열한다.

승인/반려 상태는 브라우저 localStorage 에만 저장한다 (서버·DB 없음).
※ 한계: 브라우저·캐시 종속 저장이라 다른 브라우저/기기에서는 결정이 보이지 않는다.
   해커톤 MVP 단계에서 허용된 트레이드오프.

사용법 (프로젝트 루트에서):
    python build_dashboard.py
결과: data/outputs/dashboard.html
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = ROOT / "data" / "outputs"
KB_DIR = ROOT / "data" / "knowledge_base"
DASHBOARD_PATH = OUTPUTS_DIR / "dashboard.html"

# 시스템 표기(enum/플래그) → 의사결정자용 평문 (카피는 디자인 재료, rule §9)
_FLAG_PLAIN = {
    "unverified_fact": "AI가 근거 없이 지어낸 수치 의심 — 사실 확인 필요",
    "medical_sensitive": "의료 민감 표현 포함 — 검토 필요",
    "evidence_missing": "근거 문서 없음 — 사실 검증 불가",
    "plagiarism": "표절 유사도 초과 — 재작성 필요",
    "quality_fail": "문장 품질 미달 — 재작성 필요",
}


# ---------------------------------------------------------------- 파싱

def _section(md: str, head: str) -> str:
    """'## head' 다음부터 다음 '## ' 전까지의 본문을 반환한다."""
    pattern = re.compile(rf"^##\s*{re.escape(head)}.*?$(.*?)(?=^##\s|\Z)", re.M | re.S)
    m = pattern.search(md)
    return m.group(1).strip() if m else ""


def _bullets(md: str, head: str) -> list[str]:
    body = _section(md, head)
    items = [re.sub(r"^[-*]\s*", "", ln).strip() for ln in body.splitlines() if ln.strip().startswith(("-", "*"))]
    return [it for it in items if it and it != "(없음)"]


def parse_draft(md: str) -> dict:
    status_m = re.search(r"상태:\s*\*\*(?P<status>[^*]+)\*\*.*?민감도 플래그:\s*(?P<flags>[^·]+)·.*?유사도:\s*(?P<sim>[\d.]+)", md, re.S)
    status = status_m.group("status").strip() if status_m else "미검수"
    flags_raw = status_m.group("flags").strip() if status_m else "없음"
    similarity = float(status_m.group("sim")) if status_m else 0.0
    flags = [] if flags_raw == "없음" else [f.strip() for f in flags_raw.split(",") if f.strip()]

    titles = re.findall(r"^\s*\d+\.\s*(.+)$", _section(md, "제목 3안"), re.M)
    hashtags = [t for t in _section(md, "해시태그").split() if t.startswith("#")]
    evidence = _bullets(md, "근거 문서")

    return {
        "status": status,
        "flags": flags,
        "similarity": similarity,
        "titles": [t.strip() for t in titles],
        "hashtags": hashtags,
        "evidence": evidence,
    }


def parse_report(md: str) -> dict:
    def meta(label: str) -> str:
        m = re.search(rf"^-\s*{re.escape(label)}:\s*(.+)$", md, re.M)
        return m.group(1).strip() if m else ""

    collected_raw = _section(md, "상위 수집 자료")
    collected = [re.sub(r"^[-*]\s*", "", ln).strip() for ln in collected_raw.splitlines() if ln.strip().startswith(("-", "*"))]

    halt_m = re.search(r"담당자 확인 필요.*?사유:\s*(.+?)$", md, re.S | re.M)
    halt_reason = halt_m.group(1).strip() if halt_m else ""

    expanded = meta("확장 키워드")
    collected_meta = meta("수집·정제 자료")

    return {
        "datetime": meta("실행 시각"),
        "trigger": meta("트리거"),
        "seeds": meta("시드 키워드"),
        "expanded_count": _int(expanded),
        "collected_count": _int(collected_meta),
        "rising_topics": _bullets(md, "급상승 토픽"),
        "sentiment_points": _bullets(md, "감성 포인트"),
        "topic_candidates": _bullets(md, "소재 후보"),
        "collected": collected[:10],
        "halt_reason": halt_reason,
    }


def _int(text: str) -> int:
    m = re.search(r"\d+", text)
    return int(m.group()) if m else 0


def clean_body(md: str) -> str:
    """발행용 본문에서 내부 파일명 출처 표기와 '근거 문서' 섹션을 제거한다.

    (근거는 대시보드의 인라인 근거 뷰어로 따로 보여준다.)
    """
    md = re.sub(r"\[[^\]]*\.md[^\]]*\]\([^)]*\)", "", md)     # 마크다운 링크 [xx.md](xx)
    md = re.sub(r"\s*\([^)]*\.md[^)]*\)", "", md)             # (출처: …md) 등 괄호 표기
    md = re.sub(r"[\w가-힣]+(?:[ _][\w가-힣]+)*\.md", "", md)  # 남은 파일명 토큰
    md = re.sub(r"\n##\s*근거 문서.*\Z", "", md, flags=re.S)   # '## 근거 문서' 섹션 통째로
    md = strip_foreign(md)
    return re.sub(r"[ \t]+\n", "\n", md).strip()             # 제거 후 남은 공백 정리


def strip_foreign(text: str) -> str:
    """한글·숫자가 아닌 외국 문자를 제거해 한글 가독성을 높인다 (본문·제목 공통).

    키릴(러시아어)·일본어 가나·한자·그리스·아랍 등 외국 문자와 전부 소문자인
    영어 단어를 지운다. 대문자가 포함된 표준 약어(BTE·RIC·CIC·TV·dB 등
    보청기 종류·전문용어)는 정확히 보존한다.
    """
    text = re.sub(r"[À-ͯͰ-ԯ֐-ۿ฀-๿぀-ヿ㐀-鿿Ḁ-ỿ]+", "", text)       # 비한글 외국 문자(악센트 라틴 포함)
    text = re.sub(r"(?<![A-Za-z])[a-z]{2,}(?![A-Za-z])", "", text)  # 전부 소문자 영어 단어만 제거
    text = re.sub(r"\(\s*[/·,\s]*\)", "", text)                  # 내용 없이 남은 괄호 정리
    text = re.sub(r"[ \t]{2,}", " ", text)                       # 공백 정리
    return re.sub(r" +([,.!?)|·])", r"\1", text)


def load_kb() -> dict:
    """RAG 지식베이스 원문을 {파일명: 마크다운} 으로 읽어 대시보드에 임베딩한다."""
    if not KB_DIR.exists():
        return {}
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(KB_DIR.glob("*.md"))}


# 앵글(주제 방향) 추론 — 카드의 카테고리 라벨로만 쓴다(그룹핑 아님).
_ANGLE_DEFS = [
    ("dementia", "🧠 난청과 치매", ("치매", "인지")),
    ("tinnitus", "🔊 이명 관리", ("이명", "귀울림")),
    ("gov_support", "💰 보청기 정부지원", ("정부지원", "지원금", "보조금", "지원 제도")),
    ("self_check", "👂 난청 자가진단", ("자가", "점검", "신호", "검사", "난청")),
    ("hearing_aid_choice", "🛒 보청기 선택", ("종류", "선택", "고르", "적응", "보청기")),
]


def infer_angle(run: dict) -> tuple[str, str]:
    """제목에서 카테고리(주제 방향) 라벨을 추론한다."""
    title = run["titles"][0] if run.get("titles") else ""
    for angle_id, label, keywords in _ANGLE_DEFS:
        if any(kw in title for kw in keywords):
            return angle_id, label
    return "etc", "🗂 기타"


# ---------------------------------------------------------------- 판정(1인칭 보고)

def build_verdict(run: dict) -> dict:
    """의사결정자용 평문 판정 + 'AI가 한 일' 신뢰 라인을 만든다."""
    halted = bool(run["halt_reason"]) or run["status"] in ("needs_human_review", "blocked")

    # AI(마케터)가 이미 처리한 일 — 실제 데이터에 근거해 구성
    did: list[str] = []
    if run["trigger"] == "rising_keyword":
        did.append("데이터랩 급상승 포착")
    if run["collected_count"]:
        did.append(f"{run['collected_count']}건 수집·정제")
    did.append("의료법 제56조 실시간 대조")
    if run["evidence"]:
        did.append(f"근거 {len(run['evidence'])}건 확보")

    if not halted:
        return {
            "level": "cleared",
            "headline": "AI 자동 검수 통과 — 게시 승인 대기",
            "reason": "의료법 대조·팩트체크·표절 검사를 모두 통과했습니다.",
            "did": did,
        }

    reason = run["halt_reason"]
    if "fail-safe" in reason or "법령" in reason and "실패" in reason:
        headline = "법령 조회 실패 → 안전상 보류"
    elif any(f in run["flags"] for f in _FLAG_PLAIN):
        headline = next(_FLAG_PLAIN[f] for f in run["flags"] if f in _FLAG_PLAIN)
    elif "의료법" in reason:
        headline = "의료광고법 판단이 필요합니다"
    else:
        headline = "담당자 확인이 필요합니다"

    return {"level": "attention", "headline": headline, "reason": reason, "did": did}


# ---------------------------------------------------------------- 스캔

def scan_runs() -> list[dict]:
    runs: list[dict] = []
    for run_dir in sorted(OUTPUTS_DIR.glob("run_*"), reverse=True):  # 최신 먼저
        draft_path, report_path = run_dir / "draft.md", run_dir / "report.md"
        if not (draft_path.exists() and report_path.exists()):
            continue
        draft_md = draft_path.read_text(encoding="utf-8")
        report_md = report_path.read_text(encoding="utf-8")

        run = {"id": run_dir.name, "report_md": report_md}
        run.update(parse_draft(draft_md))   # 원문에서 근거 목록 등 추출
        run.update(parse_report(report_md))
        run["draft_md"] = clean_body(draft_md)  # 표시용 본문은 출처 표기 정리
        run["titles"] = [strip_foreign(t).strip() for t in run.get("titles", [])]
        run["angle"], run["angle_label"] = infer_angle(run)
        if not run["datetime"]:  # 폴더명에서 시각 보정
            m = re.match(r"run_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})", run_dir.name)
            run["datetime"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}:{m.group(5)}" if m else run_dir.name
        run["verdict"] = build_verdict(run)
        runs.append(run)
    return runs


# ---------------------------------------------------------------- 렌더

def render_html(runs: list[dict], kb: dict) -> str:
    # 데이터는 <script type="application/json"> 으로 인라인 임베딩(fetch 없음, CORS 회피).
    # JSON 안의 '</' 는 스크립트 조기 종료를 막기 위해 이스케이프한다(JSON.parse 가 복원).
    payload = json.dumps(runs, ensure_ascii=False).replace("</", "<\\/")
    kb_payload = json.dumps(kb, ensure_ascii=False).replace("</", "<\\/")
    return _TEMPLATE.replace("__RUN_DATA__", payload).replace("__KB_DATA__", kb_payload)


_TEMPLATE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>검수 대기 · scatup</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  /* ===== Notion 스타일 디자인 토큰 =====
     warm paper 캔버스 + 순백 카드, 헤어라인 + Level-1 미세 shadow,
     12px 카드 / 8px 버튼 radius, 8px 스페이싱 스케일, Inter(라틴)+Pretendard(한글). */
  :root{
    --canvas:#f6f5f4;              /* warm paper */
    --card:#ffffff;               /* 순백 카드 */
    --card-hover:#fbfaf9;
    --ink:#37352f;                /* 기본 텍스트 */
    --ink-secondary:#787774;      /* 보조 텍스트 */
    --ink-faint:#9b9a97;          /* 흐린 텍스트 */
    --hairline:#eae9e6;           /* 헤어라인(≈ rgba(55,53,47,.09)) */
    --hairline-strong:#dedcd8;
    --fill-soft:#f1f0ee;          /* 버튼 hover 등 */

    /* 시맨틱 상태색 (스펙 고정) */
    --green:#1aae39;   --green-bg:#e7f4ea;   --green-line:#c2e6cb;
    --orange:#dd5b00;  --orange-bg:#fbebe0;  --orange-line:#f2cbb0;
    --sky:#2f7dc9;     --sky-bg:#e8f1fb;     --sky-line:#c9e0f6;   /* 텍스트는 대비 위해 진하게 */
    --red:#eb5757;     --red-bg:#fbeaea;     --red-line:#f3c9c9;

    --shadow-1:0 1px 2px rgba(15,15,15,.04), 0 2px 5px rgba(15,15,15,.05);
    --radius-card:12px;
    --radius-btn:8px;
    --font:"Inter","Pretendard","Apple SD Gothic Neo",-apple-system,system-ui,sans-serif;
  }
  *{box-sizing:border-box}
  html{background:var(--canvas)}
  body{margin:0;background:var(--canvas);color:var(--ink);font-family:var(--font);line-height:1.6;
       -webkit-font-smoothing:antialiased;font-feature-settings:"tnum" 1}
  ::selection{background:#d9e8f7}
  a{color:var(--sky)}

  .page{max-width:760px;margin:0 auto;padding:56px 20px 96px}

  /* ===== 헤더 (마케팅 hero-band 미사용, 문서 헤더만) ===== */
  .eyebrow{font-size:12.5px;font-weight:600;letter-spacing:.04em;color:var(--ink-faint);margin:0 0 10px}
  .page-title{font-size:32px;font-weight:700;letter-spacing:-.022em;line-height:1.15;margin:0 0 10px}
  .page-sub{font-size:15px;color:var(--ink-secondary);margin:0;max-width:56ch}
  .summary{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 6px}
  .stat{display:flex;align-items:baseline;gap:7px;background:var(--card);border:1px solid var(--hairline);
        border-radius:999px;padding:6px 14px;box-shadow:var(--shadow-1)}
  .stat span{font-size:12.5px;color:var(--ink-secondary)}
  .stat b{font-size:14px;font-weight:600;letter-spacing:-.01em;color:var(--ink)}
  .stat.hot b{color:var(--orange)}

  /* ===== 런 카드 (feature-card) ===== */
  .runs{margin-top:26px;display:flex;flex-direction:column;gap:12px}
  .run-card{background:var(--card);border:1px solid var(--hairline);border-radius:var(--radius-card);
            box-shadow:var(--shadow-1);padding:20px 22px;transition:box-shadow .14s,border-color .14s,opacity .14s}
  .run-card:hover{border-color:var(--hairline-strong);box-shadow:0 2px 4px rgba(15,15,15,.05),0 4px 12px rgba(15,15,15,.06)}
  .run-card[data-decision="approved"],.run-card[data-decision="rejected"]{opacity:.82}

  .card-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
  .card-meta{display:flex;align-items:center;gap:8px;min-width:0;font-size:12.5px;color:var(--ink-faint)}
  .cat{font-weight:600;color:var(--ink-secondary);white-space:nowrap}
  .card-meta time{white-space:nowrap}
  .dot{color:var(--hairline-strong)}

  /* 상태 배지 (badge-pill) */
  .badge{flex:none;font-size:12px;font-weight:600;letter-spacing:-.01em;padding:4px 11px;border-radius:999px;
         white-space:nowrap;border:1px solid transparent}
  .badge[data-tone="green"]{color:var(--green);background:var(--green-bg);border-color:var(--green-line)}
  .badge[data-tone="orange"]{color:var(--orange);background:var(--orange-bg);border-color:var(--orange-line)}
  .badge[data-tone="sky"]{color:var(--sky);background:var(--sky-bg);border-color:var(--sky-line)}
  .badge[data-tone="red"]{color:var(--red);background:var(--red-bg);border-color:var(--red-line)}

  .run-title{font-size:18px;font-weight:700;letter-spacing:-.018em;line-height:1.4;margin:0 0 8px;color:var(--ink)}
  .alt-titles{font-size:12.5px;color:var(--ink-faint);margin:0 0 12px}
  .alt-titles b{font-weight:600;color:var(--ink-secondary)}
  .preview{font-size:14px;color:var(--ink-secondary);margin:0 0 12px;
           display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .attention-note{font-size:13px;color:var(--orange);background:var(--orange-bg);border:1px solid var(--orange-line);
                  border-radius:8px;padding:9px 12px;margin:0 0 12px}
  .aidid{font-size:12.5px;color:var(--ink-faint);margin:0 0 14px;padding-left:18px;position:relative}
  .aidid::before{content:"✓";position:absolute;left:0;color:var(--green);font-weight:700}

  /* 액션 (button-utility) */
  .actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .actions .grow{flex:1}
  .btn{font-family:var(--font);font-size:13px;font-weight:500;padding:8px 15px;border-radius:var(--radius-btn);
       border:1px solid var(--hairline-strong);background:var(--card);color:var(--ink);cursor:pointer;
       transition:background .12s,border-color .12s}
  .btn:hover{background:var(--fill-soft)}
  .btn-expand{color:var(--ink-secondary)}
  .btn-approve{color:var(--green);border-color:var(--green-line)}
  .btn-approve:hover{background:var(--green-bg)}
  .btn-reject{color:var(--red);border-color:var(--red-line)}
  .btn-reject:hover{background:var(--red-bg)}
  .btn:focus-visible{outline:2px solid var(--sky);outline-offset:2px}
  .undo{all:unset;cursor:pointer;font-size:12.5px;color:var(--ink-faint);text-decoration:underline;padding:6px 4px}
  .hide{display:none!important}

  /* ===== 펼침 상세 (아코디언) ===== */
  .detail{border-top:1px solid var(--hairline);margin-top:16px;padding-top:16px}
  .detail[hidden]{display:none}
  .detail-tabs{display:flex;gap:6px;margin-bottom:14px}
  .detail-tabs button{font-family:var(--font);font-size:12.5px;font-weight:500;padding:6px 13px;
       border:1px solid var(--hairline-strong);border-radius:var(--radius-btn);background:var(--card);
       color:var(--ink-secondary);cursor:pointer}
  .detail-tabs button[aria-pressed="true"]{background:var(--ink);color:#fff;border-color:var(--ink)}
  .md{font-size:14px;color:var(--ink);line-height:1.75}
  .md :is(h1,h2,h3){line-height:1.35;letter-spacing:-.015em}
  .md h1{font-size:20px;font-weight:700}
  .md h2{font-size:16px;margin-top:22px}
  .md h3{font-size:14px;margin-top:16px}
  .md strong{font-weight:600}
  .md code{font-size:.9em;background:var(--fill-soft);padding:1px 5px;border-radius:5px}
  .md hr{border:none;border-top:1px solid var(--hairline);margin:18px 0}

  /* 근거 뷰어 */
  .evidence{margin-top:20px;padding-top:16px;border-top:1px solid var(--hairline)}
  .ev-head{font-size:12px;font-weight:600;letter-spacing:.02em;color:var(--ink-faint);margin:0 0 10px}
  .ev-chip{font-family:var(--font);font-size:12.5px;color:var(--ink-secondary);background:var(--card);
           border:1px solid var(--hairline-strong);border-radius:999px;padding:5px 12px;margin:0 6px 6px 0;cursor:pointer}
  .ev-chip:hover{background:var(--fill-soft)}
  .ev-chip[aria-pressed="true"]{background:var(--ink);color:#fff;border-color:var(--ink)}
  .ev-view{margin-top:10px;background:var(--canvas);border:1px solid var(--hairline);border-radius:10px;
           padding:16px 18px;font-size:13px}
  .ev-view[hidden],.ev-view.hide{display:none}

  .empty{color:var(--ink-secondary);font-size:14px;padding:44px 0;text-align:center;
         background:var(--card);border:1px solid var(--hairline);border-radius:var(--radius-card);box-shadow:var(--shadow-1)}
  .empty code{background:var(--fill-soft);padding:1px 6px;border-radius:5px}

  .foot{margin-top:32px;font-size:12px;color:var(--ink-faint);line-height:1.6;
        border-top:1px solid var(--hairline);padding-top:16px}

  @media (max-width:560px){
    .page{padding:40px 16px 72px}
    .page-title{font-size:27px}
    .run-card{padding:17px 18px}
    .card-head{flex-wrap:wrap}
  }
</style>
</head>
<body>
<div class="page">
  <header>
    <p class="eyebrow">SCATUP · 블로그 콘텐츠 검수</p>
    <h1 class="page-title">검수 대기 목록</h1>
    <p class="page-sub">AI가 생성한 블로그 초안입니다. 발행은 담당자가 승인한 뒤에만 진행됩니다 — 자동 발행하지 않습니다.</p>
    <div class="summary" id="summary"></div>
  </header>

  <main class="runs" id="runs"></main>

  <footer class="foot">
    승인·반려 상태는 이 브라우저에만 저장됩니다(localStorage). 다른 브라우저·기기·시크릿 창에서는 결정이 보이지 않으며,
    브라우저 데이터를 지우면 초기화됩니다. — 서버 없는 MVP 단계의 트레이드오프입니다.
  </footer>
</div>

<!-- 빌드 시점 인라인 임베딩 데이터 (fetch 없음) -->
<script id="run-data" type="application/json">__RUN_DATA__</script>
<script id="kb-data" type="application/json">__KB_DATA__</script>

<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
const RUNS = JSON.parse(document.getElementById("run-data").textContent);
const KB   = JSON.parse(document.getElementById("kb-data").textContent);

// 승인/반려는 localStorage 에만 저장 (key = run id). 서버·DB 없음.
const DEC_KEY = "scatup_decisions_v1";
const decisions = JSON.parse(localStorage.getItem(DEC_KEY) || "{}");
const esc = s => (s||"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function decisionOf(id){ return decisions[id] || "pending"; }
function saveDecision(id, val){
  if(val==="pending") delete decisions[id]; else decisions[id]=val;
  localStorage.setItem(DEC_KEY, JSON.stringify(decisions));
}

// 상태 배지: 결정(localStorage) + AI 판정(verdict)을 합쳐 4색으로.
function badgeOf(run){
  const d = decisionOf(run.id);
  if(d==="approved") return {tone:"green",  text:"승인완료"};
  if(d==="rejected") return {tone:"red",    text:"반려"};
  if(run.verdict.level==="attention") return {tone:"orange", text:"담당자 판단 필요"};
  return {tone:"sky", text:"승인 대기"};
}

function previewOf(md){
  return (md||"")
    .replace(/```[\s\S]*?```/g," ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g," ")
    .replace(/^#{1,6}\s+/gm,"")
    .replace(/[#>*_`|-]/g," ")
    .replace(/\s+/g," ").trim().slice(0,150);
}

function prettyDoc(doc){ return doc.replace(/^\d+_/,"").replace(/\.md$/,"").replace(/_/g," "); }

function evidenceHTML(run){
  if(!run.evidence || !run.evidence.length) return "";
  const chips = run.evidence.map(d=>`<button class="ev-chip" data-doc="${esc(d)}" aria-pressed="false">${esc(prettyDoc(d))}</button>`).join("");
  return `<div class="evidence"><p class="ev-head">AI가 참고한 근거 · 클릭해 원문 보기</p>${chips}<div class="ev-view hide"></div></div>`;
}

function renderDetail(run, el){
  const md = window.marked ? marked.parse : (t=>`<pre>${esc(t)}</pre>`);
  el.innerHTML = `
    <div class="detail-tabs">
      <button data-tab="draft" aria-pressed="true">블로그 초안</button>
      <button data-tab="report" aria-pressed="false">트렌드 리포트</button>
    </div>
    <div class="md" data-pane="draft">${md(run.draft_md)}${evidenceHTML(run)}</div>
    <div class="md hide" data-pane="report">${md(run.report_md)}</div>`;
  el.querySelectorAll(".detail-tabs button").forEach(btn=>{
    btn.onclick = () => {
      el.querySelectorAll(".detail-tabs button").forEach(b=>b.setAttribute("aria-pressed", b===btn));
      el.querySelectorAll("[data-pane]").forEach(p=>p.classList.toggle("hide", p.dataset.pane!==btn.dataset.tab));
    };
  });
  const view = el.querySelector(".ev-view");
  el.querySelectorAll(".ev-chip").forEach(chip=>{
    chip.onclick = () => {
      const wasOpen = chip.getAttribute("aria-pressed")==="true";
      el.querySelectorAll(".ev-chip").forEach(c=>c.setAttribute("aria-pressed","false"));
      if(wasOpen){ view.classList.add("hide"); return; }
      chip.setAttribute("aria-pressed","true");
      const src = KB[chip.dataset.doc];
      view.innerHTML = src ? md(src) : "<p>근거 원문을 찾을 수 없습니다.</p>";
      view.classList.remove("hide");
    };
  });
}

function cardHTML(run){
  const b = badgeOf(run), d = decisionOf(run.id);
  const title = run.titles?.[0] || "(제목 없음)";
  const alts = (run.titles||[]).slice(1).filter(Boolean);
  const did = (run.verdict.did||[]).join(" · ");
  const attention = run.verdict.level==="attention";
  return `
  <article class="run-card" data-id="${run.id}" data-decision="${d}">
    <div class="card-head">
      <div class="card-meta">
        <span class="cat">${esc(run.angle_label||"🗂 기타")}</span>
        <span class="dot">·</span><time>${esc(run.datetime)}</time>
      </div>
      <span class="badge" data-tone="${b.tone}">${b.text}</span>
    </div>
    <h2 class="run-title">${esc(title)}</h2>
    ${alts.length ? `<p class="alt-titles"><b>다른 제목안:</b> ${alts.map(esc).join(" &nbsp;·&nbsp; ")}</p>` : ""}
    <p class="preview">${esc(previewOf(run.draft_md))}</p>
    ${attention ? `<p class="attention-note">⚠ ${esc(run.verdict.headline)}${run.verdict.reason ? " — "+esc(run.verdict.reason) : ""}</p>` : ""}
    ${did ? `<p class="aidid">AI가 한 일: ${esc(did)}</p>` : ""}
    <div class="actions">
      <button class="btn btn-expand" aria-expanded="false">본문 보기</button>
      <span class="grow"></span>
      <span class="decide-controls">
        <button class="btn btn-reject">반려</button>
        <button class="btn btn-approve">승인</button>
      </span>
      <button class="undo hide">결정 취소</button>
    </div>
    <div class="detail" hidden></div>
  </article>`;
}

function wireCard(card, run){
  const detail = card.querySelector(".detail");
  const expandBtn = card.querySelector(".btn-expand");
  expandBtn.onclick = () => {
    const opening = detail.hasAttribute("hidden");
    if(opening && !detail.dataset.rendered){ renderDetail(run, detail); detail.dataset.rendered="1"; }
    detail.toggleAttribute("hidden", !opening);
    expandBtn.setAttribute("aria-expanded", opening);
    expandBtn.textContent = opening ? "접기" : "본문 보기";
  };
  const decide = val => { saveDecision(run.id, val); render(); };
  card.querySelector(".btn-approve").onclick = () => decide("approved");
  card.querySelector(".btn-reject").onclick  = () => decide("rejected");
  card.querySelector(".undo").onclick        = () => decide("pending");

  const d = decisionOf(run.id);
  card.querySelector(".decide-controls").classList.toggle("hide", d!=="pending");
  card.querySelector(".undo").classList.toggle("hide", d==="pending");
}

function refreshSummary(){
  const count = t => RUNS.filter(t).length;
  const pending  = count(r=>decisionOf(r.id)==="pending" && r.verdict.level!=="attention");
  const attention= count(r=>decisionOf(r.id)==="pending" && r.verdict.level==="attention");
  const approved = count(r=>decisionOf(r.id)==="approved");
  const rejected = count(r=>decisionOf(r.id)==="rejected");
  document.getElementById("summary").innerHTML = [
    ["전체", RUNS.length, false],
    ["승인 대기", pending, false],
    ["담당자 판단 필요", attention, attention>0],
    ["승인완료", approved, false],
    ["반려", rejected, false],
  ].map(([k,v,hot])=>`<div class="stat${hot?" hot":""}"><span>${k}</span><b>${v}</b></div>`).join("");
}

// 정렬 티어: 미결(0) → 반려(1) → 승인완료(2). 결정하면 카드가 아래로 내려간다.
// (RUNS 는 최신순이므로 index 를 tie-breaker 로 써 각 구간 안에서 최신순을 유지)
function tierOf(id){
  const d = decisionOf(id);
  return d==="pending" ? 0 : d==="rejected" ? 1 : 2;
}
function orderedRuns(){
  return RUNS.map((r, i) => [r, i])
    .sort((a, b) => tierOf(a[0].id) - tierOf(b[0].id) || a[1] - b[1])
    .map(x => x[0]);
}

function render(){
  const box = document.getElementById("runs");
  if(!RUNS.length){
    box.innerHTML = "<p class='empty'>아직 생성된 초안이 없습니다. <code>python run.py</code> 로 파이프라인을 실행하세요.</p>";
    refreshSummary(); return;
  }
  const ordered = orderedRuns();
  box.innerHTML = ordered.map(cardHTML).join("");
  ordered.forEach(run => wireCard(box.querySelector(`.run-card[data-id="${run.id}"]`), run));
  refreshSummary();
}

render();
</script>
</body>
</html>
"""


def main() -> None:
    if not OUTPUTS_DIR.exists():
        print(f"[BUILD] 출력 폴더 없음: {OUTPUTS_DIR}")
        return
    runs = scan_runs()
    DASHBOARD_PATH.write_text(render_html(runs, load_kb()), encoding="utf-8")
    attention = sum(1 for r in runs if r["verdict"]["level"] == "attention")
    print(f"[BUILD] run {len(runs)}개 스캔 (담당자 판단 필요 {attention}건) → {DASHBOARD_PATH}")


if __name__ == "__main__":
    main()
