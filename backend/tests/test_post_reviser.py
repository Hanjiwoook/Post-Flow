"""
post_reviser 단위 테스트. 실제 Claude API 대신 가짜 응답을 쓴다 (비용 0).

실행: cd backend → venv\\Scripts\\python -m unittest discover tests
"""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.schemas.post import ContentBlock, ImageInfo
from app.schemas.revise import BlockEdit, RevisedPost, UserAnswer
from app.services.llm_client import LLMError, LLMResult
from app.services.post_reviser import SYSTEM, apply_edits, revise_post, usable_answers
from tests.test_post_reviewer import BLOCKS, IMAGES, fake_review

FACTS = {"place_name": "테스트식당", "waiting": "없음", "paid_by_self": True}
ANSWERS = [
    UserAnswer(question="국물 첫 맛은?", answer="진하고 조금 짰음"),
    UserAnswer(question="주차는?", answer="모름"),
    UserAnswer(question="양은?", answer="  "),
]
NEW_TEXT = "라멘이 나왔어요\n국물이 진한데\n저한테는 살짝 짭조름했어요😋"


def fake_revised(edits=None, title="새 제목"):
    return RevisedPost(
        title=title,
        edits=edits if edits is not None else [BlockEdit(block_index=4, value=NEW_TEXT)],
        change_notes=["[4] 국물 맛 답변 반영"],
    )


class FakeLLM:
    def __init__(self, revised=None, error=None):
        self.revised, self.error, self.calls = revised or fake_revised(), error, []

    async def parse(self, role, content, output_format, **kwargs):
        self.calls.append({"role": role, "content": content, "output_format": output_format, **kwargs})
        if self.error:
            raise self.error
        return LLMResult(parsed=self.revised, model="claude-sonnet-5-5", input_tokens=5000,
                         output_tokens=1500, cost_usd=0.04)


class TestUsableAnswers(unittest.TestCase):
    def test_unknown_and_blank_answers_are_dropped(self):
        kept = usable_answers(ANSWERS + [UserAnswer(question="q", answer="잘 기억나지 않음")])
        self.assertEqual([a.answer for a in kept], ["진하고 조금 짰음"])

    def test_answer_that_only_mentions_unknown_is_kept(self):
        # '주차 모름'처럼 다른 정보가 같이 있으면 남긴다
        kept = usable_answers([UserAnswer(question="q", answer="대중교통으로 감, 주차 모름")])
        self.assertEqual(len(kept), 1)


class TestApplyEdits(unittest.TestCase):
    def test_only_text_block_changes(self):
        blocks, edited, fixes = apply_edits(BLOCKS, [BlockEdit(block_index=4, value=NEW_TEXT)])
        self.assertEqual(blocks[4].value, NEW_TEXT)
        self.assertEqual(edited, [4])
        self.assertEqual(fixes, [])
        self.assertEqual(BLOCKS[4].value, "라멘이 나왔어요.\n맛있었어요.")  # 원본은 그대로
        for i in range(4):
            self.assertEqual(blocks[i], BLOCKS[i])

    def test_invalid_edits_are_ignored(self):
        edits = [
            BlockEdit(block_index=9, value="없는 블록"),
            BlockEdit(block_index=3, value="사진 블록"),
            BlockEdit(block_index=1, value="인용구"),
            BlockEdit(block_index=0, value="   "),
            BlockEdit(block_index=4, value="첫 수정"),
            BlockEdit(block_index=4, value="두 번째 수정"),
        ]
        blocks, edited, fixes = apply_edits(BLOCKS, edits)
        self.assertEqual(blocks[3].image_indices, [0, 1])
        self.assertEqual(blocks[1].value, "테스트식당")
        self.assertEqual(blocks[0].value, BLOCKS[0].value)
        self.assertEqual(blocks[4].value, "첫 수정")
        self.assertEqual(edited, [4])
        self.assertEqual(len(fixes), 5)

    def test_same_value_is_not_counted_as_edit(self):
        _, edited, _ = apply_edits(BLOCKS, [BlockEdit(block_index=0, value=BLOCKS[0].value)])
        self.assertEqual(edited, [])


