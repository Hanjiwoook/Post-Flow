"""
블로그 포맷 규칙 검사기.

`docs/blog_format_spec.md`의 규칙 중 코드로 잴 수 있는 것만 검사한다.
(흐름이 자연스러운지, 사실을 지어냈는지 같은 판단은 AI 검토 단계에서 한다.)

- error  : 원본 블로그 글도 모두 지키는 형식. 하나라도 어기면 "형식이 다르다".
- warning: 원본 글에서도 가끔 벗어나는 경향. 참고용으로만 알려 준다.

기준 숫자는 2026-11-13에 원본 맛집 글 5편을 측정해서 정했다.
  - 한 줄 길이 중앙값 12~15자, 25자 넘는 줄 비율 최대 8.6%
  - 사진 묶음은 모두 1~3장, 2장 묶음 비율 52~75%
  - 이모지가 있는 줄 비율 8~19%, 한 줄 최대 3개

입력 블록은 두 형식을 모두 받는다.
  - 크롤러 형식: {"type": "image", "image_count": 2}
  - 앱 형식(ContentBlock): {"type": "image", "image_indices": [0, 1]}
"""
import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

ERROR = "error"
WARNING = "warning"

MAX_MEDIAN_LINE_LEN = 16
LONG_LINE_LEN = 25
MAX_LONG_LINE_RATIO = 0.10
MAX_IMAGE_GROUP = 3
MIN_PAIR_RATIO = 0.40
MAX_EMOJI_LINE_RATIO = 0.30
MAX_EMOJI_PER_LINE = 3
MAX_CONSECUTIVE_IMAGES = 2
MIN_CLOSING_DOT_LINES = 2

# 과장된 광고 말투 (명세서 4절). 원본 글에 한 번도 나오지 않는다.
HYPE_PHRASES = ["인생 맛집", "인생맛집", "미쳤다", "역대급", "강력 추천드립니다", "강력추천드립니다"]
# AI 같은 설명 말투. 원본에도 '특히'가 한 번 나오므로 여러 번 쓸 때만 경고한다.
AI_PHRASES = ["특히", "또한", "다양한 메뉴를 제공", "경험할 수 있"]
MAX_AI_PHRASES = 1

TITLE_TYPE_WORDS = ["맛집", "카페"]
TITLE_HOOK_WORDS = ["내돈내산", "솔직리뷰", "추천"]

_ZWSP = "​"
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⏳]")
_SECTION_TAG = re.compile(r"^\[[^\]]{1,20}\]")


@dataclass
class CheckResult:
    rule: str
    severity: str  # ERROR 또는 WARNING
    passed: bool
    detail: str


@dataclass
class FormatReport:
    results: List[CheckResult] = field(default_factory=list)

    @property
    def errors(self) -> List[CheckResult]:
        return [r for r in self.results if not r.passed and r.severity == ERROR]

    @property
    def warnings(self) -> List[CheckResult]:
        return [r for r in self.results if not r.passed and r.severity == WARNING]

    @property
    def passed(self) -> bool:
        """error 규칙을 모두 지켰는지. warning은 통과 여부에 영향을 주지 않는다."""
        return not self.errors

    def summary(self) -> str:
        lines = []
        for r in self.results:
            mark = "✅" if r.passed else ("❌" if r.severity == ERROR else "⚠️")
            lines.append(f"{mark} {r.rule}: {r.detail}")
        return "\n".join(lines)


# --- 블록 읽기 도우미 ---

def _to_dict(block: Any) -> Dict:
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return block.model_dump()
    return dict(block)


def _image_count(block: Dict) -> int:
    if block.get("image_count") is not None:
        return block["image_count"]
    if block.get("image_indices"):
        return len(block["image_indices"])
    return 1 if block.get("image_index") is not None else 0


def _raw_lines(block: Dict) -> List[str]:
    """글 블록의 줄 목록. 빈 줄은 빼고 '.' 줄은 남긴다."""
    value = (block.get("value") or "").replace(_ZWSP, "")
    return [line.strip() for line in value.split("\n") if line.strip()]


def _content_lines(text_blocks: List[Dict]) -> List[str]:
    """글 블록들의 실제 문장 줄 ('.' 구분 줄 제외)."""
    return [line for b in text_blocks for line in _raw_lines(b) if line != "."]


def _all_text(blocks: List[Dict]) -> str:
    return "\n".join(b.get("value") or "" for b in blocks if b["type"] in ("text", "quote"))


