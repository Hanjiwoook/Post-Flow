"""
post_writer 단위 테스트. 실제 Claude API 대신 가짜 응답을 쓴다 (비용 0).

실행: cd backend → venv\\Scripts\\python -m unittest discover tests
"""
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app.services.llm_client import LLMError, LLMResult
from app.services.post_writer import (
    PHOTO_REPORT_RULE, RECEIPT_REASON, UNREPORTED_REASON, ExcludedNote, PhotoNote, WriterBlock, WrittenPost,
    clean_tags, drop_receipts, sanitize_images, write_post,
)


def img(color):
    return Image.new("RGB", (64, 48), color)


GOOD_TEXT = "\n".join(["안녕하세요 😊", "오늘은 테스트식당에", "다녀왔어요!"])
CLOSING = "\n".join(["국물이 진했어요", ".", ".", "만족스러웠어요"])


def written(blocks=None, excluded=None):
    return WrittenPost(
        title="[테스트식당] 어딘가동 라멘 맛집 내돈내산 추천",
        blocks=blocks or [
            WriterBlock(type="text", value=GOOD_TEXT),
            WriterBlock(type="quote", value="테스트식당", style="default"),
            WriterBlock(type="map", value="테스트식당"),
            WriterBlock(type="quote", value="🚩위치 : 서울 어딘가", style="quotation_line"),
            WriterBlock(type="image", image_indices=[0, 1]),
            WriterBlock(type="text", value=CLOSING),
        ],
        tags=["테스트"],
        photos=[PhotoNote(index=0, category="EXTERIOR", description="간판"),
                PhotoNote(index=1, category="EXTERIOR", description="입구")],
        excluded_images=excluded if excluded is not None else [ExcludedNote(index=2, reason="흔들림")],
        writing_notes=["웨이팅은 도입부에 썼어요"],
    )


class FakeLLM:
    def __init__(self, post=None, error=None):
        self.post, self.error, self.calls = post or written(), error, []

    async def parse(self, role, content, output_format, **kwargs):
        self.calls.append({"role": role, "content": content, "output_format": output_format})
        if self.error:
            raise self.error
        return LLMResult(parsed=self.post, model="claude-opus-5-5", input_tokens=5000,
                         output_tokens=2000, cost_usd=0.06)


class TestSanitizeImages(unittest.TestCase):
    def test_valid_input_unchanged(self):
        blocks, excluded, fixes = sanitize_images(
            [WriterBlock(type="image", image_indices=[0, 1])], [ExcludedNote(index=2, reason="흔들림")], 3)
        self.assertEqual(blocks[0]["image_indices"], [0, 1])
        self.assertEqual([(e.index, e.reason) for e in excluded], [(2, "흔들림")])
        self.assertEqual(fixes, [])

    def test_out_of_range_and_duplicates_removed(self):
        blocks, _, fixes = sanitize_images([
            WriterBlock(type="image", image_indices=[0, 9]),
            WriterBlock(type="image", image_indices=[0, 1]),
        ], [], 2)
        self.assertEqual([b["image_indices"] for b in blocks], [[0], [1]])
        self.assertEqual(len(fixes), 2)

    def test_empty_image_block_dropped(self):
        blocks, _, _ = sanitize_images([WriterBlock(type="image", image_indices=[5]),
                                        WriterBlock(type="text", value="글")], [], 1)
        self.assertEqual([b["type"] for b in blocks], ["text"])

    def test_unreported_photo_is_excluded_with_reason(self):
        _, excluded, fixes = sanitize_images([WriterBlock(type="image", image_indices=[0])], [], 2)
        self.assertEqual([(e.index, e.reason) for e in excluded], [(1, UNREPORTED_REASON)])
        self.assertTrue(fixes)

    def test_used_photo_removed_from_excluded(self):
        _, excluded, _ = sanitize_images([WriterBlock(type="image", image_indices=[0])],
                                         [ExcludedNote(index=0, reason="?")], 1)
        self.assertEqual(excluded, [])


