"""
메모로 부분 고치기 (/memo-edit): 사용자 메모·검수 지적 메모마다 AI가 고친 안과 의견을 낸다.

  - AI가 고칠 수 있는 범위: 메모 단 text 블록 + 바로 앞뒤 text 블록 하나씩.
    앞뒤를 찾을 때 사진 묶음·지도·구분선은 건너뛰고, 인용구(가게 이름 등)를 만나면 멈춘다.
    제목 메모는 제목만 고친다.
  - 범위 밖 수정, text가 아닌 블록, 빈 내용은 코드가 버리고 notes에 이유를 남긴다.
  - 원래 글(before)은 서버가 채운다. 승인은 앱에서 하고 AI를 다시 부르지 않는다.
"""
import os
from typing import Dict, List, Optional, Set, Tuple

from PIL import Image

from ..core.config import settings
from ..schemas.memo_edit import TITLE_INDEX, AIEdit, Memo, MemoEditOutput, MemoEditResult, Proposal, ProposalEdit
from ..schemas.post import ContentBlock, ImageInfo
from ..schemas.revise import UserAnswer
from .llm_client import LLMClient, image_block, llm, text_block
from .post_reviewer import render_draft
from .post_reviser import render_answers, usable_answers
from .post_writer import fact_flag
from .prompt_builder import (
    FORMAT_RULES,
    NO_FABRICATION,
    build_closing_rules,
    build_disclosure_rules,
    build_fact_list,
    build_title_rules,
)

# 앞뒤 글을 찾을 때 건너뛰는 블록 (글이 아니고, 흐름을 끊지 않는 것)
SKIP_TYPES = {"image", "map", "divider", "sticker"}


def _neighbor_text(blocks: List[ContentBlock], start: int, step: int) -> Optional[int]:
    i = start + step
    while 0 <= i < len(blocks):
        t = blocks[i].type
        if t == "text":
            return i
        if t not in SKIP_TYPES:  # 인용구 등에서 멈춤
            return None
        i += step
    return None


def allowed_blocks(blocks: List[ContentBlock], memo_index: int) -> Set[int]:
    """메모 하나로 고칠 수 있는 블록 번호. 메모 위치가 잘못됐으면 빈 집합."""
    if memo_index == TITLE_INDEX:
        return {TITLE_INDEX}
    if not 0 <= memo_index < len(blocks) or blocks[memo_index].type != "text":
        return set()
    allowed = {memo_index}
    for step in (-1, 1):
        n = _neighbor_text(blocks, memo_index, step)
        if n is not None:
            allowed.add(n)
    return allowed


def current_value(title: str, blocks: List[ContentBlock], index: int) -> str:
    return title if index == TITLE_INDEX else (blocks[index].value or "")


def validate_proposal(title: str, blocks: List[ContentBlock], memo: Memo,
                      edits: List[AIEdit], opinion: str) -> Proposal:
    """AI가 낸 수정을 검증해서 앱에 보낼 안으로 만든다."""
    allowed = allowed_blocks(blocks, memo.block_index)
    out: List[ProposalEdit] = []
    notes: List[str] = []
    seen = set()
    if not allowed:
        notes.append(f"메모 위치({memo.block_index})가 글 블록이 아니라 고칠 수 없어요")
    for e in edits:
        i = e.block_index
        if i not in allowed:
            notes.append(f"범위 밖 블록 {i}의 수정을 버렸어요")
        elif i in seen:
            notes.append(f"블록 {i}를 두 번 고쳐서 첫 번째 수정만 썼어요")
        elif not e.value.strip():
            notes.append(f"블록 {i}를 비우려는 수정을 버렸어요")
        else:
            seen.add(i)
            before = current_value(title, blocks, i)
            after = e.value.strip() if i == TITLE_INDEX else e.value
            if after != before:
                out.append(ProposalEdit(block_index=i, before=before, after=after))
    out.sort(key=lambda p: p.block_index)
    return Proposal(memo_id=memo.id, edits=out, opinion=opinion.strip(), notes=notes)


# ---------------------------------------------------------------------------
# AI 호출
# ---------------------------------------------------------------------------
MEMO_EFFORT = "medium"
MAX_FACT_PHOTOS = 6  # 사실 확인용 사진은 한 번 호출에 최대 6장 (비용)

