"""
photo_dedup 단위 테스트. 실제 사진 대신 코드로 만든 무늬 이미지를 쓴다.

실행: cd backend → venv\\Scripts\\python -m unittest discover tests
"""
import random
import unittest

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from app.services.photo_dedup import SIMILAR_THRESHOLD, dhash, group_similar, hamming, sharpness


def pattern(seed, size=(400, 300)):
    """seed마다 다른, 도형이 흩어진 무늬 이미지."""
    rng = random.Random(seed)
    img = Image.new("RGB", size, (rng.randrange(256), rng.randrange(256), rng.randrange(256)))
    draw = ImageDraw.Draw(img)
    for _ in range(25):
        x, y = rng.randrange(size[0]), rng.randrange(size[1])
        r = rng.randrange(10, 60)
        color = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
    return img


def burst_of(img):
    """연사 흉내: 3% 이동 + 밝기 8% 변화."""
    w, h = img.size
    c = int(w * 0.03)
    return ImageEnhance.Brightness(img.crop((c, c, w, h)).resize((w, h))).enhance(1.08)


class TestHash(unittest.TestCase):
    def test_same_image_distance_zero(self):
        img = pattern(1)
        self.assertEqual(hamming(dhash(img), dhash(img.copy())), 0)

    def test_burst_is_close(self):
        img = pattern(1)
        self.assertLessEqual(hamming(dhash(img), dhash(burst_of(img))), SIMILAR_THRESHOLD)

    def test_resized_is_close(self):
        img = pattern(1)
        self.assertLessEqual(hamming(dhash(img), dhash(img.resize((200, 150)))), SIMILAR_THRESHOLD)

    def test_different_images_are_far(self):
        self.assertGreater(hamming(dhash(pattern(1)), dhash(pattern(2))), SIMILAR_THRESHOLD)


class TestGroupSimilar(unittest.TestCase):
    def test_groups_only_bursts(self):
        a, b = pattern(1), pattern(2)
        images = [a, b, burst_of(a), pattern(3)]
        self.assertEqual([sorted(g) for g in group_similar(images)], [[0, 2]])

    def test_chain_of_bursts_is_one_group(self):
        a = pattern(1)
        images = [a, burst_of(a), burst_of(burst_of(a))]
        self.assertEqual([sorted(g) for g in group_similar(images)], [[0, 1, 2]])

    def test_sharpest_first(self):
        a = pattern(1)
        blurry = a.filter(ImageFilter.GaussianBlur(3))
        self.assertEqual(group_similar([blurry, a]), [[1, 0]])

    def test_no_groups(self):
        self.assertEqual(group_similar([pattern(1), pattern(2)]), [])
        self.assertEqual(group_similar([]), [])


class TestSharpness(unittest.TestCase):
    def test_blur_lowers_score(self):
        img = pattern(1)
        self.assertLess(sharpness(img.filter(ImageFilter.GaussianBlur(3))), sharpness(img))


if __name__ == "__main__":
    unittest.main()
