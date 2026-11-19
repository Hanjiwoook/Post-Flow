"""
저장 직전 편집기 HTML을 초안 블록과 비교하는 자가 검사 (2026-11-18).

봇이 '저장'을 눌렀다는 것만으로는 성공이 아니었다. 11/17에 저장 직전 HTML을 손으로 비교해 보고서야
정렬·글씨 크기가 한 번도 적용되지 않았던 것을 찾았다. 그 비교를 코드로 옮긴 것이다.

브라우저 없이 HTML 문자열만 받는 순수 함수라서 가짜 HTML로 테스트할 수 있다.
검사 항목: 블록 순서·종류, 글 줄(빠진 줄), 블록 사이 빈 줄, 가운데 정렬, 글씨 크기 15, 사진 장수, 지도.
"""
import re

from bs4 import BeautifulSoup

FONT_SIZE = "se-fs15"          # 기준 블로그 글의 글씨 크기 (본문·인용구 모두)
ZERO_WIDTH = "\u200b\ufeff"    # 편집기가 빈 문단에 넣는 보이지 않는 글자


def _norm(text: str) -> str:
    """비교용: 공백과 보이지 않는 글자를 모두 뺀다 (편집기가 이모지 앞뒤 띄어쓰기를 다르게 보여 줄 수 있다)."""
    return re.sub(r"\s", "", "".join(ch for ch in text if ch not in ZERO_WIDTH))


def _kind(component) -> str:
    """편집기 블록 종류: se-text → 'text', se-imageGroup → 'imageGroup' 등."""
    for c in component.get("class", []):
        if c.startswith("se-") and c != "se-component" and not c.startswith("se-l-"):
            return c[3:]
    return "?"


def _layout(component) -> str:
    """인용구 스타일 등: se-l-quotation_line → 'quotation_line'."""
    return next((c[5:] for c in component.get("class", []) if c.startswith("se-l-")), "")


def _expected(blocks: list, image_count: int) -> list:
    """봇이 실제로 넣는 블록만, 편집기 기준 모양으로 바꾼다 (봇이 건너뛰는 빈 글·빈 사진 블록은 뺀다)."""
    out = []
    for no, b in enumerate(blocks, 1):
        t = b.get("type", "text")
        value = b.get("value") or ""
        if t == "text" and value:
            out.append({"no": no, "kind": "text", "lines": value.split("\n")})
        elif t == "quote" and value:
            out.append({"no": no, "kind": "quotation", "lines": value.split("\n"),
                        "style": b.get("style") or "default"})
        elif t == "image":
            indices = b.get("image_indices") or ([b["image_index"]] if b.get("image_index") is not None else [])
            n = sum(1 for i in indices if 0 <= i < image_count)
            if n:
                out.append({"no": no, "kind": "image" if n == 1 else "imageGroup", "photos": n})
        elif t == "map" and value:
            out.append({"no": no, "kind": "placesMap", "place": value})
        elif t == "divider":
            out.append({"no": no, "kind": "horizontalLine"})   # 구분선 이름표는 실제 편집기에서 아직 확인 안 함
    return out


def _check_lines(no: int, label: str, paragraphs: list, lines: list, problems: list):
    """초안의 줄과 편집기 문단을 한 줄씩 비교한다. 첫 번째 다른 줄만 알린다."""
    got = [_norm(p.get_text()) for p in paragraphs]
    want = [_norm(line) for line in lines]
    if got == want:
        return
    if len(got) != len(want):
        problems.append(f"{no}번 {label}: 줄 수가 다릅니다 (초안 {len(want)}줄, 편집기 {len(got)}줄)")
    for k, (g, w) in enumerate(zip(got, want), 1):
        if g != w:
            problems.append(f"{no}번 {label} {k}번째 줄이 다릅니다: 초안 '{w[:20]}' / 편집기 '{g[:20]}'")
            return


