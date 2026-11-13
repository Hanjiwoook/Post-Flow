from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class ImageInfo(BaseModel):
    path: str
    category: str  # EXTERIOR, PARKING, INTERIOR, MENU, FOOD_MAIN, FOOD_SIDE, RECEIPT, AMENITIES, MAP
    description: Optional[str] = None

class ContentBlock(BaseModel):
    type: str  # text, sticker, quote, divider, map, image
    value: Optional[str] = None
    style: Optional[str] = None # quote의 경우 box, line 등
    image_index: Optional[int] = None # 단일 이미지 (하위 호환)
    image_indices: List[int] = [] # 콜라주용 다중 이미지 인덱스

class ExcludedImage(BaseModel):
    index: int
    reason: str

class AnalyzeResult(BaseModel):
    draft_id: Optional[str] = None
    template_name: Optional[str] = None # 추가
    title: str
    content: str # 기존 하위 호환 유지
    blocks: List[ContentBlock] = [] # 레고 블록 구조 추가
    tags: List[str]
    facts: Optional[dict] = {}
    images: List[ImageInfo] = []
    image_paths: List[str] = []
    atmosphere: Optional[str] = None
    location: Optional[str] = None
    # Claude 글쓰기 결과 (2026-11 추가)
    excluded_images: List[ExcludedImage] = []  # AI가 뺀 사진과 이유
    writing_notes: List[str] = []              # 어떤 정보를 어디에 썼는지, 확인이 필요한 점
    format_check: Optional[dict] = None        # format_checker 채점 결과
    usage: Optional[dict] = None               # 모델, 토큰 수, 추정 비용

class PostPublishRequest(BaseModel):
    draft_id: str
    template_name: Optional[str] = None # 추가
    final_title: str
    final_content: str
    blocks: List[ContentBlock] = [] # 추가
    tags: List[str] = []
    facts: dict = {}
    platforms: List[str]
    images: List[ImageInfo] = []
    image_paths: List[str] = []

class RefineRequest(BaseModel):
    title: str
    content: str
    blocks: List[ContentBlock] = []  # 현재 본문 블록 데이터 (부분 수정용)
    facts: dict
    images: List[ImageInfo] = [] # 기존 이미지 정보 유지용 추가
    instruction: Optional[str] = None
    style: Optional[str] = "professional"
    template_name: Optional[str] = None # 추가

class PatchRequest(BaseModel):
    title: str
    blocks: List[ContentBlock]
    facts: dict
    images: List[ImageInfo] = [] # 기존 이미지 정보 유지용
    style: Optional[str] = "professional"
    template_name: Optional[str] = None

class JobResponse(BaseModel):
    job_id: str
    status: str

# --- 추가된 DB 관련 스키마 ---

class PostBase(BaseModel):
    title: str
    platform: str
    status: str
    post_url: Optional[str] = None

class PostCreate(PostBase):
    pass

class PostResponse(PostBase):
    id: int
    template_name: Optional[str] = None # 추가
    content: Optional[str] = None
    blocks: List[ContentBlock] = [] # 추가
    images: Optional[List[ImageInfo]] = []
    image_paths: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    facts: Optional[dict] = {}
    created_at: datetime

    class Config:
        from_attributes = True