# --- 규칙 ---

def _check_no_section_tags(lines: List[str]) -> CheckResult:
    tagged = [line for line in lines if _SECTION_TAG.match(line)]
    return CheckResult("섹션 제목 없음", ERROR, not tagged,
                       f"[섹션명] 줄 {len(tagged)}개" if tagged else "없음")


def _check_no_divider(blocks: List[Dict]) -> CheckResult:
    count = sum(b["type"] == "divider" for b in blocks)
    return CheckResult("구분선 없음", ERROR, count == 0, f"구분선 {count}개")


def _check_no_hashtags_or_stars(lines: List[str]) -> CheckResult:
    bad = [line for line in lines if line.startswith("#") or "⭐⭐" in line]
    return CheckResult("해시태그·별점 기호 없음", ERROR, not bad,
                       f"{len(bad)}줄" if bad else "없음")


def _check_greeting(blocks: List[Dict]) -> CheckResult:
    first = blocks[0] if blocks else {}
    lines = _raw_lines(first) if first.get("type") == "text" else []
    ok = bool(lines) and lines[0].startswith("안녕하세요")
    return CheckResult("인사로 시작", ERROR, ok,
                       "첫 글이 '안녕하세요'로 시작" if ok else "첫 블록이 '안녕하세요'로 시작하는 글이 아님")


def _check_opening(blocks: List[Dict]) -> CheckResult:
    types = [b["type"] for b in blocks[:3]]
    ok = types == ["text", "quote", "map"]
    return CheckResult("도입부 순서", ERROR, ok,
                       "글 → 가게 이름 인용구 → 지도" if ok else f"앞 3블록이 {types}")


def _check_info_quote(blocks: List[Dict]) -> Optional[CheckResult]:
    # 여러 가게를 묶은 글(지도 2개 이상)은 정보 인용구를 생략한다 (명세서 1절)
    if sum(b["type"] == "map" for b in blocks) != 1:
        return None
    ok = any(b["type"] == "quote" and "🚩위치" in (b.get("value") or "").replace(" ", "")
             for b in blocks)
    return CheckResult("가게 정보 인용구", ERROR, ok, "🚩위치 인용구 있음" if ok else "🚩위치 인용구 없음")


def _check_line_length(lines: List[str]) -> CheckResult:
    if not lines:
        return CheckResult("짧은 줄", ERROR, False, "글 줄이 없음")
    lengths = [len(line) for line in lines]
    median = statistics.median(lengths)
    long_ratio = sum(n > LONG_LINE_LEN for n in lengths) / len(lengths)
    ok = median <= MAX_MEDIAN_LINE_LEN and long_ratio <= MAX_LONG_LINE_RATIO
    return CheckResult("짧은 줄", ERROR, ok,
                       f"중앙값 {median:g}자 (기준 {MAX_MEDIAN_LINE_LEN} 이하), "
                       f"{LONG_LINE_LEN}자 초과 {long_ratio:.0%} (기준 {MAX_LONG_LINE_RATIO:.0%} 이하)")


def _check_image_group_size(counts: List[int]) -> CheckResult:
    bad = [c for c in counts if not 1 <= c <= MAX_IMAGE_GROUP]
    return CheckResult("사진 묶음 1~3장", ERROR, not bad,
                       f"벗어난 묶음 {bad}" if bad else f"묶음 {len(counts)}개 모두 1~3장")


def _check_image_pair_ratio(counts: List[int]) -> Optional[CheckResult]:
    if not counts:
        return None
    ratio = sum(c == 2 for c in counts) / len(counts)
    return CheckResult("2장 묶음 위주", WARNING, ratio >= MIN_PAIR_RATIO,
                       f"2장 묶음 {ratio:.0%} (기준 {MIN_PAIR_RATIO:.0%} 이상)")


def _check_image_then_text(blocks: List[Dict]) -> CheckResult:
    consecutive = sum(a["type"] == "image" and b["type"] == "image" for a, b in zip(blocks, blocks[1:]))
    return CheckResult("사진 뒤에 글", WARNING, consecutive <= MAX_CONSECUTIVE_IMAGES,
                       f"사진 묶음이 연달아 온 곳 {consecutive}곳 (기준 {MAX_CONSECUTIVE_IMAGES} 이하)")


