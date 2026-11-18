"""
가게 정보 정리(/place-info) 테스트. 실제 지도·Claude 호출 없이 가짜로 확인한다.

실행: cd backend → venv\Scripts\python -m unittest discover tests
"""
import asyncio
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.services.llm_client import LLMError, LLMResult
from app.services.place_summarizer import MAX_RAW_CHARS, PlaceInfo, build_place_prompt, summarize_place

RAW = "--- [홈 정보] ---\n테스트식당\n주소\n서울 어딘가 1층\n전화번호\n010-0000-0000\n저장\n공유"


def fake_info():
    return PlaceInfo(address="서울 어딘가 1층", phone="010-0000-0000", business_hours="", parking="",
                     amenities=["포장", "예약"], owner_intro="", recent_event="",
                     place_vibe=["혼밥하기 좋은"], visitor_insight="키오스크로 주문한다는 리뷰가 많다.")


class FakeLLM:
    def __init__(self, error=None):
        self.error, self.calls = error, []

    async def parse(self, role, content, output_format, **kwargs):
        self.calls.append({"role": role, "content": content, "output_format": output_format, **kwargs})
        if self.error:
            raise self.error
        return LLMResult(parsed=fake_info(), model="claude-opus-5-5", input_tokens=4000,
                         output_tokens=300, cost_usd=0.022)


class TestPlacePrompt(unittest.TestCase):
    def test_prompt_has_rules_name_and_raw_text(self):
        prompt = build_place_prompt("테스트식당", RAW)
        self.assertIn("원문에 없는 칸은 빈 문자열", prompt)
        self.assertIn("[가게 이름]\n테스트식당", prompt)
        self.assertIn("010-0000-0000", prompt)

    def test_long_raw_text_is_cut(self):
        prompt = build_place_prompt("테스트식당", "Q" * (MAX_RAW_CHARS + 500))
        self.assertEqual(prompt.count("Q"), MAX_RAW_CHARS)

    def test_uses_summary_role_with_low_effort(self):
        fake = FakeLLM()
        result = asyncio.run(summarize_place("테스트식당", RAW, client=fake))
        self.assertEqual(result.parsed.address, "서울 어딘가 1층")
        self.assertEqual(fake.calls[0]["role"], "summary")
        self.assertIs(fake.calls[0]["output_format"], PlaceInfo)
        self.assertEqual(fake.calls[0]["effort"], "low")


class TestPlaceInfoEndpoint(unittest.TestCase):
    def setUp(self):
        from app.main import app
        self.client = TestClient(app)

    def get(self):
        return self.client.get("/api/v1/place-info", params={"query": "테스트식당"}).json()

    def test_success_fills_app_fields(self):
        scraped = {"place_name": "테스트식당", "raw_text": RAW}

        async def ok(name, raw):
            return await FakeLLM().parse("summary", [], PlaceInfo)

        with patch("app.api.v1.endpoints.system.naver_map_service.get_place_info", return_value=scraped), \
             patch("app.api.v1.endpoints.system.summarize_place", ok):
            d = self.get()
        self.assertTrue(d["success"])
        data = d["data"]
        self.assertEqual(data["place_name"], "테스트식당")
        self.assertEqual(data["address"], "서울 어딘가 1층")
        self.assertEqual(data["amenities"], ["포장", "예약"])       # 앱은 목록으로 받는다
        self.assertEqual(data["place_vibe"], ["혼밥하기 좋은"])
        self.assertIn("키오스크", data["visitor_insight"])
        self.assertEqual(data["usage"]["model"], "claude-opus-5-5")

    def test_place_not_found_is_failure(self):
        # 예전에는 "검색 결과 없음"이 원문처럼 넘어가 success=True였다
        scraped = {"place_name": "테스트식당", "raw_text": "", "error": "네이버 지도에서 '테스트식당'를 찾지 못했습니다."}
        with patch("app.api.v1.endpoints.system.naver_map_service.get_place_info", return_value=scraped):
            d = self.get()
        self.assertFalse(d["success"])
        self.assertIn("찾지 못했습니다", d["message"])

    def test_ai_failure_is_reported(self):
        # 예전 Gemini 코드는 실패하면 빈 칸과 success=True를 돌려줬다
        scraped = {"place_name": "테스트식당", "raw_text": RAW}

        async def fail(name, raw):
            raise LLMError("요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.")

        with patch("app.api.v1.endpoints.system.naver_map_service.get_place_info", return_value=scraped), \
             patch("app.api.v1.endpoints.system.summarize_place", fail):
            d = self.get()
        self.assertFalse(d["success"])
        self.assertIn("요청이 너무 많습니다", d["message"])


if __name__ == "__main__":
    unittest.main()
