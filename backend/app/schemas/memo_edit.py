"""메모로 부분 고치기(/memo-edit) 요청·응답 형식. MemoEditOutput은 AI 응답 형식으로도 쓴다.

AI는 고친 글(value)만 낸다. 원래 글(before)은 서버가 실제 블록에서 채워서,
앱이 보여 주는 "원래 → 고친 글"이 항상 실제 글과 같게 한다.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from .post import ContentBlock, ImageInfo
from .revise import UserAnswer

TITLE_INDEX = -1  # 제목에 단 메모, 제목 수정


class MemoTurn(BaseModel):
    role: Literal["ai", "user"]  # ai: 이전 안의 의견, user: 답장
    text: str


class Memo(BaseModel):
    id: str
    block_index: int  # 메모를 단 text 블록 번호. 제목이면 -1
    quote: str = ""  # 드래그한 부분 (없으면 블록 전체에 대한 메모)
    comment: str
    source: Literal["user", "review"] = "user"
    kind: str = ""  # 검수 지적 종류 (사실, 말투, 맛 …). '사실'이면 앞 사진을 같이 보낸다
    thread: List[MemoTurn] = []  # 답장해서 다시 요청할 때 주고받은 내용


class AIEdit(BaseModel):
    block_index: int = Field(description="고칠 블록 번호. 제목이면 -1")
    value: str = Field(description="그 블록의 고친 전체 내용. 줄바꿈은 \\n")


class AIProposal(BaseModel):
    memo_id: str = Field(description="[메모]의 id 그대로")
    edits: List[AIEdit] = Field(description="이 메모 때문에 고친 블록만. 고칠 수 없으면 빈 목록")
    opinion: str = Field(description="왜 그렇게 고쳤는지 한두 문장. 고칠 수 없으면 그 이유")


class MemoEditOutput(BaseModel):
    proposals: List[AIProposal] = Field(description="[메모] 하나에 안 하나")


class ProposalEdit(BaseModel):
    block_index: int
    before: str  # 서버가 실제 글에서 채운 원래 글 (승인할 때 지금 글과 같은지 앱이 확인)
    after: str


class Proposal(BaseModel):
    memo_id: str
    edits: List[ProposalEdit]
    opinion: str
    notes: List[str] = []  # 코드 검증에서 버린 수정과 이유


class MemoEditRequest(BaseModel):
    title: str
    blocks: List[ContentBlock]
    facts: dict = {}
    images: List[ImageInfo] = []
    writing_notes: List[str] = []
    memos: List[Memo]
    answers: List[UserAnswer] = []  # 검수 질문에 답한 것 (사실 근거로 씀)


class MemoEditResult(BaseModel):
    proposals: List[Proposal]
    usage: Optional[dict] = None
