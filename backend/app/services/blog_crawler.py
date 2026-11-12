"""
NaverBlogCrawler - 네이버 블로그 공개 게시글 크롤러
로그인 불필요. 블로그 ID만 있으면 RSS + Playwright로 본문 텍스트 수집.
"""
import asyncio
import re
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from urllib.parse import urlparse, parse_qs

import httpx
from playwright.async_api import async_playwright


class NaverBlogCrawler:
    """네이버 블로그 공개 게시글 크롤러 (로그인 불필요)"""

    def __init__(self):
        self.rss_url_template = "https://rss.blog.naver.com/{blog_id}.xml"
        self.mobile_url_template = "https://m.blog.naver.com/{blog_id}/{post_no}"
        self.delay_seconds = 3  # 안티봇 대응 딜레이

    async def fetch_post_list(self, blog_id: str, max_posts: int = 5) -> List[Dict]:
        """
        RSS 피드에서 글 목록을 가져온다.
        반환: [{title, url, post_no, date}, ...]
        """
        rss_url = self.rss_url_template.format(blog_id=blog_id)
        print(f"📡 [Crawler] RSS 피드 요청: {rss_url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(rss_url, timeout=15)
            response.raise_for_status()

        # RSS XML 파싱
        root = ET.fromstring(response.text)
        
        # RSS 네임스페이스 처리
        items = root.findall('.//item')
        
        posts = []
        for item in items[:max_posts]:
            title = item.findtext('title', '').strip()
            link = item.findtext('link', '').strip()
            pub_date = item.findtext('pubDate', '').strip()
            
            # 포스트 번호 추출 (URL에서)
            post_no = self._extract_post_no(link, blog_id)
            
            if post_no:
                posts.append({
                    'title': title,
                    'url': link,
                    'post_no': post_no,
                    'date': pub_date,
                    'mobile_url': self.mobile_url_template.format(blog_id=blog_id, post_no=post_no)
                })
                print(f"  📝 [{len(posts)}] {title}")

        print(f"📋 [Crawler] 총 {len(posts)}개 포스트 발견")
        return posts

    def _extract_post_no(self, url: str, blog_id: str) -> Optional[str]:
        """URL에서 포스트 번호를 추출"""
        # 패턴 1: https://blog.naver.com/blogId/123456789
        match = re.search(r'blog\.naver\.com/[^/]+/(\d+)', url)
        if match:
            return match.group(1)
        
        # 패턴 2: ?logNo=123456789
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if 'logNo' in params:
            return params['logNo'][0]
        
        return None

    async def extract_post_content(self, mobile_url: str) -> str:
        """
        Playwright로 모바일 블로그 페이지에 접속해서 본문 텍스트를 추출한다.
        모바일 버전은 iframe이 없어서 추출이 더 쉽다.
        """
        print(f"🔍 [Crawler] 본문 추출 중: {mobile_url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
            )
            page = await context.new_page()
            
            try:
                await page.goto(mobile_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2000)  # 콘텐츠 로딩 대기
                
                # 모바일 블로그 본문 선택자들 (우선순위 순)
                selectors = [
                    'div.se-main-container',           # 스마트에디터 3.0
                    'div.post_ct',                     # 모바일 블로그 본문
                    'div.__se_component_area',         # 구버전 스마트에디터
                    'div.sect_dsc',                    # 또 다른 레이아웃
                    'article',                         # 일반 아티클
                ]
                
                content = ""
                for selector in selectors:
                    try:
                        element = page.locator(selector).first
                        if await element.count() > 0:
                            content = await element.inner_text()
                            if content and len(content.strip()) > 50:
                                break
                    except:
                        continue
                
                # 텍스트 정리
                content = self._clean_text(content)
                
                if content:
                    print(f"  ✅ 본문 추출 성공 ({len(content)}자)")
                else:
                    print(f"  ⚠️ 본문 추출 실패")
                
                return content
                
            except Exception as e:
                print(f"  ❌ 추출 오류: {e}")
                return ""
            finally:
                await browser.close()

    def _clean_text(self, text: str) -> str:
        """추출된 텍스트를 정리"""
        if not text:
            return ""
        
        # 연속 공백/줄바꿈 정리
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        # 너무 짧은 텍스트는 제외 (광고성 글이나 빈 글)
        if len(text) < 100:
            return ""
        
        return text

    async def crawl_all(self, blog_id: str, max_posts: int = 5) -> List[Dict]:
        """
        전체 파이프라인: RSS로 목록 수집 → Playwright로 본문 추출
        
        반환: [{title, url, date, content}, ...]
        """
        print(f"\n🚀 [Crawler] 크롤링 시작: blog_id='{blog_id}', max_posts={max_posts}")
        
        # 1. RSS에서 글 목록 수집
        posts = await self.fetch_post_list(blog_id, max_posts)
        
        if not posts:
            print("❌ [Crawler] RSS에서 글을 찾을 수 없습니다.")
            return []
        
        # 2. 각 포스트 본문 추출
        results = []
        for i, post in enumerate(posts):
            print(f"\n📖 [{i+1}/{len(posts)}] {post['title']}")
            
            content = await self.extract_post_content(post['mobile_url'])
            
            if content:
                results.append({
                    'title': post['title'],
                    'url': post['url'],
                    'date': post['date'],
                    'content': content
                })
            
            # 안티봇 딜레이 (마지막 글 제외)
            if i < len(posts) - 1:
                print(f"  ⏳ {self.delay_seconds}초 대기...")
                await asyncio.sleep(self.delay_seconds)
        
        print(f"\n✅ [Crawler] 크롤링 완료: {len(results)}/{len(posts)}개 성공")
        return results


# 싱글톤 인스턴스
blog_crawler = NaverBlogCrawler()
