"""
format_checker.check_post 단위 테스트.
실제 블로그 글 대신, 명세서 형식을 흉내 낸 짧은 가짜 글을 쓴다.

실행: cd backend → venv\\Scripts\\python -m unittest discover tests
"""
import unittest

from app.schemas.post import ContentBlock
from app.services.format_checker import check_post


def text(*lines):
    return {"type": "text", "value": "\n".join(lines)}


def images(n):
    return {"type": "image", "image_count": n}


def good_post():
    """명세서 형식을 지킨 가짜 글 (크롤러 형식)."""
    return [
        text("안녕하세요 😊", "날이 많이 추워졌네요", "오늘은 테스트식당에", "다녀왔어요!"),
        {"type": "quote", "value": "테스트식당", "style": "default"},
        {"type": "map", "value": "테스트식당", "address": "서울 어딘가"},
        {"type": "quote", "value": "🚩위치 : 서울 어딘가\n⏳영업시간 : 매일 11:00 - 21:00", "style": "quotation_line"},
        images(2),
        text("가게 앞에 도착하니", "벌써 웨이팅이 있더라구요", "저는 20분 정도 기다렸어요"),
        images(2),
        text("메뉴는 이렇게", "구성되어 있었어요", "가격도 괜찮았구요 😋"),
        images(1),
        text("국물이 정말 진하고", "면이 쫄깃했어요", "양도 넉넉했습니다", ".", ".",
             "전체적으로 만족스러웠어요", "다음엔 다른 메뉴도 먹어 볼래요", "👍테스트식당 추천합니다👍"),
    ]


def old_ai_post():
    """지금 프롬프트가 만드는 모양의 글: 섹션 태그, 긴 줄, 구분선, 별점, 과장 표현."""
    return [
        text("[인사말] 안녕하세요! 맛집과 일상을 기록하는 블로거입니다. 오늘도 직접 발로 뛰어 찾은 리얼 맛집 정보를 전해드릴게요!"),
        {"type": "quote", "value": "주소: 서울 어딘가", "style": "box"},
        {"type": "image", "image_indices": [0, 1, 2, 3]},
        text("[외관] 매장 외관은 깔끔한 우드톤으로 꾸며져 있어 들어가기 전부터 기대감이 높아졌습니다."),
        {"type": "divider", "style": "line"},
        text("[음식:라멘] 특히 국물이 진하고 깊은 맛이 나는 인생 맛집이었습니다. 또한 다양한 메뉴를 제공합니다."),
        text("[총평] ⭐⭐⭐⭐⭐ 강력 추천드립니다!"),
    ]


def failed_rules(report):
    return {r.rule for r in report.results if not r.passed}


class TestGoodPost(unittest.TestCase):
    def test_passes_without_errors_or_warnings(self):
        report = check_post(good_post(), title="테스트식당 어딘가동 라멘 맛집 내돈내산 추천")
        self.assertTrue(report.passed, report.summary())
        # 가짜 글은 테스트용이라 짧다. 분량 경고만 빼고 warning이 없어야 한다
        self.assertEqual([w.rule for w in report.warnings], ["너무 짧은 글"], report.summary())

    def test_accepts_app_content_blocks(self):
        # 앱 형식(image_indices)과 ContentBlock 객체도 같은 결과여야 한다
        blocks = []
        for b in good_post():
            if b["type"] == "image":
                blocks.append(ContentBlock(type="image", image_indices=list(range(b["image_count"]))))
            else:
                blocks.append(ContentBlock(type=b["type"], value=b.get("value"), style=b.get("style")))
        report = check_post(blocks)
        self.assertTrue(report.passed, report.summary())

    def test_zero_width_space_lines_are_ignored(self):
        blocks = good_post()
        blocks[0] = text("안녕하세요 😊", "\u200b", "오늘은 테스트식당에", "다녀왔어요!")
        self.assertTrue(check_post(blocks).passed)


class TestOldAiPost(unittest.TestCase):
    def test_fails_with_expected_errors(self):
        report = check_post(old_ai_post())
        self.assertFalse(report.passed)
        self.assertTrue({
            "도입부 순서", "섹션 제목 없음", "구분선 없음", "해시태그·별점 기호 없음",
            "과장 표현 없음", "맺음말 앞 '.' 줄",
        } <= failed_rules(report), report.summary())

    def test_ai_phrases_warn(self):
        self.assertIn("AI 말투 절제", {r.rule for r in check_post(old_ai_post()).warnings})


