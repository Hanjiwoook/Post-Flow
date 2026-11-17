"""
발행 봇이 어떤 사진을 올리는지 확인한다 (브라우저 없이 계산 부분만).

실행: cd backend → venv\Scripts\python -m unittest discover tests
"""
import unittest

from app.services.automation.naver_v2 import block_image_indices, unused_image_indices

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


if __name__ == "__main__":
    unittest.main()