def check_editor_html(html: str, blocks: list, image_count: int) -> list:
    """
    문제 목록을 돌려준다 (빈 목록 = 통과). image_count는 봇에게 준 사진 파일 수다.
    """
    soup = BeautifulSoup(html, "html.parser")
    problems = []

    # 글씨 크기: 실제 글자가 있는 칸만 본다. 빈 출처 칸·사진 설명 칸(se-is-empty, se-fs13)은 발행 글에 안 나온다.
    for node in soup.select(".se-component .__se-node"):
        if node.find_parent(class_="se-is-empty") or node.find_parent(class_="se-documentTitle"):
            continue
        if _norm(node.get_text()) and FONT_SIZE not in node.get("class", []):
            size = next((c for c in node.get("class", []) if c.startswith("se-fs")), "기본")
            problems.append(f"글씨 크기가 15가 아닌 글자가 있습니다 ({size}): '{node.get_text(strip=True)[:20]}'")
            break  # 전체 선택으로 한 번에 맞추므로 하나가 틀리면 보통 여러 개가 틀린다

    actual = []
    for c in soup.select(".se-component"):
        kind = _kind(c)
        if kind == "documentTitle":
            continue
        if kind == "text" and not _norm(c.get_text()):
            problems.append(f"글 사이에 빈 줄만 있는 블록이 있습니다 ({len(actual) + 1}번째 블록 자리)")
            continue
        actual.append(c)

    expected = _expected(blocks, image_count)
    if len(actual) != len(expected):
        problems.append(f"블록 수가 다릅니다 (초안 {len(expected)}개, 편집기 {len(actual)}개)")

    for exp, comp in zip(expected, actual):
        no, kind = exp["no"], _kind(comp)
        if kind != exp["kind"]:
            problems.append(f"{no}번 블록 종류가 다릅니다 (초안 {exp['kind']}, 편집기 {kind}). 이후 블록은 비교하지 않습니다")
            break

        if kind == "text":
            ps = comp.select(".se-text-paragraph")
            blank = [not _norm(p.get_text()) for p in ps]
            if blank and (blank[0] or blank[-1]):
                problems.append(f"{no}번 글 앞뒤에 빈 줄이 있습니다")
            ps = [p for p, b in zip(ps, blank) if not b] if blank and (blank[0] or blank[-1]) else ps
            _check_lines(no, "글", ps, exp["lines"], problems)
            if any("se-text-paragraph-align-center" not in p.get("class", []) for p in ps):
                problems.append(f"{no}번 글이 가운데 정렬이 아닙니다")

        elif kind == "quotation":
            if _layout(comp) != exp["style"]:
                problems.append(f"{no}번 인용구 스타일이 다릅니다 (초안 {exp['style']}, 편집기 {_layout(comp)})")
            ps = comp.select(".se-quote .se-text-paragraph")
            _check_lines(no, "인용구", ps, exp["lines"], problems)
            # 세로줄 인용구 줄은 원래 왼쪽 정렬이다 (기준 블로그 글도 같음). 기본 인용구만 가운데인지 본다.
            if exp["style"] == "default" and any("se-text-paragraph-align-center" not in p.get("class", []) for p in ps):
                problems.append(f"{no}번 인용구가 가운데 정렬이 아닙니다")

        elif kind in ("image", "imageGroup"):
            imgs = comp.select(".se-module-image img.se-image-resource")
            n = len(imgs)
            if n != exp["photos"]:
                problems.append(f"{no}번 사진 장수가 다릅니다 (초안 {exp['photos']}장, 편집기 {n}장)")
            # 주소가 data:이면 내 컴퓨터의 미리보기일 뿐 네이버에 올라가지 않은 사진이다 (11/19, 3장 이상 콜라주에서 발견)
            pending = sum(1 for img in imgs if (img.get("src") or "").startswith("data:"))
            if pending:
                problems.append(f"{no}번 사진 {pending}장이 아직 네이버에 올라가지 않았습니다 (미리보기만 있음)")

        elif kind == "placesMap":
            if _norm(exp["place"]) not in _norm(comp.get_text()):
                problems.append(f"{no}번 지도에 '{exp['place']}'가 보이지 않습니다")

    return problems
