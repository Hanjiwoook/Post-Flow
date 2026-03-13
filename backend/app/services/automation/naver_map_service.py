import time
import asyncio
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

class NaverMapService:
    def get_place_info(self, query: str):
        """성공한 '탭 순회' 로직을 적용하여 상세 정보를 수집"""
        print(f"🚀 [Naver Map] Deep Scanning for: {query}")
        
        with sync_playwright() as p:
            iphone_13 = p.devices['iPhone 13']
            # 실제 서비스에서는 headless=True (백그라운드)로 실행
            browser = p.chromium.launch(headless=True) 
            context = browser.new_context(**iphone_13)
            page = context.new_page()
            Stealth().apply_stealth_sync(page)

            try:
                # 1. 모바일 검색 및 플레이스 진입
                search_url = f"https://m.search.naver.com/search.naver?query={query}"
                page.goto(search_url)
                page.wait_for_load_state("networkidle")
                time.sleep(2)

                # 가게 제목 클릭 (텍스트 기반 검색)
                place_link = page.get_by_text(query, exact=False).first
                if place_link.is_visible(timeout=5000):
                    place_link.scroll_into_view_if_needed()
                    place_link.click(force=True)
                    page.wait_for_url("**/m.place.naver.com/**", timeout=15000)
                    time.sleep(2)
                else:
                    print(f"⚠️ [{query}] Link not found. Returning partial info.")
                    return {"place_name": query, "raw_text": "검색 결과 없음"}

                # 데이터를 담을 그릇
                scraped_data = {"홈": "", "소식": "", "정보": "", "리뷰": ""}
                
                # 2. 탭 순서대로 클릭하며 데이터 추출
                target_tabs = ["홈", "소식", "정보", "리뷰"]
                for tab_name in target_tabs:
                    tab_element = page.get_by_role("tab", name=tab_name, exact=True)
                    if tab_element.is_visible():
                        tab_element.click()
                        page.wait_for_timeout(2000) # 리뷰 탭은 데이터 로딩 시간이 조금 더 필요할 수 있음
                        scraped_data[tab_name] = page.locator("body").inner_text()
                
                # 3. 수집된 Raw Text를 하나로 합침 (AI 분석용)
                combined_text = f"--- [홈 정보] ---\n{scraped_data['홈']}\n\n"
                combined_text += f"--- [소식 정보] ---\n{scraped_data['소식']}\n\n"
                combined_text += f"--- [상세 정보] ---\n{scraped_data['정보']}\n\n"
                combined_text += f"--- [방문자 리뷰] ---\n{scraped_data['리뷰']}"

                return {
                    "place_name": query,
                    "raw_text": combined_text
                }

            except Exception as e:
                print(f"❌ Map Search Error: {e}")
                return {"place_name": query, "raw_text": str(e)}
            finally:
                browser.close()

naver_map_service = NaverMapService()
