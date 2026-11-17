"""
검수 반영 고쳐쓰기 (/revise): 초안 + 검수 결과 + 사용자 답변 → 고친 글.

  - AI는 글 전체를 다시 쓰지 않고 text 블록 단위로 교체한다 (edits).
    사진 묶음, 지도, 인용구(가게 이름, 가게 정보)는 코드가 원래대로 둔다.
    그래서 고쳐 쓰다가 사진이 빠지거나 순서가 바뀌는 일이 생기지 않는다.
  - 사용자 답변은 사실 목록과 같은 근거로 쓴다. 답이 없는 지적은 지어내지 않고 change_notes에 남긴다.
  - 글쓰기와 같은 형식 규칙을 다시 넣어서 고친 글도 원래 블로그 형식을 지킨다.
  - 호출은 요청 1번에 1번이다. 고친 뒤 자동으로 다시 검수하지 않는다 (비용 제한).
"""
from typing import Dict, List, Tuple

from ..core.config import settings
from ..schemas.post import ContentBlock, ImageInfo
from ..schemas.review import Review
from ..schemas.revise import BlockEdit, ReviseResult, RevisedPost, UserAnswer
from .format_checker import check_post
from .llm_client import LLMClient, llm, text_block
from .post_reviewer import render_draft, render_failed_checks
from .post_writer import fact_flag
from .prompt_builder import (
    FORMAT_RULES,
    NO_FABRICATION,
    build_closing_rules,
    build_disclosure_rules,
    build_fact_list,
    build_title_rules,
)

REVISE_EFFORT = "medium"

# 이 답이면 정보가 없는 것으로 보고 지시문에서 뺀다 (공백 제거 후 정확히 일치할 때만)
UNKNOWN_ANSWERS = {"", "모름", "잘모름", "모르겠음", "모르겠어요", "기억안남", "잘기억나지않음", "확인못함"}

SYSTEM = """\
너는 이 블로그 주인의 글을 다듬는 편집자다.
검수 의견과 블로그 주인이 직접 답한 내용을 반영해 초안의 text 블록을 고친다.
블로그 주인의 형식과 말투를 지키는 것이 1순위이고, 사실은 주어진 근거로만 쓴다."""

REVISE_RULES = """\
[고쳐쓰기 규칙]
- [초안]의 text 블록만 고칠 수 있다. 사진 묶음, 지도, 인용구 블록은 고치지 않는다 (코드가 원래대로 둔다).
- 고친 블록은 edits에 블록 번호와 **고친 전체 내용**을 넣는다. 바꾸지 않은 블록은 edits에 넣지 않는다.
- 새 블록을 추가할 수 없다. 넣을 내용은 알맞은 기존 text 블록에 넣는다 (예: 찾아가는 길은 외관 사진 뒤 글, 맛은 그 음식 사진 뒤 글).
- 사진 묶음 바로 뒤 글은 그 사진을 설명해야 한다. 다른 사진의 내용을 옮겨 오지 않는다.
- [사용자 답변]은 블로그 주인이 직접 답한 사실이다. [사실 목록]과 같은 근거로 쓰고, 사용자 메모와 같게 다룬다.
  답변을 그대로 옮기지 말고 먹는 장면으로 풀어 쓴다. 답변에 없는 감각이나 사실은 덧붙이지 않는다.
- [검수 의견]의 지적을 반영한다. 근거(사실 목록, 사진 설명, 사용자 답변)가 없어서 고칠 수 없는 지적은
  지어내지 말고 change_notes에 '반영 못 함: <이유>'로 적는다.
- 검수 의견과 관계없는 부분은 되도록 그대로 둔다. 근거가 있는 정보는 넣을 수 있는 만큼 넣는다. 글이 길어지는 것은 괜찮고, 근거 있는 내용을 줄이거나 빼서 짧게 만들지 않는다.
- change_notes에는 블록 번호와 함께 무엇을 왜 바꿨는지 짧게 적는다."""


def usable_answers(answers: List[UserAnswer]) -> List[UserAnswer]:
    """'모름'처럼 정보가 없는 답과 빈 답을 뺀다."""
    return [a for a in answers if "".join(a.answer.split()) not in UNKNOWN_ANSWERS]


def render_answers(answers: List[UserAnswer]) -> str:
    if not answers:
        return "- 없음"
    return "\n".join(f"- 질문: {a.question}\n  답: {a.answer.strip()}" for a in answers)


