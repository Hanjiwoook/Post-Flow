import time
import os
import pyperclip
import json
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from app.core.config import settings

def inspect_editor():
    print("🚀 네이버 에디터 정밀 진단 시작...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        page = context.new_page()
        stealth = Stealth()
        stealth.apply_stealth_sync(page)

        # 1. 로그인
        print(f"🔄 로그인 중: {settings.NAVER_ID}")
        page.goto("https://nid.naver.com/nidlogin.login")
        page.click("#id")
        pyperclip.copy(settings.NAVER_ID)
        page.keyboard.press("Control+v")
        time.sleep(0.5)
        page.click("#pw")
        pyperclip.copy(settings.NAVER_PW)
        page.keyboard.press("Control+v")
        time.sleep(0.5)
        page.click("#log\.login")
        
        try:
            page.wait_for_url("https://www.naver.com/**", timeout=30000)
            print("✅ 로그인 성공")
        except:
            print("⚠️ 로그인이 지연되거나 다른 페이지로 이동했습니다.")

        # 2. 에디터 접속
        print("🚀 에디터 접속 중...")
        page.goto("https://blog.naver.com/ohuks_life?Redirect=Write&")
        
        # mainFrame 찾기
        time.sleep(5)
        target_frame = None
        for f in page.frames:
            if "mainFrame" in f.name:
                target_frame = f
                break
        
        if not target_frame:
            print("❌ mainFrame을 찾을 수 없습니다.")
            browser.close()
            return

        print("✅ 에디터 프레임 발견")
        time.sleep(3)

        # 3. 모든 요소 분석 (Screenshot)
        page.screenshot(path="debug_state_1_initial.png")
        
        # 4. 장애물(도움말, 팝업) 리스트 추출
        print("🔎 장애물 요소 찾는 중...")
        overlay_info = target_frame.evaluate("""
            () => {
                const results = [];
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    const isVisible = style.display !== 'none' && style.visibility !== 'hidden' && el.offsetWidth > 0;
                    if (isVisible && (parseInt(style.zIndex) > 100 || el.className.includes('help') || el.className.includes('popup') || el.className.includes('layer'))) {
                        results.push({
                            tag: el.tagName,
                            class: el.className,
                            id: el.id,
                            text: el.innerText.substring(0, 30).replace(/\\n/g, ' '),
                            zIndex: style.zIndex
                        });
                    }
                });
                return results;
            }
        """)
        
        for item in overlay_info:
            print(f"⚠️ 발견된 장애물: [z:{item['zIndex']}] {item['class']} | {item['text']}")

        # 5. 저장 버튼 클릭 테스트
        print("🔘 저장 버튼 클릭 테스트 중...")
        # '저장' 글자가 포함된 버튼 모두 찾기
        save_buttons = target_frame.locator("button:has-text('저장')")
        count = save_buttons.count()
        print(f"🔎 '저장' 텍스트 포함 버튼 개수: {count}")
        
        for i in range(count):
            btn = save_buttons.nth(i)
            print(f"  [{i}] class: {btn.get_attribute('class')} | visible: {btn.is_visible()}")
            if i == 0: # 첫 번째 버튼으로 테스트
                box = btn.bounding_box()
                print(f"  📍 클릭 좌표: {box}")
                btn.click(force=True)
                print("  🔘 클릭 명령 전송됨.")

        time.sleep(3)
        page.screenshot(path="debug_state_2_after_click.png")

        print("🏁 진단 종료. 생성된 사진들을 확인하세요.")
        browser.close()

if __name__ == "__main__":
    inspect_editor()
