"""
글쓰기 AI에게 줄 지시문(프롬프트)을 만든다.

`docs/blog_format_spec.md`를 AI용 지시문으로 옮긴 것이다.
- 원본 글의 **형식만** 따르게 한다. 원문 문장 대신 "구조 뼈대"를 예시로 준다.
- 말투 참고 문장(style_samples)을 줄 때는 "문장 재사용 금지"를 함께 적는다.
- 내용은 사진, 가게 정보, 사용자 메모에서만 가져오게 한다 (지어내기 금지).
- 숫자 기준은 format_checker 상수를 그대로 써서, AI에게 시킨 기준과 채점 기준을 맞춘다.

post_writer(/analyze 글쓰기)가 이 지시문을 쓴다.
"""
from typing import Dict, List, Optional

from .format_checker import AI_PHRASES, HYPE_PHRASES, LONG_LINE_LEN, MAX_IMAGE_GROUP

# 가게 정보 인용구(명세서 3절)의 항목 순서와 이모지
INFO_QUOTE_FIELDS = [
    ("address", "🚩위치"),
    ("business_hours", "⏳영업시간"),
    ("phone", "📞전화번호"),
    ("amenities", "📰가게정보"),
    ("parking", "🚗주차"),
]

# 사실 목록에 보여 줄 항목 (앱 홈 화면이 보내는 키 → 이름)
FACT_LABELS = [
    ("place_name", "가게 이름"),
    ("address", "주소"),
    ("business_hours", "영업시간"),
    ("phone", "전화번호"),
    ("amenities", "편의시설"),
    ("parking", "주차"),
    ("waiting", "웨이팅"),
    ("ordered_menu", "주문한 메뉴"),
    ("visit_purpose", "방문 목적"),
    ("rating", "만족도(5점 만점)"),
    ("special_note", "사용자 메모"),
    ("owner_intro", "사장님 소개"),
    ("recent_event", "최근 소식"),
    ("place_vibe", "분위기 키워드"),
    ("visitor_insight", "방문자 리뷰 요약"),
]

MAX_SAMPLE_LINES = 8

ROLE = "너는 아래 블로그 주인의 글 형식을 그대로 지키면서 새 맛집 후기를 쓰는 작가야."

FORMAT_RULES = f"""\
[형식 규칙]
1. 글 구조 (이 순서를 지킨다)
   - 글: 인사(`안녕하세요 😊` / `안녕하세요~` / `안녕하세요~!` 중 하나로 시작) + 날씨·계절·상황 한마디 + 오늘 방문한 곳 소개. 인사는 매번 다르게 쓴다.
   - 인용구(style: default): 가게 이름만
   - 지도(map): 가게 이름
   - 인용구(style: quotation_line): 가게 정보. 아래 [가게 정보 인용구]를 그대로 쓴다.
   - 글: 방문 시점, 웨이팅 (사진 없이 시작해도 된다)
   - 반복: [사진 묶음] → [그 사진을 설명하는 글]. 순서는 외관 → 메뉴판 → 내부 → 주문한 메뉴 → 음식별 맛 묘사.
   - 마지막 글: 마지막 음식 설명에 이어서 맺음말을 쓴다.
2. 섹션 제목(`[외관]` 같은 태그), 구분선, 해시태그, 별점 기호(⭐⭐⭐)는 쓰지 않는다.
3. 사진 묶음
   - 한 묶음은 같은 장면이다. 2장 묶음이 기본이고, 1장이나 {MAX_IMAGE_GROUP}장은 가끔 쓴다. {MAX_IMAGE_GROUP}장을 넘기지 않는다.
   - 사진 묶음 뒤에는 그 사진을 설명하는 글이 온다. 사진 묶음을 연달아 두지 않는다.
4. 글 모양
   - 한 문장을 2~4줄로 짧게 끊는다. 한 줄은 10~16자가 기본이고 {LONG_LINE_LEN}자를 넘기지 않는다.
   - 블록 안에서 화제가 바뀌면 `.` 한 글자만 있는 줄로 띄운다.
   - 사진 뒤 설명 글은 3~6줄로, 맛·식감·양·온도·같이 먹으면 좋은 조합 같은 구체적인 정보를 담는다.
5. 말투
   - 기본은 `~요`체, `~습니다`를 가끔 섞는다. 1인칭은 `저는`.
   - 자주 쓰는 어미: `~더라구요`, `~구요`, `~거 같아요`, `~있어요!`, 가끔 `~습니당`.
   - 강조: `정말`, `너무`, `쫙~`. 이모지는 일부 문장 끝에만 1개 (😊 😋 🤩 💕 👍 😥 🤣 🌟). 모든 줄에 붙이지 않는다.
   - 단점이나 아쉬운 점도 가볍게 한두 줄 솔직하게 쓴다.
6. 쓰지 않는 표현
   - 과장 광고: {", ".join(HYPE_PHRASES)}
   - AI 같은 설명 말투: {", ".join(AI_PHRASES)}"""

