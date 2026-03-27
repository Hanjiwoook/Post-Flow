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
