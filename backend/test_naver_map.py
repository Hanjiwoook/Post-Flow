import time
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

def test_get_place_tabs_info(query: str):
    """사용자가 알아오신 '탭 순회' 로직을 적용한 고성능 테스트 스크립트 (f-string 문법 수정 버전)"""
    print(f"🚀 [Tab-Walking Test] Starting search for: {query}")
    
    with sync_playwright() as p:
        iphone_13 = p.devices['iPhone 13']
        # 눈으로 확인하기 위해 headless=False
        browser = p.chromium.launch(headless=False, slow_mo=500) 
        context = browser.new_context(**iphone_13)
        page = context.new_page()
        Stealth().apply_stealth_sync(page)

        try:
            # 1. 모바일 검색 및 플레이스 진입
            search_url = f"https://m.search.naver.com/search.naver?query={query}"
            print(f"🔗 접속 중: {search_url}")
            page.goto(search_url)
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            # 가게 제목 클릭 (텍스트 기반 검색 강화)
            print(f"🔍 [{query}] 플레이스 진입 시도 중...")
            
            # 1. 텍스트로 직접 찾기 (가장 확실함)
            # '싹쓰리곱창' 글자가 포함된 요소를 찾습니다.
            place_link = page.get_by_text(query, exact=False).first
            
            # 2. 만약 텍스트로 못 찾으면 기존 클래스 방식으로 재시도
            if not place_link.is_visible(timeout=5000):
                print("   ⚠️ 텍스트로 찾기 실패, 클래스 기반으로 재시도...")
                place_link = page.locator("a.tit, a._title, .place_item .name, .api_ani_send").first

            if place_link.is_visible(timeout=5000):
                print(f"   🖱️ 클릭 시도: {place_link.inner_text()}")
                # 스크롤해서 보이게 한 뒤 클릭
                place_link.scroll_into_view_if_needed()
                place_link.click(force=True)
                
                # 상세 페이지 로딩 대기 (URL 변화 감지)
                print("   ⏳ 상세 페이지 로딩 대기 중...")
                try:
                    page.wait_for_url("**/m.place.naver.com/**", timeout=10000)
                    time.sleep(3)
                except:
                    print("   ⚠️ URL 변화가 감지되지 않았지만 계속 진행합니다.")
            else:
                print("❌ 가게 링크를 끝내 찾지 못했습니다. 화면에 가게 이름이 떠 있는지 확인해주세요!")
                return

            # 데이터를 담을 그릇
            scraped_data = {"홈": "", "소식": "", "정보": "", "리뷰": ""}
            print("\n🚀 탭 순회 크롤링을 시작합니다...")

            # 2. 탭 순서대로 클릭하며 데이터 추출
            target_tabs = ["홈", "소식", "정보", "리뷰"]

            for tab_name in target_tabs:
                # 웹 접근성 표준(role="tab")을 활용해 정확하게 탭 찾기
                tab_element = page.get_by_role("tab", name=tab_name, exact=True)

                if tab_element.is_visible():
                    print(f"👉 [{tab_name}] 탭 클릭 중...")
                    tab_element.click()

                    # 탭 클릭 후 내용 렌더링 대기
                    page.wait_for_timeout(3000) # 리뷰 탭은 데이터 로딩 시간이 조금 더 필요할 수 있음

                    # 현재 화면의 텍스트 데이터 추출
                    content_text = page.locator("body").inner_text()

                    # 탭별 데이터 저장
                    scraped_data[tab_name] = content_text
                    print(f"✅ [{tab_name}] 데이터 추출 완료! ({len(content_text)}자)")
                else:
                    print(f"⚠️ [{tab_name}] 탭이 없습니다. 건너뜁니다.")
                    scraped_data[tab_name] = "탭 정보 없음"

            # 3. 최종 결과 출력 및 파일 저장
            print("\n" + "========================================")
            print(f"🎯 [{query}] 최종 크롤링 결과 요약")
            print(f"🏠 [홈] 데이터 길이: {len(scraped_data['홈'])}자")
            print(f"📢 [소식] 데이터 길이: {len(scraped_data['소식'])}자")
            print(f"ℹ️ [정보] 데이터 길이: {len(scraped_data['정보'])}자")
            print(f"💬 [리뷰] 데이터 길이: {len(scraped_data['리뷰'])}자")
            print("========================================\n")

            # 파일에 전체 내용 저장 (디버깅용)
            file_path = "debug_map_data.txt"
            with open(file_path, "w", encoding="utf-8") as f:
                for tab, content in scraped_data.items():
                    f.write(f"\n{'='*20} [{tab}] {'='*20}\n")
                    f.write(content)
                    f.write("\n\n")

            print(f"📂 전체 수집 데이터가 [{file_path}]에 저장되었습니다!")

            # 수집된 텍스트 중 일부 미리보기 (줄바꿈 제거 처리)
            review_preview = scraped_data['리뷰'][:100].replace('\n', ' ')
            print(f"📝 [리뷰] 미리보기: {review_preview}...")
            
            print("\n5초 후 브라우저를 종료합니다.")
            time.sleep(5)
            return scraped_data

        except Exception as e:
            print(f"❌ 에러 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    test_get_place_tabs_info("싹쓰리곱창 성수본점")
