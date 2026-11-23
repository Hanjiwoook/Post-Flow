"""
memo_editor 단위 테스트 (AI 호출 없음).

실행: cd backend → venv\\Scripts\\python -m unittest discover tests
"""
import os
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from fastapi.testclient import TestClient

from app.schemas.memo_edit import AIEdit, AIProposal, Memo, MemoEditOutput, MemoTurn
from app.schemas.post import ContentBlock, ImageInfo
from app.schemas.revise import UserAnswer
from app.services.llm_client import LLMError, LLMResult
from app.services.memo_editor import (MAX_FACT_PHOTOS, SYSTEM, allowed_blocks, fact_photos, photo_block_before,
                                      suggest_memo_edits, validate_proposal)

TITLE = "테스트식당 라멘 후기"
BLOCKS = [
    ContentBlock(type="text", value="안녕하세요😊\n오늘은 테스트식당에\n다녀왔어요!"),  # 0
    ContentBlock(type="quote", value="테스트식당", style="default"),                  # 1
    ContentBlock(type="map", value="테스트식당"),                                      # 2
    ContentBlock(type="image", image_indices=[0]),                                     # 3
    ContentBlock(type="text", value="가게 앞이에요"),                                  # 4
    ContentBlock(type="image", image_indices=[1, 2]),                                  # 5
    ContentBlock(type="divider"),                                                      # 6
    ContentBlock(type="text", value="라멘이 나왔어요\n맛있었어요"),                    # 7
    ContentBlock(type="image", image_indices=[3]),                                     # 8
    ContentBlock(type="text", value="교자도 시켰어요"),                                # 9
    ContentBlock(type="text", value="다음에 또 올게요"),                               # 10
]


def memo(i, mid="m1"):
    return Memo(id=mid, block_index=i, comment="맛 표현을 더 살려 줘")


class AllowedBlocksTest(unittest.TestCase):
    def test_skips_images_map_divider(self):
        self.assertEqual(allowed_blocks(BLOCKS, 7), {4, 7, 9})

    def test_stops_at_quote(self):
        # 4번 앞: 사진(3)·지도(2)는 건너뛰고 인용구(1)에서 멈춘다 → 0번은 못 고친다
        self.assertEqual(allowed_blocks(BLOCKS, 4), {4, 7})

    def test_first_and_last(self):
        self.assertEqual(allowed_blocks(BLOCKS, 0), {0})
        self.assertEqual(allowed_blocks(BLOCKS, 10), {9, 10})

    def test_title(self):
        self.assertEqual(allowed_blocks(BLOCKS, -1), {-1})

    def test_non_text_or_out_of_range(self):
        for i in (1, 3, -2, 11):
            self.assertEqual(allowed_blocks(BLOCKS, i), set())


class ValidateProposalTest(unittest.TestCase):
    def test_keeps_allowed_and_fills_before(self):
        p = validate_proposal(TITLE, BLOCKS, memo(7), [
            AIEdit(block_index=9, value="교자도 시켰는데\n바삭했어요"),
            AIEdit(block_index=7, value="라멘이 나왔어요\n국물이 진했어요"),
        ], " 맛을 장면으로 바꿨어요 ")
        self.assertEqual([e.block_index for e in p.edits], [7, 9])
        self.assertEqual(p.edits[0].before, "라멘이 나왔어요\n맛있었어요")
        self.assertEqual(p.edits[0].after, "라멘이 나왔어요\n국물이 진했어요")
        self.assertEqual(p.opinion, "맛을 장면으로 바꿨어요")
        self.assertEqual(p.notes, [])

    def test_drops_out_of_range_non_text_empty_duplicate(self):
        p = validate_proposal(TITLE, BLOCKS, memo(7), [
            AIEdit(block_index=0, value="범위 밖"),
            AIEdit(block_index=8, value="사진 블록"),
            AIEdit(block_index=4, value="  "),
            AIEdit(block_index=7, value="첫 수정"),
            AIEdit(block_index=7, value="두 번째 수정"),
            AIEdit(block_index=-1, value="제목도 바꿈"),
        ], "")
        self.assertEqual([(e.block_index, e.after) for e in p.edits], [(7, "첫 수정")])
        self.assertEqual(len(p.notes), 5)

    def test_unchanged_value_is_not_an_edit(self):
        p = validate_proposal(TITLE, BLOCKS, memo(9), [AIEdit(block_index=9, value="교자도 시켰어요")], "그대로 둬도 돼요")
        self.assertEqual(p.edits, [])

    def test_title_memo(self):
        p = validate_proposal(TITLE, BLOCKS, memo(-1), [AIEdit(block_index=-1, value=" 테스트식당 라멘 맛집 \n")], "")
        self.assertEqual([(e.before, e.after) for e in p.edits], [(TITLE, "테스트식당 라멘 맛집")])

    def test_memo_on_non_text_block(self):
        p = validate_proposal(TITLE, BLOCKS, memo(3), [AIEdit(block_index=4, value="x")], "")
        self.assertEqual(p.edits, [])
        self.assertTrue(p.notes)


