from typing import List, Optional
from pydantic import BaseModel

class AnalyzeResult(BaseModel):
    """
    이미지 분석 결과 (초안)
    SRS 2.2 Response Data 구조
    """
    draft_id: Optional[str] = None # 임시 저장 ID (DB 연동 후 사용)
    title: str
    content: str
    tags: List[str]
    # 추가 분석 정보 (선택 사항)
    atmosphere: Optional[str] = None
    location: Optional[str] = None

class PostPublishRequest(BaseModel):
    """
    SRS 2.3 포스팅 최종 발행 요청 Body
    """
    draft_id: str
    final_title: str
    final_content: str
    platforms: List[str] # ["naver", "tistory"]

class JobResponse(BaseModel):
    """
    비동기 작업 응답 (Job Queue)
    """
    job_id: str
    status: str # processing, completed, failed
