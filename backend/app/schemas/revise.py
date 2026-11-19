"""검수 반영 고쳐쓰기(/revise) 요청·응답 형식. RevisedPost는 AI 응답 형식으로도 쓴다."""
from typing import List, Optional

from pydantic import BaseModel, Field

from .post import ContentBlock, ImageInfo
from .review import Review


class BlockEdit(BaseModel):
    block_index: int = Field(description="고칠 text 블록 번호 ([초안]의 [번호])")
    value: str = Field(description="그 블록의 고친 전체 내용. 줄바꿈은 \\n")


class RevisedPost(BaseModel):
    title: str = Field(description="고친 제목. 고칠 필요가 없으면 원래 제목 그대로")
    edits: List[BlockEdit] = Field(description="고친 text 블록만. 바꾸지 않은 블록은 넣지 않는다")
    change_notes: List[str] = Field(description="무엇을 왜 바꿨는지, 반영하지 못한 지적은 무엇인지 짧게")


class UserAnswer(BaseModel):
    question: str
    answer: str


class ReviseRequest(BaseModel):
    title: str
    blocks: List[ContentBlock]
    facts: dict = {}
    images: List[ImageInfo] = []
    writing_notes: List[str] = []
    review: Review
    answers: List[UserAnswer] = []


class ReviseResult(BaseModel):
    title: str
    blocks: List[ContentBlock]
    change_notes: List[str]
    edited_blocks: List[int]  # 실제로 바뀐 블록 번호 (앱에서 강조 표시용)
    format_check: Optional[dict] = None  # 고친 글로 다시 돌린 규칙 검사
    usage: Optional[dict] = None