class TestLengthRules(unittest.TestCase):
    """2026-11-17: 길이 상한은 없애고 너무 짧은 것만 warning으로 알린다."""

    def test_long_lines_are_allowed(self):
        blocks = good_post()
        blocks[5] = text("가게 앞에 도착하니 벌써 웨이팅이 꽤 길게 있었는데 회전이 빨라서 금방 들어갔어요",
                         "저는 20분 정도 기다렸어요")
        self.assertTrue(check_post(blocks).passed)

    def test_long_post_has_no_length_warning(self):
        blocks = good_post()
        blocks[-1] = text(*(["국물이 진하고 면이 쫄깃해서 계속 손이 갔어요"] * 30), ".", ".", "다음에 또 올게요")
        self.assertNotIn("너무 짧은 글", failed_rules(check_post(blocks)))

    def test_short_post_warns_but_passes(self):
        report = check_post(good_post())
        self.assertIn("너무 짧은 글", {w.rule for w in report.warnings})
        self.assertTrue(report.passed)  # warning이라 막지는 않는다

    def test_many_long_lines_warn_for_mobile(self):
        blocks = good_post()
        blocks[5] = text("가게 앞에 도착하니 벌써 웨이팅이 꽤 길게 있었어요",
                         "회전이 빨라서 생각보다 금방 들어갈 수 있었어요",
                         "입구 앞에는 나무 벤치가 두 개 놓여 있었습니다",
                         "저는 20분 정도 기다렸어요")
        blocks[7] = text("메뉴는 키오스크로 주문하는 방식이었어요",
                         "라멘 종류가 생각보다 다양해서 한참 고민했습니다",
                         "가격도 이 정도면 괜찮은 편이었구요 😋")
        report = check_post(blocks)
        self.assertIn("폰에서 꺾이는 줄", {w.rule for w in report.warnings})
        self.assertTrue(report.passed)  # 참고용이라 막지 않는다

    def test_one_line_photo_text_warns(self):
        blocks = good_post()
        blocks[5] = text("웨이팅이 있었어요")  # 사진 묶음 뒤 첫 글 (블록 5)
        result = {r.rule: r for r in check_post(blocks).results}["사진 설명 충분"]
        self.assertFalse(result.passed)
        self.assertIn("[5]", result.detail)

    def test_dot_lines_do_not_count_as_photo_text(self):
        blocks = good_post()
        blocks[5] = text("웨이팅이 있었어요", ".")
        self.assertIn("사진 설명 충분", failed_rules(check_post(blocks)))


class TestImageGroups(unittest.TestCase):
    """2026-11-17: 사진 묶음 장수 제한을 없앴다. AI가 장면에 맞게 묶는다."""

    def test_big_group_is_allowed(self):
        blocks = good_post()
        blocks[4] = images(6)
        report = check_post(blocks)
        self.assertTrue(report.passed, report.summary())
        self.assertNotIn("2장 묶음 위주", {r.rule for r in report.results})

    def test_empty_group_is_error(self):
        blocks = good_post()
        blocks[4] = {"type": "image", "image_indices": []}
        self.assertIn("빈 사진 묶음 없음", {r.rule for r in check_post(blocks).errors})