class TestRevisePost(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_contents(self):
        fake = FakeLLM()
        await revise_post("제목", BLOCKS, FACTS, IMAGES, ["웨이팅은 도입부"], fake_review(), ANSWERS, client=fake)
        call = fake.calls[0]
        self.assertEqual(call["role"], "reviser")
        self.assertIs(call["output_format"], RevisedPost)
        self.assertEqual(call["system"], SYSTEM)
        self.assertEqual(call["effort"], "medium")
        prompt = call["content"][0]["text"]
        self.assertIn("[고쳐쓰기 규칙]", prompt)
        self.assertIn("[형식 규칙]", prompt)                     # 글쓰기와 같은 형식 규칙
        self.assertIn("[내돈내산 표시]", prompt)
        self.assertIn("답: 진하고 조금 짰음", prompt)
        self.assertNotIn("질문: 주차는?", prompt)                # '모름'은 빠진다
        self.assertIn("[4] 맛: 맛이 '맛있었어요'로 끝남", prompt)  # 검수 지적이 블록 번호와 함께
        self.assertIn("- 웨이팅: 없음", prompt)
        self.assertIn("[3] 사진 묶음", prompt)

    async def test_result(self):
        result = await revise_post("제목", BLOCKS, FACTS, IMAGES, [], fake_review(), ANSWERS, client=FakeLLM())
        self.assertEqual(result.title, "새 제목")
        self.assertEqual(result.blocks[4].value, NEW_TEXT)
        self.assertEqual(result.edited_blocks, [4])
        self.assertEqual(len(result.blocks), len(BLOCKS))
        self.assertIn("results", result.format_check)
        self.assertEqual(result.usage["cost_usd"], 0.04)

    async def test_blank_title_keeps_original_and_code_fixes_are_noted(self):
        fake = FakeLLM(fake_revised(edits=[BlockEdit(block_index=3, value="x")], title=" "))
        result = await revise_post("원래 제목", BLOCKS, {}, IMAGES, [], fake_review(), [], client=fake)
        self.assertEqual(result.title, "원래 제목")
        self.assertEqual(result.edited_blocks, [])
        self.assertTrue(any(n.startswith("(코드 검증)") for n in result.change_notes))
        self.assertIn("- 없음", fake.calls[0]["content"][0]["text"])  # 답변 없음

    async def test_llm_error_propagates(self):
        with self.assertRaises(LLMError):
            await revise_post("제목", BLOCKS, {}, IMAGES, [], fake_review(), [],
                              client=FakeLLM(error=LLMError("크레딧 부족")))


class TestReviseEndpoint(unittest.TestCase):
    def setUp(self):
        from app.main import app
        self.client = TestClient(app)
        self.body = {"title": "제목", "blocks": [b.model_dump() for b in BLOCKS], "facts": FACTS,
                     "images": [i.model_dump() for i in IMAGES], "writing_notes": [],
                     "review": fake_review().model_dump(),
                     "answers": [a.model_dump() for a in ANSWERS]}

    def test_success(self):
        async def ok(*args):
            return await revise_post(*args, client=FakeLLM())
        with patch("app.api.v1.endpoints.posts.revise_post", ok):
            body = self.client.post("/api/v1/posts/revise", json=self.body).json()
        self.assertTrue(body["success"], body)
        self.assertEqual(body["data"]["edited_blocks"], [4])
        self.assertEqual(body["data"]["blocks"][3]["image_indices"], [0, 1])

    def test_llm_error_message(self):
        async def fail(*args):
            raise LLMError("Claude API 키가 올바르지 않습니다.")
        with patch("app.api.v1.endpoints.posts.revise_post", fail):
            body = self.client.post("/api/v1/posts/revise", json=self.body).json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"], "LLM_ERROR")

    def test_review_is_required(self):
        body = dict(self.body)
        del body["review"]
        self.assertEqual(self.client.post("/api/v1/posts/revise", json=body).status_code, 422)


if __name__ == "__main__":
    unittest.main()
