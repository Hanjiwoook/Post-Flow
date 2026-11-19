"""
파워블로거 검수 (/review): 초안을 읽고 점수, 문제점, 빠진 정보, 사용자에게 할 질문을 돌려준다.

  - 검수 AI는 글을 직접 고치지 않는다. 고쳐 쓰기는 사용자 답변을 받은 뒤 /revise에서 한다.
  - 사실이 필요한 보강(맛, 식감, 양 등)은 지어내지 않고 사용자에게 질문으로 돌린다.
  - 형식은 원래 블로그(포맷 명세서)가 1순위다. 파워블로거의 시선은 내용의 깊이를 보는 데만 쓴다.
  - 비용을 줄이려고 사진은 다시 보내지 않고, 글쓰기 단계에서 받은 사진 설명을 쓴다.
"""
from typing import Dict, List

from ..schemas.post import ContentBlock, ImageInfo
from ..schemas.review import CRITERIA, Review, ReviewResult
from .format_checker import check_post
from .llm_client import LLMClient, llm, text_block
from .post_writer import fact_flag
from .prompt_builder import build_fact_list

MAX_QUESTIONS = 5
REVIEW_EFFORT = "medium"

# 맛집 후기에 흔히 들어가는 정보 항목 (우리 말로 정리한 체크리스트)
INFO_CHECKLIST = [
    "찾아가는 길, 위치 팁 (역·랜드마크 기준)",
    "주차 (가능 여부, 위치)",
    "영업시간, 휴무, 브레이크타임",
    "웨이팅과 붐비는 시간대 팁",
    "메뉴 구성과 가격대",
    "주문한 메뉴와 가격",
    "맛: 식감, 간, 온도, 향",
    "양 (배부름, 몇 인분 정도)",
    "추천 조합, 맛있게 먹는 방법",
    "좌석, 분위기, 혼밥·단체·아이 동반 적합성",
    "아쉬운 점",
    "재방문 의사 (만족도 근거가 있을 때만)",
]

SYSTEM = """\
너는 네이버에서 10년 넘게 맛집 블로그를 운영한 파워블로거이자 꼼꼼한 편집자다.
지금은 다른 블로거의 글 초안을 검수한다. 이 블로그 주인의 글 형식과 말투를 지키는 것이 1순위이고,
너의 역할은 그 형식 안에서 글이 더 깔끔하고, 사람이 쓴 것처럼 읽히고, 맛이 생생하게 전해지도록 돕는 것이다."""

GUIDE = f"""\
[검수 기준] 각 기준을 1~5점으로 매긴다
- 형식 일치: 한 호흡마다 줄을 바꾼 모양, 사진 → 설명 글 반복, 인사·가게 정보·맺음말 구조 (글 분량은 자유이고 너무 짧은 것만 문제로 본다. 줄은 폰 화면 한 줄, 약 20자 안쪽이면 읽기 편하다)
- 사람 같은 말투: 끝맺음이 고르게 섞였는지, 같은 어미 반복, 설명문 같은 딱딱함, 흔한 AI 표현
- 맛 표현: 식감·간·온도·향이 먹는 장면으로 전해지는지, 맛이 '좋았어요' 수준에서 끝나지 않는지
- 정보 충실도: 아래 체크리스트 중 읽는 사람이 궁금해할 정보가 있는지
- 사실 근거: [사실 목록]과 사진 설명에 없는 내용을 지어내지 않았는지 (날씨, 방문 이력, 맛 평가 등)
- 사진과 글: 사진 묶음 바로 뒤 글이 그 사진을 설명하는지

[정보 체크리스트]
{chr(10).join("- " + item for item in INFO_CHECKLIST)}

[검수 규칙]
- 글을 직접 다시 쓰지 않는다. 문제(issues)는 블록 번호와 함께 구체적으로 짚고, 고칠 방향을 적는다.
- [사실 목록]에 없는 정보로만 보강할 수 있는 부분(맛, 식감, 양, 동행, 재방문 의사 등)은
  지어내라고 하지 말고 questions로 사용자에게 묻는다. 질문은 최대 {MAX_QUESTIONS}개, 효과가 큰 순서로.
- 질문마다 바로 고를 수 있는 짧은 답 예시(example_answers)를 2~4개 붙인다.
- [사실 목록]으로 이미 답할 수 있는 것은 묻지 않는다.
- [코드 규칙 검사]에서 실패한 항목은 issues에 반영한다.
- 칭찬만 하지 않는다. 고칠 것이 없으면 needs_revision을 false로 한다.
- scores에는 다음 기준을 이 순서로 모두 넣는다: {", ".join(CRITERIA)}"""


def render_draft(title: str, blocks: List[ContentBlock], images: List[ImageInfo]) -> str:
    """검수 AI가 블록 번호로 지적할 수 있게 초안을 번호 붙은 글로 바꾼다."""
    lines = [f"[제목] {title}"]
    for i, block in enumerate(blocks):
        if block.type == "image":
            descs = []
            for idx in block.image_indices:
                info = images[idx] if idx < len(images) else None
                desc = f"{info.category}: {info.description or ''}" if info else "설명 없음"
                descs.append(f"사진 {idx} ({desc})")
            lines.append(f"[{i}] 사진 묶음 - " + " / ".join(descs))
        elif block.type == "map":
            lines.append(f"[{i}] 지도 - {block.value or ''}")
        else:
            style = f", {block.style}" if block.style else ""
            lines.append(f"[{i}] {block.type}{style}\n{block.value or ''}")
    return "\n".join(lines)


def render_failed_checks(report) -> str:
    failed = [f"- {r.severity} {r.rule}: {r.detail}" for r in report.results if not r.passed]
    return "\n".join(failed) if failed else "- 모두 통과"


async def review_post(
    title: str,
    blocks: List[ContentBlock],
    facts: Dict,
    images: List[ImageInfo],
    writing_notes: List[str],
    client: LLMClient = llm,
) -> ReviewResult:
    """초안을 검수한다. 실패하면 LLMError가 난다."""
    report = check_post([b.model_dump() for b in blocks], title, sponsored=fact_flag(facts, "sponsored"))

    prompt = "\n\n".join([
        GUIDE,
        f"[사실 목록]\n{build_fact_list(facts)}",
        f"[코드 규칙 검사]\n{render_failed_checks(report)}",
        "[글쓴이 메모]\n" + ("\n".join(f"- {n}" for n in writing_notes) or "- 없음"),
        f"[초안]\n{render_draft(title, blocks, images)}",
    ])

    print(f"\n🧐 [Reviewer] 초안 검수 시작 (블록 {len(blocks)}개)")
    # 검수는 읽고 평가하는 일이라 effort를 낮춘다. high에서는 생각 토큰이 한도(16,000)를 넘어 응답이 끊겼다 (11/13).
    result = await client.parse("reviewer", [text_block(prompt)], Review, system=SYSTEM, effort=REVIEW_EFFORT)
    review: Review = result.parsed

    return ReviewResult(
        **review.model_dump(exclude={"questions"}),
        questions=review.questions[:MAX_QUESTIONS],
        format_check={"passed": report.passed, "results": [r.__dict__ for r in report.results]},
        usage=result.usage_dict(),
    )
