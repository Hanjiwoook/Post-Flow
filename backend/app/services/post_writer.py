"""
글쓰기 (/analyze): 사진 + 가게 정보 → 블로그 글, 뺀 사진, 작성 리포트.

예전 Gemini 흐름(사진 분석 → 가게 요약 → 글쓰기, 3번 호출)을 Claude 1번 호출로 바꿨다.
  - 글쓰기 AI가 사진을 직접 보고 쓸 사진을 고른다 (흔들린 사진, 비슷한 사진 판단)
  - 가게 정보는 요약하지 않고 앱이 보낸 원래 값을 그대로 쓴다 (요약하면 웨이팅, 주문 메뉴가 빠졌다)
  - 지시문은 prompt_builder, 연사 힌트는 photo_dedup, 형식 채점은 format_checker를 쓴다

AI 응답은 그대로 믿지 않고 코드로 한 번 더 검증한다 (사진 번호 범위, 중복, 누락).
"""
from typing import Dict, List, Literal, Optional, Tuple

from PIL import Image
from pydantic import BaseModel, Field

from ..core.config import settings
from ..schemas.post import AnalyzeResult, ContentBlock, ExcludedImage, ImageInfo
from .format_checker import check_post
from .llm_client import LLMClient, image_block, llm, text_block
from .photo_dedup import group_similar
from .prompt_builder import build_writer_prompt


# --- AI 응답 형식 ---

class WriterBlock(BaseModel):
    type: Literal["text", "quote", "map", "image"]
    value: Optional[str] = Field(None, description="text/quote의 내용, map의 가게 이름. 줄바꿈은 \\n")
    style: Optional[str] = Field(None, description="quote일 때 default(가게 이름) 또는 quotation_line(가게 정보)")
    image_indices: List[int] = Field(default_factory=list, description="image일 때 사진 번호 목록 (한 장면의 사진들, 장수 제한 없음)")


class PhotoNote(BaseModel):
    index: int
    category: str = Field(description="EXTERIOR, INTERIOR, MENU, FOOD_ITEM:메뉴명, RECEIPT 중 하나")
    description: str = Field(description="사진에 보이는 그대로의 짧은 설명. 사진 속 글자(간판, 가격, 안내문)는 따옴표로 옮겨 적는다")


class ExcludedNote(BaseModel):
    index: int
    reason: str


class WrittenPost(BaseModel):
    title: str
    blocks: List[WriterBlock]
    tags: List[str]
    photos: List[PhotoNote] = Field(description="모든 사진(쓴 사진과 뺀 사진 모두)의 분류와 설명")
    excluded_images: List[ExcludedNote]
    writing_notes: List[str]


# 사진 분류/설명을 함께 받기 위한 추가 지시 (편집 화면과 이후 수정 기능에서 쓴다)
PHOTO_REPORT_RULE = """\
[사진 기록]
- photos에는 쓴 사진과 뺀 사진을 모두 넣는다. 사진마다 번호, 분류(EXTERIOR, INTERIOR, MENU, FOOD_ITEM:메뉴명, RECEIPT 중 하나), 보이는 그대로의 짧은 설명을 적는다.
- 사진 속 글자(간판, 입간판 문구, 메뉴 이름과 가격, 영업 안내문)는 설명에 따옴표로 그대로 옮겨 적는다. 예: 메뉴판 "김치찌개 9,000원", 입간판 "SINCE 2015"
  글에 쓴 가격과 문구는 반드시 해당 사진 설명에도 있어야 한다. 나중에 검수할 때 사진 대신 이 설명으로 사실을 확인한다.
- 흐려서 읽을 수 없는 글자는 지어내지 말고 `(글자 흐림)`이라고 적는다.
- 영수증은 메뉴 이름, 가격, 합계만 적는다. 카드번호, 승인번호, 사업자번호, 전화번호는 적지 않는다."""

UNREPORTED_REASON = "AI가 사용 여부를 밝히지 않은 사진이에요"
RECEIPT_REASON = "영수증 사진은 개인정보(카드번호 등) 때문에 올리지 않아요"


def drop_receipts(blocks: List[WriterBlock], photos: List[PhotoNote]) -> Tuple[List[WriterBlock], List[int]]:
    """
    AI가 RECEIPT로 분류한 사진을 글에서 뺀다 (지시를 어겨도 코드가 막는다).
    반환: (사진을 뺀 블록 목록, 뺀 영수증 번호)
    """
    receipts = {p.index for p in photos if p.category.upper().startswith("RECEIPT")}
    removed = []
    clean = []
    for block in blocks:
        if block.type == "image" and receipts & set(block.image_indices):
            removed += [i for i in block.image_indices if i in receipts]
            kept = [i for i in block.image_indices if i not in receipts]
            if not kept:
                continue
            block = block.model_copy(update={"image_indices": kept})
        clean.append(block)
    return clean, removed


# --- 사진 번호 검증 ---