SYSTEM = """\
너는 이 블로그 주인의 글을 다듬는 편집자다.
블로그 주인이 글에 단 메모마다, 메모가 가리키는 곳만 고친 안과 짧은 의견을 낸다.
마음에 드는 부분까지 바뀌는 것을 싫어하므로 메모와 관계없는 문장은 그대로 둔다."""

MEMO_RULES = """\
[메모 고치기 규칙]
- [메모] 하나마다 proposals에 안을 하나씩 낸다. memo_id는 메모의 id를 그대로 쓴다.
- 메모마다 '고칠 수 있는 블록'만 고칠 수 있다. 메모 단 블록과 바로 앞뒤 글 블록이다.
  앞뒤 블록은 메모를 반영하면 흐름이 어색해질 때만 이어지게 다듬는다. 필요 없으면 고치지 않는다.
- edits에는 고친 블록의 번호와 **고친 전체 내용**을 넣는다. 바꾸지 않은 블록은 넣지 않는다.
- 드래그한 부분이 있으면 그 부분을 중심으로 고치고, 같은 블록의 나머지 줄은 되도록 그대로 둔다.
- 메모마다 지금 [초안]을 기준으로 따로 고친다. 다른 메모의 안이 반영됐다고 가정하지 않는다.
- '검수 지적' 메모는 검수 AI가 단 것이다. 지적이 맞지 않거나 근거가 없어서 고칠 수 없으면
  edits를 비우고 opinion에 이유를 적는다. 사용자 메모도 근거 없는 사실이 필요하면 같은 방식으로 한다.
- [이전 대화]가 있으면 블로그 주인이 앞의 안에 답장한 것이다. 답장을 우선해서 다시 고친다.
- opinion은 블로그 주인에게 말하듯 한두 문장으로, 무엇을 왜 바꿨는지 적는다 (예: "앞 문장도 같이 다듬었어요").
- 사진 묶음 바로 뒤 글은 그 사진을 설명해야 한다. 다른 사진의 내용을 옮겨 오지 않는다.
- [사용자 답변]은 블로그 주인이 직접 답한 사실이다. [사실 목록]과 같은 근거로 쓴다.
- '사실 확인용 사진'이 붙은 메모는 그 사진을 직접 보고 확인한다. 글의 내용이 사진(간판·안내문·메뉴판 글자 등)에
  보이면 지적이 틀린 것이므로 고치지 말고, opinion에 '사진에 ~가 보여서 그대로 뒀어요'처럼 적는다.
  사진에도 없을 때만 지적대로 고친다."""


def _where(i: int) -> str:
    return "제목" if i == TITLE_INDEX else f"[{i}]"


def photo_block_before(blocks: List[ContentBlock], index: int) -> Optional[int]:
    """메모 단 글 바로 앞의 사진 묶음 (그 글이 설명하는 사진). 구분선만 건너뛴다."""
    i = index - 1
    while i >= 0 and blocks[i].type in {"divider", "sticker"}:
        i -= 1
    return i if i >= 0 and blocks[i].type == "image" else None


def fact_photos(memos: List[Memo], blocks: List[ContentBlock], images: List[ImageInfo]) -> Dict[str, List[Tuple[int, str]]]:
    """'사실' 검수 메모마다 확인용 사진 (사진 번호, 경로). 파일이 없는 사진은 뺀다. 서로 다른 사진은 모두 합쳐 MAX_FACT_PHOTOS장까지."""
    out: Dict[str, List[Tuple[int, str]]] = {}
    used: Set[int] = set()
    for m in memos:
        if m.source != "review" or m.kind != "사실" or m.block_index < 0:
            continue
        pb = photo_block_before(blocks, m.block_index)
        if pb is None:
            continue
        for idx in blocks[pb].image_indices:
            if not 0 <= idx < len(images):
                continue
            path = images[idx].path
            if idx not in used:  # 같은 사진을 두 메모가 쓰면 한 번만 센다
                if not path or not os.path.exists(path) or len(used) >= MAX_FACT_PHOTOS:
                    continue
                used.add(idx)
            out.setdefault(m.id, []).append((idx, path))
    return out


