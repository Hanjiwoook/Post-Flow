"""
발행 봇이 어떤 사진을 올리는지 확인한다 (브라우저 없이 계산 부분만).

실행: cd backend → venv\Scripts\python -m unittest discover tests
"""
import unittest

from app.services.automation.naver_v2 import block_image_indices, pick_place_result, unused_image_indices

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


if __name__ == "__main__":
    unittest.main()
