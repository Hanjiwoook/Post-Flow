from fastapi import APIRouter
from ...schemas.common import CommonResponse

router = APIRouter()

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
