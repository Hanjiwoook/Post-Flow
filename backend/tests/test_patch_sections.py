"""
/patch의 가게 정보 갈아 끼우기 (AI 호출 없음). 11/19 gemini_service.py에서 posts.py로 옮기면서 동작이 그대로인지 확인한다.

실행: cd backend → venv/Scripts/python -X utf8 -m unittest discover tests
"""
import unittest

from fastapi.testclient import TestClient

from app.api.v1.endpoints.posts import patch_sections
from app.schemas.post import ContentBlock

FACTS = {"place_name": "유카이도", "address": "서울 구로구", "business_hours": "11-21", "phone": "02-000", "parking": "없음"}


class TestPatchSections(unittest.TestCase):
    def test_replaces_only_marked_quote(self):
        blocks = [
            ContentBlock(type="text", value="안녕하세요"),
            ContentBlock(type="quote", value="[매장 위치 & 정보] 옛 정보"),
            ContentBlock(type="image", value=None, image_indices=[0]),  # value가 없어도 멈추지 않는다 (784540a)
        ]
        out = patch_sections(blocks, FACTS)
        self.assertEqual(out[0], blocks[0])
        self.assertEqual(out[1].value, "[매장 위치 & 정보] 유카이도 / 서울 구로구 / 11-21 / 02-000 / 없음")
        self.assertEqual(out[2], blocks[2])

    def test_new_format_posts_are_unchanged(self):
        # 지금 글쓰기의 가게 정보 인용구(quotation_line)는 표시가 없어서 바뀌지 않는다
        blocks = [ContentBlock(type="quote", value="유카이도", style="quotation_line")]
        self.assertEqual(patch_sections(blocks, FACTS), blocks)


class TestRemovedRoutes(unittest.TestCase):
    def setUp(self):
        from app.main import app
        self.client = TestClient(app)

    def test_gemini_routes_are_gone(self):
        self.assertEqual(self.client.post("/api/v1/posts/refine", json={}).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/style/learn", json={}).status_code, 404)
        self.assertEqual(self.client.post("/api/v1/style/preview", json={}).status_code, 404)

    def test_patch_still_works(self):
        body = self.client.post("/api/v1/posts/patch", json={
            "title": "t", "facts": FACTS,
            "blocks": [{"type": "quote", "value": "[매장 위치 & 정보] 옛 정보"}],
        }).json()
        self.assertTrue(body["success"])
        self.assertIn("유카이도", body["data"]["blocks"][0]["value"])


if __name__ == "__main__":
    unittest.main()
