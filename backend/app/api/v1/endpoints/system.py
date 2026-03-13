import asyncio
from fastapi import APIRouter, Query
from ....schemas.common import CommonResponse
from ....services.automation.naver_map_service import naver_map_service
from ....services.gemini_service import gemini_service # 추가

router = APIRouter()

@router.get("/place-info", response_model=CommonResponse)
async def get_place_info_api(query: str = Query(..., description="검색할 가게명")):
    """
    네이버 지도에서 가게 정보를 검색하여 가져옴 (Gemini 요약 포함)
    """
    # 1. Playwright로 Raw Text 수집
    scraped_result = await asyncio.to_thread(naver_map_service.get_place_info, query)
    
    if scraped_result and scraped_result.get("raw_text"):
        # 2. Gemini로 핵심 정보 요약
        summary = await gemini_service.summarize_place_info(scraped_result["raw_text"])
        
        # 3. 가게명 등 기본 정보 유지
        summary["place_name"] = scraped_result["place_name"]
        # 나중에 블로그 글 쓸 때 참고할 전체 텍스트도 살짝 포함 (필요 시)
        summary["full_context"] = scraped_result["raw_text"][:1000] 

        return CommonResponse(
            success=True,
            message="가게 정보를 성공적으로 요약했습니다.",
            data=summary
        )
    else:
        return CommonResponse(
            success=False,
            message="정보를 수집하지 못했습니다.",
            error="NOT_FOUND"
        )

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