def _check_emoji(lines: List[str]) -> Optional[CheckResult]:
    if not lines:
        return None
    per_line = [len(_EMOJI.findall(line)) for line in lines]
    ratio = sum(n > 0 for n in per_line) / len(lines)
    ok = ratio <= MAX_EMOJI_LINE_RATIO and max(per_line) <= MAX_EMOJI_PER_LINE
    return CheckResult("이모지 절제", WARNING, ok,
                       f"이모지 있는 줄 {ratio:.0%} (기준 {MAX_EMOJI_LINE_RATIO:.0%} 이하), "
                       f"한 줄 최대 {max(per_line)}개 (기준 {MAX_EMOJI_PER_LINE} 이하)")


def _check_hype_phrases(text: str) -> CheckResult:
    found = [p for p in HYPE_PHRASES if p in text]
    return CheckResult("과장 표현 없음", ERROR, not found, f"발견: {found}" if found else "없음")


def _check_ai_phrases(text: str) -> CheckResult:
    counts = {p: text.count(p) for p in AI_PHRASES if p in text}
    total = sum(counts.values())
    return CheckResult("AI 말투 절제", WARNING, total <= MAX_AI_PHRASES,
                       f"{counts} (합계 {total}, 기준 {MAX_AI_PHRASES} 이하)" if counts else "없음")


def _check_closing(text_blocks: List[Dict]) -> CheckResult:
    if not text_blocks:
        return CheckResult("맺음말 앞 '.' 줄", ERROR, False, "글 블록이 없음")
    dots = _raw_lines(text_blocks[-1]).count(".")
    return CheckResult("맺음말 앞 '.' 줄", ERROR, dots >= MIN_CLOSING_DOT_LINES,
                       f"마지막 글의 '.' 줄 {dots}개 (기준 {MIN_CLOSING_DOT_LINES} 이상)")


def _check_title(title: str) -> CheckResult:
    has_type = any(w in title for w in TITLE_TYPE_WORDS)
    has_hook = any(w in title for w in TITLE_HOOK_WORDS)
    return CheckResult("검색용 제목", WARNING, has_type and has_hook,
                       f"맛집/카페 {'있음' if has_type else '없음'}, "
                       f"내돈내산/솔직리뷰/추천 {'있음' if has_hook else '없음'}")


SPONSOR_WORDS = ["협찬", "제공받"]


def _check_sponsor_disclosure(blocks: List[Dict], text_blocks: List[Dict], title: Optional[str]) -> CheckResult:
    """협찬 글: 첫 글 블록에 협찬 표시가 있고, 어디에도 '내돈내산'이 없어야 한다."""
    first = (text_blocks[0].get("value") or "") if text_blocks else ""
    disclosed = any(w in first for w in SPONSOR_WORDS)
    contradicts = "내돈내산" in _all_text(blocks) or "내돈내산" in (title or "")
    detail = []
    if not disclosed:
        detail.append("첫 글에 협찬 표시 없음")
    if contradicts:
        detail.append("'내돈내산' 표현 있음")
    return CheckResult("협찬 표시", ERROR, disclosed and not contradicts,
                       ", ".join(detail) if detail else "첫 글에 협찬 표시 있음")


def check_post(blocks: List[Any], title: Optional[str] = None, sponsored: bool = False) -> FormatReport:
    """글 블록(과 제목)이 블로그 포맷 규칙을 지키는지 검사한다. sponsored면 협찬 표시도 검사한다."""
    blocks = [_to_dict(b) for b in blocks]
    text_blocks = [b for b in blocks if b["type"] == "text"]
    lines = _content_lines(text_blocks)
    image_counts = [_image_count(b) for b in blocks if b["type"] == "image"]
    text = _all_text(blocks)

    results = [
        _check_greeting(blocks),
        _check_opening(blocks),
        _check_info_quote(blocks),
        _check_no_section_tags(lines),
        _check_no_divider(blocks),
        _check_no_hashtags_or_stars(lines),
        _check_line_length(lines),
        _check_image_group_size(image_counts),
        _check_image_pair_ratio(image_counts),
        _check_image_then_text(blocks),
        _check_emoji(lines),
        _check_hype_phrases(text),
        _check_ai_phrases(text),
        _check_closing(text_blocks),
    ]
    if title is not None:
        results.append(_check_title(title))
    if sponsored:
        results.append(_check_sponsor_disclosure(blocks, text_blocks, title))
    return FormatReport([r for r in results if r is not None])
