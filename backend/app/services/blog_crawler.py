"""
NaverBlogCrawler - 네이버 블로그 공개 게시글 크롤러
로그인 불필요. 블로그 ID만 있으면 RSS로 글 목록을 받고,
PostView 페이지 HTML에서 본문을 '블록 단위'(글/사진/인용구/지도 등)로 추출한다.

브라우저(Playwright) 없이 일반 HTTP 요청만 사용한다.
PostView 페이지는 본문(se-main-container)이 서버에서 HTML로 렌더링되어 오기 때문이다.
"""
import asyncio
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup


# 네이버 스마트에디터 컴포넌트 클래스 → 우리 앱 블록 type
# (앱의 ContentBlock type: text, image, quote, divider, map 과 맞춘다)
_COMPONENT_TYPES = {
    "se-text": "text",
    "se-image": "image",
    "se-imageStrip": "image",
    "se-imageGroup": "image",
    "se-quotation": "quote",
    "se-placesMap": "map",
    "se-horizontalLine": "divider",
    "se-sticker": "sticker",
}

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _paragraph_text(container) -> str:
    """스마트에디터 문단(p.se-text-paragraph)들을 줄바꿈으로 이어 붙인다."""
    lines = []
    for p in container.select("p.se-text-paragraph"):
        # 빈 줄은 네이버가 zero-width space(\u200b)로 채워 둔다
        line = p.get_text().replace("\u200b", "").strip()
        lines.append(line)
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _component_kind(classes: List[str]) -> Optional[str]:
    """컴포넌트 div의 class 목록에서 'se-xxx' 종류를 찾는다."""
    for c in classes:
        if c in _COMPONENT_TYPES or c == "se-documentTitle":
            return c
    return None