SKELETON = f"""\
[구조 뼈대 예시] (형식만 보여 주는 뼈대다. <> 안은 실제 내용으로 바꾼다)
text   : 안녕하세요 😊 / <날씨·상황 한마디> / <오늘은 OO에 다녀왔어요>           (3~5줄)
quote  : <가게 이름>                                                    (style: default)
map    : <가게 이름>
quote  : 🚩위치 : <주소> / ⏳영업시간 : <...> / ...                        (style: quotation_line)
text   : <방문 요일·시간, 웨이팅>                                          (2~4줄)
image  : 외관 사진 2장
text   : <찾아가는 길, 외관 느낌>                                          (3~6줄)
image  : 메뉴판 사진 1장
text   : <메뉴 구성, 가격>                                               (3~6줄)
image  : 내부 사진 2장
text   : <좌석, 분위기, 기본 반찬>                                         (3~6줄)
image  : <음식A> 사진 2장
text   : <음식A 맛·식감·양 묘사>                                          (3~6줄)
image  : <음식B> 사진 2장
text   : <음식B 묘사> / . / . / <총평 한두 문장> / <재방문 의사 한 줄> / 👍<가게 이름> 추천합니다👍 / <감사 인사>
(각 줄은 실제 글에서 `\\n`으로 나눈다. 한 줄은 10~16자)"""

PHOTO_SELECTION = """\
[사진 고르기]
- 모든 사진을 쓸 필요는 없다. 글에 필요한 사진만 골라 쓴다.
- 같은 장면의 비슷한 사진이 3장 이상이면 가장 잘 나온 2장만 쓴다. 흔들리거나 흐린 사진은 뺀다.
- 영수증 사진은 글에 넣지 않는다 (카드번호 등 개인정보가 보인다). 가격과 주문 메뉴를 확인하는 데만 쓰고 excluded_images에 넣는다.
- image 블록의 image_indices에는 아래 [사진 목록]의 번호를 그대로 쓴다. 한 사진은 한 번만 쓴다.
- 쓰지 않은 사진은 모두 excluded_images에 번호와 이유(예: "사진 3, 4와 같은 파스타라서 뺐어요")를 적는다.
- writing_notes에는 어떤 정보를 글의 어디에 썼는지, 어떤 정보가 없어서 쓰지 않았는지 짧게 적는다."""

NO_FABRICATION = """\
[지어내기 금지]
- [사실 목록]과 [사진 목록]에 있는 내용만 쓴다. 가격, 맛, 웨이팅 시간, 직원 응대처럼 목록에 없는 사실은 지어내지 않는다.
- 맛은 사진에 보이는 것(색, 양, 구성)과 사용자 메모를 바탕으로 쓴다. 근거가 없으면 맛 평가를 단정하지 말고 보이는 모습을 묘사한다.
- 모르는 가게 정보 항목은 인용구에서 뺀다."""


