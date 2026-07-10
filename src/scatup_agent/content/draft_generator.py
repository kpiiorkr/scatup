"""Step 8 · 초안 생성 (rule §5 Step 8).

RAG 근거 기반으로 제목 3안 + 본문 + 해시태그를 생성한다.
MISTRAL_API_KEY 설정 시 Mistral API로 생성하고, 미설정이거나 호출 실패 시
기획안·근거를 조립하는 템플릿 방식으로 자동 폴백한다 (rule §4-2: 실패해도 전체 중단 금지).

주의: 여기서 생성된 본문은 Step 9(의료법 준수 필터링)를 반드시 통과해야 하며,
이 단계를 우회하지 않는다 (rule §7, §5 Step 9는 필수 게이트).
"""
from __future__ import annotations

import json
import re

import requests

from config.settings import settings

from ..models.schemas import BlogDraft, Metadata

_TIMEOUT_SECONDS = 60
_MAX_ATTEMPTS = 3   # 외국 문자 섞인 손상 출력 시 재생성 최대 횟수

_SYSTEM_PROMPT = """너는 scatup의 블로그 콘텐츠 작성 보조 에이전트다.
타겟 고객: 40~50대, 남녀 약 6:4, 효도상품·가족소통 니즈.
톤: 타겟에게 말 걸듯 따뜻하고 차분하게, 근거 중심으로 서술한다.
절대 금지: 치료효과를 단정·보장하는 표현('완치', '100% 효과', '부작용 없음' 등), \
특정인의 치료 경험담으로 효과를 오인시키는 서술, 다른 병원·의료인과의 비교/우수성 주장.
근거 기반 작성(중요): 본문의 사실·용어·수치는 아래에 제공되는 '근거 자료'에 있는 내용만 사용한다. \
특히 보청기 종류 이름(귀걸이형 BTE·오픈형 RIC·귓속형 ITE/ITC/CIC), 지원 조건·비율·금액, 통계·연구는 \
근거 자료의 표기를 그대로 따르고, 네 자체 지식으로 새 명칭·수치를 만들지 마라. \
근거에 없는 구체 사실은 일반적인 서술로만 쓰거나 생략한다.
출처 표기 규칙: 본문에 내부 파일명(예: 01_난청의_이해.md)이나 대괄호 파일 출처([...]) 표기를 절대 쓰지 마라. \
근거는 자연스러운 문장으로 녹이고, 필요하면 '국민건강보험공단' 같은 공신력 있는 기관을 언급한다.
언어: 반드시 한국어(한글)와 숫자로만 쓴다. 한자·러시아어·일본어 등 외국 문자나 \
소문자 영어 단어를 섞지 마라. 예) '耳鳴' → '이명', 'sound therapy' → '소리 치료', \
'carefully' → '조심스럽게'. 단, 보청기 종류(귀걸이형 BTE·오픈형 RIC·귓속형 ITE/ITC/CIC), \
dB, TV 같은 표준 약어는 대문자 그대로 정확히 표기한다.
다양성: 매번 다른 도입·구성·표현으로 쓰고 상투적 문구를 피하라. 주어진 목차 구조를 따르라.
반드시 JSON만 응답한다. 형식: {"titles": ["제목1", "제목2", "제목3"], "body": "본문(마크다운)", "hashtags": ["#태그1", ...]}"""


def generate(plan: dict, evidence: list[dict]) -> BlogDraft:
    """기획안(plan) + 근거(evidence)로 블로그 초안을 조립한다."""
    generated = _generate_with_mistral(plan, evidence) if settings.mistral_api_key else None

    if generated:
        titles, body, hashtags = generated
        print("[DRAFT] Mistral API로 초안 생성")
    else:
        titles, body, hashtags = _generate_from_template(plan, evidence)

    draft = BlogDraft(
        title_options=titles,
        body=body,
        hashtags=hashtags,
        evidence_links=[e["doc"] for e in evidence],
        metadata=Metadata(evidence_docs=[e["doc"] for e in evidence]),
    )
    print(f"[DRAFT] 제목 {len(titles)}안 + 본문 {len(body)}자 + 해시태그 {len(hashtags)}개 생성")
    return draft