def render_review(review: Review) -> str:
    def where(i: int) -> str:
        return {-1: "제목", -2: "글 전체"}.get(i, f"[{i}]")

    lines = [f"총평: {review.overall}"]
    lines += [f"- {s.criterion} {s.score}/5: {s.comment}" for s in review.scores]
    lines.append("지적:")
    lines += [f"- {where(i.block_index)} {i.kind}: {i.problem} → {i.suggestion}" for i in review.issues] or ["- 없음"]
    lines.append("빠진 정보: " + (", ".join(review.missing_info) or "없음"))
    return "\n".join(lines)


def apply_edits(blocks: List[ContentBlock], edits: List[BlockEdit]) -> Tuple[List[ContentBlock], List[int], List[str]]:
    """
    AI가 낸 edits를 검증해서 적용한다.
      - 없는 블록 번호, text가 아닌 블록, 빈 내용, 같은 블록을 두 번 고친 것은 무시한다
      - 내용이 원래와 같으면 바뀐 것으로 치지 않는다
    반환: (고친 블록 목록, 실제로 바뀐 블록 번호, 무시한 내용 메모)
    """
    result = [b.model_copy() for b in blocks]
    edited: List[int] = []
    seen = set()
    fixes = []
    for edit in edits:
        i = edit.block_index
        if not 0 <= i < len(blocks):
            fixes.append(f"없는 블록 {i}의 수정을 무시했어요")
        elif blocks[i].type != "text":
            fixes.append(f"블록 {i}는 {blocks[i].type} 블록이라 수정을 무시했어요")
        elif i in seen:
            fixes.append(f"블록 {i}를 두 번 고쳐서 첫 번째 수정만 썼어요")
        elif not edit.value.strip():
            fixes.append(f"블록 {i}를 비우려는 수정을 무시했어요")
        else:
            seen.add(i)
            if edit.value != blocks[i].value:
                result[i] = blocks[i].model_copy(update={"value": edit.value})
                edited.append(i)
    return result, sorted(edited), fixes


async def revise_post(
    title: str,
    blocks: List[ContentBlock],
    facts: Dict,
    images: List[ImageInfo],
    writing_notes: List[str],
    review: Review,
    answers: List[UserAnswer],
    client: LLMClient = llm,
) -> ReviseResult:
    """검수 결과와 사용자 답변으로 초안을 고친다. 실패하면 LLMError가 난다."""
    sponsored = fact_flag(facts, "sponsored")
    paid_by_self = fact_flag(facts, "paid_by_self") and not sponsored
    before = check_post([b.model_dump() for b in blocks], title, sponsored=sponsored)

    prompt = "\n\n".join([
        REVISE_RULES,
        FORMAT_RULES,
        build_disclosure_rules(paid_by_self, sponsored, str(facts.get("sponsor_detail") or "").strip()),
        build_closing_rules(facts, settings.BLOG_CLOSING_PHRASE or None),
        build_title_rules(facts),
        NO_FABRICATION,
        f"[사실 목록]\n{build_fact_list(facts)}",
        f"[사용자 답변]\n{render_answers(usable_answers(answers))}",
        f"[검수 의견]\n{render_review(review)}",
        f"[코드 규칙 검사]\n{render_failed_checks(before)}",
        "[글쓴이 메모]\n" + ("\n".join(f"- {n}" for n in writing_notes) or "- 없음"),
        f"[초안]\n{render_draft(title, blocks, images)}",
    ])

    print(f"\n🛠️ [Reviser] 고쳐쓰기 시작 (블록 {len(blocks)}개, 답변 {len(answers)}개)")
    result = await client.parse("reviser", [text_block(prompt)], RevisedPost, system=SYSTEM, effort=REVISE_EFFORT)
    revised: RevisedPost = result.parsed

    new_blocks, edited, fixes = apply_edits(blocks, revised.edits)
    new_title = revised.title.strip() or title
    report = check_post([b.model_dump() for b in new_blocks], new_title, sponsored=sponsored)

    return ReviseResult(
        title=new_title,
        blocks=new_blocks,
        change_notes=list(revised.change_notes) + [f"(코드 검증) {f}" for f in fixes],
        edited_blocks=edited,
        format_check={"passed": report.passed, "results": [r.__dict__ for r in report.results]},
        usage={
            "model": result.model,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cost_usd": result.cost_usd,
        },
    )
