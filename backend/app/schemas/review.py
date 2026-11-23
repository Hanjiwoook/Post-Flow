"""파워블로거 검수(/review) 요청·응답 형식. Review는 AI 응답 형식으로도 쓴다."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from .post import ContentBlock, ImageInfo

CRITERIA = ["형식 일치", "사람 같은 말투", "맛 표현", "정보 충실도", "사실 근거", "사진과 글"]


class ReviewScore(BaseModel):
    criterion: str = Field(description="평가 기준 이름 (형식 일치, 사람 같은 말투, 맛 표현, 정보 충실도, 사실 근거, 사진과 글)")
    score: int = Field(description="1~5점. 5점이 가장 좋다")
    comment: str = Field(description="점수 이유 한두 문장")


class ReviewIssue(BaseModel):
    block_index: int = Field(description="문제가 있는 블록 번호. 제목이면 -1, 글 전체면 -2")
    kind: Literal["사실", "말투", "형식", "맛", "정보", "사진"]
    quote: str = Field(default="", description="문제가 있는 부분을 그 블록(제목이면 제목)에서 한 글자도 바꾸지 않고 옮겨 적은 것. "
                                               "여러 줄이면 줄바꿈도 그대로. 블록 전체가 문제거나 글 전체 지적이면 빈 칸")
    problem: str
    suggestion: str = Field(description="어떻게 고치면 좋은지. 사실이 필요한 보강은 questions로 사용자에게 묻는다")


class ReviewQuestion(BaseModel):
    question: str = Field(description="사용자에게 할 짧은 질문")
    reason: str = Field(description="이 답이 있으면 글의 어디가 좋아지는지")
    example_answers: List[str] = Field(description="바로 고를 수 있는 짧은 답 2~4개")


class Review(BaseModel):
    overall: str = Field(description="파워블로거 시선의 한 줄 총평")
    scores: List[ReviewScore]
    issues: List[ReviewIssue]
    missing_info: List[str] = Field(description="체크리스트 중 글에 빠진 정보")
    questions: List[ReviewQuestion] = Field(description="사용자만 아는 정보를 묻는 질문, 최대 5개")
    needs_revision: bool = Field(description="고쳐 쓰면 확실히 나아지는지")


class ReviewRequest(BaseModel):
    title: str
    blocks: List[ContentBlock]
    facts: dict = {}
    images: List[ImageInfo] = []
    writing_notes: List[str] = []


class ReviewResult(Review):
    format_check: Optional[dict] = None  # 서버에서 다시 돌린 규칙 검사
    usage: Optional[dict] = None