class TestSingleRules(unittest.TestCase):
    def test_greeting_must_come_first(self):
        blocks = good_post()
        blocks[0] = text("오늘은 테스트식당에", "다녀왔어요!")
        self.assertIn("인사로 시작", failed_rules(check_post(blocks)))

    def test_info_quote_required_for_single_store(self):
        blocks = [b for b in good_post() if "🚩" not in (b.get("value") or "")]
        self.assertIn("가게 정보 인용구", failed_rules(check_post(blocks)))

    def test_info_quote_skipped_for_multi_store(self):
        blocks = [b for b in good_post() if "🚩" not in (b.get("value") or "")]
        blocks += [{"type": "quote", "value": "두번째식당", "style": "default"},
                   {"type": "map", "value": "두번째식당"}]
        rules = {r.rule for r in check_post(blocks).results}
        self.assertNotIn("가게 정보 인용구", rules)

    def test_hype_phrase_is_error(self):
        blocks = good_post()
        blocks[5] = text("여기는 정말", "역대급이었어요")
        self.assertIn("과장 표현 없음", {r.rule for r in check_post(blocks).errors})

    def test_single_ai_phrase_is_allowed(self):
        # 원본 글에도 '특히'가 한 번 나온다. 한 번은 괜찮다.
        blocks = good_post()
        blocks[5] = text("특히 국물이", "진했어요")
        self.assertNotIn("AI 말투 절제", failed_rules(check_post(blocks)))

    def test_many_emojis_warn(self):
        blocks = good_post()
        blocks[5] = text("맛있어요 😋", "최고예요 🤩", "또 올게요 💕")
        self.assertIn("이모지 절제", {r.rule for r in check_post(blocks).warnings})

    def test_title_without_keywords_warns(self):
        report = check_post(good_post(), title="테스트식당 다녀왔어요")
        self.assertIn("검색용 제목", {r.rule for r in report.warnings})
        self.assertTrue(report.passed)  # 제목은 경고일 뿐 통과에 영향 없음

    def test_sponsor_rule_only_when_sponsored(self):
        self.assertNotIn("협찬 표시", {r.rule for r in check_post(good_post()).results})
        self.assertIn("협찬 표시", {r.rule for r in check_post(good_post(), sponsored=True).errors})

    def test_sponsor_disclosure_in_first_text_passes(self):
        blocks = good_post()
        blocks[0] = text("안녕하세요 😊", "업체로부터 식사를", "제공받아 작성한 글입니다")
        self.assertTrue(check_post(blocks, title="테스트식당 라멘 맛집 추천", sponsored=True).passed)

    def test_sponsored_post_with_naedon_fails(self):
        blocks = good_post()
        blocks[0] = text("안녕하세요 😊", "협찬으로 다녀왔어요")
        report = check_post(blocks, title="테스트식당 라멘 맛집 내돈내산", sponsored=True)
        self.assertIn("협찬 표시", {r.rule for r in report.errors})

    def test_period_endings_are_error(self):
        blocks = good_post()
        blocks[5] = text("가게 앞에 도착했어요.", "웨이팅이 있었어요.", "20분 기다렸어요.", "들어갔어요.")
        self.assertIn("줄 끝 마침표 없음", {r.rule for r in check_post(blocks).errors})

    def test_dot_only_lines_are_not_period_endings(self):
        # '.' 한 글자 구분 줄은 원본 형식이라 마침표로 세지 않는다
        self.assertNotIn("줄 끝 마침표 없음", failed_rules(check_post(good_post())))

    def test_spaced_emoji_warns(self):
        blocks = good_post()
        blocks[5] = text("맛있어요 😋", "최고예요 🤩", "또 올게요 💕", "좋았어요 😊")
        self.assertIn("이모지 붙여 쓰기", {r.rule for r in check_post(blocks).warnings})

    def test_attached_emoji_passes(self):
        blocks = good_post()
        blocks[5] = text("맛있어요😋", "최고예요🤩", "좋았어요😊", "가게 앞에 도착")
        self.assertNotIn("이모지 붙여 쓰기", failed_rules(check_post(blocks)))

    def test_emoji_rule_skipped_with_few_emojis(self):
        self.assertNotIn("이모지 붙여 쓰기", {r.rule for r in check_post(good_post()).results})

    def test_repeated_guyo_warns(self):
        blocks = good_post()
        blocks[5] = text(*[f"메뉴{i}도 있구요" for i in range(8)])
        self.assertIn("끝맺음 다양성", {r.rule for r in check_post(blocks).warnings})

    def test_ai_taste_cliches_warn(self):
        blocks = good_post()
        blocks[5] = text("풍미가 가득하고", "재료가 어우러져요")
        self.assertIn("AI 말투 절제", {r.rule for r in check_post(blocks).warnings})

    def test_title_rule_skipped_without_title(self):
        self.assertNotIn("검색용 제목", {r.rule for r in check_post(good_post()).results})


if __name__ == "__main__":
    unittest.main()