def _generate_with_mistral(plan: dict, evidence: list[dict]) -> tuple[list[str], str, list[str]] | None:
    """Mistral로 초안을 생성한다.

    생성물에 외국 문자·영어가 섞이면 '손상된 출력'으로 보고 지우지 않고 재생성한다.
    (외국 문자를 지우기만 하면 '이것만'→'이 만'처럼 글자가 빠진 불완전한 문장이 남기 때문)
    끝까지 온전한 한글을 못 얻으면 None → 템플릿 폴백.
    """
    user_prompt = _build_user_prompt(plan, evidence)
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        raw = _mistral_once(user_prompt)
        if raw is None:
            continue  # API 오류 → 재시도
        titles, body, hashtags = raw
        # 단어를 깨뜨리는 외국 문자(악센트 라틴·키릴·한자 등)가 섞이면 '손상'으로 보고 재생성
        if _has_foreign_script(titles + [body]):
            print(f"[DRAFT] 생성물에 외국 문자 감지(단어 손상) → 온전한 한글로 재생성 ({attempt}/{_MAX_ATTEMPTS})")
            continue
        # 분리된 소문자 영어 단어('sound therapy' 등)는 제거 (대문자 약어 BTE·TV는 보존)
        return [_strip_english(t) for t in titles], _strip_english(body), hashtags
    print("[DRAFT] 온전한 한글 생성 실패 → 템플릿 방식으로 폴백")
    return None


def _mistral_once(user_prompt: str) -> tuple[list[str], str, list[str]] | None:
    """Mistral Chat API 1회 호출 (실패 시 None)."""
    try:
        resp = requests.post(
            f"{settings.mistral_api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.mistral_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.mistral_model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.75,
            },
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
        titles = [str(t).strip() for t in list(parsed["titles"])[:3]]
        body = str(parsed["body"])
        if not titles or not body:
            raise ValueError("titles/body 비어있음")
        return titles, body, list(parsed.get("hashtags", []))
    except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as err:
        print(f"[DRAFT] Mistral 호출 실패({err})")
        return None


def _has_foreign_script(texts: list[str]) -> bool:
    """한글 단어에 섞이면 글자를 깨뜨리는 외국 문자(악센트 라틴·키릴·한자·가나 등)가 있는지.

    이런 문자는 '이것만'→'이čá만'처럼 음절을 대체해 문장을 불완전하게 만들므로 재생성한다.
    (분리된 소문자 영어는 재생성 대상이 아니라 제거 대상 → _strip_english)
    """
    return bool(re.search(r"[À-ͯͰ-ԯ֐-ۿ฀-๿぀-ヿ㐀-鿿Ḁ-ỿ]", " ".join(texts)))


def _strip_english(text: str) -> str:
    """분리된 영어 단어를 제거한다. 소문자 단어(sound)뿐 아니라 대문자로 시작하는
    단어(Emergency·Consensus·Lancet)도 지운다. 전부 대문자 약어(BTE·RIC·CIC·ITE·ITC·TV)와
    dB는 보존한다(대문자 시작+소문자 패턴이 아니라서 자동으로 남는다)."""
    text = re.sub(r"(?<![A-Za-z])(?:[a-z]{2,}|[A-Z][a-z]+)(?![A-Za-z])", "", text)
    text = re.sub(r"\(\s*[/·:,\s]*\)", "", text)   # 내용 없이 남은 괄호((), (예:) 등)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r" +([,.!?)|·])", r"\1", text)