def render_memos(memos: List[Memo], blocks: List[ContentBlock],
                 photos: Optional[Dict[str, List[Tuple[int, str]]]] = None) -> str:
    out = []
    for m in memos:
        allowed = ", ".join(_where(i) for i in sorted(allowed_blocks(blocks, m.block_index)))
        lines = [f"- id: {m.id} ({'검수 지적' if m.source == 'review' else '사용자 메모'})",
                 f"  위치: {_where(m.block_index)} / 고칠 수 있는 블록: {allowed}"]
        if m.quote.strip():
            lines.append(f"  드래그한 부분: \"{m.quote.strip()}\"")
        lines.append(f"  메모: {m.comment.strip()}")
        if photos and photos.get(m.id):
            lines.append("  사실 확인용 사진: " + ", ".join(f"사진 {i}" for i, _ in photos[m.id]) + " (아래에 붙임)")
        if m.thread:
            lines.append("  [이전 대화]")
            lines += [f"    {'AI' if t.role == 'ai' else '블로그 주인'}: {t.text.strip()}" for t in m.thread]
        out.append("\n".join(lines))
    return "\n".join(out)


async def suggest_memo_edits(
    title: str,
    blocks: List[ContentBlock],
    facts: Dict,
    images: List[ImageInfo],
    writing_notes: List[str],
    memos: List[Memo],
    answers: List[UserAnswer],
    client: LLMClient = llm,
) -> MemoEditResult:
    """메모마다 고친 안을 만든다. 글은 바꾸지 않는다 (승인은 앱에서). 실패하면 LLMError가 난다."""
    valid = [m for m in memos if allowed_blocks(blocks, m.block_index)]
    proposals: Dict[str, Proposal] = {}
    for m in memos:
        if m not in valid:
            proposals[m.id] = validate_proposal(title, blocks, m, [], "")

    usage = None
    photos = fact_photos(valid, blocks, images)
    if valid:
        sponsored = fact_flag(facts, "sponsored")
        paid_by_self = fact_flag(facts, "paid_by_self") and not sponsored
        prompt = "\n\n".join([
            MEMO_RULES,
            FORMAT_RULES,
            build_disclosure_rules(paid_by_self, sponsored, str(facts.get("sponsor_detail") or "").strip()),
            build_closing_rules(facts, settings.BLOG_CLOSING_PHRASE or None),
            build_title_rules(facts),
            NO_FABRICATION,
            f"[사실 목록]\n{build_fact_list(facts)}",
            f"[사용자 답변]\n{render_answers(usable_answers(answers))}",
            "[글쓴이 메모]\n" + ("\n".join(f"- {n}" for n in writing_notes) or "- 없음"),
            f"[초안]\n{render_draft(title, blocks, images)}",
            f"[메모]\n{render_memos(valid, blocks, photos)}",
        ])
        content = [text_block(prompt)]
        attached: Set[int] = set()
        for idx, path in [p for ps in photos.values() for p in ps]:
            if idx in attached:
                continue
            try:
                with Image.open(path) as img:
                    content += [text_block(f"[사진 {idx}] 사실 확인용"), image_block(img)]
                attached.add(idx)
            except OSError as e:
                print(f"  ⚠️ 사진 {idx}를 열지 못해 빼고 보냅니다: {e}")
        print(f"\n📝 [MemoEditor] 메모 {len(valid)}개 고친 안 만들기 (사실 확인 사진 {len(attached)}장)")
        result = await client.parse("reviser", content, MemoEditOutput, system=SYSTEM, effort=MEMO_EFFORT)
        usage = result.usage_dict()
        by_id = {m.id: m for m in valid}
        for ai in result.parsed.proposals:
            m = by_id.get(ai.memo_id)
            if m is not None and m.id not in proposals:  # 모르는 id, 같은 메모 두 번째 안은 버린다
                proposals[m.id] = validate_proposal(title, blocks, m, ai.edits, ai.opinion)
        for m in valid:
            if m.id not in proposals:
                proposals[m.id] = Proposal(memo_id=m.id, edits=[], opinion="",
                                           notes=["AI가 이 메모에 안을 주지 않았어요. 다시 요청해 주세요"])

    return MemoEditResult(proposals=[proposals[m.id] for m in memos if m.id in proposals], usage=usage)