def sanitize_images(blocks: List[WriterBlock], excluded: List[ExcludedNote], image_count: int):
    """
    AI가 낸 사진 번호를 검증한다.
      - 범위를 벗어난 번호, 앞에서 이미 쓴 번호는 블록에서 지운다 (사진이 비면 블록도 지운다)
      - 쓴 사진은 제외 목록에서 지운다
      - 쓰지도 빼지도 않은 사진은 제외 목록에 이유와 함께 넣는다
    반환: (정리된 블록 dict 목록, 정리된 제외 목록, 고친 내용 메모)
    """
    fixes = []
    used = set()
    clean_blocks = []
    for block in blocks:
        data = block.model_dump()
        if block.type == "image":
            kept = []
            for idx in block.image_indices:
                if not 0 <= idx < image_count:
                    fixes.append(f"없는 사진 번호 {idx}를 지웠어요")
                elif idx in used:
                    fixes.append(f"두 번 쓴 사진 {idx}의 두 번째 사용을 지웠어요")
                else:
                    used.add(idx)
                    kept.append(idx)
            if not kept:
                continue
            data["image_indices"] = kept
        clean_blocks.append(data)

    clean_excluded = []
    seen = set()
    for note in excluded:
        if note.index in used or note.index in seen or not 0 <= note.index < image_count:
            continue
        seen.add(note.index)
        clean_excluded.append(ExcludedImage(index=note.index, reason=note.reason))
    for idx in range(image_count):
        if idx not in used and idx not in seen:
            clean_excluded.append(ExcludedImage(index=idx, reason=UNREPORTED_REASON))
            fixes.append(f"사진 {idx}의 사용 여부가 없어서 뺀 사진으로 분류했어요")
    clean_excluded.sort(key=lambda e: e.index)
    return clean_blocks, clean_excluded, fixes


def _style_samples() -> List[str]:
    """학습된 스타일 프로필의 예시 글. 없거나 읽기에 실패하면 빈 목록."""
    try:
        from .writing_style_service import writing_style_service
        profile = writing_style_service.get_active_profile()
        return (profile or {}).get("few_shot_examples") or []
    except Exception as e:  # 스타일 예시는 없어도 글은 쓸 수 있다
        print(f"  ⚠️ 스타일 예시를 불러오지 못했습니다: {e}")
        return []


def fact_flag(facts: Dict, key: str) -> bool:
    """앱이 보낸 체크칸 값 (true/"true"/1 등)을 bool로."""
    return str(facts.get(key, "")).lower() in ("true", "1", "yes", "y")


async def write_post(images: List[Image.Image], facts: Dict, client: LLMClient = llm) -> AnalyzeResult:
    """사진과 가게 정보로 블로그 글을 쓴다. 실패하면 LLMError가 난다."""
    hints = facts.get("image_hints") or []
    photos = [{"hint": hints[i] if i < len(hints) else ""} for i in range(len(images))]
    sponsored = fact_flag(facts, "sponsored")
    paid_by_self = fact_flag(facts, "paid_by_self") and not sponsored  # 둘 다 오면 협찬을 따른다

    prompt = build_writer_prompt(
        facts,
        photos,
        paid_by_self=paid_by_self,
        sponsored=sponsored,
        sponsor_detail=str(facts.get("sponsor_detail") or ""),
        closing_phrase=settings.BLOG_CLOSING_PHRASE or None,
        style_samples=_style_samples(),
        similar_groups=group_similar(images) if len(images) > 1 else [],
    )
    prompt += "\n\n" + PHOTO_REPORT_RULE

    # 사진을 먼저, 지시문을 마지막에 둔다. 사진마다 번호 라벨을 붙여 AI가 번호를 헷갈리지 않게 한다.
    content = []
    for i, img in enumerate(images):
        content.append(text_block(f"사진 {i}"))
        content.append(image_block(img))
    content.append(text_block(prompt))

    print(f"\n✍️ [Writer] 사진 {len(images)}장으로 글쓰기 시작")
    result = await client.parse("writer", content, WrittenPost)
    post: WrittenPost = result.parsed

    writer_blocks, receipts = drop_receipts(post.blocks, post.photos)
    excluded_notes = [n for n in post.excluded_images if n.index not in receipts]
    excluded_notes += [ExcludedNote(index=i, reason=RECEIPT_REASON) for i in receipts]
    blocks, excluded, fixes = sanitize_images(writer_blocks, excluded_notes, len(images))
    if receipts:
        fixes.append(f"글에 들어간 영수증 사진 {receipts}을 뺐어요")
    if sponsored and fact_flag(facts, "paid_by_self"):
        fixes.append("내돈내산과 협찬이 둘 다 체크되어 협찬으로 썼어요")
    notes = list(post.writing_notes) + [f"(코드 검증) {f}" for f in fixes]

    report = check_post(blocks, post.title, sponsored=sponsored)
    photo_notes = {p.index: p for p in post.photos}

    return AnalyzeResult(
        title=post.title,
        content="",
        blocks=[ContentBlock(**b) for b in blocks],
        tags=post.tags,
        facts=facts,
        images=[
            ImageInfo(
                path="",
                category=photo_notes[i].category if i in photo_notes else "UNKNOWN",
                description=photo_notes[i].description if i in photo_notes else None,
            )
            for i in range(len(images))
        ],
        excluded_images=excluded,
        writing_notes=notes,
        format_check={
            "passed": report.passed,
            "results": [r.__dict__ for r in report.results],
        },
        usage=result.usage_dict(),
    )
