from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import List
from PIL import Image
import io

from ...services.gemini_service import gemini_service
from ...schemas.post import AnalyzeResult, PostPublishRequest, JobResponse
from ...schemas.common import CommonResponse

router = APIRouter()

@router.post("/analyze", response_model=CommonResponse[AnalyzeResult])
async def analyze_post(
    files: List[UploadFile] = File(...),
    style: str = Form("emotional")
):
    """
    SRS 2.2 이미지 분석 및 초안 생성 API
    """
    if len(files) > 10:
        return CommonResponse(success=False, message="이미지는 최대 10장까지만 가능합니다.", error="TOO_MANY_IMAGES")

    try:
        # 이미지 파일 읽기 (메모리 로드)
        pil_images = []
        for file in files:
            content = await file.read()
            image = Image.open(io.BytesIO(content))
            pil_images.append(image)
        
        # AI 서비스 호출
        result = await gemini_service.analyze_images(pil_images, style)
        
        return CommonResponse(
            success=True,
            message="이미지 분석 성공",
            data=result
        )

    except Exception as e:
        return CommonResponse(
            success=False,
            message="AI 분석 중 오류가 발생했습니다.",
            error=str(e)
        )

@router.post("/publish", response_model=CommonResponse[JobResponse])
async def publish_post(request: PostPublishRequest):
    """
    SRS 2.3 포스팅 최종 발행 요청
    (현재는 Mock 응답 반환)
    """
    # TODO: 실제 비동기 Job Queue (Celery/Redis) 연동 필요
    
    return CommonResponse(
        success=True,
        message="발행 작업이 시작되었습니다.",
        data=JobResponse(
            job_id="mock_job_12345",
            status="processing"
        )
    )
