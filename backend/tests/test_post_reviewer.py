"""
post_reviewer 단위 테스트. 실제 Claude API 대신 가짜 응답을 쓴다 (비용 0).

실행: cd backend → venv\\Scripts\\python -m unittest discover tests
"""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.schemas.post import ContentBlock, ImageInfo
from app.schemas.review import CRITERIA, Review, ReviewIssue, ReviewQuestion, ReviewScore
from app.services.llm_client import LLMError, LLMResult
from app.services.post_reviewer import MAX_QUESTIONS, SYSTEM, render_draft, review_post

BLOCKS = [
    ContentBlock(type="text", value="안녕하세요😊\n오늘은 테스트식당에\n다녀왔어요!"),
    ContentBlock(type="quote", value="테스트식당", style="default"),
    ContentBlock(type="map", value="테스트식당"),
    ContentBlock(type="image", image_indices=[0, 1]),
    ContentBlock(type="text", value="라멘이 나왔어요.\n맛있었어요."),
]
IMAGES = [ImageInfo(path="", category="FOOD_ITEM:라멘", description="차슈 라멘"),
          ImageInfo(path="", category="FOOD_ITEM:라멘", description="면 들어 올리기")]
FACTS = {"place_name": "테스트식당", "waiting": "없음", "sponsored": True}


def fake_review(n_questions=2):
    return Review(
        overall="맛 표현이 아쉬워요",
        scores=[ReviewScore(criterion=c, score=3, comment="보통") for c in CRITERIA],
        issues=[ReviewIssue(block_index=4, kind="맛", problem="맛이 '맛있었어요'로 끝남",
                            suggestion="식감과 간을 장면으로")],
        missing_info=["양"],
        questions=[ReviewQuestion(question=f"질문{i}", reason="맛 단락 보강", example_answers=["예", "아니오"])
                   for i in range(n_questions)],
        needs_revision=True,
    )


class FakeLLM:
    def __init__(self, review=None, error=None):
        self.review, self.error, self.calls = review or fake_review(), error, []

    async def parse(self, role, content, output_format, **kwargs):
        self.calls.append({"role": role, "content": content, "output_format": output_format, **kwargs})
        if self.error:
            raise self.error
        return LLMResult(parsed=self.review, model="claude-sonnet-5-5", input_tokens=3000,
                         output_tokens=1000, cost_usd=0.016)


class TestRenderDraft(unittest.TestCase):
    def test_blocks_are_numbered_with_photo_descriptions(self):
        text = render_draft("제목", BLOCKS, IMAGES)
        self.assertIn("[제목] 제목", text)
        self.assertIn("[3] 사진 묶음 - 사진 0 (FOOD_ITEM:라멘: 차슈 라멘) / 사진 1", text)
        self.assertIn("[1] quote, default\n테스트식당", text)
        self.assertIn("[2] 지도 - 테스트식당", text)

    def test_missing_image_info_does_not_crash(self):
        self.assertIn("사진 5 (설명 없음)", render_draft("t", [ContentBlock(type="image", image_indices=[5])], []))


class TestReviewPost(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_contents(self):
        fake = FakeLLM()
        await review_post("제목", BLOCKS, FACTS, IMAGES, ["웨이팅은 도입부"], client=fake)
        call = fake.calls[0]
        self.assertEqual(call["role"], "reviewer")
        self.assertIs(call["output_format"], Review)
        self.assertEqual(call["system"], SYSTEM)
        self.assertEqual(call["effort"], "medium")  # high에서 생각 토큰이 한도를 넘었다
        prompt = call["content"][0]["text"]
        self.assertIn("[정보 체크리스트]", prompt)
        self.assertIn("- 웨이팅: 없음", prompt)          # 사실 목록
        self.assertIn("- 웨이팅은 도입부", prompt)       # 글쓴이 메모
        self.assertIn("줄 끝 마침표 없음", prompt)       # 코드 검사 실패 항목이 전달된다
        self.assertIn("협찬 표시", prompt)               # sponsored면 협찬 검사도 다시 돈다
        self.assertIn("[4] text", prompt)

    async def test_result_has_review_check_and_usage(self):
        result = await review_post("제목", BLOCKS, FACTS, IMAGES, [], client=FakeLLM())
        self.assertEqual(result.overall, "맛 표현이 아쉬워요")
        self.assertEqual([s.criterion for s in result.scores], CRITERIA)
        self.assertFalse(result.format_check["passed"])
        self.assertEqual(result.usage["model"], "claude-sonnet-5-5")

    async def test_questions_are_capped(self):
        result = await review_post("제목", BLOCKS, {}, IMAGES, [], client=FakeLLM(fake_review(n_questions=8)))
        self.assertEqual(len(result.questions), MAX_QUESTIONS)

    async def test_llm_error_propagates(self):
        with self.assertRaises(LLMError):
            await review_post("제목", BLOCKS, {}, IMAGES, [], client=FakeLLM(error=LLMError("크레딧 부족")))


class TestReviewEndpoint(unittest.TestCase):
    def setUp(self):
        from app.main import app
        self.client = TestClient(app)
        self.body = {"title": "제목", "blocks": [b.model_dump() for b in BLOCKS], "facts": FACTS,
                     "images": [i.model_dump() for i in IMAGES], "writing_notes": []}

    def test_success(self):
        async def ok(*args):
            return await review_post(*args, client=FakeLLM())
        with patch("app.api.v1.endpoints.posts.review_post", ok):
            body = self.client.post("/api/v1/posts/review", json=self.body).json()
        self.assertTrue(body["success"], body)
        self.assertEqual(body["data"]["questions"][0]["example_answers"], ["예", "아니오"])

    def test_llm_error_message(self):
        async def fail(*args):
            raise LLMError("Claude API 키가 올바르지 않습니다.")
        with patch("app.api.v1.endpoints.posts.review_post", fail):
            body = self.client.post("/api/v1/posts/review", json=self.body).json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"], "LLM_ERROR")


if __name__ == "__main__":
    unittest.main()
