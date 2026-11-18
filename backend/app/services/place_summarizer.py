"""
가게 정보 정리 (/place-info): 네이버 지도에서 긁은 글자를 앱 입력 칸에 맞게 나눈다 (2026-11-18).

예전에는 Gemini가 했는데, 크레딧이 떨어져 실패해도 `except: return {}`로 숨겨서
앱에는 '성공'과 빈 칸만 갔다. 이제 Claude가 하고, 실패하면 LLMError로 알린다.

원칙: 원문에 있는 것만 옮긴다. 없으면 빈 칸 (글쓰기 단계가 빈 칸을 '정보 없음'으로 처리한다).
"""
from typing import List

from pydantic import BaseModel, Field

from .llm_client import LLMClient, LLMResult, llm, text_block

# 지도 페이지 글자는 탭 4개(홈·소식·정보·리뷰)를 합친 것이라 길다. 이보다 길면 뒤(리뷰 끝부분)를 자르고 로그로 알린다.
MAX_RAW_CHARS = 30000
SUMMARY_EFFORT = "low"   # 옮겨 적기라 깊게 생각할 필요가 없다


class RecentEvent(BaseModel):
    """소식 탭의 소식 하나. 글에 넣을지는 앱에서 사용자가 고른다 (11/18 사용자 결정, 기본은 넣지 않음)."""
    text: str = Field(description="소식 내용 한두 문장")
    date: str = Field(description="원문에 적힌 소식 날짜 그대로 (예: 2026.09.24.). 없으면 빈 문자열")


class PlaceInfo(BaseModel):
    """앱 홈 화면 입력 칸과 같은 이름. 원문에 없으면 빈 문자열이나 빈 목록."""
    address: str = Field(description="도로명 주소와 층. 예: 서울 구로구 연동로11길 9 케렌시아 1층")
    phone: str = Field(description="전화번호")
    business_hours: str = Field(description="요일별 영업시간, 라스트오더, 휴무일. 원문에 '영업 중'처럼 일부만 있으면 있는 만큼만")
    parking: str = Field(description="주차 가능 여부와 안내")
    amenities: List[str] = Field(description="편의시설 항목. 예: 단체 이용 가능, 무선 인터넷, 포장")
    owner_intro: str = Field(description="사장님·가게가 직접 쓴 소개 (찾아가는 길, 가게 소개 글)")
    # 예전에는 한 줄 글이라 지난 추석 영업 안내 같은 소식도 그대로 글에 들어갈 수 있었다 (11/18).
    # 날짜만으로는 쓸 만한 소식인지 정할 수 없어서, 목록으로 보여 주고 사용자가 고르게 한다.
    recent_events: List[RecentEvent] = Field(description="소식 탭의 소식·이벤트를 하나씩. 같은 소식이 두 번 나오면 하나만")
    place_vibe: List[str] = Field(description="리뷰와 소개에서 여러 번 나오는 분위기 키워드. 예: 혼밥하기 좋은, 아늑한")
    visitor_insight: str = Field(description="여러 방문자 리뷰에 공통으로 나오는 내용 요약 (인기 메뉴, 주문 방식, 좌석 등)")


SYSTEM = """너는 네이버 지도 가게 페이지의 글자를 정해진 칸에 옮겨 적는 도우미야.
이 결과는 블로그 글의 '사실'로 쓰이니까 원문에 있는 것만 옮겨 적어야 해."""

RULES = """[규칙]
- 원문에 있는 내용만 쓴다. 원문에 없는 칸은 빈 문자열("") 또는 빈 목록([])으로 둔다. 짐작해서 채우지 않는다.
- 주소, 전화번호, 영업시간은 원문 글자 그대로 옮긴다 (띄어쓰기 정리만 한다).
- 화면 버튼 글자(저장, 공유, 길찾기, 펼쳐보기, 더보기, 복사 등)는 옮기지 않는다.
- '영업 중', '영업 종료', '곧 영업 시작'처럼 페이지를 연 순간의 상태는 영업시간이 아니므로 빼고, 시간·라스트오더·휴무일만 옮긴다.
- visitor_insight는 여러 리뷰에 공통으로 나오는 내용만 2~4문장으로 쓴다. 한 사람만 말한 경험, 리뷰 작성자 이름·아이디, 날짜는 쓰지 않는다.
- 광고 문구처럼 과장하지 않는다."""


def build_place_prompt(place_name: str, raw_text: str) -> str:
    if len(raw_text) > MAX_RAW_CHARS:
        print(f"   ✂️ [place] 지도 글자가 {len(raw_text):,}자라 앞 {MAX_RAW_CHARS:,}자만 보냅니다")
        raw_text = raw_text[:MAX_RAW_CHARS]
    return f"{RULES}\n\n[가게 이름]\n{place_name}\n\n[네이버 지도 페이지 글자]\n{raw_text}"


async def summarize_place(place_name: str, raw_text: str, client: LLMClient = llm) -> LLMResult:
    """지도 글자를 PlaceInfo로 나눈다. 실패하면 LLMError가 난다."""
    prompt = build_place_prompt(place_name, raw_text)
    return await client.parse("summary", [text_block(prompt)], PlaceInfo, system=SYSTEM,
                              max_tokens=8000, effort=SUMMARY_EFFORT)