IMAGES = [ImageInfo(path="", category="EXTERIOR", description="가게 앞")] + [
    ImageInfo(path="", category="FOOD_ITEM:라멘", description=f"라멘 {i}") for i in range(3)]


class FakeLLM:
    def __init__(self, output=None, error=None):
        self.output, self.error, self.calls = output, error, []

    async def parse(self, role, content, output_format, **kwargs):
        self.calls.append({"role": role, "content": content, "output_format": output_format, **kwargs})
        if self.error:
            raise self.error
        return LLMResult(parsed=self.output, model="claude-sonnet-5-5", input_tokens=5000,
                         output_tokens=800, cost_usd=0.03)


def output(*proposals):
    return MemoEditOutput(proposals=list(proposals))


class SuggestMemoEditsTest(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_contents(self):
        m = Memo(id="a", block_index=7, quote="맛있었어요", comment="맛을 장면으로", source="review",
                 thread=[MemoTurn(role="ai", text="국물 맛을 넣었어요"), MemoTurn(role="user", text="짜다는 말은 빼 줘")])
        fake = FakeLLM(output())
        await suggest_memo_edits(TITLE, BLOCKS, {"place_name": "테스트식당"}, IMAGES, [], [m],
                                 [UserAnswer(question="국물은?", answer="진했음")], client=fake)
        call = fake.calls[0]
        self.assertEqual(call["role"], "reviser")
        self.assertIs(call["output_format"], MemoEditOutput)
        self.assertEqual(call["system"], SYSTEM)
        self.assertEqual(call["effort"], "medium")
        prompt = call["content"][0]["text"]
        for part in ["[메모 고치기 규칙]", "[형식 규칙]", "- id: a (검수 지적)",
                     "고칠 수 있는 블록: [4], [7], [9]", '드래그한 부분: "맛있었어요"',
                     "블로그 주인: 짜다는 말은 빼 줘", "답: 진했음", "[7] text"]:
            self.assertIn(part, prompt)

    async def test_validates_each_proposal(self):
        memos = [Memo(id="a", block_index=7, comment="x"), Memo(id="b", block_index=-1, comment="y")]
        fake = FakeLLM(output(
            AIProposal(memo_id="a", edits=[AIEdit(block_index=7, value="새 글"), AIEdit(block_index=0, value="범위 밖")],
                       opinion="맛을 바꿨어요"),
            AIProposal(memo_id="zz", edits=[AIEdit(block_index=9, value="모르는 메모")], opinion=""),
            AIProposal(memo_id="b", edits=[AIEdit(block_index=-1, value="새 제목")], opinion="제목"),
            AIProposal(memo_id="a", edits=[AIEdit(block_index=9, value="두 번째 안")], opinion=""),
        ))
        r = await suggest_memo_edits(TITLE, BLOCKS, {}, IMAGES, [], memos, [], client=fake)
        self.assertEqual([p.memo_id for p in r.proposals], ["a", "b"])
        a, b = r.proposals
        self.assertEqual([(e.block_index, e.after) for e in a.edits], [(7, "새 글")])
        self.assertEqual(len(a.notes), 1)
        self.assertEqual(b.edits[0].before, TITLE)
        self.assertEqual(r.usage["cost_usd"], 0.03)

    async def test_missing_proposal_and_invalid_memo(self):
        memos = [Memo(id="img", block_index=3, comment="사진"), Memo(id="a", block_index=7, comment="x")]
        fake = FakeLLM(output())
        r = await suggest_memo_edits(TITLE, BLOCKS, {}, IMAGES, [], memos, [], client=fake)
        self.assertEqual([p.memo_id for p in r.proposals], ["img", "a"])
        self.assertTrue(all(p.edits == [] and p.notes for p in r.proposals))
        self.assertNotIn("id: img", fake.calls[0]["content"][0]["text"])  # 잘못된 메모는 AI에 안 보낸다

    async def test_no_call_when_all_memos_invalid(self):
        fake = FakeLLM(output())
        r = await suggest_memo_edits(TITLE, BLOCKS, {}, IMAGES, [], [Memo(id="q", block_index=1, comment="x")], [], client=fake)
        self.assertEqual(fake.calls, [])
        self.assertIsNone(r.usage)
        self.assertEqual(len(r.proposals), 1)

    async def test_llm_error_propagates(self):
        with self.assertRaises(LLMError):
            await suggest_memo_edits(TITLE, BLOCKS, {}, IMAGES, [], [memo(7)], [],
                                     client=FakeLLM(error=LLMError("크레딧 부족")))


class FactPhotosTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.images = []
        for i in range(4):
            path = os.path.join(self.tmp.name, f"{i}.jpg")
            Image.new("RGB", (40, 30), (i * 40, 100, 100)).save(path)
            self.images.append(ImageInfo(path=path, category="X", description=f"사진 {i}"))
        self.images[2] = ImageInfo(path=os.path.join(self.tmp.name, "없는파일.jpg"), category="X")

    def tearDown(self):
        self.tmp.cleanup()

    def test_photo_block_before(self):
        self.assertEqual(photo_block_before(BLOCKS, 7), 5)   # 6번 구분선을 건너뛴 5번 사진 묶음
        self.assertEqual(photo_block_before(BLOCKS, 4), 3)
        self.assertIsNone(photo_block_before(BLOCKS, 10))    # 바로 앞이 글
        self.assertIsNone(photo_block_before(BLOCKS, 0))

    def test_only_fact_review_memos_get_photos(self):
        memos = [
            Memo(id="f", block_index=7, comment="x", source="review", kind="사실"),   # 사진 1, 2(파일 없음)
            Memo(id="t", block_index=7, comment="x", source="review", kind="말투"),
            Memo(id="u", block_index=4, comment="x", source="user", kind="사실"),
            Memo(id="g", block_index=4, comment="x", source="review", kind="사실"),   # 사진 0
        ]
        photos = fact_photos(memos, BLOCKS, self.images)
        self.assertEqual({k: [i for i, _ in v] for k, v in photos.items()}, {"f": [1], "g": [0]})

    def test_photo_cap(self):
        blocks = [ContentBlock(type="image", image_indices=list(range(10))), ContentBlock(type="text", value="글")]
        images = [self.images[0]] * 10
        photos = fact_photos([Memo(id="f", block_index=1, comment="x", source="review", kind="사실")], blocks, images)
        self.assertEqual(len(photos["f"]), MAX_FACT_PHOTOS)

    async def test_photos_are_attached_and_listed(self):
        memo_f = Memo(id="f", block_index=4, comment="확인", source="review", kind="사실")
        fake = FakeLLM(output())
        await suggest_memo_edits(TITLE, BLOCKS, {}, self.images, [], [memo_f, memo(7, "u")], [], client=fake)
        content = fake.calls[0]["content"]
        self.assertEqual([c["type"] for c in content], ["text", "text", "image"])
        self.assertEqual(content[1]["text"], "[사진 0] 사실 확인용")
        prompt = content[0]["text"]
        self.assertIn("사실 확인용 사진: 사진 0 (아래에 붙임)", prompt)
        self.assertIn("사진에 ~가 보여서 그대로 뒀어요", prompt)

    async def test_no_photos_for_other_memos(self):
        fake = FakeLLM(output())
        await suggest_memo_edits(TITLE, BLOCKS, {}, self.images, [], [memo(7)], [], client=fake)
        self.assertEqual(len(fake.calls[0]["content"]), 1)


class MemoEditEndpointTest(unittest.TestCase):
    def setUp(self):
        from app.main import app
        self.client = TestClient(app)
        self.body = {"title": TITLE, "blocks": [b.model_dump() for b in BLOCKS],
                     "images": [i.model_dump() for i in IMAGES], "memos": [memo(7).model_dump()]}

    def test_success(self):
        fake = FakeLLM(output(AIProposal(memo_id="m1", edits=[AIEdit(block_index=7, value="새 글")], opinion="ok")))
        with patch("app.api.v1.endpoints.posts.suggest_memo_edits",
                   lambda *a: suggest_memo_edits(*a, client=fake)):
            res = self.client.post("/api/v1/posts/memo-edit", json=self.body).json()
        self.assertTrue(res["success"])
        self.assertEqual(res["data"]["proposals"][0]["edits"][0]["before"], BLOCKS[7].value)

    def test_llm_error(self):
        fake = FakeLLM(error=LLMError("크레딧 부족"))
        with patch("app.api.v1.endpoints.posts.suggest_memo_edits",
                   lambda *a: suggest_memo_edits(*a, client=fake)):
            res = self.client.post("/api/v1/posts/memo-edit", json=self.body).json()
        self.assertFalse(res["success"])
        self.assertEqual(res["error"], "LLM_ERROR")


if __name__ == "__main__":
    unittest.main()
