"""
저장 전 자가 검사 (editor_check) 테스트. 가짜 편집기 HTML은 11/17 실제 저장 직전 HTML 구조를 줄여서 만들었다.

실행: cd backend → venv\Scripts\python -m unittest discover tests
"""
import unittest

from app.services.automation.editor_check import check_editor_html


def para(text, align="center", size="se-fs15"):
    return (f'<p class="se-text-paragraph se-text-paragraph-align-{align}">'
            f'<span class="se-ff-nanumsquare {size} __se-node">{text}</span></p>')


def text_comp(lines, **kw):
    ps = "".join(para(t, **kw) for t in lines)
    return f'<div class="se-component se-text se-l-default"><div class="se-module se-module-text">{ps}</div></div>'


def quote_comp(lines, style="default", align="center"):
    ps = "".join(para(t, align=align) for t in lines)
    cite = ('<div class="se-module se-module-text se-is-empty se-cite"><p class="se-text-paragraph">'
            '<span class="se-ff-nanumgothic se-fs13 __se-node"></span>'
            '<span class="se-placeholder se-fs13">출처 입력</span></p></div>')
    return (f'<div class="se-component se-quotation se-l-{style}"><div class="se-quotation-container">'
            f'<div class="se-module se-module-text se-quote">{ps}</div>{cite}</div></div>')


def image_comp(n):
    imgs = "".join('<div class="se-module se-module-image"><img class="se-image-resource" src="x.jpg"/></div>'
                   for _ in range(n))
    kind, layout = ("se-image", "se-l-default") if n == 1 else ("se-imageGroup", "se-l-collage")
    # 사진 설명 칸은 비어 있으면 se-is-empty + 글씨 13이다 (발행 글에는 안 나온다)
    caption = ('<div class="se-module se-module-text se-is-empty"><p class="se-text-paragraph">'
               '<span class="se-fs13 __se-node"></span></p></div>')
    return f'<div class="se-component {kind} {layout}">{imgs}{caption}</div>'


def map_comp(name):
    return (f'<div class="se-component se-placesMap se-l-default"><img src="map.png"/>'
            f'<strong>{name}</strong><p>서울 어딘가</p></div>')


TITLE = '<div class="se-component se-documentTitle"><span class="se-fs32 __se-node">제목</span></div>'

BLOCKS = [
    {"type": "text", "value": "안녕하세요~!\n라멘 먹으러 왔어요 😊"},
    {"type": "quote", "value": "유카이도", "style": "default"},
    {"type": "map", "value": "유카이도"},
    {"type": "quote", "value": "🚩위치 : 구로\n⏳영업시간 : 11:00", "style": "quotation_line"},
    {"type": "image", "image_indices": [0, 1]},
    {"type": "text", "value": "국물이 진해요\n.\n또 올게요"},
    {"type": "image", "image_indices": [2]},
]


def good_parts():
    return [
        TITLE,
        text_comp(["안녕하세요~!", "라멘 먹으러 왔어요 😊"]),
        quote_comp(["유카이도"]),
        map_comp("유카이도"),
        quote_comp(["🚩 위치 : 구로", "⏳영업시간 : 11:00"], style="quotation_line", align="left"),
        image_comp(2),
        text_comp(["국물이 진해요", ".", "또 올게요"]),
        image_comp(1),
    ]


def html(parts):
    return "<html><body><div class='se-content'>" + "".join(parts) + "</div></body></html>"


