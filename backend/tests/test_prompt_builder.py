"""
prompt_builder 단위 테스트. Gemini를 부르지 않고, 만들어진 지시문 문자열만 확인한다.

실행: cd backend → venv\\Scripts\\python -m unittest discover tests
"""
import unittest

from app.services.format_checker import HYPE_PHRASES, MIN_PHOTO_TEXT_LINES
from app.services.prompt_builder import (
    SKELETON, build_info_quote, build_photo_list, build_writer_prompt,
)

FACTS = {
    "place_name": "테스트식당",
    "address": "서울 어딘가구 어딘가로 1",
    "business_hours": "매일 11:00 - 21:00",
    "phone": "",
    "parking": None,
    "waiting": "20분",
    "ordered_menu": "라멘, 교자",
    "rating": "4",
    "amenities": "",
}

PHOTOS = [
    {"category": "EXTERIOR", "description": "나무 간판", "hint": ""},
    {"category": "FOOD_ITEM:라멘", "description": "차슈 두 장이 올라간 라멘", "hint": "국물이 진했음"},
]


class TestInfoQuote(unittest.TestCase):
    def test_only_known_fields_in_spec_order(self):
        self.assertEqual(build_info_quote(FACTS),
                         "🚩위치 : 서울 어딘가구 어딘가로 1\n⏳영업시간 : 매일 11:00 - 21:00")

    def test_empty_facts(self):
        self.assertEqual(build_info_quote({}), "")


class TestWriterPrompt(unittest.TestCase):
    def setUp(self):
        self.prompt = build_writer_prompt(FACTS, PHOTOS)

    def test_contains_facts_and_photos(self):
        for expected in ["- 웨이팅: 20분", "- 주문한 메뉴: 라멘, 교자",
                         "- 사진 0 (EXTERIOR): 나무 간판",
                         "- 사진 1 (FOOD_ITEM:라멘): 차슈 두 장이 올라간 라멘 / 사용자 설명: 국물이 진했음"]:
            self.assertIn(expected, self.prompt)

    def test_empty_values_are_not_rendered(self):
        self.assertNotIn("None", self.prompt)
        self.assertNotIn("- 전화번호:", self.prompt)
        self.assertNotIn("📞전화번호 :", self.prompt)

    def test_shares_numbers_with_checker(self):
        self.assertIn(f"최소 {MIN_PHOTO_TEXT_LINES}줄 이상", self.prompt)

    def test_no_length_caps(self):
        # 2026-11-17 결정: 틀만 따르고 줄 길이·분량 상한은 두지 않는다
        self.assertIn("한 호흡(의미 단위)마다 줄을 바꿔", self.prompt)
        self.assertIn("글 전체 길이에 상한은 없다", self.prompt)
        self.assertIn("폰 화면 한 줄에 들어가게", self.prompt)
        self.assertIn("줄 수를 늘린다", self.prompt)
        for cap in ("10~16자", "3~6줄", "자를 넘기지 않는다"):
            self.assertNotIn(cap, self.prompt)
        for phrase in HYPE_PHRASES:
            self.assertIn(phrase, self.prompt)

    def test_photo_selection_and_report_fields(self):
        self.assertIn("excluded_images", self.prompt)
        self.assertIn("writing_notes", self.prompt)

    def test_old_template_is_gone(self):
        # 예전 프롬프트의 고정 인사말과 [섹션명] 지시가 없어야 한다
        self.assertNotIn("욱스", self.prompt)
        self.assertNotIn("[인사말]", self.prompt)

    def test_human_rhythm_rules(self):
        self.assertIn("줄 끝에 마침표(.)를 찍지 않는다", self.prompt)
        self.assertIn("앞 글자에 붙여 쓴다", self.prompt)
        self.assertIn("`~구요`는 글 전체에서 서너 번만", self.prompt)

    def test_taste_expression_section(self):
        self.assertIn("6. 맛 표현", self.prompt)
        self.assertIn("먹는 장면으로 풀어 쓴다", self.prompt)
        self.assertIn("풍미", self.prompt)  # 흔한 AI 맛 표현 금지 목록

    def test_no_weather_or_visit_history_guessing(self):
        self.assertNotIn("날씨·계절·상황", self.prompt)
        self.assertIn("날씨와 기온은 사실 목록에 없으면 쓰지 않는다", self.prompt)
        self.assertIn("`이번에도`", self.prompt)

    def test_rating_is_passed_to_closing(self):
        self.assertIn("만족도는 4점", self.prompt)