def _build_user_prompt(plan: dict, evidence: list[dict]) -> str:
    outline = "\n".join(f"- {sec}" for sec in plan.get("outline", []))
    sentiments = "\n".join(f"- {s}" for s in plan.get("sentiment_points", []))
    # 근거는 내용만 제공 (파일명을 노출하지 않아 본문에 파일명이 새어들지 않도록)
    evidence_block = "\n\n".join(
        f"(근거 {i}) {e['snippet']}" for i, e in enumerate(evidence, 1)
    ) or "(근거 문서 없음)"

    return f"""주제: {plan.get('main_topic', '')}
SEO 키워드: {', '.join(plan.get('seo_keywords', []))}
목차:
{outline}

독자 감성 포인트:
{sentiments or '(없음)'}

아래는 검증된 '근거 자료'다. 본문의 사실·용어·수치는 반드시 이 자료 안의 내용을 근거로 삼아 작성하고,
자료에 없는 구체 명칭·수치는 지어내지 마라. (특히 보청기 종류 이름은 자료 표기를 그대로 사용)
근거 자료:
{evidence_block}

위 정보로 블로그 글의 제목 3안, 본문(목차를 반영한 마크다운, 근거 자료 기반), 해시태그 5~7개를 JSON으로 작성해라."""


def _generate_from_template(plan: dict, evidence: list[dict]) -> tuple[list[str], str, list[str]]:
    """기획안·근거를 조립하는 템플릿 방식 (Mistral 미설정/실패 시 기본 동작)."""
    main_topic = plan.get("main_topic", "부모님 청력 관리 가이드")
    seo = plan.get("seo_keywords", [])

    titles = [
        main_topic,
        f"{seo[0]}, 부모님을 위해 알아봤습니다" if seo else "부모님 청력, 지금 점검해야 하는 이유",
        "부모님이 자꾸 되물으신다면 — 자녀가 먼저 챙기는 청력 관리",
    ]
    body = _build_body(plan, evidence)
    hashtags = ["#" + kw.replace(" ", "") for kw in seo[:5]] + ["#효도", "#부모님건강"]
    return titles, body, hashtags


def _build_body(plan: dict, evidence: list[dict]) -> str:
    outline = plan.get("outline", [])
    sentiments = plan.get("sentiment_points", [])
    sections: list[str] = []

    sections.append(
        "부모님과 통화할 때 같은 말을 두세 번 반복하게 되진 않으신가요? "
        "TV 볼륨이 예전보다 훌쩍 커졌다면, 그냥 지나칠 일이 아닐 수 있습니다. "
        "최근 커뮤니티와 영상에서도 부모님의 청력을 자녀가 먼저 챙기는 흐름이 뚜렷합니다."
    )

    if sentiments:
        bullet = "\n".join(f"- {s}" for s in sentiments)
        sections.append(f"### 요즘 사람들이 가장 궁금해하는 것\n{bullet}")

    for ev in evidence:
        doc_title = ev["doc"].rsplit(".", 1)[0].split("_", 1)[-1].replace("_", " ")
        sections.append(f"### {doc_title}\n{ev['snippet']}")

    sections.append(
        "커뮤니티에는 '보청기만 하면 완치된다'는 광고성 글도 보이지만, "
        "보청기는 치료 기기가 아니라 듣기를 돕는 재활 도구이며 효과는 개인차가 있습니다. "
        "정확한 검사와 전문가 상담이 항상 먼저입니다."
    )
    sections.append(
        "가격이 부담된다면 청각장애 등록 시 국민건강보험의 보청기 급여(5년 1회)를 "
        "활용할 수 있습니다. 기준은 바뀔 수 있으니 국민건강보험공단(1577-1000)에서 "
        "최신 조건을 꼭 확인하세요. 가장 좋은 효도는 '다시 잘 들리는 일상'을 선물하는 일입니다."
    )

    outline_block = "\n".join(f"{i}. {sec}" for i, sec in enumerate(outline, 1))
    return f"## 목차\n{outline_block}\n\n" + "\n\n".join(sections)