class TestDropReceipts(unittest.TestCase):
    PHOTOS = [PhotoNote(index=0, category="FOOD_ITEM:라멘", description=""),
              PhotoNote(index=1, category="RECEIPT", description="영수증")]

    def test_receipt_removed_from_mixed_block(self):
        blocks, removed = drop_receipts([WriterBlock(type="image", image_indices=[0, 1])], self.PHOTOS)
        self.assertEqual(blocks[0].image_indices, [0])
        self.assertEqual(removed, [1])

    def test_receipt_only_block_dropped(self):
        blocks, removed = drop_receipts([WriterBlock(type="image", image_indices=[1]),
                                         WriterBlock(type="text", value="글")], self.PHOTOS)
        self.assertEqual([b.type for b in blocks], ["text"])
        self.assertEqual(removed, [1])

    def test_no_receipt_no_change(self):
        original = [WriterBlock(type="image", image_indices=[0])]
        blocks, removed = drop_receipts(original, self.PHOTOS)
        self.assertEqual(blocks, original)
        self.assertEqual(removed, [])


class TestWritePost(unittest.IsolatedAsyncioTestCase):
    async def test_receipt_in_post_is_moved_to_excluded(self):
        post = written(
            blocks=[WriterBlock(type="text", value=GOOD_TEXT), WriterBlock(type="image", image_indices=[0, 1]),
                    WriterBlock(type="image", image_indices=[2]), WriterBlock(type="text", value=CLOSING)],
            excluded=[])
        post.photos.append(PhotoNote(index=2, category="RECEIPT", description="영수증"))
        result = await write_post([img("red"), img("blue"), img("green")], {}, client=FakeLLM(post))
        used = [i for b in result.blocks if b.type == "image" for i in b.image_indices]
        self.assertEqual(used, [0, 1])
        self.assertEqual([(e.index, e.reason) for e in result.excluded_images], [(2, RECEIPT_REASON)])
        self.assertTrue(any("영수증" in n for n in result.writing_notes))

    async def test_prompt_says_no_receipt(self):
        fake = FakeLLM()
        await write_post([img("red")], {"paid_by_self": True}, client=fake)
        prompt = fake.calls[0]["content"][-1]["text"]
        self.assertIn("영수증 사진은 글에 넣지 않는다", prompt)
        self.assertNotIn("맺음말 바로 앞에 1장으로", prompt)

    async def test_content_has_labeled_photos_then_prompt(self):
        fake = FakeLLM()
        await write_post([img("red"), img("blue"), img("green")], {"place_name": "테스트식당"}, client=fake)
        call = fake.calls[0]
        self.assertEqual(call["role"], "writer")
        self.assertIs(call["output_format"], WrittenPost)
        content = call["content"]
        self.assertEqual([b["type"] for b in content[:6]], ["text", "image"] * 3)
        self.assertEqual(content[2]["text"], "사진 1")
        prompt = content[-1]["text"]
        self.assertIn("[사진 고르기]", prompt)
        self.assertIn(PHOTO_REPORT_RULE, prompt)
        self.assertIn("첨부한 사진 0번을 직접 보고 판단", prompt)

    def test_photo_rule_transcribes_text_but_not_card_numbers(self):
        # 사진 설명에 글자가 없어서 검수가 맞는 가격을 '확인 필요'로 봤다 (11/13, 11/17)
        self.assertIn("따옴표로 그대로 옮겨 적는다", PHOTO_REPORT_RULE)
        self.assertIn("카드번호, 승인번호", PHOTO_REPORT_RULE)  # 영수증 개인정보는 옮기지 않는다

    async def test_image_hints_and_paid_flag_reach_prompt(self):
        fake = FakeLLM()
        facts = {"place_name": "테스트식당", "image_hints": ["", "국물 짰음"], "paid_by_self": "true"}
        await write_post([img("red"), img("blue"), img("green")], facts, client=fake)
        prompt = fake.calls[0]["content"][-1]["text"]
        self.assertIn("사용자 설명: 국물 짰음", prompt)
        self.assertIn("`내돈내산`을 한 번 쓴다", prompt)

    async def test_sponsored_flag_reaches_prompt_and_checker(self):
        fake = FakeLLM()
        facts = {"sponsored": True, "paid_by_self": True, "sponsor_detail": "식사 2인"}
        result = await write_post([img("red"), img("blue"), img("green")], facts, client=fake)
        prompt = fake.calls[0]["content"][-1]["text"]
        self.assertIn("제공받은 것: 식사 2인", prompt)
        self.assertNotIn("`내돈내산`을 한 번 쓴다", prompt)
        # 가짜 글에는 협찬 표시가 없으므로 검사에서 걸려야 한다
        self.assertFalse(result.format_check["passed"])
        self.assertIn("(코드 검증) 내돈내산과 협찬이 둘 다 체크되어 협찬으로 썼어요", result.writing_notes)

    async def test_result_fields(self):
        facts = {"place_name": "테스트식당", "waiting": "20분"}
        result = await write_post([img("red"), img("blue"), img("green")], facts, client=FakeLLM())
        self.assertEqual(result.facts, facts)  # 요약하지 않고 원래 값 그대로
        self.assertEqual([b.type for b in result.blocks], ["text", "quote", "map", "quote", "image", "text"])
        self.assertEqual([i.category for i in result.images], ["EXTERIOR", "EXTERIOR", "UNKNOWN"])
        self.assertEqual([e.index for e in result.excluded_images], [2])
        self.assertTrue(result.format_check["passed"], result.format_check)
        self.assertEqual(result.usage["model"], "claude-opus-5-5")
        self.assertIn("웨이팅은 도입부에 썼어요", result.writing_notes)

    async def test_code_fixes_are_reported_in_notes(self):
        post = written(excluded=[])  # 사진 2의 사용 여부를 밝히지 않음
        result = await write_post([img("red"), img("blue"), img("green")], {}, client=FakeLLM(post))
        self.assertTrue(any(n.startswith("(코드 검증)") for n in result.writing_notes))

    async def test_llm_error_propagates(self):
        with self.assertRaises(LLMError):
            await write_post([img("red")], {}, client=FakeLLM(error=LLMError("크레딧 부족")))


