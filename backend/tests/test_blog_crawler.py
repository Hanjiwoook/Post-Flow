"""
blog_crawler.parse_post_blocks 단위 테스트.
실제 블로그 글 대신, 네이버 스마트에디터 구조를 흉내 낸 짧은 가짜 HTML을 쓴다.

실행: cd backend → venv\\Scripts\\python -m unittest discover tests
"""
import unittest

from app.services.blog_crawler import parse_post_blocks, blocks_to_text


def _text(*lines):
    ps = "".join(f'<p class="se-text-paragraph"><span>{l}</span></p>' for l in lines)
    return f'<div class="se-component se-text se-l-default"><div class="se-module se-module-text">{ps}</div></div>'


def _images(n, cls="se-imageStrip se-imageStrip2", caption=None):
    imgs = "".join('<img class="se-image-resource" src="x.jpg"/>' for _ in range(n))
    cap = f'<div class="se-module se-caption"><p class="se-text-paragraph">{caption}</p></div>' if caption else ""
    return f'<div class="se-component {cls} se-l-default">{imgs}{cap}</div>'


ZWSP = "\u200b"  # 네이버가 빈 줄에 넣는 zero-width space

SAMPLE = f"""
<html><body>
<div class="se-main-container">
  <div class="se-component se-documentTitle se-l-default"><p>제목은 건너뛴다</p></div>
  {_text("안녕하세요~ 😊", ZWSP, "오늘은 테스트식당 다녀왔어요")}
  <div class="se-component se-quotation se-l-default">
    <blockquote><div class="se-module se-quote"><p class="se-text-paragraph">테스트식당</p></div></blockquote>
  </div>
  <div class="se-component se-placesMap se-l-default">
    <strong class="se-map-title">테스트식당 본점</strong><p class="se-map-address">서울 테스트구 1</p>
  </div>
  <div class="se-component se-quotation se-l-quotation_line">
    <div class="se-module se-quote">
      <p class="se-text-paragraph">🚩위치 : 서울 테스트구 1</p><p class="se-text-paragraph">⏳영업시간 : 매일 11:00~22:00</p>
    </div>
  </div>
  {_images(2, caption="[짜장, 탕수육]")}
  {_text("맛있었어요!")}
  {_images(1, cls="se-image")}
  <div class="se-component se-horizontalLine se-l-default"></div>
  <div class="se-component se-oglink se-l-default"></div>
  {_text(ZWSP)}
</div>
</body></html>
"""


class ParsePostBlocksTest(unittest.TestCase):
    def setUp(self):
        self.blocks = parse_post_blocks(SAMPLE)

    def test_block_order_and_types(self):
        # 제목과 빈 글 블록은 빠지고, 나머지는 순서대로 나온다
        self.assertEqual(
            [b["type"] for b in self.blocks],
            ["text", "quote", "map", "quote", "image", "text", "image", "divider", "other"],
        )

    def test_text_keeps_lines_and_drops_zero_width_space(self):
        self.assertEqual(self.blocks[0]["value"], "안녕하세요~ 😊\n\n오늘은 테스트식당 다녀왔어요")

    def test_quote_style_comes_from_layout_class(self):
        self.assertEqual(self.blocks[1]["style"], "default")
        self.assertEqual(self.blocks[3]["style"], "quotation_line")
        self.assertEqual(self.blocks[3]["value"], "🚩위치 : 서울 테스트구 1\n⏳영업시간 : 매일 11:00~22:00")

    def test_map_has_name_and_address(self):
        self.assertEqual(self.blocks[2], {"type": "map", "value": "테스트식당 본점", "address": "서울 테스트구 1"})

    def test_image_count_and_caption(self):
        self.assertEqual(self.blocks[4], {"type": "image", "image_count": 2, "value": "[짜장, 탕수육]"})
        self.assertEqual(self.blocks[6], {"type": "image", "image_count": 1})

    def test_unknown_component_is_kept_as_other(self):
        self.assertEqual(self.blocks[8], {"type": "other", "kind": "se-oglink"})

    def test_blocks_to_text_uses_text_and_quote_only(self):
        text = blocks_to_text(self.blocks)
        self.assertIn("테스트식당\n\n🚩위치", text)
        self.assertNotIn("테스트식당 본점", text)  # 지도 블록은 말투 분석에서 뺀다

    def test_page_without_main_container_returns_empty(self):
        self.assertEqual(parse_post_blocks("<html><body>삭제된 글</body></html>"), [])


if __name__ == "__main__":
    unittest.main()
