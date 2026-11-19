"""
발행 봇이 어떤 사진을 올리는지 확인한다 (브라우저 없이 계산 부분만).

실행: cd backend → venv\Scripts\python -m unittest discover tests
"""
import unittest
from unittest import mock

from app.services.automation.naver_v2 import (
    NaverBlogAutomationV2, block_image_indices, pick_place_result, unused_image_indices,
)

BLOCKS = [
    {"type": "text", "value": "안녕하세요"},
    {"type": "image", "image_indices": [0, 1]},
    {"type": "text", "value": "외관"},
    {"type": "image", "image_index": 4},          # 예전 형식
    {"type": "image", "image_indices": [5, 6, 7, 8]},  # 4장 이상 묶음
]


class TestImageSelection(unittest.TestCase):
    def test_block_indices_support_old_format(self):
        self.assertEqual(block_image_indices(BLOCKS[1]), [0, 1])
        self.assertEqual(block_image_indices(BLOCKS[3]), [4])
        self.assertEqual(block_image_indices(BLOCKS[0]), [])

    def test_excluded_photos_are_not_uploaded(self):
        # 2, 3번(예: 영수증)은 글에 없으니 올리지 않는다
        self.assertEqual(unused_image_indices(BLOCKS, 9), [2, 3])

    def test_all_used(self):
        self.assertEqual(unused_image_indices(BLOCKS[1:2], 2), [])



class TestPickPlace(unittest.TestCase):
    RESULTS = ["테스트라멘 강남점 서울 강남구 테헤란로 1",
               "테스트라멘 구로점 서울 구로구 연동로 9 1층",
               "테스트라멘 부산점 부산 해운대구"]

    def test_picks_branch_matching_address(self):
        self.assertEqual(pick_place_result(self.RESULTS, "서울 구로구 연동로 9 테스트빌딩 1층"), 1)

    def test_city_word_alone_does_not_decide(self):
        # '서울'(시·도)만 겹치는 건 단서로 쓰지 않는다 → 첫 번째
        self.assertEqual(pick_place_result(self.RESULTS[:1] + self.RESULTS[2:], "서울특별시"), 0)

    def test_no_address_or_no_results(self):
        self.assertEqual(pick_place_result(self.RESULTS, ""), 0)
        self.assertEqual(pick_place_result([], "서울 구로구"), -1)


class TestRetry(unittest.TestCase):
    """publish()의 재시도: 실제 브라우저 대신 _execute_publish를 가짜로 바꿔 몇 번 시도하는지만 센다."""

    def _run(self, fake_execute):
        bot = NaverBlogAutomationV2()
        calls = []

        def execute(*args, **kwargs):
            calls.append(1)
            return fake_execute(bot, len(calls))

        with mock.patch.object(bot, "_execute_publish", side_effect=execute),                 mock.patch("app.services.automation.naver_v2.time.sleep"):
            result = bot.publish("제목", [], max_retries=3)
        return result, len(calls)

    def test_login_required_stops_without_retry(self):
        # 로그인 만료로 실패하면 다시 시도해도 같고, 로그인 페이지를 여러 번 여는 것은 보호조치 위험만 키운다
        def expired(bot, n):
            bot.login_required = True
            return False
        self.assertEqual(self._run(expired), (False, 1))

    def test_other_failures_retry_up_to_max(self):
        self.assertEqual(self._run(lambda bot, n: False), (False, 3))

    def test_success_on_second_try(self):
        self.assertEqual(self._run(lambda bot, n: n == 2), (True, 2))


if __name__ == "__main__":
    unittest.main()