class TestOptions(unittest.TestCase):
    def test_paid_by_self_controls_naedon(self):
        self.assertIn("`내돈내산`을 한 번 쓴다", build_writer_prompt(FACTS, PHOTOS, paid_by_self=True))
        self.assertIn("`내돈내산`이라는 말은 쓰지 않는다", build_writer_prompt(FACTS, PHOTOS))

    def test_sponsored_requires_disclosure(self):
        prompt = build_writer_prompt(FACTS, PHOTOS, sponsored=True, sponsor_detail="식사 2인")
        self.assertIn("[협찬 표시]", prompt)
        self.assertIn("제공받은 것: 식사 2인", prompt)
        self.assertIn("첫 글 블록(인사) 안에", prompt)
        self.assertNotIn("`내돈내산`을 한 번 쓴다", prompt)

    def test_sponsored_overrides_paid(self):
        prompt = build_writer_prompt(FACTS, PHOTOS, paid_by_self=True, sponsored=True)
        self.assertIn("[협찬 표시]", prompt)
        self.assertNotIn("직접 결제한 방문이다", prompt)

    def test_sponsor_detail_optional(self):
        prompt = build_writer_prompt(FACTS, PHOTOS, sponsored=True)
        self.assertNotIn("제공받은 것:", prompt)
        self.assertIn("업체로부터 협찬을 받아 작성한 글입니다", prompt)

    def test_closing_phrase(self):
        self.assertIn("그대로 쓴다: 💕고마워요💕",
                      build_writer_prompt(FACTS, PHOTOS, closing_phrase="💕고마워요💕"))
        self.assertIn("지어내지 말고 생략", build_writer_prompt(FACTS, PHOTOS))

    def test_style_samples_are_trimmed_and_marked(self):
        sample = "\n".join(f"줄{i}" for i in range(20))
        prompt = build_writer_prompt(FACTS, PHOTOS, style_samples=[sample])
        self.assertIn("그대로 가져다 쓰지 않는다", prompt)
        self.assertIn("줄7", prompt)
        self.assertNotIn("줄8", prompt)

    def test_no_style_section_without_samples(self):
        self.assertNotIn("[말투 참고]", build_writer_prompt(FACTS, PHOTOS))

    def test_no_info_quote_when_unknown(self):
        prompt = build_writer_prompt({"place_name": "테스트식당"}, [])
        self.assertIn("정보 인용구는 빼고", prompt)
        self.assertIn("(사진 없음)", prompt)

    def test_similar_groups_hint(self):
        prompt = build_writer_prompt(FACTS, PHOTOS, similar_groups=[[1, 0]])
        self.assertIn("[거의 같은 사진]", prompt)
        self.assertIn("- 사진 1, 0", prompt)
        self.assertNotIn("[거의 같은 사진]", build_writer_prompt(FACTS, PHOTOS))

    def test_zero_rating_is_ignored(self):
        self.assertNotIn("만족도는", build_writer_prompt({"rating": "0.0"}, PHOTOS))

    def test_with_rating_revisit_and_recommend_are_required(self):
        prompt = build_writer_prompt(FACTS, PHOTOS)
        self.assertIn("재방문 의사 한 줄(다음에 먹어 보고 싶은 메뉴와 함께)", prompt)
        self.assertNotIn("만족도를 받지 못했다", prompt)

    def test_without_rating_revisit_is_not_guessed(self):
        facts = {k: v for k, v in FACTS.items() if k != "rating"}
        prompt = build_writer_prompt(facts, PHOTOS)
        self.assertIn("만족도를 받지 못했다", prompt)
        self.assertIn("짐작해서 쓰지 않는다", prompt)
        self.assertIn("만족도와 재방문 의사 확인 필요", prompt)
        self.assertNotIn("재방문 의사 한 줄(다음에 먹어 보고 싶은 메뉴와 함께) →", prompt)


class TestSkeleton(unittest.TestCase):
    def test_skeleton_has_no_section_tags(self):
        self.assertNotRegex(SKELETON, r"\[(외관|내부|메뉴판|인사말|총평)")

    def test_photo_list_numbers_match_order(self):
        self.assertTrue(build_photo_list(PHOTOS).startswith("- 사진 0"))


if __name__ == "__main__":
    unittest.main()