class TestAnalyzeEndpoint(unittest.TestCase):
    def setUp(self):
        from app.main import app
        self.client = TestClient(app)
        # 업로드 사진이 실제 backend/uploads에 쌓이지 않게 임시 폴더를 쓴다
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        upload_patch = patch("app.api.v1.endpoints.posts.UPLOAD_DIR", self.tmp.name)
        upload_patch.start()
        self.addCleanup(upload_patch.stop)

    def _post(self, initial_facts='{"place_name": "테스트식당"}'):
        buffer = io.BytesIO()
        img("red").save(buffer, format="JPEG")
        return self.client.post("/api/v1/posts/analyze",
                                files=[("files", ("a.jpg", buffer.getvalue(), "image/jpeg"))],
                                data={"initial_facts": initial_facts})

    def test_broken_facts_stop_before_writing(self):
        # 가게 정보가 깨지면 빈 정보로 글을 쓰지 않고, AI도 부르지 않고, 사진도 저장하지 않는다
        async def must_not_call(images, facts):
            raise AssertionError("write_post가 불리면 안 된다")
        for broken in ['{"place_name": ', '["목록"]']:
            with self.subTest(broken=broken), patch("app.api.v1.endpoints.posts.write_post", must_not_call):
                body = self._post(broken).json()
                self.assertFalse(body["success"])
                self.assertEqual(body["error"], "INVALID_FACTS")
        self.assertEqual(os.listdir(self.tmp.name), [])

    def test_llm_error_returns_korean_message(self):
        async def fail(images, facts):
            raise LLMError("Claude API 키가 설정되지 않았습니다.")
        with patch("app.api.v1.endpoints.posts.write_post", fail):
            body = self._post().json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"], "LLM_ERROR")
        self.assertIn("API 키", body["message"])

    def test_success_fills_image_paths(self):
        async def ok(images, facts):
            return await write_post(images, facts, client=FakeLLM(written(
                blocks=[WriterBlock(type="text", value=GOOD_TEXT), WriterBlock(type="image", image_indices=[0])],
                excluded=[])))
        with patch("app.api.v1.endpoints.posts.write_post", ok):
            body = self._post().json()
        self.assertTrue(body["success"], body)
        self.assertTrue(body["data"]["images"][0]["path"].endswith(".jpg"))
        self.assertEqual(body["data"]["facts"], {"place_name": "테스트식당"})


class CleanTagsTest(unittest.TestCase):
    def test_shape_for_naver(self):
        self.assertEqual(clean_tags(["#하남 맛집", "하남맛집", " ", "초마", "#초마"]), ["하남맛집", "초마"])

    def test_max_30(self):
        self.assertEqual(len(clean_tags([f"태그{i}" for i in range(40)])), 30)

    def test_sponsored_drops_naedon(self):
        self.assertEqual(clean_tags(["하남맛집", "하남내돈내산"], sponsored=True), ["하남맛집"])
        self.assertEqual(clean_tags(["하남내돈내산"]), ["하남내돈내산"])


if __name__ == "__main__":
    unittest.main()