def parse_post_blocks(html: str) -> List[Dict]:
    """
    PostView HTML에서 본문 블록을 순서대로 뽑는다.

    반환 예:
      {"type": "text",  "value": "안녕하세요~ ..."}
      {"type": "image", "image_count": 2, "value": "캡션(있으면)"}
      {"type": "quote", "value": "🚩 위치 : ...", "style": "quotation_line"}
      {"type": "map",   "value": "가게명", "address": "서울 ..."}
      {"type": "other", "kind": "se-oglink"}   # 아직 모르는 컴포넌트
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("div.se-main-container")
    if container is None:
        return []

    blocks: List[Dict] = []
    for comp in container.select("div.se-component"):
        classes = comp.get("class", [])
        kind = _component_kind(classes)

        if kind == "se-documentTitle":
            continue  # 제목은 RSS에서 따로 받는다
        if kind is None:
            other = next((c for c in classes if c.startswith("se-") and c != "se-component"), "unknown")
            blocks.append({"type": "other", "kind": other})
            continue

        block_type = _COMPONENT_TYPES[kind]

        if block_type == "text":
            text = _paragraph_text(comp)
            if text:
                blocks.append({"type": "text", "value": text})

        elif block_type == "image":
            caption_el = comp.select_one(".se-caption")
            block = {"type": "image", "image_count": len(comp.select("img.se-image-resource"))}
            caption = _paragraph_text(caption_el) if caption_el else ""
            if caption:
                block["value"] = caption
            blocks.append(block)

        elif block_type == "quote":
            # se-l-default(큰 따옴표형), se-l-quotation_line(세로줄형) 등 레이아웃 이름을 style로 둔다
            layout = next((c[len("se-l-"):] for c in classes if c.startswith("se-l-")), None)
            quote_el = comp.select_one(".se-quote") or comp
            blocks.append({"type": "quote", "value": _paragraph_text(quote_el), "style": layout})

        elif block_type == "map":
            title = comp.select_one(".se-map-title")
            address = comp.select_one(".se-map-address")
            blocks.append({
                "type": "map",
                "value": title.get_text(strip=True) if title else "",
                "address": address.get_text(strip=True) if address else "",
            })

        else:  # divider, sticker
            blocks.append({"type": block_type})

    return blocks


def blocks_to_text(blocks: List[Dict]) -> str:
    """블록 목록을 스타일 분석용 평문으로 바꾼다 (글과 인용구만)."""
    parts = [b["value"] for b in blocks if b["type"] in ("text", "quote") and b.get("value")]
    return "\n\n".join(parts)


class NaverBlogCrawler:
    """네이버 블로그 공개 게시글 크롤러 (로그인 불필요)"""

    def __init__(self):
        self.rss_url_template = "https://rss.blog.naver.com/{blog_id}.xml"
        self.post_view_url_template = "https://blog.naver.com/PostView.naver?blogId={blog_id}&logNo={post_no}"
        self.delay_seconds = 3  # 네이버에 부담을 주지 않도록 글 사이에 쉰다

    async def fetch_post_list(self, blog_id: str, max_posts: int = 5, category: Optional[str] = None) -> List[Dict]:
        """
        RSS 피드에서 글 목록을 가져온다. (RSS는 최신 글 일부만 담고 있다)
        category를 주면 그 카테고리 글만 고른다. (예: "맛집")
        반환: [{title, url, post_no, date, category}, ...]
        """
        rss_url = self.rss_url_template.format(blog_id=blog_id)
        print(f"📡 [Crawler] RSS 피드 요청")

        async with httpx.AsyncClient(headers=_HEADERS) as client:
            response = await client.get(rss_url, timeout=15)
            response.raise_for_status()

        # bytes로 넘겨서 XML 선언의 인코딩(UTF-8)을 그대로 따르게 한다
        root = ET.fromstring(response.content)

        posts = []
        for item in root.findall('.//item'):
            item_category = item.findtext('category', '').strip()
            if category and item_category != category:
                continue

            link = item.findtext('link', '').strip()
            post_no = self._extract_post_no(link)
            if not post_no:
                continue

            posts.append({
                'title': item.findtext('title', '').strip(),
                'url': link,
                'post_no': post_no,
                'date': item.findtext('pubDate', '').strip(),
                'category': item_category,
            })
            if len(posts) >= max_posts:
                break

        print(f"📋 [Crawler] 총 {len(posts)}개 포스트 발견")
        return posts

    def _extract_post_no(self, url: str) -> Optional[str]:
        """URL에서 포스트 번호를 추출"""
        # 패턴 1: https://blog.naver.com/blogId/123456789
        match = re.search(r'blog\.naver\.com/[^/?]+/(\d+)', url)
        if match:
            return match.group(1)

        # 패턴 2: ?logNo=123456789
        params = parse_qs(urlparse(url).query)
        if 'logNo' in params:
            return params['logNo'][0]

        return None

    async def fetch_post_blocks(self, client: httpx.AsyncClient, blog_id: str, post_no: str) -> List[Dict]:
        """글 하나의 PostView HTML을 받아 블록 목록으로 바꾼다. 실패하면 빈 목록."""
        url = self.post_view_url_template.format(blog_id=blog_id, post_no=post_no)
        try:
            response = await client.get(url, timeout=15)
            response.raise_for_status()
        except httpx.HTTPError as e:
            print(f"  ❌ 요청 실패: {e}")
            return []
        return parse_post_blocks(response.text)

    async def crawl_all(self, blog_id: str, max_posts: int = 5, category: Optional[str] = None) -> List[Dict]:
        """
        전체 파이프라인: RSS로 목록 수집 → 글마다 본문 블록 추출

        반환: [{title, url, date, category, blocks, content}, ...]
          - blocks: 글/사진/인용구/지도 순서가 담긴 블록 목록 (포맷 분석용)
          - content: 글과 인용구만 이어 붙인 평문 (말투 분석용, 기존 코드 호환)
        """
        print(f"\n🚀 [Crawler] 크롤링 시작: max_posts={max_posts}, category={category}")

        posts = await self.fetch_post_list(blog_id, max_posts, category)
        if not posts:
            print("❌ [Crawler] RSS에서 글을 찾을 수 없습니다.")
            return []

        results = []
        async with httpx.AsyncClient(headers=_HEADERS) as client:
            for i, post in enumerate(posts):
                print(f"\n📖 [{i+1}/{len(posts)}] {post['title']}")
                blocks = await self.fetch_post_blocks(client, blog_id, post['post_no'])
                content = blocks_to_text(blocks)

                # 너무 짧은 글(공지, 빈 글)은 학습 재료에서 뺀다
                if len(content) >= 100:
                    results.append({
                        'title': post['title'],
                        'url': post['url'],
                        'date': post['date'],
                        'category': post['category'],
                        'blocks': blocks,
                        'content': content,
                    })
                    print(f"  ✅ 블록 {len(blocks)}개, 본문 {len(content)}자")
                else:
                    print(f"  ⚠️ 본문이 너무 짧아 제외 ({len(content)}자)")

                if i < len(posts) - 1:
                    await asyncio.sleep(self.delay_seconds)

        print(f"\n✅ [Crawler] 크롤링 완료: {len(results)}/{len(posts)}개 성공")
        return results


# 싱글톤 인스턴스
blog_crawler = NaverBlogCrawler()