class TestEditorCheck(unittest.TestCase):
    def test_good_editor_passes(self):
        # 세로줄 인용구는 왼쪽 정렬이 정상, 빈 출처·사진 설명 칸의 글씨 13은 무시, 이모지 앞 띄어쓰기 차이도 무시
        self.assertEqual(check_editor_html(html(good_parts()), BLOCKS, 3), [])

    def test_left_aligned_text(self):
        parts = good_parts()
        parts[1] = text_comp(["안녕하세요~!", "라멘 먹으러 왔어요 😊"], align="left")
        problems = check_editor_html(html(parts), BLOCKS, 3)
        self.assertEqual(len(problems), 1)
        self.assertIn("1번 글이 가운데 정렬이 아닙니다", problems[0])

    def test_wrong_font_size(self):
        parts = good_parts()
        parts[6] = text_comp(["국물이 진해요", ".", "또 올게요"], size="se-fs16")
        problems = check_editor_html(html(parts), BLOCKS, 3)
        self.assertEqual(len(problems), 1)
        self.assertIn("se-fs16", problems[0])

    def test_blank_lines_between_blocks(self):
        # 11/17 이전 봇: 블록마다 Enter를 여러 번 눌러 빈 줄 블록과 앞뒤 빈 줄이 생겼다
        parts = good_parts()
        parts[1] = text_comp(["", "안녕하세요~!", "라멘 먹으러 왔어요 😊", ""])
        parts.insert(2, text_comp([""]))
        problems = check_editor_html(html(parts), BLOCKS, 3)
        self.assertTrue(any("빈 줄만 있는 블록" in p for p in problems))
        self.assertTrue(any("1번 글 앞뒤에 빈 줄" in p for p in problems))
        self.assertFalse(any("줄이 다릅니다" in p or "줄 수가 다릅니다" in p for p in problems))

    def test_missing_line(self):
        parts = good_parts()
        parts[6] = text_comp(["국물이 진해요", "또 올게요"])
        problems = check_editor_html(html(parts), BLOCKS, 3)
        self.assertTrue(any("6번 글: 줄 수가 다릅니다 (초안 3줄, 편집기 2줄)" in p for p in problems))

    def test_wrong_quote_style(self):
        parts = good_parts()
        parts[4] = quote_comp(["🚩위치 : 구로", "⏳영업시간 : 11:00"], style="default")
        problems = check_editor_html(html(parts), BLOCKS, 3)
        self.assertTrue(any("4번 인용구 스타일이 다릅니다" in p for p in problems))

    def test_missing_photo_in_collage(self):
        parts = good_parts()
        parts[5] = image_comp(3)
        problems = check_editor_html(html(parts), BLOCKS, 3)
        self.assertIn("5번 사진 장수가 다릅니다 (초안 2장, 편집기 3장)", problems)

    def test_preview_only_photo_is_not_uploaded(self):
        # 11/19: 화면 밖 콜라주 칸은 data: 미리보기에서 멈춘다. 장수는 맞아도 올라가지 않은 사진으로 알린다.
        parts = good_parts()
        parts[5] = image_comp(2).replace('src="x.jpg"', 'src="data:image/jpeg;base64,AAAA"', 1)
        problems = check_editor_html(html(parts), BLOCKS, 3)
        self.assertIn("5번 사진 1장이 아직 네이버에 올라가지 않았습니다 (미리보기만 있음)", problems)
        self.assertFalse(any("사진 장수" in p for p in problems))

    def test_map_missing_shifts_order(self):
        # 지도 넣기에 실패하면 뒤 블록이 한 칸씩 당겨진다 → 블록 수와 종류가 다르다고 알리고 거기서 멈춘다
        parts = good_parts()
        del parts[3]
        problems = check_editor_html(html(parts), BLOCKS, 3)
        self.assertIn("블록 수가 다릅니다 (초안 7개, 편집기 6개)", problems)
        self.assertTrue(any("3번 블록 종류가 다릅니다" in p for p in problems))

    def test_map_wrong_place(self):
        parts = good_parts()
        parts[3] = map_comp("다른 가게")
        problems = check_editor_html(html(parts), BLOCKS, 3)
        self.assertTrue(any("3번 지도" in p for p in problems))

    def test_skipped_blocks_are_not_expected(self):
        # 봇이 건너뛰는 블록(빈 글, 범위 밖 사진만 있는 사진 블록)은 편집기에 없어도 된다
        blocks = BLOCKS + [{"type": "text", "value": ""}, {"type": "image", "image_indices": [9]}]
        self.assertEqual(check_editor_html(html(good_parts()), blocks, 3), [])

    def test_zero_width_paragraph_counts_as_blank(self):
        parts = good_parts()
        parts.insert(2, text_comp(["\u200b"]))
        problems = check_editor_html(html(parts), BLOCKS, 3)
        self.assertEqual(len(problems), 1)
        self.assertIn("빈 줄만 있는 블록", problems[0])


if __name__ == "__main__":
    unittest.main()