def _clean(value) -> str:
    """빈 값, 'None', 기본값 '0' 같은 의미 없는 값은 빈 문자열로 만든다."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(v) for v in value if v)
    text = str(value).strip()
    return "" if text in ("", "None", "null", "0", "0.0") else text


def build_info_quote(facts: Dict) -> str:
    """가게 정보 인용구(명세서 3절). 모르는 항목은 뺀다."""
    lines = []
    for key, label in INFO_QUOTE_FIELDS:
        value = _clean(facts.get(key))
        if value:
            lines.append(f"{label} : {value}")
    return "\n".join(lines)


def build_fact_list(facts: Dict) -> str:
    lines = []
    for key, label in FACT_LABELS:
        value = _clean(facts.get(key))
        if value:
            lines.append(f"- {label}: {value}")
    return "\n".join(lines) if lines else "- (가게 정보 없음)"


def build_photo_list(photos: List[Dict]) -> str:
    """
    photos: [{"category": ..., "description": ..., "hint": ...}, ...] (리스트 순서 = 사진 번호)
    category/description이 없으면 AI가 첨부된 사진을 직접 보고 판단한다는 뜻으로 적는다.
    """
    if not photos:
        return "- (사진 없음)"
    lines = []
    for i, photo in enumerate(photos):
        category = _clean(photo.get("category"))
        description = _clean(photo.get("description"))
        if category or description:
            line = f"- 사진 {i} ({category or '분류 없음'}): {description}"
        else:
            line = f"- 사진 {i}: 첨부한 사진 {i}번을 직접 보고 판단"
        hint = _clean(photo.get("hint"))
        if hint:
            line += f" / 사용자 설명: {hint}"
        lines.append(line)
    return "\n".join(lines)


def build_similar_hint(similar_groups: List[List[int]]) -> str:
    """photo_dedup.group_similar 결과를 힌트로 만든다. 각 묶음은 선명한 사진이 앞에 있다."""
    if not similar_groups:
        return ""
    lines = ["[거의 같은 사진] (코드가 찾은 연사. 각 묶음에서 보통 1장만 쓰고, 앞 번호가 가장 선명하다)"]
    for group in similar_groups:
        lines.append("- 사진 " + ", ".join(str(i) for i in group))
    return "\n".join(lines)


def build_disclosure_rules(paid_by_self: bool, sponsored: bool, sponsor_detail: str) -> str:
    """내돈내산/협찬 표시. 협찬을 숨기면 광고 표시 규정 위반이 될 수 있어서 협찬이 우선이다."""
    if sponsored:
        detail = f" 제공받은 것: {sponsor_detail}." if sponsor_detail else ""
        return f"""\
[협찬 표시] (반드시 지킨다)
- 이 방문은 협찬이다.{detail}
- 첫 글 블록(인사) 안에 `업체로부터 ○○을 제공받아 작성한 글입니다`처럼 협찬 사실을 한 줄로 분명히 쓴다. 제공받은 것을 모르면 `업체로부터 협찬을 받아 작성한 글입니다`라고 쓴다.
- 맺음말에도 협찬 사실을 한 번 더 짧게 쓴다.
- `내돈내산`, `직접 결제`, `광고 아님`처럼 협찬과 반대되는 말은 쓰지 않는다. 제목에도 `내돈내산`을 넣지 않는다."""
    if paid_by_self:
        return """\
[내돈내산 표시]
- 직접 결제한 방문이다. 인사나 맺음말에 `내돈내산`을 한 번 쓴다. (영수증 사진은 넣지 않는다. 글로만 밝힌다)"""
    return """\
[내돈내산 표시]
- `내돈내산`이라는 말은 쓰지 않는다 (직접 결제했는지 확인되지 않았다)."""


def build_closing_rules(facts: Dict, closing_phrase: Optional[str]) -> str:
    rating = _clean(facts.get("rating"))
    lines = ["[맺음말]"]
    if rating:
        lines.append("- 마지막 글 블록 끝에 `.` 줄 두 개 → 총평 한두 문장 → 재방문 의사 한 줄(다음에 먹어 보고 싶은 메뉴와 함께) → `👍<가게 이름> 추천합니다👍` 순서로 쓴다.")
        lines.append(f"- 만족도는 {rating}점이다. 총평과 재방문 의사의 온도를 이 점수에 맞춘다 (낮으면 추천 줄을 빼도 된다).")
    else:
        # 만족도가 없으면 AI가 메모 분위기로 재방문·추천을 짐작해 쓰는 문제가 있었다 (2026-11-13 테스트)
        lines.append("- 마지막 글 블록 끝에 `.` 줄 두 개 → 총평 한두 문장 순서로 쓴다.")
        lines.append("- 만족도를 받지 못했다. 사용자 메모에 재방문이나 추천 의사가 직접 적혀 있을 때만 재방문 의사 한 줄과 `👍<가게 이름> 추천합니다👍`를 쓴다. "
                     "적혀 있지 않으면 두 줄을 모두 빼고, writing_notes에 '만족도와 재방문 의사 확인 필요'라고 적는다. 메모의 분위기로 짐작해서 쓰지 않는다.")
    if closing_phrase:
        lines.append(f"- 글의 마지막 줄은 이 감사 인사를 글자 하나 바꾸지 말고 그대로 쓴다: {closing_phrase}")
    else:
        lines.append("- 감사 인사 문구는 지어내지 말고 생략한다.")
    return "\n".join(lines)


def build_title_rules(facts: Dict) -> str:
    place = _clean(facts.get("place_name")) or "가게 이름"
    return f"""\
