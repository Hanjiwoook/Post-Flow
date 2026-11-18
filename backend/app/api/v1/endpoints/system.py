import asyncio
from fastapi import APIRouter, Query
from ....schemas.common import CommonResponse
from ....services.automation.naver_map_service import naver_map_service
from ....services.llm_client import LLMError
from ....services.place_summarizer import summarize_place

router = APIRouter()

@router.get("/place-info", response_model=CommonResponse)
async def get_place_info_api(query: str = Query(..., description="검색할 가게명")):
    """
    네이버 지도에서 가게 정보를 가져와 앱 입력 칸(주소, 전화번호 등)에 맞게 나눈다 (Claude).
    지도 검색이나 정리에 실패하면 success=False와 이유를 돌려준다.
    """
    # 1. Playwright로 지도 페이지 글자 수집
    scraped = await asyncio.to_thread(naver_map_service.get_place_info, query) or {}
    raw_text = scraped.get("raw_text") or ""
    if not raw_text:
        return CommonResponse(success=False, message=scraped.get("error") or "가게 정보를 가져오지 못했습니다.",
                              error="NOT_FOUND")

    # 2. Claude로 칸 나누기. 예전 Gemini 코드는 실패해도 빈 칸과 '성공'을 돌려줬다 (11/18 확인).
    try:
        result = await summarize_place(scraped.get("place_name") or query, raw_text)
    except LLMError as e:
        return CommonResponse(success=False, message=f"가게 정보를 정리하지 못했습니다: {e}", error="SUMMARY_FAILED")

    data = result.parsed.model_dump()
    data["place_name"] = scraped.get("place_name") or query
    data["full_context"] = raw_text[:1000]  # 앱이 저장해 두는 원문 일부 (글쓰기에는 쓰지 않음)
    data["usage"] = {"model": result.model, "input_tokens": result.input_tokens,
                     "output_tokens": result.output_tokens, "cost_usd": result.cost_usd}
    return CommonResponse(success=True, message="가게 정보를 가져왔습니다.", data=data)

@router.get("/health", response_model=CommonResponse)
def health_check():
    """
    서버 상태 확인
    """
    return CommonResponse(
        success=True,
        message="System is operational",
        data={"status": "ok", "version": "1.0.0"}
    )