[제목]
- 두 패턴 중 하나를 쓴다:
  `[{place}] <지역> <특징> <메뉴> 맛집 <내돈내산/솔직리뷰/추천 중 1~2개>`
  `{place} <지역> <메뉴>맛집 솔직리뷰 (<대표 메뉴>, <검색 키워드>)`
- 지역은 주소에서 동/역 이름이나 랜드마크로 쓴다. 카페면 `맛집` 대신 `카페`.
- `내돈내산`은 [내돈내산 표시] 규칙에서 허용된 경우에만 쓴다. 협찬 글에는 쓰지 않는다."""


def build_style_samples(samples: List[str]) -> str:
    """말투 참고 문장. 원본 글의 일부만, 재사용 금지 경고와 함께 넣는다."""
    cleaned = []
    for sample in samples:
        lines = [line for line in sample.replace("​", "").split("\n") if line.strip()]
        if lines:
            cleaned.append("\n".join(lines[:MAX_SAMPLE_LINES]))
    if not cleaned:
        return ""
    body = "\n---\n".join(cleaned)
    return f"""\
[말투 참고] (줄 길이, 어미, 이모지 쓰는 방식만 참고한다. 아래 문장이나 표현을 그대로 가져다 쓰지 않는다. 내용은 이 가게의 사실로만 쓴다)
{body}"""


def build_writer_prompt(
    facts: Dict,
    photos: List[Dict],
    paid_by_self: bool = False,
    closing_phrase: Optional[str] = None,
    sponsored: bool = False,
    sponsor_detail: str = "",
    style_samples: Optional[List[str]] = None,
    similar_groups: Optional[List[List[int]]] = None,
) -> str:
    """
    글쓰기 AI에게 줄 전체 지시문을 만든다.

    facts: 앱 홈 화면이 보내는 가게 정보 (place_name, address, waiting, ordered_menu, ...)
    photos: 사진 분석 결과 목록. 순서가 사진 번호다. [{"category", "description", "hint"}]
    paid_by_self: 사용자가 직접 결제했다고 확인했을 때만 True (내돈내산 표기)
    sponsored: 협찬 방문이면 True. paid_by_self보다 우선한다 (협찬 사실을 글 첫 부분과 맺음말에 밝힌다)
    sponsor_detail: 제공받은 것 (예: "식사 2인")
    closing_phrase: 매 글 고정 감사 인사. 없으면 지어내지 않고 생략시킨다.
    style_samples: 말투 참고용 원본 글 일부. 각 글에서 앞 MAX_SAMPLE_LINES줄만 쓴다.
    similar_groups: photo_dedup.group_similar 결과 (거의 같은 사진 묶음)
    """
    info_quote = build_info_quote(facts)
    parts = [
        ROLE,
        FORMAT_RULES,
        SKELETON,
        build_style_samples(style_samples or []),
        PHOTO_SELECTION,
        build_disclosure_rules(paid_by_self, sponsored, _clean(sponsor_detail)),
        build_closing_rules(facts, closing_phrase),
        build_title_rules(facts),
        NO_FABRICATION,
        f"[가게 정보 인용구]\n{info_quote}" if info_quote else "[가게 정보 인용구]\n(알려진 항목이 없다. 정보 인용구는 빼고 가게 이름 인용구와 지도만 쓴다)",
        f"[사실 목록]\n{build_fact_list(facts)}",
        f"[사진 목록]\n{build_photo_list(photos)}",
        build_similar_hint(similar_groups or []),
    ]
    return "\n\n".join(p for p in parts if p)
